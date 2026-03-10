"""Individual Learning Plans CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.ilp.services.ilp_service import ILPService
from education_system.college_system.infrastructure.auth.core import UserAuth


def ilp_menu(auth: UserAuth):
    """Individual Learning Plans management menu."""
    svc = ILPService(auth._db_path)

    while True:
        print_header("Individual Learning Plans")
        options = [
            ("1", "List Plans"),
            ("2", "Create Plan"),
            ("3", "View Plan"),
            ("4", "Add Target"),
            ("5", "Add Review"),
            ("6", "Due Reviews"),
            ("7", "Update Plan"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            print("  List Plans - use GUI for full functionality")
        elif choice == "2":
            print("  Create Plan - use GUI for full functionality")
        elif choice == "3":
            print("  View Plan - use GUI for full functionality")
        elif choice == "4":
            print("  Add Target - use GUI for full functionality")
        elif choice == "5":
            print("  Add Review - use GUI for full functionality")
        elif choice == "6":
            print("  Due Reviews - use GUI for full functionality")
        elif choice == "7":
            print("  Update Plan - use GUI for full functionality")
        else:
            print("\n  Invalid option.")
