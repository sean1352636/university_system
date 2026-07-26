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
from ._shared import is_chatbot_available

logger = logging.getLogger("education_system.systems.university.interfaces.cli.shell.auth.cli_menus")

from .user_management import display_user_management_menu
from .role_management import display_role_management_menu
from .my_account import display_my_account_menu
from .chatbot import display_chatbot_integration_menu
from .remember_me import (
    _save_cli_remember_token, _clear_cli_remember_token,
    _check_cli_remember_me_token,
)

def display_auth_menu(existing_auth=None):
    """Enhanced authentication menu with chatbot integration and remember me support.

    If *existing_auth* is provided (already logged-in), that session is reused
    instead of creating a fresh UserAuth and showing the login screen.
    """
    from education_system.systems.university.infrastructure.auth import UserAuth

    if existing_auth is not None and getattr(existing_auth, 'current_user', None):
        auth = existing_auth
        auto_login = False
    else:
        auth = UserAuth()
        # Check for remember me token first
        auth, auto_login = _check_cli_remember_me_token(auth)

    # Initialize chatbot integration
    if is_chatbot_available():
        try:
            from education_system.systems.university.infrastructure.auth.integrations.chatbot_integration import (
                initialize_chatbot_integration as _init_chatbot,
                setup_chatbot_permissions as _setup_chatbot_perms,
            )
            _init_chatbot(auth)
            _setup_chatbot_perms(auth)
        except Exception:
            pass

    while True:
        print("\nEnhanced University System:")
        print("==========================")

        if auth.current_user:
            # User is logged in
            user = auth.current_user
            print(f"Logged in as: {user['username']} (Role: {user['role']})")

            if user.get('password_reset_required'):
                # Handle password reset (existing code)
                print("\nYou must change your password before continuing.")
                current_password = input("Enter current password: ")

                while True:
                    new_password = input("Enter new password (min 8 chars, mix of letters & numbers): ")
                    confirm_password = input("Confirm new password: ")

                    if new_password != confirm_password:
                        print("Passwords don't match. Try again.")
                        continue

                    if auth.change_password(user['username'], current_password, new_password):
                        break
                    else:
                        retry = input("Do you want to try again? (y/n): ").lower()
                        if retry != 'y':
                            auth.logout()
                            break

                continue

            print("\n1. User Management")
            print("2. Role Management")
            print("3. My Account")
            user_perms = user.get('permissions', [])
            if 'access_chatbot' in user_perms:
                print("4. University Chatbot")
            print("5. Logout")
            print("6. Return to Main Menu")

            max_choice = 6
            choice = input(f"\nEnter your choice (1-{max_choice}): ")

            if choice == '1':
                if 'manage_users' in user_perms:
                    display_user_management_menu(auth)
                else:
                    print("You don't have permission to access User Management.")
            elif choice == '2':
                if 'manage_roles' in user_perms:
                    display_role_management_menu(auth)
                else:
                    print("You don't have permission to access Role Management.")
            elif choice == '3':
                display_my_account_menu(auth)
            elif choice == '4' and 'access_chatbot' in user_perms:
                display_chatbot_integration_menu(auth)
            elif choice == '5':
                # Logout and clear remember me token
                _clear_cli_remember_token()

                # Revoke all sessions if using EnhancedAuth
                try:
                    from education_system.systems.university.infrastructure.auth.enhanced_auth import EnhancedAuth
                    if isinstance(auth, EnhancedAuth):
                        user_id = user.get('id')
                        if user_id:
                            auth.logout_and_revoke_remember_me(user_id)
                except Exception as e:
                    logging.debug(f"Could not revoke remember me tokens: {e}")

                auth.logout()
            elif choice == '6':
                return auth
            else:
                print("Invalid choice. Please try again.")

        else:
            # User is not logged in (existing login code)
            print("Not logged in.")
            print("\n1. Login")
            print("2. Shut down")

            choice = input("\nEnter your choice (1-2): ")

            if choice == '1':
                # Login process with remember me support
                username = input("Username: ")
                password = input("Password: ")

                # Ask for remember me
                remember_choice = input("Remember me? (y/n, default: n): ").lower().strip()
                remember_me = remember_choice == 'y'

                try:
                    # Try to use EnhancedAuth with remember me if enabled
                    if remember_me:
                        try:
                            from education_system.systems.university.infrastructure.auth.enhanced_auth import EnhancedAuth, create_enhanced_auth
                            import socket
                            import hashlib

                            # Generate device fingerprint
                            machine_id = f"{socket.gethostname()}_{username}"
                            device_fingerprint = hashlib.sha256(machine_id.encode()).hexdigest()[:32]

                            # Create EnhancedAuth if not already
                            if not isinstance(auth, EnhancedAuth):
                                auth = create_enhanced_auth()

                            # Login with remember me
                            result = auth.login_with_remember_me(
                                username=username,
                                password=password,
                                remember_me=True,
                                device_fingerprint=device_fingerprint,
                                ip_address="127.0.0.1",
                                user_agent="CLI Terminal"
                            )

                            # Save remember me token if provided
                            if result.get('success') and result.get('remember_token'):
                                _save_cli_remember_token(username, result['remember_token'], device_fingerprint)
                                result = True  # Convert to standard boolean
                        except ImportError:
                            # EnhancedAuth not available, use standard login
                            result = auth.login(username, password)
                    else:
                        # Standard login
                        result = auth.login(username, password)
                except InvalidCredentialsError as e:
                    # Check if this is a lockout error
                    if hasattr(e, 'details') and e.details and e.details.get('wait_minutes'):
                        wait_time = e.details.get('wait_minutes')
                        print("\n⚠️  Account locked due to too many failed attempts.")
                        print(f"   Please try again in {wait_time} minutes.")
                        print("   Or enter emergency unlock password to unlock now.")

                        unlock_choice = input("\nUse emergency unlock? (y/n): ").lower().strip()
                        if unlock_choice == 'y':
                            emergency_pwd = input("Enter emergency unlock password: ")
                            result = auth.emergency_unlock(username, emergency_pwd)
                            if result['success']:
                                print(f"\n✅ {result['message']}")
                                print("You may now try logging in again.")
                            else:
                                print(f"\n❌ {result['message']}")
                    else:
                        # Show remaining attempts if available
                        remaining = auth.get_remaining_login_attempts(username)
                        print(f"\n❌ {e.message}")
                        if remaining > 0:
                            print(f"   {remaining} attempt(s) remaining before lockout.")
                        elif remaining == 0:
                            print("   Account will be locked on next failed attempt.")
                    continue
                except (AuthenticationError, DatabaseError) as e:
                    print(f"\n❌ Login failed: {e.message}")
                    continue

                if result is True:
                    # Successful password login - check MFA
                    try:
                        from education_system.systems.university.infrastructure.auth.mfa_service import MFAService
                        mfa_service = MFAService()

                        user_id = auth.current_user.get('id') if auth.current_user else None

                        if user_id:
                            # Check if verification is disabled (password-only login)
                            if mfa_service.is_verification_disabled(user_id):
                                print(f"\n✅ Login successful! Welcome, {username}!")
                                continue

                            # Check for configured email MFA
                            methods_result = mfa_service.get_user_mfa_methods(user_id)
                            email_configured = None

                            if methods_result and methods_result.get('success'):
                                for method in methods_result.get('methods', []):
                                    if method and method.get('type') == 'email' and method.get('identifier'):
                                        email_configured = method.get('identifier')
                                        break

                            if email_configured:
                                # Send OTP to email
                                otp_result = mfa_service.generate_email_otp(user_id, email_configured)

                                if otp_result.get('success'):
                                    # Mask email for display
                                    email_parts = email_configured.split('@')
                                    masked_email = email_parts[0][:2] + '***@' + email_parts[1] if len(email_parts) == 2 else email_configured

                                    if otp_result.get('email_failed'):
                                        # Email failed - show code on screen
                                        fallback_code = otp_result.get('code', '')
                                        print(f"\n⚠️  Could not send email to {masked_email}")
                                        print(f"   Your verification code is: {fallback_code}")
                                    else:
                                        print(f"\n📧 Verification code sent to: {masked_email}")
                                        print("   Please check your email.")

                                    # Verify OTP
                                    max_attempts = 3
                                    attempts = 0
                                    verified = False

                                    while attempts < max_attempts:
                                        code = input("\nEnter 6-digit verification code: ").strip()

                                        verify_result = mfa_service.verify_email_otp(user_id, code)
                                        if verify_result.get('success'):
                                            print(f"\n✅ Login successful! Welcome, {username}!")
                                            verified = True
                                            break
                                        else:
                                            attempts += 1
                                            remaining = max_attempts - attempts
                                            if remaining > 0:
                                                print(f"❌ Invalid code. {remaining} attempt(s) remaining.")
                                            else:
                                                print("❌ Too many failed attempts. Please try logging in again.")
                                                auth.logout()
                                                break

                                    if not verified:
                                        continue
                                else:
                                    # OTP generation failed - proceed without MFA
                                    print(f"\n✅ Login successful! Welcome, {username}!")
                            else:
                                # No MFA configured - simple login
                                print(f"\n✅ Login successful! Welcome, {username}!")
                        else:
                            print(f"\n✅ Login successful! Welcome, {username}!")

                    except Exception as mfa_error:
                        logging.warning(f"CLI MFA check error: {mfa_error}")
                        print(f"\n✅ Login successful! Welcome, {username}!")

                elif isinstance(result, dict) and result.get('requires_2fa'):
                    # Legacy 2FA handling
                    print("\n2-Factor Authentication required.")
                    print("Enter your 6-digit verification code from your authenticator app,")
                    print("or use a recovery code.")

                    max_attempts = 3
                    attempts = 0

                    while attempts < max_attempts:
                        code = input("\nEnter verification code: ")
                        code = code.replace('-', '')

                        if auth.complete_two_fa_login(result['user_id'], result['username'], code):
                            break
                        else:
                            attempts += 1
                            remaining = max_attempts - attempts
                            if remaining > 0:
                                print(f"Invalid code. {remaining} attempts remaining.")
                            else:
                                print("Too many failed attempts. Please try logging in again.")
                                break

                elif result == 'password_reset_required':
                    continue
                elif not result:
                    retry = input("Do you want to try again? (y/n): ").lower()
                    if retry != 'y':
                        break
            elif choice == '2':
                print("Shutting down...")
                sys.exit(0)
            else:
                print("Invalid choice. Please try again.")

    return auth

# ============================================================================
# Force Password Reset Toggle (CLI)
# ============================================================================

