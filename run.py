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

# Import i18n after path setup
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _,
    get_current_language_name,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_selector,
    display_language_menu_option,
    get_startup_language_choice,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
)

# Global exception handler will be handled in try-except blocks

def display_interface_menu():
    """Display interface selection menu"""
    print("\n" + "="*60)
    print(_("menu.title").center(60))
    print("="*60)
    print(f"\n{_('menu.choose_interface')}")
    print(f"1. {_('menu.option_cli')}")
    print(f"2. {_('menu.option_gui')}")
    print(f"3. {_('menu.option_tests')}")
    print(f"4. {_('menu.option_language')} [{get_current_language_name()}]")
    print(f"5. {_('menu.option_exit')}")
    print("-" * 60)

    while True:
        try:
            choice = input(f"\n{_('menu.enter_choice', count=5)} ").strip()

            if choice == '1':
                return 'cli'
            elif choice == '2':
                return 'gui'
            elif choice == '3':
                run_all_tests()
            elif choice == '4':
                display_language_menu_option()
                return display_interface_menu()  # Re-display menu in new language
            elif choice == '5':
                print(f"\n{_('menu.goodbye')}")
                sys.exit(0)
            else:
                print(_("menu.invalid_choice"))

        except KeyboardInterrupt:
            print(f"\n\n{_('menu.exiting')}")
            sys.exit(0)
        except EOFError:
            print(f"\n\n{_('menu.exiting')}")
            sys.exit(0)

def run_cli_mode():
    """Run the application in CLI mode"""
    logger.info("Starting Command Line Interface")

    try:
        # Show language selector before starting CLI
        logger.info("Showing language selector for CLI")
        selected_lang = display_language_selector(force_show=True)
        logger.info(f"Language selected: {selected_lang}")

        # Re-initialize i18n with selected language
        init_i18n(selected_lang)

        print(_("startup.starting_cli"))

        from university_system.modules.shared.cli.cli_main import main
        return main()
    except ImportError as e:
        log_error(e, {"mode": "CLI", "function": "run_cli_mode"}, __file__, "run_cli_mode")
        logger.error(f"CLI Import Error: {e}")
        print(_("errors.cli_import", error=str(e)))
        print(_("errors.check_dependencies"))
        return False
    except (OSError, RuntimeError, ValueError) as e:
        log_error(e, {"mode": "CLI", "function": "run_cli_mode"}, __file__, "run_cli_mode")
        logger.error(f"CLI Application Error: {e}")
        print(_("errors.cli_error", error=str(e)))
        return False
    except Exception as e:
        log_error(e, {"mode": "CLI", "function": "run_cli_mode"}, __file__, "run_cli_mode")
        logger.error(f"CLI Application Error: {e}", exc_info=True)
        print(_("errors.cli_error", error=str(e)))
        return False

def run_gui_mode():
    """Run the application in GUI mode"""
    logger.info("Starting Graphical User Interface")

    try:
        # Show language selector popup before starting GUI
        logger.info("Showing language selector")
        selected_lang = show_gui_language_selector()
        logger.info(f"Language selected: {selected_lang}")

        # Re-initialize i18n with selected language
        init_i18n(selected_lang)

        print(_("startup.starting_gui"))

        from university_system.modules.shared.gui.main import run_gui_interface
        return run_gui_interface()
    except ImportError as e:
        log_error(e, {"mode": "GUI", "function": "run_gui_mode", "fallback": "CLI"}, __file__, "run_gui_mode")
        logger.error(f"GUI Import Error: {e}")
        print(_("errors.gui_import", error=str(e)))
        print(_("errors.gui_not_available"))
        print(_("errors.fallback_cli"))
        return run_cli_mode()
    except (OSError, RuntimeError, ValueError, AttributeError) as e:
        log_error(e, {"mode": "GUI", "function": "run_gui_mode", "fallback": "CLI"}, __file__, "run_gui_mode")
        logger.error(f"GUI Application Error: {e}")
        print(_("errors.gui_error", error=str(e)))
        print(_("errors.fallback_cli"))
        return run_cli_mode()
    except Exception as e:
        log_error(e, {"mode": "GUI", "function": "run_gui_mode", "fallback": "CLI"}, __file__, "run_gui_mode")
        logger.error(f"GUI Application Error: {e}", exc_info=True)
        print(_("errors.gui_error", error=str(e)))
        print(_("errors.fallback_cli"))
        return run_cli_mode()


def main():
    """Main application entry point"""
    try:
        # Ensure directory structure exists
        logger.info("Ensuring directory structure")
        from university_system.modules.shared.constants.paths import ensure_directories
        ensure_directories()

        # Initialize i18n system - show language selector on first run
        logger.info("Initializing i18n system")
        get_startup_language_choice()

        # Initialize auth instance early to prevent warnings during imports
        logger.info("Initializing auth system")
        from university_system.infrastructure.auth import UserAuth
        from university_system.infrastructure.shared_context import set_auth

        # Create and set auth instance
        auth_instance = UserAuth()
        set_auth(auth_instance)
        logger.info("Auth system initialized successfully")

        # Initialize database on startup
        logger.info("Initializing database")
        print(_("startup.initializing_db"))
        from university_system.infrastructure.database.database_utils import init_db
        if not init_db():
            logger.warning("Database initialization encountered issues")
            print(f"  {_('startup.db_warning')}")

        # Check for command line arguments
        if len(sys.argv) > 1:
            mode = sys.argv[1].lower()
            if mode in ['--cli', '-c', 'cli']:
                return run_cli_mode()
            elif mode in ['--gui', '-g', 'gui']:
                return run_gui_mode()
            elif mode in ['--test', '-t', 'test']:
                logger.info("Running all tests")
                print(f"\n  {_('startup.running_tests')}")
                run_all_tests()
                return True
            elif mode in ['--lang', '-l', 'lang']:
                display_language_selector(force_show=True)
                return True
            elif mode in ['--help', '-h', 'help']:
                print(_("help.usage"))
                print(f"\n{_('help.modes_title')}")
                print(_("help.mode_cli"))
                print(_("help.mode_gui"))
                print(_("help.mode_test"))
                print(_("help.mode_lang"))
                print(_("help.mode_help"))
                print(f"\n{_('help.interactive_note')}")
                return True
            else:
                logger.warning(f"Unknown argument: {mode}")
                print(f"  {_('startup.unknown_argument', arg=mode)}")
                print(_("startup.use_help"))
                return False

        # No command line arguments - show interactive menu
        interface_choice = display_interface_menu()

        if interface_choice == 'cli':
            return run_cli_mode()
        elif interface_choice == 'gui':
            return run_gui_mode()

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        print(f"\n\n{_('startup.interrupted')}")
        return True
    except (ImportError, OSError, RuntimeError) as e:
        log_error(e, {"function": "main", "location": "main_application_loop"}, __file__, "main")
        logger.error(f"Application Main Loop Error: {e}")
        print(f"  {_('errors.main_error', error=str(e))}")
        return False
    except Exception as e:
        log_error(e, {"function": "main", "location": "main_application_loop"}, __file__, "main")
        logger.error(f"Application Main Loop Error: {e}", exc_info=True)
        print(f"  {_('errors.main_error', error=str(e))}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except (SystemError, MemoryError, KeyboardInterrupt) as e:
        log_critical_error(e, {"location": "main_entry_point", "critical": True})
        logger.critical(f"Critical System Error: {e}", exc_info=True)
        print(f"  {_('errors.critical_error', error=str(e))}")
        sys.exit(1)
    except Exception as e:
        log_critical_error(e, {"location": "main_entry_point", "critical": True})
        logger.critical(f"Unexpected Critical Error: {e}", exc_info=True)
        print(f"  {_('errors.unexpected_error', error=str(e))}")
        sys.exit(1)
