from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
import os
import csv
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import matplotlib
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
matplotlib.use('Agg')

from education_system.university_system.modules.domain.academics.grading.grade_calculation import select_assessment, record_assessment_grades, update_module_grade, update_grades, view_student_grades, calculate_gpa, calculate_student_gpa, generate_transcript, create_transcript_pdf, letter_to_gpa, calculate_assessment_statistics, normalize_assessment_grades, view_grade_distribution, create_grade_visualizations, generate_assessment_stats_report, map_assessments_to_outcomes, map_assessments_to_competencies, assessment_performance_summary, analyze_specific_assessment, grade_distribution_analysis, student_risk_assessment, display_risk_assessment_results, save_risk_assessments, analyze_overall_grade_trends, analyze_by_assessment_type, analyze_all_assessments, analyze_distribution_by_assessment_type, compare_by_grade_threshold, analyze_assessment_performance_trends, analyze_single_assessment_type_trends, batch_grade_predictions, batch_predict_next_assessments, predict_student_next_grade, batch_predict_module_grades, predict_module_final_grade, batch_predict_end_term_gpas, predict_end_term_gpa, forecast_assessment_performance, forecast_assessment_type_performance, build_assessment_prediction_model, validate_grade_data_integrity, build_gpa_prediction_model, predict_student_gpa, grade_prediction, predict_next_assessment_grade
from education_system.university_system.modules.domain.academics.grading.curve_analysis import apply_grading_curve, comparative_performance_analysis, performance_trends_analysis, analyze_distribution_by_course, analyze_distribution_by_module_type, analyze_overall_distribution, dropout_risk_analysis
from education_system.university_system.modules.domain.academics.grading.learning_outcomes import manage_learning_outcomes, record_outcome_achievement, view_student_outcome_achievement, generate_outcome_report, generate_student_outcome_report, generate_course_outcome_report, generate_all_courses_outcome_report, generate_module_outcome_report
from education_system.university_system.modules.domain.academics.grading.competency_assessment import add_competency_levels, manage_competency_levels, view_student_competency_profile, generate_competency_report, generate_student_competency_report, generate_course_competency_report, assess_student_risk, assess_comprehensive_student_risk
from education_system.university_system.modules.domain.academics.grading.predictive_analytics import identify_at_risk_students, calculate_risk_factors, early_warning_system, generate_early_warning_alert, export_at_risk_students, export_early_warning_alerts, export_dropout_risk_list, build_at_risk_prediction_model, analyze_dropout_risk_factors, build_dropout_prediction_model, generate_dropout_interventions, generate_dropout_intervention_plan, identify_high_dropout_risk, calculate_dropout_risk_score, generate_risk_report, collect_comprehensive_risk_data, generate_comprehensive_risk_report
from education_system.university_system.modules.domain.academics.grading.performance_analytics import module_performance_summary, analyze_module_performance, display_module_performance_results, calculate_course_statistics, generate_performance_dashboard, display_performance_dashboard, export_module_performance, analyze_course_performance_trends, forecast_course_performance, export_performance_summary, performance_prediction_models, forecast_overall_performance
from education_system.university_system.modules.domain.academics.grading  import select_student, percentage_to_letter, letter_to_percentage, generate_statistical_report, generate_module_stats_report, generate_all_modules_stats_report, generate_course_stats_report, generate_all_courses_stats_report, generate_comprehensive_stats_report, manage_competencies, record_student_competencies, student_progress_tracking, analyze_student_progress, intervention_recommendations, generate_intervention_plan, display_intervention_recommendations, success_probability_calculator, calculate_individual_success_probability, compare_by_course, display_course_comparison, compare_by_gender, compare_by_module_type, analyze_individual_student_trends, collect_dashboard_data, create_progress_visualization, perform_statistical_test, compare_by_time_period, custom_group_comparison, compare_by_module_codes, compare_by_enrollment_date, compare_by_specific_courses, analyze_single_course_trends, analyze_seasonal_trends, analyze_monthly_patterns, analyze_day_of_week_patterns, analyze_academic_term_patterns, save_intervention_recommendations, calculate_all_students_success_probability, calculate_student_success_probability, export_batch_predictions, forecast_single_course, forecast_module_difficulty, forecast_module_difficulty_single, forecast_success_rates, forecast_course_success_rate, generate_system_recommendations, extract_comprehensive_student_features, build_module_success_model, create_dashboard_visualizations, generate_dashboard_report, generate_dashboard_recommendations, generate_dashboard_alerts, extract_student_features, trend_forecasting, calculate_trend_slope, create_trend_visualization, create_individual_trend_visualization, create_course_comparison_charts, export_comparison_data


def init_basic_database():
    """Initialize the basic database tables that are missing"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing basic database tables...")

        # Create students table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            last_name TEXT NOT NULL,
            course TEXT NOT NULL,
            email_address TEXT,
            gender TEXT,
            dob TEXT,
            enrollment_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'Active'
        )
        ''')

        # Create modules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            module_code TEXT PRIMARY KEY,
            module_name TEXT NOT NULL,
            module_type TEXT,
            credits INTEGER DEFAULT 1,
            description TEXT,
            course TEXT,
            semester TEXT,
            year INTEGER
        )
        ''')

        # Add missing columns if modules was created by another subsystem
        for col, col_type in [('course', 'TEXT'), ('module_code', 'TEXT'), ('module_type', 'TEXT')]:
            try:
                cursor.execute(f'ALTER TABLE modules ADD COLUMN {col} {col_type}')
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Create student_modules table (enrollment)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            enrollment_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'Enrolled',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            UNIQUE(student_id, module_code)
        )
        ''')

        # Create assessments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_name TEXT NOT NULL,
            assessment_type TEXT NOT NULL,
            module_code TEXT NOT NULL,
            max_points REAL NOT NULL,
            weight REAL NOT NULL,
            due_date TEXT,
            date_created TEXT DEFAULT (datetime('now')),
            description TEXT,
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        conn.commit()
        conn.close()
        print("✅ Basic database tables created successfully!")
        return True

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False

def init_enhanced_grades_db():
    """Initialize the enhanced grades database with all required tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create base grade tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grades (
            grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            assessment_id INTEGER,
            score REAL,
            letter_grade TEXT,
            submission_date TEXT,
            comments TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS module_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            final_score REAL,
            final_grade TEXT,
            completion_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # 1. Grade Curve Analysis Tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grade_statistics (
            stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER,
            mean REAL,
            median REAL,
            std_dev REAL,
            min_score REAL,
            max_score REAL,
            q1 REAL,
            q3 REAL,
            skewness REAL,
            kurtosis REAL,
            date_calculated TEXT,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS normalized_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade_id INTEGER,
            z_score REAL,
            percentile REAL,
            curved_score REAL,
            curved_letter TEXT,
            FOREIGN KEY (grade_id) REFERENCES grades (grade_id)
        )
        ''')

        # 2. Learning Outcome Tracking Tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_outcomes (
            outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT,
            outcome_code TEXT,
            description TEXT,
            category TEXT,
            importance INTEGER
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER,
            outcome_id INTEGER,
            weight REAL,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id),
            FOREIGN KEY (outcome_id) REFERENCES learning_outcomes (outcome_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS outcome_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            outcome_id INTEGER,
            achievement_level REAL,
            evidence TEXT,
            date_assessed TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (outcome_id) REFERENCES learning_outcomes (outcome_id)
        )
        ''')

        # 3. Competency-Based Assessment Tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competencies (
            competency_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            category TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competency_levels (
            level_id INTEGER PRIMARY KEY AUTOINCREMENT,
            competency_id INTEGER,
            level_name TEXT,
            level_value INTEGER,
            description TEXT,
            FOREIGN KEY (competency_id) REFERENCES competencies (competency_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_competencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER,
            competency_id INTEGER,
            weight REAL,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id),
            FOREIGN KEY (competency_id) REFERENCES competencies (competency_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_competencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            competency_id INTEGER,
            level_id INTEGER,
            evidence TEXT,
            assessment_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (competency_id) REFERENCES competencies (competency_id),
            FOREIGN KEY (level_id) REFERENCES competency_levels (level_id)
        )
        ''')

        # 4. Predictive Analytics Tables
        # If risk_factors was created by admin_support_schemas with a different schema,
        # rename it so we can create the grade-tracking version
        try:
            cursor.execute("SELECT name FROM risk_factors LIMIT 0")
        except sqlite3.OperationalError:
            try:
                cursor.execute('ALTER TABLE risk_factors RENAME TO admin_risk_factors')
            except sqlite3.OperationalError:
                pass

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_factors (
            factor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            weight REAL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_risk_assessment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            risk_score REAL,
            risk_level TEXT,
            assessment_date TEXT,
            prediction_model TEXT,
            confidence REAL,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            risk_assessment_id INTEGER,
            factor_id INTEGER,
            factor_value REAL,
            factor_contribution REAL,
            FOREIGN KEY (risk_assessment_id) REFERENCES student_risk_assessment (id),
            FOREIGN KEY (factor_id) REFERENCES risk_factors (factor_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS intervention_types (
            type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommended_interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            risk_assessment_id INTEGER,
            intervention_type_id INTEGER,
            priority INTEGER,
            notes TEXT,
            FOREIGN KEY (risk_assessment_id) REFERENCES student_risk_assessment (id),
            FOREIGN KEY (intervention_type_id) REFERENCES intervention_types (type_id)
        )
        ''')

        # Insert default risk factors if they don't exist
        cursor.execute('SELECT COUNT(*) FROM risk_factors')
        if cursor.fetchone()[0] == 0:
            risk_factors = [
                ('Low GPA', 'Overall GPA below 2.0', 1.0),
                ('Failed Assessments', 'Multiple failed assessments', 0.8),
                ('Missed Submissions', 'Assignments not submitted', 0.7),
                ('Late Submissions', 'Consistently late submissions', 0.5),
                ('Low Attendance', 'Poor attendance record', 0.6),
                ('Declining Performance', 'Grades dropping over time', 0.7)
            ]
            cursor.executemany('''
            INSERT INTO risk_factors (name, description, weight)
            VALUES (?, ?, ?)
            ''', risk_factors)

        # Insert default intervention types if they don't exist
        cursor.execute('SELECT COUNT(*) FROM intervention_types')
        if cursor.fetchone()[0] == 0:
            intervention_types = [
                ('Academic Advising', 'Schedule a meeting with academic advisor'),
                ('Tutoring', 'Recommend tutoring sessions for specific subjects'),
                ('Study Skills Workshop', 'Workshop on time management and study techniques'),
                ('Mentoring', 'Pair with a peer mentor or faculty mentor'),
                ('Counseling', 'Refer to academic or personal counseling services'),
                ('Modified Schedule', 'Suggest course load reduction or schedule adjustment')
            ]
            cursor.executemany('''
            INSERT INTO intervention_types (name, description)
            VALUES (?, ?)
            ''', intervention_types)

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

def display_enhanced_grade_menu():
    """Display the enhanced grade and performance tracking menu and handle user choices"""
    # Initialize basic tables first
    if not init_basic_database():
        print(get_text('grades.db_init_failed', default='Failed to initialize basic database tables.'))
        return

    # Initialize all tables for the enhanced system
    init_enhanced_grades_db()

    while True:
        print(f"\n{get_text('grades.title', default='Grade and Performance Tracking')}:")
        print(f"\n--- {get_text('grades.sections.grade_mgmt', default='Grade Management')} ---")
        print(f"1. {get_text('grades.menu.record_grades', default='Record Grades for Assessment')}")
        print(f"2. {get_text('grades.menu.update_grades', default='Update Existing Grades')}")
        print(f"3. {get_text('grades.menu.view_grades', default='View Student Grades')}")
        print(f"4. {get_text('grades.menu.calculate_gpa', default='Calculate GPA')}")
        print(f"5. {get_text('grades.menu.generate_transcript', default='Generate Transcript')}")
        print(f"\n--- {get_text('grades.sections.advanced', default='Advanced Features')} ---")
        print(f"6. {get_text('grades.menu.curve_analysis', default='Grade Curve Analysis')}")
        print(f"7. {get_text('grades.menu.learning_outcomes', default='Learning Outcome Tracking')}")
        print(f"8. {get_text('grades.menu.competency', default='Competency-Based Assessment')}")
        print(f"9. {get_text('grades.menu.predictive', default='Predictive Analytics & Early Warning')}")
        print(f"10. {get_text('grades.menu.performance', default='Performance Analysis')}")
        print(f"\n--- {get_text('grades.sections.settings', default='Settings')} ---")
        print(f"11. {get_text('grades.menu.language', default='Language')}")
        print(f"12. {get_text('grades.menu.return_main', default='Return to Main Menu')}")

        choice = input(f"{get_text('grades.enter_choice', default='Enter your choice')} (1-12): ")

        if choice == '1':
            record_assessment_grades()
        elif choice == '2':
            update_grades()
        elif choice == '3':
            view_student_grades()
        elif choice == '4':
            calculate_gpa()
        elif choice == '5':
            generate_transcript()
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
            display_language_menu_option()
        elif choice == '12':
            print(get_text('grades.returning', default='Returning to main menu...'))
            break
        else:
            print(get_text('grades.invalid_choice', default='Invalid choice. Please try again.'))

def grade_curve_analysis_menu():
    """Display the grade curve analysis menu and handle user choices"""
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

def competency_assessment_menu():
    """Display the competency-based assessment menu and handle user choices"""
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

def predictive_analytics_menu():
    """Display the predictive analytics menu and handle user choices"""
    while True:
        print("\nPredictive Analytics & Early Warning:")
        print("1. Student Risk Assessment")
        print("2. Performance Prediction Models")
        print("3. Early Warning System")
        print("4. Intervention Recommendations")
        print("5. Success Probability Calculator")
        print("6. Dropout Risk Analysis")
        print("7. Grade Prediction")
        print("8. Trend Forecasting")
        print("9. Generate Risk Report")
        print("10. Return to Grade Menu")

        choice = input("Enter your choice (1-10): ")

        if choice == '1':
            student_risk_assessment()
        elif choice == '2':
            performance_prediction_models()
        elif choice == '3':
            early_warning_system()
        elif choice == '4':
            intervention_recommendations()
        elif choice == '5':
            success_probability_calculator()
        elif choice == '6':
            dropout_risk_analysis()
        elif choice == '7':
            grade_prediction()
        elif choice == '8':
            trend_forecasting()
        elif choice == '9':
            generate_risk_report()
        elif choice == '10':
            print("Returning to grade menu...")
            break
        else:
            print("Invalid choice. Please try again.")

def performance_analysis_menu():
    """Display the performance analysis menu and handle user choices"""
    while True:
        print("\nPerformance Analysis:")
        print("1. Identify At-Risk Students")
        print("2. Module Performance Summary")
        print("3. Assessment Performance Summary")
        print("4. Grade Distribution Analysis")
        print("5. Student Progress Tracking")
        print("6. Comparative Performance Analysis")
        print("7. Performance Trends Over Time")
        print("8. Generate Performance Dashboard")
        print("9. Return to Grade Menu")

        choice = input("Enter your choice (1-9): ")

        if choice == '1':
            identify_at_risk_students()
        elif choice == '2':
            module_performance_summary()
        elif choice == '3':
            assessment_performance_summary()
        elif choice == '4':
            grade_distribution_analysis()
        elif choice == '5':
            student_progress_tracking()
        elif choice == '6':
            comparative_performance_analysis()
        elif choice == '7':
            performance_trends_analysis()
        elif choice == '8':
            generate_performance_dashboard()
        elif choice == '9':
            print("Returning to grade menu...")
            break
        else:
            print("Invalid choice. Please try again.")
