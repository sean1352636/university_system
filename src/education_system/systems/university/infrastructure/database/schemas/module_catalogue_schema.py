"""Module catalogue tables: specification, change control, programme
designations, exclusions, waitlist, teaching team and external examiners.

Shared by the alembic migration (``b4d6f8a1c3e5``) and by
:func:`apply_to_connection`, which the application layer calls before use so
a scratch or test database gets the same schema. Everything is idempotent.

Why these, and not the tables that look similar
-----------------------------------------------
* ``course_waitlist`` cannot hold a module waitlist: ``course_id`` is NOT
  NULL with a foreign key to ``courses``, ``student_id`` is an INTEGER, and
  ``added_at`` has no default. The catalogue's "join waitlist" insert into it
  could never succeed. ``module_waitlist`` is keyed the way enrolments are
  (``module_code`` + text ``student_id``).
* ``programme_modules`` keys on ``programmes.programme_id`` — a different
  programme register from the ``courses`` codes every module link uses — and
  only knows core / not core. ``module_programme_designations`` keys on the
  course code and distinguishes core (must pass), compulsory (must take) and
  optional.
* ``curr_module_descriptors`` belongs to Curriculum Specification's own
  programme register. ``module_specifications`` is one row per catalogue
  module. Learning outcomes reuse ``learning_outcomes`` (``module_code``,
  ``outcome_type = 'module'``).
* Deliveries (a module running in more than one term) reuse
  ``course_sections``, which the enrolment gate already enforces.
"""

from __future__ import annotations

STAFF_ROLES = ("leader", "lecturer", "tutor", "marker", "moderator")
DESIGNATIONS = ("core", "compulsory", "optional")

TABLES = (
    """CREATE TABLE IF NOT EXISTS module_specifications (
        module_code TEXT PRIMARY KEY,
        aims TEXT,
        indicative_content TEXT,
        teaching_methods TEXT,
        contact_hours REAL CHECK (contact_hours IS NULL OR contact_hours >= 0),
        independent_study_hours REAL
            CHECK (independent_study_hours IS NULL OR independent_study_hours >= 0),
        placement_hours REAL CHECK (placement_hours IS NULL OR placement_hours >= 0),
        reading_list TEXT,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS module_assessment_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_code TEXT NOT NULL,
        component TEXT NOT NULL,
        assessment_type TEXT,
        weight REAL NOT NULL CHECK (weight > 0 AND weight <= 100),
        size TEXT,
        outcomes TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_module_assessment_plan_module "
    "ON module_assessment_plan(module_code)",
    """CREATE TABLE IF NOT EXISTS module_change_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_code TEXT NOT NULL,
        summary TEXT NOT NULL,
        changes_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
        proposed_by TEXT NOT NULL,
        proposed_at TEXT NOT NULL DEFAULT (datetime('now')),
        decided_by TEXT,
        decided_at TEXT,
        decision_note TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_module_change_requests_module "
    "ON module_change_requests(module_code, status)",
    """CREATE TABLE IF NOT EXISTS module_change_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_code TEXT NOT NULL,
        field TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        changed_by TEXT,
        changed_at TEXT NOT NULL DEFAULT (datetime('now')),
        request_id INTEGER REFERENCES module_change_requests(id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_module_change_history_module "
    "ON module_change_history(module_code, changed_at)",
    """CREATE TABLE IF NOT EXISTS module_programme_designations (
        course_code TEXT NOT NULL,
        module_code TEXT NOT NULL,
        category TEXT NOT NULL CHECK (category IN ('core', 'compulsory', 'optional')),
        year_of_study INTEGER CHECK (year_of_study IS NULL OR year_of_study BETWEEN 0 AND 7),
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (course_code, module_code)
    )""",
    """CREATE TABLE IF NOT EXISTS module_exclusions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_code TEXT NOT NULL,
        excluded_module_code TEXT NOT NULL,
        reason TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (module_code, excluded_module_code),
        CHECK (module_code <> excluded_module_code)
    )""",
    """CREATE TABLE IF NOT EXISTS module_waitlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_code TEXT NOT NULL,
        student_id TEXT NOT NULL,
        section_id INTEGER,
        position INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'waiting'
            CHECK (status IN ('waiting', 'enrolled', 'removed')),
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        resolved_at TEXT,
        resolved_by TEXT,
        note TEXT
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_module_waitlist_waiting "
    "ON module_waitlist(module_code, student_id) WHERE status = 'waiting'",
    """CREATE TABLE IF NOT EXISTS module_staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_code TEXT NOT NULL,
        username TEXT NOT NULL,
        role TEXT NOT NULL
            CHECK (role IN ('leader', 'lecturer', 'tutor', 'marker', 'moderator')),
        hours REAL NOT NULL DEFAULT 0 CHECK (hours >= 0),
        academic_year TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (module_code, username, role, academic_year)
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_module_staff_one_leader "
    "ON module_staff(module_code, academic_year) WHERE role = 'leader'",
    "CREATE INDEX IF NOT EXISTS idx_module_staff_user ON module_staff(username)",
    """CREATE TABLE IF NOT EXISTS module_external_examiners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_code TEXT NOT NULL,
        examiner_id INTEGER NOT NULL REFERENCES external_examiners(examiner_id),
        academic_year TEXT NOT NULL DEFAULT '',
        assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (module_code, examiner_id, academic_year)
    )""",
)

#: (table, column, declaration) added when missing.
COLUMNS = (
    # FHEQ level: 3 foundation, 4-6 undergraduate years, 7 masters, 8 doctoral.
    ("modules", "level", "INTEGER"),
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    """Create everything missing. *execute* runs one SQL statement."""
    for ddl in TABLES:
        execute(ddl)
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` on an open connection, once per database file.

    Inside a caller's open transaction it applies without committing (and is
    not remembered), so it can never commit half of someone else's work; the
    caller's commit or rollback decides. In-memory databases are never
    remembered: a connection id can be reused by a new database.
    """
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)
