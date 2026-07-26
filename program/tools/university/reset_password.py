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
import os
import secrets
from education_system.systems.university.infrastructure.database.db import sqlite3
import sys
import argparse
from datetime import datetime
from pathlib import Path
import getpass
import logging

# Add project root to path for standard imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root.parent))

# Use standard imports instead of dynamic code execution
# This avoids security risks from exec_module() which could execute arbitrary code
try:
    from education_system.systems.university.infrastructure import paths
    from education_system.systems.university.infrastructure.i18n import get_text as _t, init_i18n
    init_i18n()
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    def _t(key, **kwargs):
        """Fallback translation function"""
        # Map keys to default English text
        translations = {
            "reset_password.title": "University System - Password Reset Utility",
            "reset_password.username_prompt": "Enter username:",
            "reset_password.username_empty": "Username cannot be empty",
            "reset_password.password_prompt": "Enter new password:",
            "reset_password.password_empty": "Password cannot be empty",
            "reset_password.confirm_prompt": "Confirm new password:",
            "reset_password.passwords_no_match": "Passwords do not match. Try again.",
            "reset_password.user_not_found": "Error: User '{username}' not found in database",
            "reset_password.success": "Password reset successful for user: {username}",
            "reset_password.db_error": "Database error: {error}",
            "reset_password.unexpected_error": "Unexpected error: {error}",
            "reset_password.resetting_defaults": "Resetting default passwords for development accounts...",
            "reset_password.warning_default_passwords": "WARNING: Using default development passwords for: {accounts}",
            "reset_password.set_env_vars": "Set environment variables for production use.",
            "reset_password.reset_complete": "Reset complete! Updated {count} account(s).",
            "reset_password.users_in_db": "Users in database:",
            "reset_password.username": "Username",
            "reset_password.role": "Role",
            "reset_password.active": "Active",
            "reset_password.yes": "Yes",
            "reset_password.no": "No",
            "reset_password.na": "N/A",
            "reset_password.total": "Total: {count} users",
            "reset_password.error_listing_users": "Error listing users: {error}",
            "reset_password.resetting_for_user": "Resetting password for user: {username}",
            "reset_password.warning_insecure_cli": "WARNING: Providing passwords via command line is insecure!",
        }
        text = translations.get(key, key)
        for k, v in kwargs.items():
            text = text.replace('{' + k + '}', str(v))
        return text

    # Fallback: construct paths safely without dynamic code execution
    # This is secure because we only use static path construction
    class _SafePathsClass:
        """Minimal paths configuration for standalone execution.

        This fallback avoids dynamic code execution (exec_module) which
        could be exploited if the module source is compromised.
        """
        def __init__(self):
            self._project_root = project_root
            # Construct paths statically - no dynamic code execution
            self.DEFAULT_DB_PATH = self._project_root / 'data' / 'db_files' / 'student_records.db'
            self.DATA_DIR = self._project_root / 'data'
            self.LOG_DIR = self._project_root / 'logs'

    paths = _SafePathsClass()

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
            print(f"❌ {_t('reset_password.user_not_found', username=username)}")
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

        print(f"✅ {_t('reset_password.success', username=username)}")
        return True

    except sqlite3.Error as e:
        print(f"❌ {_t('reset_password.db_error', error=str(e))}")
        return False
    except Exception as e:
        print(f"❌ {_t('reset_password.unexpected_error', error=str(e))}")
        return False

def reset_default_passwords(db_path=None):
    """
    Reset passwords for default development/test accounts.

    Passwords are read from environment variables with fallback to development defaults.
    SECURITY: In production, ALWAYS set environment variables:
      - DEFAULT_ADMIN_PASSWORD
      - DEFAULT_STAFF_PASSWORD
      - DEFAULT_STUDENT_PASSWORD
      - DEFAULT_INSTRUCTOR_PASSWORD
      - DEFAULT_TEACHER_PASSWORD

    Args:
        db_path: Optional database path

    Returns:
        int: Number of accounts updated
    """
    # Get passwords from centralized defaults (no hardcoded fallbacks).
    # If env vars are missing, core.defaults generates secure random passwords.
    from education_system.systems.university.infrastructure.defaults import (
        DEFAULT_ADMIN_PASSWORD, DEFAULT_STAFF_PASSWORD, DEFAULT_STUDENT_PASSWORD,
    )
    default_passwords = {
        'admin': DEFAULT_ADMIN_PASSWORD,
        'staff': DEFAULT_STAFF_PASSWORD,
        'student': DEFAULT_STUDENT_PASSWORD,
        'instructor': os.environ.get('DEFAULT_INSTRUCTOR_PASSWORD', DEFAULT_STAFF_PASSWORD),
        'teacher': os.environ.get('DEFAULT_TEACHER_PASSWORD', DEFAULT_STAFF_PASSWORD),
    }

    if db_path is None:
        db_path = paths.DEFAULT_DB_PATH

    print(f"🔄 {_t('reset_password.resetting_defaults')}\n")

    updated_count = 0
    for username, password in default_passwords.items():
        if reset_user_password(username, password, db_path):
            # Don't print actual passwords in logs for security
            masked_pwd = password[:2] + '*' * (len(password) - 2) if len(password) > 2 else '***'
            print(f"   Username: {username:15} Password: {masked_pwd}")
            updated_count += 1

    print(f"\n✅ {_t('reset_password.reset_complete', count=updated_count)}")
    return updated_count

def interactive_mode(db_path=None):
    """Run in interactive mode"""
    print("=" * 60)
    print(f"         {_t('reset_password.title')}")
    print("=" * 60)
    print()

    username = input(f"{_t('reset_password.username_prompt')} ").strip()
    if not username:
        print(f"❌ {_t('reset_password.username_empty')}")
        return False

    # Get password (with confirmation)
    while True:
        password = getpass.getpass(f"{_t('reset_password.password_prompt')} ")
        if not password:
            print(f"❌ {_t('reset_password.password_empty')}")
            continue

        confirm = getpass.getpass(f"{_t('reset_password.confirm_prompt')} ")
        if password != confirm:
            print(f"❌ {_t('reset_password.passwords_no_match')}")
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

            print(f"\n{_t('reset_password.users_in_db')}")
            print("-" * 60)
            print(f"{_t('reset_password.username'):<20} {_t('reset_password.role'):<15} {_t('reset_password.active'):<10}")
            print("-" * 60)
            for username, role, is_active in users:
                status = f"✅ {_t('reset_password.yes')}" if is_active else f"❌ {_t('reset_password.no')}"
                print(f"{username:<20} {role or _t('reset_password.na'):<15} {status:<10}")
            print("-" * 60)
            print(_t('reset_password.total', count=len(users)))
        except Exception as e:
            print(f"❌ {_t('reset_password.error_listing_users', error=str(e))}")
        return

    # Reset defaults
    if args.reset_defaults:
        reset_default_passwords(db_path)
        return

    # Reset specific user
    if args.user:
        if args.password:
            # Password provided via command line (not recommended)
            print(f"⚠️  {_t('reset_password.warning_insecure_cli')}")
            reset_user_password(args.user, args.password, db_path)
        else:
            # Interactive password entry
            print(_t('reset_password.resetting_for_user', username=args.user))
            password = getpass.getpass(f"{_t('reset_password.password_prompt')} ")
            confirm = getpass.getpass(f"{_t('reset_password.confirm_prompt')} ")

            if password != confirm:
                print(f"❌ {_t('reset_password.passwords_no_match')}")
                return

            reset_user_password(args.user, password, db_path)
        return

    # Interactive mode (default)
    interactive_mode(db_path)

if __name__ == '__main__':
    main()
