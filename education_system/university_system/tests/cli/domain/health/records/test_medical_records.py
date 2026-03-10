"""
Comprehensive tests for medical records management functionality.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from education_system.university_system.modules.domain.health.records.db import audit as _audit_mod
from education_system.university_system.modules.domain.health.records.db import schema as _schema_mod
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.records.db.schema import init_enhanced_health_db
from education_system.university_system.infrastructure.database.db import get_connection

@pytest.fixture
def clean_db():
    """Provide a clean database for each test."""
    conn = get_connection()
    cursor = conn.cursor()

    # Drop test tables if they exist
    tables = [
        'audit_trail', 'health_records', 'data_retention_policies',
        'security_settings', 'allergies', 'medical_conditions',
        'prescriptions', 'vital_signs', 'care_plans', 'referrals',
        'health_metrics', 'screening_schedules', 'risk_assessments',
        'emergency_contacts', 'provider_schedules', 'health_campaigns',
        'wellness_participation', 'disease_surveillance', 'lab_results',
        'quality_metrics'
    ]

    for table in tables:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')

    conn.commit()
    conn.close()

    yield

    # Cleanup after test
    conn = get_connection()
    cursor = conn.cursor()
    for table in tables:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')
    conn.commit()
    conn.close()

class TestLogAuditEvent:
    """Tests for log_audit_event function."""

    def test_log_audit_event_basic(self, clean_db):
        """Test basic audit event logging."""
        log_audit_event(
            user_id='user123',
            action='create',
            resource_type='health_record',
            resource_id='record456'
        )

        # Verify audit trail was created
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM audit_trail')
        records = cursor.fetchall()
        conn.close()

        assert len(records) == 1
        assert records[0][1] == 'user123'  # user_id
        assert records[0][2] == 'create'   # action
        assert records[0][3] == 'health_record'  # resource_type
        assert records[0][4] == 'record456'  # resource_id

    def test_log_audit_event_with_details(self, clean_db):
        """Test audit logging with additional details."""
        log_audit_event(
            user_id='user123',
            action='update',
            resource_type='prescription',
            resource_id='rx789',
            details='Updated dosage'
        )

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT new_values FROM audit_trail')
        result = cursor.fetchone()
        conn.close()

        assert result[0] == 'Updated dosage'

    def test_log_audit_event_with_connection(self, clean_db):
        """Test logging with provided connection."""
        conn = get_connection()

        log_audit_event(
            user_id='user123',
            action='delete',
            resource_type='appointment',
            resource_id='apt101',
            conn=conn
        )

        # Should not auto-commit when connection is provided
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM audit_trail')
        records = cursor.fetchall()

        # Record should still be there (not committed yet)
        assert len(records) == 1

        conn.commit()
        conn.close()

    def test_log_audit_event_database_locked_retry(self, clean_db):
        """Test retry logic for database locked error."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database locked on first attempt, success on second
        mock_cursor.execute.side_effect = [
            sqlite3.OperationalError("database is locked"),
            None  # Success on retry
        ]

        with patch('university_system.modules.domain.health.records.db.audit.get_connection', return_value=mock_conn):
            with patch('time.sleep'):  # Mock sleep to speed up test
                log_audit_event(
                    user_id='user123',
                    action='test',
                    resource_type='test',
                    resource_id='test123',
                    max_retries=3
                )

        # Should have retried
        assert mock_cursor.execute.call_count == 2

    def test_log_audit_event_failure_handling(self, clean_db):
        """Test that audit logging failures don't break the flow."""
        # This should not raise an exception even if logging fails
        with patch('university_system.modules.domain.health.records.db.audit.get_connection', side_effect=Exception("DB Error")):
            with patch('builtins.print') as mock_print:
                log_audit_event(
                    user_id='user123',
                    action='test',
                    resource_type='test',
                    resource_id='test'
                )

                # Should print warning but not crash
                assert mock_print.called

class TestInitEnhancedHealthDB:
    """Tests for init_enhanced_health_db function."""

    def test_init_creates_all_tables(self, clean_db):
        """Test that database initialization creates all required tables."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        conn.close()

        # Verify key tables exist
        expected_tables = {
            'health_records', 'audit_trail', 'data_retention_policies',
            'security_settings', 'allergies', 'medical_conditions',
            'prescriptions', 'vital_signs', 'care_plans', 'referrals',
            'lab_results', 'quality_metrics'
        }

        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    def test_init_populates_retention_policies(self, clean_db):
        """Test that retention policies are populated on initialization."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM data_retention_policies')
        count = cursor.fetchone()[0]

        conn.close()

        assert count > 0, "Retention policies should be populated"

    def test_init_populates_security_settings(self, clean_db):
        """Test that security settings are populated."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM security_settings')
        count = cursor.fetchone()[0]

        conn.close()

        assert count > 0, "Security settings should be populated"

    def test_init_idempotent(self, clean_db):
        """Test that running init multiple times doesn't cause errors."""
        init_enhanced_health_db()
        init_enhanced_health_db()  # Run again

        conn = get_connection()
        cursor = conn.cursor()

        # Check retention policies count hasn't doubled
        cursor.execute('SELECT COUNT(*) FROM data_retention_policies')
        count = cursor.fetchone()[0]

        conn.close()

        # Should not have duplicates
        assert count <= 10, "Should not create duplicate policies"

    def test_health_records_table_structure(self, clean_db):
        """Test health_records table has correct columns."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('PRAGMA table_info(health_records)')
        columns = {row[1] for row in cursor.fetchall()}

        conn.close()

        expected_columns = {
            'id', 'student_id', 'record_type', 'record_date',
            'description', 'provider', 'confidential', 'created_at', 'encrypted_data'
        }

        assert expected_columns.issubset(columns)

    def test_audit_trail_table_structure(self, clean_db):
        """Test audit_trail table has correct columns."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('PRAGMA table_info(audit_trail)')
        columns = {row[1] for row in cursor.fetchall()}

        conn.close()

        expected_columns = {
            'id', 'user_id', 'action', 'resource_type', 'resource_id',
            'old_values', 'new_values', 'timestamp'
        }

        assert expected_columns.issubset(columns)

    def test_retention_policy_column_fix(self, clean_db):
        """Test that retention policy table uses correct column name."""
        # Create table with wrong column name
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE data_retention_policies (
                id INTEGER PRIMARY KEY,
                data_type TEXT,
                retention_days INTEGER
            )
        ''')
        conn.commit()
        conn.close()

        # Run init - should fix the column name
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('PRAGMA table_info(data_retention_policies)')
        columns = {row[1] for row in cursor.fetchall()}

        conn.close()

        # Should now have correct column name
        assert 'retention_period_days' in columns

class TestDatabaseIntegrity:
    """Tests for database integrity and foreign key constraints."""

    def test_foreign_key_constraints(self, clean_db):
        """Test that foreign key constraints are properly defined."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        # Check health_records has foreign key to students
        cursor.execute('PRAGMA foreign_key_list(health_records)')
        foreign_keys = cursor.fetchall()

        conn.close()

        # Should have at least one foreign key
        assert len(foreign_keys) > 0

    def test_default_values(self, clean_db):
        """Test that default values are set correctly."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        # Insert minimal health record
        cursor.execute('''
            INSERT INTO health_records (student_id, record_date)
            VALUES ('S001', '2024-01-01')
        ''')

        # Check default values
        cursor.execute('SELECT confidential FROM health_records WHERE student_id = "S001"')
        result = cursor.fetchone()

        conn.close()

        # Confidential should default to 0
        assert result[0] == 0

class TestComplexScenarios:
    """Tests for complex scenarios involving multiple tables."""

    def test_create_complete_patient_record(self, clean_db):
        """Test creating a complete patient record with multiple related tables."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        # Create student (assuming students table exists)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO students (student_id, first_name, last_name)
            VALUES ('S001', 'John', 'Doe')
        ''')

        # Add health record
        cursor.execute('''
            INSERT INTO health_records (student_id, record_type, record_date, description)
            VALUES ('S001', 'checkup', '2024-01-01', 'Annual checkup')
        ''')

        # Add allergy
        cursor.execute('''
            INSERT INTO allergies (student_id, allergen, severity)
            VALUES ('S001', 'Penicillin', 'severe')
        ''')

        # Add vital signs
        cursor.execute('''
            INSERT INTO vital_signs (student_id, measurement_date, heart_rate, temperature)
            VALUES ('S001', '2024-01-01', 72, 98.6)
        ''')

        conn.commit()

        # Verify all records were created
        cursor.execute('SELECT COUNT(*) FROM health_records WHERE student_id = "S001"')
        health_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM allergies WHERE student_id = "S001"')
        allergy_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM vital_signs WHERE student_id = "S001"')
        vital_count = cursor.fetchone()[0]

        conn.close()

        assert health_count == 1
        assert allergy_count == 1
        assert vital_count == 1

    def test_audit_trail_with_multiple_operations(self, clean_db):
        """Test audit trail records multiple operations."""
        init_enhanced_health_db()

        # Log multiple events
        log_audit_event('user1', 'create', 'record', 'r1')
        log_audit_event('user1', 'update', 'record', 'r1', 'Changed status')
        log_audit_event('user1', 'delete', 'record', 'r1')

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM audit_trail')
        count = cursor.fetchone()[0]

        cursor.execute('SELECT action FROM audit_trail ORDER BY id')
        actions = [row[0] for row in cursor.fetchall()]

        conn.close()

        assert count == 3
        assert actions == ['create', 'update', 'delete']

class TestErrorHandling:
    """Tests for error handling in medical records module."""

    def test_database_connection_error_handling(self, clean_db):
        """Test handling of database connection errors."""
        with patch('university_system.modules.domain.health.records.db.audit.get_connection', side_effect=Exception("Connection failed")):
            with patch('builtins.print') as mock_print:
                # Should not raise exception
                log_audit_event('user', 'test', 'test', 'test')

                # Should print warning
                assert mock_print.called

    def test_invalid_data_insertion(self, clean_db):
        """Test handling of invalid data during insertion."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        # Try to insert invalid data (missing required fields)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute('''
                INSERT INTO allergies (allergen)
                VALUES ('Peanuts')
            ''')
            conn.commit()

        conn.close()

class TestDataRetentionPolicies:
    """Tests specific to data retention policies."""

    def test_default_retention_policies(self, clean_db):
        """Test that default retention policies are created correctly."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT data_type, retention_period_days
            FROM data_retention_policies
            WHERE data_type = 'health_records'
        ''')
        result = cursor.fetchone()

        conn.close()

        assert result is not None
        assert result[0] == 'health_records'
        assert result[1] == 2555  # 7 years

    def test_all_retention_policies_created(self, clean_db):
        """Test that all required retention policies are created."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT data_type FROM data_retention_policies')
        data_types = {row[0] for row in cursor.fetchall()}

        conn.close()

        expected_types = {
            'health_records', 'vaccination_records', 'appointments',
            'audit_trail', 'prescriptions', 'lab_results', 'vital_signs'
        }

        assert expected_types.issubset(data_types)

class TestSecuritySettings:
    """Tests for security settings initialization."""

    def test_default_security_settings(self, clean_db):
        """Test that default security settings are created."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT setting_name, setting_value
            FROM security_settings
            WHERE setting_name = 'encryption_enabled'
        ''')
        result = cursor.fetchone()

        conn.close()

        assert result is not None
        assert result[0] == 'encryption_enabled'
        assert result[1] == '1'  # Should be enabled

    def test_all_security_settings_created(self, clean_db):
        """Test that all security settings are initialized."""
        init_enhanced_health_db()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT setting_name FROM security_settings')
        settings = {row[0] for row in cursor.fetchall()}

        conn.close()

        expected_settings = {
            'session_timeout_minutes', 'max_failed_login_attempts',
            'password_expiry_days', 'require_2fa_for_providers',
            'encryption_enabled', 'audit_logging_enabled'
        }

        assert expected_settings.issubset(settings)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
