#!/usr/bin/env python3
"""
SSO System Database Migration

Creates tables for Single Sign-On provider configuration,
identity mapping, and SSO session tracking.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH


def run_migration(db_path=None):
    """Execute SSO system database migration."""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. SSO Providers Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sso_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id TEXT UNIQUE NOT NULL,
                provider_type TEXT NOT NULL CHECK(provider_type IN ('saml', 'oidc')),
                display_name TEXT NOT NULL,
                config_json TEXT NOT NULL,
                is_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. SSO Identities Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sso_identities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider_id TEXT NOT NULL,
                external_id TEXT NOT NULL,
                external_email TEXT,
                attributes_json TEXT,
                last_login_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (provider_id) REFERENCES sso_providers(provider_id) ON DELETE CASCADE,
                UNIQUE(provider_id, external_id)
            )
        """)

        # 3. SSO Sessions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sso_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider_id TEXT NOT NULL,
                session_index TEXT,
                access_token_hash TEXT,
                token_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (provider_id) REFERENCES sso_providers(provider_id) ON DELETE CASCADE
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sso_identities_user
            ON sso_identities(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sso_identities_provider
            ON sso_identities(provider_id, external_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sso_sessions_user
            ON sso_sessions(user_id)
        """)

        conn.commit()
        print("SSO system migration completed successfully.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()
