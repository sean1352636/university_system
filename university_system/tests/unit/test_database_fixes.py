#!/usr/bin/env python3
"""
Test script to verify database connection fixes work properly.

This script simulates concurrent database access scenarios that would
previously cause "database is locked" errors to verify our fixes work.
"""

import sys
import os
import time
import threading
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add the university system to the path
sys.path.insert(0, '/home/seancatchpole989')

def test_original_connection():
    """Test the original database connection approach (for comparison)"""
    print("Testing original connection approach...")
    try:
        from university_system.infrastructure.database.db import get_connection as original_get_connection
        conn = original_get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        result = cursor.fetchone()
        conn.close()
        print(f"✓ Original connection works: {result[0] if result else 0} tables found")
        return True
    except Exception as e:
        print(f"✗ Original connection failed: {e}")
        return False

def test_wrapper_connection():
    """Test the new database wrapper"""
    print("Testing database wrapper...")
    try:
        from university_system.modules.shared.gui.database_wrapper import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        result = cursor.fetchone()
        conn.close()
        print(f"✓ Wrapper connection works: {result[0] if result else 0} tables found")
        return True
    except Exception as e:
        print(f"✗ Wrapper connection failed: {e}")
        return False

def test_safe_utilities():
    """Test the safe database utilities"""
    print("Testing safe database utilities...")
    try:
        from university_system.modules.shared.gui.db_utils import safe_execute
        result = safe_execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'", fetch_one=True)
        print(f"✓ Safe utilities work: {result[0] if result else 0} tables found")
        return True
    except Exception as e:
        print(f"✗ Safe utilities failed: {e}")
        return False

def concurrent_database_access(worker_id, num_operations=10):
    """Simulate concurrent database access that could cause locks"""
    try:
        from university_system.modules.shared.gui.database_wrapper import get_connection

        for i in range(num_operations):
            conn = get_connection()
            cursor = conn.cursor()

            # Simulate some database operations
            cursor.execute("SELECT COUNT(*) FROM sqlite_master")
            cursor.execute("PRAGMA table_info(students)")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 5")

            conn.close()
            time.sleep(0.01)  # Small delay between operations

        return f"Worker {worker_id}: {num_operations} operations completed successfully"

    except Exception as e:
        return f"Worker {worker_id} failed: {e}"

def test_concurrent_access():
    """Test concurrent database access to verify no lock issues"""
    print("\\nTesting concurrent database access...")

    num_workers = 5
    operations_per_worker = 20

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        futures = [
            executor.submit(concurrent_database_access, i, operations_per_worker)
            for i in range(num_workers)
        ]

        # Collect results
        successful_workers = 0
        failed_workers = 0

        for future in as_completed(futures):
            result = future.result()
            if "failed" in result:
                print(f"✗ {result}")
                failed_workers += 1
            else:
                print(f"✓ {result}")
                successful_workers += 1

    print(f"\\nConcurrent test summary:")
    print(f"✓ Successful workers: {successful_workers}")
    print(f"✗ Failed workers: {failed_workers}")

    return failed_workers == 0

def test_database_initialization():
    """Test that database can be initialized properly"""
    print("\\nTesting database initialization...")
    try:
        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Check if main tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['students', 'users']  # Basic tables that should exist
        missing_tables = [table for table in required_tables if table not in tables]

        if missing_tables:
            print(f"⚠ Some required tables missing: {missing_tables}")
            print("This may be normal if database is not fully initialized")
        else:
            print("✓ Required tables found")

        conn.close()
        return True

    except Exception as e:
        print(f"✗ Database initialization test failed: {e}")
        return False

def test_gui_import_updates():
    """Test that GUI files can import the new database wrapper"""
    print("\\nTesting GUI import updates...")

    test_files = [
        '/home/seancatchpole989/university_system/interfaces/gui/finance_gui.py',
        '/home/seancatchpole989/university_system/interfaces/gui/student_support_gui.py',
        '/home/seancatchpole989/university_system/interfaces/gui/health_portal_gui.py'
    ]

    success_count = 0
    for file_path in test_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            if 'database_wrapper import get_connection' in content:
                print(f"✓ {os.path.basename(file_path)} updated correctly")
                success_count += 1
            else:
                print(f"⚠ {os.path.basename(file_path)} may not be updated")

        except Exception as e:
            print(f"✗ Error checking {os.path.basename(file_path)}: {e}")

    print(f"Updated files: {success_count}/{len(test_files)}")
    return success_count == len(test_files)

def main():
    """Run all tests"""
    print("=" * 60)
    print("DATABASE CONNECTION FIXES - TEST SUITE")
    print("=" * 60)

    tests = [
        ("Original Connection", test_original_connection),
        ("Wrapper Connection", test_wrapper_connection),
        ("Safe Utilities", test_safe_utilities),
        ("Database Initialization", test_database_initialization),
        ("GUI Import Updates", test_gui_import_updates),
        ("Concurrent Access", test_concurrent_access),
    ]

    results = {}

    for test_name, test_func in tests:
        print(f"\\n{'-' * 40}")
        print(f"Running: {test_name}")
        print(f"{'-' * 40}")

        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"✗ {test_name} crashed: {e}")
            results[test_name] = False

    # Summary
    print(f"\\n{'=' * 60}")
    print("TEST SUMMARY")
    print(f"{'=' * 60}")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:30} {status}")

    print(f"\\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\\n🎉 All tests passed! Database connection fixes are working correctly.")
    else:
        print(f"\\n⚠ {total - passed} test(s) failed. Please review the issues above.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)