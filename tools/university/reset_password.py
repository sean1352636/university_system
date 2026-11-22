#!/usr/bin/env python3
"""
Password Reset Utility

Resets a login in the shared auth database (auth.db), which every system signs
in against. A reset therefore applies to all the systems that login can reach.

Usage:
    python tools/university/reset_password.py                    # Interactive mode
    python tools/university/reset_password.py --user admin       # Reset one user
    python tools/university/reset_password.py --list-users       # List logins
    EDU_DEV_SEED=true python tools/university/reset_password.py --reset-defaults

A reset unlocks the account, ends its sessions and sets the new password as
temporary: the user replaces it at next sign-in if forced password change is
switched on. It doesn't reactivate a deactivated account.

--reset-defaults puts the University's seeded development accounts back to the
passwords in docs/reference/DEFAULT_ACCOUNTS.md. Those passwords are public, so
it only runs when EDU_DEV_SEED is on.
"""

import argparse
import getpass
import sqlite3
import sys
from pathlib import Path

# Add the package root to path: tools/university/<this> -> tools -> <repo root> -> src
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "src"))

from education_system.platform.identity.auth.core import UserAuth  # noqa: E402
from education_system.platform.identity.auth.db import connect  # noqa: E402
from education_system.platform.identity.auth.exceptions import AuthError  # noqa: E402
from education_system.platform.identity.auth.password_manager import (  # noqa: E402
    hash_password,
)
from education_system.platform.identity.auth.schema import (  # noqa: E402
    _DEFAULT_ACCOUNTS,
    _is_dev_mode,
)

_MESSAGES = {
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



def _t(key, **kwargs):
    """The English text for *key*, with its {placeholders} filled in."""
    text = _MESSAGES.get(key, key)
    for k, v in kwargs.items():
        text = text.replace('{' + k + '}', str(v))
    return text


def _db_missing(db_path):
    """True if an explicit path doesn't exist, so a typo can't create an empty database."""
    if db_path and not Path(db_path).is_file():
        print(f"❌ {_t('reset_password.db_error', error=f'no such database: {db_path}')}")
        return True
    return False


def reset_user_password(username, new_password, db_path=None):
    """
    Reset a user's password in auth.db through the shared auth service.

    The password must meet the normal strength rules.

    Args:
        username: Username to reset
        new_password: New password
        db_path: Optional auth database path (default: the live auth.db)

    Returns:
        bool: True if successful, False otherwise
    """
    if _db_missing(db_path):
        return False

    try:
        result = UserAuth(db_path).unlock_and_reset_password(username, new_password)
    except AuthError as e:
        if str(e) == "User not found.":
            print(f"❌ {_t('reset_password.user_not_found', username=username)}")
        else:
            print(f"❌ {e}")
        return False
    except sqlite3.Error as e:
        print(f"❌ {_t('reset_password.db_error', error=str(e))}")
        return False
    except Exception as e:
        print(f"❌ {_t('reset_password.unexpected_error', error=str(e))}")
        return False

    print(f"✅ {_t('reset_password.success', username=username)}")
    if not _is_active(username, db_path):
        print(f"⚠️  '{username}' is deactivated, so it still can't sign in.")
    if result.get("email_sent"):
        print(f"   The new password was e-mailed to {result.get('email')}.")
    return True


def _is_active(username, db_path=None):
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT is_active FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()
    return bool(row and row[0])


def _university_default_accounts():
    """Seeded accounts whose access includes the University (superadmin too)."""
    return [
        account for account in _DEFAULT_ACCOUNTS
        if any(system == "university" for system, _role in account["systems"])
    ]


def reset_default_passwords(db_path=None):
    """
    Put the University's seeded development accounts back to their documented
    passwords. Those passwords are too weak for the strength rules and are
    public, so this only runs when EDU_DEV_SEED is on.

    Args:
        db_path: Optional auth database path (default: the live auth.db)

    Returns:
        int: Number of accounts updated
    """
    if not _is_dev_mode():
        print("❌ --reset-defaults sets publicly documented passwords, so it needs "
              "EDU_DEV_SEED=true. Nothing was changed.")
        return 0
    if _db_missing(db_path):
        return 0

    print(f"🔄 {_t('reset_password.resetting_defaults')}\n")

    updated = []
    conn = connect(db_path)
    try:
        for account in _university_default_accounts():
            cursor = conn.execute(
                "UPDATE users SET password_hash = ?, legacy_salt = NULL, "
                "must_change_password = 0, failed_login_attempts = 0, "
                "locked_until = NULL, updated_at = datetime('now') WHERE username = ?",
                (hash_password(account["password"]), account["username"]),
            )
            if cursor.rowcount:
                updated.append(account["username"])
        conn.execute(
            "UPDATE sessions SET is_active = 0 WHERE user_id IN "
            f"(SELECT id FROM users WHERE username IN ({','.join('?' * len(updated))}))",
            updated,
        )
        conn.commit()
    finally:
        conn.close()

    for username in updated:
        print(f"   Username: {username}")
    print(f"\n✅ {_t('reset_password.reset_complete', count=len(updated))}")
    return len(updated)


def list_users(db_path=None):
    """Print every login with its role in each system. Never prints a hash."""
    if _db_missing(db_path):
        return
    try:
        conn = connect(db_path)
        try:
            users = conn.execute(
                "SELECT u.username, u.is_active, "
                "group_concat(s.system_key || ':' || s.role, ', ') "
                "FROM users u LEFT JOIN user_systems s ON s.user_id = u.id "
                "GROUP BY u.id ORDER BY u.id"
            ).fetchall()
        finally:
            conn.close()
    except Exception as e:
        print(f"❌ {_t('reset_password.error_listing_users', error=str(e))}")
        return

    print(f"\n{_t('reset_password.users_in_db')}")
    print("-" * 60)
    print(f"{_t('reset_password.username'):<20} {_t('reset_password.active'):<8} "
          f"{_t('reset_password.role')}")
    print("-" * 60)
    for username, is_active, roles in users:
        status = _t('reset_password.yes') if is_active else _t('reset_password.no')
        print(f"{username:<20} {status:<8} {roles or _t('reset_password.na')}")
    print("-" * 60)
    print(_t('reset_password.total', count=len(users)))


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
        description='Reset login passwords in the shared auth database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Interactive mode
  %(prog)s --user admin             # Reset specific user (interactive)
  %(prog)s --reset-defaults         # Reset default dev accounts (needs EDU_DEV_SEED=true)
  %(prog)s --list-users             # List all logins
        """
    )

    parser.add_argument('--user', '-u', metavar='USERNAME',
                        help='Username to reset')
    parser.add_argument('--password', '-p', metavar='PASSWORD',
                        help='New password (WARNING: visible in command history)')
    parser.add_argument('--reset-defaults', action='store_true',
                        help='Reset the default development accounts (needs EDU_DEV_SEED=true)')
    parser.add_argument('--list-users', action='store_true',
                        help='List all logins')
    parser.add_argument('--db-path', metavar='PATH',
                        help='Auth database path (default: the live auth.db)')

    args = parser.parse_args()
    db_path = args.db_path

    if args.list_users:
        list_users(db_path)
        return

    if args.reset_defaults:
        reset_default_passwords(db_path)
        return

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
