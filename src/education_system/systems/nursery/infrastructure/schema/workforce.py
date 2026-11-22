"""Staff rota, training, paediatric first aid and payroll.

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations


# ``rota_shifts`` = staff shift scheduling. One row per shift, attached to a
# staff member, with a date, start/end time, the room they're deployed to and a
# scheduled → confirmed → cancelled workflow. The Staff:Child Ratios board can
# read these to see who is on duty.
_ROTA_SCHEMA = """
CREATE TABLE IF NOT EXISTS rota_shifts (
    shift_id    TEXT PRIMARY KEY,
    staff_id    TEXT NOT NULL,
    shift_date  TEXT,
    start_time  TEXT,
    end_time    TEXT,
    room        TEXT,
    role        TEXT,
    status      TEXT NOT NULL DEFAULT 'scheduled',
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rota_date  ON rota_shifts(shift_date);
CREATE INDEX IF NOT EXISTS idx_rota_staff ON rota_shifts(staff_id);
"""

# ``staff_training`` = structured qualification / training records behind the
# free-text ``staff.qualifications`` field. Tracks the course, level, awarding
# body, completion + expiry dates and a status, so renewals can be planned.
_TRAINING_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff_training (
    record_id       TEXT PRIMARY KEY,
    staff_id        TEXT NOT NULL,
    course          TEXT NOT NULL,
    level           TEXT,
    awarding_body   TEXT,
    completed_date  TEXT,
    expiry_date     TEXT,
    certificate_ref TEXT,
    status          TEXT NOT NULL DEFAULT 'valid',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_training_staff ON staff_training(staff_id);
"""

# ``paediatric_first_aid`` = PFA certificates (EYFS requires PFA-trained staff
# on site and on outings; a full PFA certificate lasts three years). Validity is
# derived from ``expiry_date``; saving a record syncs ``staff.is_paediatric_first_aider``.
_PFA_SCHEMA = """
CREATE TABLE IF NOT EXISTS paediatric_first_aid (
    record_id        TEXT PRIMARY KEY,
    staff_id         TEXT NOT NULL,
    certificate_type TEXT,
    awarding_body    TEXT,
    issue_date       TEXT,
    expiry_date      TEXT,
    certificate_ref  TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pfa_staff ON paediatric_first_aid(staff_id);
"""

# ── Payroll ──────────────────────────────────────────────────────────────────

# ``staff_pay`` = one live pay arrangement per staff member. Actual hours,
# overtime and cost are *computed* from ``rota_shifts`` and ``staff_absences``
# rather than stored, so the forecast always reflects the current rota.
_STAFF_PAY_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff_pay (
    pay_id              TEXT PRIMARY KEY,
    staff_id            TEXT NOT NULL UNIQUE,
    pay_type            TEXT NOT NULL DEFAULT 'hourly',
    hourly_rate         REAL NOT NULL DEFAULT 0,
    annual_salary       REAL NOT NULL DEFAULT 0,
    contracted_hours    REAL NOT NULL DEFAULT 0,
    overtime_multiplier REAL NOT NULL DEFAULT 1.5,
    is_agency           INTEGER NOT NULL DEFAULT 0,
    agency_name         TEXT,
    pension_percent     REAL NOT NULL DEFAULT 3.0,
    ni_percent          REAL NOT NULL DEFAULT 13.8,
    effective_from      TEXT,
    status              TEXT NOT NULL DEFAULT 'active',
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_staff_pay_status ON staff_pay(status);
"""
