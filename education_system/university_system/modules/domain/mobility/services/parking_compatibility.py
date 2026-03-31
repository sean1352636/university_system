"""
Parking Management Compatibility Module

This module ensures backward compatibility between the new GUI interface
and the existing console-based parking management system.

It provides wrapper functions and compatibility layers to bridge any
differences between the GUI and console implementations.
"""

import sys
import os
import io
from contextlib import redirect_stdout, redirect_stderr
import functools

from education_system.university_system.modules.shared.utils.i18n import get_text

# Global flag to track if we're running in GUI mode
GUI_MODE = False

def set_gui_mode(enabled=True):
    """Set whether the system is running in GUI mode"""
    global GUI_MODE
    GUI_MODE = enabled

def is_gui_mode():
    """Check if the system is running in GUI mode"""
    return GUI_MODE

class OutputCapture:
    """Context manager to capture console output for GUI display"""

    def __init__(self):
        self.stdout_capture = io.StringIO()
        self.stderr_capture = io.StringIO()
        self.output = ""
        self.error = ""

    def __enter__(self):
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        sys.stdout = self.stdout_capture
        sys.stderr = self.stderr_capture
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        self.output = self.stdout_capture.getvalue()
        self.error = self.stderr_capture.getvalue()

    def get_output(self):
        """Get captured stdout"""
        return self.output

    def get_error(self):
        """Get captured stderr"""
        return self.error

    def get_combined(self):
        """Get combined stdout and stderr"""
        return self.output + self.error

def gui_compatible(func):
    """Decorator to make console functions compatible with GUI"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if GUI_MODE:
            # In GUI mode, capture output instead of printing to console
            with OutputCapture() as capture:
                try:
                    result = func(*args, **kwargs)
                    return {
                        'success': True,
                        'result': result,
                        'output': capture.get_output(),
                        'error': capture.get_error()
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'result': None,
                        'output': capture.get_output(),
                        'error': capture.get_error() + str(e)
                    }
        else:
            # In console mode, run normally
            return func(*args, **kwargs)

    return wrapper

def mock_input(prompt="", default=""):
    """Mock input function for GUI mode"""
    if GUI_MODE:
        # In GUI mode, return default value or empty string
        return default
    else:
        # In console mode, use normal input
        return input(prompt)

def safe_import(module_name, fallback=None):
    """Safely import a module with fallback"""
    try:
        return __import__(module_name)
    except ImportError:
        if fallback:
            return fallback
        return None

def ensure_parking_management_compatibility():
    """Ensure compatibility with the existing parking_management.py module"""

    try:
        # Try to import the parking management module from the refactored services
        import education_system.university_system.modules.domain.mobility.services.parking_management as parking_management

        # If we're in GUI mode, monkey-patch input function
        if GUI_MODE:
            parking_management.input = mock_input  # type: ignore[attr-defined]

        return True
    except ImportError:
        return False

def validate_database_schema():
    """Validate that the database schema is compatible"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        # Check if required tables exist
        required_tables = [
            'users', 'parking_permits', 'vehicles',
            'parking_violations', 'parking_lots'
        ]

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]

        missing_tables = [table for table in required_tables if table not in existing_tables]

        conn.close()

        if missing_tables:
            print(get_text("mobility.parking.validation.missing_tables", "Warning: Missing database tables: {tables}").format(tables=missing_tables))
            return False

        return True
    except Exception as e:
        print(get_text("mobility.parking.validation.schema_error", "Error validating database schema: {error}").format(error=e))
        return False

def initialize_compatibility_layer():
    """Initialize the compatibility layer"""

    # Ensure parking management compatibility
    if not ensure_parking_management_compatibility():
        print(get_text("mobility.parking.compatibility.parking_management_failed", "Warning: Could not ensure parking management compatibility"))

    # Validate database schema
    if not validate_database_schema():
        print(get_text("mobility.parking.compatibility.schema_validation_failed", "Warning: Database schema validation failed"))

    # Set up GUI-specific configurations
    if GUI_MODE:
        # Disable certain console-specific features
        setup_gui_environment()

def setup_gui_environment():
    """Set up environment variables and configurations for GUI mode"""

    # Suppress matplotlib GUI warnings if using plotting
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
    except ImportError:
        pass

    # Set environment variables for GUI mode
    os.environ['PARKING_GUI_MODE'] = '1'

def get_function_output(func, *args, **kwargs):
    """Execute a function and return its output for GUI display"""

    with OutputCapture() as capture:
        try:
            result = func(*args, **kwargs)
            return {
                'success': True,
                'result': result,
                'output': capture.get_output(),
                'error': capture.get_error()
            }
        except Exception as e:
            return {
                'success': False,
                'result': None,
                'output': capture.get_output(),
                'error': capture.get_error() + f"\nException: {str(e)}"
            }

class ConsoleToGUIAdapter:
    """Adapter class to make console functions work with GUI"""

    def __init__(self):
        self.original_functions = {}

    def wrap_function(self, module, function_name):
        """Wrap a console function for GUI use"""

        if hasattr(module, function_name):
            original_func = getattr(module, function_name)
            self.original_functions[function_name] = original_func

            @functools.wraps(original_func)
            def gui_wrapper(*args, **kwargs):
                return get_function_output(original_func, *args, **kwargs)

            setattr(module, function_name, gui_wrapper)

    def restore_function(self, module, function_name):
        """Restore original console function"""

        if function_name in self.original_functions:
            setattr(module, function_name, self.original_functions[function_name])

def create_gui_menu_mapping():
    """Create mapping between GUI actions and console functions"""

    try:
        # Import the parking management module from the refactored services
        import education_system.university_system.modules.domain.mobility.services.parking_management as pm


        return {
            'permits': {
                'create': pm.create_parking_permit,
                'view': pm.view_parking_permit,
                'update': pm.update_parking_permit,
                'delete': pm.delete_parking_permit
            },
            'vehicles': {
                'register': pm.register_vehicle,
                'view': pm.view_vehicle,
                'update': pm.update_vehicle,
                'delete': pm.delete_vehicle
            },
            'violations': {
                'record': pm.record_violation,
                'view': pm.view_violations,
                'update': pm.update_violation,
                'delete': pm.delete_violation
            },
            'lots': {
                'view': pm.view_parking_lots,
                'add': pm.add_parking_lot,
                'update': pm.update_parking_lot,
                'delete': pm.delete_parking_lot
            },
            'reports': {
                'permits': pm.generate_permit_report,
                'violations': pm.generate_violation_report,
                'analytics': pm.generate_analytics_dashboard
            },
            'export': {
                'permits': lambda fmt: pm.export_permits(fmt),
                'vehicles': lambda fmt: pm.export_vehicles(fmt),
                'violations': lambda fmt: pm.export_violations(fmt),
                'lots': lambda fmt: pm.export_parking_lots(fmt)
            }
        }
    except ImportError:
        return {}

class InputSimulator:
    """Simulate user input for console functions when running in GUI mode"""

    def __init__(self):
        self.responses = {}
        self.response_queue = []

    def set_responses(self, responses):
        """Set predefined responses for input prompts"""
        self.responses = responses

    def queue_response(self, response):
        """Queue a response for the next input call"""
        self.response_queue.append(response)

    def mock_input(self, prompt=""):
        """Mock input function that returns predefined responses"""

        # Try to get response from queue first
        if self.response_queue:
            return self.response_queue.pop(0)

        # Look for response based on prompt
        for key, value in self.responses.items():
            if key.lower() in prompt.lower():
                return value

        # Return empty string as default
        return ""

# Global input simulator instance
input_simulator = InputSimulator()

def patch_input_for_gui():
    """Patch the built-in input function for GUI compatibility"""

    if GUI_MODE:
        import builtins
        builtins.input = input_simulator.mock_input

def restore_input():
    """Restore the original input function"""

    import builtins
    builtins.input = input

def execute_console_function_with_params(func, params=None):
    """Execute a console function with GUI-provided parameters"""

    if params:
        input_simulator.set_responses(params)

    patch_input_for_gui()

    try:
        result = get_function_output(func)
        return result
    finally:
        restore_input()

def format_console_output_for_gui(output):
    """Format console output for better GUI display"""

    if not output:
        return ""

    # Remove excessive newlines
    formatted = output.strip()

    # Replace multiple consecutive newlines with double newlines
    import re
    formatted = re.sub(r'\n{3,}', '\n\n', formatted)

    # Clean up formatting characters
    formatted = formatted.replace('=' * 50, '-' * 50)
    formatted = formatted.replace('=' * 100, '-' * 80)

    return formatted

def validate_gui_data(data, data_type):
    """Validate data from GUI forms before passing to console functions"""

    validators = {
        'permit': {
            'required': ['full_name', 'email', 'zone', 'permit_type'],
            'email_fields': ['email'],
            'date_fields': ['start_date', 'end_date']
        },
        'vehicle': {
            'required': ['license_plate', 'make', 'model', 'year'],
            'numeric_fields': ['year'],
            'uppercase_fields': ['license_plate', 'registration_state']
        },
        'violation': {
            'required': ['license_plate', 'violation_type', 'location', 'fine_amount'],
            'numeric_fields': ['fine_amount'],
            'uppercase_fields': ['license_plate']
        },
        'lot': {
            'required': ['lot_name', 'location', 'total_spaces', 'zone'],
            'numeric_fields': ['total_spaces']
        }
    }

    if data_type not in validators:
        return True, get_text("mobility.parking.validation.unknown_data_type", "Unknown data type")

    validator = validators[data_type]
    errors = []

    # Check required fields
    for field in validator.get('required', []):
        if field not in data or not data[field]:
            errors.append(get_text("mobility.parking.validation.field_required", "Field '{field}' is required").format(field=field))

    # Validate email fields
    for field in validator.get('email_fields', []):
        if field in data and data[field]:
            if '@' not in data[field]:
                errors.append(get_text("mobility.parking.validation.invalid_email", "Field '{field}' must be a valid email address").format(field=field))

    # Validate numeric fields
    for field in validator.get('numeric_fields', []):
        if field in data and data[field]:
            try:
                float(data[field])
            except ValueError:
                errors.append(get_text("mobility.parking.validation.must_be_number", "Field '{field}' must be a number").format(field=field))

    # Validate date fields
    for field in validator.get('date_fields', []):
        if field in data and data[field]:
            try:
                from datetime import datetime
                datetime.strptime(data[field], '%Y-%m-%d')
            except ValueError:
                errors.append(get_text("mobility.parking.validation.invalid_date_format", "Field '{field}' must be in YYYY-MM-DD format").format(field=field))

    # Auto-format uppercase fields
    for field in validator.get('uppercase_fields', []):
        if field in data and data[field]:
            data[field] = data[field].upper()

    return len(errors) == 0, errors

def get_user_permissions():
    """Get current user permissions for GUI access control"""

    try:
        # Pull the shared auth object from the refactored parking management
        from education_system.university_system.modules.domain.mobility.services.parking_management import auth
        if auth and auth.current_user:
            return {
                'user': auth.current_user,
                'permissions': {
                    'create_permit': auth.check_permission('create_permit'),
                    'view_any_permit': auth.check_permission('view_any_permit'),
                    'view_own_permit': auth.check_permission('view_own_permit'),
                    'update_any_permit': auth.check_permission('update_any_permit'),
                    'update_own_permit': auth.check_permission('update_own_permit'),
                    'delete_any_permit': auth.check_permission('delete_any_permit'),
                    'register_vehicle': auth.check_permission('register_vehicle'),
                    'register_own_vehicle': auth.check_permission('register_own_vehicle'),
                    'view_any_vehicle': auth.check_permission('view_any_vehicle'),
                    'view_own_vehicle': auth.check_permission('view_own_vehicle'),
                    'update_any_vehicle': auth.check_permission('update_any_vehicle'),
                    'update_own_vehicle': auth.check_permission('update_own_vehicle'),
                    'delete_any_vehicle': auth.check_permission('delete_any_vehicle'),
                    'delete_own_vehicle': auth.check_permission('delete_own_vehicle'),
                    'record_violation': auth.check_permission('record_violation'),
                    'view_any_violation': auth.check_permission('view_any_violation'),
                    'view_own_violation': auth.check_permission('view_own_violation'),
                    'update_violation': auth.check_permission('update_violation'),
                    'delete_violation': auth.check_permission('delete_violation'),
                    'manage_parking_lots': auth.check_permission('manage_parking_lots'),
                    'generate_reports': auth.check_permission('generate_reports'),
                    'export_data': auth.check_permission('export_data')
                }
            }
    except (ImportError, AttributeError):
        pass

    # Default permissions for fallback
    return {
        'user': None,
        'permissions': {
            'create_permit': False,
            'view_any_permit': False,
            'view_own_permit': False,
            'update_any_permit': False,
            'update_own_permit': False,
            'delete_any_permit': False,
            'register_vehicle': False,
            'register_own_vehicle': False,
            'view_any_vehicle': False,
            'view_own_vehicle': False,
            'update_any_vehicle': False,
            'update_own_vehicle': False,
            'delete_any_vehicle': False,
            'delete_own_vehicle': False,
            'record_violation': False,
            'view_any_violation': False,
            'view_own_violation': False,
            'update_violation': False,
            'delete_violation': False,
            'manage_parking_lots': False,
            'generate_reports': False,
            'export_data': False
        }
    }

def cleanup_compatibility_layer():
    """Clean up the compatibility layer when shutting down"""

    # Restore original functions
    restore_input()

    # Clear environment variables
    if 'PARKING_GUI_MODE' in os.environ:
        del os.environ['PARKING_GUI_MODE']

    # Reset GUI mode
    set_gui_mode(False)

# Initialize compatibility layer when module is imported
if __name__ != "__main__":
    initialize_compatibility_layer()