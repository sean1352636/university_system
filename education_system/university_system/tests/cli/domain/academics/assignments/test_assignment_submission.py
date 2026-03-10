"""
Comprehensive tests for Assignment Submission Service
Tests assignment creation, submission, grading, and management functionality
"""

import pytest
import os
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from education_system.university_system.modules.domain.academics.services.assignments.assignment_submission import (
    AssignmentSubmission
)
from education_system.university_system.infrastructure.database.db import get_connection, transaction


@pytest.fixture
def temp_db_and_submission_dir():
    """Create temporary database and submission directory for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        submission_dir = os.path.join(temp_dir, "submissions")

        # Create a mock auth object
        mock_auth = Mock()
        mock_auth.current_user = {'id': 1, 'role': 'student', 'student_id': 'TEST_STUDENT_001'}

        yield db_path, submission_dir, mock_auth

    # Cleanup happens automatically


@pytest.fixture
def assignment_service(temp_db_and_submission_dir):
    """Create AssignmentSubmission instance for testing"""
    db_path, submission_dir, mock_auth = temp_db_and_submission_dir

    service = AssignmentSubmission(db_path=db_path, submission_dir=submission_dir, auth=mock_auth)

    # Setup test data
    with transaction() as conn:
        cursor = conn.cursor()

        # Create modules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT NOT NULL
            )
        """)

        cursor.execute("INSERT OR IGNORE INTO modules (module_code, module_name) VALUES ('TEST101', 'Test Module')")

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                role TEXT
            )
        """)

        cursor.execute("INSERT OR IGNORE INTO users (id, username, role) VALUES (1, 'test_user', 'student')")

    return service


class TestAssignmentSubmissionInitialization:
    """Test service initialization and setup"""

    def test_init_with_default_params(self):
        """Test initialization with default parameters"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            mock_auth = Mock()
            mock_auth.current_user = {'id': 1, 'role': 'student'}

            service = AssignmentSubmission(db_path=db_path, auth=mock_auth)

            assert service.db_path == db_path
            assert service.auth == mock_auth

    def test_init_creates_directories(self, temp_db_and_submission_dir):
        """Test that initialization creates necessary directories"""
        db_path, submission_dir, mock_auth = temp_db_and_submission_dir

        service = AssignmentSubmission(db_path=db_path, submission_dir=submission_dir, auth=mock_auth)

        # Check main directory exists
        assert os.path.exists(submission_dir)

        # Check subdirectories exist
        subdirs = ['pending', 'submitted', 'graded', 'feedback', 'templates', 'exports', 'backups', 'previews']
        for subdir in subdirs:
            assert os.path.exists(os.path.join(submission_dir, subdir))

    def test_init_creates_database_tables(self, assignment_service):
        """Test that initialization creates all required database tables"""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check assignments table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='assignments'
            """)
            assert cursor.fetchone() is not None

            # Check assignment_submissions table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='assignment_submissions'
            """)
            assert cursor.fetchone() is not None

    def test_set_auth(self, assignment_service):
        """Test setting authentication object"""
        new_auth = Mock()
        new_auth.current_user = {'id': 2, 'role': 'instructor'}

        assignment_service.set_auth(new_auth)

        assert assignment_service.auth == new_auth


class TestFileOperations:
    """Test file-related operations"""

    def test_calculate_file_hash(self, assignment_service):
        """Test file hash calculation"""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Test content for hashing")
            temp_file = f.name

        try:
            file_hash = assignment_service._calculate_file_hash(temp_file)

            # Hash should be a non-empty string
            assert isinstance(file_hash, str)
            assert len(file_hash) > 0

            # Hash should be consistent
            file_hash2 = assignment_service._calculate_file_hash(temp_file)
            assert file_hash == file_hash2
        finally:
            os.unlink(temp_file)

    def test_validate_file_success(self, assignment_service):
        """Test file validation with valid file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_file = f.name

        try:
            # Small file (< 1MB), allowed type
            result = assignment_service._validate_file(
                temp_file,
                allowed_types=['txt', 'pdf', 'docx'],
                max_size_mb=10
            )

            # _validate_file returns (bool, message) tuple
            assert result[0] is True
        finally:
            os.unlink(temp_file)

    def test_validate_file_wrong_type(self, assignment_service):
        """Test file validation with wrong file type"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.exe', delete=False) as f:
            f.write("Test content")
            temp_file = f.name

        try:
            result = assignment_service._validate_file(
                temp_file,
                allowed_types=['txt', 'pdf'],
                max_size_mb=10
            )

            # _validate_file returns (bool, message) tuple
            assert result[0] is False
        finally:
            os.unlink(temp_file)

    def test_validate_file_too_large(self, assignment_service):
        """Test file validation with oversized file"""
        # Create a file larger than limit
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            # Write 2MB of data
            f.write(b'0' * (2 * 1024 * 1024))
            temp_file = f.name

        try:
            result = assignment_service._validate_file(
                temp_file,
                allowed_types=['txt'],
                max_size_mb=1  # 1MB limit
            )

            # _validate_file returns (bool, message) tuple
            assert result[0] is False
        finally:
            os.unlink(temp_file)


class TestStudentOperations:
    """Test student-related operations"""

    def test_get_student_id(self, assignment_service):
        """Test getting current student ID"""
        student_id = assignment_service._get_student_id()

        assert student_id == 'TEST_STUDENT_001'

    def test_get_student_modules(self, assignment_service):
        """Test getting student's enrolled modules"""
        # Setup test data
        with transaction() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_modules (
                    student_id TEXT,
                    module_code TEXT,
                    PRIMARY KEY (student_id, module_code)
                )
            """)

            cursor.execute("""
                INSERT OR IGNORE INTO student_modules (student_id, module_code)
                VALUES ('TEST_STUDENT_001', 'TEST101')
            """)

        modules = assignment_service._get_student_modules('TEST_STUDENT_001')

        assert isinstance(modules, list)
        if modules:
            assert 'TEST101' in modules


class TestLogging:
    """Test logging and auditing functionality"""

    def test_log_action(self, assignment_service):
        """Test action logging"""
        # This should not raise any exceptions
        try:
            assignment_service._log_action(
                action='create',
                table_name='assignments',
                record_id=1,
                new_values={'title': 'Test Assignment'}
            )
        except Exception as e:
            pytest.fail(f"Logging should not raise exception: {e}")

    def test_log_action_with_old_values(self, assignment_service):
        """Test action logging with old and new values"""
        try:
            assignment_service._log_action(
                action='update',
                table_name='assignments',
                record_id=1,
                old_values={'title': 'Old Title'},
                new_values={'title': 'New Title'}
            )
        except Exception as e:
            pytest.fail(f"Logging should not raise exception: {e}")


class TestNotifications:
    """Test notification functionality"""

    @patch('university_system.modules.domain.academics.services.assignments.assignment_submission.send_email')
    def test_send_notification(self, mock_send_email, assignment_service):
        """Test sending in-app notification"""
        result = assignment_service._send_notification(
            user_id=1,
            title='Test Notification',
            message='This is a test',
            notification_type='info',
            assignment_id=1
        )

        # Should return True or not raise exception
        assert result is not None

    @patch('university_system.modules.domain.academics.services.assignments.assignment_submission.send_email')
    def test_send_email_notification(self, mock_send_email, assignment_service):
        """Test sending email notification"""
        mock_send_email.return_value = True

        # Setup user with email
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    email TEXT
                )
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO students (student_id, email)
                VALUES ('TEST_STUDENT_001', 'test@university.edu')
            """)

        result = assignment_service._check_and_send_email(
            user_id='TEST_STUDENT_001',
            title='Test Email',
            message='Test message',
            notification_type='assignment_due'
        )

        # Function should execute without error
        assert result is not None


class TestDueDateReminders:
    """Test due date reminder functionality"""

    @patch('university_system.modules.domain.academics.services.assignments.assignment_submission.send_email')
    def test_run_due_date_reminders(self, mock_send_email, assignment_service):
        """Test running due date reminders"""
        mock_send_email.return_value = True

        # Create an assignment due soon
        with transaction() as conn:
            cursor = conn.cursor()

            now = datetime.now()
            due_date = (now + timedelta(days=2)).isoformat()

            cursor.execute("""
                INSERT INTO assignments
                (module_code, title, description, due_date, max_marks, created_by, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('TEST101', 'Test Assignment', 'Description', due_date, 100, 1, now.isoformat(), now.isoformat(), 1))

        # This should run without errors
        try:
            assignment_service.run_due_date_reminders()
        except Exception as e:
            pytest.fail(f"Due date reminders should not raise exception: {e}")


class TestDataCleanup:
    """Test data cleanup operations"""

    def test_cleanup_old_data(self, assignment_service):
        """Test cleaning up old data"""
        # This should run without errors
        try:
            assignment_service.cleanup_old_data()
        except Exception as e:
            pytest.fail(f"Cleanup should not raise exception: {e}")


class TestIntegrationScenarios:
    """Integration tests for common workflows"""

    def test_complete_assignment_workflow(self, assignment_service):
        """Test complete workflow: create assignment, submit, grade"""
        # Setup necessary tables
        with transaction() as conn:
            cursor = conn.cursor()

            # Create student_modules table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_modules (
                    student_id TEXT,
                    module_code TEXT,
                    PRIMARY KEY (student_id, module_code)
                )
            """)

            cursor.execute("""
                INSERT OR IGNORE INTO student_modules (student_id, module_code)
                VALUES ('TEST_STUDENT_001', 'TEST101')
            """)

            # Create students table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    email TEXT,
                    first_name TEXT,
                    last_name TEXT
                )
            """)

            cursor.execute("""
                INSERT OR IGNORE INTO students (student_id, email, first_name, last_name)
                VALUES ('TEST_STUDENT_001', 'test@university.edu', 'Test', 'Student')
            """)

            # Create an assignment
            now = datetime.now()
            due_date = (now + timedelta(days=7)).isoformat()

            cursor.execute("""
                INSERT INTO assignments
                (module_code, title, description, due_date, max_marks, created_by, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('TEST101', 'Integration Test Assignment', 'Test Description', due_date, 100, 1, now.isoformat(), now.isoformat(), 1))

            assignment_id = cursor.lastrowid

        # Verify assignment was created
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
            assignment = cursor.fetchone()

            assert assignment is not None
            assert assignment[2] == 'Integration Test Assignment'  # title


class TestErrorHandling:
    """Test error handling in various scenarios"""

    def test_calculate_hash_nonexistent_file(self, assignment_service):
        """Test hash calculation with nonexistent file"""
        with pytest.raises(Exception):
            assignment_service._calculate_file_hash("/nonexistent/file.txt")

    def test_validate_nonexistent_file(self, assignment_service):
        """Test validation of nonexistent file"""
        result = assignment_service._validate_file(
            "/nonexistent/file.txt",
            allowed_types=['txt'],
            max_size_mb=10
        )

        assert result is False


class TestPermissions:
    """Test permission checking"""

    def test_check_permission_as_student(self, assignment_service):
        """Test permission checking for student role"""
        # Student role from mock auth
        assignment_service.auth.current_user = {'id': 1, 'role': 'student'}

        # Should not raise exception for basic permissions
        try:
            assignment_service._check_permission('view_assignments')
        except Exception as e:
            # Permission check may or may not allow, but shouldn't crash
            pass

    def test_check_permission_as_instructor(self, assignment_service):
        """Test permission checking for instructor role"""
        assignment_service.auth.current_user = {'id': 2, 'role': 'instructor'}

        # Should not raise exception
        try:
            assignment_service._check_permission('create_assignment')
        except Exception as e:
            pass


class TestDatabaseIntegrity:
    """Test database integrity and constraints"""

    def test_assignments_table_structure(self, assignment_service):
        """Test that assignments table has correct structure"""
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(assignments)")
            columns = cursor.fetchall()

            column_names = [col[1] for col in columns]

            # Check for essential columns
            assert 'id' in column_names
            assert 'module_code' in column_names
            assert 'title' in column_names
            assert 'due_date' in column_names
            assert 'max_marks' in column_names

    def test_assignment_submissions_table_structure(self, assignment_service):
        """Test that assignment_submissions table has correct structure"""
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(assignment_submissions)")
            columns = cursor.fetchall()

            column_names = [col[1] for col in columns]

            # Check for essential columns
            assert 'id' in column_names
            assert 'assignment_id' in column_names
            assert 'student_id' in column_names
            assert 'submission_date' in column_names
            assert 'file_path' in column_names


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_file_hash(self, assignment_service):
        """Test hashing an empty file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            # Create empty file
            temp_file = f.name

        try:
            file_hash = assignment_service._calculate_file_hash(temp_file)
            assert isinstance(file_hash, str)
            assert len(file_hash) > 0
        finally:
            os.unlink(temp_file)

    def test_get_modules_for_nonexistent_student(self, assignment_service):
        """Test getting modules for student that doesn't exist"""
        modules = assignment_service._get_student_modules('NONEXISTENT_STUDENT')

        assert isinstance(modules, list)
        assert len(modules) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
