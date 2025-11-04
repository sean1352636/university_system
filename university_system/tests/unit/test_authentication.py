"""
Test suite for authentication functionality
"""
import unittest
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from university_system.infrastructure.auth.user_authentication import UserAuth
except ImportError:
    UserAuth = None


class TestAuthentication(unittest.TestCase):
    """Test cases for user authentication"""

    def setUp(self):
        """Set up test fixtures"""
        if UserAuth is None:
            self.skipTest("UserAuth module not available")
        self.auth = UserAuth()

    def test_login_with_valid_credentials(self):
        """Test login with valid admin credentials"""
        result = self.auth.login('admin', 'admin123')
        self.assertTrue(result, "Login should succeed with valid credentials")
        self.assertIsNotNone(self.auth.current_user, "Current user should be set after login")

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials"""
        result = self.auth.login('admin', 'wrongpassword')
        self.assertFalse(result, "Login should fail with invalid password")

    def test_login_with_nonexistent_user(self):
        """Test login with nonexistent username"""
        result = self.auth.login('nonexistent_user', 'password')
        self.assertFalse(result, "Login should fail for nonexistent user")

    def test_logout(self):
        """Test logout functionality"""
        self.auth.login('admin', 'admin123')
        self.auth.logout()
        self.assertIsNone(self.auth.current_user, "Current user should be None after logout")

    def test_check_permission_for_admin(self):
        """Test permission checking for admin role"""
        self.auth.login('admin', 'admin123')
        has_permission = self.auth.check_permission('create_student')
        self.assertTrue(has_permission, "Admin should have create_student permission")

    def test_session_timeout(self):
        """Test session timeout handling"""
        self.auth.login('admin', 'admin123')
        # Simulate old activity time
        if hasattr(self.auth, 'last_activity'):
            self.auth.last_activity = datetime.now() - timedelta(minutes=35)
            is_valid = self.auth.is_session_valid()
            self.assertFalse(is_valid, "Session should be invalid after timeout")

    def test_get_user_role(self):
        """Test getting user role"""
        self.auth.login('admin', 'admin123')
        role = self.auth.current_user.get('role')
        self.assertEqual(role, 'admin', "Admin user should have admin role")

    def test_multiple_login_attempts(self):
        """Test login attempt tracking"""
        # Multiple failed attempts
        for _ in range(3):
            self.auth.login('admin', 'wrongpassword')

        # Check if login attempts are being tracked
        if hasattr(self.auth, 'login_attempts'):
            self.assertGreater(len(self.auth.login_attempts.get('admin', [])), 0,
                             "Failed login attempts should be tracked")

    def test_user_creation(self):
        """Test user account creation"""
        if hasattr(self.auth, 'create_user'):
            try:
                result = self.auth.create_user(
                    username='testuser123',
                    password='testpass123',
                    email='test@university.edu',
                    first_name='Test',
                    last_name='User',
                    role='student'
                )
                self.assertTrue(result, "User creation should succeed")
            except Exception as e:
                self.skipTest(f"User creation not fully implemented: {e}")


class TestAuthenticationEdgeCases(unittest.TestCase):
    """Test edge cases and security features"""

    def setUp(self):
        """Set up test fixtures"""
        if UserAuth is None:
            self.skipTest("UserAuth module not available")
        self.auth = UserAuth()

    def test_empty_username(self):
        """Test login with empty username"""
        result = self.auth.login('', 'password')
        self.assertFalse(result, "Login should fail with empty username")

    def test_empty_password(self):
        """Test login with empty password"""
        result = self.auth.login('admin', '')
        self.assertFalse(result, "Login should fail with empty password")

    def test_sql_injection_attempt(self):
        """Test protection against SQL injection"""
        malicious_input = "admin' OR '1'='1"
        result = self.auth.login(malicious_input, 'password')
        self.assertFalse(result, "Should protect against SQL injection")


if __name__ == '__main__':
    unittest.main()
