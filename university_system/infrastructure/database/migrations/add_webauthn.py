#!/usr/bin/env python3
"""
WebAuthn/FIDO2 Database Migration

Creates tables for WebAuthn credential storage and
challenge tracking for passwordless authentication.
"""

from university_system.infrastructure.database.db import sqlite3
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
        # 1. WebAuthn Credentials Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webauthn_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                credential_id TEXT UNIQUE NOT NULL,
                public_key BLOB NOT NULL,
                sign_count INTEGER DEFAULT 0,
                credential_name TEXT DEFAULT 'Security Key',
                aaguid TEXT,
                transports TEXT,
                is_discoverable BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 2. WebAuthn Challenges Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webauthn_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge TEXT UNIQUE NOT NULL,
                session_id TEXT NOT NULL,
                challenge_type TEXT NOT NULL CHECK(challenge_type IN ('registration', 'authentication')),
                user_id INTEGER,
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
