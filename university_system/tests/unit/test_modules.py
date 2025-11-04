#!/usr/bin/env python3
"""
Test script for module management
Tests module data, types, and assignments
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_modules():
    """Test module management and data"""
    print("=" * 60)
    print("MODULE MANAGEMENT TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Count total modules
        cursor.execute("SELECT COUNT(*) FROM modules WHERE is_active = 1")
        total_modules = cursor.fetchone()[0]
        print(f"\n✓ Active modules: {total_modules}")

        # Expected modules from modules.py
        expected_modules = {
            "CIS0001", "CIS0002",  # Compulsory
            "CIS1001", "CIS1002", "CIS1003", "CIS1004",  # Optional
            "CIS2001", "CIS2002", "CIS2003", "CIS2004",  # CS-specific
            "CIS3001", "CIS3002", "CIS3003", "CIS3004",  # DS-specific
        }

        if total_modules == len(expected_modules):
            print(f"  ✓ Matches expected count: {len(expected_modules)}")
        else:
            print(f"  ⚠ Expected {len(expected_modules)} modules, found {total_modules}")

        # Test 2: Modules by type
        cursor.execute("""
            SELECT module_type, COUNT(*)
            FROM modules
            WHERE is_active = 1
            GROUP BY module_type
        """)
        module_types = cursor.fetchall()

        print("\n✓ Modules by type:")
        for mod_type, count in module_types:
            print(f"  - {mod_type}: {count}")

        # Test 3: Check all expected modules exist
        cursor.execute("SELECT module_code FROM modules WHERE is_active = 1")
        actual_modules = {row[0] for row in cursor.fetchall()}

        missing = expected_modules - actual_modules
        extra = actual_modules - expected_modules

        if missing:
            print(f"\n✗ FAILED: Missing modules: {missing}")
        else:
            print("\n✓ All expected modules present")

        if extra:
            print(f"\n⚠ Warning: Extra modules found: {extra}")

        # Test 4: Module enrollment statistics
        cursor.execute("""
            SELECT m.module_code, m.module_name, m.module_type,
                   COUNT(sm.student_id) as student_count
            FROM modules m
            LEFT JOIN student_modules sm ON m.module_code = sm.module_code
            WHERE m.is_active = 1
            GROUP BY m.module_code, m.module_name, m.module_type
            ORDER BY student_count DESC
        """)
        enrollment_stats = cursor.fetchall()

        print("\n✓ Module enrollment statistics:")
        for code, name, mod_type, count in enrollment_stats:
            print(f"  - {code} ({mod_type}): {count} students")

        # Test 5: Modules without students
        modules_without_students = [
            (code, name, mod_type)
            for code, name, mod_type, count in enrollment_stats
            if count == 0
        ]

        if modules_without_students:
            print(f"\n⚠ Warning: {len(modules_without_students)} modules with no students:")
            for code, name, mod_type in modules_without_students:
                print(f"  - {code}: {name}")
        else:
            print("\n✓ All modules have enrolled students")

        # Test 6: Modules by department
        cursor.execute("""
            SELECT department, COUNT(*)
            FROM modules
            WHERE is_active = 1
            GROUP BY department
        """)
        dept_distribution = cursor.fetchall()

        print("\n✓ Modules by department:")
        for dept, count in dept_distribution:
            print(f"  - {dept}: {count}")

        # Test 7: Module details
        cursor.execute("""
            SELECT module_code, module_name, module_type, department, credits
            FROM modules
            WHERE is_active = 1
            ORDER BY module_code
        """)
        all_modules = cursor.fetchall()

        print("\n✓ Complete module list:")
        for code, name, mod_type, dept, credits in all_modules:
            print(f"  - {code}: {name}")
            print(f"    Type: {mod_type} | Dept: {dept} | Credits: {credits}")

        # Test 8: Check module credits
        cursor.execute("""
            SELECT DISTINCT credits FROM modules WHERE is_active = 1
        """)
        credit_values = [row[0] for row in cursor.fetchall()]

        print(f"\n✓ Module credit values: {credit_values}")

        if all(c == 15 for c in credit_values if c):
            print("  ✓ All modules have 15 credits")
        else:
            print("  ⚠ Warning: Modules have varying credit values")

        print("\n" + "=" * 60)
        print("MODULE TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_modules()
