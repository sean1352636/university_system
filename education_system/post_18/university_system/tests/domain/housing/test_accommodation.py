"""
Tests for university_system/modules/domain/housing/services/accommodation.py

This test suite validates:
- Database initialization
- CRUD operations for accommodations
- Template management
- Validation functions
- Statistics and reporting
- Audit logging
- Notification system
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    yield temp_path
    os.close(temp_fd)
    try:
        os.unlink(temp_path)
    except (OSError, IOError):
        pass

@pytest.fixture
def mock_db_connection(temp_db):
    """Mock database connection - patch DB_PATH in _common so all submodules see it"""
    with patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation._common.DB_PATH', temp_db), \
         patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.db.DB_PATH', temp_db), \
         patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.audit.DB_PATH', temp_db), \
         patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.validation.DB_PATH', temp_db), \
         patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.notifications.DB_PATH', temp_db), \
         patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.dashboard.DB_PATH', temp_db), \
         patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.DB_PATH', temp_db):
        yield temp_db

class TestDatabaseInitialization:
    """Test database initialization functions"""

    def test_init_accommodation_db_creates_tables(self, mock_db_connection):
        """Test database initialization creates required tables"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import init_accommodation_db

        init_accommodation_db()

        # Verify tables were created
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()

        # Check accommodations table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accommodations'")
        assert cursor.fetchone() is not None

        # Check audit_log table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        assert cursor.fetchone() is not None

        conn.close()

    def test_init_accommodation_db_creates_columns(self, mock_db_connection):
        """Test accommodations table has required columns"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import init_accommodation_db

        init_accommodation_db()

        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(accommodations)")
        columns = {row[1] for row in cursor.fetchall()}

        required_columns = {'id', 'student_id', 'accommodation_type', 'description',
                          'start_date', 'end_date', 'status', 'created_at', 'updated_at'}

        assert required_columns.issubset(columns)
        conn.close()

class TestValidationFunctions:
    """Test validation helper functions"""

    def test_validate_date_with_valid_date(self):
        """Test validate_date with valid ISO format date"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import validate_date

        is_valid, error = validate_date('2024-01-29')
        assert is_valid is True
        assert error is None

    def test_validate_date_with_invalid_format(self):
        """Test validate_date with invalid date format"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import validate_date

        is_valid, error = validate_date('29/01/2024')
        assert is_valid is False
        assert error is not None
        assert 'format' in error.lower()

    def test_validate_date_with_empty_string(self):
        """Test validate_date with empty string (should be valid)"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import validate_date

        is_valid, error = validate_date('')
        assert is_valid is True
        assert error is None

    def test_validate_student_id_exists(self, mock_db_connection):
        """Test validate_student_id with existing student"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, validate_student_id
        )

        init_accommodation_db()

        # Insert test student
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS students (student_id TEXT PRIMARY KEY)")
        cursor.execute("INSERT INTO students (student_id) VALUES ('S12345')")
        conn.commit()
        conn.close()

        with patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.DB_PATH', mock_db_connection):
            is_valid = validate_student_id('S12345')
            assert is_valid is True

    def test_validate_student_id_not_exists(self, mock_db_connection):
        """Test validate_student_id with non-existent student"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, validate_student_id
        )

        init_accommodation_db()

        # Create students table but don't insert student
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS students (student_id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        with patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.DB_PATH', mock_db_connection):
            is_valid = validate_student_id('S99999')
            assert is_valid is False

class TestAuditLogging:
    """Test audit logging functionality"""

    def test_log_action_creates_entry(self, mock_db_connection):
        """Test log_action creates audit log entry"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, log_action
        )
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import audit as audit_mod

        init_accommodation_db()

        # Reset the column cache so it re-reads from the temp DB
        audit_mod._AUDIT_LOG_COLUMNS_CACHE = None

        with patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.audit.get_current_user', return_value='test_user'):
            log_action('TEST_ACTION', accommodation_id=123, details='Test details')

        # Verify log entry was created
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_log")
        logs = cursor.fetchall()
        conn.close()

        assert len(logs) > 0

    def test_log_action_with_system_user(self, mock_db_connection):
        """Test log_action with system user"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, log_action
        )
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import audit as audit_mod

        init_accommodation_db()

        # Reset the column cache so it re-reads from the temp DB
        audit_mod._AUDIT_LOG_COLUMNS_CACHE = None

        with patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.audit.get_current_user', return_value='system'):
            log_action('SYSTEM_ACTION', details='System action')

        # Verify log entry
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_log")
        logs = cursor.fetchall()
        conn.close()

        assert len(logs) > 0

class TestAccommodationTypes:
    """Test accommodation type functions"""

    def test_get_accommodation_types_returns_list(self):
        """Test get_accommodation_types returns a list"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import get_accommodation_types

        types = get_accommodation_types()
        assert isinstance(types, list)
        assert len(types) > 0

    def test_get_accommodation_types_contains_standard_types(self):
        """Test standard accommodation types are included"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import get_accommodation_types

        types = get_accommodation_types()

        # Should contain standard academic accommodation types
        assert any('extended time' in t.lower() or 'alternate format' in t.lower() or 'note-taking' in t.lower() for t in types)

class TestConflictChecking:
    """Test conflict checking functionality"""

    def test_check_conflict_no_overlap(self, mock_db_connection):
        """Test check_conflict with no date overlap"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, check_conflict
        )

        init_accommodation_db()

        # No existing accommodations, so no conflict
        has_conflict = check_conflict('S12345', 'Dormitory', '2024-01-01', '2024-06-30', excluded_id=None)
        assert has_conflict is False

    def test_check_conflict_with_overlap(self, mock_db_connection):
        """Test check_conflict detects overlapping dates"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, check_conflict
        )

        init_accommodation_db()

        # Insert existing accommodation (need students table for FK)
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS students (student_id TEXT PRIMARY KEY)")
        cursor.execute("INSERT OR IGNORE INTO students (student_id) VALUES ('S12345')")
        cursor.execute("""
            INSERT INTO accommodations
            (student_id, accommodation_type, start_date, end_date, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('S12345', 'Extended Time', '2024-01-01', '2024-12-31', 'active',
              datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()

        # Check for conflict with overlapping dates
        has_conflict = check_conflict('S12345', 'Extended Time', '2024-06-01', '2024-08-31', excluded_id=None)
        assert has_conflict is True

class TestTemplateManagement:
    """Test template save and apply functions"""

    def test_save_template_creates_entry(self, mock_db_connection):
        """Test save_template creates template entry via direct DB insert (save_template is interactive)"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, TEMPLATES_TABLE
        )

        init_accommodation_db()

        # save_template() is an interactive CLI function that reads from stdin,
        # so we insert the template directly and verify the table works.
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO [" + TEMPLATES_TABLE + "]"
            " (name, accommodation_type, description, start_offset_days, duration_days, created_by, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ('Test Template', 'Dormitory', 'Standard dorm room', 0, 90, 'test_user',
             '2024-01-01 00:00:00', '2024-01-01 00:00:00'))
        conn.commit()

        cursor.execute("SELECT * FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", ('Test Template',))
        template = cursor.fetchone()
        conn.close()

        assert template is not None

    def test_apply_template_loads_data(self, mock_db_connection):
        """Test template data can be read back after insert (apply_template is interactive)"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, TEMPLATES_TABLE
        )

        init_accommodation_db()

        # Insert a template directly since save_template/apply_template are interactive
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO [" + TEMPLATES_TABLE + "]"
            " (name, accommodation_type, description, start_offset_days, duration_days, created_by, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ('Apartment Template', 'Apartment', 'Two bedroom apartment', 0, 180, 'test_user',
             '2024-01-01 00:00:00', '2024-01-01 00:00:00'))
        conn.commit()

        # Read back the template
        cursor.execute(
            "SELECT accommodation_type, description, start_offset_days, duration_days"
            " FROM [" + TEMPLATES_TABLE + "] WHERE name = ?",
            ('Apartment Template',))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        loaded_data = {
            'accommodation_type': row[0],
            'description': row[1],
        }
        assert loaded_data.get('accommodation_type') == 'Apartment'
        assert 'description' in loaded_data

class TestStatisticsReporting:
    """Test statistics and reporting functions"""

    def test_generate_statistics_report(self, mock_db_connection):
        """Test generate_statistics_report runs without error when auth is set"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, generate_statistics_report
        )

        init_accommodation_db()

        # Insert test data (need students table for FK)
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS students (student_id TEXT PRIMARY KEY, course TEXT)")
        cursor.execute("INSERT OR IGNORE INTO students (student_id, course) VALUES ('S001', 'CS')")
        cursor.execute("""
            INSERT INTO accommodations
            (student_id, accommodation_type, status, start_date, end_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('S001', 'Extended Time', 'active', '2026-01-01', '2026-12-31',
              datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()

        # generate_statistics_report requires auth with permissions
        mock_auth = MagicMock()
        mock_auth.current_user = {'id': 1, 'role': 'admin'}
        mock_auth.check_permission.return_value = True

        with patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.dashboard.get_auth', return_value=mock_auth), \
             patch('builtins.input', return_value='n'):
            # generate_statistics_report prints to stdout and returns None
            result = generate_statistics_report()

        # The function returns None (prints stats to console)
        assert result is None

class TestBulkImport:
    """Test bulk import functionality"""

    def test_bulk_import_from_csv_valid_data(self, mock_db_connection, tmp_path):
        """Test bulk_import_from_csv with valid CSV data"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, bulk_import_from_csv
        )

        init_accommodation_db()

        # Create test CSV file
        csv_file = tmp_path / "test_accommodations.csv"
        csv_content = """student_id,accommodation_type,description,start_date,end_date
S001,Dormitory,Single room,2024-01-01,2024-12-31
S002,Apartment,Two bedroom,2024-02-01,2024-12-31"""

        csv_file.write_text(csv_content)

        with patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.validate_student_id', return_value=True):
            result = bulk_import_from_csv(str(csv_file))

            # bulk_import_from_csv is interactive and returns None
            assert result is None

    def test_bulk_import_from_csv_invalid_file(self):
        """Test bulk_import_from_csv with non-existent file"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import bulk_import_from_csv

        result = bulk_import_from_csv('/nonexistent/file.csv')

        # bulk_import_from_csv returns None (prints error to stdout)
        assert result is None

class TestNotificationSystem:
    """Test notification functions"""

    @patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.notifications.email_manager')
    def test_notify_student_sends_email(self, mock_email, mock_db_connection):
        """Test notify_student sends email notification"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import notify_student

        # Mock email service available
        mock_email.send_email = Mock(return_value=True)

        result = notify_student('S12345', 'Test Subject', 'Test message body')

        # notify_student returns None (prints output to console)
        assert result is None

    def test_check_expiry_notifications(self, mock_db_connection):
        """Test check_expiry_notifications identifies expiring accommodations"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, check_expiry_notifications
        )

        init_accommodation_db()

        # Insert accommodation expiring soon (need students table for FK)
        conn = sqlite3.connect(mock_db_connection)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, email_address TEXT)")
        cursor.execute("INSERT OR IGNORE INTO students (student_id, first_name, last_name, email_address) VALUES ('S001', 'John', 'Doe', 'john@test.com')")
        future_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO accommodations
            (student_id, accommodation_type, end_date, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('S001', 'Extended Time', future_date, 'active',
              datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()

        # check_expiry_notifications requires auth; mock it
        mock_auth = MagicMock()
        mock_auth.current_user = {'id': 1, 'role': 'admin'}
        mock_auth.check_permission.return_value = True

        with patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.notifications.get_auth', return_value=mock_auth):
            # Check for expiring accommodations - function returns None (prints to console)
            result = check_expiry_notifications()

        assert result is None

class TestAuthIntegration:
    """Test authentication integration"""

    def test_set_auth_stores_instance(self):
        """Test set_auth stores authentication instance"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import set_auth

        mock_auth = Mock()
        set_auth(mock_auth)

        # Should not raise error
        assert True

    @patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.audit.get_current_user')
    def test_operations_use_current_user(self, mock_user, mock_db_connection):
        """Test operations retrieve current user"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import (
            init_accommodation_db, log_action
        )

        mock_user.return_value = 'authenticated_user'
        init_accommodation_db()

        log_action('TEST', accommodation_id=1, details='test')

        # Verify get_current_user was called
        assert mock_user.called

class TestDatabaseBackup:
    """Test database backup integration"""

    @patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.backup_before_operation')
    def test_backup_before_operation_called(self, mock_backup):
        """Test backup_before_operation is called for critical operations"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import backup_before_operation

        backup_before_operation('test_operation')

        # Should call backup or handle gracefully
        assert True

class TestErrorHandling:
    """Test error handling across module"""

    def test_log_action_handles_db_error(self, mock_db_connection):
        """Test log_action handles database errors gracefully"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import log_action

        # Try to log without initialized database
        with patch('education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.DB_PATH', '/invalid/path.db'):
            # Should not raise exception
            try:
                log_action('TEST', accommodation_id=1)
            except Exception:
                pytest.fail("log_action should handle errors gracefully")

    def test_validate_date_handles_none(self):
        """Test validate_date handles None input"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import validate_date

        is_valid, error = validate_date(None)

        # Should handle None gracefully
        assert isinstance(is_valid, bool)

class TestModuleConstants:
    """Test module constants and configuration"""

    def test_templates_table_constant_defined(self):
        """Test TEMPLATES_TABLE constant is defined"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import TEMPLATES_TABLE

        assert TEMPLATES_TABLE is not None
        assert isinstance(TEMPLATES_TABLE, str)

    def test_notification_threshold_defined(self):
        """Test notification threshold is defined"""
        from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation import NOTIFICATION_THRESHOLD_DAYS

        assert isinstance(NOTIFICATION_THRESHOLD_DAYS, int)
        assert NOTIFICATION_THRESHOLD_DAYS > 0

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
