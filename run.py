#!/usr/bin/env python3
"""
University Management System - Main Runner
Entry point for choosing between CLI and GUI interfaces
"""

import sys
import os
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import error logging utilities
from university_system.utils import log_error, log_critical_error
from university_system.tests.run_all_tests import main as run_all_tests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global exception handler will be handled in try-except blocks

def display_interface_menu():
    """Display interface selection menu"""
    print("\n" + "="*60)
    print("UNIVERSITY MANAGEMENT SYSTEM")
    print("="*60)
    print("\nPlease choose your interface:")
    print("1. 🖥️  Command Line Interface (CLI)")
    print("2. 🖼️  Graphical User Interface (GUI)")
    print("3. run tests")
    print("4. 🚪 Exit")
    print("-" * 60)

    while True:
        try:
            choice = input("\nEnter your choice (1-4): ").strip()

            if choice == '1':
                return 'cli'
            elif choice == '2':
                return 'gui'
            elif choice == '3':
                run_all_tests()
            elif choice == '4':
                print("\n👋 Goodbye!")
                sys.exit(0)
            else:
                print("❌ Invalid choice. Please enter 1, 2, 3 or 4.")

        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            sys.exit(0)
        except EOFError:
            print("\n\n👋 Exiting...")
            sys.exit(0)

def run_cli_mode():
    """Run the application in CLI mode"""
    logger.info("Starting Command Line Interface")
    print("Starting Command Line Interface...")
    try:
        # Import and run CLI main
        sys.path.insert(0, os.path.dirname(__file__))
        from university_system.cli_main import main
        return main()
    except ImportError as e:
        log_error(e, {"mode": "CLI", "function": "run_cli_mode"}, __file__, "run_cli_mode")
        logger.error(f"CLI Import Error: {e}")
        print(f"❌ CLI Import Error: {e}")
        print("Make sure all dependencies are installed and the project structure is correct.")
        return False
    except (OSError, RuntimeError, ValueError) as e:
        log_error(e, {"mode": "CLI", "function": "run_cli_mode"}, __file__, "run_cli_mode")
        logger.error(f"CLI Application Error: {e}")
        print(f"❌ CLI Application Error: {e}")
        return False
    except Exception as e:
        log_error(e, {"mode": "CLI", "function": "run_cli_mode"}, __file__, "run_cli_mode")
        logger.error(f"CLI Application Error: {e}", exc_info=True)
        print(f"❌ CLI Application Error: {e}")
        return False

def run_gui_mode():
    """Run the application in GUI mode"""
    logger.info("Starting Graphical User Interface")
    print("Starting Graphical User Interface...")
    try:
        # Import and run GUI main
        sys.path.insert(0, os.path.dirname(__file__))
        from university_system.modules.shared.gui.main_gui import run_gui_interface
        return run_gui_interface()
    except ImportError as e:
        log_error(e, {"mode": "GUI", "function": "run_gui_mode", "fallback": "CLI"}, __file__, "run_gui_mode")
        logger.error(f"GUI Import Error: {e}")
        print(f"❌ GUI Import Error: {e}")
        print("⚠️  GUI mode is not available. Make sure all GUI dependencies are installed.")
        print("Falling back to CLI mode...")
        return run_cli_mode()
    except (OSError, RuntimeError, ValueError, AttributeError) as e:
        log_error(e, {"mode": "GUI", "function": "run_gui_mode", "fallback": "CLI"}, __file__, "run_gui_mode")
        logger.error(f"GUI Application Error: {e}")
        print(f"❌ GUI Application Error: {e}")
        print("Falling back to CLI mode...")
        return run_cli_mode()
    except Exception as e:
        log_error(e, {"mode": "GUI", "function": "run_gui_mode", "fallback": "CLI"}, __file__, "run_gui_mode")
        logger.error(f"GUI Application Error: {e}", exc_info=True)
        print(f"❌ GUI Application Error: {e}")
        print("Falling back to CLI mode...")
        return run_cli_mode()

def main():
    """Main application entry point"""
    try:
        # Ensure directory structure exists
        logger.info("Ensuring directory structure")
        from university_system.modules.shared.constants.paths import ensure_directories
        ensure_directories()

        # Initialize auth instance early to prevent warnings during imports
        logger.info("Initializing auth system")
        from university_system.infrastructure.auth.user_authentication import UserAuth
        from university_system.infrastructure.shared_context import set_auth

        # Create and set auth instance
        auth_instance = UserAuth()
        set_auth(auth_instance)
        logger.info("Auth system initialized successfully")

        # Initialize database on startup
        logger.info("Initializing database")
        print("Initializing database...")
        from university_system.infrastructure.database.database_utils import init_db
        if not init_db():
            logger.warning("Database initialization encountered issues")
            print("⚠️  Database initialization encountered issues. The application will continue, but some features may not work correctly.")

        # Check for command line arguments
        if len(sys.argv) > 1:
            mode = sys.argv[1].lower()
            if mode in ['--cli', '-c', 'cli']:
                return run_cli_mode()
            elif mode in ['--gui', '-g', 'gui']:
                return run_gui_mode()
            elif mode in ['--test', '-t', 'test']:
                logger.info("Running all tests")
                print("\n🧪 Running all tests...")
                run_all_tests()
                return True
            elif mode in ['--help', '-h', 'help']:
                print("Usage: python run.py [mode]")
                print("\nModes:")
                print("  --cli, -c, cli     Start in CLI mode")
                print("  --gui, -g, gui     Start in GUI mode")
                print("  --test, -t, test   Run all tests")
                print("  --help, -h         Show this help message")
                print("\nIf no mode is specified, an interactive menu will be shown.")
                return True
            else:
                logger.warning(f"Unknown argument: {mode}")
                print(f"❌ Unknown argument: {mode}")
                print("Use --help for usage information.")
                return False

        # No command line arguments - show interactive menu
        interface_choice = display_interface_menu()

        if interface_choice == 'cli':
            return run_cli_mode()
        elif interface_choice == 'gui':
            return run_gui_mode()

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        print("\n\nApplication interrupted by user. Goodbye!")
        return True
    except (ImportError, OSError, RuntimeError) as e:
        log_error(e, {"function": "main", "location": "main_application_loop"}, __file__, "main")
        logger.error(f"Application Main Loop Error: {e}")
        print(f"❌ Application Main Loop Error: {e}")
        return False
    except Exception as e:
        log_error(e, {"function": "main", "location": "main_application_loop"}, __file__, "main")
        logger.error(f"Application Main Loop Error: {e}", exc_info=True)
        print(f"❌ Application Main Loop Error: {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except (SystemError, MemoryError, KeyboardInterrupt) as e:
        log_critical_error(e, {"location": "main_entry_point", "critical": True})
        logger.critical(f"Critical System Error: {e}", exc_info=True)
        print(f"❌ Critical System Error: {e}")
        sys.exit(1)
    except Exception as e:
        log_critical_error(e, {"location": "main_entry_point", "critical": True})
        logger.critical(f"Unexpected Critical Error: {e}", exc_info=True)
        print(f"❌ Unexpected Critical Error: {e}")
        sys.exit(1)
