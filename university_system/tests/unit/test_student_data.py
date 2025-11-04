#!/usr/bin/env python3
"""
Test script for student data validation
Tests student records, demographics, and data quality
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from datetime import datetime
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_student_data():
    """Test student data validation"""
    print("=" * 60)
    print("STUDENT DATA VALIDATION TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Basic student count
        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]
        print(f"\n✓ Total students: {total_students}")

        # Test 2: Students by status
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM students
            GROUP BY status
        """)
        status_counts = cursor.fetchall()

        print("\n✓ Students by status:")
        for status, count in status_counts:
            status_name = status if status else "NULL/Unknown"
            print(f"  - {status_name}: {count}")

        # Test 3: Gender distribution
        cursor.execute("""
            SELECT gender, COUNT(*)
            FROM students
            GROUP BY gender
        """)
        gender_dist = cursor.fetchall()

        print("\n✓ Gender distribution:")
        for gender, count in gender_dist:
            print(f"  - {gender}: {count}")

        # Test 4: Age distribution
        cursor.execute("""
            SELECT
                CASE
                    WHEN age < 18 THEN 'Under 18'
                    WHEN age BETWEEN 18 AND 21 THEN '18-21'
                    WHEN age BETWEEN 22 AND 25 THEN '22-25'
                    WHEN age BETWEEN 26 AND 30 THEN '26-30'
                    ELSE 'Over 30'
                END as age_group,
                COUNT(*) as count
            FROM students
            WHERE age IS NOT NULL
            GROUP BY age_group
        """)
        age_distribution = cursor.fetchall()

        print("\n✓ Age distribution:")
        for age_group, count in age_distribution:
            print(f"  - {age_group}: {count}")

        # Test 5: Check for invalid ages
        cursor.execute("""
            SELECT student_id, age
            FROM students
            WHERE age < 16 OR age > 80 OR age IS NULL
        """)
        invalid_ages = cursor.fetchall()

        if invalid_ages:
            print(f"\n⚠ Warning: {len(invalid_ages)} students with invalid/missing ages:")
            for student_id, age in invalid_ages[:5]:
                print(f"  - {student_id}: {age}")
        else:
            print("\n✓ All students have valid ages (16-80)")

        # Test 6: Email addresses
        cursor.execute("""
            SELECT COUNT(*) FROM students WHERE email_address IS NULL OR email_address = ''
        """)
        missing_emails = cursor.fetchone()[0]

        if missing_emails > 0:
            print(f"\n⚠ Warning: {missing_emails} students without email addresses")
        else:
            print("\n✓ All students have email addresses")

        # Test 7: Name validation
        cursor.execute("""
            SELECT COUNT(*) FROM students
            WHERE first_name IS NULL OR first_name = ''
               OR last_name IS NULL OR last_name = ''
        """)
        missing_names = cursor.fetchone()[0]

        if missing_names > 0:
            print(f"\n✗ FAILED: {missing_names} students with missing names")
        else:
            print("\n✓ All students have first and last names")

        # Test 8: Title distribution
        cursor.execute("""
            SELECT title, COUNT(*)
            FROM students
            GROUP BY title
        """)
        title_dist = cursor.fetchall()

        print("\n✓ Title distribution:")
        for title, count in title_dist:
            title_name = title if title else "NULL"
            print(f"  - {title_name}: {count}")

        # Test 9: Course distribution
        cursor.execute("""
            SELECT course, COUNT(*)
            FROM students
            GROUP BY course
        """)
        course_dist = cursor.fetchall()

        print("\n✓ Course enrollment:")
        for course, count in course_dist:
            print(f"  - {course}: {count} students")

        # Test 10: Sample student records
        cursor.execute("""
            SELECT student_id, title, first_name, last_name, gender, age, course
            FROM students
            LIMIT 5
        """)
        sample_students = cursor.fetchall()

        print("\n✓ Sample student records:")
        for sid, title, first, last, gender, age, course in sample_students:
            print(f"  - {sid}: {title} {first} {last}")
            print(f"    Gender: {gender} | Age: {age} | Course: {course}")

        # Test 11: Date of birth validation
        cursor.execute("""
            SELECT student_id, dob, age
            FROM students
            WHERE dob IS NOT NULL
            LIMIT 3
        """)
        dob_samples = cursor.fetchall()

        if dob_samples:
            print("\n✓ DOB validation (sample):")
            current_year = datetime.now().year
            for sid, dob, age in dob_samples:
                try:
                    dob_date = datetime.strptime(dob, "%Y-%m-%d")
                    calculated_age = current_year - dob_date.year
                    match = "✓" if abs(calculated_age - age) <= 1 else "✗"
                    print(f"  {match} {sid}: DOB {dob} -> Age {age} (calc: {calculated_age})")
                except:
                    print(f"  ✗ {sid}: Invalid DOB format")

        # Test 12: Enrollment dates
        cursor.execute("""
            SELECT COUNT(*) FROM students WHERE enrollment_date IS NULL
        """)
        missing_enrollment = cursor.fetchone()[0]

        if missing_enrollment > 0:
            print(f"\n⚠ Warning: {missing_enrollment} students without enrollment dates")
        else:
            print("\n✓ All students have enrollment dates")

        print("\n" + "=" * 60)
        print("STUDENT DATA TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_student_data()
