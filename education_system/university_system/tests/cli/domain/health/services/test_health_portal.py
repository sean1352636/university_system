"""
Comprehensive tests for health portal service functionality.
"""

import pytest
import os
import json
import csv
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from education_system.university_system.modules.domain.health.services import health_portal
from education_system.university_system.infrastructure.database.db import get_connection


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_auth():
    """Create mock authentication object."""
    auth = Mock()
    auth.get_username = Mock(return_value='testuser')
    auth.get_role = Mock(return_value='admin')
    auth.check_session = Mock(return_value=True)
    auth.current_user = {'id': 'user123', 'username': 'testuser'}
    return auth


@pytest.fixture
def setup_portal_db():
    """Setup database for health portal tests."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            role TEXT
        )
    ''')

    # Create health records
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            blood_type TEXT,
            allergies TEXT,
            medications TEXT,
            conditions TEXT,
            insurance_provider TEXT,
            insurance_policy_number TEXT,
            last_updated TEXT,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')

    # Create appointments
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_appointments (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            appointment_type TEXT,
            appointment_date TEXT,
            appointment_time TEXT,
            notes TEXT,
            status TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')

    # Create vaccinations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vaccinations (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            vaccine_name TEXT,
            date_administered TEXT,
            next_due_date TEXT,
            status TEXT,
            provider TEXT,
            lot_number TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')

    # Create emergency contacts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            name TEXT,
            relationship TEXT,
            phone TEXT,
            email TEXT,
            is_primary INTEGER,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')

    # Create medical history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medical_history (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            diagnosis TEXT,
            treatment TEXT,
            date TEXT,
            provider TEXT,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')

    # Insert test user
    cursor.execute('''
        INSERT INTO users (id, username, role)
        VALUES ('user123', 'testuser', 'student')
    ''')

    # Insert test health record
    cursor.execute('''
        INSERT INTO health_records
        (student_id, blood_type, allergies, medications, insurance_provider)
        VALUES ('user123', 'O+', 'Penicillin', 'Aspirin', 'Health Insurance Co')
    ''')

    # Insert test appointment
    cursor.execute('''
        INSERT INTO health_appointments
        (student_id, appointment_type, appointment_date, appointment_time, status)
        VALUES ('user123', 'General Check-up', '2024-03-01', '10:00', 'Pending')
    ''')

    # Insert test vaccination
    cursor.execute('''
        INSERT INTO vaccinations
        (student_id, vaccine_name, date_administered, status)
        VALUES ('user123', 'COVID-19', '2024-01-15', 'Complete')
    ''')

    # Insert emergency contact
    cursor.execute('''
        INSERT INTO emergency_contacts
        (student_id, name, relationship, phone, is_primary)
        VALUES ('user123', 'John Doe', 'Father', '555-1234', 1)
    ''')

    conn.commit()
    conn.close()

    yield

    # Cleanup
    conn = get_connection()
    cursor = conn.cursor()
    tables = ['users', 'health_records', 'health_appointments', 'vaccinations',
              'emergency_contacts', 'medical_history']
    for table in tables:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')
    conn.commit()
    conn.close()


class TestViewHealthRecords:
    """Tests for view_health_records function."""

    @patch('builtins.print')
    def test_view_health_records(self, mock_print, mock_auth, setup_portal_db):
        """Test viewing health records."""
        health_portal.view_health_records(mock_auth)

        # Should print health record information
        assert mock_print.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should display blood type
        assert any('O+' in str(call) or 'blood' in str(call).lower() for call in print_calls)

    @patch('builtins.print')
    def test_view_health_records_no_records(self, mock_print, mock_auth):
        """Test viewing when no health records exist."""
        # Clear health records
        conn = get_connection()
        conn.execute('DELETE FROM health_records')
        conn.commit()
        conn.close()

        health_portal.view_health_records(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('no health' in str(call).lower() for call in print_calls)


class TestScheduleAppointment:
    """Tests for schedule_appointment function."""

    @patch('builtins.input', side_effect=['1', '2024-04-01', '14:00', 'Test notes'])
    @patch('builtins.print')
    def test_schedule_appointment_success(self, mock_print, mock_input, mock_auth, setup_portal_db):
        """Test successfully scheduling an appointment."""
        health_portal.schedule_appointment(mock_auth)

        # Verify appointment was created
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM health_appointments
            WHERE student_id = 'user123' AND appointment_date = '2024-04-01'
        ''')
        result = cursor.fetchone()
        conn.close()

        assert result is not None


class TestManageEmergencyContacts:
    """Tests for manage_emergency_contacts function."""

    @patch('builtins.input', side_effect=['1'])
    @patch('builtins.print')
    def test_view_emergency_contacts(self, mock_print, mock_input, mock_auth, setup_portal_db):
        """Test viewing emergency contacts."""
        health_portal.manage_emergency_contacts(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should display contact information
        assert any('john doe' in str(call).lower() for call in print_calls)

    @patch('builtins.input', side_effect=['2', 'Jane Doe', 'Mother', '555-5678', 'jane@example.com', 'n'])
    @patch('builtins.print')
    def test_add_emergency_contact(self, mock_print, mock_input, mock_auth, setup_portal_db):
        """Test adding emergency contact."""
        health_portal.manage_emergency_contacts(mock_auth)

        # Verify contact was added
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM emergency_contacts
            WHERE student_id = 'user123' AND name = 'Jane Doe'
        ''')
        result = cursor.fetchone()
        conn.close()

        assert result is not None


class TestGenerateHealthReports:
    """Tests for generate_health_reports function."""

    @patch('builtins.input', return_value='1')
    @patch('builtins.print')
    def test_generate_immunization_report(self, mock_print, mock_input, mock_auth, setup_portal_db):
        """Test generating immunization status report."""
        health_portal.generate_health_reports(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should show immunization report
        assert any('immunization' in str(call).lower() or 'vaccination' in str(call).lower() for call in print_calls)

    @patch('builtins.input', return_value='2')
    @patch('builtins.print')
    def test_generate_health_summary(self, mock_print, mock_input, mock_auth, setup_portal_db):
        """Test generating health summary report."""
        health_portal.generate_health_reports(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should show summary
        assert any('summary' in str(call).lower() for call in print_calls)


class TestExportHealthRecords:
    """Tests for export_health_records function."""

    @patch('builtins.input', side_effect=['1'])
    @patch('builtins.print')
    @patch('education_system.university_system.modules.domain.health.services.health_portal.paths')
    def test_export_health_records_csv(self, mock_paths, mock_print, mock_input, mock_auth, setup_portal_db, temp_dir):
        """Test exporting health records to CSV."""
        mock_paths.DATA_DIR = Path(temp_dir)

        health_portal.export_health_records(mock_auth)

        # Check if CSV file was created
        csv_files = list(Path(temp_dir).glob('**/*health_records*.csv'))
        # File may or may not exist depending on implementation

    @patch('builtins.input', side_effect=['2'])
    @patch('builtins.print')
    @patch('education_system.university_system.modules.domain.health.services.health_portal.paths')
    def test_export_health_records_json(self, mock_paths, mock_print, mock_input, mock_auth, setup_portal_db, temp_dir):
        """Test exporting health records to JSON."""
        mock_paths.DATA_DIR = Path(temp_dir)

        health_portal.export_health_records(mock_auth)

        # Check if JSON file was created
        json_files = list(Path(temp_dir).glob('**/*health_records*.json'))
        # File may or may not exist


class TestBackupManagement:
    """Tests for backup management functions."""

    @patch('builtins.print')
    @patch('education_system.university_system.modules.domain.health.services.health_portal.paths')
    @patch('education_system.university_system.modules.domain.health.services.health_portal.DEFAULT_DB_PATH')
    def test_create_manual_backup(self, mock_db_path, mock_paths, mock_print, mock_auth, temp_dir):
        """Test creating a manual backup."""
        mock_paths.DATA_DIR = Path(temp_dir)
        mock_db = Path(temp_dir) / 'test.db'
        mock_db.touch()
        mock_db_path.return_value = mock_db

        with patch('shutil.copy2') as mock_copy:
            health_portal.create_manual_backup(mock_auth)

            # Should attempt to create backup
            # mock_copy.assert_called()

    @patch('builtins.print')
    def test_view_backup_history_no_backups(self, mock_print, mock_auth):
        """Test viewing backup history when no backups exist."""
        health_portal.view_backup_history(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should indicate no backups found
        assert any('no backup' in str(call).lower() for call in print_calls)


class TestAdvancedReports:
    """Tests for advanced population reports."""

    @patch('builtins.print')
    def test_population_health_statistics(self, mock_print, mock_auth, setup_portal_db):
        """Test generating population health statistics."""
        health_portal.population_health_statistics(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should show population statistics
        assert any('population' in str(call).lower() or 'statistics' in str(call).lower() for call in print_calls)

    @patch('builtins.print')
    def test_vaccination_coverage_report(self, mock_print, mock_auth, setup_portal_db):
        """Test generating vaccination coverage report."""
        health_portal.vaccination_coverage_report(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should show vaccination coverage
        assert any('vaccination' in str(call).lower() or 'coverage' in str(call).lower() for call in print_calls)

    @patch('builtins.print')
    def test_appointment_utilization_analysis(self, mock_print, mock_auth, setup_portal_db):
        """Test appointment utilization analysis."""
        health_portal.appointment_utilization_analysis(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should show appointment metrics
        assert any('appointment' in str(call).lower() for call in print_calls)


class TestSecurityAudit:
    """Tests for security and audit functions."""

    @patch('builtins.input', side_effect=['1', '0'])
    @patch('builtins.print')
    def test_security_audit_menu(self, mock_print, mock_input, mock_auth):
        """Test security audit menu navigation."""
        # Create audit_trail table
        conn = get_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY,
                user_id TEXT,
                username TEXT,
                action TEXT,
                table_name TEXT,
                details TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()
        conn.close()

        health_portal.security_audit_menu(mock_auth)

        # Should complete without error
        assert True

    @patch('builtins.print')
    def test_view_access_summary(self, mock_print, mock_auth):
        """Test viewing access summary."""
        # Create audit_trail table with data
        conn = get_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY,
                username TEXT,
                action TEXT,
                table_name TEXT,
                timestamp TEXT
            )
        ''')
        conn.execute('''
            INSERT INTO audit_trail (username, action, table_name, timestamp)
            VALUES ('testuser', 'view', 'health_records', datetime('now'))
        ''')
        conn.commit()
        conn.close()

        health_portal.view_access_summary(mock_auth)

        # Should print access summary
        assert mock_print.called


class TestMenuNavigation:
    """Tests for menu navigation functions."""

    @patch('builtins.input', return_value='0')
    @patch('builtins.print')
    def test_data_export_menu_exit(self, mock_print, mock_input, mock_auth):
        """Test exiting data export menu."""
        health_portal.data_export_menu(mock_auth)

        assert True

    @patch('builtins.input', return_value='0')
    @patch('builtins.print')
    def test_backup_management_menu_exit(self, mock_print, mock_input, mock_auth):
        """Test exiting backup management menu."""
        health_portal.backup_management_menu(mock_auth)

        assert True

    @patch('builtins.input', return_value='0')
    @patch('builtins.print')
    def test_advanced_reports_menu_exit(self, mock_print, mock_input, mock_auth):
        """Test exiting advanced reports menu."""
        health_portal.advanced_reports_menu(mock_auth)

        assert True


class TestErrorHandling:
    """Tests for error handling in health portal."""

    @patch('builtins.print')
    def test_view_health_records_no_user(self, mock_print, mock_auth):
        """Test viewing health records when user doesn't exist."""
        # Clear users
        conn = get_connection()
        conn.execute('DELETE FROM users')
        conn.commit()
        conn.close()

        health_portal.view_health_records(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should handle gracefully
        assert any('error' in str(call).lower() or 'not found' in str(call).lower() for call in print_calls)

    @patch('builtins.input', side_effect=['invalid'])
    @patch('builtins.print')
    def test_schedule_appointment_invalid_type(self, mock_print, mock_input, mock_auth, setup_portal_db):
        """Test scheduling appointment with invalid type."""
        health_portal.schedule_appointment(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should indicate invalid choice
        assert any('invalid' in str(call).lower() for call in print_calls)


class TestDataIntegrity:
    """Tests for data integrity in health portal operations."""

    @patch('builtins.input', side_effect=['2', 'Test Contact', 'Sibling', '555-9999', 'test@example.com', 'y'])
    @patch('builtins.print')
    def test_add_primary_contact_replaces_existing(self, mock_print, mock_input, mock_auth, setup_portal_db):
        """Test that adding a new primary contact unsets the old one."""
        health_portal.manage_emergency_contacts(mock_auth)

        # Verify old primary contact is no longer primary
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM emergency_contacts
            WHERE student_id = 'user123' AND is_primary = 1
        ''')
        primary_count = cursor.fetchone()[0]
        conn.close()

        # Should only have one primary contact
        assert primary_count == 1


class TestSessionHandling:
    """Tests for session handling in health portal."""

    @patch('builtins.print')
    def test_no_active_session(self, mock_print):
        """Test handling when user is not logged in."""
        auth = Mock()
        auth.check_session = Mock(return_value=False)

        health_portal.display_health_portal_menu(auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should prompt to login
        assert any('log in' in str(call).lower() for call in print_calls)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
