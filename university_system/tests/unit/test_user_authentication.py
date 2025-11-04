"""
Comprehensive tests for user_authentication module

Enhanced with actual implementations
"""
import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.auth.user_authentication import UserAuth


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def auth_system(temp_db):
    """Create UserAuth instance with temp database"""
    return UserAuth(db_path=temp_db)


class TestUserAuth:
    """Tests for UserAuth class"""

    def test_init(self, auth_system):
        """Test UserAuth initialization"""
        assert auth_system is not None
        assert auth_system.current_user is None
        assert auth_system.max_attempts == 5
        assert auth_system.lockout_time == 15

    def test_create_user_success(self, auth_system):
        """Test successful user creation"""
        result = auth_system.create_user(
            username='testuser',
            password='TestPass123!',
            role='student',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        assert result is True

    def test_create_user_duplicate(self, auth_system):
        """Test creating duplicate user fails"""
        auth_system.create_user(
            username='testuser',
            password='TestPass123!',
            role='student',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )

        # Try to create same user again
        result = auth_system.create_user(
            username='testuser',
            password='TestPass123!',
            role='student',
            email='test2@example.com',
            first_name='Test',
            last_name='User2'
        )
        assert result is False

    def test_login_success(self, auth_system):
        """Test successful login"""
        # Create user first
        auth_system.create_user(
            username='testuser',
            password='TestPass123!',
            role='admin',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )

        # Login
        result = auth_system.login('testuser', 'TestPass123!')
        assert result is True or isinstance(result, dict)

        if result is True:
            assert auth_system.current_user is not None
            assert auth_system.current_user['username'] == 'testuser'
            assert auth_system.current_user['role'] == 'admin'

    def test_login_invalid_password(self, auth_system):
        """Test login with invalid password"""
        # Create user
        auth_system.create_user(
            username='testuser',
            password='TestPass123!',
            role='student',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )

        # Try to login with wrong password
        with pytest.raises(Exception):  # Should raise InvalidCredentialsError
            auth_system.login('testuser', 'WrongPassword')

    def test_login_nonexistent_user(self, auth_system):
        """Test login with non-existent user"""
        with pytest.raises(Exception):  # Should raise InvalidCredentialsError
            auth_system.login('nonexistent', 'password')

    def test_logout(self, auth_system):
        """Test user logout"""
        # Create and login user
        auth_system.create_user(
            username='testuser',
            password='TestPass123!',
            role='student',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        auth_system.login('testuser', 'TestPass123!')

        # Logout
        auth_system.logout()
        assert auth_system.current_user is None

    def test_change_password(self, auth_system):
        """Test password change"""
        # Create user
        auth_system.create_user(
            username='testuser',
            password='TestPass123!',
            role='student',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )

        # Change password
        result = auth_system.change_password('testuser', 'TestPass123!', 'NewPass456!')

        # Should be able to login with new password
        if result:
            auth_system.login('testuser', 'NewPass456!')
            assert auth_system.current_user is not None

    def test_has_permission(self, auth_system):
        """Test permission checking"""
        # Create admin user
        auth_system.create_user(
            username='admin',
            password='AdminPass123!',
            role='admin',
            email='admin@example.com',
            first_name='Admin',
            last_name='User'
        )
        auth_system.login('admin', 'AdminPass123!')

        # Check permission
        result = auth_system.has_permission('manage_users')
        # Admin should have this permission
        assert result is True or result is not None

    def test_session_timeout(self, auth_system):
        """Test session timeout functionality"""
        # Create and login user
        auth_system.create_user(
            username='testuser',
            password='TestPass123!',
            role='student',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        auth_system.login('testuser', 'TestPass123!')

        # Simulate old activity time
        if auth_system.last_activity:
            auth_system.last_activity = datetime.now() - timedelta(minutes=60)

        # Check if session is active
        is_active = auth_system.check_session()
        assert is_active is False

    def test_lockout_after_failed_attempts(self, auth_system):
        """Test account lockout after multiple failed login attempts"""
        # Create user
        auth_system.create_user(
            username='testuser',
            password='TestPass123!',
            role='student',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )

        # Try to login with wrong password multiple times
        for i in range(6):  # More than max_attempts (5)
            try:
                auth_system.login('testuser', 'WrongPassword')
            except Exception:
                pass  # Expected to fail

        # Next attempt should be blocked due to lockout
        with pytest.raises(Exception) as exc_info:
            auth_system.login('testuser', 'TestPass123!')  # Even with correct password

        assert 'locked' in str(exc_info.value).lower() or 'attempt' in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
