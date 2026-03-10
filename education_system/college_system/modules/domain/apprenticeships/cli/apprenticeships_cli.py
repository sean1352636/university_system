"""Apprenticeships CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.apprenticeships.services.apprenticeships_service import ApprenticeshipService
from education_system.college_system.infrastructure.auth.core import UserAuth


def apprenticeship_menu(auth: UserAuth):
    """Apprenticeships management menu."""
    svc = ApprenticeshipService(auth._db_path)

    while True:
        print_header("Apprenticeships")
        options = [
            ("1", "List Standards"),
            ("2", "Create Standard"),
            ("3", "Enroll Apprentice"),
            ("4", "List Enrollments"),
            ("5", "Log OTJ Hours"),
            ("6", "Add Progress Review"),
            ("7", "Update Enrollment"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            print("  List Standards - use GUI for full functionality")
        elif choice == "2":
            print("  Create Standard - use GUI for full functionality")
        elif choice == "3":
            print("  Enroll Apprentice - use GUI for full functionality")
        elif choice == "4":
            print("  List Enrollments - use GUI for full functionality")
        elif choice == "5":
            print("  Log OTJ Hours - use GUI for full functionality")
        elif choice == "6":
            print("  Add Progress Review - use GUI for full functionality")
        elif choice == "7":
            print("  Update Enrollment - use GUI for full functionality")
        else:
            print("\n  Invalid option.")
