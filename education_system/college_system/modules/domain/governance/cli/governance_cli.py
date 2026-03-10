"""Governance & Board CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.governance.services.governance_service import GovernanceService
from education_system.college_system.infrastructure.auth.core import UserAuth


def governance_menu(auth: UserAuth):
    """Governance & Board management menu."""
    svc = GovernanceService(auth._db_path)

    while True:
        print_header("Governance & Board")
        options = [
            ("1", "List Governors"),
            ("2", "Add Governor"),
            ("3", "Schedule Meeting"),
            ("4", "List Meetings"),
            ("5", "Add Action"),
            ("6", "Open Actions"),
            ("7", "Strategic Plans"),
            ("8", "Add Strategic Plan"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            print("  List Governors - use GUI for full functionality")
        elif choice == "2":
            print("  Add Governor - use GUI for full functionality")
        elif choice == "3":
            print("  Schedule Meeting - use GUI for full functionality")
        elif choice == "4":
            print("  List Meetings - use GUI for full functionality")
        elif choice == "5":
            print("  Add Action - use GUI for full functionality")
        elif choice == "6":
            print("  Open Actions - use GUI for full functionality")
        elif choice == "7":
            print("  Strategic Plans - use GUI for full functionality")
        elif choice == "8":
            print("  Add Strategic Plan - use GUI for full functionality")
        else:
            print("\n  Invalid option.")
