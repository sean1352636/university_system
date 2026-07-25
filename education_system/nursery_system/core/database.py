"""SQLite schema and bootstrap for the Nursery System.

Creates the shared ``nursery.db`` with ``pupils`` (the children on roll) and
``staff`` tables. Column shapes follow the Early Years / EYFS domain and stay
compatible with the cross-system superadmin dashboard, which counts the
``pupils`` and ``staff`` tables via ``shared/admin_portal/admin_service.py``.

``init_db()`` is idempotent (``CREATE TABLE IF NOT EXISTS``) and is called on
every nursery launch from ``cli_main.run`` / ``main_gui.run``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3

from education_system.nursery_system.core.paths import NURSERY_DB, ensure_directories

logger = logging.getLogger(__name__)


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

# ── Finance ──────────────────────────────────────────────────────────────────

# ``invoices`` = fee invoices raised to a child's account. ``total_amount`` is
# the net of gross fees less funded-hours deduction and any discount; the paid
# balance is derived from ``payments`` rows referencing the invoice.
_INVOICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id       TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    period           TEXT,
    issue_date       TEXT,
    due_date         TEXT,
    hours_billed     REAL,
    hourly_rate      REAL,
    gross_amount     REAL NOT NULL DEFAULT 0,
    funded_deduction REAL NOT NULL DEFAULT 0,
    discount_amount  REAL NOT NULL DEFAULT 0,
    total_amount     REAL NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'draft',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_invoices_pupil  ON invoices(pupil_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
"""

# ``payments`` = money received, optionally allocated to an invoice. Methods
# include the voucher / Tax-Free Childcare schemes registered in
# ``childcare_vouchers``.
_PAYMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    payment_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    invoice_id   TEXT,
    amount       REAL NOT NULL DEFAULT 0,
    method       TEXT,
    payment_date TEXT,
    reference    TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_payments_pupil   ON payments(pupil_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
"""

# ``funding_claims`` = claims to the local authority for funded entitlement
# hours. ``claim_amount`` = funded_hours/week × weeks × hourly_rate.
_FUNDING_CLAIMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS funding_claims (
    claim_id       TEXT PRIMARY KEY,
    pupil_id       TEXT,
    funding_period TEXT,
    entitlement    TEXT,
    funded_hours   REAL,
    weeks          REAL,
    hourly_rate    REAL,
    claim_amount   REAL NOT NULL DEFAULT 0,
    headcount_date TEXT,
    status         TEXT NOT NULL DEFAULT 'draft',
    submitted_date TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_funding_claims_status ON funding_claims(status);
"""

# ``childcare_vouchers`` = registered Tax-Free Childcare / employer-voucher
# arrangements per child (the standing arrangement; actual receipts are logged
# as ``payments`` with the matching method).
_VOUCHERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS childcare_vouchers (
    voucher_id      TEXT PRIMARY KEY,
    pupil_id        TEXT NOT NULL,
    scheme          TEXT,
    provider        TEXT,
    account_ref     TEXT,
    expected_amount REAL,
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vouchers_pupil ON childcare_vouchers(pupil_id);
"""

# ``fee_discounts`` = discount arrangements (sibling, staff, bursary) applied to
# a child's fees. Either a percentage or a fixed monthly amount.
_DISCOUNTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS fee_discounts (
    discount_id   TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    discount_type TEXT,
    percentage    REAL,
    fixed_amount  REAL,
    reason        TEXT,
    start_date    TEXT,
    end_date      TEXT,
    status        TEXT NOT NULL DEFAULT 'active',
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_discounts_pupil ON fee_discounts(pupil_id);
"""


# ── Parents & Communication ───────────────────────────────────────────────────

# ``parent_contacts`` = the parents / carers attached to a child. Captures who
# holds parental responsibility, who is allowed to collect and the primary
# day-to-day contact (the one the setting calls first). Distinct from
# ``emergency_contacts``, which are the back-up people called only when a parent
# can't be reached.
_PARENT_CONTACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_contacts (
    contact_id              TEXT PRIMARY KEY,
    pupil_id                TEXT NOT NULL,
    full_name               TEXT NOT NULL,
    relationship            TEXT,
    phone                   TEXT,
    email                   TEXT,
    address                 TEXT,
    is_primary              INTEGER NOT NULL DEFAULT 0,
    parental_responsibility INTEGER NOT NULL DEFAULT 1,
    can_collect             INTEGER NOT NULL DEFAULT 1,
    notes                   TEXT,
    created_at              TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_parent_contacts_pupil ON parent_contacts(pupil_id);
"""

# ``emergency_contacts`` = the back-up people a setting calls when a parent can't
# be reached. Ordered by ``priority`` (1 = call first). ``can_collect`` records
# whether they're on the authorised collection list as well.
_EMERGENCY_CONTACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS emergency_contacts (
    contact_id     TEXT PRIMARY KEY,
    pupil_id       TEXT NOT NULL,
    full_name      TEXT NOT NULL,
    relationship   TEXT,
    phone_primary  TEXT,
    phone_alt      TEXT,
    priority       INTEGER NOT NULL DEFAULT 1,
    can_collect    INTEGER NOT NULL DEFAULT 0,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_emergency_contacts_pupil ON emergency_contacts(pupil_id);
"""

# ``consents`` = the parental permissions a setting must record and be able to
# evidence (photos, outings, sun cream, emergency medical treatment, nappy
# changing, face painting, social media, etc.). Each row is one permission for
# one child with a granted / refused / pending status and an optional review /
# expiry date. The simple boolean consents on the ``enrolments`` record are the
# enrolment snapshot; this table is the living, auditable consent register.
_CONSENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS consents (
    consent_id    TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    consent_type  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'granted',
    date_recorded TEXT,
    expiry_date   TEXT,
    recorded_by   TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_consents_pupil  ON consents(pupil_id);
CREATE INDEX IF NOT EXISTS idx_consents_status ON consents(status);
"""

# ``parent_messages`` = the two-way message log with parents (nursery app,
# email, SMS, phone or in-person notes). ``direction`` is outgoing/incoming and
# ``status`` tracks draft → sent → read → replied so staff can see what is
# outstanding.
_PARENT_MESSAGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_messages (
    message_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    direction    TEXT NOT NULL DEFAULT 'outgoing',
    channel      TEXT,
    subject      TEXT,
    body         TEXT,
    message_date TEXT,
    staff_id     TEXT,
    status       TEXT NOT NULL DEFAULT 'sent',
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_parent_messages_pupil  ON parent_messages(pupil_id);
CREATE INDEX IF NOT EXISTS idx_parent_messages_status ON parent_messages(status);
"""

# ``daily_updates`` = the at-a-glance "how was my child's day" summary shared
# with parents (mood, meals, sleep, nappies/toileting and activities). One row
# per child per day; ``shared`` flips to 1 once it's been sent to the parent.
# Complements the fuller free-text ``daily_diary`` and the specialist sleep /
# nappy / meal logs by rolling them into a single parent-facing update.
_DAILY_UPDATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_updates (
    update_id   TEXT PRIMARY KEY,
    pupil_id    TEXT NOT NULL,
    update_date TEXT,
    mood        TEXT,
    meals       TEXT,
    sleep       TEXT,
    nappies     TEXT,
    activities  TEXT,
    notes       TEXT,
    staff_id    TEXT,
    shared      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_updates_pupil ON daily_updates(pupil_id);
CREATE INDEX IF NOT EXISTS idx_daily_updates_date  ON daily_updates(update_date);
"""

# ``newsletters`` = setting-wide bulletins issued to parents (whole setting or a
# single room). Not attached to a child. Moves draft → published, stamping
# ``published_date`` when it goes out.
_NEWSLETTERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS newsletters (
    newsletter_id  TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    issue_date     TEXT,
    audience       TEXT,
    body           TEXT,
    author         TEXT,
    status         TEXT NOT NULL DEFAULT 'draft',
    published_date TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (author) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_newsletters_status ON newsletters(status);
"""

# ``parent_meetings`` = scheduled meetings / consultations with a child's
# parents (settling review, progress chat, 2-year check, concern, parents'
# evening). Moves scheduled → completed/cancelled; ``summary`` holds the agreed
# outcome once held.
_PARENT_MEETINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_meetings (
    meeting_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    meeting_date TEXT,
    meeting_time TEXT,
    meeting_type TEXT,
    staff_id     TEXT,
    location     TEXT,
    status       TEXT NOT NULL DEFAULT 'scheduled',
    summary      TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_parent_meetings_pupil  ON parent_meetings(pupil_id);
CREATE INDEX IF NOT EXISTS idx_parent_meetings_status ON parent_meetings(status);
"""


# ── Daily care / welfare (registers behind the Compliance & Reports) ──────────

# ``attendance_records`` = the daily register. One row per child per session
# (``all-day``/``am``/``pm``) on a given date, with a status (present / absent /
# late / sick / holiday), arrival + departure times and any absence reason. The
# Attendance Report aggregates these into attendance rates by child / room /
# date range. A unique index keeps one row per child-date-session.
_ATTENDANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_records (
    record_id      TEXT PRIMARY KEY,
    pupil_id       TEXT NOT NULL,
    attend_date    TEXT NOT NULL,
    room           TEXT,
    session        TEXT NOT NULL DEFAULT 'all-day',
    status         TEXT NOT NULL DEFAULT 'present',
    arrival_time   TEXT,
    departure_time TEXT,
    absence_reason TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_attendance_date  ON attendance_records(attend_date);
CREATE INDEX IF NOT EXISTS idx_attendance_pupil ON attendance_records(pupil_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique
    ON attendance_records(pupil_id, attend_date, session);
"""

# ``accident_records`` = the statutory accident / incident / near-miss register.
# EYFS requires a written record of accidents, injuries and first aid given, and
# parents informed the same day; serious injuries may be RIDDOR-reportable. Each
# row links a child, what happened, the injury + body part, treatment +
# first-aider, whether the parent was informed / signed and whether it is
# RIDDOR-reportable. The Accident / Incident Report lists and summarises these.
_ACCIDENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS accident_records (
    record_id         TEXT PRIMARY KEY,
    pupil_id          TEXT NOT NULL,
    record_type       TEXT NOT NULL DEFAULT 'accident',
    occurred_date     TEXT,
    occurred_time     TEXT,
    location          TEXT,
    description       TEXT,
    injury            TEXT,
    body_part         TEXT,
    treatment         TEXT,
    first_aider       TEXT,
    severity          TEXT NOT NULL DEFAULT 'minor',
    parent_informed   INTEGER NOT NULL DEFAULT 0,
    parent_signed     INTEGER NOT NULL DEFAULT 0,
    riddor_reportable INTEGER NOT NULL DEFAULT 0,
    action_taken      TEXT,
    recorded_by       TEXT,
    status            TEXT NOT NULL DEFAULT 'open',
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (first_aider) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_accident_pupil ON accident_records(pupil_id);
CREATE INDEX IF NOT EXISTS idx_accident_date  ON accident_records(occurred_date);
CREATE INDEX IF NOT EXISTS idx_accident_type  ON accident_records(record_type);
"""


# ── EYFS Learning & Development ────────────────────────────────────────────────
# The EYFS (Early Years Foundation Stage) framework: seven areas of learning —
# three prime (Communication & Language, Physical Development, Personal/Social &
# Emotional) and four specific (Literacy, Mathematics, Understanding the World,
# Expressive Arts & Design) — plus the three Characteristics of Effective
# Learning. The tables below back the assessment, observation and planning cycle.

# ``eyfs_profiles`` = a per-child attainment snapshot across the seven areas,
# each judged Emerging / Expected / Exceeding for a term. The summative view a
# key person shares at a review point.
_EYFS_PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS eyfs_profiles (
    profile_id             TEXT PRIMARY KEY,
    pupil_id               TEXT NOT NULL,
    assessment_date        TEXT,
    term                   TEXT,
    communication_language TEXT,
    physical_development   TEXT,
    pse_development        TEXT,
    literacy               TEXT,
    mathematics            TEXT,
    understanding_world    TEXT,
    expressive_arts        TEXT,
    summary                TEXT,
    assessor               TEXT,
    status                 TEXT NOT NULL DEFAULT 'draft',
    created_at             TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (assessor) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_eyfs_profiles_pupil ON eyfs_profiles(pupil_id);
"""

# ``development_tracking`` = a single area assessment for a child at a point in
# time: the area (one of the seven), an optional aspect, the Development Matters
# age band reached and a judgement (Emerging / Developing / Secure). Tracking
# these over time shows progress per area.
_DEVELOPMENT_TRACKING_SCHEMA = """
CREATE TABLE IF NOT EXISTS development_tracking (
    record_id       TEXT PRIMARY KEY,
    pupil_id        TEXT NOT NULL,
    area            TEXT NOT NULL,
    aspect          TEXT,
    age_band        TEXT,
    judgement       TEXT,
    assessment_date TEXT,
    assessor        TEXT,
    next_steps      TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (assessor) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_devtrack_pupil ON development_tracking(pupil_id);
CREATE INDEX IF NOT EXISTS idx_devtrack_area  ON development_tracking(area);
"""

# ``observations`` = the day-to-day observations of a child at play that evidence
# learning (spontaneous, planned or focused), tagged to an area of learning with
# the identified next step.
_OBSERVATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    observation_id   TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    observation_date TEXT,
    observation_type TEXT,
    area             TEXT,
    title            TEXT,
    description      TEXT,
    context          TEXT,
    next_step        TEXT,
    staff_id         TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_observations_pupil ON observations(pupil_id);
CREATE INDEX IF NOT EXISTS idx_observations_date  ON observations(observation_date);
"""

# ``learning_journeys`` = the curated entries that make up each child's learning
# journey / journal — milestones and "wow moments", tagged to an area and
# optionally shared with parents.
_LEARNING_JOURNEYS_SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_journeys (
    entry_id           TEXT PRIMARY KEY,
    pupil_id           TEXT NOT NULL,
    entry_date         TEXT,
    title              TEXT,
    area               TEXT,
    description        TEXT,
    wow_moment         INTEGER NOT NULL DEFAULT 0,
    shared_with_parent INTEGER NOT NULL DEFAULT 0,
    staff_id           TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_journeys_pupil ON learning_journeys(pupil_id);
"""

# ``next_steps`` = the planned next steps for a child's learning, drawn from
# observations/assessment. Each has an area, a target and a planned → in_progress
# → achieved status.
_NEXT_STEPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS next_steps (
    step_id       TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    area          TEXT,
    description   TEXT NOT NULL,
    planned_date  TEXT,
    target_date   TEXT,
    status        TEXT NOT NULL DEFAULT 'planned',
    achieved_date TEXT,
    staff_id      TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_next_steps_pupil  ON next_steps(pupil_id);
CREATE INDEX IF NOT EXISTS idx_next_steps_status ON next_steps(status);
"""

# ``progress_check_2yr`` = the statutory EYFS progress check at age two, covering
# the three prime areas with a summary, identified strengths and any concerns,
# and whether it was shared with the parents and health visitor.
_PROGRESS_CHECK_2YR_SCHEMA = """
CREATE TABLE IF NOT EXISTS progress_check_2yr (
    check_id             TEXT PRIMARY KEY,
    pupil_id             TEXT NOT NULL,
    check_date           TEXT,
    age_months           INTEGER,
    comm_language        TEXT,
    physical_development TEXT,
    pse_development      TEXT,
    summary              TEXT,
    strengths            TEXT,
    areas_of_concern     TEXT,
    shared_with_parents  INTEGER NOT NULL DEFAULT 0,
    shared_with_hv       INTEGER NOT NULL DEFAULT 0,
    staff_id             TEXT,
    status               TEXT NOT NULL DEFAULT 'draft',
    created_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_progress2yr_pupil ON progress_check_2yr(pupil_id);
"""

# ``effective_learning`` = observations against the three Characteristics of
# Effective Learning (Playing & Exploring, Active Learning, Creating & Thinking
# Critically) — how a child learns, not what.
_EFFECTIVE_LEARNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS effective_learning (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    observation_date TEXT,
    characteristic   TEXT,
    aspect           TEXT,
    description      TEXT,
    staff_id         TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_effective_learning_pupil ON effective_learning(pupil_id);
"""

# ``curriculum_planning`` = activity / curriculum plans at room or setting level
# (not attached to a child): a theme, learning intention, the planned activities
# and resources, moving planned → delivered.
_CURRICULUM_PLANNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS curriculum_planning (
    plan_id            TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    plan_date          TEXT,
    room               TEXT,
    area               TEXT,
    theme              TEXT,
    learning_intention TEXT,
    activities         TEXT,
    resources          TEXT,
    staff_id           TEXT,
    status             TEXT NOT NULL DEFAULT 'planned',
    created_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_curriculum_status ON curriculum_planning(status);
"""

# ``cohort_tracking`` = cohort-level attainment snapshots (not per child): for a
# named cohort/room/term and area of learning, how many children are below /
# on-track / above expected. Supports gap analysis across groups.
_COHORT_TRACKING_SCHEMA = """
CREATE TABLE IF NOT EXISTS cohort_tracking (
    cohort_id       TEXT PRIMARY KEY,
    cohort_name     TEXT NOT NULL,
    room            TEXT,
    term            TEXT,
    area            TEXT,
    total_children  INTEGER,
    below_count     INTEGER,
    on_track_count  INTEGER,
    above_count     INTEGER,
    assessment_date TEXT,
    staff_id        TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cohort_tracking_room ON cohort_tracking(room);
"""

# ``evidence`` = the Photos & Evidence library: photos, videos, work samples and
# notes captured as evidence of a child's learning, tagged to an area and
# optionally shared with parents.
_EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id        TEXT PRIMARY KEY,
    pupil_id           TEXT NOT NULL,
    capture_date       TEXT,
    title              TEXT,
    evidence_type      TEXT,
    area               TEXT,
    file_ref           TEXT,
    description        TEXT,
    shared_with_parent INTEGER NOT NULL DEFAULT 0,
    staff_id           TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_pupil ON evidence(pupil_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type  ON evidence(evidence_type);
"""


# ── Daily Care & Routines ─────────────────────────────────────────────────────
# The day-to-day care records an Early Years setting keeps for each child. The
# Daily Register reuses ``attendance_records`` and the Accident & Incident Log
# reuses ``accident_records`` (both defined above); the tables below back the
# remaining routines.

# ``sign_in_out_log`` = timestamped arrival / collection events. One row per
# in/out event, recording the time, who dropped off / collected the child (and
# their relationship — collectors must be on the authorised list) and the staff
# member who recorded it. Distinct from the daily register (present/absent): this
# is the legal record of who had the child and when.
_SIGN_IN_OUT_SCHEMA = """
CREATE TABLE IF NOT EXISTS sign_in_out_log (
    event_id     TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    event_date   TEXT NOT NULL,
    event_time   TEXT,
    direction    TEXT NOT NULL DEFAULT 'in',
    person_name  TEXT,
    relationship TEXT,
    recorded_by  TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sign_in_out_pupil ON sign_in_out_log(pupil_id);
CREATE INDEX IF NOT EXISTS idx_sign_in_out_date  ON sign_in_out_log(event_date);
"""

# ``daily_diary`` = the staff diary of a child's day (mood, activities,
# highlights, free-text notes). One row per child per day. Feeds the
# parent-facing ``daily_updates`` but is the fuller practitioner record.
_DAILY_DIARY_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_diary (
    entry_id    TEXT PRIMARY KEY,
    pupil_id    TEXT NOT NULL,
    entry_date  TEXT NOT NULL,
    mood        TEXT,
    activities  TEXT,
    highlights  TEXT,
    notes       TEXT,
    staff_id    TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_diary_pupil ON daily_diary(pupil_id);
CREATE INDEX IF NOT EXISTS idx_daily_diary_date  ON daily_diary(entry_date);
"""

# ``sleep_log`` = nap records with safer-sleep checks. Each row is one sleep,
# with start/end, derived duration, where the child slept and how many sleep
# checks were carried out (settings check sleeping children at regular intervals).
_SLEEP_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS sleep_log (
    sleep_id         TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    sleep_date       TEXT NOT NULL,
    start_time       TEXT,
    end_time         TEXT,
    duration_minutes INTEGER,
    location         TEXT,
    checks           INTEGER NOT NULL DEFAULT 0,
    staff_id         TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sleep_log_pupil ON sleep_log(pupil_id);
CREATE INDEX IF NOT EXISTS idx_sleep_log_date  ON sleep_log(sleep_date);
"""

# ``toileting_log`` = nappy changes and toilet/potty use. Each row records the
# time, the type (wet/soiled/dry nappy, toilet, potty, accident), whether barrier
# cream was applied and the staff member.
_TOILETING_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS toileting_log (
    record_id     TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    log_date      TEXT NOT NULL,
    log_time      TEXT,
    type          TEXT NOT NULL DEFAULT 'nappy - wet',
    cream_applied INTEGER NOT NULL DEFAULT 0,
    staff_id      TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_toileting_pupil ON toileting_log(pupil_id);
CREATE INDEX IF NOT EXISTS idx_toileting_date  ON toileting_log(log_date);
"""

# ``meals`` = the per-child meal log (Meals & Menus). One row per child per meal
# sitting, recording the meal type, the menu served, how much was eaten and the
# drink, plus an allergy-safe flag so kitchen/room staff can evidence that a
# child's dietary needs were honoured.
_MEALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS meals (
    meal_id      TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    meal_date    TEXT NOT NULL,
    meal_type    TEXT NOT NULL DEFAULT 'Lunch',
    menu         TEXT,
    amount_eaten TEXT,
    drink        TEXT,
    allergy_safe INTEGER NOT NULL DEFAULT 1,
    staff_id     TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_meals_pupil ON meals(pupil_id);
CREATE INDEX IF NOT EXISTS idx_meals_date  ON meals(meal_date);
"""

# ``bottle_feeds`` = milk feeds for babies. Records the milk type (formula /
# expressed breast milk / cow's milk / water), the amount offered vs taken, and
# whether the temperature was checked and the baby winded.
_BOTTLE_FEEDS_SCHEMA = """
CREATE TABLE IF NOT EXISTS bottle_feeds (
    feed_id             TEXT PRIMARY KEY,
    pupil_id            TEXT NOT NULL,
    feed_date           TEXT NOT NULL,
    feed_time           TEXT,
    milk_type           TEXT NOT NULL DEFAULT 'Formula',
    offered_ml          INTEGER,
    taken_ml            INTEGER,
    temperature_checked INTEGER NOT NULL DEFAULT 1,
    winded              INTEGER NOT NULL DEFAULT 0,
    staff_id            TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_bottle_feeds_pupil ON bottle_feeds(pupil_id);
CREATE INDEX IF NOT EXISTS idx_bottle_feeds_date  ON bottle_feeds(feed_date);
"""

# ``dietary_requirements`` = the structured allergy / intolerance / dietary
# register behind the free-text ``pupils.allergies`` label. Each row records the
# category, allergen, severity, the reaction and the action required (e.g.
# EpiPen), so kitchen and room staff have an auditable care plan per child.
_DIETARY_SCHEMA = """
CREATE TABLE IF NOT EXISTS dietary_requirements (
    record_id       TEXT PRIMARY KEY,
    pupil_id        TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'allergy',
    allergen        TEXT,
    severity        TEXT,
    reaction        TEXT,
    action_required TEXT,
    epipen_required INTEGER NOT NULL DEFAULT 0,
    care_plan_ref   TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dietary_pupil  ON dietary_requirements(pupil_id);
CREATE INDEX IF NOT EXISTS idx_dietary_status ON dietary_requirements(status);
"""

# ``existing_injuries`` = injuries a child arrives WITH (not sustained at the
# setting). EYFS good practice is to log these on arrival with the parent's
# explanation and a signature, to safeguard both child and setting.
_EXISTING_INJURIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS existing_injuries (
    record_id       TEXT PRIMARY KEY,
    pupil_id        TEXT NOT NULL,
    observed_date   TEXT NOT NULL,
    observed_time   TEXT,
    body_part       TEXT,
    description     TEXT,
    explanation     TEXT,
    observed_by     TEXT,
    parent_informed INTEGER NOT NULL DEFAULT 1,
    parent_signed   INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (observed_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_existing_injuries_pupil ON existing_injuries(pupil_id);
CREATE INDEX IF NOT EXISTS idx_existing_injuries_date  ON existing_injuries(observed_date);
"""

# ``medication_log`` = the record of medicine administered (and prior parental
# consent). Each row captures the medicine, dose, route, the reason, when it was
# given and by whom, witnessed-by, and a status (administered / scheduled /
# refused). Settings must hold written parental consent before administering.
_MEDICATION_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS medication_log (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    medication_name  TEXT NOT NULL,
    dose             TEXT,
    route            TEXT,
    reason           TEXT,
    administered_date TEXT,
    administered_time TEXT,
    administered_by  TEXT,
    witnessed_by     TEXT,
    parent_consent   INTEGER NOT NULL DEFAULT 0,
    expiry_date      TEXT,
    status           TEXT NOT NULL DEFAULT 'administered',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (administered_by) REFERENCES staff(staff_id) ON DELETE SET NULL,
    FOREIGN KEY (witnessed_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_medication_pupil  ON medication_log(pupil_id);
CREATE INDEX IF NOT EXISTS idx_medication_status ON medication_log(status);
"""


# ── Sessions & bookings (the contracted booking calendar) ────────────────────

# ``booking_patterns`` = a child's *contracted* weekly pattern — the recurring
# sessions the parent is booked and billed for. One row per child per weekday
# per session, valid between ``start_date`` and an open-ended ``end_date``. This
# is what the setting plans occupancy, ratios and invoices against; the dated
# exceptions to it live in ``session_bookings``.
_BOOKING_PATTERNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS booking_patterns (
    pattern_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    weekday      INTEGER NOT NULL,
    session_type TEXT NOT NULL DEFAULT 'all-day',
    start_time   TEXT,
    end_time     TEXT,
    room         TEXT,
    funding      TEXT NOT NULL DEFAULT 'funded',
    start_date   TEXT NOT NULL,
    end_date     TEXT,
    status       TEXT NOT NULL DEFAULT 'active',
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_booking_patterns_pupil   ON booking_patterns(pupil_id);
CREATE INDEX IF NOT EXISTS idx_booking_patterns_weekday ON booking_patterns(weekday);
CREATE UNIQUE INDEX IF NOT EXISTS idx_booking_patterns_unique
    ON booking_patterns(pupil_id, weekday, session_type, start_date);
"""

# ``session_bookings`` = the dated exceptions layered over the weekly pattern:
# ad-hoc **extra** sessions a parent has booked on top of their contract, and
# **cancellations** of a contracted session. Resolving a date means taking that
# weekday's patterns, dropping the cancellations and adding the extras.
_SESSION_BOOKINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_bookings (
    booking_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    session_date TEXT NOT NULL,
    session_type TEXT NOT NULL DEFAULT 'all-day',
    kind         TEXT NOT NULL DEFAULT 'extra',
    start_time   TEXT,
    end_time     TEXT,
    room         TEXT,
    chargeable   INTEGER NOT NULL DEFAULT 1,
    notice_days  INTEGER,
    reason       TEXT,
    status       TEXT NOT NULL DEFAULT 'confirmed',
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_bookings_date  ON session_bookings(session_date);
CREATE INDEX IF NOT EXISTS idx_session_bookings_pupil ON session_bookings(pupil_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_bookings_unique
    ON session_bookings(pupil_id, session_date, session_type, kind);
"""

# ``setting_closures`` = dates the setting (or a single room) is shut — bank
# holidays, the Christmas closure, INSET days, an emergency closure. A closure
# date resolves to zero booked children, so it suppresses ratio and occupancy
# alerts and drives the "are we charging for it?" billing question.
_CLOSURES_SCHEMA = """
CREATE TABLE IF NOT EXISTS setting_closures (
    closure_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    closure_type TEXT NOT NULL DEFAULT 'holiday',
    room         TEXT,
    chargeable   INTEGER NOT NULL DEFAULT 0,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_closures_start ON setting_closures(start_date);
"""

# ── Collections (who may take a child home, and what happens when they're late)

# ``authorised_collectors`` = the vetted list of people permitted to collect a
# child, each with an optional collection password (stored only as a salted
# hash, never in the clear) and a validity window. A name that isn't on this
# list — or is outside its window, or revoked — must not leave with the child.
_COLLECTORS_SCHEMA = """
CREATE TABLE IF NOT EXISTS authorised_collectors (
    collector_id  TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    relationship  TEXT,
    phone         TEXT,
    password_hash TEXT,
    photo_on_file INTEGER NOT NULL DEFAULT 0,
    id_checked    INTEGER NOT NULL DEFAULT 0,
    is_escalation_contact INTEGER NOT NULL DEFAULT 0,
    valid_from    TEXT,
    valid_until   TEXT,
    status        TEXT NOT NULL DEFAULT 'active',
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_collectors_pupil  ON authorised_collectors(pupil_id);
CREATE INDEX IF NOT EXISTS idx_collectors_status ON authorised_collectors(status);
"""

# ``late_collections`` = the uncollected-child log. Records the booked due time,
# when the child was actually collected, the resulting late fee, and how far the
# setting had to escalate (parent → emergency contacts → manager → DSL → local
# authority) — the evidence trail Ofsted expects for an uncollected child.
_LATE_COLLECTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS late_collections (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    event_date       TEXT NOT NULL,
    due_time         TEXT NOT NULL,
    collected_time   TEXT,
    minutes_late     INTEGER NOT NULL DEFAULT 0,
    collected_by     TEXT,
    collector_id     TEXT,
    fee_amount       REAL NOT NULL DEFAULT 0,
    fee_status       TEXT NOT NULL DEFAULT 'due',
    escalation_stage TEXT NOT NULL DEFAULT 'none',
    escalated_to     TEXT,
    parent_contacted INTEGER NOT NULL DEFAULT 0,
    safeguarding_referral INTEGER NOT NULL DEFAULT 0,
    recorded_by      TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (collector_id) REFERENCES authorised_collectors(collector_id)
        ON DELETE SET NULL,
    FOREIGN KEY (recorded_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_late_collections_pupil ON late_collections(pupil_id);
CREATE INDEX IF NOT EXISTS idx_late_collections_date  ON late_collections(event_date);
"""

# ── Parent self-service ──────────────────────────────────────────────────────

# ``parent_requests`` = everything a parent submits for themselves rather than
# phoning the office: an extra session, an absence, a change of address, a
# consent answer. ``payload`` holds the type-specific body as JSON. Approving a
# request **applies** it to the real domain table and stamps ``applied_ref``, so
# nothing is ever re-keyed by staff.
_PARENT_REQUESTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_requests (
    request_id    TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    request_type  TEXT NOT NULL,
    submitted_by  TEXT,
    submitted_at  TEXT NOT NULL,
    payload       TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',
    decided_by    TEXT,
    decided_at    TEXT,
    decision_note TEXT,
    applied_ref   TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (decided_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_parent_requests_pupil  ON parent_requests(pupil_id);
CREATE INDEX IF NOT EXISTS idx_parent_requests_status ON parent_requests(status);
CREATE INDEX IF NOT EXISTS idx_parent_requests_type   ON parent_requests(request_type);
"""

# ── Digital registration forms & signatures ──────────────────────────────────

# ``form_templates`` = the wording a parent is asked to sign, versioned. Editing
# the wording of a live form issues a NEW version rather than mutating the old
# one, so a signature always points at exactly what was agreed.
_FORM_TEMPLATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_templates (
    template_id    TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    form_type      TEXT NOT NULL,
    version        TEXT NOT NULL DEFAULT '1.0',
    body           TEXT NOT NULL,
    required       INTEGER NOT NULL DEFAULT 1,
    renew_months   INTEGER,
    status         TEXT NOT NULL DEFAULT 'active',
    effective_from TEXT,
    superseded_by  TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_form_templates_type ON form_templates(form_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_form_templates_version
    ON form_templates(form_type, version);
"""

# ``form_submissions`` = a signed return. It pins the template version and a
# hash of the exact wording, plus a signature digest over (form, signer, time),
# so a later edit to the template can never silently change what was signed.
_FORM_SUBMISSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_submissions (
    submission_id    TEXT PRIMARY KEY,
    template_id      TEXT NOT NULL,
    form_type        TEXT NOT NULL,
    template_version TEXT NOT NULL,
    body_hash        TEXT NOT NULL,
    pupil_id         TEXT NOT NULL,
    respondent_name  TEXT NOT NULL,
    respondent_relationship TEXT,
    signature_name   TEXT,
    signed_at        TEXT,
    signature_hash   TEXT,
    source           TEXT NOT NULL DEFAULT 'portal',
    answers          TEXT,
    status           TEXT NOT NULL DEFAULT 'signed',
    witnessed_by     TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (template_id) REFERENCES form_templates(template_id)
        ON DELETE CASCADE,
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (witnessed_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_form_submissions_pupil ON form_submissions(pupil_id);
CREATE INDEX IF NOT EXISTS idx_form_submissions_type  ON form_submissions(form_type);
"""

# ── Consumables inventory ────────────────────────────────────────────────────

# ``stock_items`` = the things a setting runs out of: nappies, wipes, formula,
# food, first-aid supplies, learning materials, cleaning products. ``quantity``
# is the live level, kept in step by ``stock_movements``; a level at or below
# ``reorder_level`` raises a reorder alert.
_STOCK_ITEMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_items (
    item_id          TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    category         TEXT NOT NULL DEFAULT 'Consumables',
    unit             TEXT NOT NULL DEFAULT 'each',
    quantity         REAL NOT NULL DEFAULT 0,
    reorder_level    REAL NOT NULL DEFAULT 0,
    reorder_quantity REAL NOT NULL DEFAULT 0,
    unit_cost        REAL NOT NULL DEFAULT 0,
    supplier_id      TEXT,
    location         TEXT,
    room             TEXT,
    expiry_date      TEXT,
    status           TEXT NOT NULL DEFAULT 'active',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_stock_items_category ON stock_items(category);
CREATE INDEX IF NOT EXISTS idx_stock_items_supplier ON stock_items(supplier_id);
"""

# ``stock_movements`` = the audit trail behind every level change. ``quantity``
# is signed: receipts are positive, usage and waste negative.
_STOCK_MOVEMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_movements (
    movement_id   TEXT PRIMARY KEY,
    item_id       TEXT NOT NULL,
    movement_date TEXT NOT NULL,
    movement_type TEXT NOT NULL,
    quantity      REAL NOT NULL,
    room          TEXT,
    reference     TEXT,
    staff_id      TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (item_id) REFERENCES stock_items(item_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_date ON stock_movements(movement_date);
"""

# ── Suppliers, purchase orders and approvals ─────────────────────────────────

_SUPPLIERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id        TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    category           TEXT,
    contact_name       TEXT,
    email              TEXT,
    phone              TEXT,
    account_number     TEXT,
    payment_terms_days INTEGER NOT NULL DEFAULT 30,
    status             TEXT NOT NULL DEFAULT 'active',
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
"""

# ``purchase_orders`` = money going *out*, as opposed to the parent fees and
# funding claims the rest of Finance covers. A PO walks draft → submitted →
# approved → ordered → received → invoiced → paid, and the approval step is
# gated on the order total against the approver's spending limit.
_PURCHASE_ORDERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id         TEXT PRIMARY KEY,
    supplier_id   TEXT NOT NULL,
    order_date    TEXT NOT NULL,
    required_by   TEXT,
    status        TEXT NOT NULL DEFAULT 'draft',
    raised_by     TEXT,
    approved_by   TEXT,
    approved_at   TEXT,
    approval_note TEXT,
    received_at   TEXT,
    invoice_ref   TEXT,
    invoice_date  TEXT,
    invoice_due   TEXT,
    paid_at       TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    FOREIGN KEY (raised_by) REFERENCES staff(staff_id) ON DELETE SET NULL,
    FOREIGN KEY (approved_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_status   ON purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier ON purchase_orders(supplier_id);
"""

_PURCHASE_ORDER_LINES_SCHEMA = """
CREATE TABLE IF NOT EXISTS purchase_order_lines (
    line_id           TEXT PRIMARY KEY,
    po_id             TEXT NOT NULL,
    item_id           TEXT,
    description       TEXT NOT NULL,
    quantity          REAL NOT NULL DEFAULT 1,
    unit              TEXT NOT NULL DEFAULT 'each',
    unit_price        REAL NOT NULL DEFAULT 0,
    received_quantity REAL NOT NULL DEFAULT 0,
    notes             TEXT,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES stock_items(item_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_po_lines_po ON purchase_order_lines(po_id);
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

# ── Kitchen: planned menu and ingredients ────────────────────────────────────

# ``menu_plan`` = what the kitchen intends to cook, per date and meal. The
# existing ``meals`` table records what each child actually ate *afterwards*;
# this is the forward-looking half the kitchen orders and cooks against.
_MENU_PLAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS menu_plan (
    menu_id     TEXT PRIMARY KEY,
    menu_date   TEXT NOT NULL,
    meal_type   TEXT NOT NULL,
    dish        TEXT NOT NULL,
    alternative TEXT,
    allergens   TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_menu_plan_date ON menu_plan(menu_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_menu_plan_unique
    ON menu_plan(menu_date, meal_type);
"""

# ``menu_ingredients`` = per-child quantities for a planned dish, which the
# kitchen multiplies by the booked headcount to get an order total. Linking a
# line to ``stock_items`` lets the order check what is already in the store.
_MENU_INGREDIENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS menu_ingredients (
    ingredient_id      TEXT PRIMARY KEY,
    menu_id            TEXT NOT NULL,
    item_id            TEXT,
    name               TEXT NOT NULL,
    quantity_per_child REAL NOT NULL DEFAULT 0,
    unit               TEXT NOT NULL DEFAULT 'g',
    notes              TEXT,
    FOREIGN KEY (menu_id) REFERENCES menu_plan(menu_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES stock_items(item_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_menu_ingredients_menu ON menu_ingredients(menu_id);
"""


def connect() -> sqlite3.Connection:
    """Open a connection to the nursery DB, creating the data dir if needed."""
    ensure_directories()
    conn = sqlite3.connect(str(NURSERY_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create the nursery tables if they don't exist (idempotent)."""
    conn = connect()
    try:
        conn.executescript(_STAFF_SCHEMA)
        conn.executescript(_PUPILS_SCHEMA)
        conn.executescript(_ROOMS_SCHEMA)
        conn.executescript(_ADMISSIONS_SCHEMA)
        conn.executescript(_ENROLMENTS_SCHEMA)
        conn.executescript(_FUNDED_HOURS_SCHEMA)
        conn.executescript(_SETTLING_IN_SCHEMA)
        conn.executescript(_TRANSITIONS_SCHEMA)
        conn.executescript(_LEAVERS_SCHEMA)
        conn.executescript(_ROTA_SCHEMA)
        conn.executescript(_TRAINING_SCHEMA)
        conn.executescript(_PFA_SCHEMA)
        conn.executescript(_INVOICES_SCHEMA)
        conn.executescript(_PAYMENTS_SCHEMA)
        conn.executescript(_FUNDING_CLAIMS_SCHEMA)
        conn.executescript(_VOUCHERS_SCHEMA)
        conn.executescript(_DISCOUNTS_SCHEMA)
        conn.executescript(_PARENT_CONTACTS_SCHEMA)
        conn.executescript(_EMERGENCY_CONTACTS_SCHEMA)
        conn.executescript(_CONSENTS_SCHEMA)
        conn.executescript(_PARENT_MESSAGES_SCHEMA)
        conn.executescript(_DAILY_UPDATES_SCHEMA)
        conn.executescript(_NEWSLETTERS_SCHEMA)
        conn.executescript(_PARENT_MEETINGS_SCHEMA)
        conn.executescript(_EYFS_PROFILE_SCHEMA)
        conn.executescript(_DEVELOPMENT_TRACKING_SCHEMA)
        conn.executescript(_OBSERVATIONS_SCHEMA)
        conn.executescript(_LEARNING_JOURNEYS_SCHEMA)
        conn.executescript(_NEXT_STEPS_SCHEMA)
        conn.executescript(_PROGRESS_CHECK_2YR_SCHEMA)
        conn.executescript(_EFFECTIVE_LEARNING_SCHEMA)
        conn.executescript(_CURRICULUM_PLANNING_SCHEMA)
        conn.executescript(_COHORT_TRACKING_SCHEMA)
        conn.executescript(_EVIDENCE_SCHEMA)
        conn.executescript(_ATTENDANCE_SCHEMA)
        conn.executescript(_ACCIDENT_SCHEMA)
        conn.executescript(_SIGN_IN_OUT_SCHEMA)
        conn.executescript(_DAILY_DIARY_SCHEMA)
        conn.executescript(_SLEEP_LOG_SCHEMA)
        conn.executescript(_TOILETING_LOG_SCHEMA)
        conn.executescript(_MEALS_SCHEMA)
        conn.executescript(_BOTTLE_FEEDS_SCHEMA)
        conn.executescript(_DIETARY_SCHEMA)
        conn.executescript(_EXISTING_INJURIES_SCHEMA)
        conn.executescript(_MEDICATION_LOG_SCHEMA)
        conn.executescript(_BOOKING_PATTERNS_SCHEMA)
        conn.executescript(_SESSION_BOOKINGS_SCHEMA)
        conn.executescript(_CLOSURES_SCHEMA)
        conn.executescript(_COLLECTORS_SCHEMA)
        conn.executescript(_LATE_COLLECTIONS_SCHEMA)
        conn.executescript(_PARENT_REQUESTS_SCHEMA)
        conn.executescript(_FORM_TEMPLATES_SCHEMA)
        conn.executescript(_FORM_SUBMISSIONS_SCHEMA)
        conn.executescript(_SUPPLIERS_SCHEMA)
        conn.executescript(_STOCK_ITEMS_SCHEMA)
        conn.executescript(_STOCK_MOVEMENTS_SCHEMA)
        conn.executescript(_PURCHASE_ORDERS_SCHEMA)
        conn.executescript(_PURCHASE_ORDER_LINES_SCHEMA)
        conn.executescript(_STAFF_PAY_SCHEMA)
        conn.executescript(_MENU_PLAN_SCHEMA)
        conn.executescript(_MENU_INGREDIENTS_SCHEMA)
        conn.commit()
        _seed_demo_data(conn)
    finally:
        conn.close()
    logger.debug("Nursery database ready at %s", NURSERY_DB)


# ── Demo seed (dev/demo only) ────────────────────────────────────────────────
# A handful of rows so the superadmin dashboard shows live nursery counts.
# Only inserted when both tables are empty.

_DEMO_STAFF = [
    ("NST001", "Hannah", "Brooks", "Ms", "Nursery Manager", "Whole Setting",
     "Full-time", "hannah.brooks@nursery.local", "01234 567001", 1, 1, 1,
     "EYITT, Level 6 Early Years"),
    ("NST002", "Priya", "Sharma", "Miss", "Room Leader", "Toddler Room",
     "Full-time", "priya.sharma@nursery.local", "01234 567002", 0, 1, 1,
     "Level 3 Early Years Educator"),
    ("NST003", "Daniel", "Okafor", "Mr", "Nursery Practitioner", "Preschool Room",
     "Part-time", "daniel.okafor@nursery.local", "01234 567003", 0, 1, 1,
     "Level 3 Early Years Educator"),
    ("NST004", "Megan", "Lewis", "Miss", "Nursery Practitioner", "Baby Room",
     "Full-time", "megan.lewis@nursery.local", "01234 567004", 0, 0, 1,
     "Level 2 Early Years Practitioner"),
]

_DEMO_PUPILS = [
    ("NCH001", "Oliver", "Hughes", "2022-03-14", "Toddler Room", "NST002",
     "30 hours", "2024-09-02", "Sarah Hughes", "07700 900101",
     "sarah.hughes@example.com", "None", ""),
    ("NCH002", "Amelia", "Patel", "2021-11-02", "Preschool Room", "NST003",
     "15 hours", "2024-09-02", "Raj Patel", "07700 900102",
     "raj.patel@example.com", "Peanuts", "EpiPen kept in office"),
    ("NCH003", "Noah", "Campbell", "2023-06-21", "Baby Room", "NST004",
     "2-year-old funding", "2025-01-06", "Emma Campbell", "07700 900103",
     "emma.campbell@example.com", "None", ""),
    ("NCH004", "Isla", "Murphy", "2022-01-09", "Toddler Room", "NST002",
     "30 hours", "2024-09-02", "Liam Murphy", "07700 900104",
     "liam.murphy@example.com", "Dairy", ""),
    ("NCH005", "Leo", "Bennett", "2021-08-30", "Preschool Room", "NST003",
     "15 hours", "2024-09-02", "Chloe Bennett", "07700 900105",
     "chloe.bennett@example.com", "None", ""),
]


# Age-banded rooms matching the demo children's room names. Ratios follow the
# EYFS statutory minimums for each age band.
_DEMO_ROOMS = [
    ("NRM001", "Baby Room", "Birth to 2 years", 0, 24, 12, "1:3", "NST004",
     "Ground floor", "Sleep room and bottle-prep area attached."),
    ("NRM002", "Toddler Room", "2 to 3 years", 24, 36, 16, "1:4", "NST002",
     "Ground floor", "Direct access to the toddler garden."),
    ("NRM003", "Preschool Room", "3 to 5 years", 36, 60, 24, "1:8", "NST003",
     "First floor", "School-readiness focus for the pre-school year."),
]

# A small waiting list / application pipeline for the demo dashboard.
_DEMO_ADMISSIONS = [
    ("NADM001", "Freya", "Walsh", "2023-02-18", "Hannah Walsh", "07700 900201",
     "hannah.walsh@example.com", "Baby Room", "2025-09-01", "2-year-old funding",
     "Mon,Tue,Wed", "2025-03-10", "sibling", "waiting", None,
     "Older sibling already attends.", None),
    ("NADM002", "Jacob", "Reid", "2022-07-05", "Sara Reid", "07700 900202",
     "sara.reid@example.com", "Toddler Room", "2025-09-01", "15 hours",
     "Mon,Tue,Wed,Thu,Fri", "2025-03-12", "standard", "waiting", None,
     "", None),
    ("NADM003", "Maya", "Osei", "2021-12-20", "Grace Osei", "07700 900203",
     "grace.osei@example.com", "Preschool Room", "2025-04-21", "30 hours",
     "Mon,Tue,Wed,Thu,Fri", "2025-02-01", "looked-after", "offered",
     "2025-03-01", "Place offered, awaiting acceptance.", None),
]


def _last_weekdays(n: int) -> list[_dt.date]:
    """Return the most recent ``n`` weekdays (Mon–Fri), oldest first."""
    out: list[_dt.date] = []
    day = _dt.date.today()
    while len(out) < n:
        if day.weekday() < 5:  # 0=Mon … 4=Fri
            out.append(day)
        day -= _dt.timedelta(days=1)
    return list(reversed(out))


def _seed_attendance(conn: sqlite3.Connection) -> None:
    """Seed an all-day register for active demo children over recent weekdays.

    Deterministic (no randomness): a fixed pattern of late / absent / sick days
    is sprinkled in so the Attendance Report's rates and breakdowns are non-trivial.
    """
    children = conn.execute(
        "SELECT pupil_id, room FROM pupils WHERE status = 'active' "
        "ORDER BY pupil_id").fetchall()
    days = _last_weekdays(10)
    # (child index, day index) -> (status, absence_reason)
    overrides: dict[tuple[int, int], tuple[str, str | None]] = {
        (0, 2): ("late", None),
        (1, 5): ("absent", "Family holiday"),
        (2, 7): ("sick", "Temperature — kept home"),
        (3, 4): ("late", None),
        (1, 8): ("late", None),
        (4, 6): ("absent", "Medical appointment"),
    }
    rows: list[tuple] = []
    for ci, child in enumerate(children):
        for di, day in enumerate(days):
            status, reason = overrides.get((ci, di), ("present", None))
            arrival = departure = None
            if status in ("present", "late"):
                arrival = "09:15" if status == "late" else "08:30"
                departure = "15:30"
            rows.append((
                f"NATT{ci + 1:02d}{di + 1:02d}", child["pupil_id"],
                day.isoformat(), child["room"], "all-day", status,
                arrival, departure, reason, None,
            ))
    conn.executemany(
        "INSERT INTO attendance_records (record_id, pupil_id, attend_date, room, "
        "session, status, arrival_time, departure_time, absence_reason, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _seed_demo_data(conn: sqlite3.Connection) -> None:
    staff_n = conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0]
    pupils_n = conn.execute("SELECT COUNT(*) FROM pupils").fetchone()[0]
    rooms_n = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    admissions_n = conn.execute("SELECT COUNT(*) FROM admissions").fetchone()[0]

    if not (staff_n or pupils_n):
        conn.executemany(
            "INSERT INTO staff (staff_id, first_name, last_name, title, role, room, "
            "employment_status, email, work_phone, is_dsl, is_paediatric_first_aider, "
            "dbs_checked, qualifications) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _DEMO_STAFF,
        )
        conn.executemany(
            "INSERT INTO pupils (pupil_id, first_name, last_name, date_of_birth, room, "
            "key_person, funded_hours, start_date, parent_name, parent_phone, "
            "parent_email, allergies, medical_notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _DEMO_PUPILS,
        )
        logger.info("Seeded nursery demo data: %d staff, %d children",
                    len(_DEMO_STAFF), len(_DEMO_PUPILS))

    if not rooms_n:
        conn.executemany(
            "INSERT INTO rooms (room_id, name, age_group, min_age_months, "
            "max_age_months, capacity, staff_ratio, room_leader, location, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _DEMO_ROOMS,
        )
        logger.info("Seeded nursery demo rooms: %d", len(_DEMO_ROOMS))

    if not admissions_n:
        conn.executemany(
            "INSERT INTO admissions (application_id, child_first_name, "
            "child_last_name, date_of_birth, parent_name, parent_phone, "
            "parent_email, requested_room, requested_start, funded_hours, "
            "days_required, date_applied, priority, status, offer_date, notes, "
            "pupil_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _DEMO_ADMISSIONS,
        )
        logger.info("Seeded nursery demo admissions: %d", len(_DEMO_ADMISSIONS))

    # Light seeds for the Children & Admissions sub-features so their screens
    # show live data against the demo children. Each guarded independently.
    if not conn.execute("SELECT COUNT(*) FROM funded_hours_records").fetchone()[0]:
        conn.executemany(
            "INSERT INTO funded_hours_records (record_id, pupil_id, entitlement, "
            "funded_hours_pw, additional_hours, eligibility_code, "
            "eligibility_start, eligibility_end, funding_period, stretched, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NFH001", "NCH001", "30 hours", 30.0, 5.0, "50012345678",
                 "2024-09-01", "2025-08-31", "2024/25", 0, "Code reconfirmed each term."),
                ("NFH002", "NCH002", "15 hours", 15.0, 0.0, None,
                 "2024-09-01", "2025-08-31", "2024/25", 0, ""),
                ("NFH003", "NCH003", "2-year-old funding", 15.0, 0.0, "ABC123456",
                 "2025-01-06", "2025-08-31", "2024/25", 0, "DWP-eligible 2yo funding."),
            ],
        )
        logger.info("Seeded nursery demo funded-hours records")

    if not conn.execute("SELECT COUNT(*) FROM settling_in").fetchone()[0]:
        conn.executemany(
            "INSERT INTO settling_in (session_id, pupil_id, session_date, "
            "session_type, duration_minutes, key_person, settled_rating, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NSI001", "NCH003", "2025-01-02", "Home visit", 60, "NST004",
                 "Settling", "Met family at home; child shy but engaged."),
                ("NSI002", "NCH003", "2025-01-06", "First session", 120, "NST004",
                 "Settled", "Separated from parent with minimal upset."),
            ],
        )
        logger.info("Seeded nursery demo settling-in sessions")

    if not conn.execute("SELECT COUNT(*) FROM transitions").fetchone()[0]:
        conn.executemany(
            "INSERT INTO transitions (transition_id, pupil_id, destination_school, "
            "expected_start, transition_report_sent, report_sent_date, "
            "teacher_visit, activities, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NTR001", "NCH002", "St Mary's Primary School", "2025-09-03",
                 0, None, 0, "Reception teacher visit booked for July.",
                 "in_progress", "Leaving for Reception in September."),
            ],
        )
        logger.info("Seeded nursery demo transitions")

    if not conn.execute("SELECT COUNT(*) FROM staff_training").fetchone()[0]:
        conn.executemany(
            "INSERT INTO staff_training (record_id, staff_id, course, level, "
            "awarding_body, completed_date, expiry_date, certificate_ref, status, "
            "notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NQT001", "NST001", "Safeguarding & Child Protection", "Level 3",
                 "Local Safeguarding Partnership", "2024-09-15", "2026-09-15",
                 "DSL-2024-001", "valid", "Designated Safeguarding Lead training."),
                ("NQT002", "NST002", "Food Hygiene", "Level 2",
                 "Highfield", "2024-05-02", "2027-05-02", "FH-2024-220", "valid", ""),
                ("NQT003", "NST003", "SENCO Award", "Level 3",
                 "nasen", "2023-11-10", None, "SENCO-2023-3", "valid",
                 "Setting SENCO."),
            ],
        )
        logger.info("Seeded nursery demo training records")

    if not conn.execute("SELECT COUNT(*) FROM paediatric_first_aid").fetchone()[0]:
        conn.executemany(
            "INSERT INTO paediatric_first_aid (record_id, staff_id, "
            "certificate_type, awarding_body, issue_date, expiry_date, "
            "certificate_ref, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NPF001", "NST001", "Full PFA (12 hour)", "St John Ambulance",
                 "2023-06-01", "2026-06-01", "PFA-23-1001", ""),
                ("NPF002", "NST002", "Full PFA (12 hour)", "Red Cross",
                 "2024-03-12", "2027-03-12", "PFA-24-2210", ""),
                ("NPF003", "NST003", "Full PFA (12 hour)", "St John Ambulance",
                 "2024-01-20", "2027-01-20", "PFA-24-1180", ""),
            ],
        )
        logger.info("Seeded nursery demo paediatric first-aid certificates")

    if not conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]:
        conn.executemany(
            "INSERT INTO invoices (invoice_id, pupil_id, period, issue_date, "
            "due_date, hours_billed, hourly_rate, gross_amount, funded_deduction, "
            "discount_amount, total_amount, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NINV001", "NCH001", "June 2025", "2025-06-01", "2025-06-15",
                 50.0, 6.50, 325.0, 195.0, 0.0, 130.0, "issued",
                 "30 funded hours deducted."),
                ("NINV002", "NCH002", "June 2025", "2025-06-01", "2025-06-15",
                 40.0, 6.50, 260.0, 97.50, 26.0, 136.50, "part_paid",
                 "Sibling discount applied."),
                ("NINV003", "NCH004", "June 2025", "2025-06-01", "2025-06-15",
                 45.0, 6.50, 292.50, 195.0, 0.0, 97.50, "paid", ""),
            ],
        )
        logger.info("Seeded nursery demo invoices")

    if not conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]:
        conn.executemany(
            "INSERT INTO payments (payment_id, pupil_id, invoice_id, amount, "
            "method, payment_date, reference, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NPAY001", "NCH002", "NINV002", 50.0, "Tax-Free Childcare",
                 "2025-06-08", "TFC-558201", "Part payment."),
                ("NPAY002", "NCH004", "NINV003", 97.50, "Bank transfer",
                 "2025-06-10", "BACS-90233", "Paid in full."),
            ],
        )
        logger.info("Seeded nursery demo payments")

    if not conn.execute("SELECT COUNT(*) FROM funding_claims").fetchone()[0]:
        conn.executemany(
            "INSERT INTO funding_claims (claim_id, pupil_id, funding_period, "
            "entitlement, funded_hours, weeks, hourly_rate, claim_amount, "
            "headcount_date, status, submitted_date, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NFC001", "NCH001", "Summer 2025", "30 hours", 30.0, 13.0, 5.20,
                 2028.0, "2025-05-15", "submitted", "2025-05-20",
                 "Headcount return submitted to LA."),
                ("NFC002", "NCH003", "Summer 2025", "2-year-old funding", 15.0,
                 13.0, 6.00, 1170.0, "2025-05-15", "draft", None, ""),
            ],
        )
        logger.info("Seeded nursery demo funding claims")

    if not conn.execute("SELECT COUNT(*) FROM childcare_vouchers").fetchone()[0]:
        conn.executemany(
            "INSERT INTO childcare_vouchers (voucher_id, pupil_id, scheme, "
            "provider, account_ref, expected_amount, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NVCH001", "NCH002", "Tax-Free Childcare", "NS&I", "TFC-558201",
                 200.0, "active", "Government top-up scheme."),
                ("NVCH002", "NCH005", "Childcare voucher (employer)", "Edenred",
                 "EDR-77120", 243.0, "active", "Legacy employer scheme."),
            ],
        )
        logger.info("Seeded nursery demo voucher arrangements")

    if not conn.execute("SELECT COUNT(*) FROM fee_discounts").fetchone()[0]:
        conn.executemany(
            "INSERT INTO fee_discounts (discount_id, pupil_id, discount_type, "
            "percentage, fixed_amount, reason, start_date, end_date, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDIS001", "NCH002", "Sibling", 10.0, None,
                 "Second child in family", "2024-09-02", None, "active",
                 "10% off fees while sibling attends."),
            ],
        )
        logger.info("Seeded nursery demo fee discounts")

    # ── Parents & Communication seeds ─────────────────────────────────────────
    if not conn.execute("SELECT COUNT(*) FROM parent_contacts").fetchone()[0]:
        conn.executemany(
            "INSERT INTO parent_contacts (contact_id, pupil_id, full_name, "
            "relationship, phone, email, address, is_primary, "
            "parental_responsibility, can_collect, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NPC001", "NCH001", "Sarah Hughes", "Mother", "07700 900101",
                 "sarah.hughes@example.com", "12 Oak Lane, Bristol", 1, 1, 1,
                 "Primary day-to-day contact."),
                ("NPC002", "NCH001", "Mark Hughes", "Father", "07700 900111",
                 "mark.hughes@example.com", "12 Oak Lane, Bristol", 0, 1, 1, ""),
                ("NPC003", "NCH002", "Raj Patel", "Father", "07700 900102",
                 "raj.patel@example.com", "4 Elm Court, Bristol", 1, 1, 1, ""),
                ("NPC004", "NCH003", "Emma Campbell", "Mother", "07700 900103",
                 "emma.campbell@example.com", "88 Hill Road, Bristol", 1, 1, 1,
                 "Prefers contact by app."),
            ],
        )
        logger.info("Seeded nursery demo parent contacts")

    if not conn.execute("SELECT COUNT(*) FROM emergency_contacts").fetchone()[0]:
        conn.executemany(
            "INSERT INTO emergency_contacts (contact_id, pupil_id, full_name, "
            "relationship, phone_primary, phone_alt, priority, can_collect, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEC001", "NCH001", "Margaret Hughes", "Grandmother",
                 "07700 900131", "0117 496 0001", 1, 1, "Lives nearby."),
                ("NEC002", "NCH002", "Anita Patel", "Grandmother",
                 "07700 900132", None, 1, 1, ""),
                ("NEC003", "NCH002", "David Reed", "Family friend",
                 "07700 900133", None, 2, 0, "Call only if parents unreachable."),
                ("NEC004", "NCH003", "Tom Campbell", "Uncle",
                 "07700 900134", None, 1, 1, ""),
            ],
        )
        logger.info("Seeded nursery demo emergency contacts")

    if not conn.execute("SELECT COUNT(*) FROM consents").fetchone()[0]:
        conn.executemany(
            "INSERT INTO consents (consent_id, pupil_id, consent_type, status, "
            "date_recorded, expiry_date, recorded_by, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NCO001", "NCH001", "Photographs", "granted", "2024-09-02",
                 None, "NST001", "For learning journeys and displays."),
                ("NCO002", "NCH001", "Local outings", "granted", "2024-09-02",
                 None, "NST002", ""),
                ("NCO003", "NCH001", "Social media", "refused", "2024-09-02",
                 None, "NST001", "Parents declined social media use."),
                ("NCO004", "NCH002", "Photographs", "granted", "2024-09-02",
                 None, "NST001", ""),
                ("NCO005", "NCH002", "Sun cream application", "granted",
                 "2025-04-01", "2025-09-30", "NST003", "Parents supply own cream."),
                ("NCO006", "NCH003", "Emergency medical treatment", "granted",
                 "2025-01-06", None, "NST004", "Including ambulance if required."),
            ],
        )
        logger.info("Seeded nursery demo consents")

    if not conn.execute("SELECT COUNT(*) FROM parent_messages").fetchone()[0]:
        conn.executemany(
            "INSERT INTO parent_messages (message_id, pupil_id, direction, "
            "channel, subject, body, message_date, staff_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NMS001", "NCH001", "outgoing", "App", "Settling in well",
                 "Oliver had a lovely morning and enjoyed water play.",
                 "2025-06-02", "NST002", "read"),
                ("NMS002", "NCH002", "incoming", "App", "Running late",
                 "We'll be about 15 minutes late for pick-up today, thank you.",
                 "2025-06-03", None, "replied"),
                ("NMS003", "NCH002", "outgoing", "Email",
                 "Sun cream reminder",
                 "Please could you send in a named bottle of sun cream this week.",
                 "2025-06-04", "NST003", "sent"),
                ("NMS004", "NCH003", "outgoing", "App", "Photo shared",
                 "We've added new photos to Noah's learning journey today.",
                 "2025-06-05", "NST004", "sent"),
            ],
        )
        logger.info("Seeded nursery demo parent messages")

    if not conn.execute("SELECT COUNT(*) FROM daily_updates").fetchone()[0]:
        conn.executemany(
            "INSERT INTO daily_updates (update_id, pupil_id, update_date, mood, "
            "meals, sleep, nappies, activities, notes, staff_id, shared) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDU001", "NCH001", "2025-06-06", "Happy",
                 "Ate all of lunch; tried the broccoli.", "Napped 12:30–13:45",
                 "3 changes, all fine", "Water play, story time, garden.",
                 "Great day — very chatty.", "NST002", 1),
                ("NDU002", "NCH003", "2025-06-06", "Settled",
                 "Had a full bottle mid-morning.", "Two short naps",
                 "4 changes", "Treasure baskets and tummy time.",
                 "Enjoyed the sensory tray.", "NST004", 1),
                ("NDU003", "NCH002", "2025-06-06", "Tired",
                 "Ate half of lunch.", "Did not nap",
                 "Used the toilet independently twice.",
                 "Painting and outdoor play.", "A little tired by home time.",
                 "NST003", 0),
            ],
        )
        logger.info("Seeded nursery demo daily updates")

    if not conn.execute("SELECT COUNT(*) FROM newsletters").fetchone()[0]:
        conn.executemany(
            "INSERT INTO newsletters (newsletter_id, title, issue_date, audience, "
            "body, author, status, published_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NNL001", "June Newsletter", "2025-06-01", "Whole setting",
                 "Welcome to June! This month we're exploring 'Minibeasts'. "
                 "Please send in wellies for garden days.", "NST001",
                 "published", "2025-06-01"),
                ("NNL002", "Preschool Room — Summer Term",
                 "2025-06-03", "Preschool Room",
                 "Our school-readiness focus continues. Reception visits are "
                 "being arranged for our leavers.", "NST003", "published",
                 "2025-06-03"),
                ("NNL003", "Summer Fair — Save the Date", "2025-07-01",
                 "Whole setting",
                 "Our summer fair will be held in July. More details to follow.",
                 "NST001", "draft", None),
            ],
        )
        logger.info("Seeded nursery demo newsletters")

    if not conn.execute("SELECT COUNT(*) FROM parent_meetings").fetchone()[0]:
        conn.executemany(
            "INSERT INTO parent_meetings (meeting_id, pupil_id, meeting_date, "
            "meeting_time, meeting_type, staff_id, location, status, summary, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NPM001", "NCH003", "2025-02-10", "15:30", "Settling review",
                 "NST004", "Baby Room", "completed",
                 "Noah has settled well; agreed to extend sessions.", ""),
                ("NPM002", "NCH002", "2025-06-20", "16:00",
                 "Progress meeting", "NST003", "Preschool Room", "scheduled",
                 "", "Discuss school readiness ahead of transition."),
                ("NPM003", "NCH003", "2025-07-05", "15:45",
                 "2-year progress check", "NST004", "Baby Room", "scheduled",
                 "", "Statutory 2-year-old progress check review."),
            ],
        )
        logger.info("Seeded nursery demo parent meetings")

    # ── Daily register (attendance) ───────────────────────────────────────────
    # Generated against the last 10 weekdays so the Attendance Report shows live
    # data whenever the demo DB is first created. Mostly present, with a few
    # late / absent / sick rows so the rates and breakdowns aren't trivially 100%.
    if not conn.execute("SELECT COUNT(*) FROM attendance_records").fetchone()[0]:
        _seed_attendance(conn)
        logger.info("Seeded nursery demo attendance register")

    # ── Accident / incident register ──────────────────────────────────────────
    if not conn.execute("SELECT COUNT(*) FROM accident_records").fetchone()[0]:
        conn.executemany(
            "INSERT INTO accident_records (record_id, pupil_id, record_type, "
            "occurred_date, occurred_time, location, description, injury, "
            "body_part, treatment, first_aider, severity, parent_informed, "
            "parent_signed, riddor_reportable, action_taken, recorded_by, "
            "status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NAC001", "NCH001", "accident",
                 (_dt.date.today() - _dt.timedelta(days=6)).isoformat(), "10:25",
                 "Toddler garden", "Tripped on the path while running.",
                 "Grazed knee", "Left knee",
                 "Cleaned with a wipe and a plaster applied.", "NST002", "minor",
                 1, 1, 0, "Reminded children to walk on the path.", "NST002",
                 "closed", ""),
                ("NAC002", "NCH004", "accident",
                 (_dt.date.today() - _dt.timedelta(days=3)).isoformat(), "14:10",
                 "Toddler Room", "Bumped head on the edge of the play table.",
                 "Small bump", "Forehead",
                 "Cold compress applied; monitored for the afternoon.", "NST002",
                 "moderate", 1, 1, 0,
                 "Padded the table corner.", "NST002", "closed",
                 "Head-bump letter given to parent."),
                ("NAC003", "NCH002", "incident",
                 (_dt.date.today() - _dt.timedelta(days=2)).isoformat(), "11:40",
                 "Preschool Room", "Two children disagreed over a toy.",
                 "None", None, "Supported to share and take turns.", "NST003",
                 "minor", 1, 0, 0, "Circle-time on sharing planned.", "NST003",
                 "closed", ""),
                ("NAC004", "NCH003", "near-miss",
                 (_dt.date.today() - _dt.timedelta(days=1)).isoformat(), "09:15",
                 "Baby Room", "Low shelf was unstable; spotted before use.",
                 "None", None, "", "NST004", "minor", 0, 0, 0,
                 "Shelf secured to the wall by the caretaker.", "NST004",
                 "open", "Logged as a near-miss for the risk assessment review."),
            ],
        )
        logger.info("Seeded nursery demo accident/incident records")

    # ── EYFS Learning & Development seeds ─────────────────────────────────────
    if not conn.execute("SELECT COUNT(*) FROM eyfs_profiles").fetchone()[0]:
        conn.executemany(
            "INSERT INTO eyfs_profiles (profile_id, pupil_id, assessment_date, "
            "term, communication_language, physical_development, pse_development, "
            "literacy, mathematics, understanding_world, expressive_arts, summary, "
            "assessor, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEP001", "NCH002", "2025-05-30", "Summer 2025", "Expected",
                 "Expected", "Expected", "Emerging", "Expected", "Expected",
                 "Exceeding",
                 "On track across most areas; literacy emerging. Ready for "
                 "Reception in September.", "NST003", "finalised"),
                ("NEP002", "NCH005", "2025-05-30", "Summer 2025", "Expected",
                 "Exceeding", "Expected", "Expected", "Expected", "Expected",
                 "Expected", "Confident learner, strong physical development.",
                 "NST003", "draft"),
            ],
        )
        logger.info("Seeded nursery demo EYFS profiles")

    if not conn.execute("SELECT COUNT(*) FROM development_tracking").fetchone()[0]:
        conn.executemany(
            "INSERT INTO development_tracking (record_id, pupil_id, area, aspect, "
            "age_band, judgement, assessment_date, assessor, next_steps, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDT001", "NCH001", "Communication and Language", "Listening and Attention",
                 "22 to 36 months", "Developing", "2025-05-12", "NST002",
                 "Encourage turn-taking in conversation.", ""),
                ("NDT002", "NCH001", "Physical Development", "Moving and Handling",
                 "22 to 36 months", "Secure", "2025-05-12", "NST002", "", ""),
                ("NDT003", "NCH002", "Literacy", "Reading",
                 "30 to 50 months", "Emerging", "2025-05-14", "NST003",
                 "Share more rhyming books to build phonological awareness.", ""),
                ("NDT004", "NCH002", "Mathematics", "Numbers",
                 "30 to 50 months", "Developing", "2025-05-14", "NST003", "", ""),
            ],
        )
        logger.info("Seeded nursery demo development tracking")

    if not conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]:
        conn.executemany(
            "INSERT INTO observations (observation_id, pupil_id, observation_date, "
            "observation_type, area, title, description, context, next_step, staff_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NOB001", "NCH001", "2025-06-02", "Spontaneous",
                 "Communication and Language", "Water play chatter",
                 "Oliver described pouring water 'up and over' to a friend.",
                 "Water tray, free play",
                 "Model positional language during play.", "NST002"),
                ("NOB002", "NCH002", "2025-06-03", "Planned", "Mathematics",
                 "Counting cars", "Amelia counted six cars accurately, "
                 "matching one number name to each.", "Adult-led small group",
                 "Extend to counting out a given number.", "NST003"),
                ("NOB003", "NCH003", "2025-06-04", "Focused",
                 "Physical Development", "Tummy-time reaching",
                 "Noah reached and grasped a rattle during tummy time.",
                 "Baby room floor play", "Offer varied textures to grasp.",
                 "NST004"),
            ],
        )
        logger.info("Seeded nursery demo observations")

    if not conn.execute("SELECT COUNT(*) FROM learning_journeys").fetchone()[0]:
        conn.executemany(
            "INSERT INTO learning_journeys (entry_id, pupil_id, entry_date, title, "
            "area, description, wow_moment, shared_with_parent, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NLJ001", "NCH001", "2025-05-20", "First full sentence",
                 "Communication and Language",
                 "Oliver said 'I want the red one please' — his first clear "
                 "full sentence at nursery.", 1, 1, "NST002", ""),
                ("NLJ002", "NCH002", "2025-05-28", "Wrote her name",
                 "Literacy", "Amelia wrote the first letter of her name "
                 "independently.", 1, 1, "NST003", ""),
                ("NLJ003", "NCH003", "2025-06-01", "Sat unaided",
                 "Physical Development",
                 "Noah sat without support for the first time.", 1, 0,
                 "NST004", "Share with parents at pick-up."),
            ],
        )
        logger.info("Seeded nursery demo learning journeys")

    if not conn.execute("SELECT COUNT(*) FROM next_steps").fetchone()[0]:
        conn.executemany(
            "INSERT INTO next_steps (step_id, pupil_id, area, description, "
            "planned_date, target_date, status, achieved_date, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NNS001", "NCH001", "Communication and Language",
                 "Use positional language (up, over, under) in play.",
                 "2025-06-02", "2025-07-04", "in_progress", None, "NST002", ""),
                ("NNS002", "NCH002", "Literacy",
                 "Recognise and join in with rhyming strings.",
                 "2025-05-14", "2025-06-30", "planned", None, "NST003", ""),
                ("NNS003", "NCH002", "Mathematics",
                 "Count out a given number of objects up to 5.",
                 "2025-05-14", "2025-06-13", "achieved", "2025-06-10",
                 "NST003", "Achieved earlier than targeted."),
            ],
        )
        logger.info("Seeded nursery demo next steps")

    if not conn.execute("SELECT COUNT(*) FROM progress_check_2yr").fetchone()[0]:
        conn.executemany(
            "INSERT INTO progress_check_2yr (check_id, pupil_id, check_date, "
            "age_months, comm_language, physical_development, pse_development, "
            "summary, strengths, areas_of_concern, shared_with_parents, "
            "shared_with_hv, staff_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NP2001", "NCH003", "2025-06-05", 24,
                 "Developing — babbling and beginning to use single words.",
                 "Secure — crawling confidently, pulling to stand.",
                 "Developing — forming a strong bond with key person.",
                 "Noah is making good progress across the prime areas.",
                 "Physical development; strong attachment to key person.",
                 "None identified at this stage.", 1, 0, "NST004", "finalised"),
            ],
        )
        logger.info("Seeded nursery demo 2-year progress checks")

    if not conn.execute("SELECT COUNT(*) FROM effective_learning").fetchone()[0]:
        conn.executemany(
            "INSERT INTO effective_learning (record_id, pupil_id, observation_date, "
            "characteristic, aspect, description, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEL001", "NCH001", "2025-06-02", "Playing and Exploring",
                 "Finding out and exploring",
                 "Oliver investigated how water moved through the guttering.",
                 "NST002", ""),
                ("NEL002", "NCH002", "2025-06-03", "Creating and Thinking Critically",
                 "Making links",
                 "Amelia predicted which cup would hold the most water.",
                 "NST003", ""),
                ("NEL003", "NCH005", "2025-06-04", "Active Learning",
                 "Persistence",
                 "Leo kept trying to complete the puzzle despite difficulty.",
                 "NST003", ""),
            ],
        )
        logger.info("Seeded nursery demo characteristics of effective learning")

    if not conn.execute("SELECT COUNT(*) FROM curriculum_planning").fetchone()[0]:
        conn.executemany(
            "INSERT INTO curriculum_planning (plan_id, title, plan_date, room, "
            "area, theme, learning_intention, activities, resources, staff_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NCP001", "Minibeasts week", "2025-06-09", "Preschool Room",
                 "Understanding the World", "Minibeasts",
                 "To explore and name common minibeasts and their habitats.",
                 "Bug hunt in the garden; making a wormery; minibeast songs.",
                 "Magnifying glasses, bug pots, non-fiction books.", "NST003",
                 "planned"),
                ("NCP002", "Heuristic play", "2025-06-02", "Baby Room",
                 "Physical Development", "Treasure baskets",
                 "To develop grasping and exploration through natural materials.",
                 "Treasure basket exploration; texture trays.",
                 "Wooden objects, fabrics, natural materials.", "NST004",
                 "delivered"),
            ],
        )
        logger.info("Seeded nursery demo curriculum plans")

    if not conn.execute("SELECT COUNT(*) FROM cohort_tracking").fetchone()[0]:
        conn.executemany(
            "INSERT INTO cohort_tracking (cohort_id, cohort_name, room, term, area, "
            "total_children, below_count, on_track_count, above_count, "
            "assessment_date, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NCT001", "Preschool Summer 2025", "Preschool Room",
                 "Summer 2025", "Communication and Language", 24, 3, 18, 3,
                 "2025-05-30", "NST003", "Three children below tracked for support."),
                ("NCT002", "Preschool Summer 2025", "Preschool Room",
                 "Summer 2025", "Literacy", 24, 6, 16, 2, "2025-05-30",
                 "NST003", "Literacy the priority area for the cohort."),
                ("NCT003", "Toddler Summer 2025", "Toddler Room",
                 "Summer 2025", "Personal, Social and Emotional Development",
                 16, 2, 12, 2, "2025-05-30", "NST002", ""),
            ],
        )
        logger.info("Seeded nursery demo cohort tracking")

    if not conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]:
        conn.executemany(
            "INSERT INTO evidence (evidence_id, pupil_id, capture_date, title, "
            "evidence_type, area, file_ref, description, shared_with_parent, staff_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEV001", "NCH001", "2025-06-02", "Water play photo", "Photo",
                 "Communication and Language", "photos/nch001_waterplay.jpg",
                 "Oliver describing the water flow to a friend.", 1, "NST002"),
                ("NEV002", "NCH002", "2025-05-28", "Name writing sample",
                 "Work sample", "Literacy", "samples/nch002_name.jpg",
                 "First attempt at writing her name.", 1, "NST003"),
                ("NEV003", "NCH003", "2025-06-01", "Sitting unaided video",
                 "Video", "Physical Development", "videos/nch003_sitting.mp4",
                 "Noah sitting without support.", 0, "NST004"),
            ],
        )
        logger.info("Seeded nursery demo evidence")

    # ── Daily Care & Routines seeds ───────────────────────────────────────────
    _today = _dt.date.today().isoformat()
    _yest = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()

    if not conn.execute("SELECT COUNT(*) FROM sign_in_out_log").fetchone()[0]:
        conn.executemany(
            "INSERT INTO sign_in_out_log (event_id, pupil_id, event_date, "
            "event_time, direction, person_name, relationship, recorded_by, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NSO001", "NCH001", _today, "08:32", "in", "Sarah Hughes",
                 "Mother", "NST002", ""),
                ("NSO002", "NCH004", _today, "08:45", "in", "Liam Murphy",
                 "Father", "NST002", ""),
                ("NSO003", "NCH002", _today, "09:05", "in", "Raj Patel",
                 "Father", "NST003", "Arrived a little late."),
                ("NSO004", "NCH001", _yest, "15:28", "out", "Margaret Hughes",
                 "Grandmother", "NST002", "On the authorised collection list."),
            ],
        )
        logger.info("Seeded nursery demo sign in/out events")

    if not conn.execute("SELECT COUNT(*) FROM daily_diary").fetchone()[0]:
        conn.executemany(
            "INSERT INTO daily_diary (entry_id, pupil_id, entry_date, mood, "
            "activities, highlights, notes, staff_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDD001", "NCH001", _today, "Happy",
                 "Water play, story time, garden.",
                 "Counted to ten unprompted at snack time.",
                 "Very chatty today.", "NST002"),
                ("NDD002", "NCH003", _today, "Settled",
                 "Treasure baskets and tummy time.",
                 "Sat unaided for a few seconds.",
                 "Enjoyed the sensory tray.", "NST004"),
            ],
        )
        logger.info("Seeded nursery demo daily diary entries")

    if not conn.execute("SELECT COUNT(*) FROM sleep_log").fetchone()[0]:
        conn.executemany(
            "INSERT INTO sleep_log (sleep_id, pupil_id, sleep_date, start_time, "
            "end_time, duration_minutes, location, checks, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NSL001", "NCH003", _today, "12:30", "13:45", 75, "Cot", 8,
                 "NST004", "Settled quickly; checked every 10 minutes."),
                ("NSL002", "NCH001", _today, "12:40", "13:30", 50, "Sleep mat", 5,
                 "NST002", ""),
            ],
        )
        logger.info("Seeded nursery demo sleep log")

    if not conn.execute("SELECT COUNT(*) FROM toileting_log").fetchone()[0]:
        conn.executemany(
            "INSERT INTO toileting_log (record_id, pupil_id, log_date, log_time, "
            "type, cream_applied, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NTL001", "NCH003", _today, "09:50", "nappy - wet", 0, "NST004", ""),
                ("NTL002", "NCH003", _today, "13:50", "nappy - soiled", 1, "NST004",
                 "Barrier cream applied."),
                ("NTL003", "NCH001", _today, "10:15", "toilet", 0, "NST002",
                 "Used the toilet independently."),
            ],
        )
        logger.info("Seeded nursery demo toileting log")

    if not conn.execute("SELECT COUNT(*) FROM meals").fetchone()[0]:
        conn.executemany(
            "INSERT INTO meals (meal_id, pupil_id, meal_date, meal_type, menu, "
            "amount_eaten, drink, allergy_safe, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NML001", "NCH001", _today, "Lunch",
                 "Cottage pie with vegetables", "all", "Water", 1, "NST002", ""),
                ("NML002", "NCH002", _today, "Lunch",
                 "Cottage pie (nut-free kitchen)", "most", "Milk", 1, "NST003",
                 "Peanut allergy — meal checked against care plan."),
                ("NML003", "NCH004", _today, "Lunch",
                 "Cottage pie (dairy-free portion)", "some", "Water", 1, "NST002",
                 "Dairy intolerance — dairy-free option served."),
            ],
        )
        logger.info("Seeded nursery demo meals")

    if not conn.execute("SELECT COUNT(*) FROM bottle_feeds").fetchone()[0]:
        conn.executemany(
            "INSERT INTO bottle_feeds (feed_id, pupil_id, feed_date, feed_time, "
            "milk_type, offered_ml, taken_ml, temperature_checked, winded, "
            "staff_id, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NBF001", "NCH003", _today, "10:30", "Formula", 180, 160, 1, 1,
                 "NST004", "Took most of the bottle."),
                ("NBF002", "NCH003", _today, "14:15", "Formula", 180, 120, 1, 1,
                 "NST004", "A little unsettled; winded well."),
            ],
        )
        logger.info("Seeded nursery demo bottle feeds")

    if not conn.execute("SELECT COUNT(*) FROM dietary_requirements").fetchone()[0]:
        conn.executemany(
            "INSERT INTO dietary_requirements (record_id, pupil_id, category, "
            "allergen, severity, reaction, action_required, epipen_required, "
            "care_plan_ref, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDR001", "NCH002", "allergy", "Peanuts", "anaphylaxis",
                 "Swelling, difficulty breathing",
                 "Administer EpiPen and call 999.", 1, "CP-NCH002-001",
                 "active", "EpiPen kept in the office."),
                ("NDR002", "NCH004", "intolerance", "Dairy", "moderate",
                 "Stomach upset", "Serve dairy-free alternatives.", 0,
                 "CP-NCH004-001", "active", ""),
            ],
        )
        logger.info("Seeded nursery demo dietary requirements")

    if not conn.execute("SELECT COUNT(*) FROM existing_injuries").fetchone()[0]:
        conn.executemany(
            "INSERT INTO existing_injuries (record_id, pupil_id, observed_date, "
            "observed_time, body_part, description, explanation, observed_by, "
            "parent_informed, parent_signed, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEI001", "NCH004", _today, "08:46", "Left shin",
                 "Small bruise", "Fell off scooter at home over the weekend.",
                 "NST002", 1, 1, "Logged on arrival; parent signed."),
            ],
        )
        logger.info("Seeded nursery demo existing injuries")

    if not conn.execute("SELECT COUNT(*) FROM medication_log").fetchone()[0]:
        conn.executemany(
            "INSERT INTO medication_log (record_id, pupil_id, medication_name, "
            "dose, route, reason, administered_date, administered_time, "
            "administered_by, witnessed_by, parent_consent, expiry_date, status, "
            "notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NMD001", "NCH002", "Piriton (antihistamine)", "2.5 ml", "Oral",
                 "Mild hayfever symptoms", _today, "11:00", "NST003", "NST001",
                 1, "2026-04-30", "administered",
                 "Written parental consent on file."),
                ("NMD002", "NCH001", "Calpol (paracetamol)", "5 ml", "Oral",
                 "Temperature after lunch", _yest, "13:15", "NST002", "NST001",
                 1, "2026-08-31", "administered", "Parent informed at collection."),
            ],
        )
        logger.info("Seeded nursery demo medication log")

    # Contracted weekly patterns — the booking calendar the day view resolves.
    # 0=Mon … 4=Fri; the demo children are on a mix of full-time, part-week and
    # morning-only contracts so ratios and occupancy vary across the week.
    if not conn.execute("SELECT COUNT(*) FROM booking_patterns").fetchone()[0]:
        _term_start = (_dt.date.today() - _dt.timedelta(days=120)).isoformat()
        _patterns = []
        _contracts = [
            ("NCH001", (0, 1, 2, 3, 4), "all-day", "Toddler Room", "funded"),
            ("NCH002", (0, 1, 2), "am", "Preschool Room", "funded"),
            ("NCH003", (1, 3), "all-day", "Baby Room", "funded"),
            ("NCH004", (0, 1, 2, 3, 4), "all-day", "Toddler Room", "mixed"),
            ("NCH005", (2, 3, 4), "pm", "Preschool Room", "funded"),
        ]
        _seq = 1
        for pupil, days, session, room, funding in _contracts:
            start, end = {"am": ("08:00", "13:00"), "pm": ("13:00", "18:00"),
                          "all-day": ("08:00", "18:00")}[session]
            for weekday in days:
                _patterns.append((f"NBP{_seq:03d}", pupil, weekday, session,
                                  start, end, room, funding, _term_start, None,
                                  "active", ""))
                _seq += 1
        conn.executemany(
            "INSERT INTO booking_patterns (pattern_id, pupil_id, weekday, "
            "session_type, start_time, end_time, room, funding, start_date, "
            "end_date, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _patterns,
        )
        logger.info("Seeded nursery demo booking patterns")

    if not conn.execute("SELECT COUNT(*) FROM session_bookings").fetchone()[0]:
        _next_week = (_dt.date.today() + _dt.timedelta(days=7)).isoformat()
        conn.executemany(
            "INSERT INTO session_bookings (booking_id, pupil_id, session_date, "
            "session_type, kind, start_time, end_time, room, chargeable, "
            "notice_days, reason, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NSB001", "NCH003", _next_week, "all-day", "extra", "08:00",
                 "18:00", "Baby Room", 1, 5,
                 "Parent working an extra shift", "confirmed", ""),
                ("NSB002", "NCH002", _next_week, "am", "cancellation", None,
                 None, "Preschool Room", 0, 7, "Family holiday", "confirmed",
                 "Notice given in writing."),
            ],
        )
        logger.info("Seeded nursery demo session bookings")

    if not conn.execute("SELECT COUNT(*) FROM setting_closures").fetchone()[0]:
        _inset = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
        _xmas_year = _dt.date.today().year
        conn.executemany(
            "INSERT INTO setting_closures (closure_id, name, start_date, "
            "end_date, closure_type, room, chargeable, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NCL001", "Staff training day", _inset, _inset, "inset", None,
                 1, "Whole setting closed for safeguarding training."),
                ("NCL002", "Christmas closure", f"{_xmas_year}-12-24",
                 f"{_xmas_year + 1}-01-02", "holiday", None, 0, ""),
            ],
        )
        logger.info("Seeded nursery demo closures")

    # Authorised collectors. Passwords are seeded as PBKDF2 hashes of the demo
    # phrases noted below, never in the clear — the collections domain hashes
    # any new ones the same way.
    if not conn.execute(
            "SELECT COUNT(*) FROM authorised_collectors").fetchone()[0]:
        from education_system.nursery_system.modules.domain.collections import (
            collections as _collections,
        )
        conn.executemany(
            "INSERT INTO authorised_collectors (collector_id, pupil_id, "
            "full_name, relationship, phone, password_hash, photo_on_file, "
            "id_checked, is_escalation_contact, valid_from, valid_until, "
            "status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                # Demo collection password: "bluebell"
                ("NAC001", "NCH001", "Sarah Hughes", "Parent", "07700 900101",
                 _collections.hash_password("bluebell"), 1, 1, 0, None, None,
                 "active", ""),
                ("NAC002", "NCH001", "Margaret Hughes", "Grandparent",
                 "07700 900151", None, 1, 1, 1, None, None, "active",
                 "Collects on Fridays."),
                # Demo collection password: "seahorse"
                ("NAC003", "NCH002", "Raj Patel", "Parent", "07700 900102",
                 _collections.hash_password("seahorse"), 1, 1, 0, None, None,
                 "active", ""),
                ("NAC004", "NCH003", "Emma Campbell", "Parent", "07700 900103",
                 None, 0, 0, 0, None, None, "active",
                 "Photo ID still to be checked."),
            ],
        )
        logger.info("Seeded nursery demo authorised collectors")

    if not conn.execute("SELECT COUNT(*) FROM late_collections").fetchone()[0]:
        conn.executemany(
            "INSERT INTO late_collections (record_id, pupil_id, event_date, "
            "due_time, collected_time, minutes_late, collected_by, "
            "collector_id, fee_amount, fee_status, escalation_stage, "
            "escalated_to, parent_contacted, safeguarding_referral, "
            "recorded_by, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NLC001", "NCH004", _yest, "18:00", "18:25", 25,
                 "Liam Murphy", None, 10.0, "invoiced", "parent-called", None,
                 1, 0, "NST001", "Traffic on the ring road; parent called at "
                 "18:05."),
            ],
        )
        logger.info("Seeded nursery demo late collections")

    conn.commit()
