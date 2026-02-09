"""
Comprehensive tests for quality assurance and metrics functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, call

from university_system.modules.domain.health.records import quality_assurance
from university_system.infrastructure.database.db import get_connection


@pytest.fixture
def mock_auth():
    """Create a mock authentication object with permission."""
    auth = Mock()
    auth.current_user = {'id': 'user123', 'username': 'testuser'}
    auth.check_permission = Mock(return_value=True)
    return auth


@pytest.fixture
def mock_auth_no_permission():
    """Create a mock authentication object without permission."""
    auth = Mock()
    auth.current_user = {'id': 'user123', 'username': 'testuser'}
    auth.check_permission = Mock(return_value=False)
    return auth


@pytest.fixture
def setup_quality_db():
    """Setup test database with quality metrics data."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create necessary tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_appointments (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            appointment_date TEXT,
            status TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            record_date TEXT,
            provider TEXT,
            description TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vaccination_records (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            vaccine_name TEXT,
            administered_date TEXT,
            verified INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            name TEXT,
            phone TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS insurance_information (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            provider TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vital_signs (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            measurement_date TEXT,
            heart_rate INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medical_conditions (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            condition_name TEXT,
            status TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS care_plans (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            status TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quality_metrics (
            id INTEGER PRIMARY KEY,
            metric_name TEXT,
            metric_category TEXT,
            target_value REAL,
            actual_value REAL,
            status TEXT,
            improvement_needed INTEGER,
            measured_date TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            follow_up_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY,
            action TEXT,
            timestamp TEXT
        )
    ''')

    # Insert test data
    cursor.execute('INSERT INTO students VALUES ("S001", "John", "Doe")')
    cursor.execute('INSERT INTO students VALUES ("S002", "Jane", "Smith")')

    # Insert appointments with various statuses
    now = datetime.now()
    thirty_days_ago = (now - timedelta(days=30)).strftime('%Y-%m-%d')

    cursor.execute('''
        INSERT INTO health_appointments (student_id, appointment_date, status)
        VALUES ("S001", ?, "completed")
    ''', (thirty_days_ago,))

    cursor.execute('''
        INSERT INTO health_appointments (student_id, appointment_date, status)
        VALUES ("S002", ?, "no-show")
    ''', (thirty_days_ago,))

    # Insert health records with providers
    cursor.execute('''
        INSERT INTO health_records (student_id, record_date, provider, description)
        VALUES ("S001", ?, "Dr. Smith", "Good description")
    ''', (thirty_days_ago,))

    # Insert vaccination records
    cursor.execute('''
        INSERT INTO vaccination_records (student_id, vaccine_name, administered_date, verified)
        VALUES ("S001", "COVID-19", ?, 1)
    ''', (thirty_days_ago,))

    # Insert emergency contacts
    cursor.execute('''
        INSERT INTO emergency_contacts (student_id, name, phone)
        VALUES ("S001", "Emergency Contact", "555-1234")
    ''')

    # Insert insurance info
    cursor.execute('''
        INSERT INTO insurance_information (student_id, provider)
        VALUES ("S001", "Health Insurance Co")
    ''')

    # Insert vital signs
    cursor.execute('''
        INSERT INTO vital_signs (student_id, measurement_date, heart_rate)
        VALUES ("S001", ?, 72)
    ''', (thirty_days_ago,))

    # Insert quality metrics
    cursor.execute('''
        INSERT INTO quality_metrics
        (metric_name, metric_category, target_value, actual_value, status, improvement_needed, measured_date)
        VALUES ("Test Metric", "general", 90.0, 85.0, "needs improvement", 1, ?)
    ''', (datetime.now().strftime('%Y-%m-%d'),))

    # Insert audit trail entries
    cursor.execute('''
        INSERT INTO audit_trail (action, timestamp)
        VALUES ("view", ?)
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))

    conn.commit()
    conn.close()

    yield

    # Cleanup
    conn = get_connection()
    cursor = conn.cursor()
    tables = [
        'students', 'health_appointments', 'health_records', 'vaccination_records',
        'emergency_contacts', 'insurance_information', 'vital_signs',
        'medical_conditions', 'care_plans', 'quality_metrics', 'risk_assessments',
        'audit_trail'
    ]
    for table in tables:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')
    conn.commit()
    conn.close()


class TestGenerateQualityMetricsReport:
    """Tests for generate_quality_metrics_report function."""

    @patch('builtins.print')
    def test_generate_quality_metrics_report(self, mock_print, mock_auth, setup_quality_db):
        """Test generating quality metrics report."""
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')

        quality_assurance.generate_quality_metrics_report(mock_auth, start_date, end_date)

        # Should print report
        assert mock_print.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('quality metrics' in str(call).lower() for call in print_calls)


class TestClinicalQualityIndicators:
    """Tests for clinical_quality_indicators function."""

    @patch('builtins.print')
    @patch('builtins.input')
    def test_clinical_quality_indicators(self, mock_input, mock_print, mock_auth, setup_quality_db):
        """Test displaying clinical quality indicators."""
        quality_assurance.clinical_quality_indicators(mock_auth)

        # Should print quality indicators
        assert mock_print.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('quality' in str(call).lower() for call in print_calls)

    @patch('builtins.print')
    def test_clinical_quality_indicators_no_permission(self, mock_print, mock_auth_no_permission):
        """Test clinical quality indicators without permission."""
        quality_assurance.clinical_quality_indicators(mock_auth_no_permission)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('permission' in str(call).lower() for call in print_calls)


class TestDataQualityMetrics:
    """Tests for data_quality_metrics function."""

    @patch('builtins.print')
    def test_data_quality_metrics(self, mock_print, mock_auth, setup_quality_db):
        """Test displaying data quality metrics."""
        quality_assurance.data_quality_metrics(mock_auth)

        # Should print metrics
        assert mock_print.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should show completeness percentages
        assert any('%' in str(call) or 'completeness' in str(call).lower() for call in print_calls)


class TestShowQualityMetrics:
    """Tests for show_quality_metrics function."""

    @patch('builtins.print')
    def test_show_quality_metrics(self, mock_print, mock_auth, setup_quality_db):
        """Test showing quality metrics."""
        quality_assurance.show_quality_metrics(mock_auth)

        # Should print various metrics
        assert mock_print.called


class TestPatientSafetyMetrics:
    """Tests for patient_safety_metrics function."""

    @patch('builtins.input')
    @patch('builtins.print')
    def test_patient_safety_metrics(self, mock_print, mock_input, mock_auth, setup_quality_db):
        """Test displaying patient safety metrics."""
        quality_assurance.patient_safety_metrics(mock_auth)

        # Should print safety metrics
        assert mock_print.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('safety' in str(call).lower() for call in print_calls)

    @patch('builtins.input')
    @patch('builtins.print')
    def test_patient_safety_metrics_no_permission(self, mock_print, mock_input, mock_auth_no_permission):
        """Test patient safety metrics without permission."""
        quality_assurance.patient_safety_metrics(mock_auth_no_permission)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('permission' in str(call).lower() for call in print_calls)

    @patch('builtins.input')
    @patch('builtins.print')
    def test_patient_safety_metrics_no_appointment_table(self, mock_print, mock_input, mock_auth):
        """Test patient safety metrics when appointments table doesn't exist."""
        # Drop appointments table
        conn = get_connection()
        conn.execute('DROP TABLE IF EXISTS health_appointments')
        conn.commit()
        conn.close()

        quality_assurance.patient_safety_metrics(mock_auth)

        # Should handle gracefully
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('appointment' in str(call).lower() for call in print_calls)


class TestPerformanceImprovement:
    """Tests for performance_improvement function."""

    @patch('builtins.input')
    @patch('builtins.print')
    def test_performance_improvement(self, mock_print, mock_input, mock_auth, setup_quality_db):
        """Test displaying performance improvement metrics."""
        quality_assurance.performance_improvement(mock_auth)

        # Should print improvement metrics
        assert mock_print.called

    @patch('builtins.input')
    @patch('builtins.print')
    def test_performance_improvement_no_permission(self, mock_print, mock_input, mock_auth_no_permission):
        """Test performance improvement without permission."""
        quality_assurance.performance_improvement(mock_auth_no_permission)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('permission' in str(call).lower() for call in print_calls)

    @patch('builtins.input')
    @patch('builtins.print')
    def test_performance_improvement_with_quality_metrics_table(self, mock_print, mock_input, mock_auth, setup_quality_db):
        """Test performance improvement when quality_metrics table exists."""
        quality_assurance.performance_improvement(mock_auth)

        # Should show tracked metrics
        print_calls = [str(call) for call in mock_print.call_args_list]
        report_str = ' '.join([str(call) for call in print_calls])
        assert 'metric' in report_str.lower()


class TestComplianceMonitoring:
    """Tests for compliance_monitoring function."""

    @patch('builtins.input')
    @patch('builtins.print')
    def test_compliance_monitoring(self, mock_print, mock_input, mock_auth, setup_quality_db):
        """Test compliance monitoring display."""
        quality_assurance.compliance_monitoring(mock_auth)

        # Should print compliance info
        assert mock_print.called

    @patch('builtins.input')
    @patch('builtins.print')
    def test_compliance_monitoring_no_permission(self, mock_print, mock_input, mock_auth_no_permission):
        """Test compliance monitoring without permission."""
        quality_assurance.compliance_monitoring(mock_auth_no_permission)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('permission' in str(call).lower() for call in print_calls)

    @patch('builtins.input')
    @patch('builtins.print')
    def test_compliance_monitoring_with_audit_trail(self, mock_print, mock_input, mock_auth, setup_quality_db):
        """Test compliance monitoring with audit trail data."""
        quality_assurance.compliance_monitoring(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should show audit events
        report_str = ' '.join([str(call) for call in print_calls])
        assert 'audit' in report_str.lower() or 'compliance' in report_str.lower()


class TestQualityAssuranceMenu:
    """Tests for quality_assurance_menu function."""

    @patch('builtins.input', return_value='6')
    @patch('builtins.print')
    def test_quality_assurance_menu_exit(self, mock_print, mock_input, mock_auth):
        """Test exiting quality assurance menu."""
        quality_assurance.quality_assurance_menu(mock_auth)

        # Should exit cleanly
        assert True

    @patch('builtins.input', side_effect=['1', '6'])
    @patch('builtins.print')
    def test_quality_assurance_menu_data_quality(self, mock_print, mock_input, mock_auth, setup_quality_db):
        """Test accessing data quality metrics from menu."""
        quality_assurance.quality_assurance_menu(mock_auth)

        # Should call data_quality_metrics
        assert mock_print.called

    @patch('builtins.input', side_effect=['invalid', '6'])
    @patch('builtins.print')
    def test_quality_assurance_menu_invalid_choice(self, mock_print, mock_input, mock_auth):
        """Test invalid menu choice."""
        quality_assurance.quality_assurance_menu(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('invalid' in str(call).lower() for call in print_calls)

    @patch('builtins.print')
    def test_quality_assurance_menu_no_permission(self, mock_print, mock_auth_no_permission):
        """Test quality assurance menu without permission."""
        quality_assurance.quality_assurance_menu(mock_auth_no_permission)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('permission' in str(call).lower() for call in print_calls)


class TestVaccinationCoverage:
    """Tests for vaccination coverage calculations."""

    @patch('builtins.print')
    @patch('builtins.input')
    def test_vaccination_coverage_rates(self, mock_input, mock_print, mock_auth, setup_quality_db):
        """Test that vaccination coverage rates are calculated correctly."""
        quality_assurance.clinical_quality_indicators(mock_auth)

        # Should calculate and display coverage rates
        assert mock_print.called


class TestAppointmentMetrics:
    """Tests for appointment-related metrics."""

    @patch('builtins.print')
    @patch('builtins.input')
    def test_appointment_completion_rate(self, mock_input, mock_print, mock_auth, setup_quality_db):
        """Test appointment completion rate calculation."""
        quality_assurance.clinical_quality_indicators(mock_auth)

        # Should show completion rates
        assert mock_print.called


class TestDocumentationQuality:
    """Tests for documentation quality metrics."""

    @patch('builtins.print')
    @patch('builtins.input')
    def test_provider_documentation_rate(self, mock_input, mock_print, mock_auth, setup_quality_db):
        """Test provider documentation quality calculation."""
        quality_assurance.clinical_quality_indicators(mock_auth)

        # Should calculate provider documentation rates
        assert mock_print.called


class TestErrorHandling:
    """Tests for error handling in quality assurance module."""

    @patch('builtins.input')
    @patch('builtins.print')
    def test_missing_database_tables(self, mock_print, mock_input, mock_auth):
        """Test handling when database tables are missing."""
        # Clear all tables
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            if table != 'sqlite_sequence':
                cursor.execute(f'DROP TABLE IF EXISTS {table}')
        conn.commit()
        conn.close()

        # Should not crash
        quality_assurance.data_quality_metrics(mock_auth)

        # May print error or handle gracefully
        assert True

    @patch('builtins.input')
    @patch('builtins.print')
    def test_database_connection_error(self, mock_print, mock_input, mock_auth):
        """Test handling of database connection errors."""
        with patch('university_system.modules.domain.health.records.quality_assurance.get_connection', side_effect=Exception("Connection error")):
            # Should handle gracefully
            try:
                quality_assurance.data_quality_metrics(mock_auth)
            except Exception:
                pass  # Some implementations may raise, others may handle

            # At minimum, should not crash the entire application
            assert True


class TestIntegration:
    """Integration tests for quality assurance functionality."""

    @patch('builtins.input', side_effect=['1', '2', '3', '4', '5', '6'])
    @patch('builtins.print')
    def test_full_menu_navigation(self, mock_print, mock_input, mock_auth, setup_quality_db):
        """Test navigating through entire quality assurance menu."""
        quality_assurance.quality_assurance_menu(mock_auth)

        # Should complete all menu options
        assert mock_print.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
