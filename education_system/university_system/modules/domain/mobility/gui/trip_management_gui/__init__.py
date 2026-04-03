from education_system.university_system.modules.domain.mobility.gui.trip_management_gui.main_gui import TripManagementGUI
from education_system.university_system.modules.domain.mobility.gui.trip_management_gui._imports import safe_db_operation
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from tkinter import messagebox

try:
    from education_system.university_system.infrastructure.shared_context import get_auth as get_centralized_auth
except ImportError:
    def get_centralized_auth():
        return None

try:
    from education_system.university_system.core.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

import logging


# Backwards compatibility functions
def create_trip_gui(auth_instance):
    """Create and return a GUI instance - backwards compatible function"""
    return TripManagementGUI(auth_instance)

def run_trip_management_gui(auth_instance=None):
    """Run the trip management GUI - main entry point"""
    try:
        # Import original functions to ensure they're available
        from education_system.university_system.modules.domain.mobility.services import trip_management

        # Validate authentication
        if not auth_instance or not auth_instance.current_user:
            print("Error: Authentication required for Trip Management GUI")
            return False

        if not auth_instance.check_permission('view_trips'):
            print("Error: Insufficient permissions to access Trip Management")
            return False

        # Create and run GUI
        gui = TripManagementGUI(auth_instance)
        gui.run()

        return True

    except ImportError as e:
        print(f"Error: Missing required modules: {e}")
        return False
    except Exception as e:
        print(f"Error starting Trip Management GUI: {e}")
        logging.error(f"Trip Management GUI error: {e}")
        return False

# Integration function for backwards compatibility
def integrate_with_existing_system():
    """Integrate GUI with existing trip management system"""
    try:
        # Import original functions

        print("Trip Management GUI integrated successfully!")
        print("Use run_trip_management_gui(auth_instance) to start the GUI")

        return True

    except ImportError as e:
        print(f"Warning: Could not import original trip_management module: {e}")
        print("GUI will work independently but some features may be limited")
        return False

# Command-line interface compatibility
def display_trip_management_menu_gui(auth_instance):
    """GUI version of the original menu function - backwards compatible"""
    return run_trip_management_gui(auth_instance)


__all__ = [
    'TripManagementGUI', 'safe_db_operation',
    'create_trip_gui', 'run_trip_management_gui',
    'integrate_with_existing_system', 'display_trip_management_menu_gui',
]
