from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.assessment.grading.grade_calculation.constants import GRADE_SYSTEMS
from education_system.systems.university.domain.assessment.grading.grade_calculation.conversions import (
    percentage_to_letter,
    letter_to_percentage,
)
from education_system.systems.university.domain.assessment.grading.grade_calculation.utils import (
    select_student,
    select_assessment,
)


def update_module_grade(cursor, student_id, module_code):
    """Update the final grade for a student in a module based on all assessment grades"""
    try:
        # Get all assessments for this module
        cursor.execute('''
        SELECT assessment_id, weight, max_points
        FROM assessments
        WHERE module_code = ?
        ''', (module_code,))

        assessments = cursor.fetchall()

        if not assessments:
            return

        total_weighted_score = 0
        total_weight = 0

        # Calculate weighted score for each assessment
        for assessment_id, weight, max_points in assessments:
            cursor.execute('''
            SELECT score
            FROM grades
            WHERE student_id = ? AND assessment_id = ?
            ''', (student_id, assessment_id))

            grade = cursor.fetchone()

            if grade:
                # Calculate percentage score for this assessment
                percentage = (grade[0] / max_points) * 100
                weighted_score = percentage * (weight / 100)

                total_weighted_score += weighted_score
                total_weight += weight

        # Only update if at least one grade exists
        if total_weight > 0:
            # Adjust score based on total weight recorded so far
            if total_weight < 100:
                final_score = total_weighted_score * (100 / total_weight)
            else:
                final_score = total_weighted_score

            final_grade = percentage_to_letter(final_score)
            completion_date = datetime.now().strftime('%Y-%m-%d')

            # Check if a module grade already exists
            cursor.execute('''
            SELECT id
            FROM module_grades
            WHERE student_id = ? AND module_code = ?
            ''', (student_id, module_code))

            existing_grade = cursor.fetchone()

            if existing_grade:
                # Update existing grade
                cursor.execute('''
                UPDATE module_grades
                SET final_score = ?, final_grade = ?, completion_date = ?
                WHERE id = ?
                ''', (final_score, final_grade, completion_date, existing_grade[0]))
            else:
                # Insert new grade
                cursor.execute('''
                INSERT INTO module_grades (student_id, module_code, final_score, final_grade, completion_date)
                VALUES (?, ?, ?, ?, ?)
                ''', (student_id, module_code, final_score, final_grade, completion_date))

    except sqlite3.Error as e:
        print(f"Error updating module grade: {e}")


def record_assessment_grades():
    """Record grades for students for a specific assessment"""
    print("\nRecord Assessment Grades")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get the assessment to grade
        assessment_id = select_assessment(cursor)
        if assessment_id is None:
            conn.close()
            return

        # Get assessment details
        cursor.execute('''
        SELECT a.assessment_name, a.assessment_type, a.module_code, a.weight, a.max_points, m.module_name
        FROM assessments a
        JOIN modules m ON a.module_code = m.module_code
        WHERE a.assessment_id = ?
        ''', (assessment_id,))

        assessment = cursor.fetchone()

        if not assessment:
            print(f"Assessment with ID {assessment_id} not found.")
            conn.close()
            return

        assessment_name, assessment_type, module_code, weight, max_points, module_name = assessment

        print(f"\nRecording grades for: {assessment_name} ({assessment_type})")
        print(f"Module: {module_code} - {module_name}")
        print(f"Weight: {weight}%, Max Points: {max_points}")

        # Get students enrolled in this module
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.middle_name, s.last_name
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ?
        ORDER BY s.last_name, s.first_name
        ''', (module_code,))

        students = cursor.fetchall()

        if not students:
            print(f"No students found enrolled in module {module_code}.")
            conn.close()
            return

        print(f"\nFound {len(students)} students enrolled in this module.")

        # Ask for grading method
        grade_method = input("\nEnter grading method (1 for points, 2 for letter grades): ").strip()

        if grade_method not in ['1', '2']:
            print("Invalid grading method. Using points by default.")
            grade_method = '1'

        # Record grades for each student
        grades_recorded = 0
        submission_date = datetime.now().strftime('%Y-%m-%d')

        for student in students:
            student_id, first_name, middle_name, last_name = student
            middle_initial = middle_name[0] + ". " if middle_name else ""
            full_name = f"{first_name} {middle_initial}{last_name}"

            # Check if grade already exists
            cursor.execute('''
            SELECT grade_id, score, letter_grade
            FROM grades
            WHERE student_id = ? AND assessment_id = ?
            ''', (student_id, assessment_id))

            existing_grade = cursor.fetchone()

            if existing_grade:
                print(f"\n{full_name} (ID: {student_id}) already has a grade of {existing_grade[2]} ({existing_grade[1]} points) for this assessment.")
                update_this = input("Do you want to update this grade? (y/n): ").strip().lower()

                if update_this != 'y':
                    continue

                # Delete existing grade
                cursor.execute('''
                DELETE FROM grades
                WHERE grade_id = ?
                ''', (existing_grade[0],))

            print(f"\nEnter grade for {full_name} (ID: {student_id}):")

            if grade_method == '1':
                # Points method
                score = input(f"Points (max {max_points}): ").strip()

                try:
                    score = float(score)
                    if score < 0 or score > max_points:
                        print(f"Score must be between 0 and {max_points}. Skipping this student.")
                        continue

                    # Calculate letter grade based on percentage
                    percentage = (score / max_points) * 100
                    letter_grade = percentage_to_letter(percentage)

                except ValueError:
                    print("Invalid score. Please enter a number. Skipping this student.")
                    continue

            else:
                # Letter grade method
                print("Available letter grades:")
                for grade in GRADE_SYSTEMS["letter"].keys():
                    print(grade, end=" ")

                letter_grade = input("\nLetter grade: ").strip().upper()

                if letter_grade not in GRADE_SYSTEMS["letter"]:
                    print(f"Invalid letter grade. Valid grades are: {', '.join(GRADE_SYSTEMS['letter'].keys())}. Skipping this student.")
                    continue

                # Calculate score based on letter grade
                grade_percentage = letter_to_percentage(letter_grade)
                score = (grade_percentage / 100) * max_points

            # Get comments (optional)
            comments = input("Comments (optional): ").strip()

            # Insert the grade
            cursor.execute('''
            INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date, comments)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, assessment_id, score, letter_grade, submission_date, comments))

            grades_recorded += 1

            # Update final module grade
            update_module_grade(cursor, student_id, module_code)

        conn.commit()
        print(f"\nSuccessfully recorded {grades_recorded} grades for {assessment_name}.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")


def update_grades():
    """Update existing grades for assessments"""
    print("\nUpdate Existing Grades")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        student_id = input("Enter student ID (leave blank to select from a list): ").strip()

        if not student_id:
            student_id = select_student(cursor)
            if not student_id:
                conn.close()
                return

        # Get student info
        cursor.execute('''
        SELECT first_name, middle_name, last_name
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()

        if not student:
            print(f"Student with ID {student_id} not found.")
            conn.close()
            return

        first_name, middle_name, last_name = student
        middle_initial = middle_name[0] + ". " if middle_name else ""
        full_name = f"{first_name} {middle_initial}{last_name}"

        print(f"\nUpdating grades for: {full_name} (ID: {student_id})")

        # Get grades for this student
        cursor.execute('''
        SELECT g.grade_id, a.assessment_name, a.assessment_type, a.module_code, m.module_name,
               g.score, g.letter_grade, a.max_points
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        JOIN modules m ON a.module_code = m.module_code
        WHERE g.student_id = ?
        ORDER BY g.submission_date DESC
        ''', (student_id,))

        grades = cursor.fetchall()

        if not grades:
            print(f"No grades found for student {student_id}.")
            conn.close()
            return

        print("\nAvailable Grades:")
        for i, (grade_id, name, type, module_code, module_name, score, letter, max_points) in enumerate(grades):
            print(f"{i+1}. [{module_code}] {name} ({type}) - {letter} ({score}/{max_points})")

        grade_index = input("\nEnter grade number to update: ").strip()

        try:
            index = int(grade_index) - 1
            if index < 0 or index >= len(grades):
                print("Invalid grade number.")
                conn.close()
                return

            selected_grade = grades[index]
            grade_id = selected_grade[0]
            assessment_name = selected_grade[1]
            max_points = selected_grade[7]
            module_code = selected_grade[3]

            # Get the assessment ID for this grade
            cursor.execute('''
            SELECT assessment_id
            FROM grades
            WHERE grade_id = ?
            ''', (grade_id,))

            assessment_id = cursor.fetchone()[0]

            # Ask for update method
            update_method = input("\nUpdate method (1 for points, 2 for letter grade): ").strip()

            if update_method not in ['1', '2']:
                print("Invalid update method. Using points by default.")
                update_method = '1'

            if update_method == '1':
                # Update with points
                print(f"Current score: {selected_grade[5]}/{max_points}")
                score = input(f"New points (max {max_points}): ").strip()

                try:
                    score = float(score)
                    if score < 0 or score > max_points:
                        print(f"Score must be between 0 and {max_points}.")
                        conn.close()
                        return

                    # Calculate letter grade based on percentage
                    percentage = (score / max_points) * 100
                    letter_grade = percentage_to_letter(percentage)

                except ValueError:
                    print("Invalid score. Please enter a number.")
                    conn.close()
                    return

            else:
                # Update with letter grade
                print(f"Current grade: {selected_grade[6]}")
                print("Available letter grades:")
                for grade in GRADE_SYSTEMS["letter"].keys():
                    print(grade, end=" ")

                letter_grade = input("\nNew letter grade: ").strip().upper()

                if letter_grade not in GRADE_SYSTEMS["letter"]:
                    print(f"Invalid letter grade. Valid grades are: {', '.join(GRADE_SYSTEMS['letter'].keys())}.")
                    conn.close()
                    return

                # Calculate score based on letter grade
                grade_percentage = letter_to_percentage(letter_grade)
                score = (grade_percentage / 100) * max_points

            # Get comments (optional)
            print("Current comments (if any):")
            cursor.execute('''
            SELECT comments
            FROM grades
            WHERE grade_id = ?
            ''', (grade_id,))

            current_comments = cursor.fetchone()[0]
            print(current_comments if current_comments else "No comments")

            comments = input("New comments (leave blank to keep current): ").strip()

            if not comments and current_comments:
                comments = current_comments

            # Update submission date
            submission_date = datetime.now().strftime('%Y-%m-%d')

            # Update the grade
            cursor.execute('''
            UPDATE grades
            SET score = ?, letter_grade = ?, submission_date = ?, comments = ?
            WHERE grade_id = ?
            ''', (score, letter_grade, submission_date, comments, grade_id))

            # Update final module grade
            update_module_grade(cursor, student_id, module_code)

            conn.commit()
            print(f"\nSuccessfully updated grade for {assessment_name} to {letter_grade} ({score}).")

        except ValueError:
            print("Invalid input. Please enter a number.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
