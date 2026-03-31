#!/usr/bin/env python3
"""
Education System - Unified Launcher

Thin entry point that delegates to education_system.launcher modules:
  - auth:     shared auth init & MFA sync
  - systems:  per-system bootstrap, launchers, dispatch table
  - menus:    CLI interactive mode/system selection
  - roles:    superadmin role-picker dialogs
  - dispatch: GUI/CLI dispatch loops with system-switch handling
"""

import sys
import os
import argparse
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ── Backward-compatible functions expected by tests ──────────────────────────

def log_error(message, error=None):
    """Log an error message. Used by tests; delegates to the module logger."""
    if error:
        logger.error("%s: %s", message, error, exc_info=True)
    else:
        logger.error(message)


def display_interface_menu():
    """Interactive menu that returns 'cli' or 'gui', or exits."""
    while True:
        print()
        print("=" * 54)
        print("       UNIVERSITY MANAGEMENT SYSTEM")
        print("=" * 54)
        print()
        print("  [1] Command Line Interface (CLI)")
        print("  [2] Graphical User Interface (GUI)")
        print("  [3] Run Tests")
        print("  [4] Exit")
        print()
        try:
            choice = input("  Select option: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Exiting...")
            sys.exit(0)

        if choice == "1":
            return "cli"
        elif choice == "2":
            return "gui"
        elif choice == "3":
            try:
                from education_system.university_system.tests.run_all_tests import main as run_tests_main
                run_tests_main()
            except Exception:
                pass
            sys.exit(0)
        elif choice == "4":
            print("  Goodbye!")
            sys.exit(0)
        else:
            print("  Invalid choice. Please try again.")


def run_cli_mode():
    """Launch CLI mode with error handling. Returns True on success, False on failure."""
    print("  Starting Command Line Interface...")
    try:
        from education_system.university_system.modules.shared.cli.cli_main import main as cli_main
        cli_main()
        return True
    except ImportError as e:
        print(f"  CLI Import Error: {e}")
        log_error("CLI import error", e)
        return False
    except OSError as e:
        print(f"  CLI Application Error: {e}")
        log_error("CLI OS error", e)
        return False
    except Exception as e:
        print(f"  Unexpected error: {e}")
        log_error("CLI unexpected error", e)
        return False


def run_gui_mode():
    """Launch GUI mode with error handling and CLI fallback. Returns True on success."""
    print("  Starting Graphical User Interface...")
    try:
        from education_system.university_system.modules.shared.gui.main_gui import run_gui_interface
        run_gui_interface()
        return True
    except ImportError as e:
        print(f"  GUI Import Error: {e}")
        print("  Falling back to CLI mode...")
        log_error("GUI import error", e)
        return run_cli_mode()
    except OSError as e:
        print(f"  GUI Application Error: {e}")
        print("  Falling back to CLI mode...")
        log_error("GUI OS error", e)
        return run_cli_mode()
    except Exception as e:
        print(f"  Unexpected error: {e}")
        print("  Falling back to CLI mode...")
        log_error("GUI unexpected error", e)
        return run_cli_mode()


# ── Main entry ────────────────────────────────────────────────────────────────

def main():
    from education_system.launcher.auth import gui_universal_login, cli_universal_login
    from education_system.launcher.systems import (
        LAUNCHERS, AUTH_GUI_SYSTEMS, AUTH_CLI_SYSTEMS,
        run_unified_api, run_all_system_tests, run_seed,
    )
    from education_system.launcher.menus import cli_select_mode, cli_select_system
    from education_system.launcher.dispatch import dispatch_gui, dispatch_cli

    parser = argparse.ArgumentParser(
        description="Education System Launcher",
        epilog="If no flags are given an interactive menu is shown.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--cli", action="store_true", help="Command-line interface")
    mode_group.add_argument("--gui", action="store_true", help="Graphical interface")
    mode_group.add_argument("--api", action="store_true", help="REST API server")
    mode_group.add_argument("--test", action="store_true", help="Run test suite")
    mode_group.add_argument("--test-all", action="store_true", help="Run tests for all systems")

    parser.add_argument("--seed", type=int, metavar="N", help="Seed database with N demo students")

    sys_group = parser.add_mutually_exclusive_group()
    sys_group.add_argument("--university", action="store_true", help="University system")
    sys_group.add_argument("--college", action="store_true", help="College system")
    sys_group.add_argument("--school", action="store_true", help="Secondary school system")
    sys_group.add_argument("--primary", action="store_true", help="Primary school system")

    args = parser.parse_args()

    # Resolve mode from flags
    mode = None
    if args.cli:
        mode = "cli"
    elif args.gui:
        mode = "gui"
    elif args.api:
        mode = "api"
    elif args.test:
        mode = "test"
    elif args.test_all:
        mode = "test-all"

    # Resolve system from flags
    system = None
    if args.university:
        system = "university"
    elif args.college:
        system = "college"
    elif args.school:
        system = "school"
    elif args.primary:
        system = "primary"

    # ── Seed mode ──────────────────────────────────────────────────────
    if args.seed:
        if system is None:
            system = cli_select_system()
            if system is None:
                return
        run_seed(system, args.seed)
        return

    # ── Test-all mode ──────────────────────────────────────────────────
    if mode == "test-all":
        success = run_all_system_tests()
        sys.exit(0 if success else 1)

    # ── Unified i18n setup ─────────────────────────────────────────────
    try:
        from education_system.shared.i18n import init_i18n

        if mode == "gui" or mode is None:
            from education_system.shared.i18n.selector_gui import show_language_selector
            chosen = show_language_selector()
            init_i18n(chosen)
        elif mode == "cli":
            from education_system.shared.i18n.selector_cli import show_language_selector_cli
            chosen = show_language_selector_cli()
            init_i18n(chosen)
        else:
            init_i18n()
    except Exception as exc:
        logger.debug("i18n init skipped: %s", exc)

    # Interactive fallbacks
    if mode is None:
        mode = cli_select_mode()
        if mode is None:
            return

    if mode == "test-all":
        success = run_all_system_tests()
        sys.exit(0 if success else 1)

    # ── GUI with universal login ───────────────────────────────────────
    if mode == "gui" and system is None:
        result = gui_universal_login()
        if result is None:
            return
        user_info, system, role, shared_auth = result
        dispatch_gui(user_info, system, role, shared_auth)
        return

    # ── CLI with universal login ───────────────────────────────────────
    if mode == "cli" and system is None:
        result = cli_universal_login()
        if result is None:
            return
        user_info, system, role, shared_auth = result
        dispatch_cli(user_info, system, role, shared_auth)
        return

    # ── API mode ───────────────────────────────────────────────────────
    if mode == "api":
        run_unified_api()
        return

    # ── Direct system launch (system already specified) ────────────────
    while system is None:
        system = cli_select_system()
        if system is None:
            mode = cli_select_mode()
            if mode is None:
                return
            if mode == "test-all":
                success = run_all_system_tests()
                sys.exit(0 if success else 1)
            continue

    while True:
        launcher = LAUNCHERS.get((system, mode))
        if launcher is None:
            print(f"  Unknown combination: {system} + {mode}")
            sys.exit(1)

        try:
            launcher()
        except KeyboardInterrupt:
            print("\n\n  Interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error("Error: %s", e, exc_info=True)
            print(f"\n  Error: {e}")
            sys.exit(1)

        from education_system.switch import consume
        switch_request = consume()
        if switch_request is None:
            break
        system, mode = switch_request
        print(f"\n  Switching to {system} ({mode})...\n")


if __name__ == "__main__":
    main()
