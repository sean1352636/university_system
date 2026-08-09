from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.assessment.grading.grade_calculation.conversions import letter_to_gpa
from education_system.systems.university.domain.assessment.grading.grade_calculation.utils import select_student


def view_student_grades():
    """View grades for a specific student"""
    print("\nView Student Grades")

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

        print(f"\nStudent: {full_name} (ID: {student_id})")
        print(f"Course: {course}")

        # Get modules and grades for this student
        cursor.execute('''
        SELECT m.module_code, m.module_name, mg.final_score, mg.final_grade
        FROM student_modules sm
        JOIN modules m ON sm.module_code = m.module_code
        LEFT JOIN module_grades mg ON sm.module_code = mg.module_code AND sm.student_id = mg.student_id
        WHERE sm.student_id = ?
        ORDER BY m.module_name
        ''', (student_id,))

        modules = cursor.fetchall()

        if not modules:
            print("No modules found for this student.")
            conn.close()
            return

        print("\nModule Grades:")
        print("-" * 80)
        print(f"{'Module Code':<12} {'Module Name':<40} {'Final Score':<12} {'Final Grade':<12}")
        print("-" * 80)

        # Calculate overall GPA for displayed modules
        total_points = 0
        module_count = 0

        for module_code, module_name, final_score, final_grade in modules:
            if final_score is not None:
                score_display = f"{final_score:.1f}"
                total_points += letter_to_gpa(final_grade)
                module_count += 1
            else:
                score_display = "N/A"
                final_grade = "N/A"

            print(f"{module_code:<12} {module_name:<40} {score_display:<12} {final_grade:<12}")

        # Calculate GPA
        if module_count > 0:
            gpa = total_points / module_count
            print(f"\nOverall GPA: {gpa:.2f}")
        else:
            print("\nNo grades recorded yet.")

        # Ask if user wants to see detailed assessment grades
        view_detail = input("\nDo you want to see detailed assessment grades? (y/n): ").strip().lower()

        if view_detail == 'y':
            # Get detailed assessment grades
            cursor.execute('''
            SELECT a.module_code, m.module_name, a.assessment_name, a.assessment_type, a.weight,
                   g.score, a.max_points, g.letter_grade, g.submission_date, g.comments
            FROM grades g
            JOIN assessments a ON g.assessment_id = a.assessment_id
            JOIN modules m ON a.module_code = m.module_code
            WHERE g.student_id = ?
            ORDER BY a.module_code, g.submission_date DESC
            ''', (student_id,))

            assessments = cursor.fetchall()

            if not assessments:
                print("No assessment grades recorded for this student.")
            else:
                current_module = None

                for assessment in assessments:
                    module_code, module_name, assessment_name, assessment_type, weight, score, max_points, letter_grade, date, comments = assessment

                    # Print module header if it's a new module
                    if current_module != module_code:
                        current_module = module_code
                        print(f"\n{module_code} - {module_name}")
                        print("-" * 80)
                        print(f"{'Assessment':<30} {'Type':<15} {'Weight':<8} {'Score':<12} {'Grade':<8} {'Date'}")
                        print("-" * 80)

                    percentage = (score / max_points) * 100
                    score_display = f"{score}/{max_points} ({percentage:.1f}%)"

                    print(f"{assessment_name:<30} {assessment_type:<15} {weight:<8.1f} {score_display:<12} {letter_grade:<8} {date}")

                    if comments:
                        print(f"  Comments: {comments}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
