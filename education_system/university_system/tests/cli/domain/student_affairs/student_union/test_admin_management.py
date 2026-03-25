"""
Comprehensive tests for student_union administration/admin_management.py module.

Tests cover:
- Competition management
- Support groups administration
- Environmental reports
- Compliance reports
- Security audits
- Admin menu display
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.student_affairs.student_union.administration import admin_management

@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = Mock()
    cursor.fetchone = Mock(return_value=None)
    cursor.fetchall = Mock(return_value=[])
    cursor.execute = Mock()
    cursor.rowcount = 0
    cursor.lastrowid = 1
    return cursor

@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = Mock()
    conn.cursor = Mock(return_value=Mock())
    conn.commit = Mock()
    conn.close = Mock()
    return conn

@pytest.fixture
def mock_auth():
    """Create a mock authentication object."""
    auth = Mock()
    auth.current_user = {'id': 1, 'username': 'testuser'}
    auth.check_permission = Mock(return_value=True)
    auth.is_logged_in = Mock(return_value=True)
    return auth

class TestSetupPermissions:
    """Test permission setup functionality."""

    @patch('education_system.university_system.modules.domain.student_affairs.student_union.administration.admin_management.get_connection')
    def test_setup_student_union_permissions(self, mock_get_conn):
        """Test setting up student union permissions."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone = Mock(return_value=(1,))
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        admin_management.setup_student_union_permissions(None)

        # Verify permissions were created
        assert mock_cursor.execute.call_count > 0
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('education_system.university_system.modules.domain.student_affairs.student_union.administration.admin_management.get_connection')
    def test_setup_new_features_permissions(self, mock_get_conn):
        """Test setting up new features permissions."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone = Mock(return_value=(1,))
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        admin_management.setup_new_features_permissions(None)

        # Verify new permissions were created
        assert mock_cursor.execute.call_count > 0
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

class TestCompetitionAdmin:
    """Test competition administration functionality."""

    @patch('builtins.input', side_effect=['1', '6'])
    def test_manage_competition_admin_view_all(self, mock_input, mock_cursor, mock_conn):
        """Test viewing all competitions."""
        mock_cursor.fetchall.return_value = [
            (1, 'Test Competition', 'Sports', '2024-01-01', '2024-01-31', 'active', 5)
        ]

        admin_management.manage_competition_admin(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_cursor.fetchall.assert_called()

    @patch('builtins.input', side_effect=['2', '1', '3', '6'])
    def test_manage_competition_update_status(self, mock_input, mock_cursor, mock_conn):
        """Test updating competition status."""
        mock_cursor.fetchone.side_effect = [
            ('Test Competition', 'upcoming'),
            None
        ]

        admin_management.manage_competition_admin(mock_cursor, mock_conn)

        assert mock_cursor.execute.call_count >= 2
        mock_conn.commit.assert_called()

    @patch('builtins.input', side_effect=['3', '1', '6'])
    def test_view_competition_participants(self, mock_input, mock_cursor, mock_conn):
        """Test viewing competition participants."""
        mock_cursor.fetchone.side_effect = [
            ('Test Competition',),
        ]
        mock_cursor.fetchall.return_value = [
            ('Test Club', 'John', 'Doe', '2024-01-01', 95.5)
        ]

        admin_management.manage_competition_admin(mock_cursor, mock_conn)

        mock_cursor.fetchall.assert_called()

    @patch('builtins.input', side_effect=['4', '1', 'S123', '6'])
    def test_remove_participant(self, mock_input, mock_cursor, mock_conn):
        """Test removing a participant from competition."""
        mock_cursor.rowcount = 1

        admin_management.manage_competition_admin(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    @patch('builtins.input', side_effect=['5', '1', 'y', '6'])
    def test_delete_competition(self, mock_input, mock_cursor, mock_conn):
        """Test deleting a competition."""
        mock_cursor.fetchone.return_value = ('Test Competition',)

        admin_management.manage_competition_admin(mock_cursor, mock_conn)

        assert mock_cursor.execute.call_count >= 2
        mock_conn.commit.assert_called()

    @patch('builtins.input', side_effect=['5', '1', 'n', '6'])
    def test_delete_competition_cancelled(self, mock_input, mock_cursor, mock_conn):
        """Test cancelling competition deletion."""
        mock_cursor.fetchone.return_value = ('Test Competition',)

        admin_management.manage_competition_admin(mock_cursor, mock_conn)

        # Commit should not be called since deletion was cancelled
        assert mock_conn.commit.call_count == 0

    def test_manage_competition_admin_database_error(self, mock_cursor, mock_conn):
        """Test handling database errors."""
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        with patch('builtins.input', return_value='1'):
            with patch('builtins.print') as mock_print:
                admin_management.manage_competition_admin(mock_cursor, mock_conn)
                # Should print error message
                assert any('error' in str(call).lower() for call in mock_print.call_args_list)

class TestCompetitionReports:
    """Test competition reporting functionality."""

    @patch('builtins.input', return_value='1')
    def test_generate_participation_summary(self, mock_input, mock_cursor):
        """Test generating participation summary report."""
        mock_cursor.fetchall.return_value = [
            ('Test Competition', 'Sports', 'active', 5, 15)
        ]

        admin_management.generate_competition_reports(mock_cursor)

        mock_cursor.execute.assert_called()
        mock_cursor.fetchall.assert_called()

    @patch('builtins.input', return_value='2')
    def test_generate_club_performance_report(self, mock_input, mock_cursor):
        """Test generating club performance analysis."""
        mock_cursor.fetchall.return_value = [
            ('Test Club', 3, 10, 85.5, 2, 3)
        ]

        admin_management.generate_competition_reports(mock_cursor)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', return_value='3')
    def test_generate_individual_achievements(self, mock_input, mock_cursor):
        """Test generating individual student achievements."""
        mock_cursor.fetchall.return_value = [
            ('John', 'Doe', 5, 90.0, 2, 4, 1)
        ]

        admin_management.generate_competition_reports(mock_cursor)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', return_value='4')
    def test_generate_timeline_report(self, mock_input, mock_cursor):
        """Test generating competition timeline report."""
        mock_cursor.fetchall.return_value = [
            ('Test Competition', 'Sports', '2024-01-01', '2024-01-31', 'active', 5, 15)
        ]

        admin_management.generate_competition_reports(mock_cursor)

        mock_cursor.execute.assert_called()

class TestSupportGroupsAdmin:
    """Test support groups administration."""

    @patch('builtins.input', side_effect=['1', '6'])
    def test_view_all_support_groups(self, mock_input, mock_cursor, mock_conn):
        """Test viewing all support groups."""
        mock_cursor.fetchall.return_value = [
            (1, 'Test Group', 'Mental Health', 5, 10, 'John', 'Doe', 'active', '2024-01-01')
        ]

        admin_management.manage_support_groups_admin(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_cursor.fetchall.assert_called()

    @patch('builtins.input', side_effect=['2', '1', '6'])
    def test_review_group_safety(self, mock_input, mock_cursor, mock_conn):
        """Test reviewing group safety."""
        admin_management.manage_support_groups_admin(mock_cursor, mock_conn)

        # Should complete without errors
        assert True

    @patch('builtins.input', side_effect=['3', '1', '6'])
    def test_assign_facilitator_training(self, mock_input, mock_cursor, mock_conn):
        """Test assigning facilitator training."""
        mock_cursor.fetchone.return_value = ('Test Group', 'John', 'Doe')

        admin_management.manage_support_groups_admin(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', side_effect=['4', '6'])
    def test_crisis_intervention_protocols(self, mock_input, mock_cursor, mock_conn):
        """Test viewing crisis intervention protocols."""
        admin_management.manage_support_groups_admin(mock_cursor, mock_conn)

        # Should complete without errors
        assert True

    @patch('builtins.input', side_effect=['5', '1', '1', '6'])
    def test_suspend_group(self, mock_input, mock_cursor, mock_conn):
        """Test suspending a support group."""
        admin_management.manage_support_groups_admin(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

class TestEnvironmentalReports:
    """Test environmental reporting functionality."""

    @patch('builtins.input', return_value='1')
    def test_carbon_footprint_summary(self, mock_input, mock_cursor):
        """Test generating carbon footprint summary."""
        mock_cursor.fetchone.side_effect = [
            (10, 1500.0, 150.0, 85.0),
        ]
        mock_cursor.fetchall.return_value = [
            ('Test Event', 'Test Club', 95.0)
        ]

        admin_management.generate_environmental_reports(mock_cursor)

        assert mock_cursor.execute.call_count >= 2

    @patch('builtins.input', return_value='2')
    def test_waste_management_report(self, mock_input, mock_cursor):
        """Test generating waste management report."""
        mock_cursor.fetchone.return_value = (5, 100.0, 80.0, 80.0)

        admin_management.generate_environmental_reports(mock_cursor)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', return_value='3')
    def test_sustainability_trends(self, mock_input, mock_cursor):
        """Test generating sustainability trends report."""
        mock_cursor.fetchall.return_value = [
            ('2024-01', 85.0, 10),
            ('2024-02', 87.5, 12)
        ]

        admin_management.generate_environmental_reports(mock_cursor)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', return_value='4')
    def test_green_initiatives_impact(self, mock_input, mock_cursor):
        """Test generating green initiatives impact report."""
        mock_cursor.fetchall.return_value = [
            ('Green Initiatives', 5, 250)
        ]
        mock_cursor.fetchone.return_value = (15,)

        admin_management.generate_environmental_reports(mock_cursor)

        assert mock_cursor.execute.call_count >= 2

class TestComplianceReporting:
    """Test compliance reporting functionality."""

    @patch('builtins.open', new_callable=mock_open)
    def test_generate_compliance_report(self, mock_file, mock_cursor):
        """Test generating compliance report."""
        mock_cursor.fetchall.side_effect = [
            [(1, 'President', None, 'nomination', '2024-01-01', '2024-01-31')],
            [('John', 'Doe', 'President', 50.0)],
            [('approved', 5)]
        ]

        admin_management.generate_compliance_report(mock_cursor)

        mock_file.assert_called()
        assert mock_cursor.execute.call_count >= 3

    @patch('education_system.university_system.modules.domain.student_affairs.student_union.administration.admin_management.send_confirmation_email')
    @patch('education_system.university_system.modules.domain.student_affairs.student_union.administration.admin_management.render_template')
    def test_send_compliance_reminders(self, mock_render, mock_send_email, mock_cursor):
        """Test sending compliance reminders."""
        mock_cursor.fetchall.return_value = [
            ('S123', 'John', 'Doe', 'President', '2024-01-31')
        ]
        mock_render.return_value = ('Subject', 'Message body')
        mock_send_email.return_value = True

        admin_management.send_compliance_reminders(mock_cursor)

        mock_send_email.assert_called()

    @patch('education_system.university_system.modules.domain.student_affairs.student_union.administration.admin_management.send_confirmation_email')
    @patch('education_system.university_system.modules.domain.student_affairs.student_union.administration.admin_management.render_template')
    def test_send_compliance_reminders_no_candidates(self, mock_render, mock_send_email, mock_cursor):
        """Test sending reminders with no active candidates."""
        mock_cursor.fetchall.return_value = []

        admin_management.send_compliance_reminders(mock_cursor)

        mock_send_email.assert_not_called()

class TestSecurityAudits:
    """Test security audit functionality."""

    @patch('builtins.input', return_value='')
    def test_audit_trail_analysis(self, mock_input, mock_cursor):
        """Test audit trail analysis."""
        mock_cursor.fetchall.side_effect = [
            [('Election Created', 'President', '2024-01-01 10:00:00', 'System')],
            []
        ]
        mock_cursor.fetchone.side_effect = [(0,), (0,)]

        admin_management.audit_trail_analysis(mock_cursor)

        assert mock_cursor.execute.call_count >= 3

    @patch('builtins.input', return_value='')
    def test_database_security_scan(self, mock_input, mock_cursor):
        """Test database security scan."""
        mock_cursor.fetchall.side_effect = [
            [('users',), ('union_elections',), ('election_votes',)],
            [],  # Suspicious users
            []   # Weak passwords
        ]
        mock_cursor.fetchone.return_value = (10,)

        admin_management.database_security_scan(mock_cursor)

        assert mock_cursor.execute.call_count >= 4

    @patch('builtins.open', new_callable=mock_open)
    def test_generate_security_report(self, mock_file, mock_cursor, mock_auth):
        """Test generating security audit report."""
        admin_management.auth = mock_auth
        mock_cursor.fetchone.side_effect = [(5,), (2,), (100,)]

        admin_management.generate_security_report(mock_cursor)

        mock_file.assert_called()
        assert mock_cursor.execute.call_count >= 3

    @patch('builtins.open', new_callable=mock_open)
    def test_export_audit_logs(self, mock_file, mock_cursor):
        """Test exporting audit logs."""
        mock_cursor.fetchall.return_value = [
            ('vote_cast', 'S123', 1, '2024-01-01 10:00:00', 'Election vote')
        ]

        admin_management.export_audit_logs(mock_cursor)

        mock_file.assert_called()
        mock_cursor.execute.assert_called()

class TestVotingConfiguration:
    """Test voting configuration management."""

    @patch('builtins.open', new_callable=mock_open)
    def test_export_voting_configuration(self, mock_file, mock_cursor):
        """Test exporting voting configuration."""
        mock_cursor.fetchall.return_value = [
            ('max_votes', '1', 'Maximum votes per election')
        ]

        admin_management.export_voting_configuration(mock_cursor)

        mock_file.assert_called()
        mock_cursor.execute.assert_called()

    @patch('builtins.input', return_value='config.json')
    @patch('builtins.open', new_callable=mock_open, read_data='{"max_votes": {"value": "1", "description": "Max votes"}}')
    def test_import_voting_configuration(self, mock_file, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test importing voting configuration."""
        admin_management.auth = mock_auth

        admin_management.import_voting_configuration(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    @patch('builtins.input', return_value='nonexistent.json')
    def test_import_voting_configuration_file_not_found(self, mock_input, mock_cursor, mock_conn):
        """Test importing configuration with non-existent file."""
        with patch('builtins.print') as mock_print:
            admin_management.import_voting_configuration(mock_cursor, mock_conn)
            # Should print error message
            assert any('not found' in str(call).lower() for call in mock_print.call_args_list)

class TestSampleData:
    """Test sample data insertion."""

    @patch('education_system.university_system.modules.domain.student_affairs.student_union.administration.admin_management.get_connection')
    def test_insert_sample_data(self, mock_get_conn):
        """Test inserting sample data for new features."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        admin_management.insert_sample_data_for_new_features()

        assert mock_cursor.executemany.call_count >= 3
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

class TestAdminMenu:
    """Test admin menu display functionality."""

    @patch('builtins.input', side_effect=[str(i) for i in range(1, 10)])
    def test_display_admin_menu_no_permissions(self, mock_input, mock_auth):
        """Test admin menu with no permissions."""
        mock_auth.check_permission.return_value = False
        admin_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            admin_management.display_admin_menu()
            # Should print permission error
            assert any('permission' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['5'])
    @patch('education_system.university_system.modules.domain.student_affairs.student_union.administration.admin_management.get_connection')
    def test_display_admin_menu_with_permissions(self, mock_get_conn, mock_input, mock_auth):
        """Test admin menu with all permissions."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_auth.check_permission.return_value = True
        admin_management.auth = mock_auth

        admin_management.display_admin_menu()

        # Should reach return statement
        assert True

class TestAuthSetup:
    """Test authentication setup functionality."""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance."""
        admin_management.set_auth(mock_auth)

        assert admin_management.auth == mock_auth

    def test_set_auth_with_has_auth(self, mock_auth):
        """Test setting auth when HAS_AUTH is True."""
        original_has_auth = admin_management.HAS_AUTH
        admin_management.HAS_AUTH = True

        with patch('education_system.university_system.modules.domain.student_affairs.student_union.administration.admin_management.set_auth_instance') as mock_set:
            admin_management.set_auth(mock_auth)
            mock_set.assert_called_once_with(mock_auth)

        admin_management.HAS_AUTH = original_has_auth

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_database_results(self, mock_cursor):
        """Test handling of empty database results."""
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        with patch('builtins.input', return_value='1'):
            with patch('builtins.print'):
                admin_management.generate_competition_reports(mock_cursor)
                # Should handle empty results gracefully
                assert True

    def test_database_error_handling(self, mock_cursor, mock_conn):
        """Test handling of database errors."""
        mock_cursor.execute.side_effect = sqlite3.Error("Test error")

        with patch('builtins.input', return_value='1'):
            with patch('builtins.print') as mock_print:
                admin_management.manage_competition_admin(mock_cursor, mock_conn)
                # Should print error message
                assert any('error' in str(call).lower() for call in mock_print.call_args_list)

    def test_invalid_input_handling(self, mock_cursor, mock_conn):
        """Test handling of invalid user input."""
        with patch('builtins.input', side_effect=['invalid', '99', '6']):
            with patch('builtins.print'):
                admin_management.manage_competition_admin(mock_cursor, mock_conn)
                # Should handle invalid input gracefully
                assert True
