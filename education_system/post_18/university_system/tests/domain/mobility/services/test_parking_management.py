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


# Common mock path prefixes
_PKG = 'education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management'
_PERMITS = f'{_PKG}.permits'
_VEHICLES = f'{_PKG}.vehicles'
_VIOLATIONS = f'{_PKG}.violations'
_LOTS = f'{_PKG}.lots'
_REPORTS = f'{_PKG}.reports'
_MENUS = f'{_PKG}.menus'
_CORE = f'{_PKG}.core'


def _make_auth(role='admin'):
    """Create a mock auth object with permissions."""
    auth = Mock()
    auth.current_user = {'id': 1, 'username': 'testuser', 'role': role}
    auth.check_permission = Mock(return_value=True)
    return auth


class TestParkingManagementCore(unittest.TestCase):
    """Test core parking management functions"""

    def test_module_can_be_imported(self):
        """Test that module can be imported"""
        try:
            from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_management
            self.assertIsNotNone(parking_management)
        except ImportError as e:
            self.fail(f"Failed to import parking_management: {e}")

    def test_set_auth_function(self):
        """Test set_auth function"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import set_auth

        mock_auth = Mock()
        set_auth(mock_auth)

        # Should not raise an error
        self.assertTrue(callable(set_auth))

    @patch(f'{_CORE}.get_connection')
    def test_init_db(self, mock_get_conn):
        """Test database initialization"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import init_db

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [('id',)]  # users table exists
        mock_cursor.fetchone.return_value = (5,)  # parking_lots count
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        init_db()

        # Should call get_connection
        mock_get_conn.assert_called()


class TestParkingPermits(unittest.TestCase):
    """Test parking permit operations"""

    @patch(f'{_PERMITS}.get_connection')
    @patch(f'{_PERMITS}.core')
    def test_create_parking_permit(self, mock_core, mock_get_conn):
        """Test creating a parking permit - auth required, returns early without permission"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import create_parking_permit

        # No auth set -> function returns early
        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            create_parking_permit()

        # get_connection should NOT be called since auth check fails
        mock_get_conn.assert_not_called()

    @patch(f'{_PERMITS}.get_connection')
    @patch(f'{_PERMITS}.core')
    def test_create_parking_permit_with_auth(self, mock_core, mock_get_conn):
        """Test creating a parking permit with auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import create_parking_permit

        mock_core.auth = _make_auth()

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1, 'John', 'Doe', 'john@test.com')
        mock_cursor.fetchall.return_value = []

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Admin path: choice '2' for visitor, then visitor details
        with patch('builtins.input', side_effect=['2', 'John', 'Doe', 'john@test.com',
                                                   '2',  # register new vehicle
                                                   'ABC123', 'Toyota', 'Camry', '2020', 'Blue', 'Sedan', 'CA',
                                                   '1',  # zone A
                                                   '1',  # annual permit
                                                   ]):
            with patch('sys.stdout', new=io.StringIO()):
                with patch(f'{_PERMITS}.send_permit_confirmation'):
                    create_parking_permit()

    @patch(f'{_PERMITS}.get_connection')
    def test_view_parking_permit(self, mock_get_conn):
        """Test viewing a parking permit"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import view_parking_permit

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            'P001', 1, 'John Doe', 'john@test.com', 'A', 'annual',
            '2024-01-01', '2024-12-31', 'Active', 'V001', '2024-01-01'
        )

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_connection

        with patch('builtins.input', return_value='P001'):
            with patch('sys.stdout', new=io.StringIO()):
                view_parking_permit()

        mock_cursor.execute.assert_called()

    @patch(f'{_PERMITS}.get_connection')
    @patch(f'{_PERMITS}.core')
    def test_update_parking_permit(self, mock_core, mock_get_conn):
        """Test updating a parking permit - returns early without auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import update_parking_permit

        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            update_parking_permit()

        mock_get_conn.assert_not_called()

    @patch(f'{_PERMITS}.get_connection')
    @patch(f'{_PERMITS}.core')
    def test_delete_parking_permit(self, mock_core, mock_get_conn):
        """Test deleting a parking permit - returns early without auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import delete_parking_permit

        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            delete_parking_permit()

        mock_get_conn.assert_not_called()


class TestVehicleManagement(unittest.TestCase):
    """Test vehicle management operations"""

    @patch(f'{_VEHICLES}.get_connection')
    @patch(f'{_VEHICLES}.core')
    def test_register_vehicle(self, mock_core, mock_get_conn):
        """Test registering a vehicle - returns early without auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import register_vehicle

        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            register_vehicle()

        mock_get_conn.assert_not_called()

    @patch(f'{_VEHICLES}.get_connection')
    @patch(f'{_VEHICLES}.core')
    def test_view_vehicle(self, mock_core, mock_get_conn):
        """Test viewing a vehicle"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import view_vehicle

        mock_core.auth = _make_auth()

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            'V001', 'ABC123', 'Toyota', 'Camry', 2020, 'Blue', 'Sedan', 1, 'CA',
            'John', 'Doe'
        )

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_connection

        # Choice '2' = search by vehicle ID, then 'V001' = the ID to search
        with patch('builtins.input', side_effect=['2', 'V001']):
            with patch('sys.stdout', new=io.StringIO()):
                view_vehicle()

        mock_cursor.execute.assert_called()

    @patch(f'{_VEHICLES}.get_connection')
    @patch(f'{_VEHICLES}.core')
    def test_update_vehicle(self, mock_core, mock_get_conn):
        """Test updating a vehicle - returns early without auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import update_vehicle

        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            update_vehicle()

        mock_get_conn.assert_not_called()

    @patch(f'{_VEHICLES}.get_connection')
    @patch(f'{_VEHICLES}.core')
    def test_delete_vehicle(self, mock_core, mock_get_conn):
        """Test deleting a vehicle - returns early without auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import delete_vehicle

        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            delete_vehicle()

        mock_get_conn.assert_not_called()


class TestParkingViolations(unittest.TestCase):
    """Test parking violation operations"""

    @patch(f'{_VIOLATIONS}.get_connection')
    @patch(f'{_VIOLATIONS}.core')
    def test_record_violation(self, mock_core, mock_get_conn):
        """Test recording a parking violation - returns early without auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import record_violation

        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            record_violation()

        mock_get_conn.assert_not_called()

    @patch(f'{_VIOLATIONS}.get_connection')
    @patch(f'{_VIOLATIONS}.core')
    def test_view_violations(self, mock_core, mock_get_conn):
        """Test viewing parking violations"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import view_violations

        mock_core.auth = _make_auth()

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ('VIO001', 'V001', 'ABC123', 'Expired Meter', '2024-01-01', 50.00, 'unpaid', 'Lot A', 1, 'Officer Smith')
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_connection

        # Choice '1' = view all violations
        with patch('builtins.input', return_value='1'):
            with patch('sys.stdout', new=io.StringIO()):
                view_violations()

        mock_cursor.execute.assert_called()


class TestParkingLots(unittest.TestCase):
    """Test parking lot operations"""

    @patch(f'{_LOTS}.get_connection')
    def test_view_parking_lots(self, mock_get_conn):
        """Test viewing parking lots"""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ('L001', 'Lot A', 'North Campus', 100, 75, 'A', '24/7')
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_connection

        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import view_parking_lots

        with patch('sys.stdout', new=io.StringIO()):
            view_parking_lots()

        mock_cursor.execute.assert_called()

    @patch(f'{_LOTS}.get_connection')
    @patch(f'{_LOTS}.backup_before_operation')
    @patch(f'{_LOTS}.core')
    def test_add_parking_lot(self, mock_core, mock_backup, mock_get_conn):
        """Test adding a parking lot"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import add_parking_lot

        mock_core.auth = _make_auth()

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (5,)  # count for ID generation

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        with patch('builtins.input', side_effect=['Lot B', 'South Campus', '150', 'B', '24/7']):
            with patch('sys.stdout', new=io.StringIO()):
                add_parking_lot()

        mock_backup.assert_called_once()


class TestReports(unittest.TestCase):
    """Test report generation"""

    @patch(f'{_REPORTS}.get_connection')
    @patch(f'{_REPORTS}.core')
    def test_generate_permit_report(self, mock_core, mock_get_conn):
        """Test generating permit report - returns early without auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import generate_permit_report

        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            generate_permit_report()

        mock_get_conn.assert_not_called()

    @patch(f'{_REPORTS}.get_connection')
    @patch(f'{_REPORTS}.core')
    def test_generate_violation_report(self, mock_core, mock_get_conn):
        """Test generating violation report - returns early without auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import generate_violation_report

        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            generate_violation_report()

        mock_get_conn.assert_not_called()

    @patch(f'{_REPORTS}.get_connection')
    @patch(f'{_REPORTS}.core')
    def test_generate_analytics_dashboard(self, mock_core, mock_get_conn):
        """Test generating analytics dashboard - returns early without auth"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import (
            generate_analytics_dashboard
        )

        mock_core.auth = None

        with patch('sys.stdout', new=io.StringIO()):
            generate_analytics_dashboard()

        mock_get_conn.assert_not_called()


class TestMenus(unittest.TestCase):
    """Test menu functions"""

    @patch('builtins.input', return_value='5')
    @patch(f'{_MENUS}.core')
    def test_display_permit_menu_exit(self, mock_core, mock_input):
        """Test exiting permit menu"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import display_permit_menu

        mock_core.auth = _make_auth()

        with patch('sys.stdout', new=io.StringIO()):
            display_permit_menu()

    @patch('builtins.input', return_value='5')
    @patch(f'{_MENUS}.core')
    def test_display_vehicle_menu_exit(self, mock_core, mock_input):
        """Test exiting vehicle menu"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import display_vehicle_menu

        mock_core.auth = _make_auth()

        with patch('sys.stdout', new=io.StringIO()):
            display_vehicle_menu()

    @patch('builtins.input', return_value='5')
    @patch(f'{_MENUS}.core')
    def test_display_violation_menu_exit(self, mock_core, mock_input):
        """Test exiting violation menu"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import display_violation_menu

        mock_core.auth = _make_auth()

        with patch('sys.stdout', new=io.StringIO()):
            display_violation_menu()


if __name__ == '__main__':
    unittest.main()
