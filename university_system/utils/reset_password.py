#!/usr/bin/env python3
"""
Password Reset Utility

This script allows administrators to reset user passwords in the system.
Useful for:
- Resetting forgotten passwords
- Setting up development/test accounts
- Emergency access recovery

Usage:
    python reset_password.py                    # Interactive mode
    python reset_password.py --user admin       # Reset specific user
    python reset_password.py --reset-defaults   # Reset all default accounts
"""

import hashlib
import secrets
import sqlite3
import sys
import argparse
from datetime import datetime
from pathlib import Path
import getpass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root.parent))

try:
    from university_system.modules.shared.constants import paths
except ImportError:
    # Fallback for direct execution - dynamically find the paths module
    import os
    import importlib.util

    # Attempt to load paths module directly
    paths_file = project_root / 'university_system' / 'modules' / 'shared' / 'constants' / 'paths.py'
    if paths_file.exists():
        spec = importlib.util.spec_from_file_location("paths", paths_file)
        paths = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(paths)
    else:
        # Last resort: create minimal paths class
        class PathsClass:
            # Use dynamic path construction as last resort
            _project_root = project_root
            DEFAULT_DB_PATH = _project_root / 'data' / 'db_files' / 'student_records.db'

        paths = PathsClass()


def hash_password(password, salt=None):
    """
    Hash a password with PBKDF2-SHA256 (1,000,000 iterations).

    Args:
        password: Plain text password
        salt: Optional salt (generates new one if not provided)

    Returns:
        tuple: (salt, password_hash)
    """
    if salt is None:
        salt = secrets.token_hex(16)

    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt.encode(),
        1_000_000,  # OWASP recommended for PBKDF2-SHA256
        dklen=64
    )

    return salt, key.hex()


def reset_user_password(username, new_password, db_path=None):
    """
    Reset a user's password in the database.

    Args:
        username: Username to reset
        new_password: New password
        db_path: Optional database path

    Returns:
        bool: True if successful, False otherwise
    """
    if db_path is None:
        db_path = paths.DEFAULT_DB_PATH

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT id FROM user_accounts WHERE username=?", (username,))
        result = cursor.fetchone()

        if not result:
            print(f"❌ Error: User '{username}' not found in database")
            conn.close()
            return False

        # Generate new password hash
        salt, password_hash = hash_password(new_password)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Update password
        cursor.execute('''
            UPDATE user_accounts
            SET password_hash = ?,
                salt = ?,
                updated_at = ?,
                password_reset_required = 0,
                is_active = 1
            WHERE username = ?
        ''', (password_hash, salt, timestamp, username))

        conn.commit()
        conn.close()

        print(f"✅ Password reset successful for user: {username}")
        return True

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def reset_default_passwords(db_path=None):
    """
    Reset passwords for default development/test accounts.

    Args:
        db_path: Optional database path

    Returns:
        int: Number of accounts updated
    """
    default_passwords = {
        'admin': 'admin123',
        'staff': 'staff123',
        'student': 'student123',
        'instructor': 'instructor123',
        'teacher': 'teacher123',
    }

    if db_path is None:
        db_path = paths.DEFAULT_DB_PATH

    print("🔄 Resetting default passwords for development accounts...\n")

    updated_count = 0
    for username, password in default_passwords.items():
        if reset_user_password(username, password, db_path):
            print(f"   Username: {username:15} Password: {password}")
            updated_count += 1

    print(f"\n✅ Reset complete! Updated {updated_count} account(s).")
    return updated_count


def interactive_mode(db_path=None):
    """Run in interactive mode"""
    print("=" * 60)
    print("         University System - Password Reset Utility")
    print("=" * 60)
    print()

    username = input("Enter username: ").strip()
    if not username:
        print("❌ Username cannot be empty")
        return False

    # Get password (with confirmation)
    while True:
        password = getpass.getpass("Enter new password: ")
        if not password:
            print("❌ Password cannot be empty")
            continue

        confirm = getpass.getpass("Confirm new password: ")
        if password != confirm:
            print("❌ Passwords do not match. Try again.")
            continue

        break

    return reset_user_password(username, password, db_path)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Reset user passwords in the University System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Interactive mode
  %(prog)s --user admin             # Reset specific user (interactive)
  %(prog)s --reset-defaults         # Reset all default accounts
  %(prog)s --list-users             # List all users in database
        """
    )

    parser.add_argument('--user', '-u', metavar='USERNAME',
                        help='Username to reset')
    parser.add_argument('--password', '-p', metavar='PASSWORD',
                        help='New password (WARNING: visible in command history)')
    parser.add_argument('--reset-defaults', action='store_true',
                        help='Reset all default development accounts')
    parser.add_argument('--list-users', action='store_true',
                        help='List all users in the database')
    parser.add_argument('--db-path', metavar='PATH',
                        help='Database path (default: from config)')

    args = parser.parse_args()

    db_path = args.db_path if args.db_path else paths.DEFAULT_DB_PATH

    # List users
    if args.list_users:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ua.username, u.role, ua.is_active
                FROM user_accounts ua
                LEFT JOIN users u ON ua.user_id = u.id
                ORDER BY ua.id
            """)
            users = cursor.fetchall()
            conn.close()

            print("\nUsers in database:")
            print("-" * 60)
            print(f"{'Username':<20} {'Role':<15} {'Active':<10}")
            print("-" * 60)
            for username, role, is_active in users:
                status = "✅ Yes" if is_active else "❌ No"
                print(f"{username:<20} {role or 'N/A':<15} {status:<10}")
            print("-" * 60)
            print(f"Total: {len(users)} users")
        except Exception as e:
            print(f"❌ Error listing users: {e}")
        return

    # Reset defaults
    if args.reset_defaults:
        reset_default_passwords(db_path)
        return

    # Reset specific user
    if args.user:
        if args.password:
            # Password provided via command line (not recommended)
            print("⚠️  WARNING: Providing passwords via command line is insecure!")
            reset_user_password(args.user, args.password, db_path)
        else:
            # Interactive password entry
            print(f"Resetting password for user: {args.user}")
            password = getpass.getpass("Enter new password: ")
            confirm = getpass.getpass("Confirm new password: ")

            if password != confirm:
                print("❌ Passwords do not match")
                return

            reset_user_password(args.user, password, db_path)
        return

    # Interactive mode (default)
    interactive_mode(db_path)


if __name__ == '__main__':
    main()
