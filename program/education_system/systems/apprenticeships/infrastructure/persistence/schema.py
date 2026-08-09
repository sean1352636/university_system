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
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE
);

-- ── Programmes (apprenticeship standards) ──────────────────────────

CREATE TABLE IF NOT EXISTS programmes (
    programme_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    reference         TEXT    NOT NULL UNIQUE,  -- e.g. ST0119
    title             TEXT    NOT NULL,
    level             INTEGER NOT NULL,
    funding_band      INTEGER NOT NULL,         -- 1..15, see config.FUNDING_BANDS
    duration_months   INTEGER NOT NULL,
    -- Comma-separated config.EPA_METHODS the EPAO will use.
    epa_methods       TEXT,
    sector            TEXT,
    description       TEXT,
    status            TEXT    NOT NULL DEFAULT 'Draft',
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
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
    family_name       TEXT    NOT NULL,
    date_of_birth     TEXT,
    email             TEXT,
    phone             TEXT,
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
    status         TEXT    NOT NULL DEFAULT 'Planned',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (apprentice_id) REFERENCES apprentices(apprentice_id) ON DELETE CASCADE
);

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
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (review_id) REFERENCES reviews(review_id) ON DELETE CASCADE
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
    detail      TEXT
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
    # Deferred from SCHEMA so it is only attempted once the column exists.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_appr_journey ON apprentices(journey_id) "
        "WHERE journey_id IS NOT NULL")


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
