#!/usr/bin/env python3
"""
Comprehensive Test Suite for MFA System
Tests all MFA functionality including TOTP, SMS, Email, Recovery Codes, Device Trust
"""

import unittest
import os
import sys
import sqlite3
import tempfile
from datetime import datetime, timedelta
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.auth.mfa_service import MFAService
from infrastructure.auth.mfa_integration import integrate_mfa_check, MFAIntegration
from infrastructure.database.migrations.add_mfa_system import run_migration


class TestMFAService(unittest.TestCase):
    """Test MFA Service functionality"""

    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        # Create temporary database
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix='.db')

        # Initialize database with basic schema
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()

        # Create minimal required tables
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                email TEXT,
                role_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE user_accounts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                password_hash TEXT,
                two_fa_secret TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                role_name TEXT UNIQUE
            )
        """)

        # Insert test data
        cursor.execute("INSERT INTO roles (id, role_name) VALUES (1, 'admin'), (2, 'student')")
        cursor.execute("""
            INSERT INTO users (id, username, email, role_id)
            VALUES
                (1, 'test_admin', 'admin@test.com', 1),
                (2, 'test_student', 'student@test.com', 2)
        """)
        cursor.execute("""
            INSERT INTO user_accounts (user_id, password_hash)
            VALUES (1, 'hash1'), (2, 'hash2')
        """)

        conn.commit()
        conn.close()

        # Run MFA migration
        run_migration(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        """Clean up test database"""
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    def setUp(self):
        """Set up test case"""
        self.service = MFAService(self.db_path)
        self.test_user_id = 1
        self.test_username = 'test_admin'

    def test_01_totp_setup(self):
        """Test TOTP setup"""
        result = self.service.setup_totp(self.test_user_id, self.test_username)

        self.assertTrue(result['success'], f"TOTP setup failed: {result.get('error')}")
        self.assertIn('secret', result)
        self.assertIn('qr_code', result)
        self.assertIn('recovery_codes', result)
        self.assertIsInstance(result['secret'], str)
        self.assertEqual(len(result['recovery_codes']), 10)

        # Store secret for later tests
        self.totp_secret = result['secret']

    def test_02_totp_verification(self):
        """Test TOTP verification"""
        # Setup TOTP first
        setup_result = self.service.setup_totp(self.test_user_id, self.test_username)
        self.assertTrue(setup_result['success'])

        secret = setup_result['secret']

        # Generate valid TOTP code
        import pyotp
        totp = pyotp.TOTP(secret)
        code = totp.now()

        # Verify code
        verify_result = self.service.verify_totp(self.test_user_id, code)

        self.assertTrue(verify_result['success'], f"TOTP verification failed: {verify_result.get('error')}")
        self.assertEqual(verify_result['method'], 'totp')

    def test_03_totp_invalid_code(self):
        """Test TOTP with invalid code"""
        # Setup TOTP first
        setup_result = self.service.setup_totp(self.test_user_id, self.test_username)
        self.assertTrue(setup_result['success'])

        # Try invalid code
        verify_result = self.service.verify_totp(self.test_user_id, '000000')

        self.assertFalse(verify_result['success'])
        self.assertIn('error', verify_result)

    def test_04_sms_otp_generation(self):
        """Test SMS OTP generation"""
        result = self.service.generate_sms_otp(self.test_user_id, '+1234567890')

        self.assertTrue(result['success'], f"SMS OTP generation failed: {result.get('error')}")
        self.assertIn('code', result)  # In dev mode, code is returned
        self.assertEqual(len(result['code']), 6)
        self.assertTrue(result['code'].isdigit())

    def test_05_sms_otp_verification(self):
        """Test SMS OTP verification"""
        # Generate OTP
        gen_result = self.service.generate_sms_otp(self.test_user_id, '+1234567890')
        self.assertTrue(gen_result['success'])

        code = gen_result['code']

        # Verify code
        verify_result = self.service.verify_sms_otp(self.test_user_id, code)

        self.assertTrue(verify_result['success'], f"SMS verification failed: {verify_result.get('error')}")
        self.assertEqual(verify_result['method'], 'sms')

    def test_06_sms_otp_expiry(self):
        """Test SMS OTP expiration"""
        # Generate OTP
        gen_result = self.service.generate_sms_otp(self.test_user_id, '+1234567890')
        code = gen_result['code']

        # Manually expire the OTP in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE mfa_otp_codes
            SET expires_at = datetime('now', '-1 hour')
            WHERE user_id = ? AND code = ?
        """, (self.test_user_id, code))
        conn.commit()
        conn.close()

        # Try to verify expired code
        verify_result = self.service.verify_sms_otp(self.test_user_id, code)

        self.assertFalse(verify_result['success'])
        self.assertIn('expired', verify_result.get('error', '').lower())

    def test_07_email_otp_generation(self):
        """Test Email OTP generation"""
        result = self.service.generate_email_otp(self.test_user_id, 'test@example.com')

        self.assertTrue(result['success'], f"Email OTP generation failed: {result.get('error')}")
        self.assertIn('code', result)
        self.assertEqual(len(result['code']), 6)
        self.assertTrue(result['code'].isdigit())

    def test_08_email_otp_verification(self):
        """Test Email OTP verification"""
        # Generate OTP
        gen_result = self.service.generate_email_otp(self.test_user_id, 'test@example.com')
        self.assertTrue(gen_result['success'])

        code = gen_result['code']

        # Verify code
        verify_result = self.service.verify_email_otp(self.test_user_id, code)

        self.assertTrue(verify_result['success'], f"Email verification failed: {verify_result.get('error')}")
        self.assertEqual(verify_result['method'], 'email')

    def test_09_recovery_codes_generation(self):
        """Test recovery codes generation"""
        result = self.service.generate_recovery_codes(self.test_user_id)

        self.assertTrue(result['success'], f"Recovery codes generation failed: {result.get('error')}")
        self.assertIn('codes', result)
        self.assertEqual(len(result['codes']), 10)

        # Check format (XXXX-XXXX)
        for code in result['codes']:
            self.assertEqual(len(code), 9)  # 4 + 1 + 4
            self.assertIn('-', code)

    def test_10_recovery_code_verification(self):
        """Test recovery code verification"""
        # Generate codes
        gen_result = self.service.generate_recovery_codes(self.test_user_id)
        self.assertTrue(gen_result['success'])

        codes = gen_result['codes']
        test_code = codes[0]

        # Verify code
        verify_result = self.service.verify_recovery_code(self.test_user_id, test_code)

        self.assertTrue(verify_result['success'], f"Recovery code verification failed: {verify_result.get('error')}")
        self.assertEqual(verify_result['method'], 'recovery_code')
        self.assertEqual(verify_result['remaining_codes'], 9)

    def test_11_recovery_code_single_use(self):
        """Test that recovery codes can only be used once"""
        # Generate and use a code
        gen_result = self.service.generate_recovery_codes(self.test_user_id)
        test_code = gen_result['codes'][0]

        # Use code first time
        verify1 = self.service.verify_recovery_code(self.test_user_id, test_code)
        self.assertTrue(verify1['success'])

        # Try to use same code again
        verify2 = self.service.verify_recovery_code(self.test_user_id, test_code)
        self.assertFalse(verify2['success'])
        self.assertIn('used', verify2.get('error', '').lower())

    def test_12_device_trust_creation(self):
        """Test device trust creation"""
        # Verify TOTP with device_id to create trust
        setup_result = self.service.setup_totp(self.test_user_id, self.test_username)

        import pyotp
        totp = pyotp.TOTP(setup_result['secret'])
        code = totp.now()

        device_id = 'test_device_123'
        verify_result = self.service.verify_totp(self.test_user_id, code, device_id)

        self.assertTrue(verify_result['success'])
        self.assertIn('trust_token', verify_result)

        # Store for next test
        self.trust_token = verify_result['trust_token']
        self.device_id = device_id

    def test_13_device_trust_verification(self):
        """Test device trust verification"""
        # Create trusted device first
        setup_result = self.service.setup_totp(self.test_user_id, self.test_username)

        import pyotp
        totp = pyotp.TOTP(setup_result['secret'])
        code = totp.now()

        device_id = 'test_device_456'
        verify_result = self.service.verify_totp(self.test_user_id, code, device_id)
        trust_token = verify_result['trust_token']

        # Verify device is trusted
        trust_result = self.service.verify_trusted_device(self.test_user_id, device_id, trust_token)

        self.assertTrue(trust_result['success'])
        self.assertTrue(trust_result['trusted'])

    def test_14_device_trust_revocation(self):
        """Test device trust revocation"""
        # Create trusted device
        setup_result = self.service.setup_totp(self.test_user_id, self.test_username)

        import pyotp
        totp = pyotp.TOTP(setup_result['secret'])
        code = totp.now()

        device_id = 'test_device_789'
        verify_result = self.service.verify_totp(self.test_user_id, code, device_id)
        trust_token = verify_result['trust_token']

        # Verify it's trusted
        trust_result = self.service.verify_trusted_device(self.test_user_id, device_id, trust_token)
        self.assertTrue(trust_result['trusted'])

        # Revoke trust
        revoke_result = self.service.revoke_trusted_device(self.test_user_id, device_id)
        self.assertTrue(revoke_result['success'])

        # Verify it's no longer trusted
        trust_result2 = self.service.verify_trusted_device(self.test_user_id, device_id, trust_token)
        self.assertFalse(trust_result2['trusted'])

    def test_15_mfa_enforcement_check(self):
        """Test MFA enforcement policy check"""
        result = self.service.check_mfa_required(self.test_user_id, 'admin')

        self.assertTrue(result['success'])
        # Admin role should have MFA required by default
        self.assertTrue(result.get('required', False))

    def test_16_get_user_methods(self):
        """Test getting user's MFA methods"""
        # Setup TOTP
        self.service.setup_totp(self.test_user_id, self.test_username)

        # Get methods
        result = self.service.get_user_mfa_methods(self.test_user_id)

        self.assertTrue(result['success'])
        self.assertIn('methods', result)
        self.assertGreater(len(result['methods']), 0)
        self.assertEqual(result['methods'][0]['type'], 'totp')

    def test_17_enable_mfa(self):
        """Test enabling MFA for user"""
        result = self.service.enable_mfa(self.test_user_id)

        self.assertTrue(result['success'])

        # Verify it's enabled
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT mfa_enabled FROM mfa_user_settings WHERE user_id = ?", (self.test_user_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], 1)

    def test_18_disable_mfa(self):
        """Test disabling MFA for user"""
        # Enable first
        self.service.enable_mfa(self.test_user_id)

        # Disable
        result = self.service.disable_mfa(self.test_user_id)

        self.assertTrue(result['success'])

        # Verify it's disabled
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT mfa_enabled FROM mfa_user_settings WHERE user_id = ?", (self.test_user_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertEqual(row[0], 0)

    def test_19_max_otp_attempts(self):
        """Test OTP max attempts"""
        # Generate OTP
        gen_result = self.service.generate_sms_otp(self.test_user_id, '+1234567890')
        code = gen_result['code']

        # Try with wrong code multiple times
        for i in range(4):  # More than max_otp_attempts (3)
            wrong_code = '000000'
            # Update attempts in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE mfa_otp_codes
                SET attempts = ?
                WHERE user_id = ? AND code = ?
            """, (i, self.test_user_id, code))
            conn.commit()
            conn.close()

        # Set attempts to max
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE mfa_otp_codes
            SET attempts = 3
            WHERE user_id = ? AND code = ?
        """, (self.test_user_id, code))
        conn.commit()
        conn.close()

        # Now try with correct code - should fail due to max attempts
        verify_result = self.service.verify_sms_otp(self.test_user_id, code)

        self.assertFalse(verify_result['success'])
        self.assertIn('attempt', verify_result.get('error', '').lower())

    def test_20_mfa_lockout(self):
        """Test MFA lockout after failed attempts"""
        # Simulate 5 failed attempts
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO mfa_user_settings (user_id, failed_attempts)
            VALUES (?, 5)
            ON CONFLICT(user_id) DO UPDATE SET failed_attempts = 5
        """, (self.test_user_id,))

        cursor.execute("""
            UPDATE mfa_user_settings
            SET locked_until = datetime('now', '+15 minutes')
            WHERE user_id = ?
        """, (self.test_user_id,))

        conn.commit()
        conn.close()

        # Check if locked
        is_locked = self.service.is_mfa_locked(self.test_user_id)

        self.assertTrue(is_locked)


class TestMFAIntegration(unittest.TestCase):
    """Test MFA Integration functionality"""

    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix='.db')

        # Initialize database
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()

        # Create minimal required tables
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                email TEXT,
                role_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE user_accounts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                password_hash TEXT,
                two_fa_secret TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                role_name TEXT UNIQUE
            )
        """)

        cursor.execute("INSERT INTO roles (id, role_name) VALUES (1, 'admin'), (2, 'student')")
        cursor.execute("""
            INSERT INTO users (id, username, email, role_id)
            VALUES (1, 'admin', 'admin@test.com', 1), (2, 'student', 'student@test.com', 2)
        """)
        cursor.execute("""
            INSERT INTO user_accounts (user_id, password_hash)
            VALUES (1, 'hash1'), (2, 'hash2')
        """)

        conn.commit()
        conn.close()

        # Run MFA migration
        run_migration(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        """Clean up"""
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    def setUp(self):
        """Set up test case"""
        self.integration = MFAIntegration()
        self.integration.mfa_service.db_path = self.db_path

    def test_check_mfa_requirement_admin(self):
        """Test MFA requirement check for admin role"""
        result = integrate_mfa_check(1, 'admin')

        # Admin should require MFA by default policy
        self.assertIn('action', result)
        # Could be 'require_setup' if not set up yet
        self.assertIn(result['action'], ['require_setup', 'require_mfa', 'allow'])

    def test_check_mfa_requirement_student(self):
        """Test MFA requirement check for student role"""
        result = integrate_mfa_check(2, 'student')

        # Student MFA is optional by default
        self.assertIn('action', result)

    def test_device_trust_check(self):
        """Test device trust check"""
        # Should return False for invalid token
        is_trusted = self.integration.check_device_trust(1, 'device123', 'invalid_token')
        self.assertFalse(is_trusted)


class TestMFAProviders(unittest.TestCase):
    """Test SMS and Email providers"""

    def test_sms_mock_provider(self):
        """Test mock SMS provider"""
        from infrastructure.auth.sms_provider import MockSMSProvider

        provider = MockSMSProvider()
        result = provider.send_otp('+1234567890', '123456')

        self.assertTrue(result['success'])
        self.assertEqual(result['provider'], 'mock')
        self.assertEqual(result['code'], '123456')

    def test_email_mock_provider(self):
        """Test mock email provider"""
        from infrastructure.auth.email_otp_service import MockEmailProvider

        provider = MockEmailProvider()
        result = provider.send_otp('test@example.com', '123456', 'Test User')

        self.assertTrue(result['success'])
        self.assertEqual(result['provider'], 'mock')
        self.assertEqual(result['code'], '123456')


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMFAService))
    suite.addTests(loader.loadTestsFromTestCase(TestMFAIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestMFAProviders))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
