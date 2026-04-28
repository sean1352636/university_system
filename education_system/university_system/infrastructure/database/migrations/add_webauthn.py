#!/usr/bin/env python3
"""
WebAuthn/FIDO2 Database Migration

Creates tables for WebAuthn credential storage and
challenge tracking for passwordless authentication.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH


def run_migration(db_path=None):
    """Execute WebAuthn database migration."""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. WebAuthn Credentials Table — must match the canonical
        # definition in infrastructure/auth/webauthn_service.py.
        # Runtime callers (webauthn_service + webauthn_manager) use
        # `device_name` not `credential_name`, and store `user_id` as
        # TEXT (not INTEGER), so this migration was previously
        # creating a table that the runtime code couldn't read from.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webauthn_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credential_id TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                public_key BLOB NOT NULL,
                sign_count INTEGER DEFAULT 0,
                device_name TEXT DEFAULT 'Security Key',
                transports TEXT DEFAULT '[]',
                aaguid TEXT,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                attestation_format TEXT,
                credential_type TEXT DEFAULT 'public-key',
                backup_eligible INTEGER DEFAULT 0,
                backup_state INTEGER DEFAULT 0
            )
        """)

        # 2. WebAuthn Challenges Table — matches webauthn_service.py.
        # The runtime expects columns `consumed`, `consumed_at`, and
        # an explicit `created_at TEXT NOT NULL` rather than the
        # earlier `is_used` / TIMESTAMP defaults.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webauthn_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                challenge TEXT NOT NULL,
                challenge_type TEXT NOT NULL,
                user_id TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed INTEGER DEFAULT 0,
                consumed_at TEXT
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webauthn_creds_user
            ON webauthn_credentials(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webauthn_challenges_session
            ON webauthn_challenges(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webauthn_challenges_expires
            ON webauthn_challenges(expires_at)
        """)

        conn.commit()
        print("WebAuthn migration completed successfully.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()
