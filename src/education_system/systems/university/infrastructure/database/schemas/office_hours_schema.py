"""Office hours: appointment slots, booking rules, online sessions, one-off
cancellations, waitlist, meeting records, reminders and the directory link.

Shared by migration ``a4d6f8b2c3e5`` and :func:`apply_to_connection`
(``university/application/teaching/office_hours``). Idempotent.

* ``office_hours`` gains ``slot_minutes`` (NULL = drop-in for the whole
  block), ``mode`` (in_person / online / either) and ``online_url``, an
  optional ``module_code``, and per-block booking rules
  (``min_notice_hours``, ``cancel_cutoff_hours``, ``max_per_student_week``).
* ``office_hour_bookings`` gains the appointment's own ``slot_start`` /
  ``slot_end`` and ``mode``, the meeting record (``attendance``,
  ``meeting_notes``, ``actions``), ``reminder_sent_at`` and who cancelled
  and why.
* ``office_hour_exceptions`` — a single date a block does not run.
* ``office_hour_waitlist`` — students waiting for a place on a full date.
* ``staff_office_hours_directory.office_hour_id`` — the directory row that
  mirrors a bookable block, so the staff directory and the booking screen
  show the same office hours.
"""

from __future__ import annotations

MODES = ("in_person", "online", "either")
ATTENDANCE = ("attended", "no_show", "late_cancel")

COLUMNS = (
    ("office_hours", "slot_minutes", "INTEGER"),
    ("office_hours", "mode", "TEXT DEFAULT 'in_person'"),
    ("office_hours", "online_url", "TEXT"),
    ("office_hours", "module_code", "TEXT"),
    ("office_hours", "min_notice_hours", "INTEGER"),
    ("office_hours", "cancel_cutoff_hours", "INTEGER"),
    ("office_hours", "max_per_student_week", "INTEGER"),
    ("office_hour_bookings", "slot_start", "TEXT"),
    ("office_hour_bookings", "slot_end", "TEXT"),
    ("office_hour_bookings", "mode", "TEXT"),
    ("office_hour_bookings", "attendance", "TEXT"),
    ("office_hour_bookings", "meeting_notes", "TEXT"),
    ("office_hour_bookings", "actions", "TEXT"),
    ("office_hour_bookings", "recorded_by", "TEXT"),
    ("office_hour_bookings", "recorded_at", "TEXT"),
    ("office_hour_bookings", "reminder_sent_at", "TEXT"),
    ("office_hour_bookings", "cancelled_at", "TEXT"),
    ("office_hour_bookings", "cancelled_by", "TEXT"),
    ("office_hour_bookings", "cancel_reason", "TEXT"),
    ("staff_office_hours_directory", "office_hour_id", "INTEGER"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS office_hour_exceptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        office_hour_id INTEGER NOT NULL REFERENCES office_hours(id),
        exception_date TEXT NOT NULL,
        reason TEXT NOT NULL,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (office_hour_id, exception_date)
    )""",
    """CREATE TABLE IF NOT EXISTS office_hour_waitlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        office_hour_id INTEGER NOT NULL REFERENCES office_hours(id),
        booking_date TEXT NOT NULL,
        student_id TEXT NOT NULL,
        module_code TEXT,
        notes TEXT,
        position INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'waiting'
            CHECK (status IN ('waiting', 'booked', 'removed', 'expired')),
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        resolved_at TEXT
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_office_hour_waitlist_waiting ON "
    "office_hour_waitlist(office_hour_id, booking_date, student_id) WHERE status = 'waiting'",
    "CREATE INDEX IF NOT EXISTS idx_office_hour_bookings_date ON "
    "office_hour_bookings(office_hour_id, booking_date, status)",
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    if _columns(execute, "office_hours"):
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
