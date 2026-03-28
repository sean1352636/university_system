"""
Comprehensive test suite for health portal data privacy and security.
Tests all functionality in university_system/modules/domain/health/portal/data_privacy.py
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
import tempfile
import os
import json

from education_system.university_system.modules.domain.health.portal.data_privacy import (
    ensure_integration_schema,
    ensure_security_schema,
    _first_existing_column,
    get_or_create_encryption_key,
    log_audit_event,
    advanced_security_menu,
    user_session_management,
    access_control_lists,
    security_policy_configuration,
    encryption_key_management,
    integration_logs,
    data_sync_status,
    laboratory_system_integration,
    insurance_system_integration,
    security_incident_response,
    integration_health_check,
    integration_management,
    view_risk_assessments,
    screening_recommendations,
    ip_restriction_management,
    two_factor_authentication_setup,
    api_key_management,
    generate_security_report,
    population_risk_analysis,
    review_security_settings,
    update_security_settings,
    assess_contact_risk,
    security_audit_menu,
    view_audit_log,
    health_risk_assessment,
    conduct_risk_assessment,
    calculate_risk_score,
    get_risk_factors,
    generate_risk_recommendations,
)
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.auth import UserAuth

@pytest.fixture
def test_db():
    """Create a test database with necessary tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create basic tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        course TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_trail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        action TEXT,
        resource_type TEXT,
        resource_id TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS security_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_name TEXT UNIQUE,
        setting_value TEXT,
        updated_at TEXT,
        updated_by TEXT
    )
    ''')

    # Insert test data (use column names to avoid column mismatch)
    cursor.execute("INSERT INTO students (student_id, first_name, last_name, course) VALUES ('S001', 'John', 'Doe', 'CS')")
    cursor.execute("INSERT INTO students (student_id, first_name, last_name, course) VALUES ('S002', 'Jane', 'Smith', 'ENG')")

    # Insert security settings
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    settings = [
        ('session_timeout_minutes', '30', timestamp, 'admin'),
        ('max_failed_login_attempts', '3', timestamp, 'admin'),
        ('encryption_enabled', '1', timestamp, 'admin'),
        ('audit_logging_enabled', '1', timestamp, 'admin'),
    ]

    for setting in settings:
        cursor.execute('''
        INSERT OR IGNORE INTO security_settings (setting_name, setting_value, updated_at, updated_by)
        VALUES (?, ?, ?, ?)
        ''', setting)

    conn.commit()
    yield conn

    # Cleanup
    try:
        cursor.execute("DROP TABLE IF EXISTS students")
        cursor.execute("DROP TABLE IF EXISTS audit_trail")
        cursor.execute("DROP TABLE IF EXISTS security_settings")
        cursor.execute("DROP TABLE IF EXISTS integration_logs")
        cursor.execute("DROP TABLE IF EXISTS security_incidents")
        cursor.execute("DROP TABLE IF EXISTS encryption_keys")
        cursor.execute("DROP TABLE IF EXISTS security_policies")
        cursor.execute("DROP TABLE IF EXISTS roles")
        cursor.execute("DROP TABLE IF EXISTS permissions")
        cursor.execute("DROP TABLE IF EXISTS role_permissions")
        cursor.execute("DROP TABLE IF EXISTS risk_assessments")
        cursor.execute("DROP TABLE IF EXISTS medical_conditions")
        cursor.execute("DROP TABLE IF EXISTS allergies")
        cursor.execute("DROP TABLE IF EXISTS vital_signs")
        conn.commit()
    except (OSError, IOError):
        pass
    finally:
        conn.close()

@pytest.fixture
def mock_auth():
    """Create a mock authentication object with admin permissions"""
    auth = Mock(spec=UserAuth)
    auth.current_user = {
        'id': 'admin1',
        'username': 'admin',
        'role': 'admin'
    }
    auth.check_permission = Mock(return_value=True)
    return auth

class TestSchemaManagement:
    """Test database schema management functions"""

    def test_ensure_integration_schema(self, test_db):
        """Test integration schema creation"""
        ensure_integration_schema()

        cursor = test_db.cursor()

        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'integration_logs' in tables
        assert 'insurance_integration_events' in tables
        assert 'lab_integration_events' in tables
        assert 'sync_queue' in tables

    def test_ensure_security_schema(self, test_db):
        """Test security schema creation"""
        ensure_security_schema()

        cursor = test_db.cursor()

        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'security_policies' in tables
        assert 'encryption_keys' in tables
        assert 'security_incidents' in tables

    def test_first_existing_column(self, test_db):
        """Test finding first existing column"""
        cursor = test_db.cursor()

        # Test with students table
        column = _first_existing_column(test_db, 'students', ['student_id', 'id', 'pk'])
        assert column == 'student_id'

        # Test with non-existent columns
        column = _first_existing_column(test_db, 'students', ['nonexistent1', 'nonexistent2'])
        assert column is None

class TestEncryptionManagement:
    """Test encryption key management"""

    def test_get_or_create_encryption_key_creates_new(self):
        """Test creating new encryption key"""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = os.path.join(temp_dir, 'health_encryption.key')

            with patch('education_system.university_system.modules.domain.health.portal.data_privacy.os.path.exists', return_value=False):
                with patch('builtins.open', create=True) as mock_open:
                    get_or_create_encryption_key()

                    # Verify file was written
                    mock_open.assert_called()

    def test_get_or_create_encryption_key_uses_existing(self):
        """Test using existing encryption key"""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            test_key = b'test_encryption_key'
            f.write(test_key)
            key_file = f.name

        try:
            with patch('education_system.university_system.modules.domain.health.portal.data_privacy.os.path.exists', return_value=True):
                with patch('builtins.open', mock_open=Mock(return_value=open(key_file, 'rb'))):
                    key = get_or_create_encryption_key()

                    assert key == test_key
        finally:
            os.unlink(key_file)

class TestAuditLogging:
    """Test audit logging functionality"""

    @patch('education_system.university_system.modules.domain.health.portal.data_privacy.audit_logger')
    def test_log_audit_event(self, mock_logger):
        """Test audit event logging"""
        log_audit_event('user123', 'create', 'health_record', '456', 'Created new record')

        mock_logger.info.assert_called_once()
        call_args = str(mock_logger.info.call_args)

        assert 'user123' in call_args
        assert 'create' in call_args
        assert 'health_record' in call_args
        assert '456' in call_args

    def test_view_audit_log(self, test_db, mock_auth, capsys):
        """Test viewing audit log"""
        # Add test audit entries
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO audit_trail (user_id, action, resource_type, resource_id, timestamp)
        VALUES ('user1', 'view', 'health_record', '123', ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()

        view_audit_log(mock_auth)

        captured = capsys.readouterr()
        assert 'Audit Log' in captured.out or 'audit' in captured.out.lower()

class TestSecurityPolicies:
    """Test security policy management"""

    def test_security_policy_configuration(self, test_db, mock_auth, monkeypatch, capsys):
        """Test viewing security policies"""
        ensure_security_schema()

        # Add test policy
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT OR IGNORE INTO security_policies (policy_key, value, updated_at)
        VALUES ('test_policy', 'enabled', ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()

        inputs = iter([''])  # Press Enter to return
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        security_policy_configuration(mock_auth)

        captured = capsys.readouterr()
        assert 'Security Policies' in captured.out or 'policies' in captured.out.lower()

    def test_access_control_lists(self, test_db, mock_auth, monkeypatch, capsys):
        """Test viewing access control lists"""
        ensure_security_schema()

        inputs = iter([''])  # Press Enter to return
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        access_control_lists(mock_auth)

        captured = capsys.readouterr()
        assert 'Access Control' in captured.out or 'control' in captured.out.lower()

    def test_encryption_key_management(self, test_db, mock_auth, monkeypatch, capsys):
        """Test encryption key management interface"""
        ensure_security_schema()

        inputs = iter([''])  # Press Enter to return
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        encryption_key_management(mock_auth)

        captured = capsys.readouterr()
        assert 'Encryption Keys' in captured.out or 'keys' in captured.out.lower()

class TestIntegrationManagement:
    """Test integration management functions"""

    def test_integration_health_check(self, test_db, mock_auth, monkeypatch, capsys):
        """Test integration health check"""
        ensure_integration_schema()

        inputs = iter([''])  # Press Enter to return
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        integration_health_check(mock_auth)

        captured = capsys.readouterr()
        # Should display some health check information
        assert captured.out != ''

    def test_integration_logs(self, test_db, mock_auth, capsys):
        """Test viewing integration logs"""
        ensure_integration_schema()

        # Add test log entry
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO integration_logs (provider, event_type, status, message, created_at)
        VALUES ('test_system', 'sync', 'success', 'Test sync', ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()

        integration_logs(mock_auth)

        captured = capsys.readouterr()
        # Should display logs or message
        assert captured.out != ''

    def test_data_sync_status(self, test_db, mock_auth, capsys):
        """Test viewing data sync status"""
        ensure_integration_schema()

        data_sync_status(mock_auth)

        captured = capsys.readouterr()
        # Should display sync status or message about no pending items
        assert captured.out != ''

class TestSecurityIncidents:
    """Test security incident management"""

    def test_security_incident_response(self, test_db, mock_auth, monkeypatch, capsys):
        """Test security incident response interface"""
        ensure_security_schema()

        # Add test incident
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO security_incidents (incident_id, summary, severity, status, detected_at)
        VALUES ('INC-001', 'Test incident', 'high', 'open', ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()

        inputs = iter([''])  # Press Enter to return
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        security_incident_response(mock_auth)

        captured = capsys.readouterr()
        assert 'Incidents' in captured.out or 'incident' in captured.out.lower()

class TestRiskAssessment:
    """Test risk assessment functions"""

    def test_calculate_risk_score(self):
        """Test risk score calculation"""
        score = calculate_risk_score(
            'Cardiovascular Risk',
            age=65,
            conditions=[('Diabetes', 'Moderate'), ('Hypertension', 'Severe')],
            allergies=[('Penicillin', 'Severe')],
            latest_bmi=(30.5,)
        )

        assert isinstance(score, int)
        assert 0 <= score <= 100

    def test_get_risk_factors(self):
        """Test getting risk factors"""
        risk_factors = get_risk_factors(
            'General Health Risk',
            age=70,
            conditions=[('Diabetes', 'Severe')],
            allergies=[('Peanuts', 'Life-threatening')],
            latest_bmi=(28.0,)
        )

        assert isinstance(risk_factors, list)
        assert len(risk_factors) > 0

    def test_generate_risk_recommendations(self):
        """Test generating risk recommendations"""
        recommendations = generate_risk_recommendations(
            'Cardiovascular Risk',
            risk_score=75,
            risk_factors=['High blood pressure', 'Obesity']
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

    def test_view_risk_assessments(self, test_db, mock_auth, monkeypatch, capsys):
        """Test viewing risk assessments"""
        # Create risk_assessments table
        cursor = test_db.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            assessment_type TEXT,
            risk_score INTEGER,
            risk_factors TEXT,
            recommendations TEXT,
            assessed_date TEXT,
            assessed_by TEXT,
            follow_up_date TEXT,
            created_at TEXT
        )
        ''')

        # Add test assessment
        cursor.execute('''
        INSERT INTO risk_assessments
        (student_id, assessment_type, risk_score, risk_factors, recommendations, assessed_date, assessed_by, created_at)
        VALUES ('S001', 'General Health', 50, '[]', '[]', ?, 'Dr. Test', ?)
        ''', (datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        test_db.commit()

        inputs = iter(['', ''])  # Press Enter twice to return
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        view_risk_assessments(mock_auth)

        captured = capsys.readouterr()
        assert 'Risk Assessments' in captured.out or 'assessment' in captured.out.lower()

    def test_assess_contact_risk(self):
        """Test contact risk assessment"""
        contact = {
            'type': 'household',
            'duration': '120'
        }

        risk = assess_contact_risk(contact, 'COVID-19', 'Severe')

        assert risk in ['Low', 'Moderate', 'High']

    def test_assess_contact_risk_invalid_duration(self):
        """Test contact risk assessment with invalid duration"""
        contact = {
            'type': 'close',
            'duration': 'invalid'
        }

        # Should handle gracefully
        risk = assess_contact_risk(contact, 'Influenza', 'Moderate')

        assert risk in ['Low', 'Moderate', 'High']

class TestSecurityReports:
    """Test security report generation"""

    def test_generate_security_report(self, test_db, mock_auth, monkeypatch, capsys):
        """Test security report generation"""
        # Add test audit data
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO audit_trail (user_id, action, resource_type, resource_id, timestamp)
        VALUES ('user1', 'failed_login', 'auth', '0', ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()

        inputs = iter(['n'])  # Don't save report
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        generate_security_report(mock_auth)

        captured = capsys.readouterr()
        assert 'SECURITY REPORT' in captured.out or 'Security' in captured.out

class TestSessionManagement:
    """Test user session management"""

    def test_user_session_management(self, test_db, mock_auth, monkeypatch, capsys):
        """Test user session management interface"""
        # Add test login activity
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO audit_trail (user_id, action, ip_address, timestamp)
        VALUES ('user1', 'login', '192.168.1.1', ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()

        inputs = iter(['4'])  # Return to menu
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        user_session_management(mock_auth)

        captured = capsys.readouterr()
        assert 'Session' in captured.out or 'session' in captured.out.lower()

class TestIPRestrictionManagement:
    """Test IP restriction management"""

    def test_ip_restriction_management(self, test_db, mock_auth, monkeypatch, capsys):
        """Test IP restriction management interface"""
        inputs = iter(['6'])  # Return to menu
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        ip_restriction_management(mock_auth)

        captured = capsys.readouterr()
        assert 'IP Restriction' in captured.out or 'IP' in captured.out

class Test2FAManagement:
    """Test two-factor authentication management"""

    def test_two_factor_authentication_setup(self, test_db, mock_auth, monkeypatch, capsys):
        """Test 2FA setup interface"""
        inputs = iter(['5'])  # Return to menu
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        two_factor_authentication_setup(mock_auth)

        captured = capsys.readouterr()
        assert '2FA' in captured.out or 'Two-Factor' in captured.out or 'Authentication' in captured.out

class TestSecuritySettings:
    """Test security settings management"""

    def test_review_security_settings(self, test_db, mock_auth, monkeypatch, capsys):
        """Test reviewing security settings"""
        inputs = iter(['n'])  # Don't update settings
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        review_security_settings(mock_auth)

        captured = capsys.readouterr()
        assert 'Security Settings' in captured.out or 'Settings' in captured.out

    def test_update_security_settings(self, test_db, mock_auth, monkeypatch):
        """Test updating security settings"""
        inputs = iter(['q'])  # Quit without updating
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        update_security_settings(mock_auth)

        # Should not crash

class TestPopulationAnalysis:
    """Test population risk analysis"""

    def test_population_risk_analysis(self, test_db, mock_auth, capsys):
        """Test population risk analysis"""
        # Create required tables
        cursor = test_db.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS medical_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            condition_name TEXT,
            severity TEXT,
            status TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS allergies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            allergen TEXT,
            severity TEXT,
            verified INTEGER
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vaccination_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            vaccine_name TEXT,
            verified INTEGER
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            contact_name TEXT
        )
        ''')

        test_db.commit()

        population_risk_analysis(mock_auth)

        captured = capsys.readouterr()
        assert 'Population Risk' in captured.out or 'Risk' in captured.out

class TestPermissions:
    """Test permission checks"""

    def test_security_menu_admin_only(self, test_db, capsys):
        """Test advanced security menu requires admin"""
        non_admin_auth = Mock(spec=UserAuth)
        non_admin_auth.current_user = {'id': 'user1', 'username': 'user', 'role': 'student'}
        non_admin_auth.check_permission = Mock(return_value=False)

        advanced_security_menu(non_admin_auth)

        captured = capsys.readouterr()
        assert 'Only administrators' in captured.out or 'admin' in captured.out.lower()

    def test_view_risk_assessments_requires_permission(self, test_db, monkeypatch, capsys):
        """Test viewing risk assessments requires permission"""
        no_perm_auth = Mock(spec=UserAuth)
        no_perm_auth.current_user = {'id': 'user1', 'username': 'user', 'role': 'student'}
        no_perm_auth.check_permission = Mock(return_value=False)

        inputs = iter([''])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        view_risk_assessments(no_perm_auth)

        captured = capsys.readouterr()
        assert "don't have permission" in captured.out

class TestIntegration:
    """Integration tests for complete workflows"""

    def test_complete_security_workflow(self, test_db, mock_auth, monkeypatch, capsys):
        """Test complete security management workflow"""
        # Ensure schemas exist
        ensure_security_schema()
        ensure_integration_schema()

        # Add test data
        cursor = test_db.cursor()
        cursor.execute('''
        INSERT INTO audit_trail (user_id, action, resource_type, resource_id, timestamp)
        VALUES ('user1', 'view', 'health_record', '123', ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        test_db.commit()

        # View audit log
        view_audit_log(mock_auth)

        captured = capsys.readouterr()
        assert captured.out != ''  # Should output something

    def test_risk_assessment_workflow(self, test_db, mock_auth):
        """Test complete risk assessment workflow"""
        # Calculate risk score
        score = calculate_risk_score(
            'General Health Risk',
            age=25,
            conditions=[],
            allergies=[],
            latest_bmi=None
        )

        # Get risk factors
        factors = get_risk_factors(
            'General Health Risk',
            age=25,
            conditions=[],
            allergies=[],
            latest_bmi=None
        )

        # Generate recommendations
        recommendations = generate_risk_recommendations(
            'General Health Risk',
            score,
            factors
        )

        assert isinstance(score, int)
        assert isinstance(factors, list)
        assert isinstance(recommendations, list)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
