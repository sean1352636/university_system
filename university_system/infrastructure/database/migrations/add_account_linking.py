#!/usr/bin/env python3
"""
Account Linking Database Migration

Creates tables for linking multiple user accounts together and
tracking active role switches between linked accounts.
"""

from university_system.infrastructure.database.db import sqlite3
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH


def run_migration(db_path=None):
    """Execute account linking database migration."""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Linked Accounts Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS linked_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                primary_user_id INTEGER NOT NULL,
                secondary_user_id INTEGER NOT NULL,
                linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                linked_by INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (primary_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (secondary_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_by) REFERENCES users(id),
                UNIQUE(primary_user_id, secondary_user_id)
            )
        """)

        # 2. Account Link Requests Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_link_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requesting_user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'approved', 'rejected', 'cancelled')),
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolved_by INTEGER,
                FOREIGN KEY (requesting_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (resolved_by) REFERENCES users(id)
            )
        """)

        # 3. Active Role Switches Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_role_switches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_role TEXT NOT NULL,
                switched_to_role TEXT NOT NULL,
                linked_account_id INTEGER NOT NULL,
                switched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reverted_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_account_id) REFERENCES linked_accounts(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_linked_accounts_primary
            ON linked_accounts(primary_user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_linked_accounts_secondary
            ON linked_accounts(secondary_user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_link_requests_status
            ON account_link_requests(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_role_switches_user
            ON active_role_switches(user_id)
        """)

        conn.commit()
        print("Account linking migration completed successfully.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()
