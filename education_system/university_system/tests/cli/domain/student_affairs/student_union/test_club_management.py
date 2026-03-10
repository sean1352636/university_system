"""
Comprehensive tests for student_union clubs/club_management.py module.

Tests cover:
- Creating clubs
- Viewing clubs
- Joining clubs
- Managing clubs
- Club member management
- Club officer management
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.student_affairs.student_union.clubs import club_management

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

class TestCreateClub:
    """Test club creation functionality."""

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    @patch('builtins.input', side_effect=['Test Club', 'A test club', 'Academic', 'S123', 'S124', 'S125'])
    def test_create_club_success(self, mock_input, mock_get_conn, mock_auth):
        """Test successfully creating a club."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [(0,), (1,)]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        club_management.create_club()

        assert mock_cursor.execute.call_count >= 2
        mock_conn.commit.assert_called_once()

    @patch('builtins.input', return_value='')
    def test_create_club_empty_name(self, mock_input, mock_auth):
        """Test creating club with empty name."""
        club_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            club_management.create_club()
            # Should print error message
            assert any('empty' in str(call).lower() for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    @patch('builtins.input', side_effect=['Test Club', 'Description', 'Academic', 'S123'])
    def test_create_club_duplicate_name(self, mock_input, mock_get_conn, mock_auth):
        """Test creating club with duplicate name."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1,)  # Club already exists
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            club_management.create_club()
            # Should print error message
            assert any('exists' in str(call).lower() for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    @patch('builtins.input', side_effect=['Test Club', 'Description', 'Academic', 'INVALID'])
    def test_create_club_invalid_president(self, mock_input, mock_get_conn, mock_auth):
        """Test creating club with invalid president ID."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [(0,), (0,)]  # No existing club, but invalid student
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            club_management.create_club()
            # Should print error message
            assert any('not found' in str(call).lower() or 'no student' in str(call).lower() for call in mock_print.call_args_list)

    def test_create_club_no_permission(self, mock_auth):
        """Test creating club without permission."""
        mock_auth.check_permission.return_value = False
        club_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            club_management.create_club()
            # Should print permission error
            assert any('permission' in str(call).lower() for call in mock_print.call_args_list)

class TestViewClubs:
    """Test club viewing functionality."""

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    def test_view_clubs_success(self, mock_get_conn, mock_auth):
        """Test successfully viewing clubs."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, 'Test Club', 'Academic', 'A test club', 15)
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        club_management.view_clubs()

        mock_cursor.execute.assert_called_once()
        mock_cursor.fetchall.assert_called_once()

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    def test_view_clubs_empty(self, mock_get_conn, mock_auth):
        """Test viewing clubs when none exist."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            club_management.view_clubs()
            # Should print no clubs message
            assert any('no' in str(call).lower() and 'club' in str(call).lower() for call in mock_print.call_args_list)

    def test_view_clubs_not_logged_in(self):
        """Test viewing clubs when not logged in."""
        club_management.auth = None

        with patch('builtins.print') as mock_print:
            club_management.view_clubs()
            # Should print login required message
            assert any('logged in' in str(call).lower() for call in mock_print.call_args_list)

class TestJoinClub:
    """Test club joining functionality."""

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.view_clubs')
    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.send_confirmation_email')
    @patch('builtins.input', return_value='1')
    def test_join_club_success(self, mock_input, mock_email, mock_view, mock_get_conn, mock_auth):
        """Test successfully joining a club."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            ('S123',),  # student_id
            ('Test Club',),  # club exists
            (0,)  # not already a member
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        club_management.join_club()

        assert mock_cursor.execute.call_count >= 3
        mock_conn.commit.assert_called_once()
        mock_email.assert_called_once()

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.view_clubs')
    @patch('builtins.input', return_value='invalid')
    def test_join_club_invalid_id(self, mock_input, mock_view, mock_get_conn, mock_auth):
        """Test joining club with invalid ID."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('S123',)
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            club_management.join_club()
            # Should print error message
            assert any('invalid' in str(call).lower() for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.view_clubs')
    @patch('builtins.input', return_value='1')
    def test_join_club_already_member(self, mock_input, mock_view, mock_get_conn, mock_auth):
        """Test joining club when already a member."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            ('S123',),
            ('Test Club',),
            (1,)  # Already a member
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            club_management.join_club()
            # Should print already member message
            assert any('already' in str(call).lower() for call in mock_print.call_args_list)

class TestViewMyClubs:
    """Test viewing user's clubs."""

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    def test_view_my_clubs_success(self, mock_get_conn, mock_auth):
        """Test successfully viewing user's clubs."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('S123',)
        mock_cursor.fetchall.return_value = [
            (1, 'Test Club', 'Academic', 'President', '2024-01-01')
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        club_management.view_my_clubs()

        assert mock_cursor.execute.call_count >= 2
        mock_cursor.fetchall.assert_called_once()

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    def test_view_my_clubs_empty(self, mock_get_conn, mock_auth):
        """Test viewing clubs when user has none."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('S123',)
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            club_management.view_my_clubs()
            # Should print no clubs message
            assert any('not a member' in str(call).lower() for call in mock_print.call_args_list)

class TestManageClub:
    """Test club management functionality."""

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    @patch('builtins.input', side_effect=['1', '1', '6'])
    def test_manage_club_view_details(self, mock_input, mock_get_conn, mock_auth):
        """Test viewing club details."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            ('S123',),  # student_id
            (1, 'Test Club', 'Description', 'Academic', '2024-01-01', 'active', 'S123', 'S124', 'S125', 15, 500.00)
        ]
        mock_cursor.fetchall.return_value = [
            (1, 'Test Club')
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        club_management.manage_club()

        assert mock_cursor.execute.call_count >= 2

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    @patch('builtins.input', side_effect=['1', '2', '6'])
    def test_manage_club_view_members(self, mock_input, mock_get_conn, mock_auth):
        """Test viewing club members."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('S123',)
        mock_cursor.fetchall.side_effect = [
            [(1, 'Test Club')],
            [('S123', 'John', 'Doe', 'President', '2024-01-01')]
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        club_management.manage_club()

        assert mock_cursor.execute.call_count >= 3

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    @patch('builtins.input', side_effect=['1', '3', '1', 'S999', '6'])
    def test_manage_club_add_member(self, mock_input, mock_get_conn, mock_auth):
        """Test adding a club member."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            ('S123',),  # student_id
        ]
        mock_cursor.fetchall.return_value = [(1, 'Test Club')]
        # Setup responses for add member flow
        mock_cursor.fetchone = Mock(side_effect=[
            ('S123',),  # current user
            (1,),  # student exists
            (0,)  # not already a member
        ])
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        club_management.manage_club()

        mock_conn.commit.assert_called()

class TestAuthSetup:
    """Test authentication setup."""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance."""
        club_management.set_auth(mock_auth)

        assert club_management.auth == mock_auth

class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection')
    def test_database_error_handling(self, mock_get_conn, mock_auth):
        """Test handling of database errors."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        club_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            club_management.view_clubs()
            # Should print error message
            assert any('error' in str(call).lower() for call in mock_print.call_args_list)

    def test_no_student_record(self, mock_auth):
        """Test handling when user has no student record."""
        with patch('university_system.modules.domain.student_affairs.student_union.clubs.club_management.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn
            club_management.auth = mock_auth

            with patch('builtins.print') as mock_print:
                club_management.join_club()
                # Should print no student record message
                assert any('no student' in str(call).lower() for call in mock_print.call_args_list)
