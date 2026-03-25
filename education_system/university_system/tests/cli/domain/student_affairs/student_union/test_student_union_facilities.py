"""
Tests for student union facilities module.
Tests facility viewing functionality.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from unittest.mock import Mock, patch

from education_system.university_system.modules.domain.student_affairs.student_union.services import facilities

@pytest.fixture
def mock_context():
    """Mock the context module."""
    ctx = Mock()
    ctx.auth = Mock()
    ctx.auth.current_user = {'id': 1, 'username': 'testuser'}
    ctx.auth.check_permission = Mock(return_value=True)
    return ctx

@pytest.fixture
def sample_facilities():
    """Sample facility data."""
    return [
        (1, 'Conference Room A', 'Building 1, Floor 2', 50, 'Large conference room',
         'Projector, Whiteboard, Video conferencing', 25.00),
        (2, 'Study Room 1', 'Library, Floor 1', 10, 'Small study room',
         'Whiteboard, Chairs, Tables', 5.00),
        (3, 'Auditorium', 'Main Building', 200, 'Large auditorium for events',
         'Stage, Sound system, Lighting', 100.00),
    ]

class TestViewFacilities:
    """Tests for view_facilities function."""

    @patch('builtins.print')
    @patch('education_system.university_system.modules.core.services.student_union_misc.facilities.get_connection')
    @patch('education_system.university_system.modules.core.services.student_union_misc.context')
    def test_view_facilities_success(self, mock_ctx, mock_get_conn, mock_print, sample_facilities):
        """Test viewing facilities successfully."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=True)

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = sample_facilities
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Call function
        facilities.view_facilities()

        # Verify results
        assert any('Available Facilities' in str(call)
                  for call in mock_print.call_args_list)
        assert any('Conference Room A' in str(call)
                  for call in mock_print.call_args_list)
        mock_conn.close.assert_called_once()

    @patch('builtins.print')
    @patch('education_system.university_system.modules.core.services.student_union_misc.context')
    def test_view_facilities_not_logged_in(self, mock_ctx, mock_print):
        """Test viewing facilities when not logged in."""
        # Setup mocks
        mock_ctx.auth = None

        # Call function
        facilities.view_facilities()

        # Verify results
        assert any('must be logged in' in str(call).lower()
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    @patch('education_system.university_system.modules.core.services.student_union_misc.context')
    def test_view_facilities_no_permission(self, mock_ctx, mock_print):
        """Test viewing facilities without permission."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)

        # Call function
        facilities.view_facilities()

        # Verify results
        assert any("don't have permission" in str(call).lower()
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    @patch('education_system.university_system.modules.core.services.student_union_misc.facilities.get_connection')
    @patch('education_system.university_system.modules.core.services.student_union_misc.context')
    def test_view_facilities_no_facilities(self, mock_ctx, mock_get_conn, mock_print):
        """Test viewing when no facilities available."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=True)

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Call function
        facilities.view_facilities()

        # Verify results
        assert any('No available facilities' in str(call)
                  for call in mock_print.call_args_list)
        mock_conn.close.assert_called_once()

    @patch('builtins.print')
    @patch('education_system.university_system.modules.core.services.student_union_misc.facilities.get_connection')
    @patch('education_system.university_system.modules.core.services.student_union_misc.context')
    def test_view_facilities_database_error(self, mock_ctx, mock_get_conn, mock_print):
        """Test handling of database errors."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=True)

        mock_cursor = Mock()
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Call function
        facilities.view_facilities()

        # Verify results
        assert any('Database error' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    @patch('education_system.university_system.modules.core.services.student_union_misc.facilities.get_connection')
    @patch('education_system.university_system.modules.core.services.student_union_misc.context')
    def test_view_facilities_displays_all_fields(self, mock_ctx, mock_get_conn, mock_print,
                                                  sample_facilities):
        """Test that all facility fields are displayed."""
        # Setup mocks
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=True)

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = sample_facilities
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Call function
        facilities.view_facilities()

        # Verify all fields are displayed
        assert any('ID:' in str(call) for call in mock_print.call_args_list)
        assert any('Name:' in str(call) for call in mock_print.call_args_list)
        assert any('Location:' in str(call) for call in mock_print.call_args_list)
        assert any('Capacity:' in str(call) for call in mock_print.call_args_list)
        assert any('Description:' in str(call) for call in mock_print.call_args_list)
        assert any('Equipment:' in str(call) for call in mock_print.call_args_list)
        assert any('Booking Fee:' in str(call) for call in mock_print.call_args_list)

class TestIntegrationFacilities:
    """Integration tests using real database."""

    @pytest.fixture
    def db_conn(self):
        """Create a test database connection."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Create facilities table
        cursor.execute('''
            CREATE TABLE union_facilities (
                facility_id INTEGER PRIMARY KEY AUTOINCREMENT,
                facility_name TEXT,
                location TEXT,
                capacity INTEGER,
                description TEXT,
                equipment TEXT,
                booking_fee REAL,
                status TEXT
            )
        ''')

        # Insert test facilities
        cursor.execute('''
            INSERT INTO union_facilities VALUES
            (1, 'Conference Room A', 'Building 1', 50, 'Large room', 'Projector', 25.00, 'available'),
            (2, 'Study Room 1', 'Library', 10, 'Small room', 'Whiteboard', 5.00, 'available'),
            (3, 'Auditorium', 'Main Building', 200, 'Large auditorium', 'Stage, Sound', 100.00, 'unavailable')
        ''')

        conn.commit()
        yield conn
        conn.close()

    def test_query_available_facilities(self, db_conn):
        """Test querying only available facilities."""
        cursor = db_conn.cursor()

        cursor.execute('''
            SELECT facility_id, facility_name, location, capacity, description, equipment, booking_fee
            FROM union_facilities
            WHERE status = 'available'
            ORDER BY facility_name
        ''')

        facilities = cursor.fetchall()
        assert len(facilities) == 2
        assert facilities[0][1] == 'Conference Room A'
        assert facilities[1][1] == 'Study Room 1'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
