"""The academic calendar as one source of truth: academic years with a
draft → published cycle, their terms (written to ``academic_terms`` on
publish, which timetables, registers, registration and evaluation read),
key dates (enrolment, teaching, reading weeks, exams, resits, boards,
results, census dates, closures, bank holidays …), closures written to
``holidays``, the change log behind publish notices, calendar roles and
audit, personal calendar-feed tokens and event reminders, and the
``course_events`` link table (previously created at run time).

Shared by migration ``f7b9d1e3a5c8`` and :func:`apply_to_connection`
(``university/application/academic_calendar/``). Idempotent.
"""

from __future__ import annotations

COLUMNS = (
    ("academic_terms", "source", "TEXT"),
    ("academic_terms", "teaching_weeks", "INTEGER"),
    ("academic_terms", "sort_order", "INTEGER"),
    ("holidays", "source", "TEXT"),
    ("holidays", "year_code", "TEXT"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS calendar_years (
        year_code TEXT PRIMARY KEY,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
        version INTEGER NOT NULL DEFAULT 0,
        bank_holiday_region TEXT NOT NULL DEFAULT 'england-and-wales',
        published_at TEXT,
        published_by TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        notes TEXT,
        CHECK (end_date > start_date)
    )""",
    """CREATE TABLE IF NOT EXISTS calendar_terms (
        term_id INTEGER PRIMARY KEY AUTOINCREMENT,
        year_code TEXT NOT NULL REFERENCES calendar_years(year_code) ON DELETE CASCADE,
        name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        UNIQUE (year_code, name),
        CHECK (end_date > start_date)
    )""",
    """CREATE TABLE IF NOT EXISTS calendar_key_dates (
        key_date_id INTEGER PRIMARY KEY AUTOINCREMENT,
        year_code TEXT NOT NULL REFERENCES calendar_years(year_code) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        title TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT,
        audience TEXT NOT NULL DEFAULT 'all' CHECK (audience IN ('all', 'students', 'staff')),
        source TEXT NOT NULL DEFAULT 'manual',
        source_ref TEXT,
        notes TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_calendar_key_dates_year ON calendar_key_dates "
    "(year_code, start_date)",
    """CREATE TABLE IF NOT EXISTS calendar_published_snapshots (
        year_code TEXT NOT NULL,
        version INTEGER NOT NULL,
        snapshot_json TEXT NOT NULL,
        published_by TEXT,
        published_at TEXT NOT NULL DEFAULT (datetime('now')),
        changes_json TEXT,
        PRIMARY KEY (year_code, version)
    )""",
    """CREATE TABLE IF NOT EXISTS calendar_roles (
        username TEXT NOT NULL PRIMARY KEY,
        role TEXT NOT NULL DEFAULT 'calendar_admin' CHECK (role IN ('calendar_admin')),
        granted_by TEXT,
        granted_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS calendar_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor TEXT,
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS calendar_feed_tokens (
        token_hash TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        role TEXT,
        student_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_used_at TEXT,
        revoked_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS calendar_reminders (
        reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        event_id TEXT NOT NULL,
        remind_at TEXT NOT NULL,
        sent_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (username, event_id, remind_at)
    )""",
    # Per-person reminder preferences for calendar events. The calendar used to
    # create "notification_preferences" at run time, a name the baseline gives a
    # different (platform) table, so it has its own name.
    """CREATE TABLE IF NOT EXISTS calendar_notification_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        notification_type TEXT NOT NULL,
        enabled BOOLEAN DEFAULT TRUE,
        advance_time INTEGER DEFAULT 60,
        method TEXT DEFAULT 'email',
        date_added TEXT NOT NULL,
        UNIQUE(user_id, notification_type)
    )""",
    # Links calendar events to courses. It was created at run time (by the
    # calendar manager and the student-union schema); no migration made it.
    """CREATE TABLE IF NOT EXISTS course_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL,
        course_id TEXT NOT NULL,
        event_sub_type TEXT,
        date_added TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES unified_events(source_event_id) ON DELETE CASCADE,
        FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
        UNIQUE(event_id, course_id)
    )""",
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
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
