"""Audit logging decorator and user permissions management."""
import os
import time
import logging
from functools import wraps

from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search import _globals


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
    """View search audit trail backed by the search_analytics table."""
    print("\n🔍 SEARCH AUDIT TRAIL")
    print("=" * 50)

    limit_raw = input("How many recent entries to show [50]: ").strip()
    try:
        limit = max(1, min(1000, int(limit_raw))) if limit_raw else 50
    except ValueError:
        limit = 50
    user_filter = input("Filter by user (blank for all): ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(search_analytics)")
        cols = {row[1] for row in cursor.fetchall()}
        if not cols:
            print("search_analytics table is not initialized yet.")
            conn.close()
            return _fallback_audit_log_file()

        ts_col = "timestamp" if "timestamp" in cols else ("search_datetime" if "search_datetime" in cols else "NULL")
        query_col = "search_query" if "search_query" in cols else ("search_criteria" if "search_criteria" in cols else "NULL")
        results_col = "results_count" if "results_count" in cols else ("result_count" if "result_count" in cols else "NULL")

        sql = (
            f"SELECT COALESCE({ts_col}, ''), COALESCE(user_id, ''), COALESCE(search_type, ''), "
            f"COALESCE({query_col}, ''), COALESCE({results_col}, 0), COALESCE(execution_time, 0) "
            f"FROM search_analytics"
        )
        params = []
        if user_filter:
            sql += " WHERE user_id LIKE ?"
            params.append(f"%{user_filter}%")
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print("No matching audit entries found.")
            return

        print(f"\n{'Timestamp':<20} {'User':<16} {'Type':<18} {'Results':<8} {'Exec(ms)':<10} Query")
        print("-" * 100)
        for ts, user, stype, query, rcount, etime in rows:
            try:
                exec_ms = f"{float(etime) * 1000:.1f}"
            except (TypeError, ValueError):
                exec_ms = "0.0"
            query_short = (query or "")[:60]
            print(f"{str(ts)[:19]:<20} {(user or 'anon')[:15]:<16} {(stype or '')[:17]:<18} "
                  f"{int(rcount):<8} {exec_ms:<10} {query_short}")

        print(f"\n{len(rows)} entries shown.")

    except Exception as e:
        print(f"Error reading audit trail from database: {e}")
        _fallback_audit_log_file()


def _fallback_audit_log_file():
    """Fallback: print tail of the audit log file if it exists."""
    try:
        if os.path.exists('search_audit.log'):
            with open('search_audit.log', 'r') as f:
                lines = f.readlines()
            recent_lines = lines[-20:] if len(lines) > 20 else lines
            print("\nRecent audit log file entries:")
            print("-" * 80)
            for line in recent_lines:
                print(line.strip())
        else:
            print("No audit log file found.")
    except Exception as e:
        print(f"Error reading audit log file: {e}")

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
