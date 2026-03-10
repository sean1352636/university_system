"""T-Level Pathways CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.tlevel.services.tlevel_service import TLevelService
from education_system.college_system.infrastructure.auth.core import UserAuth


def tlevel_menu(auth: UserAuth):
    """T-Level Pathways management menu."""
    svc = TLevelService(auth._db_path)

    while True:
        print_header("T-Level Pathways")
        options = [
            ("1", "List Routes"),
            ("2", "Create Route"),
            ("3", "Enroll Student"),
            ("4", "List Enrollments"),
            ("5", "Log Placement Hours"),
            ("6", "View Placement Logs"),
            ("7", "Update Enrollment"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            print("  List Routes - use GUI for full functionality")
        elif choice == "2":
            print("  Create Route - use GUI for full functionality")
        elif choice == "3":
            print("  Enroll Student - use GUI for full functionality")
        elif choice == "4":
            print("  List Enrollments - use GUI for full functionality")
        elif choice == "5":
            print("  Log Placement Hours - use GUI for full functionality")
        elif choice == "6":
            print("  View Placement Logs - use GUI for full functionality")
        elif choice == "7":
            print("  Update Enrollment - use GUI for full functionality")
        else:
            print("\n  Invalid option.")
