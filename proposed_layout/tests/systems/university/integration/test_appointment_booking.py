"""
Comprehensive test suite for health appointment booking system.
Tests all functionality in university_system/modules/domain/health/appointments/appointment_booking.py
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
import sys

from education_system.systems.university.domain.pastoral.health.appointments.appointment_booking import (
    manage_provider_schedules,
    add_provider_schedule,
    view_provider_schedules,
    show_upcoming_appointments,
    provider_dashboard,
    todays_schedule,
    manage_screening_schedules,
    create_screening_schedule,
    schedule_screening_appointment,
    manage_provider_time_off,
    schedule_templates,
    provider_availability_report,
    update_provider_schedule,
    provider_statistics,
    schedule_appointment,
    view_appointments,
    update_appointment_status,
    generate_provider_utilization_report,
    generate_appointment_schedule_report,
    generate_provider_performance_report,
    show_appointment_utilization_stats,
    analyze_provider_workload,
)
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.auth import UserAuth

@pytest.fixture
def test_db():
    """Create a test database with necessary tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create required tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        course TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS provider_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_name TEXT,
        day_of_week INTEGER,
        start_time TEXT,
        end_time TEXT,
        max_appointments INTEGER,
        specialty TEXT,
        location TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS health_appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        appointment_type TEXT,
        appointment_date TEXT,
        appointment_time TEXT,
        provider TEXT,
        reason TEXT,
        status TEXT DEFAULT 'scheduled',
        notes TEXT,
        scheduled_at TEXT,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS screening_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        screening_type TEXT,
        due_date TEXT,
        completed_date TEXT,
        status TEXT DEFAULT 'due',
        provider TEXT,
        results TEXT,
        next_due_date TEXT,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS health_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        record_type TEXT,
        record_date TEXT,
        description TEXT,
        provider TEXT,
        confidential INTEGER DEFAULT 0,
        created_at TEXT,
        encrypted_data TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vaccination_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        vaccine_name TEXT,
        administered_date TEXT,
        administered_by TEXT,
        verified INTEGER DEFAULT 0
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        referring_provider TEXT,
        referral_date TEXT,
        status TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_trail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        action TEXT,
        resource_type TEXT,
        resource_id TEXT,
        old_values TEXT,
        new_values TEXT,
        ip_address TEXT,
        user_agent TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        session_id TEXT
    )
    ''')

    # Insert parent records in the 'users' table (referenced by students.user_id FK)
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, first_name, last_name, email, role, created_at)
        VALUES (100, 'jdoe', 'John', 'Doe', 'jdoe@test.edu', 'student', datetime('now'))
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, first_name, last_name, email, role, created_at)
        VALUES (101, 'jsmith', 'Jane', 'Smith', 'jsmith@test.edu', 'student', datetime('now'))
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, first_name, last_name, email, role, created_at)
        VALUES (102, 'admin1', 'Admin', 'User', 'admin@test.edu', 'admin', datetime('now'))
    """)

    # Insert test students (use column names matching the template schema in conftest)
    cursor.execute("""
        INSERT OR IGNORE INTO students (student_id, user_id, first_name, last_name, course, age, status, created_at)
        VALUES ('S001', 100, 'John', 'Doe', 'CS', 20, 'active', datetime('now'))
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO students (student_id, user_id, first_name, last_name, course, age, status, created_at)
        VALUES ('S002', 101, 'Jane', 'Smith', 'ENG', 21, 'active', datetime('now'))
    """)

    # Insert health_records for test students (referenced by joins in report functions)
    cursor.execute("""
        INSERT OR IGNORE INTO health_records (student_id, record_type, record_date, description, provider, created_at)
        VALUES ('S001', 'Annual Physical', date('now'), 'Annual physical exam', 'Dr. Test', datetime('now'))
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO health_records (student_id, record_type, record_date, description, provider, created_at)
        VALUES ('S002', 'Annual Physical', date('now'), 'Annual physical exam', 'Dr. Test', datetime('now'))
    """)

    conn.commit()
    yield conn

    # Cleanup - delete test data (child tables first to avoid FK constraints)
    cursor.execute("DELETE FROM health_appointments WHERE student_id IN ('S001', 'S002')")
    cursor.execute("DELETE FROM screening_schedules WHERE student_id IN ('S001', 'S002')")
    cursor.execute("DELETE FROM health_records WHERE student_id IN ('S001', 'S002')")
    cursor.execute("DELETE FROM provider_schedules WHERE provider_name LIKE 'Dr.%'")
    cursor.execute("DELETE FROM students WHERE student_id IN ('S001', 'S002')")
    conn.commit()
    conn.close()

@pytest.fixture
def mock_auth():
    """Create a mock authentication object with permissions"""
    auth = Mock(spec=UserAuth)
    auth.current_user = {
        'id': 'admin1',
        'username': 'admin',
        'role': 'admin'
    }
    auth.check_permission = Mock(return_value=True)
    return auth

class TestProviderScheduleManagement:
    """Test provider schedule management functions"""

    def test_add_provider_schedule(self, test_db, mock_auth, monkeypatch):
        """Test adding a provider schedule"""
        inputs = iter(['Dr. Smith', '1', '08:00', '17:00', '4', 'General Practice', 'Building A'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        add_provider_schedule(mock_auth)

        cursor = test_db.cursor()
        cursor.execute("SELECT * FROM provider_schedules WHERE provider_name = 'Dr. Smith'")
        result = cursor.fetchone()

        assert result is not None
        assert result[1] == 'Dr. Smith'  # provider_name
        assert result[2] == 1  # day_of_week (Monday)
        assert result[3] == '08:00'  # start_time
        assert result[4] == '17:00'  # end_time
        assert result[5] == 4  # max_appointments

    def test_view_provider_schedules(self, test_db, mock_auth, monkeypatch, capsys):
        """Test viewing provider schedules"""
        # Add test schedule
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO provider_schedules
        (provider_name, day_of_week, start_time, end_time, max_appointments, specialty, location, active, created_at)
        VALUES ('Dr. Test', 1, '09:00', '17:00', 5, 'Cardiology', 'Clinic B', 1, ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()

        monkeypatch.setattr('builtins.input', lambda _: '')
        view_provider_schedules(mock_auth)

        captured = capsys.readouterr()
        assert 'Dr. Test' in captured.out
        assert 'Cardiology' in captured.out

    def test_update_provider_schedule(self, test_db, mock_auth, monkeypatch):
        """Test updating provider schedule"""
        # Add test schedule
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO provider_schedules
        (provider_name, day_of_week, start_time, end_time, max_appointments, specialty, location, active, created_at)
        VALUES ('Dr. Update', 1, '09:00', '17:00', 5, 'General', 'Clinic A', 1, ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()
        schedule_id = cursor.lastrowid

        inputs = iter([str(schedule_id), '10:00', '18:00', '6'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        update_provider_schedule(mock_auth)

        cursor.execute("SELECT start_time, end_time, max_appointments FROM provider_schedules WHERE id = ?", (schedule_id,))
        result = cursor.fetchone()

        assert result[0] == '10:00'
        assert result[1] == '18:00'
        assert result[2] == 6

    def test_provider_availability_report(self, test_db, mock_auth, capsys):
        """Test provider availability report generation"""
        # Add test schedules
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO provider_schedules
        (provider_name, day_of_week, start_time, end_time, max_appointments, specialty, location, active, created_at)
        VALUES ('Dr. Available', 1, '08:00', '16:00', 4, 'General', 'Clinic A', 1, ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()

        provider_availability_report(mock_auth)

        captured = capsys.readouterr()
        assert 'Dr. Available' in captured.out
        assert 'Total Weekly Hours' in captured.out

class TestAppointmentManagement:
    """Test appointment management functions"""

    def test_schedule_appointment(self, test_db, mock_auth, monkeypatch):
        """Test scheduling an appointment"""
        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        inputs = iter(['S001', '1', future_date, '10:00', 'Dr. Smith', 'Regular checkup'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        schedule_appointment(mock_auth)

        cursor = test_db.cursor()
        cursor.execute("SELECT * FROM health_appointments WHERE student_id = 'S001'")
        result = cursor.fetchone()

        assert result is not None
        assert result[1] == 'S001'  # student_id
        assert result[5] == 'Dr. Smith'  # provider
        assert result[7] == 'scheduled'  # status

    def test_schedule_appointment_past_date_rejected(self, test_db, mock_auth, monkeypatch, capsys):
        """Test that past date appointments are rejected"""
        past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

        inputs = iter(['S001', '1', past_date, future_date, '10:00', 'Dr. Smith', 'Checkup'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        schedule_appointment(mock_auth)

        captured = capsys.readouterr()
        assert 'Cannot schedule appointments in the past' in captured.out

    def test_view_appointments(self, test_db, mock_auth, monkeypatch, capsys):
        """Test viewing appointments"""
        # Add test appointment
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO health_appointments
        (student_id, appointment_type, appointment_date, appointment_time, provider, reason, status, scheduled_at)
        VALUES ('S001', 'General Check-up', ?, '10:00', 'Dr. Test', 'Annual checkup', 'scheduled', ?)
        ''', (datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        test_db.commit()

        inputs = iter(['1', 'S001'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        view_appointments(mock_auth)

        captured = capsys.readouterr()
        assert 'Dr. Test' in captured.out or 'S001' in captured.out

    def test_update_appointment_status(self, test_db, mock_auth, monkeypatch):
        """Test updating appointment status"""
        # Add test appointment
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO health_appointments
        (student_id, appointment_type, appointment_date, appointment_time, provider, reason, status, scheduled_at)
        VALUES ('S001', 'General Check-up', ?, '10:00', 'Dr. Test', 'Checkup', 'scheduled', ?)
        ''', (datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        test_db.commit()
        appointment_id = cursor.lastrowid

        inputs = iter([str(appointment_id), '2', ''])  # 2 = completed
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        update_appointment_status(mock_auth)

        cursor.execute("SELECT status FROM health_appointments WHERE id = ?", (appointment_id,))
        result = cursor.fetchone()

        assert result[0] == 'completed'

    def test_show_upcoming_appointments(self, test_db, mock_auth, capsys):
        """Test showing upcoming appointments"""
        # Mock get_user_student_id
        with patch('education_system.systems.university.domain.pastoral.health.appointments.appointment_booking.get_user_student_id', return_value='S001'):
            # Add future appointment
            cursor = test_db.cursor()
            future_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
            cursor.execute('''
            INSERT INTO health_appointments
            (student_id, appointment_type, appointment_date, appointment_time, provider, reason, status, scheduled_at)
            VALUES ('S001', 'Follow-up', ?, '14:00', 'Dr. Future', 'Follow-up visit', 'scheduled', ?)
            ''', (future_date, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            test_db.commit()

            show_upcoming_appointments(mock_auth)

            captured = capsys.readouterr()
            assert 'Upcoming Appointments' in captured.out or 'No upcoming appointments' in captured.out

class TestScreeningSchedules:
    """Test screening schedule functions"""

    def test_create_screening_schedule(self, test_db, mock_auth, monkeypatch):
        """Test creating a screening schedule"""
        future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        inputs = iter(['S001', '1', future_date, 'Dr. Screener'])  # 1 = Annual Physical Exam
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        create_screening_schedule(mock_auth)

        cursor = test_db.cursor()
        cursor.execute("SELECT * FROM screening_schedules WHERE student_id = 'S001'")
        result = cursor.fetchone()

        assert result is not None
        assert result[1] == 'S001'
        assert result[5] == 'due'  # status (index 5: id, student_id, screening_type, due_date, completed_date, status)

    def test_schedule_screening_appointment(self, test_db, mock_auth, monkeypatch):
        """Test scheduling a screening appointment"""
        # Add screening schedule
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO screening_schedules
        (student_id, screening_type, due_date, status, provider, created_at)
        VALUES ('S001', 'Annual Physical', ?, 'due', 'Dr. Test', ?)
        ''', (datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        test_db.commit()
        screening_id = cursor.lastrowid

        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        inputs = iter([str(screening_id), future_date, '09:00', 'Dr. Screener'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        schedule_screening_appointment(mock_auth)

        cursor.execute("SELECT status FROM screening_schedules WHERE id = ?", (screening_id,))
        result = cursor.fetchone()

        assert result[0] == 'scheduled'

class TestProviderDashboard:
    """Test provider dashboard functions"""

    def test_todays_schedule(self, test_db, mock_auth, capsys):
        """Test today's schedule display"""
        # Add today's appointment
        cursor = test_db.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
        INSERT INTO health_appointments
        (student_id, appointment_type, appointment_date, appointment_time, provider, reason, status, scheduled_at)
        VALUES ('S001', 'Checkup', ?, '10:00', 'Dr. admin', 'Test', 'scheduled', ?)
        ''', (today, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        test_db.commit()

        todays_schedule(mock_auth)

        captured = capsys.readouterr()
        assert "Today's Schedule" in captured.out

    def test_provider_statistics(self, test_db, mock_auth, capsys):
        """Test provider statistics generation"""
        # Add test data
        cursor = test_db.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
        INSERT INTO health_appointments
        (student_id, appointment_type, appointment_date, appointment_time, provider, reason, status, scheduled_at)
        VALUES ('S001', 'Checkup', ?, '10:00', 'Dr. admin', 'Test', 'completed', ?)
        ''', (today, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        test_db.commit()

        provider_statistics(mock_auth)

        captured = capsys.readouterr()
        assert 'Statistics' in captured.out

class TestReportGeneration:
    """Test report generation functions"""

    def test_generate_provider_utilization_report(self, test_db, mock_auth, capsys):
        """Test provider utilization report"""
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')

        # Add test appointment
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO health_appointments
        (student_id, appointment_type, appointment_date, appointment_time, provider, reason, status, scheduled_at)
        VALUES ('S001', 'Checkup', ?, '10:00', 'Dr. Test', 'Test', 'completed', ?)
        ''', (datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        test_db.commit()

        generate_provider_utilization_report(mock_auth, start_date, end_date)

        captured = capsys.readouterr()
        assert 'PROVIDER UTILIZATION REPORT' in captured.out

    def test_generate_appointment_schedule_report(self, test_db, mock_auth, monkeypatch, capsys):
        """Test appointment schedule report"""
        inputs = iter(['', ''])  # Use defaults
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        generate_appointment_schedule_report(mock_auth)

        captured = capsys.readouterr()
        assert 'Appointment Schedule Report' in captured.out

    def test_generate_provider_performance_report(self, test_db, mock_auth, monkeypatch, capsys):
        """Test provider performance report"""
        inputs = iter(['', ''])  # Use defaults
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        generate_provider_performance_report(mock_auth)

        captured = capsys.readouterr()
        assert 'Provider Performance' in captured.out

    def test_show_appointment_utilization_stats(self, test_db, mock_auth, capsys):
        """Test appointment utilization statistics"""
        show_appointment_utilization_stats(mock_auth)

        captured = capsys.readouterr()
        assert 'Appointment Utilization Statistics' in captured.out

    def test_analyze_provider_workload(self, test_db, mock_auth, capsys):
        """Test provider workload analysis"""
        analyze_provider_workload(mock_auth)

        captured = capsys.readouterr()
        assert 'Provider Workload Analysis' in captured.out

class TestPermissions:
    """Test permission checks"""

    def test_manage_provider_schedules_no_permission(self, test_db, monkeypatch, capsys):
        """Test that users without permission cannot manage schedules"""
        auth = Mock(spec=UserAuth)
        auth.current_user = {'id': 'user1', 'username': 'user', 'role': 'student'}
        auth.check_permission = Mock(return_value=False)

        inputs = iter(['8'])  # Exit option
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        manage_provider_schedules(auth)

        captured = capsys.readouterr()
        assert "don't have permission" in captured.out

    def test_schedule_appointment_requires_permission(self, test_db, capsys):
        """Test that scheduling requires proper permission"""
        auth = Mock(spec=UserAuth)
        auth.current_user = {'id': 'user1', 'username': 'user', 'role': 'student'}
        auth.check_permission = Mock(return_value=False)

        schedule_appointment(auth)

        captured = capsys.readouterr()
        assert "don't have permission" in captured.out

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_add_provider_schedule_invalid_time_format(self, test_db, mock_auth, monkeypatch, capsys):
        """Test handling of invalid time format"""
        inputs = iter(['Dr. Invalid', '1', 'invalid', '08:00', '17:00', '4', 'General', 'Building A'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        add_provider_schedule(mock_auth)

        captured = capsys.readouterr()
        assert 'Invalid time format' in captured.out

    def test_schedule_appointment_invalid_student(self, test_db, mock_auth, monkeypatch, capsys):
        """Test scheduling appointment for non-existent student"""
        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        inputs = iter(['S999', '1', future_date, '10:00', 'Dr. Test', 'Test'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        mock_auth.current_user['role'] = 'admin'
        schedule_appointment(mock_auth)

        captured = capsys.readouterr()
        assert 'Student ID not found' in captured.out

    def test_create_screening_schedule_invalid_student(self, test_db, mock_auth, monkeypatch, capsys):
        """Test creating screening schedule for non-existent student"""
        inputs = iter(['S999'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        create_screening_schedule(mock_auth)

        captured = capsys.readouterr()
        assert 'Student ID not found' in captured.out

    def test_update_provider_schedule_not_found(self, test_db, mock_auth, monkeypatch, capsys):
        """Test updating non-existent schedule"""
        inputs = iter(['9999'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        update_provider_schedule(mock_auth)

        captured = capsys.readouterr()
        assert 'Schedule not found' in captured.out or 'No provider schedules found' in captured.out

class TestIntegration:
    """Integration tests for complete workflows"""

    def test_complete_appointment_workflow(self, test_db, mock_auth, monkeypatch):
        """Test complete workflow from scheduling to completion"""
        # 1. Add provider schedule
        inputs1 = iter(['Dr. Workflow', '1', '08:00', '17:00', '4', 'General', 'Clinic A'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs1))
        add_provider_schedule(mock_auth)

        # 2. Schedule appointment
        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        inputs2 = iter(['S001', '1', future_date, '10:00', 'Dr. Workflow', 'Checkup'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs2))
        schedule_appointment(mock_auth)

        # 3. Get appointment ID
        cursor = test_db.cursor()
        cursor.execute("SELECT id FROM health_appointments WHERE student_id = 'S001' ORDER BY id DESC LIMIT 1")
        appointment_id = cursor.fetchone()[0]

        # 4. Update to completed
        inputs3 = iter([str(appointment_id), '2', 'Visit completed successfully'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs3))
        update_appointment_status(mock_auth)

        # Verify final status
        cursor.execute("SELECT status FROM health_appointments WHERE id = ?", (appointment_id,))
        result = cursor.fetchone()
        assert result[0] == 'completed'

    def test_screening_workflow(self, test_db, mock_auth, monkeypatch):
        """Test complete screening workflow"""
        # 1. Create screening schedule
        future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        inputs1 = iter(['S001', '1', future_date, 'Dr. Screen'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs1))
        create_screening_schedule(mock_auth)

        # 2. Get screening ID
        cursor = test_db.cursor()
        cursor.execute("SELECT id FROM screening_schedules WHERE student_id = 'S001' ORDER BY id DESC LIMIT 1")
        screening_id = cursor.fetchone()[0]

        # 3. Schedule appointment for screening
        appt_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        inputs2 = iter([str(screening_id), appt_date, '09:00', 'Dr. Screen'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs2))
        schedule_screening_appointment(mock_auth)

        # Verify screening status updated
        cursor.execute("SELECT status FROM screening_schedules WHERE id = ?", (screening_id,))
        result = cursor.fetchone()
        assert result[0] == 'scheduled'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
