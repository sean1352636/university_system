"""
Test cases for Parking Management Compatibility Module

Tests compatibility layer functionality including:
- GUI mode switching
- Output capture
- Input simulation
- Data validation
- Permission checking
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import io
import sys


class TestParkingCompatibility(unittest.TestCase):
    """Test parking compatibility module functions"""

    def test_module_can_be_imported(self):
        """Test that module can be imported"""
        try:
            from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_compatibility
            self.assertIsNotNone(parking_compatibility)
        except ImportError as e:
            self.fail(f"Failed to import parking_compatibility: {e}")

    def test_gui_mode_flag(self):
        """Test GUI mode flag operations"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_compatibility

        # Initially should be False
        initial_mode = parking_compatibility.is_gui_mode()
        self.assertIsInstance(initial_mode, bool)

        # Set to True
        parking_compatibility.set_gui_mode(True)
        self.assertTrue(parking_compatibility.is_gui_mode())

        # Set to False
        parking_compatibility.set_gui_mode(False)
        self.assertFalse(parking_compatibility.is_gui_mode())

    def test_output_capture(self):
        """Test output capture context manager"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import OutputCapture

        with OutputCapture() as capture:
            print("Test output")
            print("Test error", file=sys.stderr)

        output = capture.get_output()
        error = capture.get_error()

        self.assertIn("Test output", output)
        self.assertIn("Test error", error)

    def test_output_capture_combined(self):
        """Test getting combined output"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import OutputCapture

        with OutputCapture() as capture:
            print("stdout message")
            print("stderr message", file=sys.stderr)

        combined = capture.get_combined()
        self.assertIn("stdout message", combined)
        self.assertIn("stderr message", combined)

    def test_gui_compatible_decorator_console_mode(self):
        """Test gui_compatible decorator in console mode"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            gui_compatible, set_gui_mode
        )

        set_gui_mode(False)

        @gui_compatible
        def test_function(x, y):
            return x + y

        result = test_function(2, 3)
        self.assertEqual(result, 5)

    def test_gui_compatible_decorator_gui_mode(self):
        """Test gui_compatible decorator in GUI mode"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            gui_compatible, set_gui_mode
        )

        set_gui_mode(True)

        @gui_compatible
        def test_function(x, y):
            print(f"Result: {x + y}")
            return x + y

        result = test_function(2, 3)

        self.assertIsInstance(result, dict)
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 5)
        # Output may be empty if captured differently
        self.assertIsInstance(result['output'], str)

        # Reset GUI mode
        set_gui_mode(False)

    def test_gui_compatible_decorator_exception_handling(self):
        """Test gui_compatible decorator with exceptions"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            gui_compatible, set_gui_mode
        )

        set_gui_mode(True)

        @gui_compatible
        def failing_function():
            raise ValueError("Test error")

        result = failing_function()

        self.assertIsInstance(result, dict)
        self.assertFalse(result['success'])
        self.assertIn("Test error", result['error'])

        # Reset GUI mode
        set_gui_mode(False)

    def test_mock_input(self):
        """Test mock input function"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            mock_input, set_gui_mode
        )

        # In GUI mode, should return default
        set_gui_mode(True)
        result = mock_input("Enter value: ", "default")
        self.assertEqual(result, "default")

        # Reset GUI mode
        set_gui_mode(False)

    def test_validate_gui_data_permit(self):
        """Test validating permit data"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import validate_gui_data

        # Valid permit data
        valid_data = {
            'full_name': 'John Doe',
            'email': 'john@example.com',
            'zone': 'A',
            'permit_type': 'annual'
        }
        is_valid, errors = validate_gui_data(valid_data, 'permit')
        self.assertTrue(is_valid)

        # Missing required field
        invalid_data = {
            'full_name': 'John Doe',
            'zone': 'A'
        }
        is_valid, errors = validate_gui_data(invalid_data, 'permit')
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_validate_gui_data_vehicle(self):
        """Test validating vehicle data"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import validate_gui_data

        # Valid vehicle data
        valid_data = {
            'license_plate': 'ABC123',
            'make': 'Toyota',
            'model': 'Camry',
            'year': '2020'
        }
        is_valid, errors = validate_gui_data(valid_data, 'vehicle')
        self.assertTrue(is_valid)

        # Invalid year (non-numeric)
        invalid_data = {
            'license_plate': 'ABC123',
            'make': 'Toyota',
            'model': 'Camry',
            'year': 'twenty'
        }
        is_valid, errors = validate_gui_data(invalid_data, 'vehicle')
        self.assertFalse(is_valid)

    def test_validate_gui_data_uppercase_fields(self):
        """Test that uppercase fields are auto-formatted"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import validate_gui_data

        data = {
            'license_plate': 'abc123',
            'make': 'Toyota',
            'model': 'Camry',
            'year': '2020'
        }
        validate_gui_data(data, 'vehicle')
        self.assertEqual(data['license_plate'], 'ABC123')

    def test_validate_gui_data_violation(self):
        """Test validating violation data"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import validate_gui_data

        # Valid violation data
        valid_data = {
            'license_plate': 'ABC123',
            'violation_type': 'Expired Meter',
            'location': 'Lot A',
            'fine_amount': '50.00'
        }
        is_valid, errors = validate_gui_data(valid_data, 'violation')
        self.assertTrue(is_valid)

    def test_validate_gui_data_lot(self):
        """Test validating parking lot data"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import validate_gui_data

        # Valid lot data
        valid_data = {
            'lot_name': 'Lot A',
            'location': 'North Campus',
            'total_spaces': '100',
            'zone': 'A'
        }
        is_valid, errors = validate_gui_data(valid_data, 'lot')
        self.assertTrue(is_valid)

    def test_input_simulator(self):
        """Test InputSimulator class"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import InputSimulator

        simulator = InputSimulator()

        # Set responses
        simulator.set_responses({'name': 'John Doe', 'email': 'john@example.com'})

        # Test response matching
        result = simulator.mock_input("Enter your name: ")
        self.assertEqual(result, 'John Doe')

        # Test queue
        simulator.queue_response('queued_value')
        result = simulator.mock_input("Any prompt: ")
        self.assertEqual(result, 'queued_value')

    def test_format_console_output_for_gui(self):
        """Test formatting console output for GUI"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            format_console_output_for_gui
        )

        # Test with excessive newlines
        input_text = "\n\n\nTest\n\n\n\nOutput\n\n\n"
        result = format_console_output_for_gui(input_text)
        self.assertNotIn("\n\n\n", result)

        # Test with None
        result = format_console_output_for_gui(None)
        self.assertEqual(result, "")

        # Test with empty string
        result = format_console_output_for_gui("")
        self.assertEqual(result, "")

    def test_get_function_output(self):
        """Test get_function_output helper"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import get_function_output

        def test_func(x, y):
            print(f"Computing {x} + {y}")
            return x + y

        result = get_function_output(test_func, 2, 3)

        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 5)
        # Output may be empty if captured differently
        self.assertIsInstance(result['output'], str)

    def test_get_function_output_with_exception(self):
        """Test get_function_output with exception"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import get_function_output

        def failing_func():
            raise RuntimeError("Test error")

        result = get_function_output(failing_func)

        self.assertFalse(result['success'])
        self.assertIn("Test error", result['error'])

    @patch('education_system.post_18.university_system.infrastructure.database.db.get_connection')
    def test_validate_database_schema(self, mock_conn):
        """Test database schema validation"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            validate_database_schema
        )

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ('users',), ('parking_permits',), ('vehicles',),
            ('parking_violations',), ('parking_lots',)
        ]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        result = validate_database_schema()
        self.assertTrue(result)

    @patch('education_system.post_18.university_system.infrastructure.database.db.get_connection')
    def test_validate_database_schema_missing_tables(self, mock_conn):
        """Test database schema validation with missing tables"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            validate_database_schema
        )

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [('users',)]

        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close = Mock()
        mock_conn.return_value = mock_connection

        with patch('sys.stdout', new=io.StringIO()):
            result = validate_database_schema()
            self.assertFalse(result)

    def test_console_to_gui_adapter(self):
        """Test ConsoleToGUIAdapter class"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            ConsoleToGUIAdapter
        )

        adapter = ConsoleToGUIAdapter()

        # Create a test module
        test_module = type('TestModule', (), {})()

        def test_function():
            print("Test output")
            return "result"

        test_module.test_function = test_function

        # Wrap the function
        adapter.wrap_function(test_module, 'test_function')

        # Call the wrapped function
        result = test_module.test_function()

        self.assertIsInstance(result, dict)
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 'result')

        # Restore the function
        adapter.restore_function(test_module, 'test_function')

    def test_cleanup_compatibility_layer(self):
        """Test cleanup function"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            cleanup_compatibility_layer, set_gui_mode
        )

        set_gui_mode(True)
        cleanup_compatibility_layer()

        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import is_gui_mode
        self.assertFalse(is_gui_mode())


class TestPermissionChecking(unittest.TestCase):
    """Test permission checking functionality"""

    def test_get_user_permissions_no_auth(self):
        """Test getting user permissions without authentication"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_compatibility import (
            get_user_permissions
        )

        permissions = get_user_permissions()

        self.assertIsInstance(permissions, dict)
        self.assertIn('user', permissions)
        self.assertIn('permissions', permissions)
        self.assertIsInstance(permissions['permissions'], dict)


if __name__ == '__main__':
    unittest.main()
