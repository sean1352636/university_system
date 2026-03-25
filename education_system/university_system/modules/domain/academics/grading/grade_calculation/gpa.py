import os
import csv
import numpy as np
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.academics.grading.grade_calculation.conversions import letter_to_gpa
from education_system.university_system.modules.domain.academics.grading.grade_calculation.utils import select_student


def calculate_student_gpa(cursor, student_id):
    """Calculate the GPA for a specific student (from module_grades + assignment_submissions)"""
    try:
        # Get module grades for this student
        cursor.execute('''
        SELECT mg.module_code, m.module_name, mg.final_grade
        FROM module_grades mg
        JOIN modules m ON mg.module_code = m.module_code
        WHERE mg.student_id = ?
        ''', (student_id,))

        module_grades = cursor.fetchall()

        # Also get graded assignment submissions (grouped by module for GPA)
        cursor.execute('''
        SELECT a.module_code, m.module_name,
               ROUND(AVG(sub.grade), 2) as avg_grade
        FROM assignment_submissions sub
        JOIN assignments a ON sub.assignment_id = a.id
        JOIN modules m ON a.module_code = m.module_code
        WHERE sub.student_id = ? AND sub.grade IS NOT NULL
        GROUP BY a.module_code
        ''', (student_id,))

        assignment_grades = cursor.fetchall()

        # Merge: module_grades takes priority, fill in from assignment_submissions
        seen_modules = set()
        all_grades = []

        for module_code, module_name, grade in module_grades:
            if grade:
                seen_modules.add(module_code)
                all_grades.append((module_code, module_name, grade))

        for module_code, module_name, avg_grade in assignment_grades:
            if module_code not in seen_modules and avg_grade is not None:
                all_grades.append((module_code, module_name, avg_grade))

        if not all_grades:
            return None, 0, []

        total_points = 0
        total_modules = 0
        detailed_grades = []

        for module_code, module_name, grade in all_grades:
            gpa_points = letter_to_gpa(grade)
            total_points += gpa_points
            total_modules += 1
            detailed_grades.append((module_code, module_name, grade, gpa_points))

        if total_modules == 0:
            return None, 0, []

        gpa = total_points / total_modules

        return gpa, total_modules, detailed_grades

    except sqlite3.Error as e:
        print(f"Error calculating GPA: {e}")
        return None, 0, []


def calculate_gpa():
    """Calculate GPA for a student or for all students"""
    print("\nCalculate GPA")

    gpa_type = input("Calculate GPA for (1) individual student or (2) all students? Enter 1 or 2: ").strip()

    if gpa_type not in ['1', '2']:
        print("Invalid option. Calculating for individual student.")
        gpa_type = '1'

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if gpa_type == '1':
            # Individual student GPA
            student_id = select_student(cursor)
            if not student_id:
                conn.close()
                return

            # Get student info
            cursor.execute('''
            SELECT first_name, middle_name, last_name, course
            FROM students
            WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()

            if not student:
                print(f"Student with ID {student_id} not found.")
                conn.close()
                return

            first_name, middle_name, last_name, course = student
            middle_initial = middle_name[0] + ". " if middle_name else ""
            full_name = f"{first_name} {middle_initial}{last_name}"

            # Calculate GPA
            gpa, credits, grades = calculate_student_gpa(cursor, student_id)

            if gpa is None:
                print(f"No grades found for student {full_name} (ID: {student_id}).")
                conn.close()
                return

            print(f"\nGPA Calculation for {full_name} (ID: {student_id})")
            print(f"Course: {course}")
            print(f"GPA: {gpa:.2f}")
            print(f"Credits Completed: {credits}")

            # Display individual module grades
            print("\nModule Grades:")
            print("-" * 80)
            print(f"{'Module Code':<12} {'Module Name':<40} {'Grade':<8} {'GPA Points':<12}")
            print("-" * 80)

            for module_code, module_name, grade, points in grades:
                print(f"{module_code:<12} {module_name:<40} {grade:<8} {points:<12.2f}")

        else:
            # All students GPA
            print("\nCalculating GPA for all students...")

            cursor.execute('''
            SELECT s.student_id, s.first_name, s.middle_name, s.last_name, s.course
            FROM students s
            ORDER BY s.last_name, s.first_name
            ''')

            students = cursor.fetchall()

            if not students:
                print("No students found in the database.")
                conn.close()
                return

            # Create a list to store student GPA data
            student_gpas = []

            for student_id, first_name, middle_name, last_name, course in students:
                middle_initial = middle_name[0] + ". " if middle_name else ""
                full_name = f"{last_name}, {first_name} {middle_initial}"

                # Calculate GPA
                gpa, credits, _ = calculate_student_gpa(cursor, student_id)

                student_gpas.append({
                    'id': student_id,
                    'name': full_name,
                    'course': course,
                    'gpa': gpa if gpa is not None else 0,
                    'credits': credits
                })

            # Sort by GPA (highest first)
            student_gpas.sort(key=lambda x: x['gpa'], reverse=True)

            # Display results
            print("\nStudent GPA Summary:")
            print("-" * 80)
            print(f"{'Rank':<6} {'Student ID':<12} {'Name':<40} {'Course':<8} {'GPA':<8} {'Credits'}")
            print("-" * 80)

            for i, student in enumerate(student_gpas):
                if student['gpa'] > 0:  # Only show students with grades
                    print(f"{i+1:<6} {student['id']:<12} {student['name']:<40} {student['course']:<8} {student['gpa']:<8.2f} {student['credits']}")

            # Ask if the user wants to export this data
            export = input("\nDo you want to export this GPA summary to CSV? (y/n): ").strip().lower()

            if export == 'y':
                # Create the exports directory if it doesn't exist
                exports_dir = 'grade_exports'
                if not os.path.exists(exports_dir):
                    os.makedirs(exports_dir)

                # Generate a filename based on current timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{exports_dir}/gpa_summary_{timestamp}.csv"

                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Rank', 'Student ID', 'Name', 'Course', 'GPA', 'Credits'])

                    for i, student in enumerate(student_gpas):
                        if student['gpa'] > 0:  # Only export students with grades
                            writer.writerow([
                                i+1,
                                student['id'],
                                student['name'],
                                student['course'],
                                f"{student['gpa']:.2f}",
                                student['credits']
                            ])

                print(f"GPA summary exported to {filename}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
