"""
Entry points and utility functions for the Activity Logger GUI.
"""

import sys

from ._imports import LOGGER_AVAILABLE, MATPLOTLIB_AVAILABLE
from .main_gui import EnhancedActivityLoggerGUI


def main(auth=None):
    """Main entry point for the GUI application"""
    try:
        # Initialize and run the GUI
        app = EnhancedActivityLoggerGUI(auth=auth)
        app.run()

    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


def launch_logger_gui(auth=None):
    """Launch the logger GUI - backward compatibility function"""
    main(auth=auth)


def create_gui_instance(auth=None):
    """Create GUI instance without running - for embedding in other applications"""
    return EnhancedActivityLoggerGUI(auth=auth)


def check_dependencies():
    """Check if all required dependencies are available"""
    dependencies = {
        'logger': LOGGER_AVAILABLE,
        'matplotlib': MATPLOTLIB_AVAILABLE,
        'tkinter': True  # Should always be available in standard Python
    }

    missing = [dep for dep, available in dependencies.items() if not available]

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        return False
    return True


def get_gui_version():
    """Get the current GUI version"""
    return "2.0.0"


def print_startup_banner():
    """Print the startup banner with system info"""
    print(f"""
    +===============================================================+
    |                Enhanced Activity Logger GUI                     |
    |                        Version {get_gui_version()}                           |
    |                                                               |
    |  A comprehensive management console for activity logging      |
    |  with real-time monitoring, analytics, and security features  |
    +===============================================================+

    System Status:
    - Logger Module: {'Available' if LOGGER_AVAILABLE else 'Missing (Demo Mode)'}
    - Charts Support: {'Available' if MATPLOTLIB_AVAILABLE else 'Missing'}
    - Python Version: {sys.version.split()[0]}
    - Platform: {sys.platform}

    """)


def run_demo_mode():
    """Run the GUI in demonstration mode when logger is not available"""
    print("Running in DEMO MODE")
    print("This mode allows you to explore the GUI interface without a working logger.")
    print("Some features will be simulated or disabled.")
    print()
    return True


def check_installation():
    """Check if the logger is properly installed and configured"""
    if not LOGGER_AVAILABLE:
        print("Setup Instructions:")
        print("1. Ensure 'simple_activity_logger.py' is in the same directory")
        print("2. Or install the logger package: pip install enhanced-activity-logger")
        print("3. Check that all dependencies are installed")
        print()
        return False
    return True
