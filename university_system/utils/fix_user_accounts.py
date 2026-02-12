#!/usr/bin/env python3
"""
Utility to fix user account to user profile mappings in the database.

This script:
1. Identifies and fixes incorrect user_account to users mappings
2. Ensures all system accounts (admin, staff, student) have correct roles
3. Cleans up duplicate or orphaned records
4. Validates database integrity after fixes

Run this after database initialization or if login shows wrong roles.
"""

from university_system.infrastructure.database.db import sqlite3
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from university_system.modules.shared.constants import paths

DB_PATH = str(paths.DEFAULT_DB_PATH)

# System accounts that should always exist
SYSTEM_ACCOUNTS = {
    'admin': {
        'role': 'admin',
        'first_name': 'System',
        'last_name': 'Administrator',
        'email': 'admin@university.local'
    },
    'staff': {
        'role': 'staff',
        'first_name': 'Staff',
        'last_name': 'User',
        'email': 'staff@university.local'
    },
    'student': {
        'role': 'student',
        'first_name': 'Student',
        'last_name': 'User',
        'email': 'student@university.local'
    }
}

def analyze_database(conn):
    """Analyze the database for issues"""
    cursor = conn.cursor()
    issues = []

    print("\n" + "="*70)
    print("DATABASE ANALYSIS")
    print("="*70)

    # Check 1: Accounts without matching users
    cursor.execute("""
        SELECT ua.id, ua.username, ua.user_id
        FROM user_accounts ua
        LEFT JOIN users u ON ua.user_id = u.id
        WHERE u.id IS NULL
    """)
    orphaned = cursor.fetchall()
    if orphaned:
        issues.append(f"Found {len(orphaned)} orphaned accounts (no matching user)")
        for acc_id, username, user_id in orphaned:
            print(f"  ⚠️  Account '{username}' (ID {acc_id}) points to non-existent user_id {user_id}")

    # Check 2: System accounts with wrong roles
    cursor.execute("""
        SELECT ua.username, ua.user_id, u.username as user_username, u.role
        FROM user_accounts ua
        JOIN users u ON ua.user_id = u.id
        WHERE ua.username IN ('admin', 'staff', 'student')
    """)
    system_accounts = cursor.fetchall()
    for acc_username, user_id, user_username, role in system_accounts:
        expected_role = SYSTEM_ACCOUNTS[acc_username]['role']
        if role != expected_role:
            issues.append(f"System account '{acc_username}' has wrong role '{role}' (expected '{expected_role}')")
            print(f"  ⚠️  Account '{acc_username}' → user '{user_username}' (role: {role}, expected: {expected_role})")

    # Check 3: Duplicate user_id references
    cursor.execute("""
        SELECT user_id, COUNT(*) as count, GROUP_CONCAT(username) as usernames
        FROM user_accounts
        GROUP BY user_id
        HAVING count > 1
    """)
    duplicates = cursor.fetchall()
    if duplicates:
        issues.append(f"Found {len(duplicates)} user IDs referenced by multiple accounts")
        for user_id, count, usernames in duplicates:
            print(f"  ⚠️  User ID {user_id} referenced by {count} accounts: {usernames}")

    # Check 4: System accounts that don't exist
    cursor.execute("SELECT username FROM user_accounts WHERE username IN ('admin', 'staff', 'student')")
    existing = {row[0] for row in cursor.fetchall()}
    missing = set(SYSTEM_ACCOUNTS.keys()) - existing
    if missing:
        issues.append(f"Missing system accounts: {', '.join(missing)}")
        for acc in missing:
            print(f"  ⚠️  System account '{acc}' not found")

    print(f"\n{len(issues)} issue(s) found" if issues else "\n✅ No issues found!")
    return issues

def fix_system_account(conn, username):
    """Fix or create a system account with correct user mapping"""
    cursor = conn.cursor()
    account_info = SYSTEM_ACCOUNTS[username]
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"\nFixing system account: {username}")

    # Check if user_account exists
    cursor.execute('SELECT id, user_id FROM user_accounts WHERE username = ?', (username,))
    account_row = cursor.fetchone()

    # Check if user profile exists with correct username
    cursor.execute('SELECT id, role FROM users WHERE username = ?', (username,))
    user_row = cursor.fetchone()

    if user_row:
        user_id, current_role = user_row
        # User exists - check if role is correct
        if current_role != account_info['role']:
            print(f"  → Updating user role from '{current_role}' to '{account_info['role']}'")
            cursor.execute(
                'UPDATE users SET role = ?, updated_at = ? WHERE id = ?',
                (account_info['role'], timestamp, user_id)
            )
    else:
        # Create new user profile
        print(f"  → Creating new user profile with role '{account_info['role']}'")
        cursor.execute("""
            INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            username,
            account_info['first_name'],
            account_info['last_name'],
            account_info['email'],
            account_info['role'],
            timestamp,
            timestamp
        ))
        user_id = cursor.lastrowid

    if account_row:
        # Update existing account to point to correct user
        account_id, old_user_id = account_row
        if old_user_id != user_id:
            print(f"  → Updating account to point to user_id {user_id} (was {old_user_id})")
            cursor.execute(
                'UPDATE user_accounts SET user_id = ?, updated_at = ? WHERE id = ?',
                (user_id, timestamp, account_id)
            )
        else:
            print(f"  ✓ Account already correctly mapped to user_id {user_id}")

    conn.commit()
    return user_id

def clean_duplicate_mappings(conn):
    """Clean up accounts that point to the same user_id"""
    cursor = conn.cursor()

    print("\n" + "="*70)
    print("CLEANING DUPLICATE MAPPINGS")
    print("="*70)

    cursor.execute("""
        SELECT user_id, GROUP_CONCAT(username || ':' || id) as accounts
        FROM user_accounts
        GROUP BY user_id
        HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()

    if not duplicates:
        print("✅ No duplicate mappings found")
        return

    for user_id, accounts_str in duplicates:
        accounts = [a.split(':') for a in accounts_str.split(',')]
        print(f"\nUser ID {user_id} has {len(accounts)} accounts:")
        for username, acc_id in accounts:
            print(f"  - Account ID {acc_id}: '{username}'")

        # Keep the system account if present, otherwise keep the first one
        system_accounts = [acc for acc in accounts if acc[0] in SYSTEM_ACCOUNTS]
        if system_accounts:
            keep = system_accounts[0]
            print(f"  → Keeping system account '{keep[0]}' (ID {keep[1]})")
        else:
            keep = accounts[0]
            print(f"  → Keeping first account '{keep[0]}' (ID {keep[1]})")

        # Delete others
        for username, acc_id in accounts:
            if acc_id != keep[1]:
                print(f"  → Deleting duplicate account '{username}' (ID {acc_id})")
                cursor.execute('DELETE FROM user_accounts WHERE id = ?', (int(acc_id),))

    conn.commit()
    print("\n✅ Cleaned duplicate mappings")

def verify_integrity(conn):
    """Verify database integrity after fixes"""
    cursor = conn.cursor()

    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70)

    all_good = True

    # Verify system accounts
    for username in SYSTEM_ACCOUNTS.keys():
        cursor.execute("""
            SELECT ua.username, u.role, u.id
            FROM user_accounts ua
            JOIN users u ON ua.user_id = u.id
            WHERE ua.username = ?
        """, (username,))
        result = cursor.fetchone()

        if result:
            acc_user, role, user_id = result
            expected_role = SYSTEM_ACCOUNTS[username]['role']
            if role == expected_role:
                print(f"✅ {username:10s} → user_id {user_id:3d}, role: {role}")
            else:
                print(f"❌ {username:10s} → role mismatch: {role} (expected {expected_role})")
                all_good = False
        else:
            print(f"❌ {username:10s} → NOT FOUND")
            all_good = False

    # Check for orphaned accounts
    cursor.execute("""
        SELECT COUNT(*)
        FROM user_accounts ua
        LEFT JOIN users u ON ua.user_id = u.id
        WHERE u.id IS NULL
    """)
    orphaned_count = cursor.fetchone()[0]
    if orphaned_count > 0:
        print(f"\n❌ Found {orphaned_count} orphaned accounts")
        all_good = False
    else:
        print(f"\n✅ No orphaned accounts")

    # Check for duplicate mappings
    cursor.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT user_id
            FROM user_accounts
            GROUP BY user_id
            HAVING COUNT(*) > 1
        )
    """)
    duplicate_count = cursor.fetchone()[0]
    if duplicate_count > 0:
        print(f"❌ Found {duplicate_count} duplicate user_id mappings")
        all_good = False
    else:
        print(f"✅ No duplicate user_id mappings")

    return all_good

def main():
    """Main fix routine"""
    import argparse

    parser = argparse.ArgumentParser(description='Fix user account mappings in the database')
    parser.add_argument('--yes', '-y', action='store_true', help='Automatically apply fixes without confirmation')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze, do not fix')
    args = parser.parse_args()

    print("="*70)
    print("USER ACCOUNT FIX UTILITY")
    print("="*70)
    print(f"Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"\n❌ Database not found at: {DB_PATH}")
        sys.exit(1)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('PRAGMA foreign_keys = ON')

        # Step 1: Analyze current state
        issues = analyze_database(conn)

        if not issues:
            print("\n" + "="*70)
            print("DATABASE IS HEALTHY - NO FIXES NEEDED")
            print("="*70)
            return

        if args.analyze_only:
            print("\n(Analysis only mode - no fixes applied)")
            return

        # Step 2: Ask for confirmation (unless --yes flag is used)
        print("\n" + "="*70)
        if args.yes:
            print("Auto-applying fixes (--yes flag provided)")
        else:
            try:
                response = input("Apply fixes? (yes/no): ").strip().lower()
                if response not in ('yes', 'y'):
                    print("Aborted.")
                    return
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                return

        print("\n" + "="*70)
        print("APPLYING FIXES")
        print("="*70)

        # Step 3: Fix system accounts
        for username in SYSTEM_ACCOUNTS.keys():
            fix_system_account(conn, username)

        # Step 4: Clean duplicate mappings
        clean_duplicate_mappings(conn)

        # Step 5: Verify
        if verify_integrity(conn):
            print("\n" + "="*70)
            print("✅ ALL FIXES APPLIED SUCCESSFULLY!")
            print("="*70)
        else:
            print("\n" + "="*70)
            print("⚠️  SOME ISSUES REMAIN - MANUAL REVIEW NEEDED")
            print("="*70)

        conn.close()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
