"""Duplicate detection and data quality reports."""
import re
import logging
from collections import defaultdict
from difflib import SequenceMatcher

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.utils.sql_safety import (
    validate_field_for_query,
    SQLIdentifierError,
)
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.modules.shared.services.analytics.advanced_search.admin import audit_log

logger = configure_logging(name=__name__)


@audit_log
def duplicate_detection():
    """Detect potential duplicate student records"""
    print("\n🔍 DUPLICATE DETECTION")
    print("="*40)

    print("Detection methods:")
    print("1. Exact name matches")
    print("2. Similar names (fuzzy matching)")
    print("3. Email pattern analysis")
    print("4. Comprehensive analysis")

    choice = input("Select method (1-4): ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if choice == '1':
            detect_exact_name_duplicates(cursor)
        elif choice == '2':
            detect_fuzzy_name_duplicates(cursor)
        elif choice == '3':
            detect_email_pattern_duplicates(cursor)
        elif choice == '4':
            comprehensive_duplicate_analysis(cursor)

        conn.close()

    except sqlite3.Error as e:
        print(f"Error in duplicate detection: {e}")

def detect_exact_name_duplicates(cursor):
    """Find students with exact same names"""
    cursor.execute('''
    SELECT first_name, last_name, COUNT(*) as count
    FROM students
    GROUP BY LOWER(first_name), LOWER(last_name)
    HAVING count > 1
    ORDER BY count DESC
    ''')

    duplicates = cursor.fetchall()

    if not duplicates:
        print("✅ No exact name duplicates found.")
        return

    print(f"\n⚠️  Found {len(duplicates)} sets of exact name matches:")
    print("-" * 50)

    for first_name, last_name, count in duplicates:
        print(f"{first_name} {last_name}: {count} records")

        # Get detailed records
        cursor.execute('''
        SELECT student_id, email, course, registration_datetime
        FROM students
        WHERE LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?)
        ''', (first_name, last_name))

        records = cursor.fetchall()
        for record in records:
            print(f"  → {record[0]} | {record[1]} | {record[2]} | {record[3][:10]}")
        print()

def detect_fuzzy_name_duplicates(cursor):
    """Find students with similar names using fuzzy matching"""
    cursor.execute("SELECT student_id, first_name, last_name FROM students")
    all_students = cursor.fetchall()

    threshold = 0.85  # Similarity threshold
    potential_duplicates = []

    for i, student1 in enumerate(all_students):
        for student2 in all_students[i+1:]:
            # Compare full names
            name1 = f"{student1[1]} {student1[2]}".lower()
            name2 = f"{student2[1]} {student2[2]}".lower()

            similarity = SequenceMatcher(None, name1, name2).ratio()

            if similarity >= threshold:
                potential_duplicates.append((student1, student2, similarity))

    if not potential_duplicates:
        print("✅ No fuzzy name duplicates found.")
        return

    print(f"\n⚠️  Found {len(potential_duplicates)} potential fuzzy matches:")
    print("-" * 70)

    for student1, student2, similarity in potential_duplicates:
        print(f"Similarity: {similarity:.2f}")
        print(f"  {student1[0]}: {student1[1]} {student1[2]}")
        print(f"  {student2[0]}: {student2[1]} {student2[2]}")
        print()

def comprehensive_duplicate_analysis(cursor):
    """Comprehensive duplicate analysis combining multiple methods"""
    print("\n🔬 COMPREHENSIVE DUPLICATE ANALYSIS")
    print("="*50)

    # Combine multiple detection methods
    print("Running multiple detection algorithms...")

    print("\n1. Exact name matches:")
    detect_exact_name_duplicates(cursor)

    print("\n2. Email pattern analysis:")
    detect_email_pattern_duplicates(cursor)

    print("\n3. Similar names:")
    detect_fuzzy_name_duplicates(cursor)

    print("\n✅ Comprehensive analysis complete.")

def detect_email_pattern_duplicates(cursor):
    """Detect students with similar email patterns"""
    cursor.execute("SELECT student_id, first_name, last_name, email FROM students WHERE email IS NOT NULL")
    students = cursor.fetchall()

    email_patterns = defaultdict(list)

    for student in students:
        # Extract email local part (before @)
        email = student[3]
        if '@' in email:
            local_part = email.split('@')[0].lower()
            # Remove numbers and dots to find base pattern
            base_pattern = re.sub(r'[0-9.]', '', local_part)
            if len(base_pattern) >= 3:  # Only consider meaningful patterns
                email_patterns[base_pattern].append(student)

    # Find patterns with multiple users
    duplicates = {pattern: students for pattern, students in email_patterns.items() if len(students) > 1}

    if not duplicates:
        print("✅ No email pattern duplicates found.")
        return

    print(f"\n⚠️  Found {len(duplicates)} email patterns with multiple users:")
    print("-" * 60)

    for pattern, students in duplicates.items():
        print(f"Pattern '{pattern}': {len(students)} students")
        for student in students:
            print(f"  → {student[0]} | {student[1]} {student[2]} | {student[3]}")
        print()

@audit_log
def data_quality_reports():
    """Generate data quality reports"""
    print("\n📊 DATA QUALITY REPORTS")
    print("="*40)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Analyzing data quality...")

        # Missing field analysis
        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]

        fields_to_check = [
            ('email', 'Email addresses'),
            ('first_name', 'First names'),
            ('last_name', 'Last names'),
            ('gender', 'Gender'),
            ('date_of_birth', 'Date of birth'),
            ('course', 'Course')
        ]

        # Whitelist of allowed field names for this analysis
        ALLOWED_STUDENT_FIELDS = {'email', 'first_name', 'last_name', 'gender', 'date_of_birth', 'course'}

        print(f"\n📋 MISSING FIELD ANALYSIS (Total students: {total_students}):")
        print("-" * 60)
        print(f"{'Field':<20} {'Missing':<10} {'Percentage':<12} {'Quality':<10}")
        print("-" * 60)

        for field, description in fields_to_check:
            # Validate field name against whitelist to prevent SQL injection
            try:
                validated_field = validate_field_for_query(field, ALLOWED_STUDENT_FIELDS, "field")
            except SQLIdentifierError as e:
                logger.warning(f"Skipping invalid field: {field} - {e}")
                continue
            cursor.execute("SELECT COUNT(*) FROM students WHERE [" + validated_field + "] IS NULL OR [" + validated_field + "] = ''")
            missing = cursor.fetchone()[0]
            percentage = (missing / total_students) * 100 if total_students > 0 else 0

            quality = "Excellent" if percentage < 5 else "Good" if percentage < 15 else "Poor"

            print(f"{description:<20} {missing:<10} {percentage:>8.1f}%    {quality:<10}")

        # Invalid data patterns
        print(f"\n🔍 INVALID DATA PATTERN DETECTION:")
        print("-" * 60)

        # Invalid email patterns
        cursor.execute("""
        SELECT COUNT(*) FROM students
        WHERE email IS NOT NULL AND email NOT LIKE '%@%.%'
        """)
        invalid_emails = cursor.fetchone()[0]
        print(f"Invalid email formats: {invalid_emails}")

        # Age inconsistencies
        cursor.execute("""
        SELECT COUNT(*) FROM students
        WHERE age < 16 OR age > 80
        """)
        invalid_ages = cursor.fetchone()[0]
        print(f"Suspicious age values: {invalid_ages}")

        # Course consistency
        cursor.execute("""
        SELECT COUNT(*) FROM students
        WHERE course NOT IN ('CS', 'DS') AND course IS NOT NULL
        """)
        invalid_courses = cursor.fetchone()[0]
        print(f"Invalid course codes: {invalid_courses}")

        # Data completeness score
        total_fields = len(fields_to_check)
        cursor.execute("""
        SELECT AVG(
            CASE WHEN email IS NOT NULL AND email != '' THEN 1 ELSE 0 END +
            CASE WHEN first_name IS NOT NULL AND first_name != '' THEN 1 ELSE 0 END +
            CASE WHEN last_name IS NOT NULL AND last_name != '' THEN 1 ELSE 0 END +
            CASE WHEN gender IS NOT NULL AND gender != '' THEN 1 ELSE 0 END +
            CASE WHEN date_of_birth IS NOT NULL AND date_of_birth != '' THEN 1 ELSE 0 END +
            CASE WHEN course IS NOT NULL AND course != '' THEN 1 ELSE 0 END
        ) * 100.0 / ? as completeness
        FROM students
        """, (total_fields,))

        completeness = cursor.fetchone()[0] or 0

        print(f"\n📈 OVERALL DATA QUALITY SCORE:")
        print("-" * 40)
        print(f"Data Completeness: {completeness:.1f}%")

        quality_grade = "A" if completeness >= 90 else "B" if completeness >= 80 else "C" if completeness >= 70 else "D"
        print(f"Quality Grade: {quality_grade}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Error generating quality report: {e}")
