"""Idempotent schema bootstrap for the Fitness to Practise module.

Owns four tables on the central university DB:

* ``ftp_cases``      — one row per FtP case
* ``ftp_concerns``   — concerns raised against the case (multi-row)
* ``ftp_events``     — chronological audit trail (stage transitions,
                       hearings, correspondence with the regulator)
* ``ftp_outcomes``   — committee/panel decisions and sanctions

A trigger mirrors the case ``stage`` onto the parent
``disciplinary_records.status`` when the case was escalated from one,
so the disciplinary portal sees FtP progression without polling.
"""
from __future__ import annotations

import logging
import sqlite3

from education_system.university_system.modules.shared.constants.paths import (
    DEFAULT_DB_PATH,
)

logger = logging.getLogger(__name__)


# Regulators recognised by the case form. Free-text "Other" is allowed
# at the GUI layer; this list just drives the dropdown ordering.
REGULATORS = (
    "NMC",   # Nursing & Midwifery Council
    "HCPC",  # Health & Care Professions Council
    "GMC",   # General Medical Council
    "GPhC",  # General Pharmaceutical Council
    "GDC",   # General Dental Council
    "GOC",   # General Optical Council
    "GOsC",  # General Osteopathic Council
    "GCC",   # General Chiropractic Council
    "SWE",   # Social Work England
    "GTC",   # General Teaching Council
    "SRA",   # Solicitors Regulation Authority
    "BSB",   # Bar Standards Board
    "Other",
)

# FtP stages — chosen to match the common pattern across NMC/HCPC/GMC
# guidance. Not every regulator uses every stage; the portal lets users
# skip directly to the relevant one.
STAGES = (
    "Concern Raised",
    "Initial Assessment",
    "Investigation",
    "Case Examiner Review",
    "Interim Order Considered",
    "Pending Hearing",
    "At Hearing",
    "Outcome Issued",
    "Appeal",
    "Closed",
)

# Concern categories. The four canonical pillars of FtP across all UK
# health/care regulators, plus criminal conviction (always a referral
# trigger) and a free-text catch-all.
CONCERN_CATEGORIES = (
    "Health",
    "Conduct",
    "Competence",
    "Professionalism",
    "Criminal Conviction / Caution",
    "Safeguarding",
    "Other",
)

# Outcome vocabulary. Ordered roughly from least to most severe; the
# GUI shows them in this order in the dropdown.
OUTCOMES = (
    "No Case to Answer",
    "Advice",
    "Warning",
    "Undertakings Accepted",
    "Conditions of Practice",
    "Caution Order",
    "Suspension",
    "Removal from Programme",
    "Referral to Regulator",
    "Striking-Off / Removal from Register",
)


_CREATE_FTP_CASES = """
CREATE TABLE IF NOT EXISTS ftp_cases (
    case_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT    NOT NULL,
    programme          TEXT,
    regulator          TEXT,
    registration_no    TEXT,
    stage              TEXT    NOT NULL DEFAULT 'Concern Raised',
    risk_level         TEXT    DEFAULT 'Medium',
    interim_order      TEXT,
    placement_status   TEXT    DEFAULT 'Continuing',
    date_opened        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date_closed        TEXT,
    case_officer       TEXT,
    panel_chair        TEXT,
    summary            TEXT,
    source_record_id   INTEGER,
    created_at         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_record_id)
        REFERENCES disciplinary_records(record_id) ON DELETE SET NULL
);
"""

_CREATE_FTP_CONCERNS = """
CREATE TABLE IF NOT EXISTS ftp_concerns (
    concern_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id      INTEGER NOT NULL,
    category     TEXT    NOT NULL,
    description  TEXT,
    raised_by    TEXT,
    raised_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES ftp_cases(case_id) ON DELETE CASCADE
);
"""

_CREATE_FTP_EVENTS = """
CREATE TABLE IF NOT EXISTS ftp_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id      INTEGER NOT NULL,
    event_type   TEXT    NOT NULL,
    notes        TEXT,
    actor        TEXT,
    occurred_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES ftp_cases(case_id) ON DELETE CASCADE
);
"""

_CREATE_FTP_OUTCOMES = """
CREATE TABLE IF NOT EXISTS ftp_outcomes (
    outcome_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id       INTEGER NOT NULL,
    outcome       TEXT    NOT NULL,
    sanction      TEXT,
    conditions    TEXT,
    review_date   TEXT,
    decided_by    TEXT,
    decided_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES ftp_cases(case_id) ON DELETE CASCADE
);
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_ftp_cases_student ON ftp_cases(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_ftp_cases_stage   ON ftp_cases(stage);",
    "CREATE INDEX IF NOT EXISTS idx_ftp_concerns_case ON ftp_concerns(case_id);",
    "CREATE INDEX IF NOT EXISTS idx_ftp_events_case   ON ftp_events(case_id);",
    "CREATE INDEX IF NOT EXISTS idx_ftp_outcomes_case ON ftp_outcomes(case_id);",
)

# When an FtP case was escalated from a disciplinary_records row
# (source_record_id IS NOT NULL), reflect terminal stages back onto
# the parent record. We deliberately only mirror the closed-out stages
# — mid-process FtP transitions don't have a meaningful disciplinary
# equivalent, so leaving the parent on "Escalated" is the right
# behaviour.
_TRIGGER_MIRROR_TO_DISC = """
CREATE TRIGGER IF NOT EXISTS sync_ftp_stage_to_disc
AFTER UPDATE OF stage ON ftp_cases
WHEN NEW.stage IS NOT OLD.stage
     AND NEW.source_record_id IS NOT NULL
     AND NEW.stage IN ('Outcome Issued', 'Closed')
BEGIN
    UPDATE disciplinary_records
       SET status = CASE NEW.stage
                        WHEN 'Closed' THEN 'Resolved'
                        ELSE 'Resolved'
                    END,
           updated_at = CURRENT_TIMESTAMP
     WHERE record_id = NEW.source_record_id
       AND status NOT IN ('Resolved', 'Closed');
END;
"""

# Touch updated_at on any change to ftp_cases so the dashboard's
# "recently active" sort is meaningful.
_TRIGGER_TOUCH_UPDATED = """
CREATE TRIGGER IF NOT EXISTS ftp_cases_touch_updated_at
AFTER UPDATE ON ftp_cases
BEGIN
    UPDATE ftp_cases SET updated_at = CURRENT_TIMESTAMP
     WHERE case_id = NEW.case_id;
END;
"""


def ensure_ftp_schema(db_path=None) -> None:
    """Create FtP tables, indexes, and triggers if missing. Idempotent."""
    path = str(db_path or DEFAULT_DB_PATH)
    try:
        conn = sqlite3.connect(path)
    except sqlite3.Error:
        logger.exception("could not open %s for FtP schema bootstrap", path)
        return
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for stmt in (
            _CREATE_FTP_CASES,
            _CREATE_FTP_CONCERNS,
            _CREATE_FTP_EVENTS,
            _CREATE_FTP_OUTCOMES,
            *_INDEXES,
            _TRIGGER_MIRROR_TO_DISC,
            _TRIGGER_TOUCH_UPDATED,
        ):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                logger.exception("FtP bootstrap statement failed: %s",
                                 stmt.split('\n', 1)[0])
        conn.commit()
    finally:
        conn.close()
