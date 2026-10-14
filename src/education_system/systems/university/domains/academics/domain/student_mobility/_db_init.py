"""Idempotent schema bootstrap for Student Mobility (study abroad / exchange).

Study abroad existed in this codebase only as an interest tag in social
matching and a filter in the scholarship finder. Nothing recorded that a
student was actually away, where, under which agreement, what they were
supposed to study there, or — the part that bites — what credit came back
and whether anyone recognised it.

Four tables on the central university DB:

* ``mobility_agreements``        — exchange places available under a deal
* ``mobility_placements``        — one student's period away (or with us)
* ``mobility_learning_agreements`` — the module-by-module study plan
* ``mobility_credit_recognitions`` — host credit mapped onto our own

``mobility_agreements.partner_id`` soft-links to ``partner_institutions``
from collaborative provision when that partner has been set up there; a
free-text ``host_institution`` covers the case where it has not.
"""

from __future__ import annotations

import logging

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    sqlite3,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

OUTGOING = "outgoing"
INCOMING = "incoming"
DIRECTIONS = (OUTGOING, INCOMING)

MOBILITY_TYPES = (
    "Semester Exchange",
    "Full Year Exchange",
    "Summer School",
    "Study Tour",
    "Work Placement Abroad",
    "Research Visit",
    "Field Trip",
    "Virtual Exchange",
)

# Funding routes. Erasmus+ is listed because incoming students still
# arrive on it; UK outgoing mobility runs on Turing.
FUNDING_SCHEMES = (
    "Turing Scheme",
    "Erasmus+ (incoming)",
    "Bilateral Agreement",
    "Institutional Bursary",
    "Self-Funded",
    "Employer-Funded",
    "Other",
)

# The lifecycle of a placement, in order.
APPLIED = "Applied"
NOMINATED = "Nominated"
ACCEPTED = "Accepted by Host"
APPROVED = "Approved"
IN_PROGRESS = "In Progress"
RETURNED = "Returned"
COMPLETED = "Completed"
CANCELLED = "Cancelled"
WITHDRAWN = "Withdrawn"

PLACEMENT_STATUSES = (
    APPLIED, NOMINATED, ACCEPTED, APPROVED, IN_PROGRESS, RETURNED,
    COMPLETED, CANCELLED, WITHDRAWN,
)

# Statuses in which the student is, or has been, physically away. Used by
# the "who is abroad right now" view and by credit-recognition chasing.
AWAY_STATUSES = frozenset({IN_PROGRESS})
CONCLUDED_STATUSES = frozenset({RETURNED, COMPLETED})

LEARNING_AGREEMENT_STATES = (
    "Draft",
    "Awaiting Home Approval",
    "Awaiting Host Approval",
    "Signed",
    "Amended",
    "Rejected",
)

# What we do with a grade earned elsewhere. "Pass/fail only" is the common
# institutional default — credit transfers, the mark does not.
RECOGNITION_MODES = (
    "Credit only (pass/fail)",
    "Credit and converted mark",
    "Not counted towards award",
)

RECOGNITION_STATES = (
    "Awaiting Transcript",
    "Transcript Received",
    "Recognised",
    "Partially Recognised",
    "Not Recognised",
    "Disputed",
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_AGREEMENTS = """
CREATE TABLE IF NOT EXISTS mobility_agreements (
    mobility_agreement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id            INTEGER,
    host_institution      TEXT    NOT NULL,
    country               TEXT,
    mobility_type         TEXT,
    subject_area          TEXT,
    level                 TEXT,
    places_outgoing       INTEGER DEFAULT 0,
    places_incoming       INTEGER DEFAULT 0,
    language_of_tuition   TEXT,
    language_requirement  TEXT,
    valid_from            TEXT,
    valid_to              TEXT,
    coordinator           TEXT,
    active                INTEGER NOT NULL DEFAULT 1,
    notes                 TEXT,
    created_at            TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_PLACEMENTS = """
CREATE TABLE IF NOT EXISTS mobility_placements (
    placement_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id            TEXT    NOT NULL,
    direction             TEXT    NOT NULL DEFAULT 'outgoing',
    mobility_agreement_id INTEGER,
    host_institution      TEXT,
    host_country          TEXT,
    mobility_type         TEXT,
    funding_scheme        TEXT,
    grant_amount          REAL,
    academic_year         TEXT,
    start_date            TEXT,
    end_date              TEXT,
    status                TEXT    NOT NULL DEFAULT 'Applied',
    home_programme        TEXT,
    host_programme        TEXT,
    credits_expected      REAL,
    credits_recognised    REAL DEFAULT 0,
    recognition_mode      TEXT,
    recognition_state     TEXT DEFAULT 'Awaiting Transcript',
    insurance_confirmed   INTEGER NOT NULL DEFAULT 0,
    risk_assessed         INTEGER NOT NULL DEFAULT 0,
    coordinator           TEXT,
    notes                 TEXT,
    created_at            TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mobility_agreement_id)
        REFERENCES mobility_agreements(mobility_agreement_id) ON DELETE SET NULL
);
"""

_CREATE_LEARNING_AGREEMENTS = """
CREATE TABLE IF NOT EXISTS mobility_learning_agreements (
    line_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    placement_id        INTEGER NOT NULL,
    host_module_code    TEXT,
    host_module_title   TEXT    NOT NULL,
    host_credits        REAL,
    host_credit_system  TEXT DEFAULT 'ECTS',
    home_module_code    TEXT,
    home_module_title   TEXT,
    home_credits        REAL,
    state               TEXT    NOT NULL DEFAULT 'Draft',
    approved_by_home    TEXT,
    approved_by_host    TEXT,
    approved_at         TEXT,
    amendment_of        INTEGER,
    notes               TEXT,
    created_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (placement_id)
        REFERENCES mobility_placements(placement_id) ON DELETE CASCADE
);
"""

_CREATE_RECOGNITIONS = """
CREATE TABLE IF NOT EXISTS mobility_credit_recognitions (
    recognition_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    placement_id        INTEGER NOT NULL,
    line_id             INTEGER,
    host_module_code    TEXT,
    host_grade          TEXT,
    host_credits        REAL,
    home_module_code    TEXT,
    home_credits        REAL,
    converted_mark      REAL,
    mode                TEXT,
    outcome             TEXT    NOT NULL DEFAULT 'Recognised',
    recognised_by       TEXT,
    recognised_at       TEXT,
    notes               TEXT,
    created_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (placement_id)
        REFERENCES mobility_placements(placement_id) ON DELETE CASCADE,
    FOREIGN KEY (line_id)
        REFERENCES mobility_learning_agreements(line_id) ON DELETE SET NULL
);
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_mobility_agreement_active "
    "ON mobility_agreements(active);",
    "CREATE INDEX IF NOT EXISTS idx_mobility_agreement_country "
    "ON mobility_agreements(country);",
    "CREATE INDEX IF NOT EXISTS idx_mobility_placement_student "
    "ON mobility_placements(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_mobility_placement_status "
    "ON mobility_placements(status);",
    "CREATE INDEX IF NOT EXISTS idx_mobility_placement_dates "
    "ON mobility_placements(start_date, end_date);",
    "CREATE INDEX IF NOT EXISTS idx_mobility_la_placement "
    "ON mobility_learning_agreements(placement_id);",
    "CREATE INDEX IF NOT EXISTS idx_mobility_recognition_placement "
    "ON mobility_credit_recognitions(placement_id);",
)

_TRIGGER_TOUCH_PLACEMENT = """
CREATE TRIGGER IF NOT EXISTS mobility_placements_touch
AFTER UPDATE ON mobility_placements
BEGIN
    UPDATE mobility_placements SET updated_at = CURRENT_TIMESTAMP
     WHERE placement_id = NEW.placement_id;
END;
"""

# Keep the placement's recognised-credit total in step with its
# recognition rows. Doing it in a trigger means a recognition entered
# through any interface — GUI, CLI, API — updates the total.
_TRIGGER_ROLLUP_INSERT = """
CREATE TRIGGER IF NOT EXISTS mobility_recognition_rollup_insert
AFTER INSERT ON mobility_credit_recognitions
BEGIN
    UPDATE mobility_placements
       SET credits_recognised = (
               SELECT COALESCE(SUM(home_credits), 0)
                 FROM mobility_credit_recognitions
                WHERE placement_id = NEW.placement_id
                  AND outcome IN ('Recognised', 'Partially Recognised'))
     WHERE placement_id = NEW.placement_id;
END;
"""

_TRIGGER_ROLLUP_DELETE = """
CREATE TRIGGER IF NOT EXISTS mobility_recognition_rollup_delete
AFTER DELETE ON mobility_credit_recognitions
BEGIN
    UPDATE mobility_placements
       SET credits_recognised = (
               SELECT COALESCE(SUM(home_credits), 0)
                 FROM mobility_credit_recognitions
                WHERE placement_id = OLD.placement_id
                  AND outcome IN ('Recognised', 'Partially Recognised'))
     WHERE placement_id = OLD.placement_id;
END;
"""


def ensure_student_mobility_schema(db_path=None) -> None:
    """Create the mobility tables, indexes and triggers if missing. Idempotent."""
    path = str(db_path or UNIVERSITY_DEFAULT_DB_PATH)
    try:
        conn = get_connection(path)
    except sqlite3.Error:
        logger.exception("could not open %s for student mobility bootstrap", path)
        return
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for stmt in (_CREATE_AGREEMENTS, _CREATE_PLACEMENTS,
                     _CREATE_LEARNING_AGREEMENTS, _CREATE_RECOGNITIONS,
                     *_INDEXES, _TRIGGER_TOUCH_PLACEMENT,
                     _TRIGGER_ROLLUP_INSERT, _TRIGGER_ROLLUP_DELETE):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                logger.exception("student mobility bootstrap failed: %s",
                                 stmt.strip().split("\n", 1)[0])
        conn.commit()
    finally:
        conn.close()


__all__ = [
    "OUTGOING", "INCOMING", "DIRECTIONS", "MOBILITY_TYPES", "FUNDING_SCHEMES",
    "PLACEMENT_STATUSES", "APPLIED", "NOMINATED", "ACCEPTED", "APPROVED",
    "IN_PROGRESS", "RETURNED", "COMPLETED", "CANCELLED", "WITHDRAWN",
    "AWAY_STATUSES", "CONCLUDED_STATUSES", "LEARNING_AGREEMENT_STATES",
    "RECOGNITION_MODES", "RECOGNITION_STATES",
    "ensure_student_mobility_schema",
]
