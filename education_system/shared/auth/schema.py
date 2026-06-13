"""Schema initialisation and seed data for the shared auth database."""

import hashlib
import logging
import os

import bcrypt

from education_system.shared.auth.db import connect
from education_system.shared.auth.password_manager import hash_password

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
    nursery_student_id    TEXT,
    primary_student_id    TEXT,
    school_student_id     TEXT,
    college_student_id    TEXT,
    university_student_id TEXT,
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_journey_dob_name
    ON student_journey(date_of_birth, legal_last_name, legal_first_name);
CREATE INDEX IF NOT EXISTS idx_journey_college_pk
    ON student_journey(college_pk) WHERE college_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_journey_university_pk
    ON student_journey(university_pk) WHERE university_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_journey_school_pk
    ON student_journey(school_pk) WHERE school_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_journey_primary_pk
    ON student_journey(primary_pk) WHERE primary_pk IS NOT NULL;

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
    journey_id     TEXT,
    source_system  TEXT    NOT NULL,
    source_module  TEXT    NOT NULL,
    target_system  TEXT,
    payload_json   TEXT    NOT NULL,
    actor_user_id  INTEGER,
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
    consumed_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (event_id, consumer_system, consumer_handler)
);
CREATE INDEX IF NOT EXISTS idx_cse_consumed_status
    ON cross_system_event_consumed(consumer_system, status, consumed_at);

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
# 13 accounts total:
#   1  Super Admin   — all 5 systems as admin
#   5  Admins        — 1 per system (admin/admin1/admin2/admin3/admin4)
#   4  Staff         — 1 per system (staff/staff1/staff2/staff3)
#   4  Students      — 1 per system (S12345/student1/student2/student3)
#
# Super Admin uses SuperAdmin@123

_DEFAULT_ACCOUNTS = [
    # ── Super Admin (all systems) ────────────────────────────────────────
    {
        "username": "superadmin",
        "password": "SuperAdmin@123",
        "display_name": "Super Administrator",
        "email": "superadmin@education.local",
        "systems": [
            ("university", "admin"),
            ("college", "admin"),
            ("school", "admin"),
            ("primary", "admin"),
            ("nursery", "admin"),
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
        "systems": [("college", "admin")],
    },
    {
        "username": "staff1",
        "password": "staff1234",
        "display_name": "College Staff",
        "email": "staff@college.local",
        "systems": [("college", "teacher")],
    },
    {
        "username": "student1",
        "password": "student1234",
        "display_name": "College Student",
        "email": "student@college.local",
        "systems": [("college", "student")],
    },
    # ── Secondary School accounts ────────────────────────────────────────
    {
        "username": "admin2",
        "password": "admin1234",
        "display_name": "School Administrator",
        "email": "admin@school.local",
        "systems": [("school", "admin")],
    },
    {
        "username": "staff2",
        "password": "staff1234",
        "display_name": "School Staff",
        "email": "staff@school.local",
        "systems": [("school", "teacher")],
    },
    {
        "username": "student2",
        "password": "student1234",
        "display_name": "School Student",
        "email": "student@school.local",
        "systems": [("school", "student")],
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
        "systems": [("college", "parent")],
    },
    {
        "username": "parent2",
        "password": "parent1234",
        "display_name": "School Parent",
        "email": "parent@school.local",
        "systems": [("school", "parent")],
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
# Only seeded when EDU_DEV_SEED=true or the database is brand-new (empty).
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
        conn.commit()

        # student_journey gained a nursery slot so all 5 systems can link.
        jcols = {
            r[1] for r in
            conn.execute("PRAGMA table_info(student_journey)").fetchall()
        }
        if jcols:  # table exists
            if "nursery_pk" not in jcols:
                conn.execute("ALTER TABLE student_journey ADD COLUMN nursery_pk INTEGER")
            if "nursery_student_id" not in jcols:
                conn.execute(
                    "ALTER TABLE student_journey ADD COLUMN nursery_student_id TEXT")
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
    from education_system.shared.auth.password_manager import verify_password
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
    """Check whether dev/demo seeding is explicitly enabled.

    Returns True **only** when ``EDU_DEV_SEED`` is set to a truthy value
    (``true``, ``1``, ``yes``, ``on``).  Default is False (opt-in).
    Fresh databases are always seeded regardless of this flag so the
    system is usable out of the box; this flag only controls re-seeding
    of *existing* databases with additional demo accounts.
    """
    val = os.environ.get("EDU_DEV_SEED", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def seed_default_users(db_path: str | None = None):
    """Create the default user accounts on first run, and ensure all system
    access records exist for existing databases that are being upgraded.

    In non-dev environments (``EDU_DEV_SEED=false``), existing databases are
    *not* re-seeded with demo accounts or security Q&A.
    """
    dev_mode = _is_dev_mode()
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        is_fresh = row["cnt"] == 0

        if is_fresh:
            # Fresh database — always create defaults so the system is usable
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
                "Change them before any production or internet-facing deployment. "
                "Set EDU_DEV_SEED=false in production to prevent re-seeding."
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
):
    """Insert a user and their system access records."""
    pw_hash = hash_password(password)
    cursor = conn.execute(
        """INSERT OR IGNORE INTO users
           (username, password_hash, display_name, email)
           VALUES (?, ?, ?, ?)""",
        (username, pw_hash, display_name, email),
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
