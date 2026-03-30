"""Schema initialisation and seed data for the shared auth database."""

import logging

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
    password_changed_at TEXT
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
"""

# ── Default account definitions ──────────────────────────────────────────────
#
# ⚠  WARNING — DEV/DEMO ONLY ⚠
# These passwords are intentionally weak for local development and demos.
# They MUST be changed before any production or internet-facing deployment.
# Consider using environment variables or a secrets manager in production.
#
# 13 accounts total:
#   1  Super Admin   — all 4 systems as admin
#   4  Admins        — 1 per system (admin/admin1/admin2/admin3)
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


def initialise_auth_db(db_path: str | None = None):
    """Create the auth tables if they don't already exist."""
    conn = connect(db_path)
    try:
        conn.executescript(_TABLES_SQL)
        conn.commit()

        # Add legacy_salt column to existing databases (migration)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "legacy_salt" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN legacy_salt TEXT")
            conn.commit()

        logger.info("Auth database initialised")
    finally:
        conn.close()


def seed_default_users(db_path: str | None = None):
    """Create the default user accounts on first run, and ensure all system
    access records exist for existing databases that are being upgraded."""
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        if row["cnt"] == 0:
            # Fresh database — create everything
            for acct in _DEFAULT_ACCOUNTS:
                _create_default_user(
                    conn,
                    username=acct["username"],
                    password=acct["password"],
                    display_name=acct["display_name"],
                    email=acct["email"],
                    systems=acct["systems"],
                )
            conn.commit()
            logger.info("Seeded %d default auth accounts", len(_DEFAULT_ACCOUNTS))
            logger.warning(
                "Default accounts use WEAK passwords (e.g. admin123, staff1234). "
                "Change them before any production or internet-facing deployment."
            )
        else:
            # Existing database — ensure new accounts and system access exist
            _ensure_default_accounts(conn)
            conn.commit()
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
