"""Declared column types that disagree with what they reference.

The 2026-10-18 schema audit found columns declared with the wrong type: a
``student_id`` declared INTEGER in 34 tables although ``students.student_id``
is TEXT, and 57 foreign keys whose column type differs from the column they
reference. SQLite compares values by storage class, so ``'5853694'`` and
``5853694`` are different keys; an INTEGER column also drops leading zeros.

:data:`PLAN` gives the corrected type of each column. The referenced column
is authoritative, with one exception found by looking at the data:
``unified_events.source_event_id`` was declared INTEGER but every one of its
values is a text key (``EXAM-9``, UUIDs), so it becomes TEXT and the eleven
columns that reference it keep their TEXT type (``workflow_events.event_id``,
the one INTEGER among them, becomes TEXT). ``student_id`` stays INTEGER where
it is really a foreign key to an integer person id
(``assignment_group_members`` → ``users.id``, ``research_theses`` →
``research_people.id``).

SQLite cannot change a column's type in place, so :func:`retype` rebuilds the
table: rename it aside with ``legacy_alter_table`` on (other tables' foreign
keys keep naming the original table), create it again from its own CREATE
statement with only the affected types changed, copy the rows with explicit
conversions, drop the old copy, and restore its indexes, triggers and
AUTOINCREMENT counter. A column whose values cannot be converted (text that
is not a whole number, for an INTEGER column) is left alone and reported.
Views and missing tables are skipped. Idempotent: a column already of the
right type is not touched.

Used by migration ``5e7a9c1d3f6b``.
"""

from __future__ import annotations

import re

_PARENT_ID = "TEXT"      # courses.id, parent_accounts.parent_id, parking_*.*, ...

PLAN: dict[str, dict[str, str]] = {
    # The referenced side was wrong: every stored value is text.
    "unified_events": {"source_event_id": "TEXT"},
    # student_id declared INTEGER; students.student_id is TEXT.
    **{table: {"student_id": "TEXT"} for table in (
        "accommodation_requests", "aid_packages", "applications",
        "assistive_tech_requests", "badge_issuances", "blockchain_credentials",
        "budget_line_items", "bursary_applications", "course_waitlist",
        "digital_badges", "disability_documentation", "disbursements", "documents",
        "election_votes", "exam_accommodations", "external_scholarships", "fafsa_data",
        "financial_aid_applications", "incidents", "parent_communications",
        "parent_conference_requests", "parent_conferences", "parent_document_access",
        "parent_student_links", "payment_schedules",
        "scholarship_awards", "study_room_bookings", "submission_drafts",
        "submission_receipts", "tutor_group_members", "unified_event_registrations",
        "verification_requests")},
}

# Foreign keys whose column type must follow the referenced column.
_FOLLOW_REFERENCED = {
    "courses": {"semester_id": "INTEGER"},                    # semesters.id
    "course_prerequisites": {"course_id": _PARENT_ID, "prerequisite_course_id": _PARENT_ID},
    "course_history": {"course_id": _PARENT_ID},
    "course_waitlist": {"course_id": _PARENT_ID},
    "course_analytics": {"course_id": _PARENT_ID},
    "course_schedule": {"course_id": _PARENT_ID},
    "evaluations": {"course_id": _PARENT_ID},
    "virtual_classrooms": {"course_id": _PARENT_ID},
    "parent_student_links": {"parent_id": _PARENT_ID},
    "parent_communications": {"parent_id": _PARENT_ID},
    "parent_conference_requests": {"parent_id": _PARENT_ID},
    "parent_conferences": {"parent_id": _PARENT_ID},
    "parent_document_access": {"parent_id": _PARENT_ID},
    "parent_portal_activity": {"parent_id": _PARENT_ID},
    "parking_occupancy": {"lot_id": _PARENT_ID},              # parking_lots.lot_id
    "violation_appeals": {"violation_id": _PARENT_ID},        # parking_violations
    "attendance_notifications": {"session_id": _PARENT_ID},   # attendance_sessions
    "workflow_events": {"workflow_id": _PARENT_ID,            # event_workflows.id
                        "event_id": "TEXT"},                  # unified_events.source_event_id
    "approval_requests": {"instance_id": "INTEGER"},          # workflow_instances
    "workflow_audit_log": {"instance_id": "INTEGER"},
    "restaurant_mobile_orders": {"order_id": "INTEGER"},      # orders.order_id
    "restaurant_offer_usage": {"order_id": "INTEGER", "customer_id": "INTEGER"},
    "user_timezone_preferences": {"user_id": "INTEGER"},      # users.id
    "shop_cart": {"product_id": "INTEGER"},                   # products.product_id
    "grocery_stock_movements": {"product_id": "INTEGER"},
    "grocery_transaction_items": {"product_id": "INTEGER", "transaction_id": "INTEGER"},
}
for _table, _changes in _FOLLOW_REFERENCED.items():
    PLAN.setdefault(_table, {}).update(_changes)

_CONSTRAINT_WORDS = {"PRIMARY", "NOT", "NULL", "UNIQUE", "CHECK", "DEFAULT", "COLLATE",
                     "REFERENCES", "GENERATED", "AS", "CONSTRAINT"}


def _base(declared) -> str:
    declared = (declared or "").upper()
    if "INT" in declared:
        return "INTEGER"
    if any(x in declared for x in ("CHAR", "TEXT", "CLOB")):
        return "TEXT"
    return declared


def _rewrite_type(sql, column, new_type):
    """``sql`` with ``column``'s declared type replaced; ``None`` if the
    column definition can't be found exactly once."""
    name = re.escape(column)
    pattern = re.compile(
        rf'((?:\(|,)\s*)("{name}"|`{name}`|\[{name}\]|\b{name}\b)(\s+)'
        r'([A-Za-z_]+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)', re.IGNORECASE)
    matches = [m for m in pattern.finditer(sql) if m.group(4).upper() not in _CONSTRAINT_WORDS]
    if len(matches) != 1:
        return None
    m = matches[0]
    return sql[:m.start(4)] + new_type + sql[m.end(4):]


def _convert(column, new_type) -> str:
    q = f'"{column}"'
    if new_type == "TEXT":
        return (f"CASE WHEN {q} IS NULL THEN NULL "
                f"WHEN typeof({q}) = 'real' AND {q} = CAST({q} AS INTEGER) "
                f"THEN CAST(CAST({q} AS INTEGER) AS TEXT) ELSE CAST({q} AS TEXT) END")
    return (f"CASE WHEN {q} IS NULL THEN NULL WHEN typeof({q}) = 'integer' THEN {q} "
            f"ELSE CAST(trim({q}) AS INTEGER) END")


def _convertible(execute, table, column, new_type) -> int:
    """How many values of ``column`` cannot become ``new_type``."""
    if new_type != "INTEGER":
        return 0
    q = f'"{column}"'
    return execute(
        f'SELECT COUNT(*) FROM "{table}" WHERE {q} IS NOT NULL AND NOT '  # nosec B608
        f"(typeof({q}) = 'integer' OR (typeof({q}) = 'text' AND trim({q}) <> '' AND "
        f"trim({q}) NOT GLOB '*[^0-9]*') OR (typeof({q}) = 'text' AND "
        f"substr(trim({q}), 1, 1) = '-' AND length(trim({q})) > 1 AND "
        f"substr(trim({q}), 2) NOT GLOB '*[^0-9]*'))").fetchone()[0]


def retype(execute, table, changes) -> dict:
    """Rebuild ``table`` so each column in ``changes`` has the given type.
    Returns ``{"table", "changed": [...], "skipped": [(column, reason)], "rows"}``."""
    report = {"table": table, "changed": [], "skipped": [], "rows": 0}
    row = execute("SELECT type, sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()
    if not row or row[0] != "table" or not row[1]:
        report["skipped"].append(("*", "not a table here"))
        return report
    sql = row[1]
    columns = [(r[1], r[2]) for r in execute(f'PRAGMA table_info("{table}")').fetchall()]
    current = dict(columns)
    todo = {}
    for column, new_type in changes.items():
        if column not in current:
            report["skipped"].append((column, "no such column"))
        elif _base(current[column]) == new_type:
            continue
        elif _convertible(execute, table, column, new_type):
            report["skipped"].append((column, f"values that are not {new_type}"))
        else:
            rewritten = _rewrite_type(sql, column, new_type)
            if rewritten is None:
                report["skipped"].append((column, "definition not found exactly once"))
            else:
                sql, todo[column] = rewritten, new_type
    if not todo:
        return report
    extras = [r[0] for r in execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type IN ('index', 'trigger') "
        "AND sql IS NOT NULL ORDER BY type", (table,)).fetchall()]
    seq = None
    if execute("SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'").fetchone():
        found = execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)).fetchone()
        seq = found[0] if found else None
    legacy = execute("PRAGMA legacy_alter_table").fetchone()[0]
    old = f"{table}__retype_old"
    execute("PRAGMA legacy_alter_table = ON")
    try:
        execute(f'ALTER TABLE "{table}" RENAME TO "{old}"')
        execute(sql)
        names = ", ".join(f'"{c}"' for c, _t in columns)
        values = ", ".join(_convert(c, todo[c]) if c in todo else f'"{c}"' for c, _t in columns)
        execute(f'INSERT INTO "{table}" ({names}) SELECT {values} FROM "{old}"')  # nosec B608
        report["rows"] = execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]  # nosec B608
        execute(f'DROP TABLE "{old}"')
        for ddl in extras:
            execute(ddl)
        if seq is not None:
            if execute("SELECT 1 FROM sqlite_sequence WHERE name = ?", (table,)).fetchone():
                execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = ?",
                        (seq, table))
            else:
                execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (table, seq))
    finally:
        execute(f"PRAGMA legacy_alter_table = {'ON' if legacy else 'OFF'}")
    report["changed"] = sorted(todo)
    return report


def apply(execute) -> list[dict]:
    """Every table in :data:`PLAN`; returns the per-table reports.

    The rebuild renames each table aside. With foreign-key enforcement on,
    SQLite rewrites the child tables' REFERENCES to follow that rename
    (``legacy_alter_table`` does not stop it), so dropping the renamed copy
    would break every link to it. Enforcement is therefore switched off for
    the rebuild and restored afterwards; inside an open transaction that
    cannot be done (the pragma is a no-op there), so the rebuild refuses
    instead of corrupting the links. Alembic's connection runs with
    enforcement off, which is the normal path."""
    enforced = bool(execute("PRAGMA foreign_keys").fetchone()[0])
    if enforced:
        execute("PRAGMA foreign_keys = OFF")
        if execute("PRAGMA foreign_keys").fetchone()[0]:
            raise RuntimeError("Column types can't be rebuilt with foreign keys enforced inside "
                               "an open transaction; run it on a connection with "
                               "foreign_keys off (as Alembic does).")
    try:
        return [retype(execute, table, changes) for table, changes in sorted(PLAN.items())]
    finally:
        if enforced:
            execute("PRAGMA foreign_keys = ON")
