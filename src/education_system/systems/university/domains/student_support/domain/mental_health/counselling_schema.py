"""Tables for the counselling pathway (referral → triage → waiting list →
allocation → sessions → discharge) and its outcome measures.

Additive only: three new tables, new columns on the existing
``counselling_sessions`` (whose ``notes`` / ``outcome`` are already sealed by
``health.application.health.sealed_fields``) and the tables the pathway
reads being created as their owners create them if a fresh database lacks
them (``mental_health_counselors`` as ``health_wellness_schemas`` does,
``counseling_appointments`` as ``WellnessService`` does). No migration: the
pathway calls :func:`ensure` before it reads or writes.
"""

from __future__ import annotations

import threading

from education_system.systems.university.infrastructure.database import db as _db

_READY: set[str] = set()
_LOCK = threading.Lock()

_TABLES = (
    """CREATE TABLE IF NOT EXISTS mental_health_counselors (
        counselor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        specialization TEXT,
        qualifications TEXT,
        availability_schedule TEXT,
        max_daily_appointments INTEGER DEFAULT 8,
        is_active BOOLEAN DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS counseling_appointments (
        appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        appointment_date TEXT NOT NULL,
        appointment_time TEXT NOT NULL,
        counselor_name TEXT,
        appointment_type TEXT,
        status TEXT DEFAULT 'Scheduled',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students(student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS counselling_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        counsellor TEXT,
        session_date TEXT,
        notes TEXT,
        outcome TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",
    # One referral is one episode of care. reason / triage_notes /
    # discharge_summary are sealed by the pathway (wellbeing_bus.seal_text).
    """CREATE TABLE IF NOT EXISTS counselling_referrals (
        referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'self',
        referred_by TEXT NOT NULL,
        presenting_issue TEXT,
        reason TEXT,
        consent_to_contact INTEGER NOT NULL DEFAULT 1,
        referred_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'referred',
        risk_rating TEXT,
        priority INTEGER,
        pathway TEXT,
        triaged_by TEXT,
        triage_clinician TEXT,
        triaged_at TEXT,
        triage_notes TEXT,
        same_day_due TEXT,
        safeguarding_concern_id INTEGER,
        counsellor_id INTEGER REFERENCES mental_health_counselors(counselor_id),
        allocated_by TEXT,
        allocated_at TEXT,
        session_cap INTEGER NOT NULL DEFAULT 6,
        discharged_by TEXT,
        discharged_at TEXT,
        discharge_reason TEXT,
        discharge_summary TEXT,
        updated_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students(student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS counselling_measures (
        measure_id INTEGER PRIMARY KEY AUTOINCREMENT,
        referral_id INTEGER NOT NULL REFERENCES counselling_referrals(referral_id),
        student_id TEXT NOT NULL,
        measure TEXT NOT NULL,
        stage TEXT NOT NULL,
        session_id INTEGER,
        items TEXT NOT NULL,
        total INTEGER NOT NULL,
        band TEXT,
        risk_flag INTEGER NOT NULL DEFAULT 0,
        recorded_by TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS counselling_case_notes (
        note_id INTEGER PRIMARY KEY AUTOINCREMENT,
        referral_id INTEGER NOT NULL REFERENCES counselling_referrals(referral_id),
        student_id TEXT NOT NULL,
        note_type TEXT NOT NULL DEFAULT 'note',
        note TEXT,
        author TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_counselling_referrals_student "
    "ON counselling_referrals(student_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_counselling_referrals_status "
    "ON counselling_referrals(status, priority, referred_at)",
    "CREATE INDEX IF NOT EXISTS idx_counselling_measures_referral "
    "ON counselling_measures(referral_id, measure, stage)",
    "CREATE INDEX IF NOT EXISTS idx_counselling_case_notes_referral "
    "ON counselling_case_notes(referral_id)",
)

#: Columns the pathway adds to the existing session table.
_SESSION_COLUMNS = (
    ("referral_id", "INTEGER"),
    ("counsellor_id", "INTEGER"),
    ("session_number", "INTEGER"),
    ("session_stage", "TEXT"),
    ("session_time", "TEXT"),
    ("duration_minutes", "INTEGER DEFAULT 50"),
    ("mode", "TEXT"),
    ("status", "TEXT DEFAULT 'booked'"),
    ("appointment_id", "INTEGER"),
    ("recorded_by", "TEXT"),
    ("updated_at", "TEXT"),
)


def _columns(conn, table) -> set:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}  # nosec B608


def apply_to_connection(conn) -> None:
    for statement in _TABLES:
        conn.execute(statement)
    have = _columns(conn, "counselling_sessions")
    for name, kind in _SESSION_COLUMNS:
        if name not in have:
            # db-audit: ignore[DBW001] - names and types are module literals
            conn.execute(f"ALTER TABLE counselling_sessions ADD COLUMN {name} {kind}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_counselling_sessions_referral "
                 "ON counselling_sessions(referral_id)")


def ensure() -> None:
    """Create/extend the tables once per database file per process."""
    key = str(_db.DEFAULT_DB_PATH)
    if key in _READY:
        return
    with _LOCK:
        if key in _READY:
            return
        with _db.transaction() as conn:
            apply_to_connection(conn)
        _READY.add(key)
