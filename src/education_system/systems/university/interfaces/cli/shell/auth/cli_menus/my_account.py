"""Split from cli_menus.py — assembled in package __init__.py."""
from __future__ import annotations

import sys
import json
import logging
import random
import secrets
import string
from pathlib import Path
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    DatabaseError,
)

logger = logging.getLogger("education_system.systems.university.interfaces.cli.shell.auth.cli_menus")

from .mfa_settings import display_mfa_settings_menu
from .account_linking import _display_account_linking_menu
from .webauthn import _display_webauthn_menu
from .biometric import _display_biometric_menu
from .delegated_access import _display_delegated_access_menu

def display_my_account_menu(auth):
    """Display the my account menu"""
    while True:
        if not auth.check_session():
            return

        user = auth.current_user

        print("\nMy Account:")
        print("===========")
        print(f"Username: {user['username']}")
        print(f"Role: {user['role']}")

        print("\n1. Change Password")
        print("2. View My Permissions")
        print("3. 2-Factor Authentication Settings (TOTP)")
        print("4. MFA Settings (Email Verification)")
        print("5. Account Linking")
        print("6. Security Keys (WebAuthn)")
        print("7. Biometric Enrollment")
        if user['role'] == 'student':
            print("8. Delegated Access (Grant Access)")
        elif user['role'] == 'parent':
            print("8. Delegated Access (Act as Delegate)")
        elif user['role'] == 'admin':
            print("8. Delegated Access Management")
        else:
            print("8. Delegated Access")
        print("9. Security Questions")
        print("0. Back")

        choice = input("\nEnter your choice (1-0): ")

        if choice == '1':
            # Change password
            print("\nChange Password:")
            current_password = input("Current Password: ")
            new_password = input("New Password (min 8 chars, mix of letters & numbers): ")
            confirm_password = input("Confirm New Password: ")

            if new_password != confirm_password:
                print("Passwords don't match.")
                continue

            auth.change_password(user['username'], current_password, new_password)

        elif choice == '2':
            # View permissions
            print("\nMy Permissions:")
            print("=" * 60)

            for perm in user.get('permissions', []):
                print(f"- {perm}")

            print("=" * 60)

        elif choice == '3':
            # 2FA settings
            user_details = auth.get_user(username=user['username'])

            print("\n2-Factor Authentication Settings:")
            print("=================================")
            print(f"2FA Status: {'Enabled' if user_details['two_fa_enabled'] else 'Disabled'}")

            if user_details['two_fa_enabled']:
                print("\n1. Disable 2FA")
                print("2. Regenerate Recovery Codes")
                print("3. Back")

                twofa_choice = input("\nEnter your choice (1-3): ")

                if twofa_choice == '1':
                    # Disable 2FA
                    confirm = input("Are you sure you want to disable 2FA? (y/n): ").lower()
                    if confirm == 'y':
                        result = auth.disable_two_fa(user['id'])
                        if result['success']:
                            print(result['message'])
                        else:
                            print(f"Error: {result['message']}")

                elif twofa_choice == '2':
                    # Regenerate recovery codes
                    confirm = input("Are you sure you want to regenerate recovery codes? Old codes will become invalid. (y/n): ").lower()
                    if confirm == 'y':
                        result = auth.regenerate_recovery_codes(user['id'])
                        if result['success']:
                            print(result['message'])
                            print("\n" + "=" * 50)
                            print("📱 NEW RECOVERY CODES")
                            print("=" * 50)
                            print("SAVE THESE IN A SECURE PLACE!")
                            print("-" * 50)
                            for code in result['recovery_codes']:
                                print(f"    {code}")
                            print("-" * 50)
                            input("\nPress Enter after you've saved your codes...")
                        else:
                            print(f"Error: {result['message']}")

                elif twofa_choice == '3':
                    continue
                else:
                    print("Invalid choice.")
            else:
                print("\n1. Enable 2FA")
                print("2. Back")

                twofa_choice = input("\nEnter your choice (1-2): ")

                if twofa_choice == '1':
                    # Enable 2FA
                    result = auth.enable_two_fa(user['id'])
                    if result['success']:
                        print(result['message'])

                        # Display the setup code prominently for CLI users
                        print("\n" + "=" * 60)
                        print("🔐 YOUR MFA SETUP CODE")
                        print("=" * 60)
                        print(f"\n    {result['secret']}")
                        print("\n" + "=" * 60)
                        print("\nEnter this code in your authenticator app")
                        print("(Google Authenticator, Authy, Microsoft Authenticator, etc.)")
                        print("=" * 60)

                        print("\n📱 Recovery Codes (SAVE THESE IN A SECURE PLACE):")
                        print("-" * 40)
                        for code in result['recovery_codes']:
                            print(f"    {code}")
                        print("-" * 40)

                        input("\nPress Enter after you've saved your codes...")
                    else:
                        print(f"Error: {result['message']}")

                elif twofa_choice == '2':
                    continue
                else:
                    print("Invalid choice.")

        elif choice == '4':
            # MFA Settings (Email Verification) - syncs with GUI
            display_mfa_settings_menu(auth, user)

        elif choice == '5':
            # Account Linking
            _display_account_linking_menu(auth)

        elif choice == '6':
            # Security Keys (WebAuthn)
            _display_webauthn_menu(auth)

        elif choice == '7':
            # Biometric Enrollment
            _display_biometric_menu(auth)

        elif choice == '8':
            # Delegated Access
            _display_delegated_access_menu(auth)

        elif choice == '9':
            # Security Questions
            from education_system.platform.delivery.cli.security_questions_cli import security_questions_menu
            security_questions_menu(auth)

        elif choice == '0':
            return
        else:
            print("Invalid choice. Please try again.")

# ============================================================================
# MFA Settings Menu (Email Verification)
# ============================================================================

