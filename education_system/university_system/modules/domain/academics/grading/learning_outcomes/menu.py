from education_system.university_system.modules.domain.academics.grading.learning_outcomes.management import manage_learning_outcomes
from education_system.university_system.modules.domain.academics.grading.learning_outcomes.achievement import (
    record_outcome_achievement,
    view_student_outcome_achievement,
)
from education_system.university_system.modules.domain.academics.grading.learning_outcomes.reports import (
    generate_student_outcome_report,
    generate_course_outcome_report,
    generate_all_courses_outcome_report,
    generate_module_outcome_report,
)
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.academics.grading.utils import select_student
from education_system.university_system.modules.domain.academics.grading.grade_calculation import map_assessments_to_outcomes


def learning_outcome_menu():
    """Display the learning outcome tracking menu and handle user choices"""
    while True:
        print("\nLearning Outcome Tracking:")
        print("1. Manage Learning Outcomes")
        print("2. Map Assessments to Outcomes")
        print("3. Record Outcome Achievement")
        print("4. View Student Outcome Achievement")
        print("5. Generate Outcome Report")
        print("6. Return to Grade Menu")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            manage_learning_outcomes()
        elif choice == '2':
            map_assessments_to_outcomes()
        elif choice == '3':
            record_outcome_achievement()
        elif choice == '4':
            view_student_outcome_achievement()
        elif choice == '5':
            generate_outcome_report()
        elif choice == '6':
            print("Returning to grade menu...")
            break
        else:
            print("Invalid choice. Please try again.")

def generate_outcome_report():
    """Generate a comprehensive report of learning outcome achievement"""
    print("\nGenerate Learning Outcome Report")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Ask what type of report to generate
        print("\nReport Options:")
        print("1. Individual Student Outcome Report")
        print("2. Course Outcome Achievement Summary")
        print("3. Module-Based Outcome Report")

        report_type = input("Select report type (1-3): ")

        if report_type == '1':
            # Individual student report
            student_id = select_student(cursor)
            if not student_id:
                conn.close()
                return

            generate_student_outcome_report(cursor, student_id)

        elif report_type == '2':
            # Course outcome summary
            cursor.execute("SELECT DISTINCT course FROM students ORDER BY course")
            courses = cursor.fetchall()

            if not courses:
                print("No courses found in the database.")
                conn.close()
                return

            print("\nAvailable Courses:")
            for i, (course,) in enumerate(courses):
                print(f"{i+1}. {course}")

            course_idx = input("Select course number (or 0 for all courses): ")

            try:
                idx = int(course_idx)
                if idx == 0:
                    generate_all_courses_outcome_report(cursor)
                elif 1 <= idx <= len(courses):
                    generate_course_outcome_report(cursor, courses[idx-1][0])
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif report_type == '3':
            # Module-based outcome report
            cursor.execute("SELECT DISTINCT module_code, module_name FROM modules ORDER BY module_name")
            modules = cursor.fetchall()

            if not modules:
                print("No modules found in the database.")
                conn.close()
                return

            print("\nAvailable Modules:")
            for i, (code, name) in enumerate(modules):
                print(f"{i+1}. {code} - {name}")

            module_idx = input("Select module number: ")

            try:
                idx = int(module_idx)
                if 1 <= idx <= len(modules):
                    generate_module_outcome_report(cursor, modules[idx-1][0])
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        else:
            print("Invalid report type.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
