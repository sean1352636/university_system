#!/usr/bin/env python3
"""
Multi-Factor Authentication (MFA) Database Migration
Creates comprehensive MFA system tables for:
- SMS/Email OTP verification
- Device trust management
- MFA enforcement policies per role
- Recovery codes
"""

import sqlite3
import os
import sys
from datetime import datetime

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH

def run_migration(db_path=None):
    """Execute MFA system database migration"""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. MFA Methods Table - Tracks enabled MFA methods per user
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                method_type TEXT NOT NULL CHECK(method_type IN ('totp', 'sms', 'email')),
                method_identifier TEXT,  -- Phone number for SMS, email address for email
                is_primary BOOLEAN DEFAULT 0,
                is_enabled BOOLEAN DEFAULT 1,
                setup_completed_at TIMESTAMP,
                last_used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, method_type)
            )
        """)

        # 2. OTP Codes Table - Stores active OTP codes for SMS/Email
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_otp_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                method_type TEXT NOT NULL CHECK(method_type IN ('sms', 'email')),
                code TEXT NOT NULL,
                code_hash TEXT NOT NULL,  -- Hashed version for secure comparison
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                used_at TIMESTAMP,
                attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 3. Trusted Devices Table - Device trust/remember functionality
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_trusted_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,  -- Unique device identifier
                device_name TEXT,
                device_fingerprint TEXT,  -- Browser/OS fingerprint
                ip_address TEXT,
                trust_token TEXT NOT NULL UNIQUE,  -- Secure token for verification
                is_trusted BOOLEAN DEFAULT 1,
                trusted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,  -- Trust expiration (default 30 days)
                last_used_at TIMESTAMP,
                revoked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, device_id)
            )
        """)

        # 4. MFA Enforcement Policies Table - Per-role MFA requirements
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_enforcement_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE,
                mfa_required BOOLEAN DEFAULT 0,
                allowed_methods TEXT,  -- JSON array: ["totp", "sms", "email"]
                minimum_methods INTEGER DEFAULT 1,  -- Require at least N methods
                grace_period_days INTEGER DEFAULT 7,  -- Days to enable MFA after enforcement
                enforce_on_login BOOLEAN DEFAULT 1,
                enforce_on_sensitive_actions BOOLEAN DEFAULT 1,
                allow_device_trust BOOLEAN DEFAULT 1,
                device_trust_duration_days INTEGER DEFAULT 30,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. MFA User Settings Table - Per-user MFA configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                mfa_enabled BOOLEAN DEFAULT 0,
                verification_disabled BOOLEAN DEFAULT 0,  -- Disable all verification (password only)
                backup_codes_generated BOOLEAN DEFAULT 0,
                enforcement_deadline TIMESTAMP,  -- Deadline to enable MFA if required
                bypass_until TIMESTAMP,  -- Temporary MFA bypass
                failed_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                last_successful_verification TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Add verification_disabled column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE mfa_user_settings ADD COLUMN verification_disabled BOOLEAN DEFAULT 0")
        except Exception:
            pass  # Column already exists

        # Add mfa_status column (active/disabled) if it doesn't exist
        try:
            cursor.execute("ALTER TABLE mfa_user_settings ADD COLUMN mfa_status TEXT DEFAULT 'disabled' CHECK(mfa_status IN ('active', 'disabled'))")
        except Exception:
            pass  # Column already exists

        # Add disabled_at timestamp to track when MFA was disabled (for 90-day cleanup)
        try:
            cursor.execute("ALTER TABLE mfa_user_settings ADD COLUMN disabled_at TIMESTAMP")
        except Exception:
            pass  # Column already exists

        # 6. MFA Verification Attempts Table - Audit trail
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_verification_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                method_type TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                failure_reason TEXT,
                ip_address TEXT,
                user_agent TEXT,
                device_id TEXT,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 7. Enhanced Recovery Codes Table (extend existing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,  -- Hashed recovery code
                is_used BOOLEAN DEFAULT 0,
                used_at TIMESTAMP,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,  -- Optional expiration
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mfa_methods_user ON mfa_methods(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mfa_otp_user_expires ON mfa_otp_codes(user_id, expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mfa_trusted_devices_user ON mfa_trusted_devices(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mfa_trusted_devices_token ON mfa_trusted_devices(trust_token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mfa_user_settings_user ON mfa_user_settings(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mfa_attempts_user ON mfa_verification_attempts(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mfa_recovery_user ON mfa_recovery_codes(user_id)")

        # Insert default MFA enforcement policies for all roles
        default_policies = [
            # Admin - Strict MFA required
            ('admin', 1, '["totp", "sms", "email"]', 2, 3, 1, 1, 1, 30),
            # Staff - MFA recommended
            ('staff', 1, '["totp", "sms", "email"]', 1, 7, 1, 1, 1, 30),
            # Instructor - MFA recommended for grading
            ('instructor', 0, '["totp", "sms", "email"]', 1, 14, 1, 1, 1, 30),
            # Student - Optional MFA
            ('student', 0, '["totp", "email"]', 1, 30, 0, 0, 1, 90),
            # Parent - Optional MFA
            ('parent', 0, '["totp", "email"]', 1, 30, 0, 0, 1, 90),
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO mfa_enforcement_policies
            (role_name, mfa_required, allowed_methods, minimum_methods,
             grace_period_days, enforce_on_login, enforce_on_sensitive_actions,
             allow_device_trust, device_trust_duration_days)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_policies)

        conn.commit()
        print("✓ MFA system tables created successfully")
        print("✓ Default MFA enforcement policies added")
        print("✓ Indexes created for performance optimization")

        # Print summary
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mfa_%'")
        tables = cursor.fetchall()
        print(f"\n✓ Created {len(tables)} MFA tables:")
        for table in tables:
            print(f"  - {table[0]}")

        return True

    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    success = run_migration(db_path)
    sys.exit(0 if success else 1)
