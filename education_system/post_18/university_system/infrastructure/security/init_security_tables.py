#!/usr/bin/env python3
"""
Security Database Schema Initialization
Creates all necessary tables for security features
"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from core.paths import DEFAULT_DB_PATH
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.i18n import get_text, _

def init_security_tables(db_path=None):
    """Initialize all security-related database tables"""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = get_connection(db_path=db_path, row_factory=False)
    cursor = conn.cursor()

    try:
        # 1. Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_token TEXT UNIQUE,
                session_id_hash TEXT UNIQUE,
                ip_address TEXT,
                location TEXT,
                user_agent TEXT,
                device_fingerprint TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                terminated_at TIMESTAMP,
                termination_reason TEXT
            )
        """)

        # Add missing columns to sessions table if they don't exist
        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN session_id_hash TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN device_fingerprint TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN terminated_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN termination_reason TEXT")
        except sqlite3.OperationalError:
            pass

        # 2. Security events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                details TEXT,
                ip_address TEXT,
                event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Encrypted fields metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS encrypted_fields_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                key_id TEXT,
                encrypted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(table_name, column_name)
            )
        """)

        # 4. API keys table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                key_hash TEXT UNIQUE NOT NULL,
                key_name TEXT,
                permissions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                expires_at TIMESTAMP,
                rate_limit INTEGER DEFAULT 1000,
                is_active INTEGER DEFAULT 1
            )
        """)

        # 5. API rate limits table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL,
                identifier_type TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                request_count INTEGER DEFAULT 0,
                window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(identifier, identifier_type, endpoint)
            )
        """)

        # 6. Security incidents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT,
                detected_by INTEGER,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'open',
                resolved_at TIMESTAMP,
                resolution TEXT,
                affected_users TEXT,
                affected_resources TEXT
            )
        """)

        # 7. Incident response actions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incident_response_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                action_details TEXT,
                performed_by INTEGER,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 8. Bulk export log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bulk_export_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                export_type TEXT,
                resource_type TEXT,
                record_count INTEGER,
                status TEXT DEFAULT 'pending',
                ip_address TEXT,
                exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_by INTEGER,
                approved_at TIMESTAMP
            )
        """)

        # 9. Vulnerability scan results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vulnerability_scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_type TEXT NOT NULL,
                target TEXT,
                severity TEXT,
                vulnerable INTEGER DEFAULT 0,
                details TEXT,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fixed INTEGER DEFAULT 0,
                fixed_at TIMESTAMP
            )
        """)

        # 10. Encryption keys table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS encryption_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT UNIQUE NOT NULL,
                key_type TEXT DEFAULT 'fernet',
                encrypted_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rotated_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                version INTEGER DEFAULT 1
            )
        """)

        # 11. Password history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 12. Password policy compliance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_policy_compliance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                last_password_change TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                password_expires_at TIMESTAMP,
                must_change INTEGER DEFAULT 0
            )
        """)

        # 13. Data access log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                resource_type TEXT NOT NULL,
                resource_id INTEGER,
                action TEXT NOT NULL,
                session_id INTEGER,
                ip_address TEXT,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 14. Permission changes log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_changes_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                changed_by INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                permission_name TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 15. MFA user settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                mfa_enabled INTEGER DEFAULT 0,
                verification_disabled INTEGER DEFAULT 0,
                backup_codes_generated INTEGER DEFAULT 0,
                enforcement_deadline TIMESTAMP,
                bypass_until TIMESTAMP,
                failed_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                last_successful_verification TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 16. MFA methods table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                method_type TEXT NOT NULL CHECK(method_type IN ('totp', 'sms', 'email')),
                method_identifier TEXT,
                is_primary INTEGER DEFAULT 0,
                is_enabled INTEGER DEFAULT 1,
                setup_completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, method_type)
            )
        """)

        # 17. Session activity log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                user_id INTEGER,
                activity_type TEXT NOT NULL,
                details TEXT,
                activity_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Create indexes for better performance (with error handling)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active, last_activity)")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_events_time ON security_events(event_time)")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_events_severity ON security_events(severity, event_time)")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id, is_active)")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON security_incidents(status, detected_at)")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_access_user ON data_access_log(user_id, accessed_at)")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        print("✅ Security tables initialized successfully")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Error initializing security tables: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn.close()

if __name__ == '__main__':
    init_security_tables()
