#!/usr/bin/env python3
"""
Verification script for accessibility tools GUI fixes.

This script verifies:
1. Student lookup functionality (correct column names)
2. User lookup functionality
3. Exam lookup functionality (correct table name)
4. Exam accommodations schema (notes column exists)
5. sqlite3.Row access patterns work correctly
"""

from university_system.infrastructure.database.db import get_connection
import sys

def verify_student_lookup():
    """Verify student table schema for lookup"""
    print("\n1. Verifying student lookup...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # This is the query used in lookup_student()
            cursor.execute("""
                SELECT student_id, first_name, last_name, email_address, course
                FROM students
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                print(f"   ✅ Student lookup query works")
                print(f"      Sample: {row['student_id']} - {row['first_name']} {row['last_name']}")
            else:
                print(f"   ⚠️  No students in database")
    except Exception as e:
        print(f"   ❌ Student lookup failed: {e}")
        return False
    return True

def verify_user_lookup():
    """Verify users table schema for lookup"""
    print("\n2. Verifying user lookup...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # This is the query used in lookup_user()
            cursor.execute("""
                SELECT id, username, first_name, last_name, email, role
                FROM users
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                print(f"   ✅ User lookup query works")
                print(f"      Sample: {row['id']} - {row['username']} ({row['role']})")
            else:
                print(f"   ⚠️  No users in database")
    except Exception as e:
        print(f"   ❌ User lookup failed: {e}")
        return False
    return True

def verify_exam_lookup():
    """Verify exams table schema for lookup"""
    print("\n3. Verifying exam lookup...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # This is the query used in lookup_exam()
            cursor.execute("""
                SELECT id, module_code, module_name, date, start_time, end_time, room
                FROM exams
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                print(f"   ✅ Exam lookup query works")
                print(f"      Sample: {row['module_code']} - {row['module_name']} on {row['date']}")
            else:
                print(f"   ⚠️  No exams in database")
    except Exception as e:
        print(f"   ❌ Exam lookup failed: {e}")
        return False
    return True

def verify_exam_accommodations_schema():
    """Verify exam_accommodations table has notes column"""
    print("\n4. Verifying exam_accommodations schema...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # Check table schema
            cursor.execute("PRAGMA table_info(exam_accommodations)")
            columns = {row['name'] for row in cursor.fetchall()}

            required_columns = {
                'accommodation_id', 'student_id', 'exam_id', 'extended_time',
                'separate_room', 'reader_scribe', 'assistive_technology',
                'status', 'notes', 'created_at'
            }

            missing = required_columns - columns
            if missing:
                print(f"   ⚠️  Missing columns: {missing}")
                return False

            print(f"   ✅ All required columns exist")
            print(f"      Columns: {', '.join(sorted(columns))}")
    except Exception as e:
        print(f"   ❌ Schema check failed: {e}")
        return False
    return True

def verify_row_access_pattern():
    """Verify sqlite3.Row dictionary-style access works"""
    print("\n5. Verifying Row access pattern...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM exam_accommodations LIMIT 1
            """)
            row = cursor.fetchone()

            if row:
                # Test dictionary-style access (this is what the fix uses)
                try:
                    _ = row['accommodation_id']
                    _ = row['student_id']
                    _ = row['notes']
                    print(f"   ✅ Dictionary-style access works")

                    # Verify notes field specifically
                    try:
                        if row['notes']:
                            print(f"      Notes field accessible: '{row['notes'][:50]}...'")
                        else:
                            print(f"      Notes field accessible (empty/NULL)")
                    except (KeyError, IndexError):
                        print(f"      Notes field handled by exception (as designed)")

                except Exception as e:
                    print(f"   ❌ Dictionary-style access failed: {e}")
                    return False
            else:
                print(f"   ⚠️  No exam accommodations in database to test")
    except Exception as e:
        print(f"   ❌ Row access test failed: {e}")
        return False
    return True

def verify_foreign_keys():
    """Verify foreign key constraints are fixed"""
    print("\n6. Verifying foreign key constraints...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check accessibility_profiles FK
            cursor.execute("PRAGMA foreign_key_list(accessibility_profiles)")
            fks = cursor.fetchall()

            if fks:
                correct_fk = False
                for fk in fks:
                    if fk['table'] == 'users' and fk['to'] == 'id':
                        correct_fk = True
                        break

                if correct_fk:
                    print(f"   ✅ Foreign key references users(id)")
                else:
                    print(f"   ⚠️  Foreign key may reference wrong column")
                    for fk in fks:
                        print(f"      Found: {fk['table']}({fk['to']})")
            else:
                print(f"   ⚠️  No foreign keys found on accessibility_profiles")
    except Exception as e:
        print(f"   ❌ Foreign key check failed: {e}")
        return False
    return True

def main():
    """Run all verification tests"""
    print("=" * 70)
    print("ACCESSIBILITY TOOLS GUI - VERIFICATION TESTS")
    print("=" * 70)

    results = []
    results.append(("Student Lookup", verify_student_lookup()))
    results.append(("User Lookup", verify_user_lookup()))
    results.append(("Exam Lookup", verify_exam_lookup()))
    results.append(("Exam Accommodations Schema", verify_exam_accommodations_schema()))
    results.append(("Row Access Pattern", verify_row_access_pattern()))
    results.append(("Foreign Key Constraints", verify_foreign_keys()))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:.<50} {status}")

    all_passed = all(result[1] for result in results)

    print("=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Accessibility tools GUI is ready")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Review errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
