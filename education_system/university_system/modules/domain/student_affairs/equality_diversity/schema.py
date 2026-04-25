"""Schema + idempotent migrations for the Equality & Diversity module.

All tables are prefixed ``ed_`` and live in the main university DB. The
migration runner is safe to call repeatedly from any entry point.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Iterable

from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- allow-list of all fields callers may pivot/sort on (feature 5, 19–21) ----
DEMOGRAPHIC_FIELDS = (
    "person_type", "department", "age_group", "gender", "ethnicity",
    "disability", "religion", "sexual_orientation", "nationality",
)
SORTABLE_RECORD_COLUMNS = (
    "id", "ref_code", "person_type", "department", "age_group", "gender",
    "ethnicity", "disability", "religion", "sexual_orientation",
    "nationality", "date_added",
)

# feature 25 — lightweight HESA-style representation baselines
DEFAULT_BASELINES = {
    "gender": {"Female": 57.0, "Male": 42.0, "Non-binary": 0.5, "Other": 0.3, "Prefer not to say": 0.2},
    "ethnicity": {
        "White - British": 63.0, "White - Other": 10.0, "Asian - Indian": 4.0,
        "Asian - Pakistani": 2.5, "Asian - Chinese": 3.0, "Asian - Other": 2.5,
        "Black - African": 4.0, "Black - Caribbean": 2.0, "Mixed": 4.0,
        "Arab": 1.0, "Other": 2.0, "Prefer not to say": 2.0,
    },
    "disability": {
        "No known disability": 82.0, "Mental health": 5.0, "Learning difficulty": 4.0,
        "Physical": 2.0, "Sensory": 1.0, "Long-term health condition": 3.0,
        "Multiple": 1.0, "Prefer not to say": 2.0,
    },
}

_DDL = [
    # core tables (superset of what gui.py creates — safe to re-run)
    """
    CREATE TABLE IF NOT EXISTS ed_people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_code TEXT UNIQUE NOT NULL,
        person_type TEXT NOT NULL,
        department TEXT,
        age_group TEXT,
        gender TEXT,
        ethnicity TEXT,
        disability TEXT,
        religion TEXT,
        sexual_orientation TEXT,
        nationality TEXT,
        date_added TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ed_incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_reported TEXT NOT NULL,
        category TEXT NOT NULL,
        department TEXT,
        description TEXT,
        status TEXT DEFAULT 'Open',
        reported_by TEXT
    )
    """,
    # feature 31 — E&D-specific audit trail (also mirrored to main audit_log)
    """
    CREATE TABLE IF NOT EXISTS ed_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        entity TEXT NOT NULL,
        entity_id TEXT,
        details TEXT
    )
    """,
    # feature 11 — attachments on incidents
    """
    CREATE TABLE IF NOT EXISTS ed_incident_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        uploaded_by TEXT,
        uploaded_at TEXT,
        FOREIGN KEY (incident_id) REFERENCES ed_incidents(id) ON DELETE CASCADE
    )
    """,
    # feature 13 — investigation notes
    """
    CREATE TABLE IF NOT EXISTS ed_incident_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        ts TEXT NOT NULL,
        note_type TEXT,
        body TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES ed_incidents(id) ON DELETE CASCADE
    )
    """,
    # feature 4 — soft-delete restore queue + feature 40 — two-person approvals
    """
    CREATE TABLE IF NOT EXISTS ed_deletions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        snapshot TEXT NOT NULL,
        requested_by TEXT NOT NULL,
        requested_at TEXT NOT NULL,
        approved_by TEXT,
        approved_at TEXT,
        status TEXT DEFAULT 'pending_restore',
        hard_deleted_at TEXT
    )
    """,
    # feature 6 — saved searches per user
    """
    CREATE TABLE IF NOT EXISTS ed_saved_searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        name TEXT NOT NULL,
        query TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(owner, name)
    )
    """,
    # feature 7 — column preferences per user
    """
    CREATE TABLE IF NOT EXISTS ed_column_prefs (
        owner TEXT PRIMARY KEY,
        prefs TEXT NOT NULL
    )
    """,
    # feature 42 — view log (read receipts)
    """
    CREATE TABLE IF NOT EXISTS ed_view_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        viewer TEXT NOT NULL,
        viewed_at TEXT NOT NULL
    )
    """,
    # feature 45 — consent state per person
    """
    CREATE TABLE IF NOT EXISTS ed_consent (
        person_id INTEGER PRIMARY KEY,
        consent_flags TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (person_id) REFERENCES ed_people(id) ON DELETE CASCADE
    )
    """,
    # feature 46 — anonymous self-ID tokens
    """
    CREATE TABLE IF NOT EXISTS ed_anonymous_tokens (
        token TEXT PRIMARY KEY,
        issued_by TEXT,
        issued_at TEXT NOT NULL,
        used_at TEXT,
        expires_at TEXT
    )
    """,
    # feature 24 — scheduled reports
    """
    CREATE TABLE IF NOT EXISTS ed_report_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        cadence TEXT NOT NULL,
        field TEXT NOT NULL,
        format TEXT NOT NULL DEFAULT 'pdf',
        output_dir TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_run_at TEXT,
        next_run_at TEXT
    )
    """,
    # feature 25 — stored baselines (populated on first run from DEFAULT_BASELINES)
    """
    CREATE TABLE IF NOT EXISTS ed_benchmarks (
        field TEXT NOT NULL,
        category TEXT NOT NULL,
        baseline_pct REAL NOT NULL,
        source TEXT,
        PRIMARY KEY (field, category)
    )
    """,
    # helpful indexes
    "CREATE INDEX IF NOT EXISTS ix_ed_people_deleted ON ed_people(ref_code)",
    "CREATE INDEX IF NOT EXISTS ix_ed_audit_entity ON ed_audit_log(entity, entity_id)",
    "CREATE INDEX IF NOT EXISTS ix_ed_view_entity ON ed_view_log(entity, entity_id)",
    "CREATE INDEX IF NOT EXISTS ix_ed_notes_incident ON ed_incident_notes(incident_id)",
]

# feature 1/4/10/26/29/44 — columns added to ed_people after initial release
_PEOPLE_COLUMNS = [
    ("user_id", "INTEGER"),
    ("student_id", "TEXT"),
    ("staff_id", "INTEGER"),
    ("salary", "REAL"),
    ("hours_per_week", "REAL"),
    ("accommodations", "TEXT"),
    ("self_updated_at", "TEXT"),
    ("deleted_at", "TEXT"),
    ("deleted_by", "TEXT"),
    ("updated_at", "TEXT"),
    ("updated_by", "TEXT"),
]

# feature 14/15/16/17 — columns added to ed_incidents
_INCIDENT_COLUMNS = [
    ("severity", "TEXT"),
    ("sla_deadline", "TEXT"),
    ("assigned_to", "TEXT"),
    ("respondent", "TEXT"),
    ("witnesses", "TEXT"),
    ("outcome", "TEXT"),
    ("resolution_category", "TEXT"),
    ("lessons_learned", "TEXT"),
    ("anonymous", "INTEGER DEFAULT 0"),
    ("referred_to", "TEXT"),
    ("referred_at", "TEXT"),
]


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: Iterable[tuple[str, str]]) -> None:
    have = _existing_columns(conn, table)
    for name, decl in columns:
        if name not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def _seed_benchmarks(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT COUNT(*) FROM ed_benchmarks")
    if cur.fetchone()[0]:
        return
    rows = [
        (field, cat, pct, "HESA-style default")
        for field, cats in DEFAULT_BASELINES.items()
        for cat, pct in cats.items()
    ]
    conn.executemany(
        "INSERT INTO ed_benchmarks (field, category, baseline_pct, source) VALUES (?, ?, ?, ?)",
        rows,
    )


def migrate() -> None:
    """Create/extend all E&D tables. Idempotent."""
    conn = get_connection()
    try:
        for stmt in _DDL:
            conn.execute(stmt)
        _add_missing_columns(conn, "ed_people", _PEOPLE_COLUMNS)
        _add_missing_columns(conn, "ed_incidents", _INCIDENT_COLUMNS)
        _seed_benchmarks(conn)
        conn.commit()
    finally:
        conn.close()


def dump_schedule_config(name: str, cadence: str, field: str, fmt: str, output_dir: str) -> str:
    """Serialise a schedule config to JSON (used by the scheduler)."""
    return json.dumps({
        "name": name, "cadence": cadence, "field": field, "format": fmt, "output_dir": output_dir,
    })
