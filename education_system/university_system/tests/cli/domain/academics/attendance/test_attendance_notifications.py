"""
Comprehensive tests for Attendance Notification Service
Tests the automated attendance monitoring and notification system
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, call
from education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
    AttendanceNotificationService,
    check_and_notify_low_attendance
)
from education_system.university_system.infrastructure.database.db import get_connection, transaction


@pytest.fixture
def setup_test_data():
    """Setup test database with sample students, modules, and attendance data"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create tables if they don't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_modules (
                student_id TEXT,
                module_code TEXT,
                PRIMARY KEY (student_id, module_code)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                module_code TEXT NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS parent_accounts (
                parent_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT,
                phone TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS parent_student_relationships (
                parent_id TEXT,
                student_id TEXT,
                PRIMARY KEY (parent_id, student_id)
            )
        """)

        # Insert test data
        cursor.execute("DELETE FROM students WHERE student_id LIKE 'ATT_TEST%'")
        cursor.execute("DELETE FROM modules WHERE module_code LIKE 'ATT_TEST%'")

        # Test students
        cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, email)
            VALUES
                ('ATT_TEST_001', 'John', 'Doe', 'john.doe@university.edu'),
                ('ATT_TEST_002', 'Jane', 'Smith', 'jane.smith@university.edu'),
                ('ATT_TEST_003', 'Bob', 'Johnson', 'bob.johnson@university.edu')
        """)

        # Test modules
        cursor.execute("""
            INSERT INTO modules (module_code, module_name)
            VALUES
                ('ATT_TEST_101', 'Test Module 101'),
                ('ATT_TEST_102', 'Test Module 102')
        """)

        # Enroll students
        cursor.execute("""
            INSERT INTO student_modules (student_id, module_code)
            VALUES
                ('ATT_TEST_001', 'ATT_TEST_101'),
                ('ATT_TEST_002', 'ATT_TEST_101'),
                ('ATT_TEST_003', 'ATT_TEST_102')
        """)

        # Create attendance records
        # Student 001: Low attendance (50%) - 5 sessions, 2 present, 3 absent
        base_date = datetime.now() - timedelta(days=30)
        for i in range(5):
            status = 'Present' if i < 2 else 'Absent'
            cursor.execute("""
                INSERT INTO attendance_records (student_id, module_code, date, status)
                VALUES (?, ?, ?, ?)
            """, ('ATT_TEST_001', 'ATT_TEST_101', (base_date + timedelta(days=i*7)).isoformat(), status))

        # Student 002: Good attendance (95%) - 20 sessions, 19 present
        for i in range(20):
            status = 'Absent' if i == 0 else 'Present'
            cursor.execute("""
                INSERT INTO attendance_records (student_id, module_code, date, status)
                VALUES (?, ?, ?, ?)
            """, ('ATT_TEST_002', 'ATT_TEST_101', (base_date + timedelta(days=i*3)).isoformat(), status))

        # Student 003: Low attendance (60%) - 10 sessions, 6 present, 4 absent
        for i in range(10):
            status = 'Present' if i < 6 else 'Absent'
            cursor.execute("""
                INSERT INTO attendance_records (student_id, module_code, date, status)
                VALUES (?, ?, ?, ?)
            """, ('ATT_TEST_003', 'ATT_TEST_102', (base_date + timedelta(days=i*5)).isoformat(), status))

        # Create parent data
        cursor.execute("DELETE FROM parent_accounts WHERE parent_id LIKE 'ATT_PARENT%'")
        cursor.execute("""
            INSERT INTO parent_accounts (parent_id, first_name, last_name, email, phone)
            VALUES
                ('ATT_PARENT_001', 'Robert', 'Doe', 'robert.doe@email.com', '555-0001'),
                ('ATT_PARENT_002', 'Mary', 'Smith', 'mary.smith@email.com', '555-0002')
        """)

        cursor.execute("DELETE FROM parent_student_relationships WHERE student_id LIKE 'ATT_TEST%'")
        cursor.execute("""
            INSERT INTO parent_student_relationships (parent_id, student_id)
            VALUES
                ('ATT_PARENT_001', 'ATT_TEST_001'),
                ('ATT_PARENT_002', 'ATT_TEST_002')
        """)

    yield

    # Cleanup
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM attendance_records WHERE student_id LIKE 'ATT_TEST%'")
        cursor.execute("DELETE FROM student_modules WHERE student_id LIKE 'ATT_TEST%'")
        cursor.execute("DELETE FROM parent_student_relationships WHERE student_id LIKE 'ATT_TEST%'")
        cursor.execute("DELETE FROM students WHERE student_id LIKE 'ATT_TEST%'")
        cursor.execute("DELETE FROM modules WHERE module_code LIKE 'ATT_TEST%'")
        cursor.execute("DELETE FROM parent_accounts WHERE parent_id LIKE 'ATT_PARENT%'")
        cursor.execute("DELETE FROM attendance_notifications WHERE student_id LIKE 'ATT_TEST%'")


class TestAttendanceNotificationServiceInit:
    """Test service initialization"""

    def test_default_threshold(self):
        """Test service initialization with default threshold"""
        service = AttendanceNotificationService()
        assert service.attendance_threshold == 90.0

    def test_custom_threshold(self):
        """Test service initialization with custom threshold"""
        service = AttendanceNotificationService(attendance_threshold=85.0)
        assert service.attendance_threshold == 85.0

    def test_very_low_threshold(self):
        """Test with very low threshold"""
        service = AttendanceNotificationService(attendance_threshold=50.0)
        assert service.attendance_threshold == 50.0

    def test_very_high_threshold(self):
        """Test with very high threshold"""
        service = AttendanceNotificationService(attendance_threshold=99.0)
        assert service.attendance_threshold == 99.0


class TestGetLowAttendanceStudents:
    """Test getting students with low attendance"""

    def test_get_low_attendance_without_module_filter(self, setup_test_data):
        """Test getting all students with low attendance"""
        service = AttendanceNotificationService(attendance_threshold=90.0)
        students = service.get_low_attendance_students()

        # Should find students with attendance < 90%
        test_students = [s for s in students if s['student_id'].startswith('ATT_TEST')]
        assert len(test_students) >= 2  # ATT_TEST_001 (50%) and ATT_TEST_003 (60%)

        # Verify student 001 is in the list
        student_ids = [s['student_id'] for s in test_students]
        assert 'ATT_TEST_001' in student_ids
        assert 'ATT_TEST_003' in student_ids
        assert 'ATT_TEST_002' not in student_ids  # Has 95% attendance

    def test_get_low_attendance_with_module_filter(self, setup_test_data):
        """Test getting low attendance students for specific module"""
        service = AttendanceNotificationService(attendance_threshold=90.0)
        students = service.get_low_attendance_students(module_code='ATT_TEST_101')

        # Should only find students in ATT_TEST_101 with low attendance
        assert len(students) >= 1
        assert all(s['module_code'] == 'ATT_TEST_101' for s in students)

        # Student 001 should be in the list
        student_ids = [s['student_id'] for s in students]
        assert 'ATT_TEST_001' in student_ids

    def test_low_attendance_data_structure(self, setup_test_data):
        """Test structure of returned student data"""
        service = AttendanceNotificationService(attendance_threshold=90.0)
        students = service.get_low_attendance_students()

        if students:
            student = students[0]
            assert 'student_id' in student
            assert 'first_name' in student
            assert 'last_name' in student
            assert 'email' in student
            assert 'module_code' in student
            assert 'module_name' in student
            assert 'total_sessions' in student
            assert 'attended_sessions' in student
            assert 'attendance_percentage' in student

    def test_attendance_percentage_calculation(self, setup_test_data):
        """Test that attendance percentage is calculated correctly"""
        service = AttendanceNotificationService(attendance_threshold=90.0)
        students = service.get_low_attendance_students()

        for student in students:
            if student['student_id'] == 'ATT_TEST_001':
                # This student has 2/5 = 40% attendance
                assert student['total_sessions'] == 5
                assert student['attended_sessions'] == 2
                assert abs(student['attendance_percentage'] - 40.0) < 1.0

    def test_with_different_thresholds(self, setup_test_data):
        """Test that threshold affects results"""
        # With 90% threshold
        service_90 = AttendanceNotificationService(attendance_threshold=90.0)
        students_90 = [s for s in service_90.get_low_attendance_students()
                       if s['student_id'].startswith('ATT_TEST')]

        # With 50% threshold
        service_50 = AttendanceNotificationService(attendance_threshold=50.0)
        students_50 = [s for s in service_50.get_low_attendance_students()
                       if s['student_id'].startswith('ATT_TEST')]

        # More students should be flagged with higher threshold
        assert len(students_90) >= len(students_50)


class TestNotifyStudentLowAttendance:
    """Test student notification functionality"""

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.render_template')
    def test_notify_student_success(self, mock_render, mock_load, mock_send, setup_test_data):
        """Test successful student notification"""
        # Setup mocks
        mock_load.return_value = "Template content"
        mock_render.return_value = ("Subject", "Body")
        mock_send.return_value = True

        service = AttendanceNotificationService(attendance_threshold=90.0)
        students = service.get_low_attendance_students()

        if students:
            student_data = students[0]
            result = service.notify_student_low_attendance(student_data)

            assert result is True
            mock_send.assert_called_once()
            mock_render.assert_called_once()

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    def test_notify_student_template_not_found(self, mock_load, mock_send, setup_test_data):
        """Test notification when template is not found"""
        mock_load.return_value = None

        service = AttendanceNotificationService(attendance_threshold=90.0)
        student_data = {
            'student_id': 'ATT_TEST_001',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@university.edu',
            'module_code': 'ATT_TEST_101',
            'module_name': 'Test Module',
            'total_sessions': 10,
            'attended_sessions': 5,
            'attendance_percentage': 50.0
        }

        result = service.notify_student_low_attendance(student_data)

        assert result is False
        mock_send.assert_not_called()

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.render_template')
    def test_notify_student_email_failure(self, mock_render, mock_load, mock_send, setup_test_data):
        """Test notification when email sending fails"""
        mock_load.return_value = "Template"
        mock_render.return_value = ("Subject", "Body")
        mock_send.return_value = False

        service = AttendanceNotificationService(attendance_threshold=90.0)
        student_data = {
            'student_id': 'ATT_TEST_001',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@university.edu',
            'module_code': 'ATT_TEST_101',
            'module_name': 'Test Module',
            'total_sessions': 10,
            'attended_sessions': 5,
            'attendance_percentage': 50.0
        }

        result = service.notify_student_low_attendance(student_data)

        assert result is False


class TestNotifyParentsLowAttendance:
    """Test parent notification functionality"""

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.render_template')
    def test_notify_parents_success(self, mock_render, mock_load, mock_send, setup_test_data):
        """Test successful parent notifications"""
        mock_load.return_value = "Template"
        mock_render.return_value = ("Subject", "Body")
        mock_send.return_value = True

        service = AttendanceNotificationService(attendance_threshold=90.0)
        student_data = {
            'student_id': 'ATT_TEST_001',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@university.edu',
            'module_code': 'ATT_TEST_101',
            'module_name': 'Test Module',
            'total_sessions': 10,
            'attended_sessions': 5,
            'attendance_percentage': 50.0
        }

        count = service.notify_parents_low_attendance(student_data)

        # Should notify at least one parent
        assert count >= 1

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    def test_notify_parents_no_parents(self, mock_load, mock_send, setup_test_data):
        """Test parent notification when student has no parents"""
        service = AttendanceNotificationService(attendance_threshold=90.0)
        student_data = {
            'student_id': 'ATT_TEST_003',  # No parents registered
            'first_name': 'Bob',
            'last_name': 'Johnson',
            'email': 'bob.johnson@university.edu',
            'module_code': 'ATT_TEST_102',
            'module_name': 'Test Module',
            'total_sessions': 10,
            'attended_sessions': 6,
            'attendance_percentage': 60.0
        }

        count = service.notify_parents_low_attendance(student_data)

        assert count == 0


class TestCheckAndNotifyLowAttendance:
    """Test the main check and notify workflow"""

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.render_template')
    def test_check_and_notify_workflow(self, mock_render, mock_load, mock_send, setup_test_data):
        """Test complete notification workflow"""
        mock_load.return_value = "Template"
        mock_render.return_value = ("Subject", "Body")
        mock_send.return_value = True

        service = AttendanceNotificationService(attendance_threshold=90.0)
        results = service.check_and_notify_low_attendance(
            send_to_students=True,
            send_to_parents=True
        )

        assert 'students_checked' in results
        assert 'students_notified' in results
        assert 'parents_notified' in results
        assert 'emails_sent' in results
        assert 'errors' in results

        assert results['students_checked'] >= 2

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.render_template')
    def test_check_and_notify_students_only(self, mock_render, mock_load, mock_send, setup_test_data):
        """Test notification to students only"""
        mock_load.return_value = "Template"
        mock_render.return_value = ("Subject", "Body")
        mock_send.return_value = True

        service = AttendanceNotificationService(attendance_threshold=90.0)
        results = service.check_and_notify_low_attendance(
            send_to_students=True,
            send_to_parents=False
        )

        assert results['parents_notified'] == 0

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.render_template')
    def test_check_and_notify_with_module_filter(self, mock_render, mock_load, mock_send, setup_test_data):
        """Test notification for specific module"""
        mock_load.return_value = "Template"
        mock_render.return_value = ("Subject", "Body")
        mock_send.return_value = True

        service = AttendanceNotificationService(attendance_threshold=90.0)
        results = service.check_and_notify_low_attendance(
            module_code='ATT_TEST_101',
            send_to_students=True,
            send_to_parents=False
        )

        assert results['students_checked'] >= 1


class TestGetNotificationHistory:
    """Test notification history retrieval"""

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.render_template')
    def test_get_notification_history(self, mock_render, mock_load, mock_send, setup_test_data):
        """Test retrieving notification history"""
        mock_load.return_value = "Template"
        mock_render.return_value = ("Subject", "Body")
        mock_send.return_value = True

        service = AttendanceNotificationService(attendance_threshold=90.0)

        # Send some notifications
        service.check_and_notify_low_attendance(send_to_students=True, send_to_parents=False)

        # Get history
        history = service.get_notification_history(days=30)

        assert isinstance(history, list)

    def test_get_notification_history_with_student_filter(self, setup_test_data):
        """Test getting history for specific student"""
        service = AttendanceNotificationService(attendance_threshold=90.0)

        history = service.get_notification_history(student_id='ATT_TEST_001', days=30)

        assert isinstance(history, list)


class TestConvenienceFunction:
    """Test convenience function"""

    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.send_email')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.load_template')
    @patch('education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications.render_template')
    def test_convenience_function(self, mock_render, mock_load, mock_send, setup_test_data):
        """Test the standalone convenience function"""
        mock_load.return_value = "Template"
        mock_render.return_value = ("Subject", "Body")
        mock_send.return_value = True

        results = check_and_notify_low_attendance(
            threshold=90.0,
            send_to_students=True,
            send_to_parents=False
        )

        assert 'students_checked' in results
        assert 'students_notified' in results


class TestBuildAttendanceSummary:
    """Test attendance summary formatting"""

    def test_build_attendance_summary(self):
        """Test attendance summary formatting"""
        service = AttendanceNotificationService(attendance_threshold=90.0)

        student_data = {
            'total_sessions': 10,
            'attended_sessions': 5,
            'attendance_percentage': 50.0
        }

        summary = service._build_attendance_summary(student_data)

        assert '10' in summary  # Total sessions
        assert '5' in summary   # Attended
        assert '5' in summary   # Absent (10-5)
        assert '50.0%' in summary  # Percentage


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
