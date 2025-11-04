#!/usr/bin/env python3
"""
Test script for database integrity
Tests foreign keys, constraints, and data consistency
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_database_integrity():
    """Test database integrity and constraints"""
    print("=" * 60)
    print("DATABASE INTEGRITY TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Foreign key constraints enabled
        cursor.execute("PRAGMA foreign_keys")
        fk_status = cursor.fetchone()[0]

        if fk_status:
            print("\n✓ Foreign key constraints: ENABLED")
        else:
            print("\n✗ WARNING: Foreign key constraints: DISABLED")

        # Test 2: Check orphaned student_modules (modules assigned to non-existent students)
        cursor.execute("""
            SELECT sm.student_id, sm.module_code
            FROM student_modules sm
            WHERE NOT EXISTS (
                SELECT 1 FROM students s WHERE s.student_id = sm.student_id
            )
        """)
        orphaned_student_modules = cursor.fetchall()

        if orphaned_student_modules:
            print(f"\n✗ FAILED: {len(orphaned_student_modules)} orphaned student_modules entries")
        else:
            print("\n✓ No orphaned student_modules entries")

        # Test 3: Check orphaned student_modules (non-existent modules)
        cursor.execute("""
            SELECT sm.student_id, sm.module_code
            FROM student_modules sm
            WHERE NOT EXISTS (
                SELECT 1 FROM modules m WHERE m.module_code = sm.module_code
            )
        """)
        invalid_modules = cursor.fetchall()

        if invalid_modules:
            print(f"\n✗ FAILED: {len(invalid_modules)} student_modules with invalid module codes")
        else:
            print("\n✓ No invalid module codes in student_modules")

        # Test 4: Check users without student references
        cursor.execute("""
            SELECT u.username, u.role
            FROM users u
            WHERE u.role = 'student' AND u.student_id IS NULL
        """)
        students_without_id = cursor.fetchall()

        if students_without_id:
            print(f"\n✗ FAILED: {len(students_without_id)} student users without student_id")
        else:
            print("\n✓ All student users have valid student_id")

        # Test 5: Check user_accounts without users
        cursor.execute("""
            SELECT ua.username
            FROM user_accounts ua
            WHERE NOT EXISTS (
                SELECT 1 FROM users u WHERE u.id = ua.user_id
            )
        """)
        orphaned_accounts = cursor.fetchall()

        if orphaned_accounts:
            print(f"\n✗ FAILED: {len(orphaned_accounts)} orphaned user_accounts")
        else:
            print("\n✓ No orphaned user_accounts")

        # Test 6: Check instructor_modules integrity
        cursor.execute("""
            SELECT COUNT(*) FROM instructor_modules im
            WHERE NOT EXISTS (
                SELECT 1 FROM instructors i WHERE i.id = im.instructor_id
            )
        """)
        orphaned_instructor_modules = cursor.fetchone()[0]

        if orphaned_instructor_modules > 0:
            print(f"\n✗ FAILED: {orphaned_instructor_modules} orphaned instructor_modules")
        else:
            print("\n✓ No orphaned instructor_modules")

        # Test 7: Check duplicate student IDs
        cursor.execute("""
            SELECT student_id, COUNT(*) as count
            FROM students
            GROUP BY student_id
            HAVING count > 1
        """)
        duplicate_students = cursor.fetchall()

        if duplicate_students:
            print(f"\n✗ FAILED: {len(duplicate_students)} duplicate student IDs")
        else:
            print("\n✓ No duplicate student IDs")

        # Test 8: Check NULL values in critical fields
        critical_checks = [
            ("students", "student_id"),
            ("students", "first_name"),
            ("students", "last_name"),
            ("students", "course"),
            ("modules", "module_code"),
            ("modules", "module_name"),
            ("users", "username"),
            ("instructors", "first_name"),
            ("instructors", "last_name"),
        ]

        print("\n✓ Checking NULL values in critical fields:")
        all_clean = True
        for table, field in critical_checks:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {field} IS NULL")
            null_count = cursor.fetchone()[0]
            if null_count > 0:
                print(f"  ✗ {table}.{field}: {null_count} NULL values")
                all_clean = False

        if all_clean:
            print("  ✓ No NULL values in critical fields")

        # Test 9: Database file size
        db_size = os.path.getsize(DEFAULT_DB_PATH)
        db_size_mb = db_size / (1024 * 1024)
        print(f"\n✓ Database size: {db_size_mb:.2f} MB")

        # Test 10: Table counts
        important_tables = [
            'students', 'modules', 'student_modules', 'instructors',
            'instructor_modules', 'users', 'user_accounts',
            'student_timetables', 'instructor_schedules'
        ]

        print("\n✓ Table row counts:")
        for table in important_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  - {table}: {count}")
            except:
                print(f"  - {table}: (table not found)")

        print("\n" + "=" * 60)
        print("DATABASE INTEGRITY TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_database_integrity()
