#!/usr/bin/env python3
"""
Test script for student enrollment process
Tests student creation, module assignment, and enrollment validation
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_student_enrollment():
    """Test student enrollment and module assignment"""
    print("=" * 60)
    print("STUDENT ENROLLMENT TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Count total students
        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]
        print(f"\n✓ Total students in system: {total_students}")

        # Test 2: Count students by course
        cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course")
        course_counts = cursor.fetchall()
        print("\n✓ Students by course:")
        for course, count in course_counts:
            print(f"  - {course}: {count} students")

        # Test 3: Check students have exactly 6 modules
        cursor.execute("""
            SELECT s.student_id, COUNT(sm.module_code) as module_count
            FROM students s
            LEFT JOIN student_modules sm ON s.student_id = sm.student_id
            GROUP BY s.student_id
            HAVING module_count != 6
        """)
        invalid_modules = cursor.fetchall()

        if invalid_modules:
            print(f"\n✗ FAILED: {len(invalid_modules)} students don't have exactly 6 modules:")
            for student_id, count in invalid_modules[:5]:
                print(f"  - {student_id}: {count} modules")
        else:
            print("\n✓ All students have exactly 6 modules")

        # Test 4: Verify compulsory modules
        cursor.execute("""
            SELECT s.student_id
            FROM students s
            WHERE NOT EXISTS (
                SELECT 1 FROM student_modules sm
                WHERE sm.student_id = s.student_id AND sm.module_code = 'CIS0001'
            )
            OR NOT EXISTS (
                SELECT 1 FROM student_modules sm
                WHERE sm.student_id = s.student_id AND sm.module_code = 'CIS0002'
            )
        """)
        missing_compulsory = cursor.fetchall()

        if missing_compulsory:
            print(f"\n✗ FAILED: {len(missing_compulsory)} students missing compulsory modules")
        else:
            print("\n✓ All students have both compulsory modules (CIS0001, CIS0002)")

        # Test 5: Check enrollment status
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM student_modules
            GROUP BY status
        """)
        status_counts = cursor.fetchall()
        print("\n✓ Module enrollment status:")
        for status, count in status_counts:
            print(f"  - {status}: {count}")

        # Test 6: Sample student module breakdown
        cursor.execute("""
            SELECT s.student_id, s.course, m.module_code, m.module_type
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            JOIN modules m ON sm.module_code = m.module_code
            WHERE s.student_id = (SELECT student_id FROM students LIMIT 1)
            ORDER BY m.module_type
        """)
        sample_modules = cursor.fetchall()

        if sample_modules:
            student_id = sample_modules[0][0]
            course = sample_modules[0][1]
            print(f"\n✓ Sample student ({student_id} - {course}) modules:")
            for _, _, code, mod_type in sample_modules:
                print(f"  - {code} ({mod_type})")

        print("\n" + "=" * 60)
        print("ENROLLMENT TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_student_enrollment()
