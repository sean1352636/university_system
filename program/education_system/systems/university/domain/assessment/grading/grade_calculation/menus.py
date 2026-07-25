from education_system.systems.university.domain.assessment.grading.grade_calculation.db_init import init_enhanced_grades_db
from education_system.systems.university.domain.assessment.grading.grade_calculation.grade_entry import (
    record_assessment_grades,
    update_grades,
)
from education_system.systems.university.domain.assessment.grading.grade_calculation.views import view_student_grades
from education_system.systems.university.domain.assessment.grading.grade_calculation.gpa import calculate_gpa
from education_system.systems.university.domain.assessment.grading.grade_calculation.transcripts import generate_transcript
from education_system.systems.university.domain.assessment.grading.grade_calculation.statistics import (
    calculate_assessment_statistics,
    normalize_assessment_grades,
)
from education_system.systems.university.domain.assessment.grading.grade_calculation.visualization import view_grade_distribution
from education_system.systems.university.domain.assessment.grading.grade_calculation.learning_outcomes import map_assessments_to_competencies
from education_system.systems.university.domain.assessment.grading.grade_calculation.utils import select_student
from education_system.systems.university.domain.assessment.grading.grade_calculation.prediction import (
    predict_next_assessment_grade,
    predict_final_module_grade,
    predict_end_term_gpa,
    batch_grade_predictions,
)

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection


def display_enhanced_grade_menu():
    """Display the enhanced grade and performance tracking menu and handle user choices"""
    from education_system.systems.university.domain.assessment.grading import grade_calculation
    from education_system.systems.university.domain.assessment.grading.learning_outcomes.menu import learning_outcome_menu
    from education_system.systems.university.domain.assessment.grading.predictive_analytics import predictive_analytics_menu
    from education_system.systems.university.domain.assessment.grading.curve_analysis import performance_analysis_menu
    # Initialize basic tables first
    if not grade_calculation.init_basic_database():
        print("Failed to initialize basic database tables.")
        return

    # Initialize all tables for the enhanced system
    grade_calculation.init_enhanced_grades_db()

    while True:
        print("\nGrade and Performance Tracking:")
        print("\n--- Grade Management ---")
        print("1. Record Grades for Assessment")
        print("2. Update Existing Grades")
        print("3. View Student Grades")
        print("4. Calculate GPA")
        print("5. Generate Transcript")
        print("\n--- Advanced Features ---")
        print("6. Grade Curve Analysis")
        print("7. Learning Outcome Tracking")
        print("8. Competency-Based Assessment")
        print("9. Predictive Analytics & Early Warning")
        print("10. Performance Analysis")
        print("11. Return to Main Menu")

        choice = input("Enter your choice (1-11): ")

        if choice == '1':
            grade_calculation.record_assessment_grades()
        elif choice == '2':
            grade_calculation.update_grades()
        elif choice == '3':
            grade_calculation.view_student_grades()
        elif choice == '4':
            grade_calculation.calculate_gpa()
        elif choice == '5':
            grade_calculation.generate_transcript()
        elif choice == '6':
            grade_curve_analysis_menu()
        elif choice == '7':
            learning_outcome_menu()
        elif choice == '8':
            competency_assessment_menu()
        elif choice == '9':
            predictive_analytics_menu()
        elif choice == '10':
            performance_analysis_menu()
        elif choice == '11':
            print("Returning to main menu...")
            break
        else:
            print("Invalid choice. Please try again.")


def grade_curve_analysis_menu():
    """Display the grade curve analysis menu and handle user choices"""
    from education_system.systems.university.domain.assessment.grading.curve_analysis import apply_grading_curve
    from education_system.systems.university.domain.assessment.grading.reports import generate_statistical_report
    while True:
        print("\nGrade Curve Analysis:")
        print("1. Calculate Statistics for Assessment")
        print("2. Normalize Grades for Assessment")
        print("3. View Grade Distribution")
        print("4. Apply Grading Curve")
        print("5. Generate Statistical Report")
        print("6. Return to Grade Menu")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            calculate_assessment_statistics()
        elif choice == '2':
            normalize_assessment_grades()
        elif choice == '3':
            view_grade_distribution()
        elif choice == '4':
            apply_grading_curve()
        elif choice == '5':
            generate_statistical_report()
        elif choice == '6':
            print("Returning to grade menu...")
            break
        else:
            print("Invalid choice. Please try again.")


def competency_assessment_menu():
    """Display the competency-based assessment menu and handle user choices"""
    from education_system.systems.university.domain.assessment.grading.competency import manage_competencies, record_student_competencies
    from education_system.systems.university.domain.assessment.grading.competency_assessment import manage_competency_levels, view_student_competency_profile, generate_competency_report
    while True:
        print("\nCompetency-Based Assessment:")
        print("1. Manage Competencies")
        print("2. Manage Competency Levels")
        print("3. Map Assessments to Competencies")
        print("4. Record Student Competencies")
        print("5. View Student Competency Profile")
        print("6. Generate Competency Report")
        print("7. Return to Grade Menu")

        choice = input("Enter your choice (1-7): ")

        if choice == '1':
            manage_competencies()
        elif choice == '2':
            manage_competency_levels()
        elif choice == '3':
            map_assessments_to_competencies()
        elif choice == '4':
            record_student_competencies()
        elif choice == '5':
            view_student_competency_profile()
        elif choice == '6':
            generate_competency_report()
        elif choice == '7':
            print("Returning to grade menu...")
            break
        else:
            print("Invalid choice. Please try again.")


def grade_prediction():
    """Predict future grades based on current performance"""
    print("\nGrade Prediction System")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nGrade Prediction Options:")
        print("1. Predict Next Assessment Grade")
        print("2. Predict Final Module Grade")
        print("3. Predict GPA at End of Term")
        print("4. Batch Grade Predictions")

        choice = input("Enter your choice (1-4): ").strip()

        if choice == '1':
            predict_next_assessment_grade(cursor)
        elif choice == '2':
            predict_final_module_grade(cursor)
        elif choice == '3':
            student_id = select_student(cursor)
            if student_id:
                result = predict_end_term_gpa(cursor, student_id)
                if result:
                    print(f"\nCurrent GPA: {result['current_gpa']:.2f}")
                    print(f"Predicted End-of-Term GPA: {result['predicted_gpa']:.2f}")
                    print(f"Trend delta: {result['trend']:+.2f}")
                else:
                    print("Not enough data to predict GPA.")
            else:
                print("No student selected.")
        elif choice == '4':
            batch_grade_predictions(cursor)
        else:
            print("Invalid choice. Returning to menu.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
