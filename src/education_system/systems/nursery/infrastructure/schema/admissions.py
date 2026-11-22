"""Admissions, enrolments, funded hours, settling-in, transitions and leavers.

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations


# ``admissions`` = enquiries / applications and the waiting list. A row starts
# life as ``waiting`` and moves through offer → accept; accepting it feeds the
# Registration & Enrolment flow, which on success stamps ``pupil_id`` and marks
# the row ``enrolled``. The child only joins the ``pupils`` roll at that point.
_ADMISSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions (
    application_id   TEXT PRIMARY KEY,
    child_first_name TEXT NOT NULL,
    child_last_name  TEXT NOT NULL,
    date_of_birth    TEXT,
    parent_name      TEXT,
    parent_phone     TEXT,
    parent_email     TEXT,
    requested_room   TEXT,
    requested_start  TEXT,
    funded_hours     TEXT,
    days_required    TEXT,
    date_applied     TEXT,
    priority         TEXT NOT NULL DEFAULT 'standard',
    status           TEXT NOT NULL DEFAULT 'waiting',
    offer_date       TEXT,
    notes            TEXT,
    pupil_id         TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_admissions_status   ON admissions(status);
CREATE INDEX IF NOT EXISTS idx_admissions_priority ON admissions(priority);
"""

# ``enrolments`` = the formal registration record created when a child joins the
# roll: contracted room/hours/sessions, the registration date and the statutory
# EYFS consents (photo, outings, emergency medical treatment, sun cream). Each
# row points at a ``pupils`` record and, optionally, the admissions row it came
# from.
_ENROLMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolments (
    enrolment_id            TEXT PRIMARY KEY,
    pupil_id                TEXT NOT NULL,
    application_id          TEXT,
    room                    TEXT,
    start_date              TEXT,
    funded_hours            TEXT,
    weekly_sessions         TEXT,
    registration_date       TEXT,
    contract_signed         INTEGER NOT NULL DEFAULT 0,
    photo_consent           INTEGER NOT NULL DEFAULT 0,
    outings_consent         INTEGER NOT NULL DEFAULT 0,
    medical_consent         INTEGER NOT NULL DEFAULT 0,
    suncream_consent        INTEGER NOT NULL DEFAULT 0,
    emergency_contact_name  TEXT,
    emergency_contact_phone TEXT,
    notes                   TEXT,
    status                  TEXT NOT NULL DEFAULT 'enrolled',
    created_at              TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (application_id) REFERENCES admissions(application_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_enrolments_pupil  ON enrolments(pupil_id);
CREATE INDEX IF NOT EXISTS idx_enrolments_status ON enrolments(status);
"""

# ``funded_hours_records`` = the detailed funded-entitlement record behind the
# simple ``pupils.funded_hours`` label. Captures the weekly funded hours, any
# additional paid hours, the DfE eligibility code (30-hour / 2-year-old) and the
# funding period so claims can be evidenced.
_FUNDED_HOURS_SCHEMA = """
CREATE TABLE IF NOT EXISTS funded_hours_records (
    record_id         TEXT PRIMARY KEY,
    pupil_id          TEXT NOT NULL,
    entitlement       TEXT NOT NULL,
    funded_hours_pw   REAL,
    additional_hours  REAL,
    eligibility_code  TEXT,
    eligibility_start TEXT,
    eligibility_end   TEXT,
    funding_period    TEXT,
    stretched         INTEGER NOT NULL DEFAULT 0,
    notes             TEXT,
    status            TEXT NOT NULL DEFAULT 'active',
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_funded_pupil  ON funded_hours_records(pupil_id);
CREATE INDEX IF NOT EXISTS idx_funded_status ON funded_hours_records(status);
"""

# ``settling_in`` = the EYFS settling-in sessions logged when a child starts
# (home visit, taster session, first sessions, reviews). Each row captures how
# the child settled so the key person can track progress to "Settled".
_SETTLING_IN_SCHEMA = """
CREATE TABLE IF NOT EXISTS settling_in (
    session_id       TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    session_date     TEXT,
    session_type     TEXT,
    duration_minutes INTEGER,
    key_person       TEXT,
    settled_rating   TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (key_person) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_settling_pupil ON settling_in(pupil_id);
"""

# ``transitions`` = the move on to primary school (Reception). Tracks the
# destination school, expected start, whether the transition report was sent and
# the activities (visits, transition days) completed.
_TRANSITIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS transitions (
    transition_id          TEXT PRIMARY KEY,
    pupil_id               TEXT NOT NULL,
    destination_school     TEXT,
    expected_start         TEXT,
    transition_report_sent INTEGER NOT NULL DEFAULT 0,
    report_sent_date       TEXT,
    teacher_visit          INTEGER NOT NULL DEFAULT 0,
    activities             TEXT,
    status                 TEXT NOT NULL DEFAULT 'planned',
    notes                  TEXT,
    created_at             TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transitions_pupil  ON transitions(pupil_id);
CREATE INDEX IF NOT EXISTS idx_transitions_status ON transitions(status);
"""

# ``leavers`` = children who have left the setting. Records the leaving date,
# reason and destination. Recording a leaver also flips the child's
# ``pupils.status`` to 'left' so they drop off the active roll.
_LEAVERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS leavers (
    leaver_id           TEXT PRIMARY KEY,
    pupil_id            TEXT NOT NULL,
    leaving_date        TEXT,
    last_day_attended   TEXT,
    reason              TEXT,
    destination         TEXT,
    records_transferred INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_leavers_pupil ON leavers(pupil_id);
"""
