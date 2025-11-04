#!/usr/bin/env python3
"""
Test script for email validation
Tests email formats and distribution
"""

import sys
import os
import re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def is_valid_email(email):
    """Basic email validation"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def test_email_validation():
    """Test email validation and formats"""
    print("=" * 60)
    print("EMAIL VALIDATION TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Student emails
        print("\n✓ Test 1: Student email validation")
        cursor.execute("SELECT student_id, email_address FROM students")
        student_emails = cursor.fetchall()

        valid_count = 0
        invalid_emails = []

        for student_id, email in student_emails:
            if is_valid_email(email):
                valid_count += 1
            else:
                invalid_emails.append((student_id, email))

        print(f"  Valid emails: {valid_count}/{len(student_emails)}")

        if invalid_emails:
            print(f"\n  ✗ Invalid email formats found: {len(invalid_emails)}")
            for sid, email in invalid_emails[:5]:
                print(f"    - {sid}: {email}")
        else:
            print("  ✓ All student emails are valid")

        # Test 2: User emails
        print("\n✓ Test 2: User email validation")
        cursor.execute("SELECT username, email FROM users")
        user_emails = cursor.fetchall()

        valid_user_emails = 0
        invalid_user_emails = []

        for username, email in user_emails:
            if is_valid_email(email):
                valid_user_emails += 1
            else:
                invalid_user_emails.append((username, email))

        print(f"  Valid emails: {valid_user_emails}/{len(user_emails)}")

        if invalid_user_emails:
            print(f"\n  ✗ Invalid email formats found: {len(invalid_user_emails)}")
            for username, email in invalid_user_emails[:5]:
                print(f"    - {username}: {email}")
        else:
            print("  ✓ All user emails are valid")

        # Test 3: Email domain distribution
        print("\n✓ Test 3: Email domain distribution")
        cursor.execute("""
            SELECT
                SUBSTR(email_address, INSTR(email_address, '@') + 1) as domain,
                COUNT(*) as count
            FROM students
            WHERE email_address IS NOT NULL
            GROUP BY domain
            ORDER BY count DESC
        """)
        domains = cursor.fetchall()

        for domain, count in domains:
            percentage = (count / len(student_emails)) * 100
            print(f"  - {domain}: {count} ({percentage:.1f}%)")

        # Test 4: Duplicate emails
        print("\n✓ Test 4: Checking for duplicate emails")
        cursor.execute("""
            SELECT email_address, COUNT(*) as count
            FROM students
            GROUP BY email_address
            HAVING count > 1
        """)
        duplicate_student_emails = cursor.fetchall()

        if duplicate_student_emails:
            print(f"  ✗ Found {len(duplicate_student_emails)} duplicate student emails:")
            for email, count in duplicate_student_emails[:5]:
                print(f"    - {email}: {count} occurrences")
        else:
            print("  ✓ No duplicate student emails")

        cursor.execute("""
            SELECT email, COUNT(*) as count
            FROM users
            GROUP BY email
            HAVING count > 1
        """)
        duplicate_user_emails = cursor.fetchall()

        if duplicate_user_emails:
            print(f"  ✗ Found {len(duplicate_user_emails)} duplicate user emails:")
            for email, count in duplicate_user_emails[:5]:
                print(f"    - {email}: {count} occurrences")
        else:
            print("  ✓ No duplicate user emails")

        # Test 5: Email consistency between students and users
        print("\n✓ Test 5: Email consistency (students vs users)")
        cursor.execute("""
            SELECT s.student_id, s.email_address as student_email, u.email as user_email
            FROM students s
            JOIN users u ON s.student_id = u.student_id
            WHERE s.email_address != u.email
        """)
        mismatched_emails = cursor.fetchall()

        if mismatched_emails:
            print(f"  ✗ Found {len(mismatched_emails)} email mismatches:")
            for sid, s_email, u_email in mismatched_emails[:5]:
                print(f"    - {sid}:")
                print(f"      Student: {s_email}")
                print(f"      User: {u_email}")
        else:
            print("  ✓ All student/user emails match")

        # Test 6: Instructor emails
        print("\n✓ Test 6: Instructor email validation")
        cursor.execute("SELECT first_name, last_name, email FROM instructors WHERE is_active = 1")
        instructor_emails = cursor.fetchall()

        valid_instructor_emails = 0
        invalid_instructor_emails = []

        for first, last, email in instructor_emails:
            if is_valid_email(email):
                valid_instructor_emails += 1
            else:
                invalid_instructor_emails.append((f"{first} {last}", email))

        print(f"  Valid emails: {valid_instructor_emails}/{len(instructor_emails)}")

        if invalid_instructor_emails:
            print(f"\n  ✗ Invalid instructor email formats:")
            for name, email in invalid_instructor_emails:
                print(f"    - {name}: {email}")
        else:
            print("  ✓ All instructor emails are valid")

        # Test 7: Email format patterns
        print("\n✓ Test 7: Email format patterns")
        cursor.execute("""
            SELECT
                CASE
                    WHEN email_address LIKE '%@%.edu' THEN 'Educational (.edu)'
                    WHEN email_address LIKE '%@%.com' THEN 'Commercial (.com)'
                    WHEN email_address LIKE '%@%.org' THEN 'Organization (.org)'
                    ELSE 'Other'
                END as email_type,
                COUNT(*) as count
            FROM students
            WHERE email_address IS NOT NULL
            GROUP BY email_type
        """)
        email_patterns = cursor.fetchall()

        for pattern, count in email_patterns:
            print(f"  - {pattern}: {count}")

        print("\n" + "=" * 60)
        print("EMAIL VALIDATION TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_email_validation()
