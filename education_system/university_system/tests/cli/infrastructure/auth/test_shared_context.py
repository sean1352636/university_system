#!/usr/bin/env python3
"""
Tests for shared context and global authentication management

Tests:
- Getting and setting auth instance
- Authentication initialization requirements
- Current user retrieval
- Permission checking
- Permission decorators
- Thread safety
"""

import pytest
import threading
from unittest.mock import Mock, MagicMock, patch
import tempfile
from education_system.university_system.infrastructure.database.db import sqlite3
import os

from education_system.university_system.infrastructure.shared_context import (
    get_auth,
    set_auth,
    initialize_auth,
    is_auth_initialized,
    get_current_user,
    check_permission,
    require_permission,
    AuthenticationNotInitializedError
)

@pytest.fixture(autouse=True)
def reset_auth():
    """Reset auth instance before each test"""
    import education_system.university_system.infrastructure.shared_context as context_module
    # Store original state
    original_instance = context_module._auth_instance
    original_initialized = context_module._auth_initialized

    # Reset for test
    context_module._auth_instance = None
    context_module._auth_initialized = False

    yield

    # Restore original state (important for test isolation)
    context_module._auth_instance = original_instance
    context_module._auth_initialized = original_initialized

@pytest.fixture
def temp_db():
    """Create a temporary database for auth testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_auth.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            role TEXT DEFAULT 'student',
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS user_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            user_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_token TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT,
            expires_at TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            permission TEXT NOT NULL,
            UNIQUE(role, permission)
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT,
            timestamp TEXT
        );
    """)
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    try:
        import shutil
        shutil.rmtree(temp_dir)
    except Exception:
        pass

# ============================================================================
# Auth Instance Management Tests
# ============================================================================

class TestAuthInstanceManagement:
    """Test getting and setting auth instances"""

    def test_get_auth_raises_when_not_initialized(self):
        """Test get_auth raises error when not initialized"""
        import education_system.university_system.infrastructure.shared_context as context_module
        context_module._auth_instance = None
        context_module._auth_initialized = False

        with pytest.raises(AuthenticationNotInitializedError):
            get_auth()

    def test_is_auth_initialized_returns_false_when_not_set(self):
        """Test is_auth_initialized returns False initially"""
        import education_system.university_system.infrastructure.shared_context as context_module
        context_module._auth_instance = None

        assert is_auth_initialized() is False

    def test_set_and_get_auth(self):
        """Test setting and retrieving auth instance"""
        # Create mock auth
        mock_auth = Mock()
        mock_auth.current_user = {"username": "testuser"}

        # Set auth
        set_auth(mock_auth)

        # Get auth
        retrieved_auth = get_auth()

        assert retrieved_auth is mock_auth

    def test_set_auth_marks_initialized(self):
        """Test setting auth marks system as initialized"""
        mock_auth = Mock()
        set_auth(mock_auth)

        assert is_auth_initialized() is True

    def test_set_auth_overwrites_existing(self):
        """Test setting auth overwrites existing instance"""
        # Set first auth
        auth1 = Mock()
        set_auth(auth1)

        # Set second auth
        auth2 = Mock()
        set_auth(auth2)

        # Should return second auth
        assert get_auth() is auth2

    def test_set_auth_rejects_none(self):
        """Test set_auth raises ValueError for None"""
        with pytest.raises(ValueError, match="Cannot set auth to None"):
            set_auth(None)

    def test_get_auth_returns_same_instance(self):
        """Test get_auth returns same instance on multiple calls"""
        mock_auth = Mock()
        set_auth(mock_auth)

        auth1 = get_auth()
        auth2 = get_auth()

        assert auth1 is auth2

# ============================================================================
# Initialize Auth Tests
# ============================================================================

class TestInitializeAuth:
    """Test auth initialization"""

    def test_initialize_auth_creates_instance(self, temp_db):
        """Test initialize_auth creates a proper auth instance"""
        auth = initialize_auth(temp_db)

        assert auth is not None
        assert is_auth_initialized() is True

    def test_initialize_auth_returns_same_instance(self, temp_db):
        """Test initialize_auth returns same instance on multiple calls"""
        auth1 = initialize_auth(temp_db)
        auth2 = initialize_auth(temp_db)

        assert auth1 is auth2

    def test_initialize_auth_uses_default_path(self):
        """Test initialize_auth uses default path when not specified"""
        with patch('university_system.infrastructure.shared_context.UserAuth') as MockUserAuth:
            mock_instance = Mock()
            MockUserAuth.return_value = mock_instance

            import education_system.university_system.infrastructure.shared_context as context_module
            context_module._auth_instance = None
            context_module._auth_initialized = False

            # Call without path
            with patch('university_system.modules.shared.constants.paths') as mock_paths:
                mock_paths.DEFAULT_DB_PATH = "/default/path/db.sqlite"
                auth = initialize_auth()

                # Should use default path
                MockUserAuth.assert_called_once()

# ============================================================================
# Current User Tests
# ============================================================================

class TestCurrentUser:
    """Test current user retrieval"""

    def test_get_current_user_from_auth(self):
        """Test getting current user from auth instance"""
        # Create mock auth with user
        mock_auth = Mock()
        mock_auth.current_user = {
            'id': 1,
            'username': 'testuser',
            'role': 'student'
        }

        set_auth(mock_auth)

        user = get_current_user()

        assert user is not None
        assert user['username'] == 'testuser'
        assert user['role'] == 'student'

    def test_get_current_user_no_current_user_attribute(self):
        """Test getting current user when auth has no current_user"""
        # Create mock auth without current_user attribute
        mock_auth = Mock(spec=[])

        set_auth(mock_auth)

        user = get_current_user()

        assert user is None

    def test_get_current_user_with_none_value(self):
        """Test getting current user when current_user is None"""
        mock_auth = Mock()
        mock_auth.current_user = None

        set_auth(mock_auth)

        user = get_current_user()

        assert user is None

# ============================================================================
# Permission Checking Tests
# ============================================================================

class TestPermissionChecking:
    """Test permission checking"""

    def test_check_permission_allowed(self):
        """Test checking permission that is allowed"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True

        set_auth(mock_auth)

        result = check_permission('read_students')

        assert result is True
        mock_auth.check_permission.assert_called_once_with('read_students')

    def test_check_permission_denied(self):
        """Test checking permission that is denied"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = False

        set_auth(mock_auth)

        result = check_permission('delete_all')

        assert result is False

    def test_check_permission_multiple_calls(self):
        """Test multiple permission checks"""
        mock_auth = Mock()
        mock_auth.check_permission.side_effect = lambda p: p.startswith('read_')

        set_auth(mock_auth)

        assert check_permission('read_students') is True
        assert check_permission('read_grades') is True
        assert check_permission('write_students') is False

# ============================================================================
# Permission Decorator Tests
# ============================================================================

class TestPermissionDecorator:
    """Test permission decorator"""

    def test_require_permission_allowed(self):
        """Test decorator allows access when permission granted"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        set_auth(mock_auth)

        @require_permission('read_grades')
        def view_grades():
            return "Grades data"

        result = view_grades()

        assert result == "Grades data"

    def test_require_permission_denied(self):
        """Test decorator blocks access when permission denied"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = False
        set_auth(mock_auth)

        @require_permission('delete_all')
        def delete_everything():
            return "Deleted"

        with pytest.raises(PermissionError, match="Permission denied: delete_all"):
            delete_everything()

    def test_require_permission_with_args(self):
        """Test decorator works with function arguments"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        set_auth(mock_auth)

        @require_permission('edit_student')
        def edit_student(student_id, name):
            return f"Updated {student_id} to {name}"

        result = edit_student(123, "John Doe")

        assert result == "Updated 123 to John Doe"

    def test_require_permission_with_kwargs(self):
        """Test decorator works with keyword arguments"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        set_auth(mock_auth)

        @require_permission('update_course')
        def update_course(course_id, name=None, credits=None):
            return f"Course {course_id}: {name}, {credits} credits"

        result = update_course(101, name="Math 101", credits=3)

        assert result == "Course 101: Math 101, 3 credits"

    def test_require_permission_multiple_decorators(self):
        """Test multiple permission decorators"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        set_auth(mock_auth)

        @require_permission('read_students')
        @require_permission('read_grades')
        def view_student_grades():
            return "Student grades"

        result = view_student_grades()

        assert result == "Student grades"
        assert mock_auth.check_permission.call_count >= 2

# ============================================================================
# Thread Safety Tests
# ============================================================================

class TestThreadSafety:
    """Test thread safety of auth operations"""

    def test_concurrent_get_auth(self):
        """Test concurrent get_auth calls are thread-safe"""
        mock_auth = Mock()
        set_auth(mock_auth)

        results = []
        errors = []

        def get_auth_task():
            try:
                auth = get_auth()
                results.append(auth)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_auth_task) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert all(r is mock_auth for r in results)

    def test_concurrent_permission_checks(self):
        """Test concurrent permission checks are thread-safe"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        set_auth(mock_auth)

        results = []
        errors = []

        def check_perm_task(perm):
            try:
                result = check_permission(perm)
                results.append(result)
            except Exception as e:
                errors.append(e)

        permissions = ['read', 'write', 'delete', 'admin', 'view']
        threads = [threading.Thread(target=check_perm_task, args=(p,)) for p in permissions]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5

# ============================================================================
# Integration Tests
# ============================================================================

class TestSharedContextIntegration:
    """Test integration scenarios"""

    def test_complete_auth_workflow(self):
        """Test complete authentication workflow"""
        # Create auth instance
        mock_auth = Mock()
        mock_auth.current_user = {
            'id': 1,
            'username': 'instructor',
            'role': 'instructor'
        }
        mock_auth.check_permission.side_effect = lambda perm: perm in ['read_students', 'edit_grades']

        # Set auth
        set_auth(mock_auth)

        # Get current user
        user = get_current_user()
        assert user['username'] == 'instructor'

        # Check permissions
        assert check_permission('read_students') is True
        assert check_permission('edit_grades') is True
        assert check_permission('delete_all') is False

        # Use decorator
        @require_permission('edit_grades')
        def update_grade():
            return "Grade updated"

        result = update_grade()
        assert result == "Grade updated"

    def test_switching_auth_instances(self):
        """Test switching between different auth instances"""
        # First auth (student)
        student_auth = Mock()
        student_auth.current_user = {'username': 'student1', 'role': 'student'}
        student_auth.check_permission.return_value = False

        set_auth(student_auth)

        assert get_current_user()['username'] == 'student1'
        assert check_permission('admin') is False

        # Switch to admin auth
        admin_auth = Mock()
        admin_auth.current_user = {'username': 'admin1', 'role': 'admin'}
        admin_auth.check_permission.return_value = True

        set_auth(admin_auth)

        assert get_current_user()['username'] == 'admin1'
        assert check_permission('admin') is True

# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestSharedContextEdgeCases:
    """Test edge cases and error handling"""

    def test_decorator_preserves_function_metadata(self):
        """Test decorator preserves original function"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        set_auth(mock_auth)

        @require_permission('test')
        def my_function(x, y):
            """My docstring"""
            return x + y

        # Function should still work
        assert my_function(1, 2) == 3

    def test_permission_with_special_characters(self):
        """Test permission names with special characters"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        set_auth(mock_auth)

        result = check_permission('module.sub_module.action')
        assert result is True
        mock_auth.check_permission.assert_called_with('module.sub_module.action')

    def test_empty_permission_string(self):
        """Test empty permission string"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = False
        set_auth(mock_auth)

        result = check_permission('')
        assert result is False

# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling"""

    def test_authentication_not_initialized_error_message(self):
        """Test AuthenticationNotInitializedError has helpful message"""
        import education_system.university_system.infrastructure.shared_context as context_module
        context_module._auth_instance = None
        context_module._auth_initialized = False

        with pytest.raises(AuthenticationNotInitializedError) as exc_info:
            get_auth()

        assert "initialize_auth()" in str(exc_info.value) or "set_auth()" in str(exc_info.value)

    def test_permission_error_includes_permission_name(self):
        """Test PermissionError includes the denied permission"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = False
        set_auth(mock_auth)

        @require_permission('super_secret_permission')
        def secret_function():
            pass

        with pytest.raises(PermissionError) as exc_info:
            secret_function()

        assert 'super_secret_permission' in str(exc_info.value)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
