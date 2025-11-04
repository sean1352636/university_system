#!/usr/bin/env python3
"""
Test script for course requirements validation
Tests if students meet course requirements
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_course_requirements():
    """Test course requirements compliance"""
    print("=" * 60)
    print("COURSE REQUIREMENTS VALIDATION TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Define course requirements
        REQUIREMENTS = {
            'compulsory': ['CIS0001', 'CIS0002'],
            'min_optional': 2,
            'min_course_specific': 2,
            'total_modules': 6
        }

        # Test 1: Check total module count
        print("\n✓ Test 1: Total module count per student")
        cursor.execute("""
            SELECT s.student_id, s.course, COUNT(sm.module_code) as module_count
            FROM students s
            LEFT JOIN student_modules sm ON s.student_id = sm.student_id
            GROUP BY s.student_id, s.course
        """)
        module_counts = cursor.fetchall()

        incorrect_counts = [(sid, course, count) for sid, course, count in module_counts
                           if count != REQUIREMENTS['total_modules']]

        if incorrect_counts:
            print(f"  ✗ FAILED: {len(incorrect_counts)} students with incorrect module count:")
            for sid, course, count in incorrect_counts[:5]:
                print(f"    - {sid} ({course}): {count} modules (expected {REQUIREMENTS['total_modules']})")
        else:
            print(f"  ✓ All students have exactly {REQUIREMENTS['total_modules']} modules")

        # Test 2: Compulsory modules compliance
        print("\n✓ Test 2: Compulsory modules compliance")
        for req_module in REQUIREMENTS['compulsory']:
            cursor.execute("""
                SELECT COUNT(*) FROM students s
                WHERE NOT EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id = s.student_id AND sm.module_code = ?
                )
            """, (req_module,))
            missing_count = cursor.fetchone()[0]

            if missing_count > 0:
                print(f"  ✗ {req_module}: {missing_count} students missing this module")
            else:
                print(f"  ✓ {req_module}: All students enrolled")

        # Test 3: CS students with correct CS modules
        print("\n✓ Test 3: CS students have CS-specific modules")
        cursor.execute("""
            SELECT s.student_id, COUNT(CASE WHEN m.module_type = 'CS_optional' THEN 1 END) as cs_modules
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            JOIN modules m ON sm.module_code = m.module_code
            WHERE s.course = 'CS'
            GROUP BY s.student_id
            HAVING cs_modules < ?
        """, (REQUIREMENTS['min_course_specific'],))
        cs_non_compliant = cursor.fetchall()

        if cs_non_compliant:
            print(f"  ✗ FAILED: {len(cs_non_compliant)} CS students without enough CS modules:")
            for sid, cs_count in cs_non_compliant[:5]:
                print(f"    - {sid}: Only {cs_count} CS modules (need {REQUIREMENTS['min_course_specific']})")
        else:
            print(f"  ✓ All CS students have at least {REQUIREMENTS['min_course_specific']} CS-specific modules")

        # Test 4: DS students with correct DS modules
        print("\n✓ Test 4: DS students have DS-specific modules")
        cursor.execute("""
            SELECT s.student_id, COUNT(CASE WHEN m.module_type = 'DS_optional' THEN 1 END) as ds_modules
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            JOIN modules m ON sm.module_code = m.module_code
            WHERE s.course = 'DS'
            GROUP BY s.student_id
            HAVING ds_modules < ?
        """, (REQUIREMENTS['min_course_specific'],))
        ds_non_compliant = cursor.fetchall()

        if ds_non_compliant:
            print(f"  ✗ FAILED: {len(ds_non_compliant)} DS students without enough DS modules:")
            for sid, ds_count in ds_non_compliant[:5]:
                print(f"    - {sid}: Only {ds_count} DS modules (need {REQUIREMENTS['min_course_specific']})")
        else:
            print(f"  ✓ All DS students have at least {REQUIREMENTS['min_course_specific']} DS-specific modules")

        # Test 5: Optional modules count
        print("\n✓ Test 5: General optional modules")
        cursor.execute("""
            SELECT s.student_id, s.course,
                   COUNT(CASE WHEN m.module_type = 'optional' THEN 1 END) as optional_count
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            JOIN modules m ON sm.module_code = m.module_code
            GROUP BY s.student_id, s.course
            HAVING optional_count < ?
        """, (REQUIREMENTS['min_optional'],))
        insufficient_optional = cursor.fetchall()

        if insufficient_optional:
            print(f"  ✗ FAILED: {len(insufficient_optional)} students with insufficient optional modules:")
            for sid, course, opt_count in insufficient_optional[:5]:
                print(f"    - {sid} ({course}): Only {opt_count} optional (need {REQUIREMENTS['min_optional']})")
        else:
            print(f"  ✓ All students have at least {REQUIREMENTS['min_optional']} general optional modules")

        # Test 6: Module breakdown summary
        print("\n✓ Test 6: Module breakdown by student (sample)")
        cursor.execute("""
            SELECT s.student_id, s.course,
                   SUM(CASE WHEN m.module_type = 'compulsory' THEN 1 ELSE 0 END) as compulsory,
                   SUM(CASE WHEN m.module_type = 'optional' THEN 1 ELSE 0 END) as optional,
                   SUM(CASE WHEN m.module_type = 'CS_optional' THEN 1 ELSE 0 END) as cs_specific,
                   SUM(CASE WHEN m.module_type = 'DS_optional' THEN 1 ELSE 0 END) as ds_specific
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            JOIN modules m ON sm.module_code = m.module_code
            GROUP BY s.student_id, s.course
            LIMIT 5
        """)
        breakdowns = cursor.fetchall()

        for sid, course, comp, opt, cs, ds in breakdowns:
            print(f"  {sid} ({course}):")
            print(f"    Compulsory: {comp} | Optional: {opt} | CS: {cs} | DS: {ds}")

        # Test 7: Credits calculation (if applicable)
        print("\n✓ Test 7: Total credits per student")
        cursor.execute("""
            SELECT s.student_id, SUM(COALESCE(m.credits, 15)) as total_credits
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            JOIN modules m ON sm.module_code = m.module_code
            GROUP BY s.student_id
        """)
        credits = cursor.fetchall()

        expected_credits = REQUIREMENTS['total_modules'] * 15  # Assuming 15 credits per module
        incorrect_credits = [(sid, cred) for sid, cred in credits if cred != expected_credits]

        if incorrect_credits:
            print(f"  ⚠ {len(incorrect_credits)} students with unexpected credit totals:")
            for sid, cred in incorrect_credits[:5]:
                print(f"    - {sid}: {cred} credits (expected {expected_credits})")
        else:
            print(f"  ✓ All students have correct credit total ({expected_credits} credits)")

        # Test 8: Course compliance summary
        print("\n✓ Test 8: Overall course compliance summary")
        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT s.student_id) FROM students s WHERE EXISTS (SELECT 1 FROM student_modules sm WHERE sm.student_id = s.student_id AND sm.module_code = 'CIS0001') AND EXISTS (SELECT 1 FROM student_modules sm WHERE sm.student_id = s.student_id AND sm.module_code = 'CIS0002')")
        compliant_compulsory = cursor.fetchone()[0]

        compliance_rate = (compliant_compulsory / total_students) * 100

        print(f"  Total students: {total_students}")
        print(f"  Compulsory compliance: {compliant_compulsory} ({compliance_rate:.1f}%)")

        if compliance_rate == 100:
            print("  ✓ 100% compliance with compulsory modules")
        else:
            print(f"  ✗ Only {compliance_rate:.1f}% compliance")

        print("\n" + "=" * 60)
        print("COURSE REQUIREMENTS TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_course_requirements()
