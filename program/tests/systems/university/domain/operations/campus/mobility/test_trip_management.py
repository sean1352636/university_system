"""
Test cases for Trip Management Service

Tests all trip management functionality including:
- Trip creation and management
- Trip registration
- Participant management
- Payment tracking
- Calendar integration
- Reports
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import io
import sys


class TestTripManagementCore(unittest.TestCase):
    """Test core trip management functions"""

    def test_module_can_be_imported(self):
        """Test that module can be imported"""
        try:
            from education_system.systems.university.domain.operations.campus.mobility.services import trip_management
            self.assertIsNotNone(trip_management)
        except ImportError as e:
            self.fail(f"Failed to import trip_management: {e}")

    def test_set_auth_function(self):
        """Test set_auth function"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import set_auth

        mock_auth = Mock()
        set_auth(mock_auth)

        # Should not raise an error
        self.assertTrue(callable(set_auth))

    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.transaction')
    def test_init_trip_db(self, mock_transaction):
        """Test database initialization"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import init_trip_db

        mock_conn = Mock()
        mock_transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_transaction.return_value.__exit__ = Mock()

        init_trip_db()

        # Should call transaction
        mock_transaction.assert_called()


class TestTripCreation(unittest.TestCase):
    """Test trip creation operations"""

    @patch('builtins.input', side_effect=[
        'City Tour', 'Tour of the city', '2024-06-01', '2024-06-05',
        'City Center', '50', '200.00'
    ])
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.log_activity')
    def test_create_trip(self, mock_log, mock_conn, mock_input):
        """Test creating a trip"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import create_trip

        mock_cursor = Mock()
        mock_cursor.lastrowid = 123

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.commit = Mock()
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            create_trip()

        mock_log.assert_called_once()

    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    def test_view_trips(self, mock_conn):
        """Test viewing trips"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import view_trips

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, 'City Tour', 'Tour of the city', '2024-06-01', '2024-06-05',
             'City Center', 50, 200.00, 1)
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            view_trips()

        mock_cursor.execute.assert_called_once()

    @patch('builtins.input', return_value='123')
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    def test_view_trip_details(self, mock_conn, mock_input):
        """Test viewing trip details"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import view_trip_details

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            123, 'City Tour', 'Tour of the city', '2024-06-01', '2024-06-05',
            'City Center', 50, 200.00, 1
        )
        mock_cursor.fetchall.return_value = []

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            view_trip_details(123)

    @patch('builtins.input', side_effect=['123', '2', '2024-06-10'])
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.log_activity')
    def test_update_trip(self, mock_log, mock_conn, mock_input):
        """Test updating a trip"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import update_trip

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            123, 'City Tour', 'Tour of the city', '2024-06-01', '2024-06-05',
            'City Center', 50, 200.00, 1
        )

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.commit = Mock()
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            update_trip()

    @patch('builtins.input', side_effect=['123', 'yes'])
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.log_activity')
    def test_delete_trip(self, mock_log, mock_conn, mock_input):
        """Test deleting a trip"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import delete_trip

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (123, 'City Tour')

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.commit = Mock()
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            delete_trip()

        mock_log.assert_called_once()


class TestTripRegistration(unittest.TestCase):
    """Test trip registration operations"""

    @patch('builtins.input', side_effect=['123', 'student1', 'yes'])
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.log_activity')
    def test_register_for_trip(self, mock_log, mock_conn, mock_input):
        """Test registering for a trip"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import register_for_trip

        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            (123, 'City Tour', 50, 200.00),  # Trip details
            (10,),  # Current participant count
            None  # No existing registration
        ]
        mock_cursor.lastrowid = 456

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.commit = Mock()
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            register_for_trip()

        mock_log.assert_called_once()

    @patch('builtins.input', return_value='student1')
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    def test_view_my_trip_registrations(self, mock_conn, mock_input):
        """Test viewing user's trip registrations"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            view_my_trip_registrations
        )

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, 'City Tour', '2024-06-01', 'confirmed', 'paid', 200.00)
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            view_my_trip_registrations()

        mock_cursor.execute.assert_called_once()


class TestParticipantManagement(unittest.TestCase):
    """Test participant management operations"""

    @patch('builtins.input', side_effect=['123', '1', '1', '1', '0'])
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    def test_manage_trip_participants(self, mock_conn, mock_input):
        """Test managing trip participants"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            manage_trip_participants
        )

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (123, 'City Tour')
        mock_cursor.fetchall.return_value = [
            (1, 'student1', 'John Doe', 'confirmed', 'paid', '2024-01-01')
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.commit = Mock()
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            manage_trip_participants()


class TestPaymentManagement(unittest.TestCase):
    """Test payment management operations"""

    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.log_activity')
    def test_update_payment_status(self, mock_log, mock_conn):
        """Test updating payment status"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            update_payment_status
        )

        mock_connection = Mock()
        mock_connection.cursor.return_value = Mock()
        mock_connection.commit = Mock()
        mock_conn.return_value = mock_connection

        participants = [(1, 'student1', 'John Doe', 'confirmed', 'pending', '2024-01-01')]

        with patch('builtins.input', side_effect=['1', '1', 'paid', '']):
            with patch('sys.stdout', new=io.StringIO()):
                update_payment_status(mock_connection, 123, participants)


class TestCalendarIntegration(unittest.TestCase):
    """Test calendar integration"""

    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    def test_view_trips_with_calendar(self, mock_conn):
        """Test viewing trips with calendar"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            view_trips_with_calendar
        )

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, 'City Tour', '2024-06-01', '2024-06-05', 'City Center')
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('builtins.input', side_effect=['2024', '6']):
            with patch('sys.stdout', new=io.StringIO()):
                view_trips_with_calendar()


class TestReports(unittest.TestCase):
    """Test report generation"""

    def test_setup_report_permissions(self):
        """Test setting up report permissions"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            setup_report_permissions
        )

        # Should not raise an error
        setup_report_permissions()


class TestMenuFunction(unittest.TestCase):
    """Test menu function"""

    def test_display_trip_management_menu_exit(self):
        """Test exiting trip management menu"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            display_trip_management_menu, _common
        )
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import menu as _menu_mod

        # Set up auth so all permission checks pass, giving a known menu size
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'test', 'role': 'admin'}
        mock_auth.check_permission.return_value = True

        original_auth = _common.auth
        original_cal = getattr(_menu_mod, 'CALENDAR_AVAILABLE', False)
        try:
            _common.auth = mock_auth
            _menu_mod.CALENDAR_AVAILABLE = False
            # 8 permission-based options + exit at 9
            with patch('builtins.input', return_value='9'):
                with patch('sys.stdout', new=io.StringIO()):
                    display_trip_management_menu()
        finally:
            _common.auth = original_auth
            _menu_mod.CALENDAR_AVAILABLE = original_cal


class TestDatabaseConnection(unittest.TestCase):
    """Test database connection utilities"""

    def test_get_db_connection_function_exists(self):
        """Test that get_db_connection function exists"""
        from education_system.systems.university.domain.operations.campus.mobility.services import trip_management

        self.assertTrue(hasattr(trip_management, 'get_db_connection'))
        self.assertTrue(callable(trip_management.get_db_connection))

    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_connection')
    def test_get_db_connection(self, mock_get_connection):
        """Test get_db_connection function"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            get_db_connection
        )

        mock_conn = Mock()
        mock_get_connection.return_value = mock_conn

        result = get_db_connection()

        self.assertEqual(result, mock_conn)
        mock_get_connection.assert_called_once()

    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_connection')
    def test_safe_db_operation(self, mock_get_connection):
        """Test safe_db_operation wrapper"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            safe_db_operation
        )

        mock_conn = Mock()
        mock_get_connection.return_value = mock_conn

        def test_operation():
            return "success"

        result = safe_db_operation(test_operation)

        self.assertEqual(result, "success")


class TestPermissions(unittest.TestCase):
    """Test permission setup"""

    def test_setup_trip_permissions(self):
        """Test setting up trip permissions"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            setup_trip_permissions
        )

        # Should not raise an error
        setup_trip_permissions()


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def test_create_trip_empty_name(self):
        """Test creating trip with no auth returns gracefully"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import (
            create_trip, _common
        )

        original_auth = _common.auth
        try:
            _common.auth = None
            with patch('sys.stdout', new=io.StringIO()):
                result = create_trip()
                self.assertFalse(result)
        finally:
            _common.auth = original_auth

    @patch('builtins.input', return_value='999')
    @patch('education_system.systems.university.domain.operations.campus.mobility.services.trip_management.get_db_connection')
    def test_view_trip_details_not_found(self, mock_conn, mock_input):
        """Test viewing details of non-existent trip"""
        from education_system.systems.university.domain.operations.campus.mobility.services.trip_management import view_trip_details

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()) as output:
            view_trip_details(999)
            # Should handle not found case


if __name__ == '__main__':
    unittest.main()
