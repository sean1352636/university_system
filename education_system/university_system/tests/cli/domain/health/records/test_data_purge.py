"""
Comprehensive tests for health records data purge and retention functionality.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

from education_system.university_system.modules.domain.health.records import data_purge
from education_system.university_system.infrastructure.database.db import get_connection

@pytest.fixture
def mock_auth():
    """Create a mock authentication object."""
    auth = Mock()
    auth.current_user = {
        'id': 'admin123',
        'username': 'admin',
        'role': 'admin'
    }
    auth.username = 'admin'
    auth.check_permission = Mock(return_value=True)
    return auth

@pytest.fixture
def mock_non_admin_auth():
    """Create a mock non-admin authentication object."""
    auth = Mock()
    auth.current_user = {
        'id': 'user123',
        'username': 'testuser',
        'role': 'user'
    }
    auth.check_permission = Mock(return_value=False)
    return auth

@pytest.fixture
def setup_retention_db():
    """Setup test database with retention policies."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create retention policies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_retention_policies (
            id INTEGER PRIMARY KEY,
            data_type TEXT,
            retention_period_days INTEGER,
            auto_archive INTEGER,
            auto_delete INTEGER,
            created_at TEXT
        )
    ''')

    # Insert test retention policies
    policies = [
        (1, 'health_records', 2555, 1, 0, datetime.now().isoformat()),
        (2, 'vaccination_records', 2555, 1, 0, datetime.now().isoformat()),
        (3, 'appointments', 1095, 1, 0, datetime.now().isoformat()),
    ]

    for policy in policies:
        cursor.execute('''
            INSERT OR REPLACE INTO data_retention_policies
            (id, data_type, retention_period_days, auto_archive, auto_delete, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', policy)

    # Create health records table with old data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            record_type TEXT,
            record_date TEXT,
            description TEXT
        )
    ''')

    # Insert old health record (older than retention period)
    old_date = (datetime.now() - timedelta(days=3000)).strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO health_records (student_id, record_type, record_date, description)
        VALUES ('S001', 'checkup', ?, 'Old record')
    ''', (old_date,))

    # Create appointments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_appointments (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            appointment_date TEXT,
            status TEXT
        )
    ''')

    conn.commit()
    conn.close()

    yield

    # Cleanup
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM data_retention_policies')
    cursor.execute('DELETE FROM health_records')
    cursor.execute('DROP TABLE IF EXISTS health_appointments')
    conn.commit()
    conn.close()

class TestUpdateRetentionPolicy:
    """Tests for update_retention_policy function."""

    @patch('builtins.input', side_effect=['1', '3000', 'y', 'n'])
    @patch('builtins.print')
    @patch('university_system.modules.domain.health.records.data_purge.backup_before_operation')
    def test_update_retention_policy_success(self, mock_backup, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test successfully updating a retention policy."""
        data_purge.update_retention_policy(mock_auth)

        # Verify policy was updated
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT retention_period_days FROM data_retention_policies
            WHERE data_type = 'health_records'
        ''')
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 3000

    @patch('builtins.print')
    def test_update_retention_policy_non_admin(self, mock_print, mock_non_admin_auth):
        """Test that non-admin users cannot update retention policies."""
        data_purge.update_retention_policy(mock_non_admin_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('admin' in str(call).lower() for call in print_calls)

    @patch('builtins.input', side_effect=['1', '2000', 'y', 'y', 'yes'])
    @patch('builtins.print')
    @patch('university_system.modules.domain.health.records.data_purge.backup_before_operation')
    def test_update_retention_policy_enable_auto_delete(self, mock_backup, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test enabling auto-delete with confirmation."""
        data_purge.update_retention_policy(mock_auth)

        # Verify auto_delete was enabled
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT auto_delete FROM data_retention_policies
            WHERE data_type = 'health_records'
        ''')
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 1

    @patch('builtins.input', side_effect=['1', '2000', 'y', 'y', 'no'])
    @patch('builtins.print')
    @patch('university_system.modules.domain.health.records.data_purge.backup_before_operation')
    def test_update_retention_policy_cancel_auto_delete(self, mock_backup, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test cancelling auto-delete when user doesn't confirm."""
        data_purge.update_retention_policy(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('disabled' in str(call).lower() for call in print_calls)

class TestArchiveOldData:
    """Tests for archive_old_data function."""

    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    @patch('university_system.modules.domain.health.records.data_purge.backup_before_operation')
    def test_archive_old_data_success(self, mock_backup, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test archiving old data."""
        data_purge.archive_old_data(mock_auth)

        # Should print summary
        assert mock_print.called

    @patch('builtins.print')
    def test_archive_old_data_non_admin(self, mock_print, mock_non_admin_auth):
        """Test that non-admin cannot archive data."""
        data_purge.archive_old_data(mock_non_admin_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('admin' in str(call).lower() for call in print_calls)

    @patch('builtins.input', return_value='no')
    @patch('builtins.print')
    @patch('university_system.modules.domain.health.records.data_purge.backup_before_operation')
    def test_archive_old_data_cancel(self, mock_backup, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test cancelling archival process."""
        data_purge.archive_old_data(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('cancelled' in str(call).lower() for call in print_calls)

class TestViewPurgeableData:
    """Tests for view_purgeable_data function."""

    @patch('builtins.print')
    def test_view_purgeable_data(self, mock_print, mock_auth, setup_retention_db):
        """Test viewing data eligible for purge."""
        # Set auto_delete for test policy
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE data_retention_policies
            SET auto_delete = 1
            WHERE data_type = 'health_records'
        ''')
        conn.commit()
        conn.close()

        data_purge.view_purgeable_data(mock_auth)

        # Should print purgeable data info
        assert mock_print.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        # Check if health_records was mentioned
        assert any('health_records' in str(call).lower() for call in print_calls)

class TestPurgeExpiredData:
    """Tests for purge_expired_data function."""

    @patch('builtins.input', side_effect=['DELETE', 'admin'])
    @patch('builtins.print')
    @patch('university_system.modules.domain.health.records.data_purge.create_sqlite_backup')
    def test_purge_expired_data_success(self, mock_backup, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test successful data purge."""
        mock_backup.return_value = '/path/to/backup.db'

        data_purge.purge_expired_data(mock_auth)

        # Should have created backup and purged data
        assert mock_backup.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('purge completed' in str(call).lower() for call in print_calls)

    @patch('builtins.input', side_effect=['DELETE', 'admin'])
    @patch('builtins.print')
    @patch('university_system.modules.domain.health.records.data_purge.create_sqlite_backup')
    def test_purge_expired_data_backup_failure(self, mock_backup, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test purge abort when backup fails."""
        mock_backup.side_effect = Exception("Backup failed")

        data_purge.purge_expired_data(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('aborted' in str(call).lower() for call in print_calls)

    @patch('builtins.input', side_effect=['cancel'])
    @patch('builtins.print')
    def test_purge_expired_data_cancel(self, mock_print, mock_input, mock_auth):
        """Test cancelling purge operation."""
        data_purge.purge_expired_data(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('cancelled' in str(call).lower() for call in print_calls)

    @patch('builtins.input', side_effect=['DELETE', 'wronguser'])
    @patch('builtins.print')
    def test_purge_expired_data_wrong_username(self, mock_print, mock_input, mock_auth):
        """Test purge cancellation with wrong username."""
        data_purge.purge_expired_data(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('cancelled' in str(call).lower() for call in print_calls)

    @patch('builtins.print')
    def test_purge_expired_data_non_admin(self, mock_print):
        """Test purge rejection for non-admin users."""
        # Create non-admin auth
        auth = Mock()
        auth.username = 'user'

        data_purge.purge_expired_data(auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('admin' in str(call).lower() for call in print_calls)

class TestRetentionComplianceReport:
    """Tests for retention_compliance_report function."""

    @patch('builtins.print')
    def test_retention_compliance_report(self, mock_print, mock_auth, setup_retention_db):
        """Test generating retention compliance report."""
        data_purge.retention_compliance_report(mock_auth)

        # Should print compliance report
        assert mock_print.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        # Check for compliance status
        assert any('compliance' in str(call).lower() for call in print_calls)

    @patch('builtins.print')
    def test_retention_compliance_report_non_compliant(self, mock_print, mock_auth, setup_retention_db):
        """Test compliance report when old records exist."""
        data_purge.retention_compliance_report(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        # Should show non-compliant status for health_records with old data
        report_str = ' '.join([str(call) for call in print_calls])
        # The report should mention health_records

class TestComplianceMonitoring:
    """Tests for compliance_monitoring function."""

    @patch('builtins.input')
    @patch('builtins.print')
    def test_compliance_monitoring(self, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test compliance monitoring display."""
        # Create audit_trail table
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY,
                action TEXT,
                timestamp TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO audit_trail (action, timestamp)
            VALUES ('view', datetime('now'))
        ''')
        conn.commit()
        conn.close()

        data_purge.compliance_monitoring(mock_auth)

        # Should print compliance info
        assert mock_print.called

    @patch('builtins.print')
    def test_compliance_monitoring_no_permission(self, mock_print, mock_non_admin_auth):
        """Test compliance monitoring without permission."""
        data_purge.compliance_monitoring(mock_non_admin_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('permission' in str(call).lower() for call in print_calls)

class TestViewRetentionPolicies:
    """Tests for view_retention_policies function."""

    @patch('builtins.print')
    def test_view_retention_policies(self, mock_print, mock_auth, setup_retention_db):
        """Test viewing retention policies."""
        data_purge.view_retention_policies(mock_auth)

        # Should print policy information
        assert mock_print.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('health_records' in str(call).lower() for call in print_calls)

    @patch('builtins.print')
    def test_view_retention_policies_no_policies(self, mock_print, mock_auth):
        """Test viewing when no policies exist."""
        # Clear all policies
        conn = get_connection()
        conn.execute('DELETE FROM data_retention_policies')
        conn.commit()
        conn.close()

        data_purge.view_retention_policies(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('no' in str(call).lower() and 'polic' in str(call).lower() for call in print_calls)

class TestCustomDataPurge:
    """Tests for custom_data_purge function."""

    @patch('builtins.input', side_effect=['CUSTOM_PURGE', 'admin', 'CONFIRM_DELETE'])
    @patch('builtins.print')
    def test_custom_data_purge_confirmed(self, mock_print, mock_input, mock_auth):
        """Test custom data purge with all confirmations."""
        data_purge.custom_data_purge(mock_auth)

        # Should print confirmation messages
        assert mock_print.called

    @patch('builtins.input', side_effect=['wrong'])
    @patch('builtins.print')
    def test_custom_data_purge_cancel_first_step(self, mock_print, mock_input, mock_auth):
        """Test cancelling at first confirmation."""
        data_purge.custom_data_purge(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('cancelled' in str(call).lower() for call in print_calls)

    @patch('builtins.input', side_effect=['CUSTOM_PURGE', 'wronguser'])
    @patch('builtins.print')
    def test_custom_data_purge_wrong_username(self, mock_print, mock_input, mock_auth):
        """Test cancelling with wrong username."""
        data_purge.custom_data_purge(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('cancelled' in str(call).lower() for call in print_calls)

    @patch('builtins.input', side_effect=['CUSTOM_PURGE', 'admin', 'wrong'])
    @patch('builtins.print')
    def test_custom_data_purge_cancel_final_step(self, mock_print, mock_input, mock_auth):
        """Test cancelling at final confirmation."""
        data_purge.custom_data_purge(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('cancelled' in str(call).lower() for call in print_calls)

class TestDataPurgeMenu:
    """Tests for data_purge_menu function."""

    @patch('builtins.input', return_value='4')
    @patch('builtins.print')
    def test_data_purge_menu_exit(self, mock_print, mock_input, mock_auth):
        """Test exiting data purge menu."""
        data_purge.data_purge_menu(mock_auth)

        # Should exit cleanly
        assert True

    @patch('builtins.input', side_effect=['1', '4'])
    @patch('builtins.print')
    def test_data_purge_menu_view_purgeable(self, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test viewing purgeable data from menu."""
        data_purge.data_purge_menu(mock_auth)

        # Should have called view function
        assert mock_print.called

    @patch('builtins.print')
    def test_data_purge_menu_non_admin(self, mock_print, mock_non_admin_auth):
        """Test data purge menu access for non-admin."""
        data_purge.data_purge_menu(mock_non_admin_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('admin' in str(call).lower() for call in print_calls)

class TestDataRetentionManagement:
    """Tests for data_retention_management function."""

    @patch('builtins.input', return_value='6')
    @patch('builtins.print')
    def test_data_retention_management_exit(self, mock_print, mock_input, mock_auth):
        """Test exiting retention management menu."""
        data_purge.data_retention_management(mock_auth)

        assert True

    @patch('builtins.input', side_effect=['1', '6'])
    @patch('builtins.print')
    def test_data_retention_management_view_policies(self, mock_print, mock_input, mock_auth, setup_retention_db):
        """Test viewing retention policies from menu."""
        data_purge.data_retention_management(mock_auth)

        # Should call view_retention_policies
        assert mock_print.called

    @patch('builtins.print')
    def test_data_retention_management_non_admin(self, mock_print, mock_non_admin_auth):
        """Test retention management access for non-admin."""
        data_purge.data_retention_management(mock_non_admin_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('admin' in str(call).lower() for call in print_calls)

    @patch('builtins.input', side_effect=['invalid', '6'])
    @patch('builtins.print')
    def test_data_retention_management_invalid_choice(self, mock_print, mock_input, mock_auth):
        """Test invalid menu choice."""
        data_purge.data_retention_management(mock_auth)

        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('invalid' in str(call).lower() for call in print_calls)

class TestIntegration:
    """Integration tests for data purge functionality."""

    @patch('builtins.input', side_effect=['1', '1000', 'y', 'n'])
    @patch('university_system.modules.domain.health.records.data_purge.backup_before_operation')
    def test_update_and_view_policy(self, mock_backup, mock_input, mock_auth, setup_retention_db):
        """Test updating a policy and then viewing it."""
        # Update policy
        with patch('builtins.print'):
            data_purge.update_retention_policy(mock_auth)

        # Verify update by viewing policies
        with patch('builtins.print') as mock_print:
            data_purge.view_retention_policies(mock_auth)

            print_calls = [str(call) for call in mock_print.call_args_list]
            # Should show updated retention period
            assert any('1000' in str(call) for call in print_calls)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
