"""
Tests for student union competitions module.
Tests competition viewing and management functionality.
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
from unittest.mock import Mock, patch

from university_system.modules.domain.student_affairs.student_union.services import competitions

@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = Mock()
    cursor.fetchall = Mock(return_value=[])
    cursor.fetchone = Mock(return_value=None)
    cursor.execute = Mock()
    return cursor

@pytest.fixture
def sample_competitions():
    """Sample competition data."""
    return [
        (1, 'Hackathon 2024', 'coding', '2024-12-01', '2024-12-03', '2024-11-28', 5, 'registration_open', 3),
        (2, 'Sports Tournament', 'sports', '2024-12-10', '2024-12-12', '2024-12-05', 10, 'upcoming', 5),
    ]

@pytest.fixture
def sample_results():
    """Sample competition results."""
    return [
        ('Tech Club', 95.5, 1, 10),
        ('Science Club', 88.0, 2, 8),
        ('Engineering Club', 82.5, 3, 9),
    ]

class TestViewActiveCompetitions:
    """Tests for view_active_competitions function."""

    @patch('builtins.print')
    def test_view_competitions_success(self, mock_print, mock_cursor, sample_competitions):
        """Test viewing active competitions."""
        mock_cursor.fetchall.side_effect = [sample_competitions]
        mock_cursor.fetchone.side_effect = [
            ('Coding competition', '1st: Laptop, 2nd: Tablet'),
            ('Team sports competition', '1st: Trophy'),
        ]

        competitions.view_active_competitions(mock_cursor)

        # Verify output
        assert any('Active Competitions' in str(call)
                  for call in mock_print.call_args_list)
        assert any('Hackathon 2024' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_competitions_none_available(self, mock_print, mock_cursor):
        """Test when no competitions are available."""
        mock_cursor.fetchall.return_value = []

        competitions.view_active_competitions(mock_cursor)

        # Verify no competitions message
        assert any('No active competitions' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_competitions_database_error(self, mock_print, mock_cursor):
        """Test handling of database errors."""
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        competitions.view_active_competitions(mock_cursor)

        # Verify error message
        assert any('Database error' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_competitions_displays_details(self, mock_print, mock_cursor,
                                                sample_competitions):
        """Test that all competition details are displayed."""
        mock_cursor.fetchall.return_value = sample_competitions
        mock_cursor.fetchone.side_effect = [
            ('Description 1', 'Prizes 1'),
            ('Description 2', 'Prizes 2'),
        ]

        competitions.view_active_competitions(mock_cursor)

        # Verify details are shown
        assert any('Type:' in str(call) for call in mock_print.call_args_list)
        assert any('Start Date:' in str(call) for call in mock_print.call_args_list)
        assert any('Registration Deadline:' in str(call) for call in mock_print.call_args_list)

class TestViewCompetitionResults:
    """Tests for view_competition_results function."""

    @patch('builtins.input', side_effect=['1'])
    @patch('builtins.print')
    def test_view_results_success(self, mock_print, mock_input, mock_cursor,
                                  sample_competitions, sample_results):
        """Test viewing competition results."""
        mock_cursor.fetchall.side_effect = [sample_competitions, sample_results]

        competitions.view_competition_results(mock_cursor)

        # Verify results are displayed
        assert any('results' in str(call).lower()
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_results_no_competitions(self, mock_print, mock_cursor):
        """Test when no competitions have results."""
        mock_cursor.fetchall.return_value = []

        competitions.view_competition_results(mock_cursor)

        # Verify message
        assert any('No competitions' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['999'])
    @patch('builtins.print')
    def test_view_results_invalid_selection(self, mock_print, mock_input,
                                            mock_cursor, sample_competitions):
        """Test invalid competition selection."""
        mock_cursor.fetchall.return_value = sample_competitions

        competitions.view_competition_results(mock_cursor)

        # Verify invalid message
        assert any('Invalid' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['abc'])
    @patch('builtins.print')
    def test_view_results_non_numeric_selection(self, mock_print, mock_input,
                                                 mock_cursor, sample_competitions):
        """Test non-numeric selection."""
        mock_cursor.fetchall.return_value = sample_competitions

        competitions.view_competition_results(mock_cursor)

        # Verify invalid message
        assert any('Invalid' in str(call)
                  for call in mock_print.call_args_list)

class TestIntegrationCompetitions:
    """Integration tests using real database."""

    @pytest.fixture
    def db_conn(self):
        """Create a test database connection."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Create tables
        cursor.execute('''
            CREATE TABLE club_competitions (
                competition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition_name TEXT,
                competition_type TEXT,
                start_date TEXT,
                end_date TEXT,
                registration_deadline TEXT,
                max_participants_per_club INTEGER,
                status TEXT,
                description TEXT,
                prizes TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE competition_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition_id INTEGER,
                club_id INTEGER,
                student_id TEXT,
                score REAL,
                rank_position INTEGER,
                FOREIGN KEY (competition_id) REFERENCES club_competitions(competition_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE student_clubs (
                club_id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_name TEXT
            )
        ''')

        # Insert test data
        cursor.execute('''
            INSERT INTO club_competitions VALUES
            (1, 'Hackathon', 'coding', '2024-12-01', '2024-12-03', '2024-11-28',
             5, 'active', 'Coding competition', '1st: Laptop')
        ''')

        cursor.execute("INSERT INTO student_clubs VALUES (1, 'Tech Club')")
        cursor.execute("INSERT INTO student_clubs VALUES (2, 'Science Club')")

        cursor.execute('''
            INSERT INTO competition_participants VALUES
            (1, 1, 1, 'S12345', 95.5, 1),
            (2, 1, 2, 'S12346', 88.0, 2)
        ''')

        conn.commit()
        yield conn
        conn.close()

    def test_query_active_competitions(self, db_conn):
        """Test querying active competitions."""
        cursor = db_conn.cursor()

        cursor.execute('''
            SELECT c.competition_id, c.competition_name, c.competition_type,
                   c.start_date, c.end_date, c.registration_deadline,
                   c.max_participants_per_club, c.status,
                   COUNT(DISTINCT cp.club_id) as registered_clubs
            FROM club_competitions c
            LEFT JOIN competition_participants cp ON c.competition_id = cp.competition_id
            WHERE c.status IN ('upcoming', 'active', 'registration_open')
            GROUP BY c.competition_id
        ''')

        comps = cursor.fetchall()
        assert len(comps) == 1
        assert comps[0][1] == 'Hackathon'
        assert comps[0][8] == 2  # registered clubs

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
