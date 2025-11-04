#!/usr/bin/env python3
"""
Test script for data consistency
Tests data relationships and business logic consistency
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_data_consistency():
    """Test data consistency across tables"""
    print("=" * 60)
    print("DATA CONSISTENCY TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: CS students should not have DS modules
        cursor.execute("""
            SELECT s.student_id, s.course, m.module_code, m.module_type
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            JOIN modules m ON sm.module_code = m.module_code
            WHERE s.course = 'CS' AND m.module_type = 'DS_optional'
        """)
        cs_with_ds_modules = cursor.fetchall()

        if cs_with_ds_modules:
            print(f"\n✗ FAILED: {len(cs_with_ds_modules)} CS students with DS modules:")
            for sid, course, code, mod_type in cs_with_ds_modules[:5]:
                print(f"  - {sid}: {code} ({mod_type})")
        else:
            print("\n✓ No CS students have DS-specific modules")

        # Test 2: DS students should not have CS modules
        cursor.execute("""
            SELECT s.student_id, s.course, m.module_code, m.module_type
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            JOIN modules m ON sm.module_code = m.module_code
            WHERE s.course = 'DS' AND m.module_type = 'CS_optional'
        """)
        ds_with_cs_modules = cursor.fetchall()

        if ds_with_cs_modules:
            print(f"\n✗ FAILED: {len(ds_with_cs_modules)} DS students with CS modules:")
            for sid, course, code, mod_type in ds_with_cs_modules[:5]:
                print(f"  - {sid}: {code} ({mod_type})")
        else:
            print("\n✓ No DS students have CS-specific modules")

        # Test 3: All students should have compulsory modules
        cursor.execute("""
            SELECT s.student_id, s.course,
                   SUM(CASE WHEN m.module_code = 'CIS0001' THEN 1 ELSE 0 END) as has_cis0001,
                   SUM(CASE WHEN m.module_code = 'CIS0002' THEN 1 ELSE 0 END) as has_cis0002
            FROM students s
            LEFT JOIN student_modules sm ON s.student_id = sm.student_id
            LEFT JOIN modules m ON sm.module_code = m.module_code
            GROUP BY s.student_id, s.course
            HAVING has_cis0001 = 0 OR has_cis0002 = 0
        """)
        missing_compulsory = cursor.fetchall()

        if missing_compulsory:
            print(f"\n✗ FAILED: {len(missing_compulsory)} students missing compulsory modules")
        else:
            print("\n✓ All students have compulsory modules")

        # Test 4: Student timetables should match enrolled modules
        cursor.execute("""
            SELECT COUNT(*)
            FROM student_timetables st
            WHERE NOT EXISTS (
                SELECT 1 FROM student_modules sm
                WHERE sm.student_id = st.student_id
                AND sm.module_code = st.module_code
            )
        """)
        timetable_mismatches = cursor.fetchone()[0]

        if timetable_mismatches > 0:
            print(f"\n✗ FAILED: {timetable_mismatches} timetable entries for non-enrolled modules")
        else:
            print("\n✓ All timetable entries match enrolled modules")

        # Test 5: Instructor assignments should match their schedules
        cursor.execute("""
            SELECT COUNT(*)
            FROM instructor_schedules isch
            WHERE NOT EXISTS (
                SELECT 1 FROM instructor_modules im
                WHERE im.instructor_id = isch.instructor_id
                AND im.module_code = isch.module_code
            )
        """)
        schedule_assignment_mismatch = cursor.fetchone()[0]

        if schedule_assignment_mismatch > 0:
            print(f"\n✗ FAILED: {schedule_assignment_mismatch} instructor schedules without module assignments")
        else:
            print("\n✓ All instructor schedules match module assignments")

        # Test 6: Email uniqueness across students
        cursor.execute("""
            SELECT email_address, COUNT(*) as count
            FROM students
            WHERE email_address IS NOT NULL
            GROUP BY email_address
            HAVING count > 1
        """)
        duplicate_emails = cursor.fetchall()

        if duplicate_emails:
            print(f"\n✗ FAILED: {len(duplicate_emails)} duplicate email addresses:")
            for email, count in duplicate_emails[:5]:
                print(f"  - {email}: {count} occurrences")
        else:
            print("\n✓ All student email addresses are unique")

        # Test 7: User-Student consistency
        cursor.execute("""
            SELECT u.username, u.student_id, s.student_id
            FROM users u
            JOIN students s ON u.student_id = s.student_id
            WHERE u.role = 'student'
            AND (u.first_name != s.first_name OR u.last_name != s.last_name)
        """)
        name_mismatches = cursor.fetchall()

        if name_mismatches:
            print(f"\n⚠ Warning: {len(name_mismatches)} name mismatches between users and students")
        else:
            print("\n✓ User names match student records")

        # Test 8: Module capacity check (each module should have reasonable enrollment)
        cursor.execute("""
            SELECT m.module_code, m.module_name, COUNT(sm.student_id) as enrollment
            FROM modules m
            LEFT JOIN student_modules sm ON m.module_code = sm.module_code
            WHERE m.is_active = 1
            GROUP BY m.module_code, m.module_name
        """)
        module_enrollments = cursor.fetchall()

        print("\n✓ Module enrollment balance:")
        min_enrollment = min(e[2] for e in module_enrollments)
        max_enrollment = max(e[2] for e in module_enrollments)
        avg_enrollment = sum(e[2] for e in module_enrollments) / len(module_enrollments)

        print(f"  - Min: {min_enrollment}")
        print(f"  - Max: {max_enrollment}")
        print(f"  - Avg: {avg_enrollment:.1f}")

        if max_enrollment > avg_enrollment * 2:
            print("  ⚠ Warning: Large variance in module enrollments")

        # Test 9: Academic year consistency
        cursor.execute("""
            SELECT DISTINCT academic_year FROM instructor_modules
            UNION
            SELECT DISTINCT academic_year FROM instructor_schedules
            UNION
            SELECT DISTINCT academic_year FROM student_timetables
        """)
        academic_years = [row[0] for row in cursor.fetchall() if row[0]]

        print(f"\n✓ Academic years in use: {academic_years}")

        # Test 10: Gender distribution balance
        cursor.execute("""
            SELECT gender, COUNT(*) * 100.0 / (SELECT COUNT(*) FROM students) as percentage
            FROM students
            GROUP BY gender
        """)
        gender_percentages = cursor.fetchall()

        print("\n✓ Gender distribution:")
        for gender, pct in gender_percentages:
            print(f"  - {gender}: {pct:.1f}%")

        print("\n" + "=" * 60)
        print("DATA CONSISTENCY TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_data_consistency()
