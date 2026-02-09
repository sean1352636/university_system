#!/usr/bin/env python3
"""
Quick test script for Staff CRUD functionality
Tests database schema and basic operations
"""

import sqlite3
import hashlib
import secrets
from datetime import datetime

DB_PATH = "data/db_files/student_records.db"

def test_database_schema():
    """Test that required tables and columns exist"""
    print("=" * 60)
    print("Testing Database Schema")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check users table
    print("\n1. Checking 'users' table...")
    cursor.execute("PRAGMA table_info(users)")
    users_columns = {row[1] for row in cursor.fetchall()}
    required_users_cols = {'id', 'username', 'email', 'first_name', 'last_name', 'role', 'created_at'}

    if required_users_cols.issubset(users_columns):
        print("   ✅ users table has all required columns")
        print(f"   Columns: {', '.join(sorted(users_columns))}")
    else:
        missing = required_users_cols - users_columns
        print(f"   ❌ Missing columns in users table: {missing}")
        return False

    # Check user_accounts table
    print("\n2. Checking 'user_accounts' table...")
    cursor.execute("PRAGMA table_info(user_accounts)")
    accounts_columns = {row[1] for row in cursor.fetchall()}
    required_accounts_cols = {'id', 'username', 'password_hash', 'salt', 'user_id', 'is_active'}

    if required_accounts_cols.issubset(accounts_columns):
        print("   ✅ user_accounts table has all required columns")
        print(f"   Columns: {', '.join(sorted(accounts_columns))}")
    else:
        missing = required_accounts_cols - accounts_columns
        print(f"   ❌ Missing columns in user_accounts table: {missing}")
        return False

    conn.close()
    print("\n✅ Database schema validation passed!")
    return True


def test_create_staff():
    """Test creating a staff member"""
    print("\n" + "=" * 60)
    print("Testing Staff Creation")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Generate test data
    test_username = f"test_staff_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_email = f"{test_username}@university.edu"
    test_password = "TestPassword123"

    print(f"\n1. Creating test staff member...")
    print(f"   Username: {test_username}")
    print(f"   Email: {test_email}")
    print(f"   Role: staff")

    try:
        # Hash password
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            test_password.encode(),
            salt.encode(),
            1_000_000,
            dklen=64
        )
        password_hash = key.hex()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert into users table
        cursor.execute('''
            INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (test_username, "Test", "Staff", test_email, "staff", timestamp, timestamp))

        user_id = cursor.lastrowid
        print(f"   ✅ Created user record (ID: {user_id})")

        # Insert into user_accounts table
        cursor.execute('''
            INSERT INTO user_accounts (username, password_hash, salt, user_id, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
        ''', (test_username, password_hash, salt, user_id, timestamp, timestamp))

        print(f"   ✅ Created user_accounts record")

        conn.commit()

        # Verify the staff member was created
        cursor.execute('''
            SELECT u.id, u.username, u.email, u.role, ua.is_active
            FROM users u
            LEFT JOIN user_accounts ua ON u.id = ua.user_id
            WHERE u.username = ?
        ''', (test_username,))

        result = cursor.fetchone()
        if result:
            print(f"   ✅ Verification successful:")
            print(f"      ID: {result[0]}")
            print(f"      Username: {result[1]}")
            print(f"      Email: {result[2]}")
            print(f"      Role: {result[3]}")
            print(f"      Active: {bool(result[4])}")

            # Clean up test data
            print(f"\n2. Cleaning up test data...")
            cursor.execute('DELETE FROM user_accounts WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            print(f"   ✅ Test data cleaned up")

            conn.close()
            print("\n✅ Staff creation test passed!")
            return True
        else:
            print("   ❌ Verification failed - staff member not found")
            conn.close()
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        conn.rollback()
        conn.close()
        return False


def test_query_staff():
    """Test querying existing staff members"""
    print("\n" + "=" * 60)
    print("Testing Staff Query")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("\n1. Querying all staff members...")
        cursor.execute('''
            SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role,
                   COALESCE(ua.is_active, 1) as is_active
            FROM users u
            LEFT JOIN user_accounts ua ON u.id = ua.user_id
            WHERE u.role IN ('staff', 'instructor', 'admin')
            LIMIT 5
        ''')

        results = cursor.fetchall()

        if results:
            print(f"   ✅ Found {len(results)} staff member(s)")
            print("\n   Staff Members:")
            for i, staff in enumerate(results, 1):
                user_id, username, email, first_name, last_name, role, is_active = staff
                full_name = f"{first_name or ''} {last_name or ''}".strip()
                status = "Active" if is_active else "Inactive"
                print(f"   {i}. [{user_id}] {username} - {full_name} ({role}) - {status}")
        else:
            print("   ⚠️  No staff members found in database")
            print("   This is normal if you haven't created any staff members yet")

        conn.close()
        print("\n✅ Staff query test passed!")
        return True

    except Exception as e:
        print(f"   ❌ Error: {e}")
        conn.close()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("STAFF CRUD SYSTEM - DATABASE VALIDATION TEST")
    print("=" * 60)

    tests = [
        ("Database Schema", test_database_schema),
        ("Staff Creation", test_create_staff),
        ("Staff Query", test_query_staff)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 All tests passed! Staff CRUD system is ready to use.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the errors above.")

    print("=" * 60)


if __name__ == "__main__":
    main()
