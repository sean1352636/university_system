"""Schema initialisation and seed data for the shared auth database."""

import hashlib
import logging
import os
import sqlite3

import bcrypt

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.password_manager import hash_password

logger = logging.getLogger(__name__)

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    UNIQUE NOT NULL,
    password_hash   TEXT    NOT NULL,
    display_name    TEXT,
    email           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login      TEXT,
    legacy_salt     TEXT,
    password_changed_at TEXT,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    line_manager_id INTEGER
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    token       TEXT    UNIQUE NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT    NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS mfa_secrets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER UNIQUE NOT NULL,
    totp_secret TEXT    NOT NULL,
    is_enabled  INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    code_hash   TEXT    NOT NULL,
    is_used     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_systems (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    system_key  TEXT    NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'student',
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, system_key)
);

CREATE TABLE IF NOT EXISTS password_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    password_hash   TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    token_hash  TEXT    NOT NULL,
    expires_at  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cross_system_notifications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_user_id      INTEGER NOT NULL,
    sender_system       TEXT    NOT NULL,
    recipient_user_id   INTEGER NOT NULL,
    recipient_system    TEXT    NOT NULL,
    title               TEXT    NOT NULL,
    message             TEXT,
    priority            TEXT    DEFAULT 'normal',
    is_read             INTEGER DEFAULT 0,
    created_at          TEXT    DEFAULT (datetime('now')),
    read_at             TEXT,
    FOREIGN KEY (sender_user_id)    REFERENCES users(id),
    FOREIGN KEY (recipient_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS consent_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    consent_type    TEXT    NOT NULL,
    granted         INTEGER NOT NULL DEFAULT 0,
    granted_at      TEXT,
    withdrawn_at    TEXT,
    ip_address      TEXT,
    source          TEXT    DEFAULT 'manual',
    version         TEXT    DEFAULT '1.0',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_consent_user ON consent_records(user_id);
CREATE INDEX IF NOT EXISTS idx_consent_type ON consent_records(consent_type);

CREATE TABLE IF NOT EXISTS security_questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    question    TEXT    NOT NULL,
    answer_hash TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_security_questions_user ON security_questions(user_id);

CREATE TABLE IF NOT EXISTS sq_verification_attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL,
    success     INTEGER NOT NULL DEFAULT 0,
    ip_address  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sq_attempts_user ON sq_verification_attempts(username, created_at);

CREATE TABLE IF NOT EXISTS security_audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT    NOT NULL,
    username    TEXT,
    user_id     INTEGER,
    detail      TEXT,
    ip_address  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_event ON security_audit_log(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_user ON security_audit_log(username, created_at);

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    token_hash  TEXT    NOT NULL,
    email       TEXT    NOT NULL,
    expires_at  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_email_verify_user ON email_verification_tokens(user_id);

CREATE TABLE IF NOT EXISTS rate_limits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT    NOT NULL,
    timestamp   REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_limits_key ON rate_limits(key, timestamp);

CREATE TABLE IF NOT EXISTS trusted_devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    device_hash TEXT    NOT NULL,
    device_name TEXT,
    last_used_at TEXT   NOT NULL DEFAULT (datetime('now')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_trusted_devices_user ON trusted_devices(user_id);

CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    credential_id TEXT    NOT NULL UNIQUE,
    public_key    BLOB    NOT NULL,
    sign_count    INTEGER NOT NULL DEFAULT 0,
    device_name   TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_webauthn_user ON webauthn_credentials(user_id);

CREATE TABLE IF NOT EXISTS oauth_accounts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    provider          TEXT    NOT NULL,
    provider_user_id  TEXT    NOT NULL,
    email             TEXT,
    display_name      TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(provider, provider_user_id)
);
CREATE INDEX IF NOT EXISTS idx_oauth_user ON oauth_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_provider ON oauth_accounts(provider, provider_user_id);

-- ── Cross-system identity continuity ──
-- One row per student lifecycle. Per-system PKs / human IDs are NULL until
-- that system has a record. Identity hints (DOB + name + UPN/NHS) bootstrap
-- a journey when no link exists yet. See shared.cross_system.identity_service.
CREATE TABLE IF NOT EXISTS student_journey (
    journey_id            TEXT    PRIMARY KEY,
    nursery_pk            INTEGER,
    primary_pk            INTEGER,
    school_pk             INTEGER,
    college_pk            INTEGER,
    university_pk         INTEGER,
    -- FE College and Apprenticeships are post-16 destinations that sit
    -- alongside sixth form rather than after it. They get their own slots
    -- because ``college_*`` already belongs to the sixth-form system and
    -- reusing it would merge two different institutions' learner ids.
    fe_college_pk         INTEGER,
    apprenticeships_pk    INTEGER,
    nursery_student_id    TEXT,
    primary_student_id    TEXT,
    school_student_id     TEXT,
    college_student_id    TEXT,
    university_student_id TEXT,
    fe_college_student_id TEXT,
    -- Named ``learner_id``, not ``student_id``: an apprentice is employed
    -- and the system's own vocabulary says so throughout.
    apprenticeships_learner_id TEXT,
    legal_first_name      TEXT    NOT NULL,
    legal_last_name       TEXT    NOT NULL,
    date_of_birth         TEXT    NOT NULL,
    nhs_number            TEXT,
    upn                   TEXT,
    current_system        TEXT    NOT NULL,
    status                TEXT    NOT NULL DEFAULT 'active',
    created_at            TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT    NOT NULL DEFAULT (datetime('now'))
);
-- Identity lookup index — deliberately NOT unique. Two different people can
-- share a legal name and a date of birth; the old unique
-- ``idx_journey_dob_name`` made the registry fold the second of them onto
-- the first one's journey, so their records silently merged. Resolution
-- now disambiguates on NHS number, UPN and open local records (see
-- identity_service), and real duplicates are merged deliberately through
-- identity_service.merge_journeys. The old index is dropped in the
-- migration block of initialise_auth_db.
CREATE INDEX IF NOT EXISTS idx_journey_identity
    ON student_journey(date_of_birth, legal_last_name, legal_first_name);
CREATE INDEX IF NOT EXISTS idx_journey_college_pk
    ON student_journey(college_pk) WHERE college_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_journey_university_pk
    ON student_journey(university_pk) WHERE university_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_journey_school_pk
    ON student_journey(school_pk) WHERE school_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_journey_primary_pk
    ON student_journey(primary_pk) WHERE primary_pk IS NOT NULL;
-- NB: the fe_college_pk / apprenticeships_pk indexes are deliberately NOT
-- here. This script runs before the column migration below, so on an
-- existing database CREATE TABLE is a no-op, the columns do not exist yet,
-- and indexing them would raise "no such column" and abort the whole init.
-- They are created in the migration block instead, after the ALTERs.

-- Append-only audit of every system transition.
CREATE TABLE IF NOT EXISTS student_journey_transitions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id    TEXT    NOT NULL REFERENCES student_journey(journey_id),
    from_system   TEXT,
    to_system     TEXT    NOT NULL,
    reason        TEXT,
    actor_user_id INTEGER,
    occurred_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_journey_trans_journey
    ON student_journey_transitions(journey_id);

-- Log of identity merges (identity_service.merge_journeys). One row per
-- duplicate folded into a survivor; the snapshot is the duplicate's row as
-- it stood, so an operator can reverse a wrong merge by hand.
CREATE TABLE IF NOT EXISTS student_journey_merges (
    merge_id                TEXT    PRIMARY KEY,
    survivor_id             TEXT    NOT NULL REFERENCES student_journey(journey_id),
    duplicate_id            TEXT    NOT NULL REFERENCES student_journey(journey_id),
    actor                   TEXT    NOT NULL,
    reason                  TEXT,
    moved_json              TEXT    NOT NULL,
    duplicate_snapshot_json TEXT    NOT NULL,
    merged_at               TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_journey_merges_duplicate
    ON student_journey_merges(duplicate_id);
CREATE INDEX IF NOT EXISTS idx_journey_merges_survivor
    ON student_journey_merges(survivor_id);

-- Pairs an administrator has confirmed are different people (twins, two
-- unrelated learners sharing a name and birthday), so the duplicate
-- finder stops proposing them. Stored with journey_a < journey_b.
CREATE TABLE IF NOT EXISTS student_journey_distinct (
    journey_a   TEXT    NOT NULL,
    journey_b   TEXT    NOT NULL,
    actor       TEXT    NOT NULL,
    reason      TEXT,
    decided_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (journey_a, journey_b)
);

-- ── Cross-system durable event bus ──
-- Producers append; consumer pollers (one per subsystem process) read events
-- targeted at their system (or with target_system NULL = broadcast) and
-- record an ack row in cross_system_event_consumed. See
-- shared.integrations.cross_system_bus.
--
-- NB: named ``cross_system_event_outbox`` because the table name
-- ``cross_system_events`` was already taken by the calendar module
-- (shared/calendar/calendar_service.py) for a completely different
-- schema (title/date/time). Both live in this same auth DB.
CREATE TABLE IF NOT EXISTS cross_system_event_outbox (
    event_id       TEXT    PRIMARY KEY,
    event_name     TEXT    NOT NULL,
    event_version  INTEGER NOT NULL DEFAULT 1,
    correlation_id TEXT    NOT NULL,
    causation_id   TEXT,
    idempotency_key TEXT   NOT NULL UNIQUE,
    journey_id     TEXT,
    source_system  TEXT    NOT NULL,
    source_module  TEXT    NOT NULL,
    target_system  TEXT,
    payload_json   TEXT    NOT NULL,
    actor_user_id  INTEGER,
    available_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cse_target_time
    ON cross_system_event_outbox(target_system, created_at);
CREATE INDEX IF NOT EXISTS idx_cse_event_name
    ON cross_system_event_outbox(event_name, created_at);
CREATE INDEX IF NOT EXISTS idx_cse_journey
    ON cross_system_event_outbox(journey_id) WHERE journey_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cross_system_event_consumed (
    event_id         TEXT    NOT NULL REFERENCES cross_system_event_outbox(event_id),
    consumer_system  TEXT    NOT NULL,
    consumer_handler TEXT    NOT NULL,
    status           TEXT    NOT NULL,
    error_message    TEXT,
    attempts         INTEGER NOT NULL DEFAULT 1,
    next_attempt_at  TEXT,
    consumed_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (event_id, consumer_system, consumer_handler)
);
CREATE INDEX IF NOT EXISTS idx_cse_consumed_status
    ON cross_system_event_consumed(consumer_system, status, consumed_at);

-- Sensitive-record purpose and break-glass access control. No clinical or
-- safeguarding content is stored here; only authorization/audit metadata.
CREATE TABLE IF NOT EXISTS sensitive_access_audit (
    audit_id       TEXT PRIMARY KEY,
    actor_id       TEXT NOT NULL,
    actor_role     TEXT NOT NULL,
    domain         TEXT NOT NULL,
    subject_id     TEXT,
    fields_json    TEXT NOT NULL,
    purpose        TEXT NOT NULL,
    decision       TEXT NOT NULL,
    reason         TEXT,
    correlation_id TEXT,
    occurred_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sensitive_access_subject
    ON sensitive_access_audit(domain, subject_id, occurred_at);
CREATE TRIGGER IF NOT EXISTS prevent_sensitive_access_audit_update
BEFORE UPDATE ON sensitive_access_audit
BEGIN
    SELECT RAISE(ABORT, 'sensitive access audit records are immutable');
END;
CREATE TRIGGER IF NOT EXISTS prevent_sensitive_access_audit_delete
BEFORE DELETE ON sensitive_access_audit
BEGIN
    SELECT RAISE(ABORT, 'sensitive access audit records are immutable');
END;

CREATE TABLE IF NOT EXISTS break_glass_grants (
    grant_id        TEXT PRIMARY KEY,
    actor_id        TEXT NOT NULL,
    domain          TEXT NOT NULL,
    subject_id      TEXT,
    purpose         TEXT NOT NULL,
    reason          TEXT NOT NULL,
    approved_by     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    requested_at    TEXT NOT NULL DEFAULT (datetime('now')),
    approved_at     TEXT,
    expires_at      TEXT NOT NULL,
    reviewed_by     TEXT,
    reviewed_at     TEXT,
    review_outcome  TEXT
);
CREATE INDEX IF NOT EXISTS idx_break_glass_actor
    ON break_glass_grants(actor_id, status, expires_at);

-- ── Cross-system safeguarding alerts ──
-- A flag raised in one system, keyed on the canonical journey_id so it
-- follows the learner everywhere. Any system can read a pupil's alerts via
-- shared.safeguarding.alert_service.get_alerts(journey_id).
CREATE TABLE IF NOT EXISTS safeguarding_alerts (
    alert_id      TEXT    PRIMARY KEY,
    journey_id    TEXT    NOT NULL,
    source_system TEXT    NOT NULL,
    source_ref    TEXT,
    category      TEXT,
    severity      TEXT    NOT NULL DEFAULT 'medium',
    summary       TEXT,
    raised_by     TEXT,
    status        TEXT    NOT NULL DEFAULT 'open',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_safeguard_journey
    ON safeguarding_alerts(journey_id, status);

-- ── Cross-system staff directory ──
-- One row per real staff member; per-system staff ids fill in as they're
-- employed across systems. Matched on (first/last name) — staff have no
-- shared natural key. See shared.staff_directory.staff_directory_service.
CREATE TABLE IF NOT EXISTS staff_directory (
    staff_person_id  TEXT    PRIMARY KEY,
    nursery_staff_id    TEXT,
    primary_staff_id    TEXT,
    school_staff_id     TEXT,
    college_staff_id    TEXT,
    university_staff_id TEXT,
    legal_first_name TEXT    NOT NULL,
    legal_last_name  TEXT    NOT NULL,
    email            TEXT,
    primary_role     TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_staffdir_name
    ON staff_directory(legal_last_name, legal_first_name);
"""

# ── Default account definitions ──────────────────────────────────────────────
#
# ⚠  WARNING — DEV/DEMO ONLY ⚠
# These passwords are intentionally weak for local development and demos.
# They MUST be changed before any production or internet-facing deployment.
# Consider using environment variables or a secrets manager in production.
#
# 26 accounts total:
#   1  Super Admin   — every system as admin (SuperAdmin@123)
#   7  Admins        — 1 per system
#                     (admin/admin1/admin2/admin3/admin4/admin5/admin6)
#   4  Staff         — university, college, school, primary
#                     (staff/staff1/staff2/staff3)
#   4  Students      — university, college, school, primary
#                     (S12345/student1/student2/student3)
#   4  Parents       — university, college, school, primary
#                     (parent/parent1/parent2/parent3)
#   4  Apprenticeships-specific — tutor1, apprentice1, employer1, assessor1
#   2  FE College-specific      — lecturer1, learner1
#
# Nursery seeds an admin only.

_DEFAULT_ACCOUNTS = [
    # ── Super Admin (all systems) ────────────────────────────────────────
    {
        "username": "superadmin",
        "password": "SuperAdmin@123",
        "display_name": "Super Administrator",
        "email": "superadmin@education.local",
        "systems": [
            ("university", "admin"),
            ("sixth_form", "admin"),
            ("secondary", "admin"),
            ("primary", "admin"),
            ("nursery", "admin"),
            ("apprenticeships", "admin"),
            ("fe_college", "admin"),
        ],
    },
    # ── University accounts ────────────────────────────────────────────────
    {
        "username": "admin",
        "password": "admin123",
        "display_name": "University Administrator",
        "email": "admin@university.edu",
        "systems": [("university", "admin")],
    },
    {
        "username": "staff",
        "password": "staff123",
        "display_name": "University Staff",
        "email": "staff@university.edu",
        "systems": [("university", "staff")],
    },
    {
        "username": "S12345",
        "password": "student123",
        "display_name": "Demo Student",
        "email": "student@university.edu",
        "systems": [("university", "student")],
    },
    # ── College accounts ─────────────────────────────────────────────────
    {
        "username": "admin1",
        "password": "admin1234",
        "display_name": "College Administrator",
        "email": "admin@college.local",
        "systems": [("sixth_form", "admin")],
    },
    {
        "username": "staff1",
        "password": "staff1234",
        "display_name": "College Staff",
        "email": "staff@college.local",
        "systems": [("sixth_form", "teacher")],
    },
    {
        "username": "student1",
        "password": "student1234",
        "display_name": "College Student",
        "email": "student@college.local",
        "systems": [("sixth_form", "student")],
    },
    # ── Secondary School accounts ────────────────────────────────────────
    {
        "username": "admin2",
        "password": "admin1234",
        "display_name": "School Administrator",
        "email": "admin@school.local",
        "systems": [("secondary", "admin")],
    },
    {
        "username": "staff2",
        "password": "staff1234",
        "display_name": "School Staff",
        "email": "staff@school.local",
        "systems": [("secondary", "teacher")],
    },
    {
        "username": "student2",
        "password": "student1234",
        "display_name": "School Student",
        "email": "student@school.local",
        "systems": [("secondary", "student")],
    },
    # ── Primary School accounts ──────────────────────────────────────────
    {
        "username": "admin3",
        "password": "admin1234",
        "display_name": "Primary Administrator",
        "email": "admin@primary.local",
        "systems": [("primary", "admin")],
    },
    {
        "username": "staff3",
        "password": "staff1234",
        "display_name": "Primary Staff",
        "email": "staff@primary.local",
        "systems": [("primary", "teacher")],
    },
    {
        "username": "student3",
        "password": "student1234",
        "display_name": "Primary Student",
        "email": "student@primary.local",
        "systems": [("primary", "student")],
    },
    # ── Nursery accounts ─────────────────────────────────────────────────
    {
        "username": "admin4",
        "password": "admin1234",
        "display_name": "Nursery Administrator",
        "email": "admin@nursery.local",
        "systems": [("nursery", "admin")],
    },
    # ── Apprenticeships accounts ─────────────────────────────────────────
    # Five roles, because an apprenticeship has five parties round it:
    # the provider, the tutor delivering it, the learner, the employer,
    # and the independent end-point assessor.
    {
        "username": "admin5",
        "password": "admin1234",
        "display_name": "Apprenticeships Administrator",
        "email": "admin@apprenticeships.local",
        "systems": [("apprenticeships", "admin")],
    },
    {
        "username": "tutor1",
        "password": "tutor1234",
        "display_name": "Apprenticeship Tutor",
        "email": "tutor@apprenticeships.local",
        "systems": [("apprenticeships", "staff")],
    },
    {
        "username": "apprentice1",
        "password": "apprentice1234",
        "display_name": "Demo Apprentice",
        "email": "apprentice@apprenticeships.local",
        "systems": [("apprenticeships", "apprentice")],
    },
    {
        "username": "employer1",
        "password": "employer1234",
        "display_name": "Employer Manager",
        "email": "manager@employer.local",
        "systems": [("apprenticeships", "employer")],
    },
    {
        "username": "assessor1",
        "password": "assessor1234",
        "display_name": "End-Point Assessor",
        "email": "assessor@epao.local",
        "systems": [("apprenticeships", "end_point_assessor")],
    },
    # ── FE College accounts ──────────────────────────────────────────────
    # The emails matter: the FE College system joins a signed-in account to
    # its own staff or learner record by email address, so these must match
    # the records its demo seed creates (see fe_college demo_data.ADMIN_EMAIL,
    # LECTURER_EMAIL and LEARNER_EMAIL). Change one and change both.
    {
        "username": "admin6",
        "password": "admin1234",
        "display_name": "FE College Administrator",
        "email": "admin@riverside.ac.uk",
        "systems": [("fe_college", "admin")],
    },
    {
        "username": "lecturer1",
        "password": "lecturer1234",
        "display_name": "FE College Lecturer",
        "email": "dev.chaudhury@riverside.ac.uk",
        "systems": [("fe_college", "teacher")],
    },
    {
        "username": "learner1",
        "password": "learner1234",
        "display_name": "FE College Learner",
        "email": "student@riverside.ac.uk",
        "systems": [("fe_college", "student")],
    },
    # ── Parent accounts ─────────────────────────────────────────────────
    {
        "username": "parent",
        "password": "parent123",
        "display_name": "University Parent",
        "email": "parent@university.edu",
        "systems": [("university", "parent")],
    },
    {
        "username": "parent1",
        "password": "parent1234",
        "display_name": "College Parent",
        "email": "parent@college.local",
        "systems": [("sixth_form", "parent")],
    },
    {
        "username": "parent2",
        "password": "parent1234",
        "display_name": "School Parent",
        "email": "parent@school.local",
        "systems": [("secondary", "parent")],
    },
    {
        "username": "parent3",
        "password": "parent1234",
        "display_name": "Primary Parent",
        "email": "parent@primary.local",
        "systems": [("primary", "parent")],
    },
]


# ── Default security questions for demo accounts ────────────────────────────
# Maps username → list of (question, answer) tuples.
# Only seeded when EDU_DEV_SEED=true (dev/demo); never on a production DB.
_DEFAULT_SECURITY_QA = {
    "superadmin": [
        ("What is your mother's maiden name?", "smith"),
        ("What city were you born in?", "london"),
        ("What is the name of your first pet?", "buddy"),
    ],
    "S12345": [
        ("What is your mother's maiden name?", "jones"),
        ("What city were you born in?", "manchester"),
        ("What is the name of your first pet?", "max"),
    ],
    "student1": [
        ("What is your mother's maiden name?", "williams"),
        ("What city were you born in?", "birmingham"),
        ("What is the name of your first pet?", "charlie"),
    ],
    "student2": [
        ("What is your mother's maiden name?", "brown"),
        ("What city were you born in?", "leeds"),
        ("What is the name of your first pet?", "bella"),
    ],
    "student3": [
        ("What is your mother's maiden name?", "taylor"),
        ("What city were you born in?", "bristol"),
        ("What is the name of your first pet?", "daisy"),
    ],
}

# Canonical list of security questions users can choose from.
# Includes knowledge-based, behavioral, and preference-based options.
SECURITY_QUESTIONS = [
    # Knowledge-based
    "What is your mother's maiden name?",
    "What city were you born in?",
    "What is the name of your first pet?",
    "What was the name of your first school?",
    # Preference-based
    "What is your favourite book?",
    "What is your favourite film?",
    "What is your favourite food?",
    # Behavioral
    "What street did you grow up on?",
    "What was the first concert you attended?",
    "What was the make of your first car?",
    "What is the middle name of your oldest sibling?",
    "What was the name of your childhood best friend?",
]

# ── Security-answer policy ──────────────────────────────────────────────────

MIN_ANSWER_LENGTH = 4

# Answers that are too common / obvious to provide meaningful security.
BANNED_ANSWERS = frozenset({
    "password", "123456", "none", "n/a", "test", "unknown",
    "default", "abc", "abcd", "xxxx", "admin", "user", "answer", "secret",
    "idk", "null", "blank", "nothing", "same", "myself", "asdf",
    "1234", "qwerty", "hello", "name", "word", "pass", "true", "false",
})

# Retention: how many days to keep rate-limit attempts and audit entries.
# Override via environment variables.
SQ_ATTEMPTS_RETENTION_DAYS = int(os.environ.get("SQ_ATTEMPTS_RETENTION_DAYS", "90"))
SECURITY_AUDIT_RETENTION_DAYS = int(os.environ.get("SECURITY_AUDIT_RETENTION_DAYS", "365"))


def _hash_answer(answer: str) -> str:
    """Hash a security question answer with bcrypt (case-insensitive).

    Uses bcrypt for adaptive-cost offline attack resistance, unlike the
    previous SHA-256 approach which was fast and unsalted.
    """
    normalised = answer.strip().lower().encode("utf-8")
    return bcrypt.hashpw(normalised, bcrypt.gensalt()).decode("utf-8")


def _verify_answer(answer: str, answer_hash: str) -> bool:
    """Verify a security question answer against its bcrypt hash.

    Also supports legacy SHA-256 hashes (64 hex chars, no ``$`` prefix)
    for answers stored before the bcrypt upgrade.
    """
    normalised = answer.strip().lower().encode("utf-8")
    # Legacy SHA-256 detection: 64 hex chars, no bcrypt "$2" prefix
    if len(answer_hash) == 64 and not answer_hash.startswith("$"):
        return hashlib.sha256(normalised).hexdigest() == answer_hash
    try:
        return bcrypt.checkpw(normalised, answer_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def rehash_answer_if_legacy(answer: str, answer_hash: str) -> str | None:
    """If *answer_hash* is a legacy SHA-256 hash and the answer matches,
    return a fresh bcrypt hash.  Otherwise return None (no rehash needed)."""
    if len(answer_hash) == 64 and not answer_hash.startswith("$"):
        normalised = answer.strip().lower().encode("utf-8")
        if hashlib.sha256(normalised).hexdigest() == answer_hash:
            return bcrypt.hashpw(normalised, bcrypt.gensalt()).decode("utf-8")
    return None


def validate_answer(answer: str) -> tuple[bool, str]:
    """Validate a security-question answer against policy rules.

    Checks: minimum length, banned answers, and basic entropy (must not
    be a single repeated character).

    Returns (is_valid, error_message).
    """
    stripped = answer.strip()
    if len(stripped) < MIN_ANSWER_LENGTH:
        return False, f"Answer must be at least {MIN_ANSWER_LENGTH} characters."
    if stripped.lower() in BANNED_ANSWERS:
        return False, "That answer is too common. Please choose something more specific."
    # Entropy check: reject single-character repetition (e.g. "aaaa", "1111")
    if len(set(stripped.lower())) == 1:
        return False, "Answer must contain more than one distinct character."
    return True, ""


def cleanup_sq_tables(db_path: str | None = None):
    """Delete expired rows from sq_verification_attempts and security_audit_log.

    Called opportunistically (e.g. on startup or via a scheduled job).
    Retention periods are controlled by ``SQ_ATTEMPTS_RETENTION_DAYS`` and
    ``SECURITY_AUDIT_RETENTION_DAYS`` (env-var overridable).
    """
    from datetime import datetime, timedelta
    conn = connect(db_path)
    try:
        attempt_cutoff = (datetime.utcnow() - timedelta(days=SQ_ATTEMPTS_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            "DELETE FROM sq_verification_attempts WHERE created_at < ?",
            (attempt_cutoff,),
        )
        attempts_deleted = cur.rowcount

        audit_cutoff = (datetime.utcnow() - timedelta(days=SECURITY_AUDIT_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            "DELETE FROM security_audit_log WHERE created_at < ?",
            (audit_cutoff,),
        )
        audit_deleted = cur.rowcount

        conn.commit()
        if attempts_deleted or audit_deleted:
            logger.info(
                "Retention cleanup: removed %d expired SQ attempts, %d audit entries",
                attempts_deleted, audit_deleted,
            )
    finally:
        conn.close()


def initialise_auth_db(db_path: str | None = None):
    """Create the auth tables if they don't already exist."""
    conn = connect(db_path)
    try:
        conn.executescript(_TABLES_SQL)
        conn.commit()

        # Add missing columns to existing databases (migrations)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "legacy_salt" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN legacy_salt TEXT")
        if "password_changed_at" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN password_changed_at TEXT")
        if "email_verified" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
        if "line_manager_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN line_manager_id INTEGER")
        if "must_change_password" not in cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN must_change_password "
                "INTEGER NOT NULL DEFAULT 0"
            )
        # Login -> learner link (identity_service.link_user_account). The
        # users row and the student_journey row describe the same person
        # but nothing joined them, so "which logins does this learner
        # have?" could only be guessed from names or emails.
        if "journey_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN journey_id TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_journey "
            "ON users(journey_id) WHERE journey_id IS NOT NULL"
        )
        conn.commit()

        # System-key rename: converge Sixth Form (college→sixth_form) and
        # Secondary (school→secondary) onto their canonical keys. Idempotent —
        # a no-op once rows are already canonical.
        try:
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_systems'"
            ).fetchone():
                conn.execute(
                    "UPDATE user_systems SET system_key='sixth_form' WHERE system_key='college'"
                )
                conn.execute(
                    "UPDATE user_systems SET system_key='secondary' WHERE system_key='school'"
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.warning("System-key migration skipped: %s", exc)

        # student_journey gained a nursery slot so all 5 systems can link,
        # then fe_college and apprenticeships slots when those two joined the
        # cross-system registry. Adding a slot is always additive: an existing
        # database keeps every row and simply gains NULL columns, so this is
        # safe to run against a live auth.db.
        jcols = {
            r[1] for r in
            conn.execute("PRAGMA table_info(student_journey)").fetchall()
        }
        if jcols:  # table exists
            for column, coltype in (
                ("nursery_pk", "INTEGER"),
                ("nursery_student_id", "TEXT"),
                ("fe_college_pk", "INTEGER"),
                ("fe_college_student_id", "TEXT"),
                ("apprenticeships_pk", "INTEGER"),
                ("apprenticeships_learner_id", "TEXT"),
                # Identity merge tombstone: a merged journey keeps its row
                # (status 'merged') and points at the survivor.
                ("merged_into", "TEXT"),
                ("merged_at", "TEXT"),
            ):
                if column not in jcols:
                    conn.execute(
                        f"ALTER TABLE student_journey ADD COLUMN {column} {coltype}")
            # The unique name+DOB index forced two different people who share
            # a name and birthday onto one journey. It is replaced by the
            # non-unique idx_journey_identity in _TABLES_SQL. Dropping an index
            # never touches rows, and IF EXISTS makes this a no-op once done.
            conn.execute("DROP INDEX IF EXISTS idx_journey_dob_name")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_journey_merged_into "
                "ON student_journey(merged_into) WHERE merged_into IS NOT NULL")
            # The partial indexes live in _TABLES_SQL, which runs before this
            # block — on an old database the columns did not exist yet, so
            # those CREATE INDEX statements were skipped. Create them here now
            # the columns are present.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_journey_fe_college_pk "
                "ON student_journey(fe_college_pk) WHERE fe_college_pk IS NOT NULL")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_journey_apprenticeships_pk "
                "ON student_journey(apprenticeships_pk) "
                "WHERE apprenticeships_pk IS NOT NULL")
            conn.commit()

        event_cols = {
            r[1] for r in
            conn.execute("PRAGMA table_info(cross_system_event_outbox)").fetchall()
        }
        for name, definition in (
            ("event_version", "INTEGER NOT NULL DEFAULT 1"),
            ("correlation_id", "TEXT"),
            ("causation_id", "TEXT"),
            ("idempotency_key", "TEXT"),
            ("available_at", "TEXT"),
        ):
            if event_cols and name not in event_cols:
                conn.execute(
                    f"ALTER TABLE cross_system_event_outbox "
                    f"ADD COLUMN {name} {definition}"
                )
        if event_cols:
            conn.execute(
                "UPDATE cross_system_event_outbox "
                "SET correlation_id = COALESCE(correlation_id, event_id), "
                "idempotency_key = COALESCE(idempotency_key, event_id), "
                "available_at = COALESCE(available_at, created_at)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_cse_idempotency "
                "ON cross_system_event_outbox(idempotency_key)"
            )
        receipt_cols = {
            r[1] for r in
            conn.execute("PRAGMA table_info(cross_system_event_consumed)").fetchall()
        }
        if receipt_cols and "next_attempt_at" not in receipt_cols:
            conn.execute(
                "ALTER TABLE cross_system_event_consumed "
                "ADD COLUMN next_attempt_at TEXT"
            )
        conn.commit()

        logger.info("Auth database initialised")
    finally:
        conn.close()

    # Opportunistic retention cleanup
    try:
        cleanup_sq_tables(db_path)
    except Exception:
        pass  # table may not exist on very first init


_WEAK_DEFAULT_USERNAMES = {a["username"] for a in _DEFAULT_ACCOUNTS}
_WEAK_DEFAULT_PASSWORDS = {a["password"] for a in _DEFAULT_ACCOUNTS}


def check_weak_defaults(db_path: str | None = None) -> list[str]:
    """Check whether any default demo accounts still use their original weak
    passwords.  Returns a list of usernames that should be rotated.

    In production (``EDU_PRODUCTION=true``), logs a critical warning.
    """
    from education_system.platform.identity.auth.password_manager import verify_password
    conn = connect(db_path)
    try:
        weak = []
        for acct in _DEFAULT_ACCOUNTS:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE username = ? AND is_active = 1",
                (acct["username"],),
            ).fetchone()
            if row and verify_password(acct["password"], row["password_hash"]):
                weak.append(acct["username"])
        if weak and os.environ.get("EDU_PRODUCTION", "").strip().lower() in ("1", "true", "yes"):
            logger.critical(
                "PRODUCTION SECURITY WARNING: %d default account(s) still use "
                "weak demo passwords: %s. Rotate them immediately.",
                len(weak), ", ".join(weak),
            )
        return weak
    finally:
        conn.close()


def _is_dev_mode() -> bool:
    """Check whether dev/demo seeding is enabled.

    Returns True **only** when ``EDU_DEV_SEED`` is set to a truthy value
    (``true``, ``1``, ``yes``, ``on``).  Default is False (opt-in).

    This flag gates *all* seeding of the well-known weak demo accounts,
    including on a brand-new database. A fresh production database (flag
    unset) is therefore never auto-provisioned with ``admin``/``admin123``
    and friends; use ``EDU_INITIAL_ADMIN_USER``/``EDU_INITIAL_ADMIN_PASSWORD``
    to bootstrap a single strong admin instead (see ``_bootstrap_admin_from_env``).
    """
    val = os.environ.get("EDU_DEV_SEED", "").strip().lower()
    return val in ("1", "true", "yes", "on")


# Minimum length for an operator-supplied bootstrap admin password. Kept
# deliberately stricter than the weak demo passwords this feature replaces.
_MIN_BOOTSTRAP_PASSWORD_LEN = 12


def _bootstrap_admin_from_env(conn) -> bool:
    """On a fresh, non-dev database, create a single admin from environment.

    Reads ``EDU_INITIAL_ADMIN_USER`` and ``EDU_INITIAL_ADMIN_PASSWORD`` (and
    optional ``EDU_INITIAL_ADMIN_EMAIL``) and, if both are present and the
    password meets the minimum strength bar, creates one admin account with
    access to all five systems. The operator chose this password, so it is
    *not* flagged must-change. Returns True if an account was created.
    """
    username = os.environ.get("EDU_INITIAL_ADMIN_USER", "").strip()
    password = os.environ.get("EDU_INITIAL_ADMIN_PASSWORD", "")
    if not username or not password:
        return False

    if len(password) < _MIN_BOOTSTRAP_PASSWORD_LEN:
        logger.error(
            "EDU_INITIAL_ADMIN_PASSWORD is too short (min %d chars); "
            "refusing to bootstrap admin '%s'.",
            _MIN_BOOTSTRAP_PASSWORD_LEN, username,
        )
        return False

    email = os.environ.get("EDU_INITIAL_ADMIN_EMAIL", "").strip() or None
    all_systems = [
        ("university", "admin"),
        ("sixth_form", "admin"),
        ("secondary", "admin"),
        ("primary", "admin"),
        ("nursery", "admin"),
        ("fe_college", "admin"),
    ]
    _create_default_user(
        conn,
        username=username,
        password=password,
        display_name="Initial Administrator",
        email=email,
        systems=all_systems,
        must_change=0,
    )
    return True


def seed_default_users(db_path: str | None = None):
    """Create the default user accounts on first run, and ensure all system
    access records exist for existing databases that are being upgraded.

    Seeding of the well-known weak demo accounts is gated behind
    ``EDU_DEV_SEED`` — including on a fresh database. A fresh *production*
    database (flag unset) is bootstrapped from ``EDU_INITIAL_ADMIN_*`` env
    vars if provided, otherwise left empty with guidance logged. Existing
    databases are never re-seeded with demo accounts unless in dev mode.
    """
    dev_mode = _is_dev_mode()
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        is_fresh = row["cnt"] == 0

        if is_fresh and dev_mode:
            # Fresh database in dev mode — create the demo accounts
            for acct in _DEFAULT_ACCOUNTS:
                _create_default_user(
                    conn,
                    username=acct["username"],
                    password=acct["password"],
                    display_name=acct["display_name"],
                    email=acct["email"],
                    systems=acct["systems"],
                )
            _seed_security_questions(conn)
            conn.commit()
            logger.info("Seeded %d default auth accounts", len(_DEFAULT_ACCOUNTS))
            logger.warning(
                "Default accounts use WEAK passwords (e.g. admin123, staff1234). "
                "They are seeded because EDU_DEV_SEED is enabled. NEVER enable "
                "EDU_DEV_SEED on a production or internet-facing deployment."
            )
        elif is_fresh and not dev_mode:
            # Fresh production database — do NOT auto-provision weak defaults.
            if _bootstrap_admin_from_env(conn):
                conn.commit()
                logger.info(
                    "Bootstrapped initial admin from EDU_INITIAL_ADMIN_* env vars."
                )
            else:
                logger.warning(
                    "Fresh auth database and EDU_DEV_SEED is not enabled: no default "
                    "accounts were created. To bootstrap, either set "
                    "EDU_INITIAL_ADMIN_USER + EDU_INITIAL_ADMIN_PASSWORD to create a "
                    "single strong admin, or set EDU_DEV_SEED=true for the weak demo "
                    "accounts (local development / demos only)."
                )
        elif dev_mode:
            # Existing database in dev mode — ensure new accounts exist
            _ensure_default_accounts(conn)
            _seed_security_questions(conn)
            conn.commit()
        else:
            logger.debug(
                "Skipping demo account seeding (EDU_DEV_SEED is not enabled "
                "and database already has %d users)", row["cnt"],
            )
    finally:
        conn.close()


def _ensure_default_accounts(conn):
    """For existing databases, create any missing default accounts and
    ensure all user_systems records exist (e.g. when university is added
    to a database that only had college/school/primary)."""
    for acct in _DEFAULT_ACCOUNTS:
        username = acct["username"]
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()

        if row is None:
            # Account doesn't exist — create it
            _create_default_user(
                conn,
                username=username,
                password=acct["password"],
                display_name=acct["display_name"],
                email=acct["email"],
                systems=acct["systems"],
            )
            logger.info("Created missing default account: %s", username)
        else:
            # Account exists — ensure all system access records are present
            user_id = row["id"]
            for system_key, role in (acct.get("systems") or []):
                conn.execute(
                    """INSERT OR IGNORE INTO user_systems
                       (user_id, system_key, role) VALUES (?, ?, ?)""",
                    (user_id, system_key, role),
                )


def _create_default_user(
    conn, username, password, display_name=None, email=None, systems=None,
    must_change=1,
):
    """Insert a user and their system access records.

    ``must_change`` defaults to 1 for the weak demo accounts so the login flow
    forces a new password on first use. An operator-provided bootstrap admin
    (whose password they chose deliberately) passes ``must_change=0``.
    """
    pw_hash = hash_password(password)
    # Stamp password_changed_at so seeded demo accounts aren't treated as
    # "never set" (which check_password_expiry counts as expired and would
    # force a password reset on the very first login). This mirrors the other
    # default accounts, which already carry a timestamp.
    cursor = conn.execute(
        """INSERT OR IGNORE INTO users
           (username, password_hash, display_name, email,
            password_changed_at, must_change_password)
           VALUES (?, ?, ?, ?, datetime('now'), ?)""",
        (username, pw_hash, display_name, email, must_change),
    )
    user_id = cursor.lastrowid
    if user_id and systems:
        for system_key, role in systems:
            conn.execute(
                """INSERT OR IGNORE INTO user_systems
                   (user_id, system_key, role) VALUES (?, ?, ?)""",
                (user_id, system_key, role),
            )


def _seed_security_questions(conn):
    """Seed security questions for demo accounts that don't already have them."""
    for username, qa_list in _DEFAULT_SECURITY_QA.items():
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not row:
            continue
        user_id = row["id"]
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM security_questions WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if existing["cnt"] > 0:
            continue
        for question, answer in qa_list:
            conn.execute(
                "INSERT INTO security_questions (user_id, question, answer_hash) VALUES (?, ?, ?)",
                (user_id, question, _hash_answer(answer)),
            )
    logger.info("Security questions seeded for demo accounts")
