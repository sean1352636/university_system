"""Tables for Disabled Students' Allowances casework (``dsa``) and personal
emergency evacuation plans (``peeps``). Additive only; created on first use.
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.database import db as _db

_READY: set = set()

DSA_DDL = (
    """CREATE TABLE IF NOT EXISTS dsa_cases (
        case_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        funding_body TEXT NOT NULL DEFAULT 'SFE',
        sfe_reference TEXT,
        status TEXT NOT NULL DEFAULT 'not_applied',
        applied_date TEXT,
        eligibility_date TEXT,
        assessment_booked_date TEXT,
        assessed_date TEXT,
        dsa2_date TEXT,
        support_in_place_date TEXT,
        closed_date TEXT,
        notes TEXT,
        created_by TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
    "CREATE INDEX IF NOT EXISTS idx_dsa_cases_student ON dsa_cases(student_id)",
    """CREATE TABLE IF NOT EXISTS dsa_status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES dsa_cases(case_id),
        from_status TEXT, to_status TEXT NOT NULL,
        changed_by TEXT, changed_at TEXT DEFAULT CURRENT_TIMESTAMP, note TEXT)""",
    """CREATE TABLE IF NOT EXISTS dsa_needs_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES dsa_cases(case_id),
        centre TEXT, assessor TEXT,
        assessment_date TEXT NOT NULL, assessment_time TEXT,
        mode TEXT DEFAULT 'in person',
        attended INTEGER,
        notes TEXT,
        booked_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS dsa_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES dsa_cases(case_id),
        category TEXT NOT NULL,
        recommendation TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'recommended',
        accommodation_id INTEGER,
        created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS dsa_nmh_support (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES dsa_cases(case_id),
        worker_name TEXT, agency TEXT,
        support_type TEXT NOT NULL,
        band TEXT,
        hours_allocated REAL NOT NULL DEFAULT 0,
        start_date TEXT, end_date TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS dsa_nmh_hours (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        support_id INTEGER NOT NULL REFERENCES dsa_nmh_support(id),
        session_date TEXT NOT NULL,
        hours REAL NOT NULL,
        notes TEXT,
        logged_by TEXT, logged_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS dsa_equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES dsa_cases(case_id),
        item TEXT NOT NULL, supplier TEXT,
        ordered_date TEXT, delivered_date TEXT, training_date TEXT,
        status TEXT NOT NULL DEFAULT 'recommended',
        notes TEXT,
        created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS dsa_exam_arrangements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES dsa_cases(case_id),
        student_id TEXT NOT NULL,
        extra_percent INTEGER NOT NULL DEFAULT 0,
        separate_room INTEGER NOT NULL DEFAULT 0,
        rest_breaks INTEGER NOT NULL DEFAULT 0,
        reader INTEGER NOT NULL DEFAULT 0,
        scribe INTEGER NOT NULL DEFAULT 0,
        assistive_technology TEXT,
        other TEXT,
        valid_from TEXT, valid_to TEXT,
        status TEXT NOT NULL DEFAULT 'recommended',
        accommodation_id INTEGER,
        applied_by TEXT, applied_at TEXT,
        withdrawn_reason TEXT,
        created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS dsa_case_adjustments (
        case_id INTEGER NOT NULL REFERENCES dsa_cases(case_id),
        accommodation_id INTEGER NOT NULL,
        linked_by TEXT, linked_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (case_id, accommodation_id))""",
)

PEEP_DDL = (
    """CREATE TABLE IF NOT EXISTS peeps (
        peep_id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_type TEXT NOT NULL CHECK (person_type IN ('student', 'staff')),
        person_ref TEXT NOT NULL,
        person_name TEXT,
        locations TEXT NOT NULL DEFAULT '[]',
        assistance_needed TEXT NOT NULL,
        evacuation_method TEXT,
        equipment TEXT,
        refuge_points TEXT,
        alarm_method TEXT,
        other_notes TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        review_date TEXT,
        manager_username TEXT,
        last_reviewed_by TEXT, last_reviewed_at TEXT,
        reminder_sent_for TEXT,
        created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
    "CREATE INDEX IF NOT EXISTS idx_peeps_person ON peeps(person_type, person_ref)",
    """CREATE TABLE IF NOT EXISTS peep_buddies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        peep_id INTEGER NOT NULL REFERENCES peeps(peep_id),
        name TEXT NOT NULL,
        contact TEXT,
        notes TEXT)""",
)


def _key(kind) -> tuple:
    return (kind, str(_db.DEFAULT_DB_PATH))


def ensure(kind: str = "dsa") -> None:
    """Create the ``kind`` ('dsa' / 'peeps') tables once per database."""
    if _key(kind) in _READY:
        return
    statements = DSA_DDL if kind == "dsa" else PEEP_DDL
    with _db.transaction() as conn:
        for sql in statements:
            conn.execute(sql)
    _READY.add(_key(kind))
