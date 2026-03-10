"""Value-Added Analysis CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.value_added.services.value_added_service import ValueAddedService
from education_system.college_system.infrastructure.auth.core import UserAuth


def value_added_menu(auth: UserAuth):
    """Value-Added Analysis management menu."""
    svc = ValueAddedService(auth._db_path)

    while True:
        print_header("Value-Added Analysis")
        options = [
            ("1", "Set Baseline"),
            ("2", "Set Prediction"),
            ("3", "Update Actual Grade"),
            ("4", "List Predictions"),
            ("5", "Subject VA"),
            ("6", "College VA"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            print("  Set Baseline - use GUI for full functionality")
        elif choice == "2":
            print("  Set Prediction - use GUI for full functionality")
        elif choice == "3":
            print("  Update Actual Grade - use GUI for full functionality")
        elif choice == "4":
            print("  List Predictions - use GUI for full functionality")
        elif choice == "5":
            print("  Subject VA - use GUI for full functionality")
        elif choice == "6":
            print("  College VA - use GUI for full functionality")
        else:
            print("\n  Invalid option.")
