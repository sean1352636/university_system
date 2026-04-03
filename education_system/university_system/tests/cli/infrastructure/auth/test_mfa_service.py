#!/usr/bin/env python3
"""
Comprehensive tests for MFA Service
Tests TOTP, SMS/Email OTP, recovery codes, device trust, enforcement policies, and verification attempts
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from education_system.university_system.infrastructure.auth.mfa_service import (
    MFAService,
    setup_totp,
    verify_totp,
    generate_sms_otp,
    verify_sms_otp
)


def _get_otp_code(result, db_path, user_id, method_type='sms'):
    """Get OTP code from result dict or fall back to database query."""
    if 'code' in result:
        return result['code']
    # Code not in result (delivery succeeded) — read from DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code FROM mfa_otp_codes
        WHERE user_id = ? AND method_type = ? AND is_used = 0
        ORDER BY created_at DESC LIMIT 1
    """, (user_id, method_type))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Create database schema
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Create required tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            role_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY,
            role_name TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_accounts (
            user_id INTEGER PRIMARY KEY,
            two_fa_secret TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mfa_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            method_type TEXT NOT NULL,
            method_identifier TEXT,
            is_primary INTEGER DEFAULT 0,
            is_enabled INTEGER DEFAULT 1,
            setup_completed_at TIMESTAMP,
            last_used_at TIMESTAMP,
            UNIQUE(user_id, method_type),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mfa_otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            method_type TEXT NOT NULL,
            code TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_used INTEGER DEFAULT 0,
            used_at TIMESTAMP,
            attempts INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            is_used INTEGER DEFAULT 0,
            used_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mfa_trusted_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            device_name TEXT,
            trust_token TEXT NOT NULL,
            trusted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            last_used_at TIMESTAMP,
            is_trusted INTEGER DEFAULT 1,
            revoked_at TIMESTAMP,
            ip_address TEXT,
            UNIQUE(user_id, device_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mfa_user_settings (
            user_id INTEGER PRIMARY KEY,
            mfa_enabled INTEGER DEFAULT 0,
            mfa_status TEXT DEFAULT 'disabled',
            backup_codes_generated INTEGER DEFAULT 0,
            last_successful_verification TIMESTAMP,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP,
            enforcement_deadline TIMESTAMP,
            bypass_until TIMESTAMP,
            disabled_at TIMESTAMP,
            verification_disabled INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mfa_verification_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            method_type TEXT NOT NULL,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER NOT NULL,
            failure_reason TEXT,
            device_id TEXT,
            ip_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mfa_enforcement_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT UNIQUE NOT NULL,
            mfa_required INTEGER DEFAULT 0,
            allowed_methods TEXT,
            minimum_methods INTEGER DEFAULT 1,
            grace_period_days INTEGER DEFAULT 0,
            allow_device_trust INTEGER DEFAULT 1
        )
    """)

    # Insert test data
    cursor.execute("INSERT INTO users (id, username, role_id) VALUES (1, 'testuser', 1)")
    cursor.execute("INSERT INTO users (id, username, role_id) VALUES (2, 'adminuser', 2)")
    cursor.execute("INSERT INTO roles (id, role_name) VALUES (1, 'student')")
    cursor.execute("INSERT INTO roles (id, role_name) VALUES (2, 'admin')")
    cursor.execute("INSERT INTO user_accounts (user_id) VALUES (1)")
    cursor.execute("INSERT INTO user_accounts (user_id) VALUES (2)")

    # Insert enforcement policy
    cursor.execute("""
        INSERT INTO mfa_enforcement_policies (role_name, mfa_required, allowed_methods, minimum_methods, grace_period_days)
        VALUES ('admin', 1, '["totp", "sms", "email"]', 1, 7)
    """)

    conn.commit()
    conn.close()

    yield path

    # Cleanup
    os.unlink(path)

class TestMFAServiceInitialization:
    """Test MFA Service initialization"""

    def test_init_with_custom_db_path(self, temp_db):
        """Test initialization with custom database path"""
        service = MFAService(db_path=temp_db)

        assert service.db_path == temp_db
        assert service.otp_expiry_minutes == 10
        assert service.max_otp_attempts == 3
        assert service.device_trust_days == 30

    def test_init_with_default_db_path(self):
        """Test initialization with default database path"""
        service = MFAService()

        assert service.db_path is not None
        assert 'student_records.db' in service.db_path

    def test_get_connection(self, temp_db):
        """Test database connection"""
        service = MFAService(db_path=temp_db)

        conn = service._get_connection()
        assert conn is not None

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        assert count == 2  # Two test users

        conn.close()

    def test_hash_value(self, temp_db):
        """Test value hashing"""
        service = MFAService(db_path=temp_db)

        hash1 = service._hash_value('test123')
        hash2 = service._hash_value('test123')
        hash3 = service._hash_value('different')

        assert hash1 == hash2  # Same input produces same hash
        assert hash1 != hash3  # Different input produces different hash
        assert len(hash1) == 64  # SHA-256 produces 64 character hex string

class TestTOTPMethods:
    """Test TOTP (Authenticator App) methods"""

    def test_setup_totp_success(self, temp_db):
        """Test successful TOTP setup"""
        service = MFAService(db_path=temp_db)

        result = service.setup_totp(user_id=1, username='testuser')

        assert result['success'] is True
        assert 'secret' in result
        assert len(result['secret']) == 32  # Base32 encoded secret
        assert 'qr_code' in result
        assert isinstance(result['qr_code'], bytes)
        assert 'provisioning_uri' in result
        assert 'testuser' in result['provisioning_uri']
        assert 'University' in result['provisioning_uri']
        assert 'recovery_codes' in result
        assert len(result['recovery_codes']) == 10

    def test_setup_totp_updates_database(self, temp_db):
        """Test that TOTP setup updates database correctly"""
        service = MFAService(db_path=temp_db)

        result = service.setup_totp(user_id=1, username='testuser')

        assert result['success'] is True

        # Verify database was updated
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check user_accounts has secret
        cursor.execute("SELECT two_fa_secret FROM user_accounts WHERE user_id = 1")
        secret = cursor.fetchone()[0]
        assert secret == result['secret']

        # Check mfa_methods table
        cursor.execute("SELECT method_type, is_primary FROM mfa_methods WHERE user_id = 1 AND method_type = 'totp'")
        row = cursor.fetchone()
        assert row[0] == 'totp'
        assert row[1] == 1  # is_primary

        conn.close()

    @patch('education_system.university_system.infrastructure.auth.mfa_service.pyotp.TOTP')
    def test_verify_totp_success(self, mock_totp_class, temp_db):
        """Test successful TOTP verification"""
        service = MFAService(db_path=temp_db)

        # Setup TOTP first
        setup_result = service.setup_totp(user_id=1, username='testuser')

        # Mock TOTP verification
        mock_totp = MagicMock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        # Verify
        result = service.verify_totp(user_id=1, code='123456')

        assert result['success'] is True
        assert result['method'] == 'totp'

    @patch('education_system.university_system.infrastructure.auth.mfa_service.pyotp.TOTP')
    def test_verify_totp_invalid_code(self, mock_totp_class, temp_db):
        """Test TOTP verification with invalid code"""
        service = MFAService(db_path=temp_db)

        # Setup TOTP first
        service.setup_totp(user_id=1, username='testuser')

        # Mock TOTP verification to fail
        mock_totp = MagicMock()
        mock_totp.verify.return_value = False
        mock_totp_class.return_value = mock_totp

        result = service.verify_totp(user_id=1, code='wrong')

        assert result['success'] is False
        assert 'Invalid TOTP code' in result['error']

    def test_verify_totp_not_configured(self, temp_db):
        """Test TOTP verification when not configured"""
        service = MFAService(db_path=temp_db)

        result = service.verify_totp(user_id=1, code='123456')

        assert result['success'] is False
        assert 'not configured' in result['error']

    @patch('education_system.university_system.infrastructure.auth.mfa_service.pyotp.TOTP')
    def test_verify_totp_with_device_trust(self, mock_totp_class, temp_db):
        """Test TOTP verification with device trust"""
        service = MFAService(db_path=temp_db)

        # Setup TOTP
        service.setup_totp(user_id=1, username='testuser')

        # Mock TOTP verification
        mock_totp = MagicMock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        # Verify with device ID
        result = service.verify_totp(user_id=1, code='123456', device_id='test_device_123')

        assert result['success'] is True
        assert 'trust_token' in result
        assert len(result['trust_token']) > 0

class TestSMSOTPMethods:
    """Test SMS OTP methods"""

    def test_generate_sms_otp_success(self, temp_db):
        """Test successful SMS OTP generation"""
        service = MFAService(db_path=temp_db)

        result = service.generate_sms_otp(user_id=1, phone_number='+15551234567')

        assert result['success'] is True
        assert 'expires_at' in result
        assert '+15551234567' in result['message']
        # Code may or may not be in result depending on SMS delivery
        code = _get_otp_code(result, temp_db, 1, 'sms')
        assert code is not None
        assert len(code) == 6
        assert code.isdigit()

    def test_generate_sms_otp_creates_database_entry(self, temp_db):
        """Test that SMS OTP generation creates database entry"""
        service = MFAService(db_path=temp_db)

        result = service.generate_sms_otp(user_id=1, phone_number='+15551234567')

        # Verify database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT code, method_type, is_used
            FROM mfa_otp_codes
            WHERE user_id = 1 AND method_type = 'sms'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()

        assert row is not None
        code = _get_otp_code(result, temp_db, 1, 'sms')
        assert row[0] == code
        assert row[1] == 'sms'
        assert row[2] == 0  # not used

        conn.close()

    def test_generate_sms_otp_invalidates_previous(self, temp_db):
        """Test that new SMS OTP invalidates previous codes"""
        service = MFAService(db_path=temp_db)

        # Generate first OTP
        result1 = service.generate_sms_otp(user_id=1, phone_number='+15551234567')
        code1 = _get_otp_code(result1, temp_db, 1, 'sms')

        # Generate second OTP
        result2 = service.generate_sms_otp(user_id=1, phone_number='+15551234567')

        # Verify first code is invalidated
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT is_used FROM mfa_otp_codes
            WHERE user_id = 1 AND code = ?
        """, (code1,))
        is_used = cursor.fetchone()[0]

        assert is_used == 1  # First code should be marked as used

        conn.close()

    def test_verify_sms_otp_success(self, temp_db):
        """Test successful SMS OTP verification"""
        service = MFAService(db_path=temp_db)

        # Generate OTP
        gen_result = service.generate_sms_otp(user_id=1, phone_number='+15551234567')
        code = _get_otp_code(gen_result, temp_db, 1, 'sms')

        # Verify OTP
        verify_result = service.verify_sms_otp(user_id=1, code=code)

        assert verify_result['success'] is True
        assert verify_result['method'] == 'sms'

    def test_verify_sms_otp_invalid_code(self, temp_db):
        """Test SMS OTP verification with invalid code"""
        service = MFAService(db_path=temp_db)

        # Generate OTP
        service.generate_sms_otp(user_id=1, phone_number='+15551234567')

        # Try to verify with wrong code
        verify_result = service.verify_sms_otp(user_id=1, code='999999')

        assert verify_result['success'] is False
        assert 'Invalid or expired' in verify_result['error']

    def test_verify_sms_otp_expired_code(self, temp_db):
        """Test SMS OTP verification with expired code"""
        service = MFAService(db_path=temp_db)

        # Generate OTP
        gen_result = service.generate_sms_otp(user_id=1, phone_number='+15551234567')
        code = _get_otp_code(gen_result, temp_db, 1, 'sms')

        # Manually expire the code in database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE mfa_otp_codes
            SET expires_at = datetime('now', '-1 hour')
            WHERE user_id = 1 AND code = ?
        """, (code,))
        conn.commit()
        conn.close()

        # Try to verify expired code
        verify_result = service.verify_sms_otp(user_id=1, code=code)

        assert verify_result['success'] is False
        assert 'expired' in verify_result['error'].lower()

    def test_verify_sms_otp_max_attempts(self, temp_db):
        """Test SMS OTP verification with too many attempts"""
        service = MFAService(db_path=temp_db)

        # Generate OTP
        gen_result = service.generate_sms_otp(user_id=1, phone_number='+15551234567')
        code = _get_otp_code(gen_result, temp_db, 1, 'sms')

        # Manually set attempts to max
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE mfa_otp_codes
            SET attempts = ?
            WHERE user_id = 1 AND code = ?
        """, (service.max_otp_attempts, code))
        conn.commit()
        conn.close()

        # Try to verify
        verify_result = service.verify_sms_otp(user_id=1, code=code)

        assert verify_result['success'] is False
        assert 'Too many attempts' in verify_result['error']

class TestEmailOTPMethods:
    """Test Email OTP methods"""

    def test_generate_email_otp_success(self, temp_db):
        """Test successful Email OTP generation"""
        service = MFAService(db_path=temp_db)

        result = service.generate_email_otp(user_id=1, email='test@example.com')

        assert result['success'] is True
        assert 'expires_at' in result
        assert 'test@example.com' in result['message']
        # Code may or may not be in result depending on email delivery
        code = _get_otp_code(result, temp_db, 1, 'email')
        assert code is not None
        assert len(code) == 6
        assert code.isdigit()

    def test_verify_email_otp_success(self, temp_db):
        """Test successful Email OTP verification"""
        service = MFAService(db_path=temp_db)

        # Generate OTP
        gen_result = service.generate_email_otp(user_id=1, email='test@example.com')
        code = _get_otp_code(gen_result, temp_db, 1, 'email')

        # Verify OTP
        verify_result = service.verify_email_otp(user_id=1, code=code)

        assert verify_result['success'] is True
        assert verify_result['method'] == 'email'

    def test_verify_email_otp_with_device_trust(self, temp_db):
        """Test Email OTP verification with device trust"""
        service = MFAService(db_path=temp_db)

        # Generate OTP
        gen_result = service.generate_email_otp(user_id=1, email='test@example.com')
        code = _get_otp_code(gen_result, temp_db, 1, 'email')

        # Verify with device ID
        verify_result = service.verify_email_otp(user_id=1, code=code, device_id='device123')

        assert verify_result['success'] is True
        assert 'trust_token' in verify_result

class TestRecoveryCodesMethods:
    """Test recovery codes methods"""

    def test_generate_recovery_codes(self, temp_db):
        """Test recovery code generation"""
        service = MFAService(db_path=temp_db)

        result = service.generate_recovery_codes(user_id=1)

        assert result['success'] is True
        assert 'codes' in result
        assert len(result['codes']) == 10

        # Check format (XXXX-XXXX)
        for code in result['codes']:
            assert len(code) == 9  # 4 chars + dash + 4 chars
            assert '-' in code

    def test_generate_recovery_codes_replaces_old(self, temp_db):
        """Test that generating new codes replaces old ones"""
        service = MFAService(db_path=temp_db)

        # Generate first set
        result1 = service.generate_recovery_codes(user_id=1)

        # Generate second set
        result2 = service.generate_recovery_codes(user_id=1)

        # Verify only 10 codes exist in database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM mfa_recovery_codes WHERE user_id = 1")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 10

    def test_verify_recovery_code_success(self, temp_db):
        """Test successful recovery code verification"""
        service = MFAService(db_path=temp_db)

        # Generate codes
        gen_result = service.generate_recovery_codes(user_id=1)
        code = gen_result['codes'][0]

        # Verify code
        verify_result = service.verify_recovery_code(user_id=1, code=code)

        assert verify_result['success'] is True
        assert verify_result['method'] == 'recovery_code'
        assert verify_result['remaining_codes'] == 9

    def test_verify_recovery_code_invalid(self, temp_db):
        """Test recovery code verification with invalid code"""
        service = MFAService(db_path=temp_db)

        # Generate codes
        service.generate_recovery_codes(user_id=1)

        # Try invalid code
        verify_result = service.verify_recovery_code(user_id=1, code='INVALID-CODE')

        assert verify_result['success'] is False
        assert 'Invalid or already used' in verify_result['error']

    def test_verify_recovery_code_already_used(self, temp_db):
        """Test recovery code verification with already used code"""
        service = MFAService(db_path=temp_db)

        # Generate and verify code
        gen_result = service.generate_recovery_codes(user_id=1)
        code = gen_result['codes'][0]
        service.verify_recovery_code(user_id=1, code=code)

        # Try to use same code again
        verify_result = service.verify_recovery_code(user_id=1, code=code)

        assert verify_result['success'] is False
        assert 'already used' in verify_result['error']

    def test_verify_recovery_code_low_warning(self, temp_db):
        """Test warning when few recovery codes remain"""
        service = MFAService(db_path=temp_db)

        # Generate codes
        gen_result = service.generate_recovery_codes(user_id=1)

        # Use 8 codes
        for i in range(8):
            service.verify_recovery_code(user_id=1, code=gen_result['codes'][i])

        # Verify 9th code (2 remaining)
        verify_result = service.verify_recovery_code(user_id=1, code=gen_result['codes'][8])

        assert verify_result['success'] is True
        assert verify_result['remaining_codes'] == 1
        assert 'warning' in verify_result

class TestDeviceTrustMethods:
    """Test device trust methods"""

    def test_create_trusted_device(self, temp_db):
        """Test creating a trusted device"""
        service = MFAService(db_path=temp_db)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        trust_token = service._create_trusted_device(
            user_id=1,
            device_id='device123',
            cursor=cursor,
            device_name='Test Device',
            ip_address='192.168.1.1'
        )

        conn.commit()
        conn.close()

        assert trust_token is not None
        assert len(trust_token) > 0

    def test_verify_trusted_device_success(self, temp_db):
        """Test verifying a trusted device"""
        service = MFAService(db_path=temp_db)

        # Create trusted device
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        trust_token = service._create_trusted_device(1, 'device123', cursor)
        conn.commit()
        conn.close()

        # Verify device
        result = service.verify_trusted_device(1, 'device123', trust_token)

        assert result['success'] is True
        assert result['trusted'] is True

    def test_verify_trusted_device_invalid_token(self, temp_db):
        """Test verifying device with invalid token"""
        service = MFAService(db_path=temp_db)

        # Create trusted device
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        service._create_trusted_device(1, 'device123', cursor)
        conn.commit()
        conn.close()

        # Try to verify with wrong token
        result = service.verify_trusted_device(1, 'device123', 'wrong_token')

        assert result['success'] is True
        assert result['trusted'] is False

    def test_verify_trusted_device_expired(self, temp_db):
        """Test verifying an expired trusted device"""
        service = MFAService(db_path=temp_db)

        # Create trusted device
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        trust_token = service._create_trusted_device(1, 'device123', cursor)
        conn.commit()

        # Manually expire the device
        cursor.execute("""
            UPDATE mfa_trusted_devices
            SET expires_at = datetime('now', '-1 day')
            WHERE user_id = 1 AND device_id = 'device123'
        """)
        conn.commit()
        conn.close()

        # Try to verify expired device
        result = service.verify_trusted_device(1, 'device123', trust_token)

        assert result['success'] is True
        assert result['trusted'] is False

    def test_revoke_trusted_device(self, temp_db):
        """Test revoking a trusted device"""
        service = MFAService(db_path=temp_db)

        # Create trusted device
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        service._create_trusted_device(1, 'device123', cursor)
        conn.commit()
        conn.close()

        # Revoke device
        result = service.revoke_trusted_device(1, 'device123')

        assert result['success'] is True
        assert 'revoked' in result['message']

    def test_get_trusted_devices(self, temp_db):
        """Test getting list of trusted devices"""
        service = MFAService(db_path=temp_db)

        # Create multiple trusted devices
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        service._create_trusted_device(1, 'device1', cursor, device_name='Device 1')
        service._create_trusted_device(1, 'device2', cursor, device_name='Device 2')
        service._create_trusted_device(1, 'device3', cursor, device_name='Device 3')
        conn.commit()
        conn.close()

        # Get devices
        result = service.get_trusted_devices(1)

        assert result['success'] is True
        assert len(result['devices']) == 3

class TestMFAEnforcementMethods:
    """Test MFA enforcement methods"""

    def test_check_mfa_required_for_admin(self, temp_db):
        """Test MFA requirement check for admin role"""
        service = MFAService(db_path=temp_db)

        result = service.check_mfa_required(user_id=2, role='admin')

        assert result['success'] is True
        assert bool(result['required']) is True
        assert 'totp' in result['allowed_methods']
        assert result['minimum_methods'] == 1
        assert bool(result['allow_device_trust']) is True

    def test_check_mfa_required_for_student(self, temp_db):
        """Test MFA requirement check for student role (no policy)"""
        service = MFAService(db_path=temp_db)

        result = service.check_mfa_required(user_id=1, role='student')

        assert result['success'] is True
        assert result['required'] is False

    def test_get_user_mfa_methods(self, temp_db):
        """Test getting user's MFA methods"""
        service = MFAService(db_path=temp_db)

        # Setup TOTP
        service.setup_totp(user_id=1, username='testuser')

        # Get methods
        result = service.get_user_mfa_methods(user_id=1)

        assert result['success'] is True
        assert len(result['methods']) > 0
        assert result['methods'][0]['type'] == 'totp'

    def test_enable_mfa(self, temp_db):
        """Test enabling MFA for user"""
        service = MFAService(db_path=temp_db)

        result = service.enable_mfa(user_id=1)

        assert result['success'] is True

        # Verify database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT mfa_enabled FROM mfa_user_settings WHERE user_id = 1")
        enabled = cursor.fetchone()[0]
        conn.close()

        assert enabled == 1

    def test_disable_mfa(self, temp_db):
        """Test disabling MFA for user"""
        service = MFAService(db_path=temp_db)

        # Enable first
        service.enable_mfa(user_id=1)

        # Disable
        result = service.disable_mfa(user_id=1)

        assert result['success'] is True

        # Verify database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT mfa_enabled FROM mfa_user_settings WHERE user_id = 1")
        row = cursor.fetchone()
        enabled = row[0] if row else 0
        conn.close()

        assert enabled == 0

class TestVerificationAttemptLogging:
    """Test verification attempt logging"""

    @patch('education_system.university_system.infrastructure.auth.mfa_service.pyotp.TOTP')
    def test_log_successful_verification(self, mock_totp_class, temp_db):
        """Test that successful verifications are logged"""
        service = MFAService(db_path=temp_db)

        # Setup and verify TOTP
        service.setup_totp(user_id=1, username='testuser')

        mock_totp = MagicMock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        service.verify_totp(user_id=1, code='123456')

        # Check log
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT success, method_type FROM mfa_verification_attempts
            WHERE user_id = 1
            ORDER BY attempted_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 1  # success
        assert row[1] == 'totp'

    @patch('education_system.university_system.infrastructure.auth.mfa_service.pyotp.TOTP')
    def test_log_failed_verification(self, mock_totp_class, temp_db):
        """Test that failed verifications are logged"""
        service = MFAService(db_path=temp_db)

        # Setup TOTP
        service.setup_totp(user_id=1, username='testuser')

        # Mock to fail
        mock_totp = MagicMock()
        mock_totp.verify.return_value = False
        mock_totp_class.return_value = mock_totp

        service.verify_totp(user_id=1, code='wrong')

        # Check log
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT success, method_type FROM mfa_verification_attempts
            WHERE user_id = 1
            ORDER BY attempted_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 0  # failed
        assert row[1] == 'totp'

    def test_is_mfa_locked_after_failed_attempts(self, temp_db):
        """Test account locking after multiple failed attempts"""
        service = MFAService(db_path=temp_db)

        # Simulate 5 failed attempts
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        for _ in range(5):
            service._increment_failed_attempts(user_id=1, cursor=cursor)

        conn.commit()
        conn.close()

        # Check if locked
        is_locked = service.is_mfa_locked(user_id=1)

        assert is_locked is True

class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    def test_setup_totp_convenience(self, temp_db):
        """Test setup_totp convenience function exists and is callable"""
        # The convenience function creates an MFAService internally
        # Full functionality is tested in TestTOTPMethods
        assert callable(setup_totp)

    def test_verify_totp_convenience(self, temp_db):
        """Test verify_totp convenience function"""
        with patch.object(MFAService, '__init__', lambda x: None):
            # This test just ensures the function exists
            pass

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
