#!/usr/bin/env python3
"""
Test script for search functionality
Tests various search queries and filters
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_search():
    """Test search functionality"""
    print("=" * 60)
    print("SEARCH FUNCTIONALITY TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Search students by name
        print("\n✓ Test 1: Search by name (partial match)")
        cursor.execute("""
            SELECT student_id, first_name, last_name, course
            FROM students
            WHERE first_name LIKE '%John%' OR last_name LIKE '%John%'
            LIMIT 5
        """)
        name_results = cursor.fetchall()

        print(f"  Found {len(name_results)} students:")
        for sid, first, last, course in name_results:
            print(f"  - {sid}: {first} {last} ({course})")

        # Test 2: Search by course
        print("\n✓ Test 2: Search by course")
        for course in ['CS', 'DS']:
            cursor.execute("""
                SELECT COUNT(*) FROM students WHERE course = ?
            """, (course,))
            count = cursor.fetchone()[0]
            print(f"  - {course}: {count} students")

        # Test 3: Search by age range
        print("\n✓ Test 3: Search by age range (18-22)")
        cursor.execute("""
            SELECT student_id, first_name, last_name, age, course
            FROM students
            WHERE age BETWEEN 18 AND 22
            LIMIT 5
        """)
        age_results = cursor.fetchall()

        print(f"  Found {len(age_results)} students:")
        for sid, first, last, age, course in age_results:
            print(f"  - {sid}: {first} {last}, Age {age} ({course})")

        # Test 4: Search by module enrollment
        print("\n✓ Test 4: Students enrolled in CIS0001")
        cursor.execute("""
            SELECT s.student_id, s.first_name, s.last_name, s.course
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code = 'CIS0001'
            LIMIT 5
        """)
        module_students = cursor.fetchall()

        print(f"  Found {len(module_students)} students:")
        for sid, first, last, course in module_students:
            print(f"  - {sid}: {first} {last} ({course})")

        # Test 5: Search instructors by specialization
        print("\n✓ Test 5: Search instructors by specialization")
        cursor.execute("""
            SELECT DISTINCT specialization FROM instructors WHERE is_active = 1
        """)
        specializations = cursor.fetchall()

        for (spec,) in specializations[:3]:
            cursor.execute("""
                SELECT first_name, last_name
                FROM instructors
                WHERE specialization = ? AND is_active = 1
            """, (spec,))
            instructors = cursor.fetchall()
            print(f"  {spec}:")
            for first, last in instructors:
                print(f"    - {first} {last}")

        # Test 6: Complex multi-criteria search
        print("\n✓ Test 6: Complex search (CS students, age 20-25, with CIS2001)")
        cursor.execute("""
            SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.age
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE s.course = 'CS'
            AND s.age BETWEEN 20 AND 25
            AND sm.module_code = 'CIS2001'
            LIMIT 5
        """)
        complex_results = cursor.fetchall()

        print(f"  Found {len(complex_results)} students:")
        for sid, first, last, age in complex_results:
            print(f"  - {sid}: {first} {last}, Age {age}")

        # Test 7: Search by email domain
        print("\n✓ Test 7: Search by email domain")
        cursor.execute("""
            SELECT COUNT(*),
                   SUBSTR(email_address, INSTR(email_address, '@') + 1) as domain
            FROM students
            WHERE email_address IS NOT NULL
            GROUP BY domain
        """)
        domains = cursor.fetchall()

        print("  Email domains:")
        for count, domain in domains:
            print(f"  - {domain}: {count} students")

        # Test 8: Search students without timetables
        print("\n✓ Test 8: Students without timetables")
        cursor.execute("""
            SELECT s.student_id, s.first_name, s.last_name
            FROM students s
            WHERE NOT EXISTS (
                SELECT 1 FROM student_timetables st
                WHERE st.student_id = s.student_id
            )
            LIMIT 5
        """)
        no_timetable = cursor.fetchall()

        if no_timetable:
            print(f"  Found {len(no_timetable)} students without timetables:")
            for sid, first, last in no_timetable:
                print(f"  - {sid}: {first} {last}")
        else:
            print("  All students have timetables")

        # Test 9: Search by gender
        print("\n✓ Test 9: Search by gender distribution")
        cursor.execute("""
            SELECT gender, course, COUNT(*) as count
            FROM students
            GROUP BY gender, course
            ORDER BY course, gender
        """)
        gender_dist = cursor.fetchall()

        for gender, course, count in gender_dist:
            print(f"  {course} - {gender}: {count}")

        # Test 10: Full-text search simulation
        print("\n✓ Test 10: Full-text search simulation")
        search_term = "software"
        cursor.execute("""
            SELECT module_code, module_name, module_type
            FROM modules
            WHERE LOWER(module_name) LIKE ?
            OR LOWER(module_type) LIKE ?
        """, (f'%{search_term}%', f'%{search_term}%'))
        search_results = cursor.fetchall()

        print(f"  Search for '{search_term}':")
        if search_results:
            for code, name, mod_type in search_results:
                print(f"  - {code}: {name} ({mod_type})")
        else:
            print("  No results found")

        print("\n" + "=" * 60)
        print("SEARCH FUNCTIONALITY TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_search()
