"""Timetable additions: which delivery a weekly slot belongs to, which
teaching weeks it runs in, its online link, and one-off changes to a single
week's session.

Shared by migration ``c7e9a2b4d6f8`` and :func:`apply_to_connection` (used by
``university/application/teaching/occurrences`` so scratch and test
databases get the same schema). Idempotent.

* ``module_schedule.section_id`` — the ``course_sections`` delivery the slot
  is taught for. NULL means every delivery of the module.
* ``module_schedule.week_pattern`` — teaching weeks of the term, e.g.
  ``1-5,7-11`` to skip a reading week. NULL means every week.
* ``module_schedule.online_url`` — Teams / Zoom link for online or hybrid
  sessions.
* ``module_session_changes`` — one row per changed occurrence of a weekly
  slot: cancelled, or moved (to another date / time / room). Keyed on the
  slot and the date it would normally have run.
"""

from __future__ import annotations

ACTIONS = ("cancel", "move")

TABLES = (
    """CREATE TABLE IF NOT EXISTS module_session_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER NOT NULL REFERENCES module_schedule(id) ON DELETE CASCADE,
        session_date TEXT NOT NULL,
        action TEXT NOT NULL CHECK (action IN ('cancel', 'move')),
        new_date TEXT,
        new_start TEXT,
        new_end TEXT,
        new_room_id INTEGER REFERENCES rooms(id),
        reason TEXT NOT NULL,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (schedule_id, session_date),
        CHECK (action = 'cancel' OR new_date IS NOT NULL)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_module_session_changes_new_date "
    "ON module_session_changes(new_date)",
)

COLUMNS = (
    ("module_schedule", "section_id", "INTEGER"),
    ("module_schedule", "week_pattern", "TEXT"),
    ("module_schedule", "online_url", "TEXT"),
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    """Create everything missing. *execute* runs one SQL statement."""
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    if _columns(execute, "module_schedule"):
        for ddl in TABLES:
            execute(ddl)


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
