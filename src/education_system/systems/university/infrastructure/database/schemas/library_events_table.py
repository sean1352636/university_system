"""The one definition of ``library_events`` and ``library_event_attendance``.

The two are defined together because an event is only half the feature: the
CLI's attendance and reporting screens join them, and a registration is
meaningless without the event it points at.

They had three disagreeing definitions on ``student_records.db``:

* the baseline migration created ``library_events`` with ``event_date`` and
  ``event_time`` ``NOT NULL`` and no ``status`` column — this is the shape the
  live table actually has, and it is the one reproduced here;
* the library CLI (``domain/services/library/menu.py``) declared a different
  column *order*, made the date and time nullable, and added ``status`` by
  ``ALTER`` afterwards. Because ``CREATE TABLE IF NOT EXISTS`` is a no-op on an
  existing table, that definition never took effect on a database the
  migration had already built — it only ever ran on a fresh one, which is how
  two shapes came to exist;
* the library GUI (``interfaces/gui/library/maintenance.py``) declared a third,
  without ``status`` at all and without ``library_event_attendance``, so
  whichever screen a user opened first decided the schema.

``library_event_attendance`` was declared only by the CLI, lazily, on the way
into its events menu. On the live database it was never created at all: the
``status`` column shows the CLI's ``ALTER`` did run once, but at that time the
attendance table had not been added to it yet. Every attendance and reporting
query therefore ran against a table that did not exist.

**These tables are now legacy.** Library events live in ``unified_events``
tagged ``source_type = 'library'`` (see
``tools/university/migrate_library_events.py``). This module is retained as the
record of the source shape and so the legacy tables can still be created and
read during the migration; new code should not write to them.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

#: The authoritative ``library_events`` shape — the baseline migration's
#: columns, in the baseline's order, plus ``status``.
LIBRARY_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS library_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_time TEXT NOT NULL,
    location TEXT,
    description TEXT,
    max_capacity INTEGER DEFAULT 50,
    registered_count INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TEXT,
    status TEXT DEFAULT 'scheduled'
)
"""

#: ``ON DELETE CASCADE`` is declared for databases that run with
#: ``PRAGMA foreign_keys = ON``. SQLite leaves foreign keys off by default and
#: this project does not turn them on globally, so a caller deleting an event
#: must still remove its attendance rows explicitly.
LIBRARY_EVENT_ATTENDANCE_SQL = """
CREATE TABLE IF NOT EXISTS library_event_attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    attendee_id TEXT NOT NULL,
    attendee_name TEXT,
    registered_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (event_id) REFERENCES library_events (event_id) ON DELETE CASCADE
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_library_event_attendance_event "
    "ON library_event_attendance (event_id)",
    "CREATE INDEX IF NOT EXISTS idx_library_events_date "
    "ON library_events (event_date)",
)

#: Values ``library_events.status`` is expected to hold.
EVENT_STATUSES = ("scheduled", "cancelled", "completed")
DEFAULT_EVENT_STATUS = "scheduled"


def ensure_library_events_schema(conn) -> None:
    """Create both tables if absent and backfill ``status``.

    Accepts a connection or a cursor — both expose ``execute`` — so it can join
    a caller's open transaction rather than opening a competing one against a
    WAL database. Idempotent; safe to call on every entry point.
    """
    try:
        conn.execute(LIBRARY_EVENTS_SQL)

        # The live table pre-dates ``status``; add it rather than assuming a
        # fresh CREATE ran.
        existing = {row[1] for row in conn.execute("PRAGMA table_info(library_events)")}
        if "status" not in existing:
            conn.execute(
                "ALTER TABLE library_events ADD COLUMN status TEXT DEFAULT 'scheduled'"
            )
            logger.info("Added library_events.status")

        conn.execute(LIBRARY_EVENT_ATTENDANCE_SQL)

        for statement in _INDEXES:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                logger.debug("library events index skipped: %s", statement)
    except sqlite3.Error:
        logger.exception("library events schema bootstrap failed")
        raise
