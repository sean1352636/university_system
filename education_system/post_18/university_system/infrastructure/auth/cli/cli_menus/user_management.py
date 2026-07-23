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

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    DatabaseError,
)

logger = logging.getLogger("education_system.post_18.university_system.infrastructure.auth.cli.cli_menus")

def _toggle_force_password_reset_cli():
    """Toggle the forced password reset setting from the CLI."""
    try:
        from education_system.shared.auth.core import UserAuth as _SharedAuth
        shared_auth = _SharedAuth()
        current = shared_auth.get_system_password_policy("university")

        status = "ON" if current else "OFF"
        print(f"\nForced Password Reset (University) is currently: {status}")
        print("When ON, University users with expired/unset passwords must reset on login.")
        print("When OFF, University password expiry checks are skipped.\n")

        toggle = input(f"Turn it {'OFF' if current else 'ON'}? (y/n): ").strip().lower()
        if toggle == 'y':
            new_val = not current
            shared_auth.set_system_password_policy("university", new_val)
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
                print("\nUser created successfully. Temporary password has been set - user must change on first login.")

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

