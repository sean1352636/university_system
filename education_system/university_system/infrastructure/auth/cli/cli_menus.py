"""
CLI Menu Functions for Authentication System

This module contains all CLI menu functions extracted from user_authentication.py
to improve code organization and maintainability.

Functions:
    - display_auth_menu(): Main authentication menu with login/logout
    - display_user_management_menu(): User CRUD operations
    - display_role_management_menu(): Role and permission management
    - display_my_account_menu(): Account settings and password management
    - display_mfa_settings_menu(): MFA configuration (Email Verification)
    - display_chatbot_integration_menu(): Chatbot interface menu
    - Remember-me token functions for CLI

Author: University System Team
Date: 2025
"""

import sys
import json
import logging
import random
import secrets
import string
from education_system.university_system.infrastructure.database.db import sqlite3
from pathlib import Path
from datetime import datetime

# Import custom exceptions
from education_system.university_system.infrastructure.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    DatabaseError,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Chatbot availability is probed lazily — the probe imports the entire chatbot
# module tree (~1.8s). Deferring via PEP 562 module __getattr__ keeps CLI menu
# import cheap for callers that never invoke the chatbot.
try:
    from education_system.university_system.infrastructure.auth.optional_dependencies import (
        is_chatbot_available,
    )
except ImportError:
    def is_chatbot_available():  # type: ignore[misc]
        return False


def __getattr__(name):  # noqa: N807 — PEP 562 module-level hook
    if name == 'CHATBOT_AVAILABLE':
        try:
            return is_chatbot_available()
        except Exception:
            return False
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Default roles constant (used for role protection)
ROLES = {
    'admin': 'Administrator with full system access',
    'staff': 'Staff with access to student records and reports',
    'student': 'Student with access to own records only',
    'instructor': 'Instructor with access to assigned modules and student grades',
    'parent': 'Parent with access to their children\'s records'
}

# Export all menu functions
__all__ = [
    'display_auth_menu',
    'display_user_management_menu',
    'display_role_management_menu',
    'display_my_account_menu',
    'display_mfa_settings_menu',
    'display_chatbot_integration_menu',
]

# ============================================================================
# Remember-Me Token Functions (CLI)
# ============================================================================

def _save_cli_remember_token(username, token, device_fingerprint):
    """Save remember me token to file for CLI"""
    try:
        token_file = Path.home() / '.university_system' / 'cli_remember_me.json'
        token_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'username': username,
            'token': token,
            'device_fingerprint': device_fingerprint
        }

        with open(token_file, 'w') as f:
            json.dump(data, f)

        print(f"✅ Remember me token saved. You'll be automatically logged in next time.")

    except Exception as e:
        logging.warning(f"Failed to save remember me token: {e}")

def _load_cli_remember_token():
    """Load remember me token from file for CLI"""
    try:
        token_file = Path.home() / '.university_system' / 'cli_remember_me.json'

        if not token_file.exists():
            return None

        with open(token_file, 'r') as f:
            data = json.load(f)

        return data

    except Exception as e:
        logging.warning(f"Failed to load remember me token: {e}")
        return None

def _clear_cli_remember_token():
    """Clear remember me token from file for CLI"""
    try:
        token_file = Path.home() / '.university_system' / 'cli_remember_me.json'

        if token_file.exists():
            token_file.unlink()
            print("Remember me token cleared.")

    except Exception as e:
        logging.warning(f"Failed to clear remember me token: {e}")

def _check_cli_remember_me_token(auth):
    """Check for remember me token and auto-login if valid"""
    try:
        from education_system.university_system.infrastructure.auth.enhanced_auth import EnhancedAuth, create_enhanced_auth

        # Load saved token
        token_data = _load_cli_remember_token()
        if not token_data:
            return auth, False

        username = token_data.get('username')
        token = token_data.get('token')
        device_fingerprint = token_data.get('device_fingerprint')

        if not all([username, token, device_fingerprint]):
            return auth, False

        # Create/use EnhancedAuth
        if not isinstance(auth, EnhancedAuth):
            auth = create_enhanced_auth()

        # Verify token
        result = auth.verify_remember_me_token(
            token=token,
            device_fingerprint=device_fingerprint,
            ip_address="127.0.0.1"
        )

        if result.get('success'):
            # Update saved token if rotated
            if result.get('new_token'):
                _save_cli_remember_token(username, result['new_token'], device_fingerprint)

            print(f"\n🔓 Auto-login successful! Welcome back, {username}!")
            return auth, True
        else:
            # Token invalid or expired - clear it
            _clear_cli_remember_token()
            return auth, False

    except Exception as e:
        logging.warning(f"Remember me auto-login failed: {e}")
        return auth, False

# ============================================================================
# Main Authentication Menu
# ============================================================================

def display_auth_menu(existing_auth=None):
    """Enhanced authentication menu with chatbot integration and remember me support.

    If *existing_auth* is provided (already logged-in), that session is reused
    instead of creating a fresh UserAuth and showing the login screen.
    """
    from education_system.university_system.infrastructure.auth import UserAuth

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
            from education_system.university_system.infrastructure.auth.integrations.chatbot_integration import (
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
                    from education_system.university_system.infrastructure.auth.enhanced_auth import EnhancedAuth
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
                            from education_system.university_system.infrastructure.auth.enhanced_auth import EnhancedAuth, create_enhanced_auth
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
                        print(f"\n⚠️  Account locked due to too many failed attempts.")
                        print(f"   Please try again in {wait_time} minutes.")
                        print(f"   Or enter emergency unlock password to unlock now.")

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
                            print(f"   Account will be locked on next failed attempt.")
                    continue
                except (AuthenticationError, DatabaseError) as e:
                    print(f"\n❌ Login failed: {e.message}")
                    continue

                if result is True:
                    # Successful password login - check MFA
                    try:
                        from education_system.university_system.infrastructure.auth.mfa_service import MFAService
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

def _toggle_force_password_reset_cli():
    """Toggle the forced password reset setting from the CLI."""
    try:
        from education_system.shared.auth.core import UserAuth as _SharedAuth
        shared_auth = _SharedAuth()
        current = shared_auth.get_setting("force_password_reset", True)

        status = "ON" if current else "OFF"
        print(f"\nForced Password Reset is currently: {status}")
        print("When ON, users with expired or unset passwords must reset on login.")
        print("When OFF, password expiry checks are skipped.\n")

        toggle = input(f"Turn it {'OFF' if current else 'ON'}? (y/n): ").strip().lower()
        if toggle == 'y':
            new_val = not current
            shared_auth.set_setting("force_password_reset", new_val)
            new_status = "ON" if new_val else "OFF"
            print(f"\nForced password reset is now {new_status}.")
        else:
            print("No changes made.")
    except Exception as e:
        print(f"Error toggling setting: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# User Management Menu
# ============================================================================

def display_user_management_menu(auth):
    """Display the user management menu with enhanced debugging"""
    while True:
        if not auth.check_session() or not auth.check_permission('manage_users'):
            print("You don't have permission to access User Management.")
            return

        print("\nUser Management:")
        print("================")
        print("1. List All Users")
        print("2. Create New User")
        print("3. View User Details")
        print("4. Edit User")
        print("5. Reset User Password")
        print("6. Deactivate/Activate User")
        print("7. Delete User")
        print("8. Manage User Permissions")
        print("9. Fix Database Consistency Issues")  # New option
        print("10. Debug User Database")  # New option
        print("11. Toggle Forced Password Reset")
        print("12. Back")

        choice = input("\nEnter your choice (1-12): ")

        if choice == '1':
            # List all users with enhanced information
            users = auth.list_users()

            if users:
                print("\nAll Users:")
                print("=" * 100)
                print(f"{'ID':<5} {'Username':<15} {'Name':<25} {'Role':<10} {'Status':<10} {'2FA':<5} {'Last Login':<20}")
                print("-" * 100)

                for user in users:
                    full_name = f"{user['first_name']} {user['last_name']}"
                    status = "Active" if user['is_active'] else "Inactive"
                    two_fa = "Yes" if user['two_fa_enabled'] else "No"
                    last_login = user['last_login'] if user['last_login'] else "Never"

                    print(f"{user['id']:<5} {user['username']:<15} {full_name:<25} {user['role']:<10} {status:<10} {two_fa:<5} {last_login:<20}")

                print("=" * 100)

        elif choice == '2':
            # Create new user
            print("\nCreate New User:")
            username = input("Username: ")

            # Check if username is valid
            if not auth._validate_username(username):
                print("Invalid username format. Username must be 3-20 characters and contain only letters, numbers, underscores, or hyphens.")
                continue

            # Check if user exists
            conn = auth._create_configured_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM user_accounts WHERE username = ?', (username,))
            if cursor.fetchone():
                print("Username already exists.")
                conn.close()
                continue
            conn.close()

            email = input("Email: ")
            first_name = input("First Name: ")
            last_name = input("Last Name: ")

            # Get available roles
            conn = auth._create_configured_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT role_name FROM roles')
            available_roles = [row[0] for row in cursor.fetchall()]
            conn.close()

            print("\nAvailable Roles:")
            for i, role in enumerate(available_roles, 1):
                print(f"{i}. {role}")

            while True:
                role_choice = input("Select role (enter number): ")
                try:
                    role_index = int(role_choice) - 1
                    if 0 <= role_index < len(available_roles):
                        role = available_roles[role_index]
                        break
                    else:
                        print("Invalid choice.")
                except ValueError:
                    print("Please enter a number.")

            # If role is student, ask for student_id
            student_id = None
            if role == 'student':
                student_id = input("Student ID (must be an existing student ID): ")

            # Generate a random initial password
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))

            # Create the user
            if auth.create_user(username, temp_password, email, first_name, last_name, role, student_id, True):
                print(f"\nUser created successfully. Temporary password has been set - user must change on first login.")

        elif choice == '3':
            # View user details with better input handling
            user_input = input("Enter user ID or username to view: ")

            user = None

            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)

            if user:
                print("\nUser Details:")
                print("=" * 60)
                print(f"ID: {user['id']}")
                print(f"Username: {user['username']}")
                print(f"Email: {user['email']}")
                print(f"Name: {user['first_name']} {user['last_name']}")
                print(f"Role: {user['role']}")
                print(f"Active: {'Yes' if user['is_active'] else 'No'}")
                print(f"2FA Enabled: {'Yes' if user['two_fa_enabled'] else 'No'}")
                print(f"Student ID: {user['student_id'] or 'N/A'}")
                print(f"Last Login: {user['last_login'] or 'Never'}")
                print(f"Created: {user['created_at']}")
                print(f"Updated: {user['updated_at']}")

                print("\nPermissions:")
                perms = user.get('permissions') or auth.get_user_permissions(user['id'])
                if perms:
                    for perm in perms:
                        print(f"- {perm}")
                else:
                    print("- (none)")

                print("=" * 60)

        elif choice == '4':
            # Edit User
            user_input = input("Enter user ID or username to edit: ")

            user = None
            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)

            if user:
                print(f"\nEdit User: {user['username']}")
                print("=" * 40)
                print(f"Current Username: {user['username']}")
                print(f"Current Email: {user['email']}")
                print(f"Current First Name: {user['first_name']}")
                print(f"Current Last Name: {user['last_name']}")
                print(f"Current Role: {user['role']}")
                print(f"Current Student ID: {user['student_id'] or 'N/A'}")

                print("\nEnter new values (leave blank to keep current):")
                new_username = input("New Username: ")
                new_email = input("New Email: ")
                new_first_name = input("New First Name: ")
                new_last_name = input("New Last Name: ")

                # Role selection
                conn = auth._create_configured_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT role_name FROM roles')
                available_roles = [row[0] for row in cursor.fetchall()]
                conn.close()

                print(f"\nCurrent Role: {user['role']}")
                print("Available Roles:")
                for i, role in enumerate(available_roles, 1):
                    print(f"{i}. {role}")

                role_choice = input("Select new role (enter number, or leave blank to keep current): ")
                new_role = None
                if role_choice:
                    try:
                        role_index = int(role_choice) - 1
                        if 0 <= role_index < len(available_roles):
                            new_role = available_roles[role_index]
                        else:
                            print("Invalid choice, keeping current role.")
                    except ValueError:
                        print("Invalid input, keeping current role.")

                new_student_id = input("New Student ID (leave blank to keep current): ")

                # Build update dictionary
                updates = {}
                if new_username:
                    updates['username'] = new_username
                if new_email:
                    updates['email'] = new_email
                if new_first_name:
                    updates['first_name'] = new_first_name
                if new_last_name:
                    updates['last_name'] = new_last_name
                if new_role:
                    updates['role'] = new_role
                if new_student_id:
                    updates['student_id'] = new_student_id

                if updates:
                    if auth.update_user(user['id'], **updates):
                        print("User updated successfully.")
                    else:
                        print("Failed to update user.")
                else:
                    print("No changes made.")
            else:
                print("User not found.")

        elif choice == '5':
            # Reset User Password
            user_input = input("Enter username to reset password: ")

            # Verify user exists
            user = auth.get_user(username=user_input)
            if user:
                confirm = input(f"Are you sure you want to reset password for '{user_input}'? (y/n): ").lower()
                if confirm == 'y':
                    if auth.reset_password(user_input, auth.current_user.get('user_id') or auth.current_user.get('id')):
                        print("Password reset successfully. User will receive a temporary password.")
                    else:
                        print("Failed to reset password.")
            else:
                print("User not found.")

        elif choice == '6':
            # Deactivate/Activate User
            user_input = input("Enter user ID or username to activate/deactivate: ")

            user = None
            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)

            if user:
                current_status = "Active" if user['is_active'] else "Inactive"
                print(f"\nUser: {user['username']}")
                print(f"Current Status: {current_status}")

                if user['is_active']:
                    # User is active, offer to deactivate
                    confirm = input("Do you want to deactivate this user? (y/n): ").lower()
                    if confirm == 'y':
                        if auth.deactivate_user(user['id']):
                            print("User deactivated successfully.")
                        else:
                            print("Failed to deactivate user.")
                else:
                    # User is inactive, offer to activate
                    confirm = input("Do you want to activate this user? (y/n): ").lower()
                    if confirm == 'y':
                        if auth.activate_user(user['id']):
                            print("User activated successfully.")
                        else:
                            print("Failed to activate user.")
            else:
                print("User not found.")

        elif choice == '7':
            # Delete User
            user_input = input("Enter user ID or username to delete: ")

            user = None
            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)

            if user:
                print(f"\nUser to delete: {user['username']}")
                print(f"Name: {user['first_name']} {user['last_name']}")
                print(f"Role: {user['role']}")
                print(f"Email: {user['email']}")

                # Confirm deletion
                confirm1 = input("\nAre you sure you want to delete this user? This action cannot be undone. (y/n): ").lower()
                if confirm1 == 'y':
                    confirm2 = input("Type 'DELETE' to confirm: ")
                    if confirm2 == 'DELETE':
                        if auth.delete_user(user['id']):
                            print("User deleted successfully.")
                        else:
                            print("Failed to delete user.")
                    else:
                        print("Deletion cancelled.")
                else:
                    print("Deletion cancelled.")
            else:
                print("User not found.")

        elif choice == '8':
            # Manage User Permissions
            user_input = input("Enter user ID or username to manage permissions: ")

            user = None
            # Try as user ID first
            try:
                user_id = int(user_input)
                user = auth.get_user(user_id=user_id)
            except ValueError:
                # If not a number, try as username
                user = auth.get_user(username=user_input)

            if user:
                while True:
                    print(f"\nManage Permissions for: {user['username']}")
                    print("=" * 50)

                    # Get all permissions
                    conn = auth._create_configured_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT permission_name, description FROM permissions ORDER BY permission_name')
                    all_permissions = cursor.fetchall()
                    conn.close()

                    # Get user's current permissions
                    user_permissions = user.get('permissions') or auth.get_user_permissions(user['id'])

                    print(f"Role: {user['role']}")
                    print("Current Permissions:")

                    for i, (perm_name, perm_desc) in enumerate(all_permissions, 1):
                        status = "✓" if perm_name in user_permissions else " "
                        print(f"{i:2}. [{status}] {perm_name} - {perm_desc}")

                    print("\nOptions:")
                    print("1. Grant Permission")
                    print("2. Revoke Permission")
                    print("3. Remove Custom Permission (revert to role default)")
                    print("4. Back")

                    perm_choice = input("\nEnter choice (1-4): ")

                    if perm_choice == '1':
                        # Grant permission
                        perm_number = input("Enter permission number to grant: ")
                        try:
                            perm_index = int(perm_number) - 1
                            if 0 <= perm_index < len(all_permissions):
                                perm_name = all_permissions[perm_index][0]
                                if auth.set_user_permission(user['id'], perm_name, True):
                                    # Refresh user data
                                    user = auth.get_user(user_id=user['id'])
                                    print(f"Permission '{perm_name}' granted successfully.")
                                else:
                                    print("Failed to grant permission.")
                            else:
                                print("Invalid permission number.")
                        except ValueError:
                            print("Please enter a number.")

                    elif perm_choice == '2':
                        # Revoke permission
                        perm_number = input("Enter permission number to revoke: ")
                        try:
                            perm_index = int(perm_number) - 1
                            if 0 <= perm_index < len(all_permissions):
                                perm_name = all_permissions[perm_index][0]
                                if auth.set_user_permission(user['id'], perm_name, False):
                                    # Refresh user data
                                    user = auth.get_user(user_id=user['id'])
                                    print(f"Permission '{perm_name}' revoked successfully.")
                                else:
                                    print("Failed to revoke permission.")
                            else:
                                print("Invalid permission number.")
                        except ValueError:
                            print("Please enter a number.")

                    elif perm_choice == '3':
                        # Remove custom permission
                        perm_number = input("Enter permission number to reset to role default: ")
                        try:
                            perm_index = int(perm_number) - 1
                            if 0 <= perm_index < len(all_permissions):
                                perm_name = all_permissions[perm_index][0]
                                if auth.remove_user_permission(user['id'], perm_name):
                                    # Refresh user data
                                    user = auth.get_user(user_id=user['id'])
                                    print(f"Custom permission '{perm_name}' removed. User now has role default.")
                                else:
                                    print("Failed to remove custom permission.")
                            else:
                                print("Invalid permission number.")
                        except ValueError:
                            print("Please enter a number.")

                    elif perm_choice == '4':
                        break
                    else:
                        print("Invalid choice.")
            else:
                print("User not found.")

        elif choice == '9':
            # Fix database consistency issues
            print("\nFix Database Consistency Issues:")
            print("This will attempt to fix orphaned records between users and user_accounts tables.")
            confirm = input("Do you want to proceed? (y/n): ").lower()

            if confirm == 'y':
                auth.fix_database_consistency()

        elif choice == '10':
            # Debug user database
            print("\nDatabase Debug Information:")
            print("=" * 60)

            try:
                conn = auth._create_configured_connection()
                cursor = conn.cursor()

                # Count records in each table
                cursor.execute('SELECT COUNT(*) FROM users')
                user_count = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(*) FROM user_accounts')
                account_count = cursor.fetchone()[0]

                print(f"Total users in 'users' table: {user_count}")
                print(f"Total accounts in 'user_accounts' table: {account_count}")

                # Check for mismatches
                cursor.execute('''
                    SELECT COUNT(*) FROM users u
                    LEFT JOIN user_accounts ua ON u.id = ua.user_id
                    WHERE ua.user_id IS NULL
                ''')
                orphaned_users = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*) FROM user_accounts ua
                    LEFT JOIN users u ON ua.user_id = u.id
                    WHERE u.id IS NULL
                ''')
                orphaned_accounts = cursor.fetchone()[0]

                print(f"Users without accounts: {orphaned_users}")
                print(f"Accounts without users: {orphaned_accounts}")

                if orphaned_users > 0 or orphaned_accounts > 0:
                    print("\nWarning: Database inconsistencies detected!")
                    print("Use option 9 to fix these issues.")
                else:
                    print("\nDatabase consistency: OK")

                # Show table schemas
                print("\nUsers table schema:")
                cursor.execute("PRAGMA table_info(users)")
                for column in cursor.fetchall():
                    print(f"  {column[1]} ({column[2]})")

                print("\nUser_accounts table schema:")
                cursor.execute("PRAGMA table_info(user_accounts)")
                for column in cursor.fetchall():
                    print(f"  {column[1]} ({column[2]})")

                conn.close()

            except sqlite3.Error as e:
                logger.error(f"Database error: {e}")

            print("=" * 60)

        elif choice == '11':
            _toggle_force_password_reset_cli()

        elif choice == '12':
            return

        else:
            print("Invalid choice. Please try again.")

# ============================================================================
# Role Management Menu
# ============================================================================

def display_role_management_menu(auth):
    """Display the role management menu"""
    while True:
        if not auth.check_session() or not auth.check_permission('manage_roles'):
            print("You don't have permission to access Role Management.")
            return

        print("\nRole Management:")
        print("===============")
        print("1. List All Roles")
        print("2. Create New Role")
        print("3. View Role Details")
        print("4. Edit Role")
        print("5. Delete Role")
        print("6. Manage Role Permissions")
        print("7. List All Permissions")
        print("8. Create New Permission")
        print("9. Back")

        choice = input("\nEnter your choice (1-9): ")

        if choice == '1':
            # List all roles
            roles = auth.list_roles()

            if roles:
                print("\nAll Roles:")
                print("=" * 70)
                print(f"{'ID':<5} {'Role Name':<15} {'Description':<30} {'Users':<10}")
                print("-" * 70)

                for role in roles:
                    print(f"{role['id']:<5} {role['role_name']:<15} {role['description'][:28]:<30} {role['user_count']:<10}")

                print("=" * 70)

        elif choice == '2':
            # Create new role
            print("\nCreate New Role:")
            role_name = input("Role Name: ")
            description = input("Description: ")

            # Get permissions
            conn = auth._create_configured_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, permission_name, description FROM permissions ORDER BY permission_name')
            all_permissions = cursor.fetchall()
            conn.close()

            if all_permissions:
                print("\nSelect permissions (comma-separated numbers, blank for none):")
                for i, perm in enumerate(all_permissions, 1):
                    perm_id, perm_name, perm_desc = perm
                    print(f"{i}. {perm_name} - {perm_desc}")

                perm_choices = input("\nPermissions: ")

                selected_permissions = []
                if perm_choices:
                    try:
                        indices = [int(idx.strip()) - 1 for idx in perm_choices.split(',')]
                        selected_permissions = [all_permissions[idx][1] for idx in indices if 0 <= idx < len(all_permissions)]
                    except ValueError:
                        print("Invalid input. No permissions will be added.")

                auth.create_role(role_name, description, selected_permissions)
            else:
                auth.create_role(role_name, description)

        elif choice == '3':
            # View role details
            role_id = input("Enter role ID to view: ")

            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)

                if role:
                    print("\nRole Details:")
                    print("=" * 60)
                    print(f"ID: {role['id']}")
                    print(f"Name: {role['role_name']}")
                    print(f"Description: {role['description']}")
                    print(f"Created: {role['created_at']}")
                    print(f"Updated: {role['updated_at']}")
                    print(f"Users with this role: {role['user_count']}")

                    print("\nPermissions:")
                    for perm in role['permissions']:
                        print(f"- {perm}")

                    print("=" * 60)

            except ValueError:
                print("Invalid role ID. Please enter a number.")

        elif choice == '4':
            # Edit role
            role_id = input("Enter role ID to edit: ")

            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)

                if role:
                    # Check if this is a default role
                    if role['role_name'] in ROLES:
                        print(f"Cannot edit default role '{role['role_name']}'.")
                        continue

                    print("\nEdit Role:")
                    print(f"Current Name: {role['role_name']}")
                    print(f"Current Description: {role['description']}")

                    print("\nEnter new values (leave blank to keep current):")
                    new_name = input("New Name: ")
                    new_description = input("New Description: ")

                    # Build update dictionary
                    updates = {}
                    if new_name:
                        updates['role_name'] = new_name
                    if new_description:
                        updates['description'] = new_description

                    if updates:
                        auth.update_role(role_id, **updates)
                    else:
                        print("No changes made.")

            except ValueError:
                print("Invalid role ID. Please enter a number.")

        elif choice == '5':
            # Delete role
            role_id = input("Enter role ID to delete: ")

            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)

                if role:
                    # Check if this is a default role
                    if role['role_name'] in ROLES:
                        print(f"Cannot delete default role '{role['role_name']}'.")
                        continue

                    # Check if any users have this role
                    if role['user_count'] > 0:
                        print(f"Cannot delete role '{role['role_name']}' because it is assigned to {role['user_count']} user(s).")
                        continue

                    # Confirm deletion
                    confirm = input(f"Are you sure you want to delete role '{role['role_name']}'? (y/n): ").lower()

                    if confirm == 'y':
                        auth.delete_role(role_id)

            except ValueError:
                print("Invalid role ID. Please enter a number.")

        elif choice == '6':
            # Manage role permissions
            role_id = input("Enter role ID to manage permissions: ")

            try:
                role_id = int(role_id)
                role = auth.get_role(role_id=role_id)

                if role:
                    # Check if this is a default role
                    if role['role_name'] in ROLES:
                        print(f"Cannot modify permissions for default role '{role['role_name']}'.")
                        continue

                    while True:
                        print(f"\nPermissions for role '{role['role_name']}':")
                        print("=" * 60)

                        # Get all permissions
                        conn = auth._create_configured_connection()
                        cursor = conn.cursor()
                        cursor.execute('SELECT permission_name FROM permissions ORDER BY permission_name')
                        all_permissions = [row[0] for row in cursor.fetchall()]
                        conn.close()

                        # Check which permissions the role has
                        role_permissions = role['permissions']

                        for i, perm in enumerate(all_permissions, 1):
                            status = "✓" if perm in role_permissions else " "
                            print(f"{i:2}. [{status}] {perm}")

                        print("\n1. Add permission")
                        print("2. Remove permission")
                        print("3. Back")

                        perm_choice = input("\nEnter choice (1-3): ")

                        if perm_choice == '1':
                            # Add permission
                            perm_number = input("Enter permission number to add: ")

                            try:
                                perm_index = int(perm_number) - 1
                                if 0 <= perm_index < len(all_permissions):
                                    perm_name = all_permissions[perm_index]
                                    auth.add_role_permission(role_id, perm_name)
                                    # Refresh role data
                                    role = auth.get_role(role_id=role_id)
                                else:
                                    print("Invalid permission number.")
                            except ValueError:
                                print("Please enter a number.")

                        elif perm_choice == '2':
                            # Remove permission
                            perm_number = input("Enter permission number to remove: ")

                            try:
                                perm_index = int(perm_number) - 1
                                if 0 <= perm_index < len(all_permissions):
                                    perm_name = all_permissions[perm_index]
                                    auth.remove_role_permission(role_id, perm_name)
                                    # Refresh role data
                                    role = auth.get_role(role_id=role_id)
                                else:
                                    print("Invalid permission number.")
                            except ValueError:
                                print("Please enter a number.")

                        elif perm_choice == '3':
                            break
                        else:
                            print("Invalid choice.")

            except ValueError:
                print("Invalid role ID. Please enter a number.")

        elif choice == '7':
            # List all permissions
            permissions = auth.list_permissions()

            if permissions:
                print("\nAll Permissions:")
                print("=" * 80)
                print(f"{'ID':<5} {'Permission Name':<30} {'Description':<45}")
                print("-" * 80)

                for perm in permissions:
                    print(f"{perm['id']:<5} {perm['permission_name']:<30} {perm['description'][:43]:<45}")

                print("=" * 80)

        elif choice == '8':
            # Create new permission
            print("\nCreate New Permission:")
            print("Note: Permission names should be lowercase with underscores (e.g., view_reports)")
            permission_name = input("Permission Name: ")
            description = input("Description: ")

            auth.create_permission(permission_name, description)

        elif choice == '9':
            return
        else:
            print("Invalid choice. Please try again.")

# ============================================================================
# My Account Menu
# ============================================================================

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
            from education_system.shared.cli.security_questions_cli import security_questions_menu
            security_questions_menu(auth)

        elif choice == '0':
            return
        else:
            print("Invalid choice. Please try again.")

# ============================================================================
# MFA Settings Menu (Email Verification)
# ============================================================================

def display_mfa_settings_menu(auth, user):
    """Display MFA settings menu (Email Verification) - syncs with GUI"""
    try:
        from education_system.university_system.infrastructure.auth.mfa_service import MFAService
        mfa_service = MFAService()
    except ImportError as e:
        print(f"\n❌ MFA module not available: {e}")
        return

    user_id = user.get('id')
    username = user.get('username')

    if not user_id:
        print("\n❌ Unable to get user information")
        return

    while True:
        print("\n" + "=" * 50)
        print("MFA Settings (Email Verification)")
        print("=" * 50)

        # Get current MFA status
        try:
            is_verification_disabled = mfa_service.is_verification_disabled(user_id)
            methods_result = mfa_service.get_user_mfa_methods(user_id)
            saved_methods_result = mfa_service.get_saved_mfa_methods(user_id)

            active_methods = []
            if methods_result and methods_result.get('success'):
                active_methods = methods_result.get('methods', [])

            saved_methods = []
            if saved_methods_result and saved_methods_result.get('success'):
                saved_methods = saved_methods_result.get('methods', [])

            has_saved_disabled = any(
                not m.get('is_enabled', True)
                for m in saved_methods
                if m and isinstance(m, dict)
            ) if saved_methods else False

        except Exception as e:
            print(f"\n❌ Error getting MFA status: {e}")
            return

        # Display current status
        if is_verification_disabled:
            print(f"\nStatus: ❌ DISABLED (Password only login)")
        elif active_methods:
            print(f"\nStatus: ✅ ENABLED")
        else:
            print(f"\nStatus: ⚠️  NOT CONFIGURED")

        # Show configured methods
        if active_methods:
            print("\nActive Methods:")
            for method in active_methods:
                if method and isinstance(method, dict):
                    method_type = str(method.get('type', 'Unknown')).upper()
                    identifier = method.get('identifier', '')
                    # Mask identifier
                    if identifier and '@' in str(identifier):
                        parts = str(identifier).split('@')
                        masked = parts[0][:2] + '***@' + parts[1]
                    elif identifier:
                        masked = str(identifier)[:3] + '****'
                    else:
                        masked = 'Configured'
                    print(f"  • {method_type}: {masked}")
        elif has_saved_disabled:
            print("\nSaved Methods (Disabled):")
            for method in saved_methods:
                if method and isinstance(method, dict) and not method.get('is_enabled'):
                    method_type = str(method.get('type', 'Unknown')).upper()
                    identifier = method.get('identifier', '')
                    if identifier and '@' in str(identifier):
                        parts = str(identifier).split('@')
                        masked = parts[0][:2] + '***@' + parts[1]
                    elif identifier:
                        masked = str(identifier)[:3] + '****'
                    else:
                        masked = 'Configured'
                    print(f"  • {method_type}: {masked}")

        print("\n" + "-" * 50)

        # Show appropriate options based on status
        if active_methods or not is_verification_disabled:
            # MFA is enabled
            print("1. Change Email Address")
            print("2. Disable MFA")
            print("3. Back")
            max_choice = 3
        elif has_saved_disabled:
            # MFA disabled but has saved settings
            print("1. Re-enable MFA (use saved settings)")
            print("2. Setup New MFA")
            print("3. Back")
            max_choice = 3
        else:
            # No MFA configured
            print("1. Setup MFA")
            print("2. Back")
            max_choice = 2

        choice = input(f"\nEnter your choice (1-{max_choice}): ").strip()

        if active_methods or not is_verification_disabled:
            # MFA is enabled
            if choice == '1':
                # Change email
                _cli_setup_mfa_email(mfa_service, user_id, username)
            elif choice == '2':
                # Disable MFA
                _cli_disable_mfa(mfa_service, user_id)
            elif choice == '3':
                return
            else:
                print("Invalid choice.")

        elif has_saved_disabled:
            # MFA disabled with saved settings
            if choice == '1':
                # Re-enable with saved settings
                _cli_reenable_mfa(mfa_service, user_id, username, saved_methods)
            elif choice == '2':
                # Setup new
                _cli_setup_mfa_email(mfa_service, user_id, username)
            elif choice == '3':
                return
            else:
                print("Invalid choice.")

        else:
            # No MFA configured
            if choice == '1':
                # Setup MFA
                _cli_setup_mfa_email(mfa_service, user_id, username)
            elif choice == '2':
                return
            else:
                print("Invalid choice.")

# ============================================================================
# MFA Helper Functions
# ============================================================================

def _cli_setup_mfa_email(mfa_service, user_id, username):
    """Setup or update email MFA via CLI"""
    print("\n" + "=" * 50)
    print("Setup Email MFA")
    print("=" * 50)

    email = input("\nEnter your email address: ").strip()

    if not email or '@' not in email:
        print("\n❌ Invalid email address")
        return

    # Confirm
    confirm = input(f"\nSetup MFA with email: {email}? (y/n): ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        # Send verification OTP
        print(f"\n📧 Sending verification code to {email}...")
        otp_result = mfa_service.generate_email_otp(user_id, email)

        if not otp_result.get('success'):
            print(f"\n❌ Failed to send verification code: {otp_result.get('error')}")
            return

        if otp_result.get('email_failed'):
            # Show code on screen as fallback
            code = otp_result.get('code', '')
            print(f"\n⚠️  Email delivery failed. Your verification code is: {code}")
        else:
            print(f"\n✅ Verification code sent to {email}")

        # Verify the code
        max_attempts = 3
        for attempt in range(max_attempts):
            code_input = input("\nEnter 6-digit verification code: ").strip()

            verify_result = mfa_service.verify_email_otp(user_id, code_input)
            if verify_result.get('success'):
                # Update/save the MFA method
                update_result = mfa_service.update_mfa_method(user_id, 'email', email)
                if update_result.get('success'):
                    print("\n✅ MFA has been successfully configured!")
                    print(f"   Email: {email}")
                    print("\n   You will receive verification codes at this email when logging in.")
                else:
                    print(f"\n❌ Failed to save MFA settings: {update_result.get('error')}")
                return
            else:
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    print(f"❌ Invalid code. {remaining} attempt(s) remaining.")
                else:
                    print("❌ Too many failed attempts. Setup cancelled.")

    except Exception as e:
        print(f"\n❌ Error setting up MFA: {e}")

def _cli_disable_mfa(mfa_service, user_id):
    """Disable MFA via CLI"""
    print("\n" + "=" * 50)
    print("Disable MFA")
    print("=" * 50)
    print("\n⚠️  Warning: Disabling MFA makes your account less secure.")
    print("   Your settings will be saved and can be restored later.")

    confirm = input("\nAre you sure you want to disable MFA? (y/n): ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        result = mfa_service.disable_mfa(user_id)
        if result.get('success'):
            print("\n✅ MFA has been disabled.")
            print("   Your settings have been saved for 90 days.")
            print("   You can re-enable MFA from CLI or GUI at any time.")
        else:
            print(f"\n❌ Failed to disable MFA: {result.get('error')}")
    except Exception as e:
        print(f"\n❌ Error disabling MFA: {e}")

def _cli_reenable_mfa(mfa_service, user_id, username, saved_methods):
    """Re-enable MFA with saved settings via CLI"""
    print("\n" + "=" * 50)
    print("Re-enable MFA")
    print("=" * 50)

    print("\nYour previously saved MFA settings will be restored.")

    confirm = input("\nRe-enable MFA with saved settings? (y/n): ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        result = mfa_service.reenable_mfa(user_id)
        if result.get('success'):
            print("\n✅ MFA has been re-enabled!")
            print(f"   {result.get('methods_count', 1)} method(s) restored.")

            # Try to send confirmation email
            email_to_notify = None
            if saved_methods:
                for method in saved_methods:
                    if method and method.get('type') == 'email' and method.get('identifier'):
                        email_to_notify = method.get('identifier')
                        break

            if email_to_notify:
                try:
                    from education_system.university_system.infrastructure.auth.email_otp_service import SMTPEmailProvider
                    from education_system.university_system.infrastructure.email.template_utils import render_template
                    import smtplib
                    from email.mime.text import MIMEText
                    from email.mime.multipart import MIMEMultipart

                    smtp_provider = SMTPEmailProvider()

                    # Load template from file (same as GUI)
                    template_vars = {
                        'username': username,
                        'email': email_to_notify,
                        'methods_count': str(result.get('methods_count', 1))
                    }
                    subject, body = render_template('authentication/mfa_reenabled', template_vars)

                    # Fallback if template fails
                    if not subject or not body:
                        subject = "MFA Re-enabled for Your Account"
                        body = f"Hello {username},\n\nMFA has been re-enabled for your account.\n\nUniversity System Security Team"

                    msg = MIMEMultipart()
                    msg['Subject'] = subject
                    msg['From'] = f"{smtp_provider.from_name} <{smtp_provider.from_email}>"
                    msg['To'] = email_to_notify
                    msg.attach(MIMEText(body, 'plain'))

                    with smtplib.SMTP(smtp_provider.smtp_server, smtp_provider.smtp_port) as server:
                        server.starttls()
                        server.login(smtp_provider.username, smtp_provider.password)
                        server.send_message(msg)

                    print(f"\n   Confirmation email sent to: {email_to_notify}")
                except Exception as email_error:
                    print(f"\n   (Confirmation email could not be sent)")

        else:
            print(f"\n❌ Failed to re-enable MFA: {result.get('error')}")
    except Exception as e:
        print(f"\n❌ Error re-enabling MFA: {e}")

# ============================================================================
# Account Linking Menu
# ============================================================================

def _display_account_linking_menu(auth):
    """Display account linking sub-menu"""
    while True:
        if not auth.check_session():
            return

        user = auth.current_user
        print("\nAccount Linking:")
        print("================")
        print("1. View Linked Accounts")
        print("2. Create Link Request")
        print("3. View Pending Link Requests")
        print("4. Switch Active Role")
        print("5. Revert to Original Role")
        print("6. Unlink Account")
        print("7. Back")

        choice = input("\nEnter your choice (1-7): ")

        if choice == '1':
            linked = auth.get_linked_accounts()
            if linked:
                print("\nLinked Accounts:")
                print("=" * 70)
                for acc in linked:
                    print(f"  Link #{acc.get('id')}: {acc.get('primary_username', 'N/A')} <-> {acc.get('secondary_username', 'N/A')} (Active: {acc.get('is_active')})")
                print("=" * 70)
            else:
                print("No linked accounts found.")

        elif choice == '2':
            target = input("Enter user ID to link with: ").strip()
            reason = input("Reason for linking (optional): ").strip() or None
            try:
                result = auth.create_link_request(int(target), reason)
                if result.get('success'):
                    print(f"Link request created (ID: {result.get('request_id')})")
                else:
                    print(f"Failed: {result.get('error')}")
            except ValueError:
                print("Invalid user ID.")

        elif choice == '3':
            direction = input("View (i)ncoming or (o)utgoing requests? [i]: ").strip().lower()
            direction = 'outgoing' if direction == 'o' else 'incoming'
            requests = auth.get_link_requests(status='pending', direction=direction)
            if requests:
                print(f"\n{direction.title()} Link Requests:")
                for req in requests:
                    print(f"  Request #{req.get('id')}: from user {req.get('requesting_user_id')} to user {req.get('target_user_id')} - {req.get('status')}")

                if direction == 'incoming':
                    action = input("\nApprove or Reject a request? (a/r/n): ").strip().lower()
                    if action in ('a', 'r'):
                        req_id = input("Enter request ID: ").strip()
                        try:
                            if action == 'a':
                                result = auth.approve_link_request(int(req_id))
                            else:
                                reason = input("Rejection reason (optional): ").strip() or None
                                result = auth.reject_link_request(int(req_id), reason)
                            print(f"{'Approved' if action == 'a' else 'Rejected'}: {result.get('success')}")
                        except ValueError:
                            print("Invalid request ID.")
            else:
                print("No pending requests.")

        elif choice == '4':
            linked = auth.get_linked_accounts()
            if linked:
                for acc in linked:
                    print(f"  Link #{acc.get('id')}: {acc.get('primary_username')} <-> {acc.get('secondary_username')}")
                link_id = input("Enter link ID to switch to: ").strip()
                try:
                    result = auth.switch_active_role(int(link_id))
                    if result.get('success'):
                        print(f"Switched to role: {result.get('new_role')}")
                    else:
                        print(f"Failed: {result.get('error')}")
                except ValueError:
                    print("Invalid link ID.")
            else:
                print("No linked accounts to switch to.")

        elif choice == '5':
            result = auth.revert_role()
            if result.get('success'):
                print(f"Reverted to original role: {result.get('role')}")
            else:
                print(f"Failed: {result.get('error')}")

        elif choice == '6':
            link_id = input("Enter link ID to unlink: ").strip()
            try:
                confirm = input("Are you sure? (y/n): ").lower()
                if confirm == 'y':
                    result = auth.unlink_account(int(link_id))
                    if result.get('success'):
                        print("Account unlinked.")
                    else:
                        print(f"Failed: {result.get('error')}")
            except ValueError:
                print("Invalid link ID.")

        elif choice == '7':
            return
        else:
            print("Invalid choice.")


# ============================================================================
# WebAuthn Menu
# ============================================================================

def _display_webauthn_menu(auth):
    """Display WebAuthn/FIDO2 security key sub-menu"""
    while True:
        if not auth.check_session():
            return

        print("\nSecurity Keys (WebAuthn/FIDO2):")
        print("===============================")
        print("1. List Registered Keys")
        print("2. Register New Key")
        print("3. Remove Key")
        print("4. Rename Key")
        print("5. Back")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            keys = auth.list_webauthn_keys()
            if keys:
                print("\nRegistered Security Keys:")
                print("=" * 70)
                for key in keys:
                    name = key.get('credential_name', 'Unnamed')
                    cred_id = key.get('credential_id', '')[:16] + '...'
                    created = key.get('created_at', 'Unknown')
                    active = 'Active' if key.get('is_active') else 'Inactive'
                    print(f"  {name} (ID: {cred_id}) - {active} - Registered: {created}")
                print("=" * 70)
            else:
                print("No security keys registered.")

        elif choice == '2':
            name = input("Key name (e.g., 'My YubiKey'): ").strip()
            result = auth.register_webauthn_key(name or None)
            if result.get('success'):
                print(f"\nRegistration challenge created (session: {result.get('session_id', '')[:8]}...)")
                print("Complete registration using your security key device.")
                print("Note: Full WebAuthn registration requires a browser or compatible client.")
            else:
                print(f"Failed: {result.get('error')}")

        elif choice == '3':
            cred_id = input("Enter credential ID to remove: ").strip()
            if cred_id:
                confirm = input("Are you sure? (y/n): ").lower()
                if confirm == 'y':
                    result = auth.remove_webauthn_key(cred_id)
                    if result.get('success'):
                        print("Key removed.")
                    else:
                        print(f"Failed: {result.get('error')}")

        elif choice == '4':
            cred_id = input("Enter credential ID to rename: ").strip()
            new_name = input("New name: ").strip()
            if cred_id and new_name:
                result = auth.rename_webauthn_key(cred_id, new_name)
                if result.get('success'):
                    print("Key renamed.")
                else:
                    print(f"Failed: {result.get('error')}")

        elif choice == '5':
            return
        else:
            print("Invalid choice.")


# ============================================================================
# Biometric Menu
# ============================================================================

def _display_biometric_menu(auth):
    """Display biometric authentication sub-menu"""
    while True:
        if not auth.check_session():
            return

        print("\nBiometric Authentication:")
        print("=========================")
        print("1. List Enrollments")
        print("2. Enroll Face")
        print("3. Enroll Fingerprint")
        print("4. Revoke Enrollment")
        print("5. Back")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            enrollments = auth.list_biometric_enrollments()
            if enrollments:
                print("\nBiometric Enrollments:")
                print("=" * 70)
                for e in enrollments:
                    bio_type = e.get('biometric_type', 'Unknown')
                    active = 'Active' if e.get('is_active') else 'Revoked'
                    quality = e.get('quality_score', 'N/A')
                    created = e.get('enrolled_at', 'Unknown')
                    print(f"  #{e.get('id')} - {bio_type} - {active} - Quality: {quality} - Enrolled: {created}")
                print("=" * 70)
            else:
                print("No biometric enrollments found.")

        elif choice == '2':
            print("\nFace Enrollment:")
            print("Note: In a production environment, this would capture a photo via webcam.")
            print("For CLI testing, provide a base64-encoded face template.")
            data = input("Enter face template data (base64): ").strip()
            if data:
                result = auth.enroll_biometric('face', data)
                if result.get('success'):
                    print(f"Face enrolled successfully (ID: {result.get('enrollment_id')})")
                else:
                    print(f"Failed: {result.get('error')}")
            else:
                print("No data provided.")

        elif choice == '3':
            print("\nFingerprint Enrollment:")
            print("Note: Requires a compatible fingerprint reader.")
            data = input("Enter fingerprint template data (base64): ").strip()
            if data:
                result = auth.enroll_biometric('fingerprint', data)
                if result.get('success'):
                    print(f"Fingerprint enrolled successfully (ID: {result.get('enrollment_id')})")
                else:
                    print(f"Failed: {result.get('error')}")
            else:
                print("No data provided.")

        elif choice == '4':
            enrollment_id = input("Enter enrollment ID to revoke: ").strip()
            try:
                confirm = input("Are you sure? (y/n): ").lower()
                if confirm == 'y':
                    result = auth.revoke_biometric_enrollment(int(enrollment_id))
                    if result.get('success'):
                        print("Enrollment revoked.")
                    else:
                        print(f"Failed: {result.get('error')}")
            except ValueError:
                print("Invalid enrollment ID.")

        elif choice == '5':
            return
        else:
            print("Invalid choice.")


# ============================================================================
# Delegated Access Menu
# ============================================================================

def _display_delegated_access_menu(auth):
    """Display delegated access sub-menu"""
    while True:
        if not auth.check_session():
            return

        user = auth.current_user
        role = user.get('role', '')

        print("\nDelegated Access:")
        print("=================")

        if role == 'student':
            print("1. View My Delegations (Granted)")
            print("2. Grant Access to Someone")
            print("3. Revoke a Delegation")
            print("4. View Delegation Requests")
            print("5. Back")

            choice = input("\nEnter your choice (1-5): ")

            if choice == '1':
                delegations = auth.get_delegations_for_user(direction='granted')
                if delegations:
                    print("\nActive Delegations (you granted):")
                    for d in delegations:
                        print(f"  #{d.get('id')} -> User {d.get('delegate_user_id')} | Scopes: {d.get('scope_keys')} | Expires: {d.get('expires_at', 'Never')}")
                else:
                    print("No active delegations.")

            elif choice == '2':
                delegate_id = input("Enter user ID to grant access to: ").strip()
                print("\nAvailable scopes: view_grades, view_finances, view_health, view_attendance, view_timetable, make_payments, communicate_staff")
                scopes = input("Enter scope keys (comma-separated): ").strip()
                relationship = input("Relationship (e.g., parent, guardian): ").strip() or None
                expires = input("Expiry date (YYYY-MM-DD, blank for no expiry): ").strip() or None
                try:
                    scope_keys = [s.strip() for s in scopes.split(',') if s.strip()]
                    result = auth.create_delegation(int(delegate_id), scope_keys, relationship, expires)
                    if result.get('success'):
                        print(f"Delegation created (ID: {result.get('delegation_id')})")
                    else:
                        print(f"Failed: {result.get('error')}")
                except ValueError:
                    print("Invalid input.")

            elif choice == '3':
                delegation_id = input("Enter delegation ID to revoke: ").strip()
                try:
                    result = auth.revoke_delegation(int(delegation_id))
                    if result.get('success'):
                        print("Delegation revoked.")
                    else:
                        print(f"Failed: {result.get('error')}")
                except ValueError:
                    print("Invalid delegation ID.")

            elif choice == '4':
                requests = auth.get_delegation_requests(direction='incoming')
                if requests:
                    print("\nPending Delegation Requests:")
                    for r in requests:
                        print(f"  #{r.get('id')} from User {r.get('requester_user_id')} | Relationship: {r.get('relationship')} | Scopes: {r.get('requested_scope_keys')}")
                    action = input("\nApprove or Reject? (a/r/n): ").strip().lower()
                    if action in ('a', 'r'):
                        req_id = input("Request ID: ").strip()
                        try:
                            if action == 'a':
                                result = auth.approve_delegation_request(int(req_id))
                            else:
                                reason = input("Reason (optional): ").strip() or None
                                result = auth.reject_delegation_request(int(req_id), reason)
                            print(f"Result: {'Success' if result.get('success') else result.get('error')}")
                        except ValueError:
                            print("Invalid ID.")
                else:
                    print("No pending requests.")

            elif choice == '5':
                return

        elif role == 'parent':
            print("1. View My Delegations (Received)")
            print("2. Request Access to a Student")
            print("3. View My Requests")
            print("4. Act as Delegate")
            print("5. Stop Acting as Delegate")
            print("6. Back")

            choice = input("\nEnter your choice (1-6): ")

            if choice == '1':
                delegations = auth.get_delegations_for_user(direction='received')
                if delegations:
                    print("\nActive Delegations (granted to you):")
                    for d in delegations:
                        print(f"  #{d.get('id')} from User {d.get('grantor_user_id')} | Scopes: {d.get('scope_keys')} | Expires: {d.get('expires_at', 'Never')}")
                else:
                    print("No active delegations.")

            elif choice == '2':
                target_id = input("Enter student user ID: ").strip()
                relationship = input("Relationship (parent/guardian): ").strip()
                print("\nAvailable scopes: view_grades, view_finances, view_health, view_attendance, view_timetable, make_payments, communicate_staff")
                scopes = input("Enter requested scope keys (comma-separated): ").strip()
                reason = input("Reason for request: ").strip() or None
                try:
                    scope_keys = [s.strip() for s in scopes.split(',') if s.strip()]
                    result = auth.create_delegation_request(int(target_id), relationship, scope_keys, reason)
                    if result.get('success'):
                        print(f"Request submitted (ID: {result.get('request_id')})")
                    else:
                        print(f"Failed: {result.get('error')}")
                except ValueError:
                    print("Invalid input.")

            elif choice == '3':
                requests = auth.get_delegation_requests(direction='outgoing')
                if requests:
                    print("\nMy Delegation Requests:")
                    for r in requests:
                        print(f"  #{r.get('id')} to User {r.get('target_user_id')} | Status: {r.get('status')}")
                else:
                    print("No requests found.")

            elif choice == '4':
                delegations = auth.get_delegations_for_user(direction='received')
                if delegations:
                    for d in delegations:
                        print(f"  #{d.get('id')} from User {d.get('grantor_user_id')} | Scopes: {d.get('scope_keys')}")
                    target_id = input("Enter grantor user ID to act on behalf of: ").strip()
                    try:
                        auth.session_manager.current_user['acting_as_delegate_for'] = int(target_id)
                        print(f"Now acting as delegate for user {target_id}. Your permissions are scoped.")
                    except (ValueError, TypeError):
                        print("Invalid user ID.")
                else:
                    print("No delegations available.")

            elif choice == '5':
                if user.get('acting_as_delegate_for'):
                    auth.session_manager.current_user['acting_as_delegate_for'] = None
                    print("Stopped acting as delegate.")
                else:
                    print("You are not currently acting as a delegate.")

            elif choice == '6':
                return

        else:
            # Admin or other roles
            print("1. View All Delegations")
            print("2. View Delegation Requests")
            print("3. Expire Overdue Delegations")
            print("4. Back")

            choice = input("\nEnter your choice (1-4): ")

            if choice == '1':
                user_id_input = input("Enter user ID (blank for all): ").strip()
                user_id = int(user_id_input) if user_id_input else None
                delegations = auth.get_delegations_for_user(user_id, direction='granted')
                if delegations:
                    print("\nDelegations:")
                    for d in delegations:
                        print(f"  #{d.get('id')} | Grantor: {d.get('grantor_user_id')} -> Delegate: {d.get('delegate_user_id')} | Active: {d.get('is_active')}")
                else:
                    print("No delegations found.")

            elif choice == '2':
                requests = auth.get_delegation_requests(status='pending')
                if requests:
                    print("\nPending Delegation Requests:")
                    for r in requests:
                        print(f"  #{r.get('id')} | Requester: {r.get('requester_user_id')} -> Target: {r.get('target_user_id')}")
                else:
                    print("No pending requests.")

            elif choice == '3':
                result = auth.expire_delegations()
                if result.get('success'):
                    print(f"Expired {result.get('expired_count', 0)} delegation(s).")
                else:
                    print(f"Failed: {result.get('error')}")

            elif choice == '4':
                return


# ============================================================================
# Chatbot Integration Menu
# ============================================================================

def display_chatbot_integration_menu(auth):
    """Display chatbot integration menu"""
    from education_system.university_system.infrastructure.auth.integrations.chatbot_integration import (
        launch_chatbot_interface as _launch_chatbot,
        get_chatbot_conversation_history as _get_chatbot_history,
        generate_chatbot_analytics as _gen_chatbot_analytics,
        initialize_chatbot_integration as _init_chatbot,
    )
    while True:
        if not auth.check_session():
            return

        user = auth.current_user

        # Check if user has chatbot access
        user_perms = user.get('permissions', [])
        if 'access_chatbot' not in user_perms:
            print("You don't have permission to access the chatbot.")
            return

        print("\nUniversity Chatbot Integration:")
        print("===============================")
        print(f"Logged in as: {user['username']} ({user['role']})")

        if is_chatbot_available():
            print("Status: ✅ Available")
        else:
            print("Status: ⚠️ Limited functionality")

        # Build menu based on permissions
        menu_options = []
        menu_options.append("1. Start Chatbot Session")
        menu_options.append("2. View My Conversation History")

        option_num = 3
        if 'chatbot_admin' in user_perms:
            menu_options.append(f"{option_num}. View Chatbot Analytics")
            analytics_option = option_num
            option_num += 1
        else:
            analytics_option = None

        if 'view_all_conversations' in user_perms:
            menu_options.append(f"{option_num}. View All User Conversations")
            all_conversations_option = option_num
            option_num += 1
        else:
            all_conversations_option = None

        menu_options.append(f"{option_num}. Test Chatbot Integration")
        test_option = option_num
        option_num += 1

        menu_options.append(f"{option_num}. Back")
        back_option = option_num

        # Display menu
        for option in menu_options:
            print(option)

        choice = input(f"\nEnter your choice (1-{back_option}): ")

        try:
            choice_num = int(choice)
        except ValueError:
            print("Invalid choice. Please enter a number.")
            continue

        if choice == '1':
            # Start chatbot session
            _launch_chatbot(auth)

        elif choice_num == 2:
            # View conversation history - FIXED VERSION
            try:
                history = _get_chatbot_history(auth, user['username'])
                if history:
                    print(f"\nYour Chatbot Conversation History ({len(history)} interactions):")
                    print("=" * 60)
                    for i, conv in enumerate(history[:10], 1):
                        # Handle different conversation history formats
                        timestamp = conv.get('timestamp', 'Unknown time')

                        # Try to extract message text from different possible structures
                        message_text = None
                        if 'message' in conv:
                            message_text = conv['message']
                        elif 'details' in conv:
                            # Extract from details field (activity log format)
                            details = conv['details']
                            if details and 'Q:' in details:
                                # Extract question from "Q: ... A: ..." format
                                try:
                                    message_text = details.split('Q:')[1].split('A:')[0].strip()
                                except (IndexError, AttributeError) as e:
                                    logger.debug(f"Failed to parse Q/A format: {e}")
                                    message_text = details[:40] if details else "Chat interaction"
                            else:
                                message_text = details[:40] if details else "Chat interaction"
                        else:
                            message_text = "Chat interaction"

                        # Truncate message if too long
                        if message_text and len(message_text) > 40:
                            display_text = message_text[:40] + "..."
                        else:
                            display_text = message_text or "Chat interaction"

                        print(f"{i}. {timestamp} - {display_text}")

                    if len(history) > 10:
                        print(f"... and {len(history) - 10} more interactions")
                else:
                    print("No conversation history found. Start a chatbot session to begin!")

            except Exception as e:
                print(f"Error retrieving conversation history: {e}")
                print("No conversation history available at this time.")

        elif choice_num == analytics_option and analytics_option:
            # View analytics
            try:
                analytics = _gen_chatbot_analytics(auth)
                if analytics and 'error' not in analytics:
                    print("\nChatbot Analytics:")
                    print("=" * 40)
                    print(f"Total Interactions: {analytics.get('total_interactions', 0)}")
                    if 'unique_users' in analytics:
                        print(f"Unique Users: {analytics.get('unique_users', 0)}")
                    if 'interactions_by_role' in analytics:
                        print(f"Interactions by Role: {analytics.get('interactions_by_role', {})}")
                    print(f"Status: {analytics.get('status', 'Active')}")
                    print(f"Generated: {analytics.get('generated_at', 'unknown')}")

                    if analytics.get('daily_interactions'):
                        print("\nDaily Activity:")
                        for date, count in analytics['daily_interactions'].items():
                            print(f"  {date}: {count}")
                else:
                    print("No analytics data available or error occurred.")
            except Exception as e:
                print(f"Error generating analytics: {e}")

        elif choice_num == all_conversations_option and all_conversations_option:
            # View all conversations - FIXED VERSION
            print("\nAll User Conversations:")
            print("=" * 50)
            try:
                with auth.db_manager.get_connection() as conn:
                    cursor = conn.cursor()

                    # Try to get from activity_log table (more likely to exist)
                    cursor.execute('''
                        SELECT username, COUNT(*) as count, MAX(timestamp) as last_chat
                        FROM activity_log
                        WHERE action = 'Chatbot interaction'
                        GROUP BY username
                        ORDER BY last_chat DESC
                        LIMIT 20
                    ''')

                    all_conversations = cursor.fetchall()
                    if all_conversations:
                        print(f"{'Username':<15} {'Interactions':<12} {'Last Activity':<20}")
                        print("-" * 50)
                        for username, count, last_chat in all_conversations:
                            print(f"{username:<15} {count:<12} {last_chat:<20}")
                    else:
                        print("No conversations found in activity log.")

                        # Try alternative table if it exists
                        try:
                            cursor.execute('''
                                SELECT name FROM sqlite_master
                                WHERE type='table' AND name='chatbot_conversations'
                            ''')
                            if cursor.fetchone():
                                cursor.execute('''
                                    SELECT username, COUNT(*) as count, MAX(timestamp) as last_chat
                                    FROM chatbot_conversations
                                    GROUP BY username
                                    ORDER BY last_chat DESC
                                    LIMIT 20
                                ''')
                                alt_conversations = cursor.fetchall()
                                if alt_conversations:
                                    print("Found conversations in chatbot_conversations table:")
                                    for username, count, last_chat in alt_conversations:
                                        print(f"{username}: {count} conversations (Last: {last_chat})")
                                else:
                                    print("No conversations found in chatbot_conversations table either.")
                            else:
                                print("No chatbot-specific conversation tables found.")
                        except Exception as alt_e:
                            print(f"Error checking alternative tables: {alt_e}")

            except Exception as e:
                print(f"Error retrieving conversations: {e}")

        elif choice_num == test_option:
            # Test integration
            print("\nTesting Chatbot Integration:")
            print("=" * 35)

            if is_chatbot_available():
                print("✅ Chatbot module available")

                if hasattr(auth, 'chatbot') and auth.chatbot:
                    print("✅ Chatbot instance created")

                    try:
                        test_response = auth.chatbot.process_message("Hello", user['username'])
                        print(f"✅ Message processing works")
                        print(f"  Test response: {test_response[:80]}...")
                    except Exception as e:
                        print(f"❌ Message processing failed: {e}")

                    print("✅ Integration test completed")
                else:
                    print("❌ Chatbot instance not found")
                    if _init_chatbot(auth):
                        print("✅ Chatbot initialized successfully")
                    else:
                        print("❌ Failed to initialize chatbot")
            else:
                print("⚠️ Chatbot in limited mode")

        elif choice_num == back_option:
            return

        else:
            print("Invalid choice. Please try again.")
