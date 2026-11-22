"""Storage for the Year 6 → Year 7 transition tables.

The tables live in the primary pupils database beside ``pupils``, which they
reference (``ON DELETE CASCADE``). The rules are in
``domain/learners/pupils/year6_transition.py``; this module owns the schema
and the connection.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

Error = sqlite3.Error

SCHEMA = """
CREATE TABLE IF NOT EXISTS y6_transition (
    pupil_id              TEXT NOT NULL,
    academic_year         TEXT NOT NULL,
    destination_type      TEXT NOT NULL DEFAULT '',
    destination_school    TEXT NOT NULL DEFAULT '',
    application_status    TEXT NOT NULL DEFAULT 'not_applied',
    applied_on            TEXT,
    offered_on            TEXT,
    offered_school        TEXT,
    accepted_on           TEXT,
    declined_on           TEXT,
    declined_reason       TEXT,
    transition_id         TEXT,
    consent_json          TEXT NOT NULL DEFAULT '{}',
    consent_given_by      TEXT,
    consent_on            TEXT,
    consent_method        TEXT,
    handover_approved_on  TEXT,
    handover_approved_by  TEXT,
    secondary_status      TEXT,
    secondary_note        TEXT,
    secondary_status_at   TEXT,
    moved_on              TEXT,
    secondary_pupil_id    TEXT,
    notes                 TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (pupil_id, academic_year),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS y6_transition_report (
    pupil_id              TEXT NOT NULL,
    academic_year         TEXT NOT NULL,
    strengths             TEXT,
    interests             TEXT,
    learning_style        TEXT,
    worries               TEXT,
    friendships_json      TEXT NOT NULL DEFAULT '[]',
    keep_apart_json       TEXT NOT NULL DEFAULT '[]',
    all_about_me          TEXT,
    teacher_comments      TEXT,
    enhanced_transition   INTEGER NOT NULL DEFAULT 0,
    enhanced_reason       TEXT,
    written_by            TEXT,
    written_on            TEXT,
    updated_at            TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (pupil_id, academic_year),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS y6_transition_visits (
    visit_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id              TEXT NOT NULL,
    academic_year         TEXT NOT NULL,
    visit_date            TEXT NOT NULL,
    visit_type            TEXT NOT NULL,
    school_name           TEXT,
    attended              INTEGER NOT NULL DEFAULT 1,
    notes                 TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS y6_safeguarding_transfers (
    transfer_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id              TEXT NOT NULL,
    academic_year         TEXT NOT NULL,
    has_file              INTEGER NOT NULL DEFAULT 1,
    sent_on               TEXT,
    sent_to_name          TEXT,
    sent_to_role          TEXT,
    sent_to_school        TEXT,
    method                TEXT,
    receipt_confirmed_on  TEXT,
    recorded_by           TEXT,
    notes                 TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, academic_year),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_y6_transition_year ON y6_transition(academic_year);
CREATE INDEX IF NOT EXISTS ix_y6_visits_year ON y6_transition_visits(academic_year, pupil_id);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """A connection to the pupils database (rows by name, foreign keys on).
    Use as ``with connect(path) as conn`` for a committed transaction."""
    os.makedirs(Path(db_path).parent, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(db_path: str | Path) -> None:
    """Create the Year 6 tables (idempotent)."""
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


__all__ = ["Error", "SCHEMA", "connect", "init_schema"]
