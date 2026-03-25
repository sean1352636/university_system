"""
Tests for student union points system module.
Tests points tracking, leaderboards, and automatic point awarding.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from education_system.university_system.modules.domain.student_affairs.student_union.services import points
from education_system.university_system.infrastructure.database.db import get_connection

@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = Mock()
    cursor.fetchall = Mock(return_value=[])
    cursor.fetchone = Mock(return_value=None)
    cursor.execute = Mock()
    cursor.lastrowid = 1
    cursor.rowcount = 1
    return cursor

@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = Mock()
    conn.commit = Mock()
    conn.rollback = Mock()
    conn.close = Mock()
    return conn

@pytest.fixture
def sample_checkouts():
    """Sample equipment checkout data."""
    return [
        (1, 'Projector', 'John', 'Doe', '2024-01-01', '2024-01-07', None, 'checked_out', 'Drama Club'),
        (2, 'Camera', 'Jane', 'Smith', '2024-01-02', '2024-01-09', '2024-01-08', 'returned', 'Photo Society'),
    ]

@pytest.fixture
def sample_leaderboard():
    """Sample leaderboard data."""
    return [
        ('John', 'Doe', 250, 3),
        ('Jane', 'Smith', 180, 2),
        ('Bob', 'Johnson', 150, 1),
    ]

class TestViewAllCheckouts:
    """Tests for view_all_checkouts function."""

    @patch('builtins.print')
    @patch('builtins.input', return_value='n')
    def test_view_checkouts_with_data(self, mock_input, mock_print, mock_cursor, sample_checkouts):
        """Test viewing checkouts when data exists."""
        mock_cursor.fetchall.return_value = sample_checkouts
        mock_cursor.fetchone.return_value = (2,)  # 2 overdue items

        points.view_all_checkouts(mock_cursor)

        # Verify SQL queries were executed
        assert mock_cursor.execute.call_count >= 1
        # Verify output was printed
        assert any('Equipment' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_checkouts_no_data(self, mock_print, mock_cursor):
        """Test viewing checkouts when no data exists."""
        mock_cursor.fetchall.return_value = []

        points.view_all_checkouts(mock_cursor)

        # Should indicate no checkouts found
        assert any('No equipment checkouts' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    @patch('builtins.input', return_value='y')
    def test_view_overdue_items(self, mock_input, mock_print, mock_cursor, sample_checkouts):
        """Test viewing overdue items."""
        mock_cursor.fetchall.side_effect = [
            sample_checkouts,
            [('Projector', 'John', 'Doe', '2024-01-07', 5)]  # Overdue item
        ]
        mock_cursor.fetchone.return_value = (1,)  # 1 overdue item

        points.view_all_checkouts(mock_cursor)

        # Should show overdue warning
        assert any('overdue' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_checkouts_database_error(self, mock_print, mock_cursor):
        """Test handling of database errors."""
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        points.view_all_checkouts(mock_cursor)

        # Should print error message
        assert any('Database error' in str(call) for call in mock_print.call_args_list)

class TestViewLeaderboard:
    """Tests for view_leaderboard function."""

    @patch('builtins.print')
    def test_view_leaderboard_with_data(self, mock_print, mock_cursor, sample_leaderboard):
        """Test viewing leaderboard with data."""
        current_month = datetime.now().strftime('%Y-%m')
        mock_cursor.fetchall.side_effect = [
            sample_leaderboard,
            sample_leaderboard[:2]  # Monthly leaders
        ]

        points.view_leaderboard(mock_cursor)

        # Verify output contains leaderboard data
        assert any('Leaderboard' in str(call) for call in mock_print.call_args_list)
        assert any('John' in str(call) or 'Jane' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_leaderboard_no_data(self, mock_print, mock_cursor):
        """Test viewing leaderboard with no data."""
        mock_cursor.fetchall.return_value = []

        points.view_leaderboard(mock_cursor)

        # Should indicate no data
        assert any('No engagement data' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_leaderboard_monthly(self, mock_print, mock_cursor, sample_leaderboard):
        """Test monthly leaderboard display."""
        mock_cursor.fetchall.side_effect = [
            sample_leaderboard,
            sample_leaderboard[:1]  # One monthly leader
        ]

        points.view_leaderboard(mock_cursor)

        # Should show monthly section
        assert any('Month' in str(call) for call in mock_print.call_args_list)

class TestViewPointOpportunities:
    """Tests for view_point_opportunities function."""

    @patch('builtins.print')
    def test_view_opportunities(self, mock_print, mock_cursor):
        """Test viewing point earning opportunities."""
        mock_cursor.fetchall.return_value = [
            ('Tech Talk', 'Tech Society', '2024-12-20'),
            ('Game Night', 'Gaming Club', '2024-12-22'),
        ]

        points.view_point_opportunities(mock_cursor)

        # Should display opportunities
        assert any('Ways to Earn Points' in str(call) for call in mock_print.call_args_list)
        assert any('Event Attendance' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_opportunities_with_events(self, mock_print, mock_cursor):
        """Test viewing opportunities with upcoming events."""
        upcoming_events = [
            ('Tech Talk', 'Tech Society', '2024-12-20'),
            ('Game Night', 'Gaming Club', '2024-12-22'),
        ]
        mock_cursor.fetchall.return_value = upcoming_events

        points.view_point_opportunities(mock_cursor)

        # Should show upcoming events
        assert any('Upcoming' in str(call) for call in mock_print.call_args_list)

class TestAwardPointsToStudent:
    """Tests for award_points_to_student function."""

    @patch('builtins.print')
    @patch('builtins.input', side_effect=['S12345', '50', 'Event Attendance', 'Attended Tech Talk'])
    @patch('education_system.university_system.modules.core.services.student_union_misc.points.check_and_award_badges')
    def test_award_points_success(self, mock_check_badges, mock_input, mock_print, mock_cursor, mock_conn):
        """Test successfully awarding points to a student."""
        mock_cursor.fetchone.side_effect = [
            ('John', 'Doe'),  # Student exists
            (100,)  # Current balance
        ]

        points.award_points_to_student(mock_cursor, mock_conn)

        # Verify point insertion
        assert any('INSERT INTO student_points' in str(call) for call in mock_cursor.execute.call_args_list)
        mock_conn.commit.assert_called_once()
        # Should check for new badges
        mock_check_badges.assert_called_once()

    @patch('builtins.print')
    @patch('builtins.input', side_effect=['S99999', ''])
    def test_award_points_student_not_found(self, mock_input, mock_print, mock_cursor, mock_conn):
        """Test awarding points when student doesn't exist."""
        mock_cursor.fetchone.return_value = None

        points.award_points_to_student(mock_cursor, mock_conn)

        # Should indicate student not found
        assert any('No student found' in str(call) for call in mock_print.call_args_list)
        mock_conn.commit.assert_not_called()

    @patch('builtins.print')
    @patch('builtins.input', side_effect=['S12345', 'invalid', ''])
    def test_award_points_invalid_amount(self, mock_input, mock_print, mock_cursor, mock_conn):
        """Test awarding invalid point amount."""
        mock_cursor.fetchone.return_value = ('John', 'Doe')

        points.award_points_to_student(mock_cursor, mock_conn)

        # Should indicate invalid format
        assert any('Invalid points format' in str(call) for call in mock_print.call_args_list)
        mock_conn.commit.assert_not_called()

    @patch('builtins.print')
    @patch('builtins.input', side_effect=['S12345', '-10', ''])
    def test_award_points_negative_amount(self, mock_input, mock_print, mock_cursor, mock_conn):
        """Test awarding negative points."""
        mock_cursor.fetchone.return_value = ('John', 'Doe')

        points.award_points_to_student(mock_cursor, mock_conn)

        # Should reject negative points
        assert any('positive' in str(call).lower() for call in mock_print.call_args_list)
        mock_conn.commit.assert_not_called()

    @patch('builtins.print')
    @patch('builtins.input', side_effect=['', ''])
    def test_award_points_empty_student_id(self, mock_input, mock_print, mock_cursor, mock_conn):
        """Test with empty student ID."""
        points.award_points_to_student(mock_cursor, mock_conn)

        # Should indicate ID cannot be empty
        assert any('cannot be empty' in str(call).lower() for call in mock_print.call_args_list)

class TestAutoAwardPoints:
    """Tests for auto_award_points function."""

    def test_auto_award_points_success(self, mock_cursor, mock_conn):
        """Test automatically awarding points."""
        mock_cursor.fetchone.return_value = (100,)  # Current balance

        result = points.auto_award_points(
            'S12345', 'Event Attendance', 50, 'Attended Tech Talk', mock_cursor, mock_conn
        )

        assert result is True
        mock_conn.commit.assert_called_once()
        # Verify INSERT query was executed
        assert any('INSERT INTO student_points' in str(call) for call in mock_cursor.execute.call_args_list)

    def test_auto_award_points_zero_balance(self, mock_cursor, mock_conn):
        """Test awarding points to student with zero balance."""
        mock_cursor.fetchone.return_value = (0,)

        result = points.auto_award_points(
            'S12345', 'Volunteering', 25, 'Helped at event', mock_cursor, mock_conn
        )

        assert result is True
        # New balance should be 25
        insert_call = [call for call in mock_cursor.execute.call_args_list
                      if 'INSERT' in str(call)][0]
        args = insert_call[0][1]
        assert args[2] == 25  # new_balance parameter

    def test_auto_award_points_database_error(self, mock_cursor, mock_conn):
        """Test handling of database error during auto award."""
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        result = points.auto_award_points(
            'S12345', 'Event', 10, 'Test', mock_cursor, mock_conn
        )

        assert result is False
        mock_conn.commit.assert_not_called()

    def test_auto_award_points_calculates_balance(self, mock_cursor, mock_conn):
        """Test that balance is correctly calculated."""
        mock_cursor.fetchone.return_value = (150,)  # Existing balance

        points.auto_award_points(
            'S12345', 'Achievement', 75, 'Won competition', mock_cursor, mock_conn
        )

        # New balance should be 150 + 75 = 225
        insert_call = [call for call in mock_cursor.execute.call_args_list
                      if 'INSERT' in str(call)][0]
        args = insert_call[0][1]
        assert args[2] == 225  # new_balance parameter

class TestIntegrationPoints:
    """Integration tests using real database."""

    @pytest.fixture
    def db_conn(self):
        """Create a test database connection."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Create required tables
        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE student_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                points_earned INTEGER,
                points_spent INTEGER DEFAULT 0,
                current_balance INTEGER,
                activity_type TEXT,
                activity_description TEXT,
                earned_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE student_badges (
                badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                badge_name TEXT,
                earned_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')

        # Insert test student
        cursor.execute(
            "INSERT INTO students VALUES (?, ?, ?)",
            ('S12345', 'John', 'Doe')
        )

        conn.commit()
        yield conn
        conn.close()

    def test_auto_award_integration(self, db_conn):
        """Test auto award with real database."""
        cursor = db_conn.cursor()

        # Award points
        result = points.auto_award_points(
            'S12345', 'Event', 50, 'Test event', cursor, db_conn
        )

        assert result is True

        # Verify points were recorded
        cursor.execute(
            'SELECT points_earned, current_balance FROM student_points WHERE student_id = ?',
            ('S12345',)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 50  # points_earned
        assert row[1] == 50  # current_balance

    def test_multiple_awards_accumulate(self, db_conn):
        """Test that multiple point awards accumulate correctly."""
        cursor = db_conn.cursor()

        # Award points multiple times
        points.auto_award_points('S12345', 'Event', 50, 'Event 1', cursor, db_conn)
        points.auto_award_points('S12345', 'Event', 30, 'Event 2', cursor, db_conn)
        points.auto_award_points('S12345', 'Volunteering', 20, 'Volunteer work', cursor, db_conn)

        # Check total balance
        cursor.execute(
            'SELECT SUM(points_earned), SUM(current_balance) FROM student_points WHERE student_id = ?',
            ('S12345',)
        )
        row = cursor.fetchone()
        assert row[0] == 100  # Total points earned
        # Last current_balance should reflect cumulative total
        cursor.execute(
            'SELECT current_balance FROM student_points WHERE student_id = ? ORDER BY id DESC LIMIT 1',
            ('S12345',)
        )
        assert cursor.fetchone()[0] == 100

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
