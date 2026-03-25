"""Audit logging decorator and user permissions management."""
import os
import time
import logging
from functools import wraps

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.services.analytics.advanced_search import _globals


def audit_log(func):
    """Decorator to log search activities for audit trail"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time

        logging.info(f"User: {_globals.current_user}, Function: {func.__name__}, "
                    f"Args: {args[:2] if args else 'None'}, "
                    f"Execution Time: {execution_time:.2f}s")
        return result
    return wrapper

def view_search_audit_trail():
    """View search audit trail"""
    print("\n🔍 SEARCH AUDIT TRAIL")
    print("="*50)

    # Read from log file
    try:
        if os.path.exists('search_audit.log'):
            with open('refactored/core/logs/search_audit.log', 'r') as f:
                lines = f.readlines()

            # Show last 20 entries
            recent_lines = lines[-20:] if len(lines) > 20 else lines

            print("Recent search activities:")
            print("-" * 80)

            for line in recent_lines:
                print(line.strip())
        else:
            print("No audit log found.")

    except Exception as e:
        print(f"Error reading audit log: {e}")

def manage_user_permissions():
    """Manage user permissions (admin feature)"""
    print("\n👥 USER PERMISSIONS MANAGEMENT")
    print("="*50)

    print("1. View User Permissions")
    print("2. Add User")
    print("3. Modify User Permissions")
    print("4. Remove User")

    choice = input("Select option (1-4): ").strip()

    if choice == '1':
        view_user_permissions()
    elif choice == '2':
        add_user_permissions()
    elif choice == '3':
        modify_user_permissions()
    elif choice == '4':
        remove_user_permissions()

def view_user_permissions():
    """View all user permissions"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT user_id, role, permissions, created_date
        FROM user_permissions
        ORDER BY created_date DESC
        ''')

        users = cursor.fetchall()

        if not users:
            print("No user permissions found.")
            return

        print("\n👥 USER PERMISSIONS:")
        print("-" * 80)
        print(f"{'User ID':<20} {'Role':<15} {'Permissions':<30} {'Created':<15}")
        print("-" * 80)

        for user_id, role, permissions, created in users:
            print(f"{user_id:<20} {role:<15} {permissions:<30} {created[:10]:<15}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Error viewing permissions: {e}")

def add_user_permissions():
    """Add new user permissions"""
    user_id = input("Enter User ID: ").strip()
    role = input("Enter Role (admin/user/viewer): ").strip()
    permissions = input("Enter Permissions (comma-separated): ").strip()

    if not all([user_id, role, permissions]):
        print("All fields are required.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO user_permissions (user_id, role, permissions)
        VALUES (?, ?, ?)
        ''', (user_id, role, permissions))

        conn.commit()
        conn.close()

        print(f"✅ User '{user_id}' added successfully with role '{role}'.")

    except sqlite3.Error as e:
        print(f"Error adding user: {e}")

def modify_user_permissions():
    """Modify user permissions"""
    view_user_permissions()

    user_id = input("\nEnter User ID to modify: ").strip()
    if not user_id:
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute('SELECT role, permissions FROM user_permissions WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            print("User not found.")
            return

        current_role, current_permissions = result
        print(f"\nCurrent role: {current_role}")
        print(f"Current permissions: {current_permissions}")

        new_role = input(f"New role (current: {current_role}): ").strip()
        new_permissions = input(f"New permissions (current: {current_permissions}): ").strip()

        if new_role or new_permissions:
            if new_role:
                cursor.execute('UPDATE user_permissions SET role = ? WHERE user_id = ?', (new_role, user_id))
            if new_permissions:
                cursor.execute('UPDATE user_permissions SET permissions = ? WHERE user_id = ?', (new_permissions, user_id))

            conn.commit()
            print(f"✅ User '{user_id}' permissions updated successfully.")
        else:
            print("No changes made.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Error modifying permissions: {e}")

def remove_user_permissions():
    """Remove user permissions"""
    view_user_permissions()

    user_id = input("\nEnter User ID to remove: ").strip()
    if not user_id:
        return

    confirm = input(f"Remove all permissions for user '{user_id}'? (y/n): ").strip().lower()

    if confirm == 'y':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('DELETE FROM user_permissions WHERE user_id = ?', (user_id,))

            if cursor.rowcount > 0:
                conn.commit()
                print(f"✅ User '{user_id}' removed successfully.")
            else:
                print("User not found.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Error removing user: {e}")
    else:
        print("Removal cancelled.")
