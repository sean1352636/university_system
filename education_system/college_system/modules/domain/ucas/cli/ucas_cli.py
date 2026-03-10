"""UCAS Applications CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.ucas.services.ucas_service import UCASService
from education_system.college_system.infrastructure.auth.core import UserAuth


def ucas_menu(auth: UserAuth):
    """UCAS Applications management menu."""
    svc = UCASService(auth._db_path)

    while True:
        print_header("UCAS Applications")
        options = [
            ("1", "List Applications"),
            ("2", "Create Application"),
            ("3", "View Application"),
            ("4", "Add Choice"),
            ("5", "Update Offer"),
            ("6", "Set Firm/Insurance"),
            ("7", "Submit Application"),
            ("8", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            print("  List Applications - use GUI for full functionality")
        elif choice == "2":
            print("  Create Application - use GUI for full functionality")
        elif choice == "3":
            print("  View Application - use GUI for full functionality")
        elif choice == "4":
            print("  Add Choice - use GUI for full functionality")
        elif choice == "5":
            print("  Update Offer - use GUI for full functionality")
        elif choice == "6":
            print("  Set Firm/Insurance - use GUI for full functionality")
        elif choice == "7":
            print("  Submit Application - use GUI for full functionality")
        elif choice == "8":
            print("  Statistics - use GUI for full functionality")
        else:
            print("\n  Invalid option.")
