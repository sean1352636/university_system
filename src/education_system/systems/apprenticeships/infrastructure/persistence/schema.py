"""SQLite schema and connection handling for the apprenticeships system.

One physical database file holds every table. The screens are join-heavy
by nature — an apprentice's dashboard reads their programme, employer,
off-the-job hours, portfolio, reviews, gateway and EPA record in one go —
so splitting these across files would buy nothing and cost cross-connection
coordination.

Conventions, matching the rest of the platform:

* dates are ISO ``YYYY-MM-DD`` TEXT, timestamps ``datetime('now')`` UTC
* money is REAL, booleans are INTEGER 0/1
* every table carries ``created_at``; mutable ones carry ``updated_at``
* foreign keys are declared and enforced (``PRAGMA foreign_keys=ON``)

``init_db()`` is idempotent and cheap after the first call. Every public
service function calls it before touching the database, so no caller has
to remember to bootstrap.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.APPRENTICESHIPS_DB


# ═════════════════════════════════════════════════════════════════════
# Schema
# ═════════════════════════════════════════════════════════════════════

SCHEMA: str = """
-- ── Employers ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS employers (
    employer_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    -- Companies House number, when the employer is a registered company.
    company_number  TEXT,
    sector          TEXT,
    size            TEXT,                       -- config.EMPLOYER_SIZES
    headcount       INTEGER,
    -- Annual pay bill: decides levy liability and co-investment rate.
    paybill         REAL,
    address         TEXT,
    postcode        TEXT,
    status          TEXT    NOT NULL DEFAULT 'Prospect',
    contract_start  TEXT,
    contract_end    TEXT,
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employer_workplaces (
    workplace_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id       INTEGER NOT NULL,
    name              TEXT    NOT NULL,
    address           TEXT,
    postcode          TEXT,
    -- Health and safety vetting must be current for apprentices to be
    -- placed here; the compliance screen flags stale checks.
    hs_checked_date   TEXT,
    hs_expiry_date    TEXT,
    active            INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employer_managers (
    manager_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id  INTEGER NOT NULL,
    full_name    TEXT    NOT NULL,
    job_title    TEXT,
    email        TEXT,
    phone        TEXT,
    -- The signatory on the commitment statement and progress reviews.
    is_primary   INTEGER NOT NULL DEFAULT 0,
    -- Login handle, so an employer user can be matched to their record.
    username     TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    -- What they do for the apprenticeship: config.EMPLOYER_CONTACT_ROLES.
    contact_role TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE
);

-- ── Programmes (apprenticeship standards) ──────────────────────────

CREATE TABLE IF NOT EXISTS programmes (
    programme_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    -- e.g. ST0119. Unique per version, not alone: every version of a
    -- standard is its own row sharing the reference.
    reference         TEXT    NOT NULL,
    title             TEXT    NOT NULL,
    level             INTEGER NOT NULL,
    funding_band      INTEGER NOT NULL,         -- 1..15, see config.FUNDING_BANDS
    duration_months   INTEGER NOT NULL,
    -- Comma-separated config.EPA_METHODS the EPAO will use.
    epa_methods       TEXT,
    sector            TEXT,
    description       TEXT,
    status            TEXT    NOT NULL DEFAULT 'Draft',
    version           TEXT    NOT NULL DEFAULT '1.0',
    -- The version this one replaced; that row is now 'Superseded'.
    supersedes_programme_id INTEGER,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (supersedes_programme_id)
        REFERENCES programmes(programme_id) ON DELETE SET NULL,
    UNIQUE (reference, version)
);

CREATE TABLE IF NOT EXISTS programme_ksbs (
    ksb_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id  INTEGER NOT NULL,
    code          TEXT    NOT NULL,             -- K1, S4, B2 …
    ksb_type      TEXT    NOT NULL,             -- config.KSB_TYPES
    description   TEXT    NOT NULL,
    duty_ref      TEXT,                         -- occupational duty it serves
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE,
    UNIQUE (programme_id, code)
);

CREATE TABLE IF NOT EXISTS occupational_duties (
    duty_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id  INTEGER NOT NULL,
    code          TEXT    NOT NULL,             -- D1, D2 …
    description   TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE,
    UNIQUE (programme_id, code)
);

-- ── Degree apprenticeship integration ─────────────────────────────────
-- These rows contain links only. Academic records, credits and outcomes
-- remain owned by the university database and are never copied here.

CREATE TABLE IF NOT EXISTS degree_apprenticeship_programmes (
    apprenticeship_programme_id INTEGER PRIMARY KEY,
    university_degree_program_id INTEGER NOT NULL,
    credits_required             REAL,
    integration_type             TEXT NOT NULL DEFAULT 'Integrated',
    active                       INTEGER NOT NULL DEFAULT 1,
    created_at                   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprenticeship_programme_id)
        REFERENCES programmes(programme_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS degree_apprenticeship_links (
    link_id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id                 INTEGER NOT NULL UNIQUE,
    journey_id                    TEXT NOT NULL UNIQUE,
    university_student_id         TEXT NOT NULL UNIQUE,
    university_degree_program_id  INTEGER NOT NULL,
    status                        TEXT NOT NULL DEFAULT 'Pending',
    reconciliation_state          TEXT NOT NULL DEFAULT 'Pending',
    linked_at                     TEXT,
    last_academic_sync_at         TEXT,
    created_at                    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_degree_link_journey
    ON degree_apprenticeship_links(journey_id);
CREATE INDEX IF NOT EXISTS ix_degree_link_university_student
    ON degree_apprenticeship_links(university_student_id);

-- Replaceable dashboard projection. Every academic value originates in a
-- university event and may be rebuilt; it is never used as the academic
-- system of record.
CREATE TABLE IF NOT EXISTS degree_academic_progress_projection (
    apprentice_id                 INTEGER PRIMARY KEY,
    university_student_id         TEXT NOT NULL,
    university_degree_program_id  INTEGER NOT NULL,
    degree_program_code           TEXT,
    degree_program_name           TEXT,
    registration_status           TEXT,
    credits_earned                REAL NOT NULL DEFAULT 0,
    credits_required              REAL NOT NULL DEFAULT 0,
    modules_completed             INTEGER NOT NULL DEFAULT 0,
    academic_standing             TEXT,
    university_gateway_confirmed  INTEGER NOT NULL DEFAULT 0,
    degree_outcome                TEXT,
    degree_awarded_at             TEXT,
    source_event_id               TEXT NOT NULL UNIQUE,
    source_occurred_at            TEXT,
    updated_at                    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

-- ── Provider staff ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS staff (
    staff_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   TEXT    NOT NULL,
    email       TEXT,
    phone       TEXT,
    staff_role  TEXT    NOT NULL DEFAULT 'Tutor',   -- config.STAFF_ROLES
    -- Login handle, so a staff user can be matched to their caseload.
    username    TEXT,
    -- Standards this member of staff is qualified to deliver, comma-separated.
    specialisms TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Apprentices ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS apprentices (
    apprentice_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Unique Learner Number: 10 digits, follows the learner for life.
    uln               TEXT    UNIQUE,
    -- The platform's canonical cross-system identity, stamped when the
    -- apprentice arrived from (or was matched to) another system. Also
    -- what makes a redelivered handover idempotent: a second delivery
    -- finds this row instead of creating a duplicate apprentice.
    journey_id        TEXT,
    given_name        TEXT    NOT NULL,
    middle_name       TEXT,
    family_name       TEXT    NOT NULL,
    preferred_name    TEXT,
    date_of_birth     TEXT,
    gender            TEXT,                     -- config.GENDERS
    email             TEXT,
    phone             TEXT,
    address_line1     TEXT,
    address_line2     TEXT,
    town              TEXT,
    postcode          TEXT,
    emergency_contact_name          TEXT,
    emergency_contact_relationship  TEXT,
    emergency_contact_phone         TEXT,
    -- Login handle, so an apprentice user can be matched to their record.
    username          TEXT,
    programme_id      INTEGER,
    employer_id       INTEGER,
    workplace_id      INTEGER,
    tutor_id          INTEGER,
    status            TEXT    NOT NULL DEFAULT 'Applicant',
    start_date        TEXT,
    planned_end_date  TEXT,
    actual_end_date   TEXT,
    -- Contracted weekly hours: below 30 the programme must be extended.
    weekly_hours      REAL    NOT NULL DEFAULT 30.0,
    funding_model     TEXT,                     -- config.FUNDING_MODELS
    prior_learning    TEXT,
    support_needs     TEXT,
    -- Learning difficulty or disability, and an Education, Health and
    -- Care plan: the needs flags the other systems record on add.
    has_lldd          INTEGER NOT NULL DEFAULT 0,
    has_ehcp          INTEGER NOT NULL DEFAULT 0,
    medical_notes     TEXT,
    notes             TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE SET NULL,
    FOREIGN KEY (employer_id)  REFERENCES employers(employer_id)  ON DELETE SET NULL,
    FOREIGN KEY (workplace_id) REFERENCES employer_workplaces(workplace_id) ON DELETE SET NULL,
    FOREIGN KEY (tutor_id)     REFERENCES staff(staff_id)         ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS apprentice_status_history (
    history_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    from_status    TEXT,
    to_status      TEXT    NOT NULL,
    reason         TEXT,
    effective_date TEXT    NOT NULL,
    actor          TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS breaks_in_learning (
    break_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id       INTEGER NOT NULL,
    start_date          TEXT    NOT NULL,
    expected_return     TEXT,
    actual_return       TEXT,
    reason              TEXT    NOT NULL,
    notes               TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS withdrawals (
    withdrawal_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id      INTEGER NOT NULL,
    withdrawal_date    TEXT    NOT NULL,
    last_activity_date TEXT,
    reason             TEXT    NOT NULL,
    notes              TEXT,
    recorded_by        TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

-- ── Training delivery ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS training_sessions (
    session_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id   INTEGER,
    title          TEXT    NOT NULL,
    session_date   TEXT    NOT NULL,
    start_time     TEXT,
    end_time       TEXT,
    delivery_mode  TEXT    NOT NULL DEFAULT 'Classroom',
    location       TEXT,
    trainer_id     INTEGER,
    capacity       INTEGER,
    -- Off-the-job hours each attendee earns for a full attendance.
    otj_hours      REAL    NOT NULL DEFAULT 0,
    ksb_codes      TEXT,
    notes          TEXT,
    status         TEXT    NOT NULL DEFAULT 'Scheduled',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE SET NULL,
    FOREIGN KEY (trainer_id)   REFERENCES staff(staff_id)          ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS session_attendance (
    attendance_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     INTEGER NOT NULL,
    apprentice_id  INTEGER NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'Present',
    -- Hours actually earned; defaults to the session's but a late
    -- arrival earns less.
    otj_hours      REAL    NOT NULL DEFAULT 0,
    notes          TEXT,
    -- config.ABSENCE_REASONS; set only on Absent / Excused marks.
    absence_reason TEXT,
    recorded_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id)    REFERENCES training_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id)    ON DELETE CASCADE,
    UNIQUE (session_id, apprentice_id)
);

CREATE TABLE IF NOT EXISTS training_plan_items (
    item_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    title          TEXT    NOT NULL,
    description    TEXT,
    planned_start  TEXT,
    planned_end    TEXT,
    planned_hours  REAL    NOT NULL DEFAULT 0,
    ksb_codes      TEXT,
    delivery_mode  TEXT,
    status         TEXT    NOT NULL DEFAULT 'Planned',   -- config.PLAN_ITEM_STATUSES
    -- The learning-plan objective this activity delivers, if any.
    objective_id   INTEGER,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    FOREIGN KEY (objective_id)  REFERENCES ilp_objectives(objective_id) ON DELETE SET NULL
);

-- ── Individual learning plan ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ilp_objectives (
    objective_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    title          TEXT    NOT NULL,
    description    TEXT,
    ksb_codes      TEXT,
    target_date    TEXT,
    status         TEXT    NOT NULL DEFAULT 'Not started',   -- config.OBJECTIVE_STATUSES
    progress       INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    achieved_at    TEXT,
    created_by     TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_ilp_objectives_appr ON ilp_objectives(apprentice_id);

-- The conversation on a plan. A deleted objective leaves its comments on
-- the plan as a whole rather than taking the history with it.
CREATE TABLE IF NOT EXISTS ilp_comments (
    comment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    objective_id   INTEGER,
    author         TEXT    NOT NULL,
    author_role    TEXT    NOT NULL,
    body           TEXT    NOT NULL,
    -- Set when the comment records a progress update.
    progress       INTEGER,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id)   ON DELETE CASCADE,
    FOREIGN KEY (objective_id)  REFERENCES ilp_objectives(objective_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_ilp_comments_appr ON ilp_comments(apprentice_id);

-- ── Off-the-job hours ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS otj_entries (
    entry_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id   INTEGER NOT NULL,
    activity_date   TEXT    NOT NULL,
    hours           REAL    NOT NULL,
    activity_type   TEXT    NOT NULL,
    description     TEXT    NOT NULL,
    ksb_codes       TEXT,
    status          TEXT    NOT NULL DEFAULT 'Draft',
    -- Set when a training session register generated this entry, so a
    -- register correction can find and update it.
    session_id      INTEGER,
    submitted_at    TEXT,
    approved_by     TEXT,
    approved_at     TEXT,
    decision_note   TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id)   ON DELETE CASCADE,
    FOREIGN KEY (session_id)    REFERENCES training_sessions(session_id) ON DELETE SET NULL
);

-- ── Portfolio ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS portfolio_evidence (
    evidence_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    title          TEXT    NOT NULL,
    evidence_type  TEXT    NOT NULL,
    description    TEXT,
    -- Relative to paths.APPRENTICESHIPS_EVIDENCE_DIR; NULL for
    -- narrative-only evidence such as a reflective account.
    file_name      TEXT,
    status         TEXT    NOT NULL DEFAULT 'Draft',
    submitted_at   TEXT,
    assessor_id    INTEGER,
    assessed_at    TEXT,
    feedback       TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    FOREIGN KEY (assessor_id)   REFERENCES staff(staff_id)            ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS evidence_ksb_map (
    map_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id   INTEGER NOT NULL,
    ksb_id        INTEGER NOT NULL,
    -- The assessor's judgement of how far this evidence takes the KSB.
    coverage      TEXT    NOT NULL DEFAULT 'Developing',
    assessor_note TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (evidence_id) REFERENCES portfolio_evidence(evidence_id) ON DELETE CASCADE,
    FOREIGN KEY (ksb_id)      REFERENCES programme_ksbs(ksb_id)          ON DELETE CASCADE,
    UNIQUE (evidence_id, ksb_id)
);

CREATE TABLE IF NOT EXISTS portfolio_verifications (
    verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id     INTEGER NOT NULL,
    verifier_id     INTEGER,
    outcome         TEXT    NOT NULL,     -- Agreed / Not agreed
    comments        TEXT,
    verified_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (evidence_id) REFERENCES portfolio_evidence(evidence_id) ON DELETE CASCADE,
    FOREIGN KEY (verifier_id) REFERENCES staff(staff_id)                 ON DELETE SET NULL
);

-- ── Progress reviews ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS reviews (
    review_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id   INTEGER NOT NULL,
    scheduled_date  TEXT    NOT NULL,
    held_date       TEXT,
    status          TEXT    NOT NULL DEFAULT 'Scheduled',
    conducted_by    INTEGER,
    progress_rating TEXT,                 -- config.RAG_RATINGS
    otj_on_track    INTEGER,
    summary         TEXT,
    apprentice_comments TEXT,
    employer_comments   TEXT,
    next_review_date    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    FOREIGN KEY (conducted_by)  REFERENCES staff(staff_id)            ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS review_targets (
    target_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id    INTEGER NOT NULL,
    description  TEXT    NOT NULL,
    due_date     TEXT,
    ksb_codes    TEXT,
    status       TEXT    NOT NULL DEFAULT 'Open',
    outcome_note TEXT,
    -- Action-plan fields. owner is config.ACTION_OWNERS, priority
    -- config.ACTION_PRIORITIES; completed_at is stamped when the action
    -- is settled Met or Not Met and cleared if it is reopened.
    owner        TEXT    NOT NULL DEFAULT 'Apprentice',
    priority     TEXT    NOT NULL DEFAULT 'Normal',
    completed_at TEXT,
    -- Set on the copy made when an outstanding action is carried onto a
    -- later review, pointing back at the one it replaced.
    carried_from INTEGER,
    carry_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (review_id)    REFERENCES reviews(review_id)        ON DELETE CASCADE,
    FOREIGN KEY (carried_from) REFERENCES review_targets(target_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS review_signatures (
    signature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id    INTEGER NOT NULL,
    signatory    TEXT    NOT NULL,        -- config.REVIEW_SIGNATORIES
    signed_by    TEXT    NOT NULL,
    signed_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (review_id) REFERENCES reviews(review_id) ON DELETE CASCADE,
    UNIQUE (review_id, signatory)
);

CREATE TABLE IF NOT EXISTS employer_feedback (
    feedback_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id   INTEGER NOT NULL,
    apprentice_id INTEGER,
    review_id     INTEGER,
    satisfaction  TEXT    NOT NULL,       -- config.SATISFACTION_SCALE
    comments      TEXT,
    submitted_by  TEXT,
    submitted_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employer_id)   REFERENCES employers(employer_id)     ON DELETE CASCADE,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE SET NULL,
    FOREIGN KEY (review_id)     REFERENCES reviews(review_id)         ON DELETE SET NULL
);

-- ── Functional skills ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS functional_skills (
    fs_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    subject        TEXT    NOT NULL,      -- English / Maths
    level          TEXT,
    status         TEXT    NOT NULL DEFAULT 'Not started',
    achieved_date  TEXT,
    exemption_reason TEXT,
    notes          TEXT,
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    UNIQUE (apprentice_id, subject)
);

-- ── Gateway ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gateway_records (
    gateway_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL UNIQUE,
    status         TEXT    NOT NULL DEFAULT 'Not Ready',
    requested_at   TEXT,
    requested_by   TEXT,
    decided_at     TEXT,
    decided_by     TEXT,
    decision_notes TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gateway_checks (
    check_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    gateway_id      INTEGER NOT NULL,
    requirement_key TEXT    NOT NULL,     -- config.GATEWAY_REQUIREMENTS
    met             INTEGER NOT NULL DEFAULT 0,
    -- Set when the service derived this from data rather than a human
    -- ticking it; an automatic check is recomputed on every read.
    automatic       INTEGER NOT NULL DEFAULT 0,
    evidence_note   TEXT,
    checked_by      TEXT,
    checked_at      TEXT,
    FOREIGN KEY (gateway_id) REFERENCES gateway_records(gateway_id) ON DELETE CASCADE,
    UNIQUE (gateway_id, requirement_key)
);

-- ── End-Point Assessment ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS epaos (
    epao_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    contact_name  TEXT,
    contact_email TEXT,
    phone         TEXT,
    -- Programme references this EPAO is approved to assess.
    standards     TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS epa_bookings (
    booking_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    epao_id        INTEGER,
    method         TEXT    NOT NULL,      -- config.EPA_METHODS
    scheduled_date TEXT,
    scheduled_time TEXT,
    location       TEXT,
    assessor_name  TEXT,
    -- Login handle of the EPA assessor, so their dashboard can filter
    -- to their own bookings.
    assessor_username TEXT,
    status         TEXT    NOT NULL DEFAULT 'Requested',
    -- Set on a resit booking so the result chain can be followed back.
    resit_of       INTEGER,
    notes          TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    FOREIGN KEY (epao_id)       REFERENCES epaos(epao_id)             ON DELETE SET NULL,
    FOREIGN KEY (resit_of)      REFERENCES epa_results(result_id)     ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS epa_results (
    result_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id     INTEGER NOT NULL UNIQUE,
    apprentice_id  INTEGER NOT NULL,
    method         TEXT    NOT NULL,
    grade          TEXT    NOT NULL,      -- config.EPA_GRADES
    assessed_date  TEXT    NOT NULL,
    assessor_name  TEXT,
    feedback       TEXT,
    -- Attempt number for this method: 1 is the first sitting.
    attempt        INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id)    REFERENCES epa_bookings(booking_id)   ON DELETE CASCADE,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS epa_resits (
    resit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    result_id      INTEGER NOT NULL,
    resit_type     TEXT    NOT NULL,      -- Resit / Retake
    reason         TEXT,
    -- Retakes require further training before the re-sitting.
    training_plan  TEXT,
    requested_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    requested_by   TEXT,
    status         TEXT    NOT NULL DEFAULT 'Requested',
    booking_id     INTEGER,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    FOREIGN KEY (result_id)     REFERENCES epa_results(result_id)     ON DELETE CASCADE,
    FOREIGN KEY (booking_id)    REFERENCES epa_bookings(booking_id)   ON DELETE SET NULL
);

-- ── Funding ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS funding_records (
    funding_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id           INTEGER NOT NULL UNIQUE,
    funding_model           TEXT    NOT NULL,
    band                    INTEGER NOT NULL,
    -- What provider and employer actually agreed; may be below the band
    -- maximum, never above it (the excess would be unfundable).
    negotiated_price        REAL    NOT NULL,
    employer_contribution   REAL    NOT NULL DEFAULT 0,
    government_contribution REAL    NOT NULL DEFAULT 0,
    -- Incentive or additional-needs payments outside the main price.
    additional_payments     REAL    NOT NULL DEFAULT 0,
    notes                   TEXT,
    created_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS funding_payments (
    payment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    due_date       TEXT    NOT NULL,
    amount         REAL    NOT NULL,
    -- 'Monthly' instalment or the withheld 'Completion' balance.
    payment_type   TEXT    NOT NULL DEFAULT 'Monthly',
    status         TEXT    NOT NULL DEFAULT 'Scheduled',
    claimed_at     TEXT,
    paid_at        TEXT,
    notes          TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

-- ── Compliance ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS compliance_documents (
    document_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    doc_key        TEXT    NOT NULL,      -- config.COMPLIANCE_DOCUMENTS
    status         TEXT    NOT NULL DEFAULT 'Missing',
    issued_date    TEXT,
    signed_date    TEXT,
    expiry_date    TEXT,
    file_name      TEXT,
    notes          TEXT,
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    UNIQUE (apprentice_id, doc_key)
);

CREATE TABLE IF NOT EXISTS eligibility_checks (
    check_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    check_key      TEXT    NOT NULL,      -- config.ELIGIBILITY_CHECKS
    passed         INTEGER NOT NULL DEFAULT 0,
    evidence       TEXT,
    checked_by     TEXT,
    checked_at     TEXT,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    UNIQUE (apprentice_id, check_key)
);

-- ── Correspondence ─────────────────────────────────────────────────

-- Every message the provider sends or receives. An apprenticeship has
-- more parties round it than a school place, so a message may be
-- addressed to the apprentice, the employer, or neither — hence both
-- links are optional and the address is what actually identifies the
-- recipient.
--
-- ON DELETE SET NULL rather than CASCADE: removing an apprentice must
-- not erase the record of what the provider wrote to them. That
-- correspondence is funding-audit evidence.
CREATE TABLE IF NOT EXISTS email_messages (
    message_id    TEXT    PRIMARY KEY,
    direction     TEXT    NOT NULL DEFAULT 'Outgoing',
    channel       TEXT    NOT NULL DEFAULT 'Email',
    category      TEXT    NOT NULL DEFAULT 'General',
    priority      TEXT    NOT NULL DEFAULT 'Normal',
    status        TEXT    NOT NULL DEFAULT 'Draft',
    subject       TEXT    NOT NULL,
    body          TEXT,
    from_name     TEXT,
    from_address  TEXT,
    to_name       TEXT,
    to_address    TEXT,
    apprentice_id INTEGER,
    employer_id   INTEGER,
    -- Who sent it, as a username: staff come and go and the audit trail
    -- must survive a staff record being removed.
    sent_by       TEXT,
    tags          TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    sent_at       TEXT,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE SET NULL,
    FOREIGN KEY (employer_id)   REFERENCES employers(employer_id)     ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL DEFAULT (datetime('now')),
    actor       TEXT,
    actor_role  TEXT,
    action      TEXT    NOT NULL,
    entity      TEXT    NOT NULL,
    entity_id   TEXT,
    detail      TEXT,
    changes     TEXT    -- JSON [{field, before, after}]; NULL for an event, not an edit
);

-- ── Preferences ────────────────────────────────────────────────────
-- Interface preferences, keyed on the shared-auth username rather than
-- on any record in this system: an administrator has no apprentice,
-- employer or staff row to hang them off, and the same login carries
-- them between the CLI and the GUI.
CREATE TABLE IF NOT EXISTS user_preferences (
    username    TEXT    NOT NULL,
    pref_key    TEXT    NOT NULL,
    pref_value  TEXT,
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (username, pref_key)
);

-- ── Indexes ────────────────────────────────────────────────────────
-- Cover the filters every list screen offers, plus the foreign keys
-- the dashboards aggregate over.

CREATE INDEX IF NOT EXISTS ix_appr_status     ON apprentices(status);
CREATE INDEX IF NOT EXISTS ix_appr_employer   ON apprentices(employer_id);
CREATE INDEX IF NOT EXISTS ix_appr_programme  ON apprentices(programme_id);
CREATE INDEX IF NOT EXISTS ix_appr_tutor      ON apprentices(tutor_id);
CREATE INDEX IF NOT EXISTS ix_email_status    ON email_messages(status);
CREATE INDEX IF NOT EXISTS ix_email_direction ON email_messages(direction);
CREATE INDEX IF NOT EXISTS ix_email_appr      ON email_messages(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_email_employer  ON email_messages(employer_id);
CREATE INDEX IF NOT EXISTS ix_appr_username   ON apprentices(username);
-- ix_appr_journey is created in _migrate(), not here: this script runs
-- against existing databases too, where CREATE TABLE is a no-op and the
-- journey_id column does not exist yet.
CREATE INDEX IF NOT EXISTS ix_staff_username  ON staff(username);
CREATE INDEX IF NOT EXISTS ix_mgr_username    ON employer_managers(username);
CREATE INDEX IF NOT EXISTS ix_mgr_employer    ON employer_managers(employer_id);
CREATE INDEX IF NOT EXISTS ix_wp_employer     ON employer_workplaces(employer_id);
CREATE INDEX IF NOT EXISTS ix_ksb_programme   ON programme_ksbs(programme_id);
CREATE INDEX IF NOT EXISTS ix_duty_programme  ON occupational_duties(programme_id);
CREATE INDEX IF NOT EXISTS ix_otj_appr        ON otj_entries(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_otj_status      ON otj_entries(status);
CREATE INDEX IF NOT EXISTS ix_otj_date        ON otj_entries(activity_date);
CREATE INDEX IF NOT EXISTS ix_evi_appr        ON portfolio_evidence(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_evi_status      ON portfolio_evidence(status);
CREATE INDEX IF NOT EXISTS ix_map_evidence    ON evidence_ksb_map(evidence_id);
CREATE INDEX IF NOT EXISTS ix_map_ksb         ON evidence_ksb_map(ksb_id);
CREATE INDEX IF NOT EXISTS ix_rev_appr        ON reviews(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_rev_status      ON reviews(status);
CREATE INDEX IF NOT EXISTS ix_rev_sched       ON reviews(scheduled_date);
CREATE INDEX IF NOT EXISTS ix_tgt_review      ON review_targets(review_id);
CREATE INDEX IF NOT EXISTS ix_sig_review      ON review_signatures(review_id);
CREATE INDEX IF NOT EXISTS ix_sess_date       ON training_sessions(session_date);
CREATE INDEX IF NOT EXISTS ix_sess_programme  ON training_sessions(programme_id);
CREATE INDEX IF NOT EXISTS ix_att_session     ON session_attendance(session_id);
CREATE INDEX IF NOT EXISTS ix_att_appr        ON session_attendance(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_tpi_appr        ON training_plan_items(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_gw_status       ON gateway_records(status);
CREATE INDEX IF NOT EXISTS ix_gwc_gateway     ON gateway_checks(gateway_id);
CREATE INDEX IF NOT EXISTS ix_book_appr       ON epa_bookings(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_book_status     ON epa_bookings(status);
CREATE INDEX IF NOT EXISTS ix_book_assessor   ON epa_bookings(assessor_username);
CREATE INDEX IF NOT EXISTS ix_res_appr        ON epa_results(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_resit_appr      ON epa_resits(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_pay_appr        ON funding_payments(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_pay_status      ON funding_payments(status);
CREATE INDEX IF NOT EXISTS ix_doc_appr        ON compliance_documents(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_elig_appr       ON eligibility_checks(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_fs_appr         ON functional_skills(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_hist_appr       ON apprentice_status_history(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_audit_entity    ON audit_log(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_ts        ON audit_log(ts);

-- ══ Progress: action plans, assignments, skills matrix ══════════════

-- The history of an action: progress notes, and every status move made
-- by its owner, in one place. Notes stay with the action they were made
-- on; a carried-forward copy reaches them through carried_from.
CREATE TABLE IF NOT EXISTS action_notes (
    note_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id    INTEGER NOT NULL,
    author       TEXT    NOT NULL,
    author_role  TEXT    NOT NULL,
    body         TEXT    NOT NULL,
    -- Both set when the note records a status move.
    from_status  TEXT,
    to_status    TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (target_id) REFERENCES review_targets(target_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_action_notes_target ON action_notes(target_id);
CREATE INDEX IF NOT EXISTS ix_tgt_due             ON review_targets(due_date);
-- ix_tgt_owner is created in _migrate(): on an existing database the
-- owner column does not exist until the migration has added it.

-- Work set by the provider. The row holds the current attempt; each
-- attempt's own submission, grade and feedback are in
-- assignment_submissions, so a referral does not overwrite history.
-- set_by / marked_by are usernames: an administrator has no staff row,
-- and the moderator-is-not-the-marker check compares logins.
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id   INTEGER NOT NULL,
    title           TEXT    NOT NULL,
    brief           TEXT,
    assignment_type TEXT    NOT NULL,       -- config.ASSIGNMENT_TYPES
    ksb_codes       TEXT,
    set_by          TEXT,
    set_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    due_date        TEXT,
    status          TEXT    NOT NULL DEFAULT 'Set',   -- config.ASSIGNMENT_STATUSES
    attempt         INTEGER NOT NULL DEFAULT 1,
    max_attempts    INTEGER NOT NULL DEFAULT 3,
    grade           TEXT,                   -- config.ASSIGNMENT_GRADES
    feedback        TEXT,
    marked_by       TEXT,
    marked_at       TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assignment_submissions (
    submission_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id  INTEGER NOT NULL,
    attempt        INTEGER NOT NULL,
    body           TEXT,
    -- Optional pointer at portfolio evidence that is the submission.
    evidence_id    INTEGER,
    submitted_by   TEXT    NOT NULL,
    submitted_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    -- Late work is accepted but flagged; the flag is fixed at submission.
    is_late        INTEGER NOT NULL DEFAULT 0,
    grade          TEXT,
    feedback       TEXT,
    marked_by      TEXT,
    marked_at      TEXT,
    FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id)      ON DELETE CASCADE,
    FOREIGN KEY (evidence_id)   REFERENCES portfolio_evidence(evidence_id) ON DELETE SET NULL,
    UNIQUE (assignment_id, attempt)
);

-- One moderation per attempt: a second opinion on the marker's grade.
CREATE TABLE IF NOT EXISTS assignment_moderations (
    moderation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id  INTEGER NOT NULL,
    attempt        INTEGER NOT NULL,
    moderator      TEXT    NOT NULL,
    outcome        TEXT    NOT NULL,        -- config.ASSIGNMENT_MODERATION_OUTCOMES
    original_grade TEXT,
    adjusted_grade TEXT,
    notes          TEXT,
    moderated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id) ON DELETE CASCADE,
    UNIQUE (assignment_id, attempt)
);

CREATE INDEX IF NOT EXISTS ix_asg_appr      ON assignments(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_asg_status    ON assignments(status);
CREATE INDEX IF NOT EXISTS ix_asg_due       ON assignments(due_date);
CREATE INDEX IF NOT EXISTS ix_asub_asg      ON assignment_submissions(assignment_id);
CREATE INDEX IF NOT EXISTS ix_amod_asg      ON assignment_moderations(assignment_id);

-- ══ Learner support: functional skills, qualifications, adjustments, welfare ══

-- Initial and diagnostic assessments: where an apprentice started in
-- English, Maths and Digital, and what a later diagnostic found. The
-- functional_skills row above is the current position; these are the
-- evidence behind it and are never overwritten.
CREATE TABLE IF NOT EXISTS skills_assessments (
    assessment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    subject        TEXT    NOT NULL,      -- config.SKILLS_ASSESSMENT_SUBJECTS
    kind           TEXT    NOT NULL,      -- config.SKILLS_ASSESSMENT_KINDS
    assessed_on    TEXT    NOT NULL,
    level          TEXT,                  -- config.SKILLS_ASSESSMENT_LEVELS
    score          REAL,                  -- percentage, 0-100
    notes          TEXT,
    assessed_by    TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_skass_appr ON skills_assessments(apprentice_id);

-- Qualifications held before the programme, taken during it, and achieved.
CREATE TABLE IF NOT EXISTS qualifications (
    qualification_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id           INTEGER NOT NULL,
    title                   TEXT    NOT NULL,
    level                   TEXT,                 -- config.QUALIFICATION_LEVELS
    awarding_body           TEXT,
    reference               TEXT,                 -- QAN or awarding-body reference
    status                  TEXT    NOT NULL DEFAULT 'In progress',
    grade                   TEXT,
    start_date              TEXT,
    achieved_date           TEXT,
    certificate_ref         TEXT,
    -- Counted as recognised prior learning when the programme was planned.
    relevant_prior_learning INTEGER NOT NULL DEFAULT 0,
    notes                   TEXT,
    recorded_by             TEXT,
    created_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_qual_appr ON qualifications(apprentice_id);

-- Reasonable adjustments and support. share_with_employer is the
-- apprentice's consent: an employer sees an arrangement only when it is set.
CREATE TABLE IF NOT EXISTS support_arrangements (
    arrangement_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id        INTEGER NOT NULL,
    need_category        TEXT    NOT NULL,        -- config.SUPPORT_NEED_CATEGORIES
    adjustment           TEXT    NOT NULL,
    arrangements         TEXT,
    responsible_staff_id INTEGER,
    review_date          TEXT,
    status               TEXT    NOT NULL DEFAULT 'Active',   -- config.SUPPORT_STATUSES
    share_with_employer  INTEGER NOT NULL DEFAULT 0,
    created_by           TEXT,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id)        REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    FOREIGN KEY (responsible_staff_id) REFERENCES staff(staff_id)            ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_support_appr   ON support_arrangements(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_support_review ON support_arrangements(review_date);

-- The history of an arrangement: reviews, status changes, notes.
CREATE TABLE IF NOT EXISTS support_notes (
    note_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    arrangement_id  INTEGER NOT NULL,
    author          TEXT    NOT NULL,
    author_role     TEXT    NOT NULL,
    body            TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (arrangement_id) REFERENCES support_arrangements(arrangement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_support_notes_arr ON support_notes(arrangement_id);

-- Welfare concerns. Restricted: provider staff only, and a tutor only for
-- their own caseload. escalated_to is free text because the escalation
-- often leaves the organisation (a DSL, the local authority, Prevent).
CREATE TABLE IF NOT EXISTS welfare_concerns (
    concern_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id  INTEGER NOT NULL,
    category       TEXT    NOT NULL,      -- config.WELFARE_CATEGORIES
    severity       TEXT    NOT NULL,      -- config.WELFARE_SEVERITIES
    description    TEXT    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'Open',   -- config.WELFARE_STATUSES
    raised_by      TEXT    NOT NULL,
    raised_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    assigned_to    INTEGER,
    escalated_to   TEXT,
    escalated_at   TEXT,
    closed_at      TEXT,
    outcome        TEXT,
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to)   REFERENCES staff(staff_id)            ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_welfare_appr   ON welfare_concerns(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_welfare_status ON welfare_concerns(status);

CREATE TABLE IF NOT EXISTS welfare_notes (
    note_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id   INTEGER NOT NULL,
    author       TEXT    NOT NULL,
    author_role  TEXT    NOT NULL,
    note         TEXT    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (concern_id) REFERENCES welfare_concerns(concern_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_welfare_notes_concern ON welfare_notes(concern_id);

-- ══ Records: documents, signatures, audit ══════════════════════════

-- Uploaded files. Exactly one owner: an apprentice, or (for the
-- employer's own paperwork) an employer. An apprentice's document does
-- not copy the employer id — it is scoped through the apprentice, so a
-- change of employer moves visibility with them.
--
-- Versions: every upload is a row. Version 1 is its own series; a new
-- version shares series_id, bumps version and names the row it
-- supersedes, so the history is never overwritten. The file itself
-- sits in paths.APPRENTICESHIPS_DOCUMENTS_DIR under stored_name, which
-- is generated — never derived from original_filename.
CREATE TABLE IF NOT EXISTS documents (
    document_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    apprentice_id     INTEGER,
    employer_id       INTEGER,
    category          TEXT    NOT NULL,   -- config.DOCUMENT_CATEGORIES
    title             TEXT    NOT NULL,
    original_filename TEXT    NOT NULL,
    stored_name       TEXT    NOT NULL UNIQUE,
    size_bytes        INTEGER NOT NULL,
    sha256            TEXT    NOT NULL,
    version           INTEGER NOT NULL DEFAULT 1,
    series_id         INTEGER,
    supersedes        INTEGER,
    -- The compliance_documents checklist item this file evidences, if any.
    checklist_key     TEXT,
    uploaded_by       TEXT    NOT NULL,
    uploaded_role     TEXT    NOT NULL,
    uploaded_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    expiry_date       TEXT,
    approval_status   TEXT    NOT NULL DEFAULT 'Pending',
    approved_by       TEXT,
    approved_at       TEXT,
    rejection_reason  TEXT,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE,
    FOREIGN KEY (employer_id)   REFERENCES employers(employer_id)     ON DELETE CASCADE,
    FOREIGN KEY (supersedes)    REFERENCES documents(document_id)     ON DELETE SET NULL,
    UNIQUE (series_id, version)
);

-- A signature is a claim about content: content_hash is what the
-- signatory saw. It stays valid only while the thing still hashes to
-- that value, so an edit after signing invalidates it without anybody
-- having to remember to. entity_id is polymorphic (an apprentice id for
-- a learning plan, a document id for a document), hence no FK on it;
-- apprentice_id is carried for scoping and cascades with the record.
-- review_signatures is separate and older; progress reviews keep it.
CREATE TABLE IF NOT EXISTS signatures (
    signature_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type    TEXT    NOT NULL,      -- learning_plan / document
    entity_id      INTEGER NOT NULL,
    apprentice_id  INTEGER,
    signatory_role TEXT    NOT NULL,      -- config.SIGNATORY_ROLES
    signed_by      TEXT    NOT NULL,
    signer_role    TEXT,                  -- the login's role when signing
    signed_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    statement      TEXT    NOT NULL,
    content_hash   TEXT    NOT NULL,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_docs_appr       ON documents(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_docs_employer   ON documents(employer_id);
CREATE INDEX IF NOT EXISTS ix_docs_series     ON documents(series_id);
CREATE INDEX IF NOT EXISTS ix_docs_supersedes ON documents(supersedes);
CREATE INDEX IF NOT EXISTS ix_docs_expiry     ON documents(expiry_date);
CREATE INDEX IF NOT EXISTS ix_sigs_entity     ON signatures(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_sigs_appr       ON signatures(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_audit_actor     ON audit_log(actor);

-- ══ Employers and programmes: contacts, commitments, curriculum ═════

-- Every conversation with an employer: who, about which apprentice, and
-- what has to happen next. The follow-up date is what the task list reads.
CREATE TABLE IF NOT EXISTS employer_contact_log (
    log_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id        INTEGER NOT NULL,
    contact_id         INTEGER,                -- employer_managers.manager_id
    apprentice_id      INTEGER,
    contacted_on       TEXT    NOT NULL,
    channel            TEXT    NOT NULL,       -- config.CONTACT_CHANNELS
    summary            TEXT    NOT NULL,
    follow_up_date     TEXT,
    follow_up_done_at  TEXT,
    follow_up_done_by  TEXT,
    logged_by          TEXT    NOT NULL,
    logged_by_role     TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employer_id)   REFERENCES employers(employer_id)        ON DELETE CASCADE,
    FOREIGN KEY (contact_id)    REFERENCES employer_managers(manager_id) ON DELETE SET NULL,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id)    ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_ecl_employer  ON employer_contact_log(employer_id);
CREATE INDEX IF NOT EXISTS ix_ecl_appr      ON employer_contact_log(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_ecl_follow_up ON employer_contact_log(follow_up_date);

-- What the employer has undertaken to do, and how hard it is being chased.
CREATE TABLE IF NOT EXISTS employer_commitments (
    commitment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id        INTEGER NOT NULL,
    apprentice_id      INTEGER,
    commitment         TEXT    NOT NULL,
    category           TEXT    NOT NULL DEFAULT 'Other',   -- config.COMMITMENT_CATEGORIES
    due_date           TEXT,
    status             TEXT    NOT NULL DEFAULT 'Open',    -- config.COMMITMENT_STATUSES
    escalation_level   INTEGER NOT NULL DEFAULT 0 CHECK (escalation_level BETWEEN 0 AND 3),
    escalated_at       TEXT,
    escalated_by       TEXT,
    escalation_reason  TEXT,
    closed_at          TEXT,
    notes              TEXT,
    created_by         TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employer_id)   REFERENCES employers(employer_id)     ON DELETE CASCADE,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_ecm_employer ON employer_commitments(employer_id);
CREATE INDEX IF NOT EXISTS ix_ecm_appr     ON employer_commitments(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_ecm_due      ON employer_commitments(due_date);

-- A standard's curriculum: the modules delivered, stage by stage.
CREATE TABLE IF NOT EXISTS programme_modules (
    module_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id   INTEGER NOT NULL,
    stage          TEXT    NOT NULL DEFAULT 'Year 1',
    position       INTEGER NOT NULL DEFAULT 1,
    title          TEXT    NOT NULL,
    description    TEXT,
    ksb_codes      TEXT,
    planned_hours  REAL    NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE,
    UNIQUE (programme_id, title)
);

CREATE INDEX IF NOT EXISTS ix_pmod_programme ON programme_modules(programme_id);
CREATE INDEX IF NOT EXISTS ix_prog_reference ON programmes(reference);

-- Which modules have been applied to which apprentice's learning plan, so
-- applying the curriculum again adds only what is new. A deleted
-- objective keeps its row here: it was removed on purpose.
CREATE TABLE IF NOT EXISTS curriculum_applications (
    apprentice_id  INTEGER NOT NULL,
    module_id      INTEGER NOT NULL,
    objective_id   INTEGER,
    item_id        INTEGER,
    applied_by     TEXT,
    applied_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (apprentice_id, module_id),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id)    ON DELETE CASCADE,
    FOREIGN KEY (module_id)     REFERENCES programme_modules(module_id)  ON DELETE CASCADE,
    FOREIGN KEY (objective_id)  REFERENCES ilp_objectives(objective_id)  ON DELETE SET NULL,
    FOREIGN KEY (item_id)       REFERENCES training_plan_items(item_id)  ON DELETE SET NULL
);

-- Where an applicant is inside admissions. No row means Application.
CREATE TABLE IF NOT EXISTS admission_stages (
    apprentice_id     INTEGER PRIMARY KEY,
    stage             TEXT    NOT NULL DEFAULT 'Application',  -- config.ADMISSION_STAGES
    offer_date        TEXT,
    offer_conditions  TEXT,
    enrolment_date    TEXT,
    updated_by        TEXT,
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

-- ══ Quality: complaints, appeals, surveys ══════════════════════════

-- Keyed on the complainant's username rather than a record: every role
-- may complain, and an admin or an EPAO has no row to hang it off. The
-- apprentice and employer links say who it is *about*, and SET NULL so
-- removing a record does not erase the complaint made about it.
-- The deadlines are stored rather than derived so "what is overdue" is
-- a plain indexed comparison.
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    reference        TEXT    UNIQUE,              -- CMP-0001, set on insert
    raised_by        TEXT    NOT NULL,
    raised_role      TEXT    NOT NULL,
    apprentice_id    INTEGER,
    employer_id      INTEGER,
    category         TEXT    NOT NULL,            -- config.COMPLAINT_CATEGORIES
    subject          TEXT    NOT NULL,
    description      TEXT    NOT NULL,
    received_at      TEXT    NOT NULL,            -- date
    status           TEXT    NOT NULL DEFAULT 'Received',
    handler          TEXT,                        -- username of the provider handler
    acknowledged_at  TEXT,
    ack_due_on       TEXT    NOT NULL,
    response_due_on  TEXT    NOT NULL,
    outcome          TEXT,
    closed_at        TEXT,
    escalated_to     TEXT,
    -- NULL until the complainant says; 1 satisfied, 0 not.
    satisfied        INTEGER,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE SET NULL,
    FOREIGN KEY (employer_id)   REFERENCES employers(employer_id)     ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_cmp_status     ON complaints(status);
CREATE INDEX IF NOT EXISTS ix_cmp_raised_by  ON complaints(raised_by);
CREATE INDEX IF NOT EXISTS ix_cmp_appr       ON complaints(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_cmp_resp_due   ON complaints(response_due_on);

-- The running record of a complaint. Internal notes stay with the
-- provider; only rows marked visible reach the complainant.
CREATE TABLE IF NOT EXISTS complaint_updates (
    update_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id            INTEGER NOT NULL,
    note                    TEXT    NOT NULL,
    author                  TEXT    NOT NULL,
    author_role             TEXT    NOT NULL,
    visible_to_complainant  INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_cmpu_complaint ON complaint_updates(complaint_id);

-- An apprentice's challenge to a decision about them. decision_ref_id
-- carries no foreign key because what it points at depends on the type
-- (an epa_results row for an EPA result, nothing for most others);
-- decision_ref is the human description that always makes sense.
CREATE TABLE IF NOT EXISTS appeals (
    appeal_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    reference        TEXT    UNIQUE,              -- APL-0001, set on insert
    apprentice_id    INTEGER NOT NULL,
    raised_by        TEXT    NOT NULL,
    appeal_type      TEXT    NOT NULL,            -- config.APPEAL_TYPES
    decision_ref_id  INTEGER,
    decision_ref     TEXT,
    decision_date    TEXT    NOT NULL,            -- when the appealed decision was made
    grounds          TEXT    NOT NULL,
    lodged_at        TEXT    NOT NULL,            -- date
    deadline         TEXT    NOT NULL,            -- decide by
    status           TEXT    NOT NULL DEFAULT 'Lodged',
    decided_by       TEXT,
    decided_at       TEXT,
    decision         TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_apl_status   ON appeals(status);
CREATE INDEX IF NOT EXISTS ix_apl_appr     ON appeals(apprentice_id);
CREATE INDEX IF NOT EXISTS ix_apl_type     ON appeals(appeal_type);
CREATE INDEX IF NOT EXISTS ix_apl_deadline ON appeals(deadline);

CREATE TABLE IF NOT EXISTS surveys (
    survey_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    audience    TEXT    NOT NULL,                 -- config.SURVEY_AUDIENCES
    kind        TEXT    NOT NULL,                 -- config.SURVEY_KINDS
    status      TEXT    NOT NULL DEFAULT 'Draft', -- config.SURVEY_STATUSES
    opens_on    TEXT,
    closes_on   TEXT,
    created_by  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_srv_status ON surveys(status);

-- Who responded is stored only to enforce one response each and to
-- count the response rate; the results queries never select it.
CREATE TABLE IF NOT EXISTS survey_responses (
    response_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id        INTEGER NOT NULL,
    respondent       TEXT    NOT NULL,
    respondent_role  TEXT    NOT NULL,
    apprentice_id    INTEGER,
    employer_id      INTEGER,
    answers          TEXT    NOT NULL,            -- JSON: question -> score 1..5
    comment          TEXT,
    submitted_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (survey_id)     REFERENCES surveys(survey_id)         ON DELETE CASCADE,
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE SET NULL,
    FOREIGN KEY (employer_id)   REFERENCES employers(employer_id)     ON DELETE SET NULL,
    UNIQUE (survey_id, respondent)
);

CREATE INDEX IF NOT EXISTS ix_srvr_survey ON survey_responses(survey_id);

-- ══ Workspace: tasks, calendar ═════════════════════════════════════
"""


# ═════════════════════════════════════════════════════════════════════
# Connection handling
# ═════════════════════════════════════════════════════════════════════

_DB_READY: bool = False
_READY_LOCK = threading.Lock()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """A configured connection, committed on success and always closed.

    Foreign keys are enforced per-connection in SQLite — the PRAGMA is
    not persisted in the file — so it has to be set here, every time.
    """
    paths.ensure_apprenticeships_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_APPRENTICE_DETAIL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("middle_name", "TEXT"),
    ("preferred_name", "TEXT"),
    ("gender", "TEXT"),
    ("address_line1", "TEXT"),
    ("address_line2", "TEXT"),
    ("town", "TEXT"),
    ("postcode", "TEXT"),
    ("emergency_contact_name", "TEXT"),
    ("emergency_contact_relationship", "TEXT"),
    ("emergency_contact_phone", "TEXT"),
    ("has_lldd", "INTEGER NOT NULL DEFAULT 0"),
    ("has_ehcp", "INTEGER NOT NULL DEFAULT 0"),
    ("medical_notes", "TEXT"),
)


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring an existing database up to the current schema.

    ``executescript(SCHEMA)`` only ever *creates* — ``CREATE TABLE IF NOT
    EXISTS`` is a no-op once the table is there, so a column added to the
    definition above never reaches a database that already exists. Adding
    it here is what closes that gap. Every step must be idempotent: this
    runs on every process start, not once.
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(apprentices)").fetchall()}
    if not cols:
        return  # fresh database; SCHEMA has just built it correctly
    if "journey_id" not in cols:
        conn.execute("ALTER TABLE apprentices ADD COLUMN journey_id TEXT")
        logger.info("Added apprentices.journey_id (cross-system identity link)")
    # Personal, address, emergency-contact and needs details (2026-11-06).
    for column, ddl in _APPRENTICE_DETAIL_COLUMNS:
        if column not in cols:
            conn.execute(f"ALTER TABLE apprentices ADD COLUMN {column} {ddl}")
            logger.info("Added apprentices.%s", column)
    # Deferred from SCHEMA so it is only attempted once the column exists.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_appr_journey ON apprentices(journey_id) "
        "WHERE journey_id IS NOT NULL")
    link_cols = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(degree_apprenticeship_links)"
        ).fetchall()
    }
    if link_cols and "last_academic_sync_at" not in link_cols:
        conn.execute(
            "ALTER TABLE degree_apprenticeship_links "
            "ADD COLUMN last_academic_sync_at TEXT"
        )
        logger.info(
            "Added degree_apprenticeship_links.last_academic_sync_at"
        )
    projection_cols = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(degree_academic_progress_projection)"
        ).fetchall()
    }
    if projection_cols and "university_gateway_confirmed" not in projection_cols:
        conn.execute(
            "ALTER TABLE degree_academic_progress_projection "
            "ADD COLUMN university_gateway_confirmed INTEGER NOT NULL DEFAULT 0"
        )
    attendance_cols = {
        r[1] for r in conn.execute("PRAGMA table_info(session_attendance)").fetchall()
    }
    if attendance_cols and "absence_reason" not in attendance_cols:
        conn.execute("ALTER TABLE session_attendance ADD COLUMN absence_reason TEXT")
        logger.info("Added session_attendance.absence_reason")
    plan_cols = {
        r[1] for r in conn.execute("PRAGMA table_info(training_plan_items)").fetchall()
    }
    if plan_cols and "objective_id" not in plan_cols:
        conn.execute(
            "ALTER TABLE training_plan_items ADD COLUMN objective_id INTEGER "
            "REFERENCES ilp_objectives(objective_id) ON DELETE SET NULL"
        )
        logger.info("Added training_plan_items.objective_id (learning-plan link)")

    # ── Progress: action plans, assignments ──
    target_cols = {
        r[1] for r in conn.execute("PRAGMA table_info(review_targets)").fetchall()
    }
    for column, ddl in (
        ("owner", "owner TEXT NOT NULL DEFAULT 'Apprentice'"),
        ("priority", "priority TEXT NOT NULL DEFAULT 'Normal'"),
        ("completed_at", "completed_at TEXT"),
        ("carried_from", "carried_from INTEGER "
                         "REFERENCES review_targets(target_id) ON DELETE SET NULL"),
        ("carry_count", "carry_count INTEGER NOT NULL DEFAULT 0"),
    ):
        if target_cols and column not in target_cols:
            conn.execute(f"ALTER TABLE review_targets ADD COLUMN {ddl}")
            logger.info("Added review_targets.%s (action plans)", column)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_tgt_owner ON review_targets(owner)")

    # ── Learner support ──

    # ── Records: documents, signatures, audit ──
    # The documents and signatures tables are new, so SCHEMA creates them
    # on an existing database as well; only the audit_log column needs
    # adding in place.
    audit_cols = {r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()}
    if audit_cols and "changes" not in audit_cols:
        conn.execute("ALTER TABLE audit_log ADD COLUMN changes TEXT")
        logger.info("Added audit_log.changes (before -> after values)")

    # ── Employers and programmes ──
    manager_cols = {
        r[1] for r in conn.execute("PRAGMA table_info(employer_managers)").fetchall()
    }
    if manager_cols and "contact_role" not in manager_cols:
        conn.execute("ALTER TABLE employer_managers ADD COLUMN contact_role TEXT")
        logger.info("Added employer_managers.contact_role")
    programme_cols = {
        r[1] for r in conn.execute("PRAGMA table_info(programmes)").fetchall()
    }
    if programme_cols and "version" not in programme_cols:
        conn.execute(
            "ALTER TABLE programmes ADD COLUMN version TEXT NOT NULL DEFAULT '1.0'"
        )
        logger.info("Added programmes.version")
    if programme_cols and "supersedes_programme_id" not in programme_cols:
        conn.execute(
            "ALTER TABLE programmes ADD COLUMN supersedes_programme_id INTEGER "
            "REFERENCES programmes(programme_id) ON DELETE SET NULL"
        )
        logger.info("Added programmes.supersedes_programme_id")
    # reference was UNIQUE on its own, which stops two versions sharing it.
    # SQLite cannot drop that constraint in place, so the table is rebuilt.
    from education_system.systems.apprenticeships.infrastructure.persistence import (
        programme_versions_migration,
    )
    programme_versions_migration.allow_versions_to_share_a_reference(conn)

    # ── Quality ──

    # ── Workspace ──


def init_db() -> None:
    """Create the schema if it isn't there. Idempotent and thread-safe.

    Every public service function calls this first, so the first call in
    a process pays for the DDL and the rest short-circuit on a flag.
    """
    global _DB_READY
    if _DB_READY:
        return
    with _READY_LOCK:
        if _DB_READY:
            return
        with connect() as conn:
            conn.executescript(SCHEMA)
            _migrate(conn)
        logger.debug("Apprenticeships schema ready at %s", DB_PATH)
        _DB_READY = True


def reset_ready_flag() -> None:
    """Forget that the schema was created.

    Only for tests that repoint ``DB_PATH`` at a temporary file — without
    this the next ``init_db()`` would no-op and leave the new file empty.
    """
    global _DB_READY
    _DB_READY = False
