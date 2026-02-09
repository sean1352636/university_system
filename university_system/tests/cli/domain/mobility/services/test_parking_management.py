"""
Test cases for Parking Management Service

Tests all parking management functionality including:
- Parking permits CRUD operations
- Vehicle registration and management
- Parking violations
- Parking lots management
- Reports and analytics
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import io
import sys


class TestParkingManagementCore(unittest.TestCase):
    """Test core parking management functions"""

    def test_module_can_be_imported(self):
        """Test that module can be imported"""
        try:
            from university_system.modules.domain.mobility.services import parking_management
            self.assertIsNotNone(parking_management)
        except ImportError as e:
            self.fail(f"Failed to import parking_management: {e}")

    def test_set_auth_function(self):
        """Test set_auth function"""
        from university_system.modules.domain.mobility.services.parking_management import set_auth

        mock_auth = Mock()
        set_auth(mock_auth)

        # Should not raise an error
        self.assertTrue(callable(set_auth))

    @patch('university_system.modules.domain.mobility.services.parking_management.transaction')
    def test_init_db(self, mock_transaction):
        """Test database initialization"""
        from university_system.modules.domain.mobility.services.parking_management import init_db

        mock_conn = Mock()
        mock_transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_transaction.return_value.__exit__ = Mock()

        init_db()

        # Should call transaction
        mock_transaction.assert_called()


class TestParkingPermits(unittest.TestCase):
    """Test parking permit operations"""

    @patch('builtins.input', side_effect=['John Doe', 'john@test.com', 'A', '1', '2024-01-01', '2024-12-31', '100'])
    @patch('university_system.modules.domain.mobility.services.parking_management.transaction')
    @patch('university_system.modules.domain.mobility.services.parking_management.log_activity')
    def test_create_parking_permit(self, mock_log, mock_transaction, mock_input):
        """Test creating a parking permit"""
        from university_system.modules.domain.mobility.services.parking_management import create_parking_permit

        mock_cursor = Mock()
        mock_cursor.lastrowid = 123

        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor

        mock_transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_transaction.return_value.__exit__ = Mock()

        with patch('sys.stdout', new=io.StringIO()):
            create_parking_permit()

        mock_log.assert_called_once()

    @patch('builtins.input', return_value='123')
    @patch('university_system.modules.domain.mobility.services.parking_management.get_connection')
    def test_view_parking_permit(self, mock_conn, mock_input):
        """Test viewing a parking permit"""
        from university_system.modules.domain.mobility.services.parking_management import view_parking_permit

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            123, 'John Doe', 'john@test.com', 'A', 'annual',
            '2024-01-01', '2024-12-31', 'active', 100.00
        )

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            view_parking_permit()

        mock_cursor.execute.assert_called_once()

    @patch('builtins.input', side_effect=['123', '2', '2', '2025-01-01'])
    @patch('university_system.modules.domain.mobility.services.parking_management.get_connection')
    @patch('university_system.modules.domain.mobility.services.parking_management.transaction')
    @patch('university_system.modules.domain.mobility.services.parking_management.log_activity')
    def test_update_parking_permit(self, mock_log, mock_transaction, mock_get_conn, mock_input):
        """Test updating a parking permit"""
        from university_system.modules.domain.mobility.services.parking_management import update_parking_permit

        # Mock get_connection for viewing
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            123, 'John Doe', 'john@test.com', 'A', 'annual',
            '2024-01-01', '2024-12-31', 'active', 100.00
        )

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_get_conn.return_value = mock_connection

        # Mock transaction for updating
        mock_trans_conn = Mock()
        mock_transaction.return_value.__enter__ = Mock(return_value=mock_trans_conn)
        mock_transaction.return_value.__exit__ = Mock()

        with patch('sys.stdout', new=io.StringIO()):
            update_parking_permit()

    @patch('builtins.input', side_effect=['123', 'yes'])
    @patch('university_system.modules.domain.mobility.services.parking_management.transaction')
    @patch('university_system.modules.domain.mobility.services.parking_management.log_activity')
    def test_delete_parking_permit(self, mock_log, mock_transaction, mock_input):
        """Test deleting a parking permit"""
        from university_system.modules.domain.mobility.services.parking_management import delete_parking_permit

        mock_conn = Mock()
        mock_transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_transaction.return_value.__exit__ = Mock()

        with patch('sys.stdout', new=io.StringIO()):
            delete_parking_permit()

        mock_log.assert_called_once()


class TestVehicleManagement(unittest.TestCase):
    """Test vehicle management operations"""

    @patch('builtins.input', side_effect=['ABC123', 'Toyota', 'Camry', '2020', 'Blue', 'CA', '123'])
    @patch('university_system.modules.domain.mobility.services.parking_management.transaction')
    @patch('university_system.modules.domain.mobility.services.parking_management.log_activity')
    def test_register_vehicle(self, mock_log, mock_transaction, mock_input):
        """Test registering a vehicle"""
        from university_system.modules.domain.mobility.services.parking_management import register_vehicle

        mock_cursor = Mock()
        mock_cursor.lastrowid = 456

        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor

        mock_transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_transaction.return_value.__exit__ = Mock()

        with patch('sys.stdout', new=io.StringIO()):
            register_vehicle()

        mock_log.assert_called_once()

    @patch('builtins.input', return_value='ABC123')
    @patch('university_system.modules.domain.mobility.services.parking_management.get_connection')
    def test_view_vehicle(self, mock_conn, mock_input):
        """Test viewing a vehicle"""
        from university_system.modules.domain.mobility.services.parking_management import view_vehicle

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            456, 'ABC123', 'Toyota', 'Camry', 2020, 'Blue', 'CA', 123
        )

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            view_vehicle()

        mock_cursor.execute.assert_called_once()

    @patch('builtins.input', side_effect=['ABC123', '2', 'Red'])
    @patch('university_system.modules.domain.mobility.services.parking_management.get_connection')
    @patch('university_system.modules.domain.mobility.services.parking_management.transaction')
    @patch('university_system.modules.domain.mobility.services.parking_management.log_activity')
    def test_update_vehicle(self, mock_log, mock_transaction, mock_get_conn, mock_input):
        """Test updating a vehicle"""
        from university_system.modules.domain.mobility.services.parking_management import update_vehicle

        # Mock get_connection for viewing
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            456, 'ABC123', 'Toyota', 'Camry', 2020, 'Blue', 'CA', 123
        )

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_get_conn.return_value = mock_connection

        # Mock transaction for updating
        mock_trans_conn = Mock()
        mock_transaction.return_value.__enter__ = Mock(return_value=mock_trans_conn)
        mock_transaction.return_value.__exit__ = Mock()

        with patch('sys.stdout', new=io.StringIO()):
            update_vehicle()

    @patch('builtins.input', side_effect=['ABC123', 'yes'])
    @patch('university_system.modules.domain.mobility.services.parking_management.transaction')
    @patch('university_system.modules.domain.mobility.services.parking_management.log_activity')
    def test_delete_vehicle(self, mock_log, mock_transaction, mock_input):
        """Test deleting a vehicle"""
        from university_system.modules.domain.mobility.services.parking_management import delete_vehicle

        mock_conn = Mock()
        mock_transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_transaction.return_value.__exit__ = Mock()

        with patch('sys.stdout', new=io.StringIO()):
            delete_vehicle()

        mock_log.assert_called_once()


class TestParkingViolations(unittest.TestCase):
    """Test parking violation operations"""

    @patch('builtins.input', side_effect=['ABC123', 'Expired Meter', 'Lot A', '50.00', 'Officer Smith'])
    @patch('university_system.modules.domain.mobility.services.parking_management.transaction')
    @patch('university_system.modules.domain.mobility.services.parking_management.log_activity')
    def test_record_violation(self, mock_log, mock_transaction, mock_input):
        """Test recording a parking violation"""
        from university_system.modules.domain.mobility.services.parking_management import record_violation

        mock_cursor = Mock()
        mock_cursor.lastrowid = 789

        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor

        mock_transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_transaction.return_value.__exit__ = Mock()

        with patch('sys.stdout', new=io.StringIO()):
            record_violation()

        mock_log.assert_called_once()

    @patch('builtins.input', return_value='ABC123')
    @patch('university_system.modules.domain.mobility.services.parking_management.get_connection')
    def test_view_violations(self, mock_conn, mock_input):
        """Test viewing parking violations"""
        from university_system.modules.domain.mobility.services.parking_management import view_violations

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (789, 'ABC123', 'Expired Meter', 'Lot A', '2024-01-01', 50.00, 'unpaid', 'Officer Smith')
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            view_violations()

        mock_cursor.execute.assert_called_once()


class TestParkingLots(unittest.TestCase):
    """Test parking lot operations"""

    @patch('university_system.modules.domain.mobility.services.parking_management.get_connection')
    def test_view_parking_lots(self, mock_conn):
        """Test viewing parking lots"""
        from university_system.modules.domain.mobility.services.parking_management import view_parking_lots

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, 'Lot A', 'North Campus', 100, 75, 'A', 1)
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            view_parking_lots()

        mock_cursor.execute.assert_called_once()

    @patch('builtins.input', side_effect=['Lot B', 'South Campus', '150', 'B'])
    @patch('university_system.modules.domain.mobility.services.parking_management.transaction')
    @patch('university_system.modules.domain.mobility.services.parking_management.log_activity')
    def test_add_parking_lot(self, mock_log, mock_transaction, mock_input):
        """Test adding a parking lot"""
        from university_system.modules.domain.mobility.services.parking_management import add_parking_lot

        mock_cursor = Mock()
        mock_cursor.lastrowid = 2

        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor

        mock_transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_transaction.return_value.__exit__ = Mock()

        with patch('sys.stdout', new=io.StringIO()):
            add_parking_lot()

        mock_log.assert_called_once()


class TestReports(unittest.TestCase):
    """Test report generation"""

    @patch('university_system.modules.domain.mobility.services.parking_management.get_connection')
    def test_generate_permit_report(self, mock_conn):
        """Test generating permit report"""
        from university_system.modules.domain.mobility.services.parking_management import generate_permit_report

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (123, 'John Doe', 'john@test.com', 'A', 'annual', 'active')
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            generate_permit_report()

    @patch('university_system.modules.domain.mobility.services.parking_management.get_connection')
    def test_generate_violation_report(self, mock_conn):
        """Test generating violation report"""
        from university_system.modules.domain.mobility.services.parking_management import generate_violation_report

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (789, 'ABC123', 'Expired Meter', '2024-01-01', 50.00, 'unpaid')
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            generate_violation_report()

    @patch('university_system.modules.domain.mobility.services.parking_management.get_connection')
    def test_generate_analytics_dashboard(self, mock_conn):
        """Test generating analytics dashboard"""
        from university_system.modules.domain.mobility.services.parking_management import (
            generate_analytics_dashboard
        )

        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [(100,), (50,), (25,), (15000.00,)]
        mock_cursor.fetchall.return_value = []

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            generate_analytics_dashboard()


class TestMenus(unittest.TestCase):
    """Test menu functions"""

    @patch('builtins.input', return_value='5')
    def test_display_permit_menu_exit(self, mock_input):
        """Test exiting permit menu"""
        from university_system.modules.domain.mobility.services.parking_management import display_permit_menu

        with patch('sys.stdout', new=io.StringIO()):
            display_permit_menu()

    @patch('builtins.input', return_value='5')
    def test_display_vehicle_menu_exit(self, mock_input):
        """Test exiting vehicle menu"""
        from university_system.modules.domain.mobility.services.parking_management import display_vehicle_menu

        with patch('sys.stdout', new=io.StringIO()):
            display_vehicle_menu()

    @patch('builtins.input', return_value='4')
    def test_display_violation_menu_exit(self, mock_input):
        """Test exiting violation menu"""
        from university_system.modules.domain.mobility.services.parking_management import display_violation_menu

        with patch('sys.stdout', new=io.StringIO()):
            display_violation_menu()


if __name__ == '__main__':
    unittest.main()
