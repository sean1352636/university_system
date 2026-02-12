#!/usr/bin/env python3
"""
Biometric Authentication Database Migration

Creates tables for biometric enrollment storage and
authentication attempt logging.
"""

from university_system.infrastructure.database.db import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH


def run_migration(db_path=None):
    """Execute biometric authentication database migration."""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Biometric Enrollments Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS biometric_enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                biometric_type TEXT NOT NULL CHECK(biometric_type IN ('face', 'fingerprint')),
                template_data BLOB NOT NULL,
                template_hash TEXT NOT NULL,
                quality_score REAL DEFAULT 0.0,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, biometric_type)
            )
        """)

        # 2. Biometric Auth Log Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS biometric_auth_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                biometric_type TEXT NOT NULL,
                match_score REAL,
                success BOOLEAN NOT NULL,
                device_info TEXT,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_biometric_enrollments_user
            ON biometric_enrollments(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_biometric_auth_log_user
            ON biometric_auth_log(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_biometric_auth_log_time
            ON biometric_auth_log(attempted_at)
        """)

        conn.commit()
        print("Biometric authentication migration completed successfully.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()
