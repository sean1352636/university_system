#!/usr/bin/env python3
"""
Delegated Access / Power of Attorney Database Migration

Creates tables for managing delegated access permissions,
delegation requests, and audit trails.
"""

from university_system.infrastructure.database.db import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH


def run_migration(db_path=None):
    """Execute delegated access database migration."""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Delegated Access Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delegated_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grantor_user_id INTEGER NOT NULL,
                delegate_user_id INTEGER NOT NULL,
                relationship TEXT NOT NULL,
                scope_json TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                revoked_at TIMESTAMP,
                revoked_by INTEGER,
                FOREIGN KEY (grantor_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (delegate_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (revoked_by) REFERENCES users(id)
            )
        """)

        # 2. Delegated Access Requests Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delegated_access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                relationship TEXT NOT NULL,
                requested_scope_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'approved', 'rejected', 'cancelled')),
                supporting_documents TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolved_by INTEGER,
                FOREIGN KEY (requester_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (resolved_by) REFERENCES users(id)
            )
        """)

        # 3. Delegated Access Audit Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delegated_access_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                delegation_id INTEGER NOT NULL,
                delegate_user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (delegation_id) REFERENCES delegated_access(id) ON DELETE CASCADE,
                FOREIGN KEY (delegate_user_id) REFERENCES users(id),
                FOREIGN KEY (target_user_id) REFERENCES users(id)
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegated_access_grantor
            ON delegated_access(grantor_user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegated_access_delegate
            ON delegated_access(delegate_user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegated_access_active
            ON delegated_access(is_active)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegation_requests_status
            ON delegated_access_requests(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegation_audit_delegation
            ON delegated_access_audit(delegation_id)
        """)

        conn.commit()
        print("Delegated access migration completed successfully.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()
