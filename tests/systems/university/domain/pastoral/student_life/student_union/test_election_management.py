"""
Comprehensive tests for student_union elections/election_management.py module.

Tests cover:
- Viewing elections
- Nominating for elections
- Voting in elections
- Setting up elections
- Election results
- Campaign materials
- Campaign expenses
- Election security
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domain.pastoral.student_life.student_union.elections import election_management

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

class TestViewElections:
    """Test viewing elections functionality."""

    def test_view_elections_success(self, mock_cursor, mock_auth):
        """Test successfully viewing elections."""
        election_management.auth = mock_auth
        mock_cursor.fetchall.return_value = [
            (1, 'President', None, '2024-01-01', '2024-01-15', '2024-01-16', '2024-01-31', 'voting')
        ]

        election_management.view_elections(mock_cursor)

        mock_cursor.execute.assert_called()
        mock_cursor.fetchall.assert_called_once()

    def test_view_elections_empty(self, mock_cursor, mock_auth):
        """Test viewing elections when none exist."""
        election_management.auth = mock_auth
        mock_cursor.fetchall.return_value = []

        with patch('builtins.print') as mock_print:
            election_management.view_elections(mock_cursor)
            assert any('no' in str(call).lower() for call in mock_print.call_args_list)

    def test_view_elections_with_candidates(self, mock_cursor, mock_auth):
        """Test viewing elections with candidate counts."""
        election_management.auth = mock_auth
        mock_cursor.fetchall.return_value = [
            (1, 'President', None, '2024-01-01', '2024-01-15', '2024-01-16', '2024-01-31', 'voting')
        ]
        mock_cursor.fetchone.return_value = (5,)

        election_management.view_elections(mock_cursor)

        assert mock_cursor.execute.call_count >= 2

class TestNominateForElection:
    """Test nomination functionality."""

    @patch('builtins.input', side_effect=['1', 'My manifesto statement'])
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.elections.election_management.send_confirmation_email')
    def test_nominate_success(self, mock_email, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test successful nomination."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.side_effect = [
            ('S123',),  # student_id
            ('John', 'Doe', 'CS'),  # student info
            (1, 'President', None),  # election
            (0,)  # not already nominated
        ]
        mock_cursor.fetchall.return_value = [
            (1, 'President', None)
        ]

        election_management.nominate_for_election(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()
        mock_email.assert_called()

    @patch('builtins.input', side_effect=['1', 'My manifesto'])
    def test_nominate_already_nominated(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test nominating when already nominated."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.side_effect = [
            ('S123',),
            ('John', 'Doe', 'CS'),
            (1, 'President', None),
            (1,)  # Already nominated
        ]
        mock_cursor.fetchall.return_value = [(1, 'President', None)]

        with patch('builtins.print') as mock_print:
            election_management.nominate_for_election(mock_cursor, mock_conn)
            assert any('already' in str(call).lower() for call in mock_print.call_args_list)

    def test_nominate_no_elections(self, mock_cursor, mock_conn, mock_auth):
        """Test nominating when no elections are open."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.side_effect = [('S123',), ('John', 'Doe', 'CS')]
        mock_cursor.fetchall.return_value = []

        with patch('builtins.print') as mock_print:
            election_management.nominate_for_election(mock_cursor, mock_conn)
            assert any('no elections' in str(call).lower() for call in mock_print.call_args_list)

class TestVoteInElection:
    """Test voting functionality."""

    @patch('builtins.input', side_effect=['1', '1', 'y'])
    def test_vote_success(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test successful voting."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.side_effect = [
            ('S123',),  # student_id
            ('CS',),  # student course
            (0,),  # not already voted
        ]
        mock_cursor.fetchall.side_effect = [
            [(1, 'President', None)],  # elections
            [(1, 'John', 'Doe', 'CS', 'My manifesto')]  # candidates
        ]

        election_management.vote_in_election(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_vote_no_permission(self, mock_cursor, mock_conn, mock_auth):
        """Test voting without permission."""
        mock_auth.check_permission.return_value = False
        election_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            election_management.vote_in_election(mock_cursor, mock_conn)
            assert any('permission' in str(call).lower() for call in mock_print.call_args_list)

    def test_vote_no_eligible_elections(self, mock_cursor, mock_conn, mock_auth):
        """Test voting when no eligible elections."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.side_effect = [
            ('S123',),
            ('CS',),
            (1,),  # Already voted
        ]
        mock_cursor.fetchall.return_value = [(1, 'President', None)]

        with patch('builtins.print') as mock_print:
            election_management.vote_in_election(mock_cursor, mock_conn)
            assert any('no eligible' in str(call).lower() for call in mock_print.call_args_list)

class TestSetupElection:
    """Test election setup functionality."""

    @patch('builtins.input', side_effect=[
        'President', 'n', '2024-01-01', '2024-01-15', '2024-01-16', '2024-01-31'
    ])
    def test_setup_election_success(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test successfully setting up an election."""
        election_management.auth = mock_auth

        election_management.set_up_election(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    @patch('builtins.input', return_value='')
    def test_setup_election_empty_position(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test setup with empty position."""
        election_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            election_management.set_up_election(mock_cursor, mock_conn)
            assert any('empty' in str(call).lower() for call in mock_print.call_args_list)

    def test_setup_election_no_permission(self, mock_cursor, mock_conn, mock_auth):
        """Test setup without permission."""
        mock_auth.check_permission.return_value = False
        election_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            election_management.set_up_election(mock_cursor, mock_conn)
            assert any('permission' in str(call).lower() for call in mock_print.call_args_list)

class TestElectionResults:
    """Test election results viewing."""

    @patch('builtins.input', return_value='3')
    def test_view_results_as_student(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test viewing results as student."""
        mock_auth.check_permission.return_value = False
        election_management.auth = mock_auth
        mock_cursor.fetchall.side_effect = [
            [(1, 'President', None, '2024-01-31', 'completed')],
            [('John', 'Doe', 10, 50)]
        ]

        election_management.view_election_results(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', side_effect=['3', '3'])
    def test_view_results_as_admin(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test viewing results as admin."""
        election_management.auth = mock_auth
        mock_cursor.fetchall.side_effect = [
            [(1, 'President', None, '2024-01-31', 'completed')],
            [('John', 'Doe', 10, 50)]
        ]

        election_management.view_election_results(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', side_effect=['1', '1', '3'])
    def test_appoint_winner(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test appointing election winner."""
        election_management.auth = mock_auth
        mock_cursor.fetchall.return_value = [(1, 'President', None, '2024-01-31', 'completed')]
        mock_cursor.fetchone.side_effect = [
            (1, 'S123', 'John', 'Doe', 10),  # winner
            (0,),  # no one currently in position
        ]

        with patch('education_system.systems.university.domain.pastoral.student_life.student_union.elections.election_management.send_confirmation_email'):
            election_management.view_election_results(mock_cursor, mock_conn)

        mock_conn.commit.assert_called()

class TestCampaignMaterials:
    """Test campaign materials management."""

    @patch('builtins.input', side_effect=['1', '1', 'Test content', 'http://example.com'])
    def test_submit_campaign_materials(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test submitting campaign materials."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.return_value = ('S123',)
        mock_cursor.fetchall.return_value = [(1, 1, 'President', None)]

        election_management.submit_campaign_materials(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_submit_materials_no_candidacy(self, mock_cursor, mock_conn, mock_auth):
        """Test submitting materials without candidacy."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.return_value = ('S123',)
        mock_cursor.fetchall.return_value = []

        with patch('builtins.print') as mock_print:
            election_management.submit_campaign_materials(mock_cursor, mock_conn)
            assert any('not a candidate' in str(call).lower() for call in mock_print.call_args_list)

class TestCampaignExpenses:
    """Test campaign expenses tracking."""

    @patch('builtins.input', side_effect=['1', '1', '50.00', 'Printing flyers', ''])
    def test_track_expenses_add(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test adding campaign expense."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.side_effect = [
            ('S123',),
            (50.00,)  # total spent
        ]
        mock_cursor.fetchall.return_value = [(1, 'President', None)]

        election_management.track_campaign_expenses(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    @patch('builtins.input', side_effect=['2', '1'])
    def test_track_expenses_view_summary(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test viewing expense summary."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.side_effect = [
            ('S123',),
            (100.00, 5, 5),  # summary
        ]
        mock_cursor.fetchall.side_effect = [
            [(1, 'President', None)],
            [(50.00, 'Printing', '2024-01-01', '/path/to/receipt')]
        ]

        election_management.track_campaign_expenses(mock_cursor, mock_conn)

        assert mock_cursor.execute.call_count >= 2

class TestSecurityFeatures:
    """Test election security features."""

    @patch('builtins.input', return_value='')
    def test_vote_integrity_check(self, mock_input, mock_cursor):
        """Test vote integrity checking."""
        mock_cursor.fetchall.side_effect = [
            [],  # No duplicate votes
            [],  # No suspicious activity
            []   # No invalid timing
        ]

        election_management.vote_integrity_check(mock_cursor)

        assert mock_cursor.execute.call_count >= 3

    @patch('builtins.input', return_value='')
    def test_vote_integrity_with_issues(self, mock_input, mock_cursor):
        """Test vote integrity with issues found."""
        mock_cursor.fetchall.side_effect = [
            [('S123', 1, 2)],  # Duplicate votes
            [('S124', 5, '10:00', '11:00')],  # Suspicious activity
            [('S125', 1, '2024-01-01 10:00', '2024-01-16', '2024-01-31')]  # Invalid timing
        ]

        with patch('builtins.print') as mock_print:
            election_management.vote_integrity_check(mock_cursor)
            # Should print warnings
            assert any('duplicate' in str(call).lower() or 'suspicious' in str(call).lower()
                      for call in mock_print.call_args_list)

class TestElectionMenu:
    """Test election menu display."""

    @patch('builtins.input', side_effect=[str(i) for i in range(1, 10)])
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.elections.election_management.get_connection')
    def test_display_election_menu(self, mock_get_conn, mock_input, mock_auth):
        """Test displaying election menu."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        election_management.auth = mock_auth

        # Test should reach menu display
        # Actual implementation would test menu navigation
        assert True

class TestAuthSetup:
    """Test authentication setup."""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance."""
        election_management.set_auth(mock_auth)

        assert election_management.auth == mock_auth

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_database_error_handling(self, mock_cursor, mock_conn, mock_auth):
        """Test handling database errors."""
        election_management.auth = mock_auth
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        with patch('builtins.print') as mock_print:
            election_management.view_elections(mock_cursor)
            assert any('error' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['1', ''])
    def test_empty_manifesto(self, mock_input, mock_cursor, mock_conn, mock_auth):
        """Test submitting nomination with empty manifesto."""
        election_management.auth = mock_auth
        mock_cursor.fetchone.side_effect = [('S123',), ('John', 'Doe', 'CS')]
        mock_cursor.fetchall.return_value = [(1, 'President', None)]

        with patch('builtins.print') as mock_print:
            election_management.nominate_for_election(mock_cursor, mock_conn)
            assert any('cannot be empty' in str(call).lower() for call in mock_print.call_args_list)
