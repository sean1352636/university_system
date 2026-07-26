"""
Tests for student union volunteering module.
Tests volunteer opportunity management and community service tracking.
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch

from education_system.systems.university.domain.pastoral.student_life.student_union.services import volunteering

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
def sample_opportunities():
    """Sample volunteer opportunity data."""
    return [
        (1, 'Food Bank', 'Help distribute food', 'City Center', '2024-12-01',
         '2024-12-01', 4, 'None', 10, 5, 'open'),
        (2, 'Beach Cleanup', 'Clean local beach', 'Seaside', '2024-12-05',
         '2024-12-05', 3, 'None', 20, 15, 'open'),
    ]

class TestBrowseVolunteerOpportunities:
    """Tests for browse_volunteer_opportunities function."""

    @patch('builtins.input', return_value='')
    @patch('builtins.print')
    def test_browse_with_opportunities(self, mock_print, mock_input,
                                       mock_cursor, sample_opportunities):
        """Test browsing when opportunities exist."""
        mock_cursor.fetchall.return_value = sample_opportunities

        volunteering.browse_volunteer_opportunities(mock_cursor)

        # Should display opportunities
        assert any('Volunteer Opportunities' in str(call) for call in mock_print.call_args_list)
        assert any('Food Bank' in str(call) or 'Beach Cleanup' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', return_value='')
    @patch('builtins.print')
    def test_browse_no_opportunities(self, mock_print, mock_input, mock_cursor):
        """Test browsing when no opportunities exist."""
        mock_cursor.fetchall.return_value = []

        volunteering.browse_volunteer_opportunities(mock_cursor)

        # Should indicate no opportunities
        assert any('No volunteer opportunities' in str(call) for call in mock_print.call_args_list)

class TestSignupForVolunteerOpportunity:
    """Tests for signup_for_volunteer_opportunity function."""

    @patch('builtins.input', side_effect=['y'])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context.auth')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.volunteering.auto_award_points')
    def test_signup_success(self, mock_award, mock_auth, mock_print, mock_input, mock_cursor):
        """Test successfully signing up for opportunity."""
        # Mock context
        mock_auth.current_user = {'id': 1}

        mock_cursor.fetchone.side_effect = [
            ('S12345',),  # Student ID
            ('Food Bank', 'Help distribute food', 10, 5),  # Opportunity details
            (0,)  # Not already signed up
        ]

        volunteering.signup_for_volunteer_opportunity(1, mock_cursor)

        # Should insert signup
        assert any('INSERT INTO volunteer_signups' in str(call)
                  for call in mock_cursor.execute.call_args_list)

    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context.auth')
    def test_signup_opportunity_not_found(self, mock_auth, mock_print, mock_cursor):
        """Test signing up for non-existent opportunity."""
        mock_auth.current_user = {'id': 1}

        mock_cursor.fetchone.side_effect = [
            ('S12345',),
            None  # Opportunity not found
        ]

        volunteering.signup_for_volunteer_opportunity(999, mock_cursor)

        # Should indicate not found
        assert any('not found' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context.auth')
    def test_signup_opportunity_full(self, mock_auth, mock_print, mock_cursor):
        """Test signing up for full opportunity."""
        mock_auth.current_user = {'id': 1}

        mock_cursor.fetchone.side_effect = [
            ('S12345',),
            ('Full Event', 'Description', 10, 10),  # Full
        ]

        volunteering.signup_for_volunteer_opportunity(1, mock_cursor)

        # Should indicate full
        assert any('full' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context.auth')
    def test_signup_already_signed_up(self, mock_auth, mock_print, mock_cursor):
        """Test signing up when already signed up."""
        mock_auth.current_user = {'id': 1}

        mock_cursor.fetchone.side_effect = [
            ('S12345',),
            ('Event', 'Description', 10, 5),
            (1,)  # Already signed up
        ]

        volunteering.signup_for_volunteer_opportunity(1, mock_cursor)

        # Should indicate already signed up
        assert any('already signed up' in str(call).lower() for call in mock_print.call_args_list)

class TestViewMyVolunteerActivities:
    """Tests for view_my_volunteer_activities function."""

    @patch('builtins.print')
    def test_view_activities_with_data(self, mock_print, mock_cursor):
        """Test viewing activities when student has activities."""
        activities = [
            ('Food Bank', 'Help distribute food', '2024-11-01',
             '2024-12-01', '2024-12-01', 4.0, 'completed'),
            ('Beach Cleanup', 'Clean beach', '2024-11-05',
             '2024-12-05', '2024-12-05', 3.0, 'completed'),
        ]
        mock_cursor.fetchall.return_value = activities

        volunteering.view_my_volunteer_activities('S12345', mock_cursor)

        # Should display activities
        assert any('Volunteer Activities' in str(call) for call in mock_print.call_args_list)
        assert any('Food Bank' in str(call) for call in mock_print.call_args_list)
        # Should show volunteer level
        assert any('Community' in str(call) or 'Volunteer' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_activities_no_data(self, mock_print, mock_cursor):
        """Test viewing when no activities."""
        mock_cursor.fetchall.return_value = []

        volunteering.view_my_volunteer_activities('S12345', mock_cursor)

        # Should indicate no activities
        assert any('no volunteer activities' in str(call).lower() for call in mock_print.call_args_list)

class TestTrackCommunityServiceHours:
    """Tests for track_community_service_hours function."""

    @patch('builtins.input', side_effect=['1', '1', '5', '', 'Helped serve meals'])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.volunteering.auto_award_points')
    def test_log_hours_success(self, mock_award, mock_print, mock_input,
                               mock_cursor, mock_conn):
        """Test logging volunteer hours successfully."""
        mock_cursor.fetchall.return_value = [
            (1, 'Food Bank', 'Help distribute food')
        ]

        volunteering.track_community_service_hours('S12345', mock_cursor, mock_conn)

        # Should update signup with hours
        assert any('UPDATE volunteer_signups' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_conn.commit.assert_called()
        # Should award points
        mock_award.assert_called()

    @patch('builtins.input', side_effect=['1', ''])
    @patch('builtins.print')
    def test_log_hours_no_opportunities(self, mock_print, mock_input,
                                        mock_cursor, mock_conn):
        """Test logging hours when no active opportunities."""
        mock_cursor.fetchall.return_value = []

        volunteering.track_community_service_hours('S12345', mock_cursor, mock_conn)

        # Should indicate no opportunities
        assert any('No active volunteer' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['2'])
    @patch('builtins.print')
    def test_view_hour_summary(self, mock_print, mock_input, mock_cursor, mock_conn):
        """Test viewing hour summary."""
        mock_cursor.fetchone.return_value = (50.0, 5, 5)
        mock_cursor.fetchall.return_value = [
            ('2024-11', 20.0),
            ('2024-10', 30.0),
        ]

        volunteering.track_community_service_hours('S12345', mock_cursor, mock_conn)

        # Should display summary
        assert any('Summary' in str(call) or 'Total' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['3'])
    @patch('builtins.print')
    def test_generate_service_verification(self, mock_print, mock_input,
                                           mock_cursor, mock_conn):
        """Test generating service verification."""
        mock_cursor.fetchone.side_effect = [
            (50.0,),  # Total hours
            ('John', 'Doe')  # Student name
        ]

        volunteering.track_community_service_hours('S12345', mock_cursor, mock_conn)

        # Should show verification
        assert any('Verification' in str(call) or 'verified' in str(call).lower()
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['4', '100'])
    @patch('builtins.print')
    def test_set_volunteer_goals(self, mock_print, mock_input, mock_cursor, mock_conn):
        """Test setting volunteer goals."""
        mock_cursor.fetchone.return_value = (25.0,)  # Current hours

        volunteering.track_community_service_hours('S12345', mock_cursor, mock_conn)

        # Should display goal progress
        assert any('Goal' in str(call) or 'progress' in str(call).lower()
                  for call in mock_print.call_args_list)

class TestIntegrationVolunteering:
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
            CREATE TABLE volunteer_opportunities (
                opportunity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_name TEXT,
                description TEXT,
                location TEXT,
                start_date TEXT,
                end_date TEXT,
                hours_required INTEGER,
                skills_needed TEXT,
                max_volunteers INTEGER,
                current_volunteers INTEGER,
                status TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE volunteer_signups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER,
                student_id TEXT,
                signup_date TEXT,
                hours_completed REAL,
                completion_date TEXT,
                feedback TEXT,
                status TEXT,
                FOREIGN KEY (opportunity_id) REFERENCES volunteer_opportunities(opportunity_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')

        # Insert test data
        cursor.execute("INSERT INTO students VALUES (?, ?, ?)", ('S12345', 'John', 'Doe'))
        cursor.execute('''
            INSERT INTO volunteer_opportunities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (1, 'Food Bank', 'Help distribute food', 'City Center',
              '2024-12-01', '2024-12-01', 4, 'None', 10, 5, 'open'))

        conn.commit()
        yield conn
        conn.close()

    def test_browse_opportunities_integration(self, db_conn):
        """Test browsing opportunities with real database."""
        cursor = db_conn.cursor()

        # Insert a future-dated opportunity so the date filter matches
        future_date = (datetime.now() + __import__('datetime').timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO volunteer_opportunities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (2, 'Park Cleanup', 'Help clean the park', 'City Park',
              future_date, future_date, 3, 'None', 15, 5, 'open'))
        db_conn.commit()

        cursor.execute('''
            SELECT opportunity_id, organization_name, description, location,
                   start_date, end_date, hours_required, skills_needed,
                   max_volunteers, current_volunteers, status
            FROM volunteer_opportunities
            WHERE status = 'open' AND start_date >= date('now')
            ORDER BY start_date
        ''')

        opportunities = cursor.fetchall()
        assert len(opportunities) >= 1
        assert opportunities[0][1] == 'Park Cleanup'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
