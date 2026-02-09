"""
Test suite for Enhanced Course Management Module

Tests the course management system including:
- Database schema initialization
- Validation functions
- Course CRUD operations
- Prerequisite management
- Course scheduling
- Instructor management
"""

import pytest
import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from university_system.modules.domain.academics.services import course_management as cm
from university_system.infrastructure.database.db import get_connection


class TestDatabaseInitialization:
    """Test course management database initialization"""

    def test_initialize_enhanced_database(self):
        """Test that enhanced database initializes successfully"""
        result = cm.initialize_enhanced_database()
        assert result is True

        # Verify tables were created
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND (
                name = 'courses' OR
                name = 'course_prerequisites' OR
                name = 'course_schedule' OR
                name = 'instructors'
            )
        """)
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]

        assert 'courses' in table_names
        assert 'course_prerequisites' in table_names
        assert 'course_schedule' in table_names
        assert 'instructors' in table_names

        conn.close()

    def test_courses_table_structure(self):
        """Test courses table has correct structure"""
        cm.initialize_enhanced_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(courses)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        # Check for key columns
        assert 'course_code' in column_names
        assert 'course_name' in column_names
        assert 'description' in column_names
        assert 'credit_hours' in column_names
        assert 'department' in column_names
        assert 'max_enrollment' in column_names
        assert 'course_type' in column_names
        assert 'lab_required' in column_names
        assert 'online_available' in column_names

        conn.close()

    def test_course_prerequisites_table_structure(self):
        """Test course prerequisites table structure"""
        cm.initialize_enhanced_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(course_prerequisites)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        assert 'course_id' in column_names
        assert 'prerequisite_course_id' in column_names
        assert 'is_required' in column_names

        conn.close()


class TestValidationFunctions:
    """Test validation helper functions"""

    def test_validate_course_code_valid(self):
        """Test valid course code formats"""
        valid_codes = ['CS101', 'MATH200', 'ENG110', 'BIO230', 'PHYS101']

        for code in valid_codes:
            assert cm.validate_course_code(code) is True

    def test_validate_course_code_invalid(self):
        """Test invalid course code formats"""
        invalid_codes = ['cs101', 'C1', '12345', 'COURSE1', 'AB1', 'ABCDE123']

        for code in invalid_codes:
            assert cm.validate_course_code(code) is False

    def test_validate_email_valid(self):
        """Test valid email formats"""
        valid_emails = [
            'test@university.edu',
            'john.doe@example.com',
            'instructor123@school.ac.uk',
            'prof_smith@college.org'
        ]

        for email in valid_emails:
            assert cm.validate_email(email) is True

    def test_validate_email_invalid(self):
        """Test invalid email formats"""
        invalid_emails = [
            'invalid.email',
            '@example.com',
            'test@',
            'test@@example.com',
            'test @example.com'
        ]

        for email in invalid_emails:
            assert cm.validate_email(email) is False

    def test_validate_time_format_valid(self):
        """Test valid time formats"""
        valid_times = ['09:00', '14:30', '23:59', '00:00', '12:00']

        for time in valid_times:
            assert cm.validate_time_format(time) is True

    def test_validate_time_format_invalid(self):
        """Test invalid time formats"""
        invalid_times = ['9:00', '25:00', '12:60', 'abc', '12:5', '']

        for time in invalid_times:
            assert cm.validate_time_format(time) is False

    def test_validate_days_of_week_valid(self):
        """Test valid days of week format"""
        valid_days = [
            'Monday',
            'Monday,Wednesday',
            'Monday,Wednesday,Friday',
            'Tuesday,Thursday',
            'Saturday,Sunday'
        ]

        for days in valid_days:
            assert cm.validate_days_of_week(days) is True

    def test_validate_days_of_week_invalid(self):
        """Test invalid days of week format"""
        invalid_days = [
            'Mon',
            'monday',
            'Monday,Funday',
            'Mon,Wed,Fri'
        ]

        for days in invalid_days:
            assert cm.validate_days_of_week(days) is False


class TestCircularPrerequisiteCheck:
    """Test circular prerequisite detection"""

    def setUp(self):
        """Set up test data"""
        cm.initialize_enhanced_database()

        conn = get_connection()
        cursor = conn.cursor()

        # Create test courses
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO courses (course_code, course_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, ('CS101', 'Intro to CS', timestamp, timestamp))
        course1_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO courses (course_code, course_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, ('CS201', 'Advanced CS', timestamp, timestamp))
        course2_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO courses (course_code, course_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, ('CS301', 'Expert CS', timestamp, timestamp))
        course3_id = cursor.lastrowid

        # Add prerequisite: CS201 requires CS101
        cursor.execute("""
            INSERT INTO course_prerequisites (course_id, prerequisite_course_id, is_required, created_at)
            VALUES (?, ?, ?, ?)
        """, (course2_id, course1_id, True, timestamp))

        conn.commit()
        conn.close()

        return course1_id, course2_id, course3_id

    def test_check_circular_prerequisite_no_cycle(self):
        """Test when there's no circular dependency"""
        course1_id, course2_id, course3_id = self.setUp()

        conn = get_connection()
        cursor = conn.cursor()

        # Adding CS301 requires CS201 (no cycle)
        has_cycle = cm.check_circular_prerequisite(cursor, course3_id, course2_id)
        assert has_cycle is False

        conn.close()

    def test_check_circular_prerequisite_direct_cycle(self):
        """Test direct circular dependency"""
        course1_id, course2_id, course3_id = self.setUp()

        conn = get_connection()
        cursor = conn.cursor()

        # Adding CS101 requires CS201 would create cycle (CS201 -> CS101 -> CS201)
        has_cycle = cm.check_circular_prerequisite(cursor, course1_id, course2_id)
        assert has_cycle is True

        conn.close()

    def test_check_circular_prerequisite_indirect_cycle(self):
        """Test indirect circular dependency"""
        course1_id, course2_id, course3_id = self.setUp()

        conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Add CS301 requires CS201
        cursor.execute("""
            INSERT INTO course_prerequisites (course_id, prerequisite_course_id, is_required, created_at)
            VALUES (?, ?, ?, ?)
        """, (course3_id, course2_id, True, timestamp))
        conn.commit()

        # Now check if adding CS101 requires CS301 would create cycle
        # (CS301 -> CS201 -> CS101 -> CS301)
        has_cycle = cm.check_circular_prerequisite(cursor, course1_id, course3_id)
        assert has_cycle is True

        conn.close()


class TestCourseCreation:
    """Test course creation functionality"""

    @patch('builtins.input')
    def test_create_enhanced_course_mock_auth_no_permission(self, mock_input):
        """Test course creation without permission"""
        # Create mock auth without permission
        mock_auth = Mock()
        mock_auth.current_user = Mock(id=1, username='testuser')
        mock_auth.check_permission = Mock(return_value=False)

        result = cm.create_enhanced_course(mock_auth)
        assert result is False

    @patch('builtins.input')
    def test_create_enhanced_course_no_auth(self, mock_input):
        """Test course creation without authentication"""
        result = cm.create_enhanced_course(None)
        assert result is False


class TestPrerequisiteManagement:
    """Test prerequisite management functionality"""

    @patch('builtins.input')
    def test_add_prerequisite_no_auth(self, mock_input):
        """Test adding prerequisite without authentication"""
        result = cm.add_prerequisite(None)
        assert result is False

    @patch('builtins.input')
    def test_add_prerequisite_no_permission(self, mock_input):
        """Test adding prerequisite without permission"""
        mock_auth = Mock()
        mock_auth.current_user = Mock(id=1, username='testuser')
        mock_auth.check_permission = Mock(return_value=False)

        result = cm.add_prerequisite(mock_auth)
        assert result is False

    def test_add_prerequisite_insufficient_courses(self):
        """Test adding prerequisite when fewer than 2 courses exist"""
        cm.initialize_enhanced_database()

        # Clear any existing courses
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM courses")
        conn.commit()

        # Add only one course
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO courses (course_code, course_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, ('CS101', 'Intro to CS', timestamp, timestamp))
        conn.commit()
        conn.close()

        mock_auth = Mock()
        mock_auth.current_user = Mock(id=1, username='admin')
        mock_auth.check_permission = Mock(return_value=True)

        with patch('builtins.input'):
            result = cm.add_prerequisite(mock_auth)
            assert result is False


class TestViewPrerequisites:
    """Test viewing prerequisites functionality"""

    @patch('builtins.input')
    def test_view_prerequisites_no_auth(self, mock_input):
        """Test viewing prerequisites without authentication"""
        result = cm.view_prerequisites(None)
        assert result is False


class TestCourseTableOperations:
    """Test direct course table operations"""

    def test_insert_course_direct(self):
        """Test direct course insertion into database"""
        cm.initialize_enhanced_database()

        conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO courses (
                course_code, course_name, description, duration, level, department,
                credit_hours, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('TEST101', 'Test Course', 'Test Description', 3, 'Undergraduate',
              'Testing', 3.0, timestamp, timestamp))

        course_id = cursor.lastrowid
        conn.commit()

        # Verify insertion
        cursor.execute("SELECT * FROM courses WHERE course_code = ?", ('TEST101',))
        result = cursor.fetchone()

        assert result is not None
        assert result[1] == 'TEST101'  # course_code column
        assert result[2] == 'Test Course'  # course_name column

        conn.close()

    def test_course_unique_constraint(self):
        """Test course code unique constraint"""
        cm.initialize_enhanced_database()

        conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert first course
        cursor.execute("""
            INSERT INTO courses (course_code, course_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, ('DUP101', 'Duplicate Course', timestamp, timestamp))
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO courses (course_code, course_name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, ('DUP101', 'Another Course', timestamp, timestamp))
            conn.commit()

        conn.close()


class TestInstructorsTable:
    """Test instructors table operations"""

    def test_insert_instructor(self):
        """Test inserting instructor record"""
        cm.initialize_enhanced_database()

        conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO instructors (
                first_name, last_name, email, department, specialization, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('John', 'Doe', 'john.doe@university.edu', 'Computer Science',
              'AI and Machine Learning', timestamp, timestamp))

        instructor_id = cursor.lastrowid
        conn.commit()

        # Verify
        cursor.execute("SELECT * FROM instructors WHERE id = ?", (instructor_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result[1] == 'John'  # first_name
        assert result[3] == 'john.doe@university.edu'  # email

        conn.close()

    def test_instructor_email_unique(self):
        """Test instructor email unique constraint"""
        cm.initialize_enhanced_database()

        conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO instructors (first_name, last_name, email, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, ('John', 'Doe', 'duplicate@university.edu', timestamp, timestamp))
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO instructors (first_name, last_name, email, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, ('Jane', 'Smith', 'duplicate@university.edu', timestamp, timestamp))
            conn.commit()

        conn.close()


class TestCourseScheduleTable:
    """Test course schedule table operations"""

    def test_insert_course_schedule(self):
        """Test inserting course schedule"""
        cm.initialize_enhanced_database()

        conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Create a course first
        cursor.execute("""
            INSERT INTO courses (course_code, course_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, ('SCHED101', 'Scheduled Course', timestamp, timestamp))
        course_id = cursor.lastrowid
        conn.commit()

        # Insert schedule
        cursor.execute("""
            INSERT INTO course_schedule (
                course_id, semester, year, start_time, end_time, days_of_week, classroom, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (course_id, 'Fall', 2024, '09:00', '10:30', 'Monday,Wednesday', 'Room 101', timestamp))
        schedule_id = cursor.lastrowid
        conn.commit()

        # Verify
        cursor.execute("SELECT * FROM course_schedule WHERE id = ?", (schedule_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result[2] == 'Fall'  # semester
        assert result[6] == 'Monday,Wednesday'  # days_of_week

        conn.close()


class TestCourseAnalyticsTable:
    """Test course analytics table operations"""

    def test_course_analytics_table_exists(self):
        """Test course analytics table exists"""
        cm.initialize_enhanced_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='course_analytics'
        """)
        result = cursor.fetchone()

        assert result is not None

        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
