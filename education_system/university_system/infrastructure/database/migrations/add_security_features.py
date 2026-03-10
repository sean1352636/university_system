#!/usr/bin/env python3
"""
Security Features Database Migration
Creates tables for:
- Advanced Session Management
- Security Audit & Compliance
- Encrypted Data Storage
- API Security
- Password Security
- Incident Response
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import os
import sys
from datetime import datetime

# Import centralized database path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH

def run_migration(db_path=None):
    """Execute security features database migration"""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Creating security feature tables...")

        # ========== SESSION MANAGEMENT ==========

        # 1. Sessions table - Track all user sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id_hash TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                device_fingerprint TEXT,
                location TEXT,  -- JSON: {city, country, lat, lon}
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                terminated_at TIMESTAMP,
                termination_reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 2. Session Activity Log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,  -- 'page_view', 'api_call', 'data_access', etc.
                details TEXT,  -- JSON with additional info
                activity_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # ========== SECURITY AUDIT & COMPLIANCE ==========

        # 3. Security Events - Track all security-related events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,  -- 'failed_login', 'suspicious_login', 'permission_change', etc.
                details TEXT,  -- JSON with event details
                event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                severity TEXT DEFAULT 'medium',  -- 'low', 'medium', 'high', 'critical'
                ip_address TEXT,
                resolved BOOLEAN DEFAULT 0,
                resolved_at TIMESTAMP,
                resolved_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # 4. Data Access Log - Track who accessed what data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                resource_type TEXT NOT NULL,  -- 'student', 'grade', 'health_record', etc.
                resource_id INTEGER NOT NULL,
                action TEXT NOT NULL,  -- 'view', 'edit', 'delete', 'export'
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                session_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
            )
        """)

        # 5. Permission Changes Log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_changes_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                changed_by INTEGER NOT NULL,
                target_user_id INTEGER,
                target_role_id INTEGER,
                permission_name TEXT NOT NULL,
                action TEXT NOT NULL,  -- 'granted', 'revoked'
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT,
                FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # ========== DATA ENCRYPTION ==========

        # 6. Encryption Keys - Key management
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS encryption_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT NOT NULL UNIQUE,
                key_type TEXT NOT NULL,  -- 'master', 'data', 'file'
                encrypted_key TEXT NOT NULL,  -- The key itself, encrypted
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rotated_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                version INTEGER DEFAULT 1
            )
        """)

        # 7. Encrypted Fields Metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS encrypted_fields_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                encryption_key_id TEXT NOT NULL,
                encrypted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(table_name, column_name),
                FOREIGN KEY (encryption_key_id) REFERENCES encryption_keys(key_id)
            )
        """)

        # ========== API SECURITY ==========

        # 8. API Keys
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                key_name TEXT,
                permissions TEXT,  -- JSON array of allowed endpoints
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_used_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                rate_limit INTEGER DEFAULT 1000,  -- Requests per hour
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 9. API Rate Limiting
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL,  -- user_id, api_key, or IP address
                identifier_type TEXT NOT NULL,  -- 'user', 'api_key', 'ip'
                endpoint TEXT NOT NULL,
                request_count INTEGER DEFAULT 0,
                window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(identifier, identifier_type, endpoint)
            )
        """)

        # 10. API Request Log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_request_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER,
                user_id INTEGER,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                ip_address TEXT,
                request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                response_status INTEGER,
                response_time_ms INTEGER,
                FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE SET NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # ========== PASSWORD SECURITY ==========

        # 11. Password History - Prevent password reuse
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 12. Password Policy Compliance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_policy_compliance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                last_password_change TIMESTAMP,
                password_strength_score INTEGER,  -- 0-100
                is_compromised BOOLEAN DEFAULT 0,
                compromised_check_date TIMESTAMP,
                next_rotation_due TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # ========== DATA LOSS PREVENTION ==========

        # 13. Bulk Export Log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bulk_export_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                export_type TEXT NOT NULL,  -- 'csv', 'pdf', 'excel'
                resource_type TEXT NOT NULL,
                record_count INTEGER NOT NULL,
                exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'denied', 'completed'
                approved_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # 14. Document Access Control
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_access_control (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                document_type TEXT NOT NULL,
                classification TEXT DEFAULT 'internal',  -- 'public', 'internal', 'confidential', 'restricted'
                watermark_enabled BOOLEAN DEFAULT 0,
                print_disabled BOOLEAN DEFAULT 0,
                screenshot_disabled BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(document_id, document_type)
            )
        """)

        # ========== INCIDENT RESPONSE ==========

        # 15. Security Incidents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_type TEXT NOT NULL,  -- 'data_breach', 'unauthorized_access', 'malware', etc.
                severity TEXT NOT NULL,  -- 'low', 'medium', 'high', 'critical'
                description TEXT NOT NULL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                detected_by INTEGER,
                status TEXT DEFAULT 'open',  -- 'open', 'investigating', 'contained', 'resolved'
                assigned_to INTEGER,
                resolved_at TIMESTAMP,
                resolution_notes TEXT,
                affected_users TEXT,  -- JSON array of user IDs
                affected_resources TEXT,  -- JSON array of resources
                FOREIGN KEY (detected_by) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # 16. Incident Response Actions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incident_response_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,  -- 'lockout', 'notification', 'investigation', etc.
                action_details TEXT,  -- JSON
                performed_by INTEGER NOT NULL,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                result TEXT,
                FOREIGN KEY (incident_id) REFERENCES security_incidents(id) ON DELETE CASCADE,
                FOREIGN KEY (performed_by) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # ========== VULNERABILITY SCANNING ==========

        # 17. Vulnerability Scan Results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vulnerability_scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_type TEXT NOT NULL,  -- 'sql_injection', 'xss', 'dependency', etc.
                scan_target TEXT NOT NULL,
                vulnerability_found BOOLEAN DEFAULT 0,
                severity TEXT,  -- 'low', 'medium', 'high', 'critical'
                details TEXT,  -- JSON
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fixed BOOLEAN DEFAULT 0,
                fixed_at TIMESTAMP
            )
        """)

        # 18. Dependency Vulnerabilities
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dependency_vulnerabilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT NOT NULL,
                installed_version TEXT NOT NULL,
                vulnerability_id TEXT,  -- CVE ID
                severity TEXT NOT NULL,
                description TEXT,
                fixed_version TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                patched BOOLEAN DEFAULT 0,
                patched_at TIMESTAMP
            )
        """)

        # Create indexes for performance
        print("Creating indexes...")

        # Session indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active, expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_activity_user ON session_activity_log(user_id)")

        # Security event indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_events_user ON security_events(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_events_time ON security_events(event_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_events_type ON security_events(event_type)")

        # Data access indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_access_user ON data_access_log(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_access_resource ON data_access_log(resource_type, resource_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_access_time ON data_access_log(accessed_at)")

        # API indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_rate_limits_identifier ON api_rate_limits(identifier, identifier_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_requests_time ON api_request_log(request_time)")

        # Password indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_history_user ON password_history(user_id)")

        # Incident indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON security_incidents(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_severity ON security_incidents(severity)")

        conn.commit()
        print("✓ Security feature tables created successfully")

        # Print summary
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'sessions', 'session_activity_log', 'security_events',
                'data_access_log', 'permission_changes_log', 'encryption_keys',
                'encrypted_fields_metadata', 'api_keys', 'api_rate_limits',
                'api_request_log', 'password_history', 'password_policy_compliance',
                'bulk_export_log', 'document_access_control', 'security_incidents',
                'incident_response_actions', 'vulnerability_scan_results',
                'dependency_vulnerabilities'
            )
        """)
        tables = cursor.fetchall()
        print(f"\n✓ Created {len(tables)} security tables:")
        for table in tables:
            print(f"  - {table[0]}")

        print("\n✓ Indexes created for performance optimization")
        print("\n✓ Migration completed successfully!")

        return True

    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    success = run_migration(db_path)
    sys.exit(0 if success else 1)
