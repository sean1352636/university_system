"""
Comprehensive tests for student_union facilities/facility_management.py module.

Tests cover:
- Equipment management system
- Browsing available equipment
- Checking out equipment
- Returning equipment
- Equipment maintenance tracking
- Facility booking
- Booking approval
- Equipment reports
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities import facility_management

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

class TestBrowseEquipment:
    """Test browsing equipment functionality."""

    @patch('builtins.input', return_value='')
    def test_browse_available_equipment_success(self, mock_input, mock_cursor):
        """Test successfully browsing available equipment."""
        mock_cursor.fetchall.return_value = [
            (1, 'Laptop', 'Technology', 'High-performance laptop', 'Equipment Store', 'good', 'available')
        ]

        facility_management.browse_available_equipment(mock_cursor)

        mock_cursor.execute.assert_called()
        mock_cursor.fetchall.assert_called_once()

    @patch('builtins.input', return_value='')
    def test_browse_equipment_empty(self, mock_input, mock_cursor):
        """Test browsing when no equipment available."""
        mock_cursor.fetchall.return_value = []

        with patch('builtins.print') as mock_print:
            facility_management.browse_available_equipment(mock_cursor)
            assert any('no equipment' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.input', return_value='1')
    def test_view_equipment_details(self, mock_input, mock_cursor):
        """Test viewing detailed equipment information."""
        mock_cursor.fetchall.side_effect = [
            [(1, 'Laptop', 'Technology', 'Description', 'Equipment Store', 'good', 'available')],
            []  # checkout history
        ]
        mock_cursor.fetchone.return_value = (
            'Laptop', 'Technology', 'High-performance laptop', 'MAC001', '2023-01-15',
            'good', 'Equipment Store', 'available', None, 1500.00
        )

        facility_management.browse_available_equipment(mock_cursor)

        assert mock_cursor.execute.call_count >= 2

class TestEquipmentCheckout:
    """Test equipment checkout functionality."""

    @patch('builtins.input', side_effect=['1', 'personal', '2024-02-01', 'good', 'Test notes'])
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.datetime')
    def test_check_out_equipment_success(self, mock_datetime, mock_input, mock_cursor, mock_conn):
        """Test successfully checking out equipment."""
        mock_datetime.now.return_value.strftime.return_value = '2024-01-15 10:00:00'
        mock_cursor.fetchall.side_effect = [
            [],  # no clubs
            [(1, 'Laptop', 'Technology', 'Equipment Store', 'good')]
        ]
        mock_cursor.fetchone.return_value = ('Laptop', 'available')

        facility_management.check_out_equipment('S123', mock_cursor, mock_conn)

        assert mock_cursor.execute.call_count >= 3
        mock_conn.commit.assert_called_once()

    @patch('builtins.input', side_effect=['1', 'club', '1', '2024-02-01', 'good', ''])
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.datetime')
    def test_check_out_equipment_for_club(self, mock_datetime, mock_input, mock_cursor, mock_conn):
        """Test checking out equipment for a club."""
        mock_datetime.now.return_value.strftime.return_value = '2024-01-15 10:00:00'
        mock_cursor.fetchall.side_effect = [
            [(1, 'Test Club', 'President')],  # user's clubs
            [(1, 'Laptop', 'Technology', 'Equipment Store', 'good')]
        ]
        mock_cursor.fetchone.return_value = ('Laptop', 'available')

        facility_management.check_out_equipment('S123', mock_cursor, mock_conn)

        mock_conn.commit.assert_called_once()

    @patch('builtins.input', side_effect=['1'])
    def test_check_out_equipment_unavailable(self, mock_input, mock_cursor, mock_conn):
        """Test checking out unavailable equipment."""
        mock_cursor.fetchall.side_effect = [
            [],
            [(1, 'Laptop', 'Technology', 'Equipment Store', 'good')]
        ]
        mock_cursor.fetchone.return_value = ('Laptop', 'checked_out')

        with patch('builtins.print') as mock_print:
            facility_management.check_out_equipment('S123', mock_cursor, mock_conn)
            assert any('not available' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.input', return_value='invalid')
    def test_check_out_equipment_invalid_id(self, mock_input, mock_cursor, mock_conn):
        """Test checking out with invalid equipment ID."""
        mock_cursor.fetchall.side_effect = [[], [(1, 'Laptop', 'Technology', 'Store', 'good')]]

        with patch('builtins.print') as mock_print:
            facility_management.check_out_equipment('S123', mock_cursor, mock_conn)
            assert any('invalid' in str(call).lower() for call in mock_print.call_args_list)

class TestEquipmentReturn:
    """Test equipment return functionality."""

    @patch('builtins.input', side_effect=['1', 'good', 'No issues'])
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.datetime')
    def test_return_equipment_success(self, mock_datetime, mock_input, mock_cursor, mock_conn):
        """Test successfully returning equipment."""
        mock_datetime.now.return_value.strftime.return_value = '2024-01-20 10:00:00'
        mock_cursor.fetchall.return_value = [
            (1, 'Laptop', '2024-01-15', '2024-02-01', None)
        ]
        mock_cursor.fetchone.return_value = (1, 'Laptop')

        facility_management.return_equipment('S123', mock_cursor, mock_conn)

        assert mock_cursor.execute.call_count >= 3
        mock_conn.commit.assert_called_once()

    @patch('builtins.input', side_effect=['1', 'damaged', 'Screen cracked'])
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.datetime')
    def test_return_equipment_damaged(self, mock_datetime, mock_input, mock_cursor, mock_conn):
        """Test returning damaged equipment."""
        mock_datetime.now.return_value.strftime.return_value = '2024-01-20 10:00:00'
        mock_cursor.fetchall.return_value = [
            (1, 'Laptop', '2024-01-15', '2024-02-01', None)
        ]
        mock_cursor.fetchone.return_value = (1, 'Laptop')

        with patch('builtins.print') as mock_print:
            facility_management.return_equipment('S123', mock_cursor, mock_conn)
            # Should print maintenance required message
            assert any('maintenance' in str(call).lower() for call in mock_print.call_args_list)

    def test_return_equipment_no_checkouts(self, mock_cursor, mock_conn):
        """Test returning when no equipment checked out."""
        mock_cursor.fetchall.return_value = []

        with patch('builtins.print') as mock_print:
            facility_management.return_equipment('S123', mock_cursor, mock_conn)
            assert any('no equipment' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.input', return_value='invalid')
    def test_return_equipment_invalid_id(self, mock_input, mock_cursor, mock_conn):
        """Test returning with invalid checkout ID."""
        mock_cursor.fetchall.return_value = [(1, 'Laptop', '2024-01-15', '2024-02-01', None)]

        with patch('builtins.print') as mock_print:
            facility_management.return_equipment('S123', mock_cursor, mock_conn)
            assert any('invalid' in str(call).lower() for call in mock_print.call_args_list)

class TestViewEquipmentCheckouts:
    """Test viewing equipment checkouts."""

    def test_view_my_equipment_checkouts_success(self, mock_cursor):
        """Test viewing user's equipment checkouts."""
        mock_cursor.fetchall.return_value = [
            (1, 'Laptop', '2024-01-15 10:00', '2024-02-01', None, 'good', None, 'checked_out', None)
        ]

        facility_management.view_my_equipment_checkouts('S123', mock_cursor)

        mock_cursor.execute.assert_called()
        mock_cursor.fetchall.assert_called_once()

    def test_view_my_equipment_checkouts_empty(self, mock_cursor):
        """Test viewing when no checkouts exist."""
        mock_cursor.fetchall.return_value = []

        with patch('builtins.print') as mock_print:
            facility_management.view_my_equipment_checkouts('S123', mock_cursor)
            assert any('no equipment' in str(call).lower() for call in mock_print.call_args_list)

    def test_view_equipment_checkout_statistics(self, mock_cursor):
        """Test viewing checkout statistics."""
        mock_cursor.fetchall.return_value = [
            (1, 'Laptop', '2024-01-15 10:00', '2024-02-01', '2024-01-31 15:00', 'good', 'good', 'returned', None)
        ]

        facility_management.view_my_equipment_checkouts('S123', mock_cursor)

        # Should display statistics
        mock_cursor.fetchall.assert_called_once()

class TestSearchEquipment:
    """Test equipment search functionality."""

    @patch('builtins.input', return_value='laptop')
    def test_search_equipment_success(self, mock_input, mock_cursor):
        """Test successfully searching equipment."""
        mock_cursor.fetchall.return_value = [
            (1, 'Laptop', 'Technology', 'High-performance laptop', 'Equipment Store', 'good', 'available')
        ]

        facility_management.search_equipment(mock_cursor)

        mock_cursor.execute.assert_called()
        mock_cursor.fetchall.assert_called_once()

    @patch('builtins.input', return_value='nonexistent')
    def test_search_equipment_no_results(self, mock_input, mock_cursor):
        """Test searching with no results."""
        mock_cursor.fetchall.return_value = []

        with patch('builtins.print') as mock_print:
            facility_management.search_equipment(mock_cursor)
            assert any('no equipment' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.input', return_value='')
    def test_search_equipment_empty_term(self, mock_input, mock_cursor):
        """Test searching with empty search term."""
        with patch('builtins.print') as mock_print:
            facility_management.search_equipment(mock_cursor)
            assert any('cannot be empty' in str(call).lower() for call in mock_print.call_args_list)

class TestAddNewEquipment:
    """Test adding new equipment (admin only)."""

    @patch('builtins.input', side_effect=[
        'Laptop', 'Technology', 'High-performance laptop', 'MAC001',
        'Equipment Store', '1500', '2023-01-15', 'good'
    ])
    def test_add_new_equipment_success(self, mock_input, mock_cursor, mock_conn):
        """Test successfully adding new equipment."""
        facility_management.add_new_equipment(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called_once()

    @patch('builtins.input', return_value='')
    def test_add_new_equipment_empty_name(self, mock_input, mock_cursor, mock_conn):
        """Test adding equipment with empty name."""
        with patch('builtins.print') as mock_print:
            facility_management.add_new_equipment(mock_cursor, mock_conn)
            assert any('cannot be empty' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=[
        'Laptop', 'Technology', 'Description', '',
        'Store', 'invalid', '2023-01-15', 'good'
    ])
    def test_add_equipment_invalid_cost(self, mock_input, mock_cursor, mock_conn):
        """Test adding equipment with invalid cost."""
        # Should handle invalid cost gracefully (default to 0.0)
        facility_management.add_new_equipment(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()

class TestUpdateEquipmentStatus:
    """Test updating equipment status (admin only)."""

    @patch('builtins.input', side_effect=['1', '1', 'good'])
    def test_update_equipment_condition(self, mock_input, mock_cursor, mock_conn):
        """Test updating equipment condition."""
        mock_cursor.fetchone.return_value = ('Laptop', 'good', 'available', 'Equipment Store')

        facility_management.update_equipment_status(mock_cursor, mock_conn)

        assert mock_cursor.execute.call_count >= 2
        mock_conn.commit.assert_called_once()

    @patch('builtins.input', side_effect=['1', '2', 'maintenance_required'])
    def test_update_equipment_availability(self, mock_input, mock_cursor, mock_conn):
        """Test updating equipment availability."""
        mock_cursor.fetchone.return_value = ('Laptop', 'good', 'available', 'Equipment Store')

        facility_management.update_equipment_status(mock_cursor, mock_conn)

        mock_conn.commit.assert_called_once()

    @patch('builtins.input', side_effect=['1', '3', 'New Location'])
    def test_update_equipment_location(self, mock_input, mock_cursor, mock_conn):
        """Test updating equipment location."""
        mock_cursor.fetchone.return_value = ('Laptop', 'good', 'available', 'Equipment Store')

        facility_management.update_equipment_location(mock_cursor, mock_conn)

        mock_conn.commit.assert_called_once()

    @patch('builtins.input', side_effect=['invalid'])
    def test_update_equipment_invalid_id(self, mock_input, mock_cursor, mock_conn):
        """Test updating with invalid equipment ID."""
        with patch('builtins.print') as mock_print:
            facility_management.update_equipment_status(mock_cursor, mock_conn)
            assert any('invalid' in str(call).lower() for call in mock_print.call_args_list)

class TestMaintenanceTracking:
    """Test equipment maintenance tracking."""

    @patch('builtins.input', side_effect=['1', '5'])
    def test_view_equipment_needing_maintenance(self, mock_input, mock_cursor, mock_conn):
        """Test viewing equipment needing maintenance."""
        mock_cursor.fetchall.return_value = [
            (1, 'Laptop', 'poor', 'maintenance_required', '2024-02-01', 'Equipment Store')
        ]

        facility_management.equipment_maintenance_tracking(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', side_effect=['2', '1', '2024-02-15', '5'])
    def test_schedule_maintenance(self, mock_input, mock_cursor, mock_conn):
        """Test scheduling maintenance."""
        facility_management.equipment_maintenance_tracking(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    @patch('builtins.input', side_effect=['3', '1', 'good', '2024-06-01', '5'])
    def test_complete_maintenance(self, mock_input, mock_cursor, mock_conn):
        """Test completing maintenance."""
        facility_management.equipment_maintenance_tracking(mock_cursor, mock_conn)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

class TestEquipmentReports:
    """Test equipment reporting functionality."""

    @patch('builtins.input', return_value='1')
    def test_inventory_summary_report(self, mock_input, mock_cursor):
        """Test generating inventory summary report."""
        mock_cursor.fetchall.return_value = [
            ('Technology', 10, 8, 1, 1, 0)
        ]

        facility_management.generate_equipment_reports(mock_cursor)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', return_value='2')
    def test_usage_statistics_report(self, mock_input, mock_cursor):
        """Test generating usage statistics report."""
        mock_cursor.fetchall.return_value = [
            ('Laptop', 25, 7.5)
        ]

        facility_management.generate_equipment_reports(mock_cursor)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', return_value='3')
    def test_overdue_equipment_report(self, mock_input, mock_cursor):
        """Test generating overdue equipment report."""
        mock_cursor.fetchall.return_value = [
            ('Laptop', 'John', 'Doe', 'john@example.com', '2024-01-15', '2024-01-10', 5)
        ]

        facility_management.generate_equipment_reports(mock_cursor)

        mock_cursor.execute.assert_called()

    @patch('builtins.input', return_value='4')
    def test_maintenance_schedule_report(self, mock_input, mock_cursor):
        """Test generating maintenance schedule report."""
        mock_cursor.fetchall.return_value = [
            (1, 'Laptop', '2024-02-01', 'good', 'Equipment Store')
        ]

        facility_management.generate_equipment_reports(mock_cursor)

        mock_cursor.execute.assert_called()

class TestFacilityBooking:
    """Test facility booking functionality."""

    @patch('builtins.input', side_effect=[
        '1', '2024-02-01', '10:00', '12:00', 'n', 'Meeting', ''
    ])
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.view_facilities', create=True)
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.send_confirmation_email')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.get_connection')
    def test_request_facility_booking_success(self, mock_get_conn, mock_email, mock_view, mock_input, mock_auth):
        """Test successfully requesting facility booking."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            ('S123',),  # student_id
            ('Main Hall',),  # facility exists
            (0,)  # time slot available
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        facility_management.auth = mock_auth

        facility_management.request_facility_booking()

        mock_conn.commit.assert_called_once()
        mock_email.assert_called()

    @patch('builtins.input', side_effect=[
        '1', '2024-02-01', '10:00', '12:00', 'y', '1', 'Meeting', ''
    ])
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.view_facilities', create=True)
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.send_confirmation_email')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.get_connection')
    def test_request_booking_for_club(self, mock_get_conn, mock_email, mock_view, mock_input, mock_auth):
        """Test requesting facility booking for a club."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            ('S123',),
            ('Main Hall',),
            (0,),
        ]
        mock_cursor.fetchall.side_effect = [
            [(1, 'Test Club')]  # user's clubs
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        facility_management.auth = mock_auth

        facility_management.request_facility_booking()

        mock_conn.commit.assert_called()

class TestAuthSetup:
    """Test authentication setup."""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance."""
        facility_management.set_auth(mock_auth)

        assert facility_management.auth == mock_auth

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_database_error_handling(self, mock_cursor):
        """Test handling database errors."""
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        with patch('builtins.input', return_value=''):
            with patch('builtins.print') as mock_print:
                facility_management.browse_available_equipment(mock_cursor)
                assert any('error' in str(call).lower() for call in mock_print.call_args_list)

    def test_manage_equipment_system_not_logged_in(self):
        """Test accessing equipment system without login."""
        facility_management.auth = None

        with patch('builtins.print') as mock_print:
            with patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.get_connection'):
                facility_management.manage_equipment_system()
                assert any('logged in' in str(call).lower() for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.facilities.facility_management.get_connection')
    def test_no_student_record(self, mock_get_conn, mock_auth):
        """Test handling when user has no student record."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        facility_management.auth = mock_auth

        with patch('builtins.print') as mock_print:
            facility_management.manage_equipment_system()
            assert any('no student' in str(call).lower() for call in mock_print.call_args_list)
