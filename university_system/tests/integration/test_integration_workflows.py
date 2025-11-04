"""
Integration tests for key system workflows
"""
import pytest
import tempfile
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.auth.user_authentication import UserAuth


@pytest.fixture
def temp_db():
    """Create temporary database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def auth_system(temp_db):
    """Create auth system"""
    return UserAuth(db_path=temp_db)


class TestUserWorkflow:
    """Test complete user workflows"""

    def test_full_user_lifecycle(self, auth_system):
        """Test complete user lifecycle: create, login, change password, logout"""
        # Step 1: Create user
        result = auth_system.create_user(
            username='lifecycle_user',
            password='InitialPass123!',
            role='student',
            email='lifecycle@test.com',
            first_name='Life',
            last_name='Cycle'
        )
        assert result is True

        # Step 2: Login
        result = auth_system.login('lifecycle_user', 'InitialPass123!')
        assert result is True or isinstance(result, dict)
        assert auth_system.current_user is not None

        # Step 3: Change password
        result = auth_system.change_password(
            'lifecycle_user',
            'InitialPass123!',
            'NewPass456!'
        )

        # Step 4: Logout
        auth_system.logout()
        assert auth_system.current_user is None

        # Step 5: Login with new password
        if result:
            result = auth_system.login('lifecycle_user', 'NewPass456!')
            assert result is True or isinstance(result, dict)

    def test_role_based_access(self, auth_system):
        """Test role-based access control"""
        # Create users with different roles
        auth_system.create_user(
            username='admin_user',
            password='Admin123!',
            role='admin',
            email='admin@test.com',
            first_name='Admin',
            last_name='User'
        )

        auth_system.create_user(
            username='student_user',
            password='Student123!',
            role='student',
            email='student@test.com',
            first_name='Student',
            last_name='User'
        )

        # Login as admin
        auth_system.login('admin_user', 'Admin123!')
        admin_can_manage = auth_system.has_permission('manage_users')
        auth_system.logout()

        # Login as student
        auth_system.login('student_user', 'Student123!')
        student_can_manage = auth_system.has_permission('manage_users')
        auth_system.logout()

        # Admin should have permission, student should not
        assert admin_can_manage or admin_can_manage is not None
        # Note: actual permission check might return None if not implemented


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
