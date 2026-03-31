"""CLI interactive menus for mode and system selection."""

import sys


def _flush_stdin():
    """Drain any leftover characters from stdin (e.g. after a tkinter dialog)."""
    import select
    try:
        while select.select([sys.stdin], [], [], 0.0)[0]:
            sys.stdin.readline()
    except Exception:
        pass


def cli_select_mode() -> str | None:
    """CLI menu: pick a run mode. Returns mode string or None to exit."""
    mapping = {"1": "cli", "2": "gui", "3": "api", "4": "test", "5": "test-all"}
    _flush_stdin()

    while True:
        print()
        print("=" * 54)
        print("       Education System Launcher")
        print("=" * 54)
        print()
        print("  [1] CLI    - Command-line interface")
        print("  [2] GUI    - Graphical interface")
        print("  [3] API    - REST API server (includes web dashboard)")
        print("  [4] Test   - Run test suite (single system)")
        print("  [5] Test   - Run ALL tests (all systems)")
        print("  [0] Exit")
        print()

        choice = input("  Select mode: ").strip()
        if choice == "0":
            print("\n  Goodbye!")
            return None
        if choice in mapping:
            return mapping[choice]
        print("\n  Invalid option. Please try again.")


def cli_select_system() -> str | None:
    """CLI menu: pick a system. Returns system key or None for back."""
    mapping = {"1": "university", "2": "college", "3": "school", "4": "primary"}
    _flush_stdin()

    while True:
        print()
        print("  ── Select System ──")
        print()
        print("  [1] University Management System")
        print("  [2] Sixth Form College System")
        print("  [3] Secondary School Management System")
        print("  [4] Primary School Management System")
        print("  [0] Back")
        print()

        choice = input("  Select system: ").strip()
        if choice == "0":
            return None
        if choice in mapping:
            return mapping[choice]
        print("\n  Invalid option. Please try again.")
