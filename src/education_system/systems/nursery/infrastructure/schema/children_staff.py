"""Children on roll (pupils + parity columns), staff and rooms.

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations

import sqlite3


# ``pupils`` = the children on roll. Early Years settings group children by
# room/age band and assign each a key person (EYFS statutory requirement),
# alongside funded-hours and welfare details.
_PUPILS_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupils (
    pupil_id        TEXT PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    date_of_birth   TEXT,
    room            TEXT,
    key_person      TEXT,
    funded_hours    TEXT,
    start_date      TEXT,
    parent_name     TEXT,
    parent_phone    TEXT,
    parent_email    TEXT,
    allergies       TEXT,
    medical_notes   TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (key_person) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pupils_room   ON pupils(room);
CREATE INDEX IF NOT EXISTS idx_pupils_status ON pupils(status);
"""

# Parity with the primary and secondary schools' Add Pupil (2026-11-05): the
# child record asks the same identity / address / needs / parent questions,
# so a child reads the same on both sides of the nursery -> Reception
# handover. ``start_date`` is the admission date and ``status`` stays the
# active/left roll flag; ``left_date`` / ``exit_reason`` record why a child
# left. Existing databases gain the columns on the next init_db().
PUPILS_PARITY_COLUMNS = (
    ("middle_names", "TEXT"),
    ("preferred_name", "TEXT"),
    ("gender", "TEXT"),
    ("upn", "TEXT"),
    ("address_line1", "TEXT"),
    ("address_line2", "TEXT"),
    ("town", "TEXT"),
    ("postcode", "TEXT"),
    ("sen_status", "TEXT"),
    ("fsm_eligible", "INTEGER NOT NULL DEFAULT 0"),
    ("eal", "INTEGER NOT NULL DEFAULT 0"),
    ("notes", "TEXT"),
    ("parent_relationship", "TEXT"),
    ("left_date", "TEXT"),
    ("exit_reason", "TEXT"),
)


def _migrate_pupils(conn: sqlite3.Connection) -> None:
    """Add the parity columns to an older ``pupils`` table. Idempotent."""
    have = {row[1] for row in conn.execute("PRAGMA table_info(pupils)")}
    for name, decl in PUPILS_PARITY_COLUMNS:
        if name not in have:
            conn.execute(f"ALTER TABLE pupils ADD COLUMN {name} {decl}")  # nosec B608 - constant
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_nursery_pupils_upn "
        "ON pupils(upn) WHERE upn IS NOT NULL")

# ``staff`` = nursery practitioners and management. Tracks the welfare-critical
# flags an Ofsted-registered setting must evidence: DSL, paediatric first aid
# and DBS checks.
_STAFF_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    staff_id              TEXT PRIMARY KEY,
    first_name            TEXT NOT NULL,
    last_name             TEXT NOT NULL,
    title                 TEXT,
    role                  TEXT NOT NULL DEFAULT 'Nursery Practitioner',
    room                  TEXT,
    employment_status     TEXT NOT NULL DEFAULT 'Full-time',
    email                 TEXT NOT NULL,
    work_phone            TEXT,
    start_date            TEXT,
    end_date              TEXT,
    is_dsl                INTEGER NOT NULL DEFAULT 0,
    is_paediatric_first_aider INTEGER NOT NULL DEFAULT 0,
    dbs_checked           INTEGER NOT NULL DEFAULT 0,
    qualifications        TEXT,
    notes                 TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_nursery_staff_email ON staff(email);
CREATE INDEX IF NOT EXISTS idx_nursery_staff_role         ON staff(role);
CREATE INDEX IF NOT EXISTS idx_nursery_staff_status       ON staff(employment_status);
"""

# ``rooms`` = the age-banded base rooms an Early Years setting groups children
# into. Each carries the EYFS staff:child ratio that applies to its age band
# (under 2 → 1:3, two-year-olds → 1:4, three-and-over → 1:8/1:13) plus a
# capacity. Live occupancy is derived by matching ``pupils.room`` to ``name``.
_ROOMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    room_id         TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    age_group       TEXT,
    min_age_months  INTEGER,
    max_age_months  INTEGER,
    capacity        INTEGER NOT NULL DEFAULT 0,
    staff_ratio     TEXT,
    room_leader     TEXT,
    location        TEXT,
    notes           TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (room_leader) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
"""
