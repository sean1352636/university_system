"""Student records: contact and entry details on ``students``, the
field-level change history, and erasure requests.

Shared by migrations ``e8b0d2f4a6c9`` / ``c9e1a3b5d7f2`` and :func:`apply_to_connection`
(``university/application/students/lifecycle`` and friends).
Idempotent.
"""

from __future__ import annotations

COLUMNS = (
    ("students", "personal_email", "TEXT"),
    ("students", "fee_status", "TEXT"),
    ("students", "entry_route", "TEXT"),
    ("students", "entry_override_reason", "TEXT"),
    # Add-form parity with the other systems (migration c9e1a3b5d7f2).
    ("students", "preferred_name", "TEXT"),
    ("students", "postcode", "TEXT"),
    ("students", "notes", "TEXT"),
    ("students", "address_line1", "TEXT"),
    ("students", "address_line2", "TEXT"),
    ("students", "town", "TEXT"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS student_record_changes (
        change_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        field TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        reason TEXT NOT NULL,
        actor_id TEXT,
        changed_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_student_record_changes_student ON student_record_changes "
    "(student_id, changed_at)",
    """CREATE TABLE IF NOT EXISTS student_erasure_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        case_reference TEXT NOT NULL,
        reason TEXT NOT NULL,
        requested_by TEXT NOT NULL,
        requested_at TEXT NOT NULL DEFAULT (datetime('now')),
        impact_json TEXT,
        status TEXT NOT NULL DEFAULT 'requested'
            CHECK (status IN ('requested', 'approved', 'rejected', 'completed')),
        decided_by TEXT,
        decided_at TEXT,
        decision_note TEXT,
        completed_by TEXT,
        completed_at TEXT
    )""",
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    if not _columns(execute, "students"):
        return
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in TABLES:
        execute(ddl)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file. Inside a caller's open
    transaction it applies without committing or caching."""
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
