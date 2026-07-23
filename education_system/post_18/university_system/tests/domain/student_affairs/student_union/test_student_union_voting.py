"""
Tests for student union voting module.
Tests enhanced voting system including ranked choice voting and campaigns.
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from education_system.post_18.university_system.modules.domain.student_affairs.student_union.services import voting

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
def sample_elections():
    """Sample election data."""
    return [
        (1, 'President', 'Student Union'),
        (2, 'Secretary', 'Engineering Society'),
    ]

@pytest.fixture
def sample_candidates():
    """Sample candidate data."""
    return [
        (1, 'Alice', 'Brown', 'I will improve student facilities'),
        (2, 'Bob', 'Green', 'More events and activities'),
        (3, 'Charlie', 'White', 'Better academic support'),
    ]

class TestRankedChoiceVoting:
    """Tests for ranked_choice_voting function."""

    @patch('builtins.input', side_effect=['1', '1', '2', '3', 'y'])
    @patch('builtins.print')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.union_context.auth')
    def test_ranked_vote_success(self, mock_auth, mock_print, mock_input,
                                 mock_cursor, mock_conn, sample_elections, sample_candidates):
        """Test successfully casting ranked choice vote."""
        mock_auth.current_user = {'id': 1}

        current_date = datetime.now().strftime('%Y-%m-%d')
        mock_cursor.fetchone.return_value = ('S12345',)
        mock_cursor.fetchall.side_effect = [
            sample_elections,
            sample_candidates
        ]

        voting.ranked_choice_voting(mock_cursor, mock_conn)

        # Should insert ranked vote
        assert any('INSERT INTO ranked_votes' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_conn.commit.assert_called()

    @patch('builtins.print')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.union_context.auth')
    def test_ranked_vote_no_elections(self, mock_auth, mock_print, mock_cursor, mock_conn):
        """Test ranked voting when no elections available."""
        mock_auth.current_user = {'id': 1}

        mock_cursor.fetchone.return_value = ('S12345',)
        mock_cursor.fetchall.return_value = []

        voting.ranked_choice_voting(mock_cursor, mock_conn)

        # Should indicate no elections
        assert any('No elections' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['1', '0', '0', '0'])
    @patch('builtins.print')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.union_context.auth')
    def test_ranked_vote_no_preferences(self, mock_auth, mock_print, mock_input,
                                        mock_cursor, mock_conn, sample_elections, sample_candidates):
        """Test ranked voting with no preferences selected."""
        mock_auth.current_user = {'id': 1}

        mock_cursor.fetchone.return_value = ('S12345',)
        mock_cursor.fetchall.side_effect = [sample_elections, sample_candidates]

        voting.ranked_choice_voting(mock_cursor, mock_conn)

        # Should indicate no preferences
        assert any('No preferences' in str(call) for call in mock_print.call_args_list)
        mock_conn.commit.assert_not_called()

class TestConfigureVotingMethods:
    """Tests for configure_voting_methods function."""

    @patch('builtins.input', side_effect=['100'])  # Exit choice
    @patch('builtins.print')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.union_context.auth')
    def test_configure_initializes_defaults(self, mock_auth, mock_print, mock_input,
                                            mock_cursor, mock_conn):
        """Test that configuration initializes with defaults."""
        mock_auth.current_user = {'id': 1}
        mock_auth.check_permission = Mock(return_value=True)

        mock_cursor.fetchall.return_value = []

        voting.configure_voting_methods(mock_cursor, mock_conn)

        # Should create voting configuration table
        assert any('CREATE TABLE IF NOT EXISTS voting_configuration' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        # Should insert default configs
        assert any('INSERT OR IGNORE INTO voting_configuration' in str(call)
                  for call in mock_cursor.execute.call_args_list)

    @patch('builtins.input', side_effect=['100'])  # Exit
    @patch('builtins.print')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.union_context.auth')
    def test_configure_displays_settings(self, mock_auth, mock_print, mock_input,
                                         mock_cursor, mock_conn):
        """Test that configuration displays current settings."""
        mock_auth.current_user = {'id': 1}
        mock_auth.check_permission = Mock(return_value=True)

        mock_cursor.fetchall.return_value = [
            ('default_voting_method', 'simple', 'Default voting method'),
            ('allow_ranked_choice', 'true', 'Allow ranked choice'),
        ]

        voting.configure_voting_methods(mock_cursor, mock_conn)

        # Should display configuration
        assert any('Configuration' in str(call) for call in mock_print.call_args_list)

class TestHelperFunctions:
    """Tests for helper functions in voting module."""

    @patch('builtins.input', return_value='0')
    @patch('builtins.print')
    def test_review_pending_materials(self, mock_print, mock_input, mock_cursor):
        """Test reviewing pending campaign materials."""
        pending_materials = [
            (1, 'poster', 'Vote for Alice!', '2024-11-15', 'Alice', 'Brown', 'President'),
            (2, 'flyer', 'Bob for Secretary', '2024-11-16', 'Bob', 'Green', 'Secretary'),
        ]
        mock_cursor.fetchall.return_value = pending_materials

        voting.review_pending_materials(mock_cursor)

        # Should display pending materials
        assert any('Pending' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', return_value='0')
    @patch('builtins.print')
    def test_view_detailed_spending(self, mock_print, mock_input, mock_cursor):
        """Test viewing detailed campaign spending."""
        expenses = [
            ('Alice', 'Brown', 'President', 50.00, 'Posters', '2024-11-15', '/receipt.pdf'),
            ('Alice', 'Brown', 'President', 30.00, 'Flyers', '2024-11-16', None),
        ]
        mock_cursor.fetchall.return_value = expenses

        voting.view_detailed_spending(mock_cursor)

        # Should display expenses
        assert any('Spending' in str(call) or 'expense' in str(call).lower()
                  for call in mock_print.call_args_list)

    @patch('builtins.input', return_value='')
    @patch('builtins.print')
    def test_access_control_review(self, mock_print, mock_input, mock_cursor):
        """Test access control review."""
        admin_users = [
            (1, 'admin1', 'admin', '2024-01-01', '2024-11-15'),
            (2, 'staff1', 'staff', '2024-02-01', '2024-11-14'),
        ]
        mock_cursor.fetchall.side_effect = [admin_users, [], []]

        voting.access_control_review(mock_cursor)

        # Should display admin users
        assert any('Access Control' in str(call) or 'admin' in str(call).lower()
                  for call in mock_print.call_args_list)

class TestLogConfigurationChange:
    """Tests for log_configuration_change function."""

    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.union_context.auth')
    def test_log_change_creates_audit_table(self, mock_auth, mock_cursor, mock_conn):
        """Test that logging creates audit table."""
        mock_auth.current_user = {'id': 1}

        voting.log_configuration_change(
            mock_cursor, mock_conn,
            'test_key', 'old_value', 'new_value', 'Test setting'
        )

        # Should create audit table
        assert any('CREATE TABLE IF NOT EXISTS configuration_audit' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        # Should insert audit record
        assert any('INSERT INTO configuration_audit' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_conn.commit.assert_called()

class TestEmailNotifications:
    """Tests for email notification functions."""

    @patch('builtins.input', return_value='test@example.com')
    @patch('builtins.print')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.union_context.auth')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.voting.render_template',
           return_value=('Test Subject', 'Test Body'))
    @patch('education_system.post_18.university_system.infrastructure.email.queue_email', return_value=True)
    def test_email_notification_success(self, mock_email, mock_render, mock_auth, mock_print,
                                        mock_input, mock_cursor, mock_conn):
        """Test sending email notification."""
        mock_auth.current_user = {'id': 1, 'username': 'testuser'}

        voting.test_email_notifications(mock_cursor, mock_conn)

        # Should send email
        mock_email.assert_called_once()
        # Should confirm success
        assert any('sent successfully' in str(call).lower() for call in mock_print.call_args_list)

class TestIntegrationVoting:
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
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                username TEXT,
                role TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE union_elections (
                election_id INTEGER PRIMARY KEY AUTOINCREMENT,
                position TEXT,
                department TEXT,
                status TEXT,
                voting_start TEXT,
                voting_end TEXT,
                created_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE election_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                election_id INTEGER,
                student_id TEXT,
                manifesto TEXT,
                FOREIGN KEY (election_id) REFERENCES union_elections(election_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE ranked_votes (
                vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                election_id INTEGER,
                voter_id TEXT,
                candidate_preferences TEXT,
                vote_time TEXT,
                FOREIGN KEY (election_id) REFERENCES union_elections(election_id),
                FOREIGN KEY (voter_id) REFERENCES students(student_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE voting_configuration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                description TEXT,
                updated_by INTEGER,
                updated_at TEXT,
                FOREIGN KEY (updated_by) REFERENCES users(id)
            )
        ''')

        # Insert test data
        cursor.execute("INSERT INTO students VALUES (?, ?, ?)", ('S12345', 'John', 'Doe'))
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (1, 'S12345', 'testuser', 'student'))

        conn.commit()
        yield conn
        conn.close()

    def test_voting_configuration_integration(self, db_conn):
        """Test voting configuration with real database."""
        cursor = db_conn.cursor()

        # Insert configuration
        cursor.execute('''
            INSERT INTO voting_configuration (config_key, config_value, description, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', ('test_key', 'test_value', 'Test configuration', 1, '2024-11-15'))

        db_conn.commit()

        # Verify configuration
        cursor.execute('SELECT * FROM voting_configuration WHERE config_key = ?', ('test_key',))
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == 'test_key'
        assert row[2] == 'test_value'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
