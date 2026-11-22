"""Student search: per-user saved searches (optionally shared), the audit of
searches, exports, bulk actions and reports, and scheduled reports.

New tables rather than the legacy ``saved_searches`` / ``search_analytics``:
the former's key is ``search_id`` with a NOT NULL ``name`` the old code never
filled, and the latter is shared with the FAQ / resource / ticket searches.

Later: favourite students, follow-ups (marked from a search or a student,
with priority, due date and who closed them) and duplicate-pair decisions,
migration ``a7c9e1b3d5f2``.

Shared by migrations ``f9c1e3a5b7d0`` / ``a7c9e1b3d5f2`` and :func:`apply_to_connection`
(``university/application/students/search``). Idempotent.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS student_saved_searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        name TEXT NOT NULL,
        criteria_json TEXT NOT NULL,
        shared INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (owner, name)
    )""",
    """CREATE TABLE IF NOT EXISTS student_search_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL CHECK (action IN ('search', 'export', 'bulk', 'report')),
        criteria_json TEXT,
        result_count INTEGER,
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_student_search_audit_at ON student_search_audit (at)",
    """CREATE TABLE IF NOT EXISTS student_report_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        name TEXT NOT NULL,
        saved_search_id INTEGER REFERENCES student_saved_searches(id) ON DELETE CASCADE,
        frequency TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly')),
        recipients TEXT NOT NULL,
        fields_json TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        next_run_on TEXT NOT NULL,
        last_run_at TEXT,
        last_result TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS student_search_favourites (
        owner TEXT NOT NULL,
        student_id TEXT NOT NULL,
        note TEXT,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (owner, student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS student_followups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
        due_on TEXT,
        assigned_to TEXT,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        closed_by TEXT,
        closed_at TEXT,
        outcome TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_student_followups_status ON student_followups (status, due_on)",
    """CREATE TABLE IF NOT EXISTS student_duplicate_reviews (
        student_a TEXT NOT NULL,
        student_b TEXT NOT NULL,
        decision TEXT NOT NULL CHECK (decision IN ('not_duplicate', 'duplicate')),
        note TEXT,
        reviewed_by TEXT NOT NULL,
        reviewed_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (student_a, student_b)
    )""",
)


def apply(execute) -> None:
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
