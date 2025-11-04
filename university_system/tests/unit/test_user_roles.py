#!/usr/bin/env python3
"""
Test script for user roles and permissions
Tests role-based access and user management
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_user_roles():
    """Test user roles and permissions"""
    print("=" * 60)
    print("USER ROLES & PERMISSIONS TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Role distribution
        cursor.execute("""
            SELECT role, COUNT(*)
            FROM users
            GROUP BY role
            ORDER BY COUNT(*) DESC
        """)
        role_distribution = cursor.fetchall()

        print("\n✓ User role distribution:")
        total_users = sum(count for _, count in role_distribution)
        for role, count in role_distribution:
            percentage = (count / total_users) * 100
            print(f"  - {role}: {count} ({percentage:.1f}%)")

        # Test 2: Students with user accounts
        cursor.execute("""
            SELECT COUNT(*) FROM students
        """)
        total_students = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM users WHERE role = 'student'
        """)
        student_users = cursor.fetchone()[0]

        print(f"\n✓ Student account coverage: {student_users}/{total_students}")
        if student_users < total_students:
            print(f"  ⚠ {total_students - student_users} students without user accounts")

        # Test 3: Instructors with user accounts
        cursor.execute("""
            SELECT COUNT(*) FROM instructors WHERE is_active = 1
        """)
        total_instructors = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM users WHERE role = 'instructor'
        """)
        instructor_users = cursor.fetchone()[0]

        print(f"\n✓ Instructor account coverage: {instructor_users}/{total_instructors}")

        # Test 4: Admin users
        cursor.execute("""
            SELECT COUNT(*) FROM users WHERE role = 'admin'
        """)
        admin_count = cursor.fetchone()[0]

        print(f"\n✓ Admin users: {admin_count}")

        if admin_count == 0:
            print("  ⚠ Warning: No admin users found")
        elif admin_count > 10:
            print("  ⚠ Warning: High number of admin users")

        # Test 5: Users with multiple roles
        cursor.execute("""
            SELECT username, COUNT(DISTINCT role) as role_count
            FROM users
            GROUP BY username
            HAVING role_count > 1
        """)
        multi_role_users = cursor.fetchall()

        if multi_role_users:
            print(f"\n⚠ Warning: {len(multi_role_users)} users with multiple roles")
        else:
            print("\n✓ No users have multiple roles (via username)")

        # Test 6: Orphaned roles (users with roles but no related entity)
        cursor.execute("""
            SELECT u.username, u.role
            FROM users u
            WHERE u.role = 'student'
            AND u.student_id IS NULL
        """)
        orphaned_students = cursor.fetchall()

        if orphaned_students:
            print(f"\n✗ FAILED: {len(orphaned_students)} student users without student_id")
        else:
            print("\n✓ All student users have valid student_id")

        # Test 7: Email consistency
        cursor.execute("""
            SELECT u.email as user_email, s.email_address as student_email
            FROM users u
            JOIN students s ON u.student_id = s.student_id
            WHERE u.role = 'student' AND u.email != s.email_address
        """)
        email_mismatches = cursor.fetchall()

        if email_mismatches:
            print(f"\n⚠ Warning: {len(email_mismatches)} email mismatches between users and students")
        else:
            print("\n✓ User emails match student records")

        # Test 8: Sample users by role
        print("\n✓ Sample users by role:")
        for role, _ in role_distribution:
            cursor.execute("""
                SELECT username, email, created_at
                FROM users
                WHERE role = ?
                LIMIT 2
            """, (role,))
            samples = cursor.fetchall()

            print(f"\n  {role.upper()}:")
            for username, email, created_at in samples:
                print(f"    - {username} ({email})")

        # Test 9: Recently created users
        cursor.execute("""
            SELECT role, username, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT 5
        """)
        recent_users = cursor.fetchall()

        print("\n✓ Most recently created users:")
        for role, username, created_at in recent_users:
            print(f"  - {username} ({role}) - {created_at}")

        # Test 10: User account status
        cursor.execute("""
            SELECT
                CASE WHEN ua.password_hash IS NOT NULL THEN 'Active' ELSE 'Inactive' END as status,
                COUNT(*) as count
            FROM users u
            LEFT JOIN user_accounts ua ON u.id = ua.user_id
            GROUP BY status
        """)
        account_status = cursor.fetchall()

        print("\n✓ User account status:")
        for status, count in account_status:
            print(f"  - {status}: {count}")

        print("\n" + "=" * 60)
        print("USER ROLES TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_user_roles()
