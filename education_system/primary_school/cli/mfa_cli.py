"""MFA settings CLI module for the Primary School system."""

from education_system.primary_school.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.primary_school.infrastructure.auth.mfa_service import MFAService
from education_system.primary_school.infrastructure.auth.core import UserAuth


def mfa_settings_menu(auth: UserAuth):
    """MFA settings menu."""
    svc = MFAService(auth._db_path)
    user_id = auth.current_user["user_id"]
    username = auth.current_user["username"]

    while True:
        enabled = svc.is_mfa_enabled(user_id)
        status = "Enabled" if enabled else "Disabled"
        print_header(f"MFA Settings (Status: {status})")
        options = [
            ("1", "Setup MFA"),
            ("2", "Disable MFA"),
            ("3", "View Recovery Code Count"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _setup_mfa(svc, user_id, username)
        elif choice == "2":
            _disable_mfa(svc, user_id)
        elif choice == "3":
            _view_recovery_count(svc, user_id)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _setup_mfa(svc: MFAService, user_id: int, username: str):
    print_header("Setup MFA")
    try:
        result = svc.setup_totp(user_id, username)
        print(f"\n  TOTP Secret: {result['secret']}")
        print(f"  Provisioning URI: {result['provisioning_uri']}")
        print(f"\n  Recovery Codes (save these securely!):")
        for code in result["recovery_codes"]:
            print(f"    {code}")
        print(f"\n  MFA has been enabled for your account.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _disable_mfa(svc: MFAService, user_id: int):
    print_header("Disable MFA")
    try:
        confirm = input("Are you sure you want to disable MFA? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.disable_mfa(user_id)
        print("\n  MFA has been disabled.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_recovery_count(svc: MFAService, user_id: int):
    try:
        count = svc.get_remaining_recovery_codes(user_id)
        print(f"\n  Remaining recovery codes: {count}")
    except Exception as e:
        print(f"\n  Error: {e}")
