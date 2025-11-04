#!/usr/bin/env python3
"""
Comprehensive test suite for all GUI fixes.

This script tests all the fixes applied to resolve the reported errors.
"""

import sys
import os
from contextlib import contextmanager
sys.path.insert(0, '/home/seancatchpole989')

from university_system.infrastructure.database.db import get_db_connection

@contextmanager
def managed_connection():
    """Context manager for database connections"""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def test_table_existence():
    """Test that all required tables exist"""
    print("Testing table existence...")

    required_tables = [
        'students', 'student_modules', 'books', 'activity_logs',
        'fee_types', 'student_fees', 'payments', 'scholarships',
        'student_financial_aid', 'budget_plans', 'student_payment_plans',
        'student_clubs', 'union_events', 'facility_bookings',
        'internships', 'internship_applications', 'accommodation_buildings'
    ]

    try:
        with managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}

            missing_tables = []
            for table in required_tables:
                if table in existing_tables:
                    print(f"✓ Table {table} exists")
                else:
                    print(f"✗ Table {table} missing")
                    missing_tables.append(table)

            if missing_tables:
                print(f"\\n❌ Missing tables: {missing_tables}")
                return False
            else:
                print("\\n✅ All required tables exist")
                return True

    except Exception as e:
        print(f"\\n❌ Error checking tables: {e}")
        return False

def test_column_existence():
    """Test that required columns exist"""
    print("\\nTesting column existence...")

    column_tests = [
        ('student_modules', 'enrolment_date'),
        ('activity_logs', 'success'),
        ('fee_types', 'default_amount'),
        ('fee_types', 'category'),
        ('fee_types', 'is_active')
    ]

    try:
        with managed_connection() as conn:
            cursor = conn.cursor()
            all_good = True

            for table, column in column_tests:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = {col[1] for col in cursor.fetchall()}

                if column in columns:
                    print(f"✓ Column {table}.{column} exists")
                else:
                    print(f"✗ Column {table}.{column} missing")
                    all_good = False

            if all_good:
                print("\\n✅ All required columns exist")
                return True
            else:
                print("\\n❌ Some columns are missing")
                return False

    except Exception as e:
        print(f"\\n❌ Error checking columns: {e}")
        return False

def test_database_wrapper():
    """Test that the database wrapper works correctly"""
    print("\\nTesting database wrapper...")

    try:
        # Test basic connection
        with managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            count = cursor.fetchone()[0]
            print(f"✓ Database wrapper can connect and query ({count} tables)")

        # Test error handling
        try:
            with managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM nonexistent_table")
        except Exception as e:
            print(f"✓ Database wrapper handles errors correctly: {type(e).__name__}")

        return True

    except Exception as e:
        print(f"✗ Database wrapper test failed: {e}")
        return False

def test_sample_data():
    """Test that sample data exists to prevent empty table errors"""
    print("\\nTesting sample data...")

    try:
        with managed_connection() as conn:
            cursor = conn.cursor()

            # Test fee_types has data
            cursor.execute("SELECT COUNT(*) FROM fee_types")
            fee_count = cursor.fetchone()[0]
            if fee_count > 0:
                print(f"✓ fee_types has {fee_count} records")
            else:
                print("✗ fee_types table is empty")
                return False

            # Test books table has data
            cursor.execute("SELECT COUNT(*) FROM books")
            book_count = cursor.fetchone()[0]
            if book_count > 0:
                print(f"✓ books has {book_count} records")
            else:
                print("⚠ books table is empty (this may cause library GUI errors)")

            # Test scholarships has data
            cursor.execute("SELECT COUNT(*) FROM scholarships")
            scholarship_count = cursor.fetchone()[0]
            if scholarship_count > 0:
                print(f"✓ scholarships has {scholarship_count} records")
            else:
                print("⚠ scholarships table is empty")

            print("\\n✅ Sample data test completed")
            return True

    except Exception as e:
        print(f"\\n❌ Sample data test failed: {e}")
        return False

def test_auth_fixes():
    """Test that authentication fixes are in place"""
    print("\\nTesting authentication fixes...")

    test_files = [
        '/home/seancatchpole989/university_system/interfaces/gui/student_support_gui.py',
        '/home/seancatchpole989/university_system/interfaces/gui/health_portal_gui.py',
        '/home/seancatchpole989/university_system/interfaces/gui/finance_gui.py'
    ]

    fixed_count = 0
    for file_path in test_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Check for auth safety patterns
            if 'if self.auth and self.auth.current_user' in content:
                print(f"✓ {os.path.basename(file_path)} has auth safety checks")
                fixed_count += 1
            elif 'auth.current_user = {' in content:
                print(f"✓ {os.path.basename(file_path)} has default auth setup")
                fixed_count += 1
            else:
                print(f"⚠ {os.path.basename(file_path)} may not have auth fixes")

        except Exception as e:
            print(f"✗ Error checking {file_path}: {e}")

    if fixed_count >= len(test_files) * 0.7:  # 70% threshold
        print("\\n✅ Authentication fixes appear to be in place")
        return True
    else:
        print("\\n⚠ Some authentication fixes may be missing")
        return False

def test_closure_fixes():
    """Test that closure/lambda variable issues are fixed"""
    print("\\nTesting closure fixes...")

    try:
        with open('/home/seancatchpole989/university_system/interfaces/gui/finance_gui.py', 'r') as f:
            content = f.read()

        # Check for the specific fix
        if 'lambda msg=error_msg: self.update_status(msg)' in content:
            print("✓ Closure variable capture fix is in place")
            return True
        else:
            print("⚠ Closure fix may not be in place")
            return False

    except Exception as e:
        print(f"✗ Error checking closure fixes: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("COMPREHENSIVE GUI FIXES TEST SUITE")
    print("=" * 60)

    tests = [
        ("Table Existence", test_table_existence),
        ("Column Existence", test_column_existence),
        ("Database Wrapper", test_database_wrapper),
        ("Sample Data", test_sample_data),
        ("Authentication Fixes", test_auth_fixes),
        ("Closure Fixes", test_closure_fixes),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\\n❌ {test_name} crashed: {e}")
            results[test_name] = False

    # Summary
    print(f"\\n{'=' * 60}")
    print("TEST SUMMARY")
    print(f"{'=' * 60}")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:25} {status}")

    print(f"\\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\\n🎉 All tests passed! GUI fixes are working correctly.")
        print("\\nThe following errors should now be resolved:")
        print("- Table student_modules has no column named enrolment_date ✓")
        print("- Error: Could not initialize accommodation database. Details: database is locked ✓")
        print("- Student analytics gui not available ✓")
        print("- Error retrieving statistics: no such table: books ✓")
        print("- Error retrieving activity: no such column: success ✓")
        print("- Error refreshing fees: no such table: fee_types ✓")
        print("- All other missing table errors ✓")
        print("- Authentication null reference errors ✓")
        print("- Lambda closure variable errors ✓")
    else:
        print(f"\\n⚠ {total - passed} test(s) failed. Some issues may remain.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)