from university_system.infrastructure.database.db import sqlite3, DatabaseManager
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
from university_system.infrastructure.database.db import get_connection
matplotlib.use('Agg')

# Grade system constants
GRADE_SYSTEMS = {
    "letter": {
        "A+": 4.3,
        "A": 4.0,
        "A-": 3.7,
        "B+": 3.3,
        "B": 3.0,
        "B-": 2.7,
        "C+": 2.3,
        "C": 2.0,
        "C-": 1.7,
        "D+": 1.3,
        "D": 1.0,
        "D-": 0.7,
        "F": 0.0
    }
}

def percentage_to_letter(percentage):
    """Convert a percentage score to a letter grade"""
    if percentage >= 97:
        return "A+"
    elif percentage >= 93:
        return "A"
    elif percentage >= 90:
        return "A-"
    elif percentage >= 87:
        return "B+"
    elif percentage >= 83:
        return "B"
    elif percentage >= 80:
        return "B-"
    elif percentage >= 77:
        return "C+"
    elif percentage >= 73:
        return "C"
    elif percentage >= 70:
        return "C-"
    elif percentage >= 67:
        return "D+"
    elif percentage >= 63:
        return "D"
    elif percentage >= 60:
        return "D-"
    else:
        return "F"

def letter_to_percentage(letter_grade):
    """Convert a letter grade to a percentage (midpoint of range)"""
    grade_midpoints = {
        "A+": 98.5,
        "A": 95.0,
        "A-": 91.5,
        "B+": 85.0,
        "B": 81.5,
        "B-": 78.5,
        "C+": 75.0,
        "C": 71.5,
        "C-": 68.5,
        "D+": 65.0,
        "D": 61.5,
        "D-": 58.5,
        "F": 30.0  # Arbitrary low value for F
    }
    return grade_midpoints.get(letter_grade, 0)

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
        print("Failed to initialize basic database tables.")
        return
        
    # Initialize all tables for the enhanced system
    init_enhanced_grades_db()
    
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
            print("Returning to main menu...")
            break
        else:
            print("Invalid choice. Please try again.")

def select_student(cursor):
    """Let user pick a student; returns student_id or None."""
    cursor.execute('''
        SELECT student_id, first_name, middle_name, last_name, course
        FROM students
        ORDER BY last_name, first_name
    ''')
    rows = cursor.fetchall()
    if not rows:
        print("No students found.")
        return None

    print("\nAvailable Students:")
    for i, (sid, fname, mname, lname, course) in enumerate(rows, start=1):
        middle_initial = mname[0] + ". " if mname else ""
        full_name = f"{fname} {middle_initial}{lname}"
        print(f"{i}. {full_name} (ID: {sid}) - {course}")

    choice = input("Enter student number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(rows):
            print("Invalid selection.")
            return None
        return rows[idx][0]  # Return student_id
    except ValueError:
        print("Please enter a valid number.")
        return None

def calculate_trend_slope(values):
    """Calculate the trend slope for a list of values"""
    if len(values) < 2:
        return 0
    
    x = np.arange(len(values))
    slope = np.polyfit(x, values, 1)[0]
    return slope

def create_trend_visualization(daily_trends, monthly_trends, filename_prefix):
    """Create trend visualizations"""
    try:
        # Create directory if it doesn't exist
        plots_dir = 'statistics_plots'
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir)
        
        plt.figure(figsize=(12, 8))
        
        # Daily trends
        plt.subplot(2, 1, 1)
        dates = [trend[0] for trend in daily_trends]
        averages = [trend[1] for trend in daily_trends]
        
        plt.plot(dates, averages, marker='o', linewidth=1, markersize=3)
        plt.title('Daily Grade Trends')
        plt.xlabel('Date')
        plt.ylabel('Average Percentage')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        
        # Monthly trends
        plt.subplot(2, 1, 2)
        months = [trend[0] for trend in monthly_trends]
        monthly_averages = [trend[1] for trend in monthly_trends]
        
        plt.bar(months, monthly_averages, color='lightblue')
        plt.title('Monthly Grade Trends')
        plt.xlabel('Month')
        plt.ylabel('Average Percentage')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save the plot
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        plot_filename = f"{plots_dir}/{filename_prefix}_{timestamp}.png"
        plt.savefig(plot_filename)
        plt.close()
        
        print(f"Trend visualization saved to {plot_filename}")
        
    except Exception as e:
        print(f"Error creating trend visualization: {e}")

def export_batch_predictions(predictions, filename_prefix):
    """Export batch predictions to CSV"""
    try:
        # Create the exports directory if it doesn't exist
        exports_dir = 'grade_exports'
        if not os.path.exists(exports_dir):
            os.makedirs(exports_dir)
        
        # Generate a filename based on current timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{exports_dir}/{filename_prefix}_{timestamp}.csv"
        
        with open(filename, 'w', newline='') as csvfile:
            if predictions:
                fieldnames = predictions[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(predictions)
        
        print(f"Predictions exported to {filename}")
        
    except Exception as e:
        print(f"Error exporting predictions: {e}")

def extract_student_features(cursor, student_id):
    """Extract features for a student for prediction models"""
    try:
        # Get assessment scores
        cursor.execute('''
        SELECT g.score / a.max_points * 100 as percentage
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        WHERE g.student_id = ?
        ''', (student_id,))
        
        scores = [row[0] for row in cursor.fetchall()]
        
        if not scores:
            return None
        
        # Calculate basic features
        avg_score = np.mean(scores)
        assessment_count = len(scores)
        failed_count = sum(1 for score in scores if score < 60)
        
        # Get total possible assessments for submission rate
        cursor.execute('''
        SELECT COUNT(DISTINCT a.assessment_id)
        FROM assessments a
        JOIN student_modules sm ON a.module_code = sm.module_code
        WHERE sm.student_id = ?
        ''', (student_id,))
        
        total_assessments = cursor.fetchone()[0]
        submission_rate = assessment_count / total_assessments if total_assessments > 0 else 0
        
        return {
            'avg_score': avg_score,
            'submission_rate': submission_rate,
            'assessment_count': assessment_count,
            'failed_count': failed_count
        }
        
    except sqlite3.Error as e:
        print(f"Error extracting features for student {student_id}: {e}")
        return None

def assess_student_risk(cursor, student_id, first_name, last_name, course):
    """Assess risk level for a specific student"""
    try:
        # Calculate current GPA
        gpa, credits, _ = calculate_student_gpa(cursor, student_id)
        
        # Initialize risk factors
        risk_factors = []
        risk_score = 0
        
        # Factor 1: Low GPA
        if gpa and gpa < 2.0:
            risk_factors.append("Low GPA")
            risk_score += 30
        elif gpa and gpa < 2.5:
            risk_factors.append("Below Average GPA")
            risk_score += 15
        
        # Factor 2: Failed assessments
        cursor.execute('''
        SELECT COUNT(*) FROM grades g
        WHERE g.student_id = ? AND g.letter_grade = 'F'
        ''', (student_id,))
        
        failed_count = cursor.fetchone()[0]
        if failed_count > 2:
            risk_factors.append("Multiple Failed Assessments")
            risk_score += 25
        elif failed_count > 0:
            risk_factors.append("Some Failed Assessments")
            risk_score += 10
        
        # Factor 3: Declining performance trend
        cursor.execute('''
        SELECT g.score / a.max_points * 100
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        WHERE g.student_id = ?
        ORDER BY g.submission_date DESC
        LIMIT 5
        ''', (student_id,))
        
        recent_scores = [row[0] for row in cursor.fetchall()]
        if len(recent_scores) >= 3:
            trend_slope = calculate_trend_slope(recent_scores[::-1])  # Reverse for chronological order
            if trend_slope < -5:  # Declining by more than 5% per assessment
                risk_factors.append("Declining Performance")
                risk_score += 20
        
        # Factor 4: Low submission rate
        features = extract_student_features(cursor, student_id)
        if features and features['submission_rate'] < 0.8:
            risk_factors.append("Low Submission Rate")
            risk_score += 15
        
        # Determine risk level
        if risk_score >= 50:
            risk_level = "High"
        elif risk_score >= 30:
            risk_level = "Medium"
        elif risk_score >= 15:
            risk_level = "Low"
        else:
            risk_level = "Minimal"
        
        return {
            'student_id': student_id,
            'name': f"{first_name} {last_name}",
            'course': course,
            'gpa': gpa,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors
        }
        
    except sqlite3.Error as e:
        print(f"Error assessing risk for student {student_id}: {e}")
        return None

def select_assessment(cursor):
    """Let user pick an assessment; returns assessment_id or None."""
    cursor.execute('''
        SELECT assessment_id, assessment_name, module_code
        FROM assessments
        ORDER BY date_created DESC
    ''')
    rows = cursor.fetchall()
    if not rows:
        print("No assessments found.")
        return None

    print("\nAvailable Assessments:")
    for i, (aid, name, module) in enumerate(rows, start=1):
        print(f"{i}. [{module}] {name} (ID: {aid})")

    choice = input("Enter assessment number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(rows):
            print("Invalid selection.")
            return None
        return rows[idx][0]
    except ValueError:
        print("Please enter a valid number.")
        return None

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

def calculate_student_gpa(cursor, student_id):
    """Calculate the GPA for a specific student"""
    try:
        # Get module grades for this student
        cursor.execute('''
        SELECT mg.module_code, m.module_name, mg.final_grade
        FROM module_grades mg
        JOIN modules m ON mg.module_code = m.module_code
        WHERE mg.student_id = ?
        ''', (student_id,))
        
        module_grades = cursor.fetchall()
        
        if not module_grades:
            return None, 0, []
            
        total_points = 0
        total_modules = 0
        
        detailed_grades = []
        
        for module_code, module_name, grade in module_grades:
            if grade:
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

def generate_transcript():
    """Generate a transcript for a student"""
    print("\nGenerate Transcript")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        student_id = select_student(cursor)
        if not student_id:
            conn.close()
            return
        
        # Get student info
        cursor.execute('''
        SELECT first_name, middle_name, last_name, course, email_address, gender, dob
        FROM students
        WHERE student_id = ?
        ''', (student_id,))
        
        student = cursor.fetchone()
        
        if not student:
            print(f"Student with ID {student_id} not found.")
            conn.close()
            return
            
        first_name, middle_name, last_name, course, email, gender, dob = student
        
        # Calculate GPA
        gpa, credits, module_grades = calculate_student_gpa(cursor, student_id)
        
        if gpa is None:
            print(f"No grades found for student {first_name} {last_name} (ID: {student_id}).")
            transcript_anyway = input("Generate transcript anyway? (y/n): ").strip().lower()
            if transcript_anyway != 'y':
                conn.close()
                return
            gpa = 0
        
        # Get all assessment grades
        cursor.execute('''
        SELECT a.module_code, m.module_name, a.assessment_name, a.assessment_type, a.weight,
               g.score, a.max_points, g.letter_grade, g.submission_date
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        JOIN modules m ON a.module_code = m.module_code
        WHERE g.student_id = ?
        ORDER BY a.module_code, a.assessment_name
        ''', (student_id,))
        
        assessment_grades = cursor.fetchall()
        
        # Create the exports directory if it doesn't exist
        exports_dir = 'transcripts'
        if not os.path.exists(exports_dir):
            os.makedirs(exports_dir)
        
        # Generate a filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{exports_dir}/transcript_{student_id}_{timestamp}.pdf"
        
        # Ask for transcript format
        format_choice = input("\nTranscript format: (1) Simple or (2) Detailed? Enter 1 or 2: ").strip()
        
        if format_choice not in ['1', '2']:
            print("Invalid format choice. Using simple format.")
            format_choice = '1'
        
        # Generate PDF transcript
        create_transcript_pdf(
            filename,
            student_id,
            first_name,
            middle_name,
            last_name,
            course,
            email,
            gender,
            dob,
            gpa,
            credits,
            module_grades,
            assessment_grades if format_choice == '2' else None
        )
        
        print(f"\nTranscript generated successfully: {filename}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def create_transcript_pdf(filename, student_id, first_name, middle_name, last_name, course, email, gender, dob, gpa, credits, module_grades, assessment_grades=None):
    """Create a PDF transcript for a student"""
    try:
        # Create a PDF document
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Add university header
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Heading1'],
            alignment=1,  # Center alignment
            fontSize=16,
            spaceAfter=20
        )
        elements.append(Paragraph("University Student Transcript", header_style))
        
        # Add current date
        date_style = ParagraphStyle(
            'Date',
            parent=styles['Normal'],
            alignment=1,  # Center alignment
            fontSize=10,
            spaceAfter=20
        )
        current_date = datetime.now().strftime('%B %d, %Y')
        elements.append(Paragraph(f"Generated on {current_date}", date_style))
        
        # Add student information
        elements.append(Paragraph("Student Information", styles['Heading2']))
        
        middle_initial = middle_name[0] + ". " if middle_name else ""
        full_name = f"{first_name} {middle_initial}{last_name}"
        
        student_info = [
            ['Name:', full_name],
            ['ID:', student_id],
            ['Course:', course],
            ['Email:', email],
            ['Gender:', gender.capitalize()],
            ['Date of Birth:', dob],
            ['GPA:', f"{gpa:.2f}" if gpa else "N/A"],
            ['Credits Completed:', str(credits)]
        ]
        
        student_table = Table(student_info, colWidths=[100, 400])
        student_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))
        
        elements.append(student_table)
        elements.append(Spacer(1, 20))
        
        # Add module grades
        elements.append(Paragraph("Module Grades", styles['Heading2']))
        
        if module_grades:
            module_header = [['Module Code', 'Module Name', 'Grade', 'GPA Points']]
            module_data = [[m[0], m[1], m[2], f"{m[3]:.2f}"] for m in module_grades]
            
            module_table = Table(module_header + module_data, colWidths=[80, 280, 60, 80])
            module_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (3, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (3, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (2, 0), (3, -1), 'CENTER'),
                ('GRID', (0, 0), (3, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(module_table)
        else:
            elements.append(Paragraph("No module grades recorded.", styles['Normal']))
            
        elements.append(Spacer(1, 20))
        
        # Add assessment grades if detailed format
        if assessment_grades:
            elements.append(Paragraph("Assessment Grades", styles['Heading2']))
            
            # Group assessments by module
            modules = {}
            for grade in assessment_grades:
                module_code = grade[0]
                if module_code not in modules:
                    modules[module_code] = {
                        'name': grade[1],
                        'assessments': []
                    }
                
                # Add assessment to this module
                assessment_name = grade[2]
                assessment_type = grade[3]
                weight = grade[4]
                score = grade[5]
                max_points = grade[6]
                letter_grade = grade[7]
                submission_date = grade[8]
                
                percentage = (score / max_points) * 100
                score_display = f"{score}/{max_points} ({percentage:.1f}%)"
                
                modules[module_code]['assessments'].append([
                    assessment_name,
                    assessment_type,
                    f"{weight}%",
                    score_display,
                    letter_grade,
                    submission_date
                ])
            
            # Add each module's assessments to the PDF
            for module_code, module_data in modules.items():
                elements.append(Paragraph(f"{module_code} - {module_data['name']}", styles['Heading3']))
                
                assessment_header = [['Assessment', 'Type', 'Weight', 'Score', 'Grade', 'Date']]
                
                if module_data['assessments']:
                    assessment_table = Table(
                        assessment_header + module_data['assessments'],
                        colWidths=[150, 80, 50, 100, 50, 70]
                    )
                    assessment_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (5, 0), 'Helvetica-Bold'),
                        ('BACKGROUND', (0, 0), (5, 0), colors.lightgrey),
                        ('ALIGN', (2, 0), (5, -1), 'CENTER'),
                        ('GRID', (0, 0), (5, -1), 0.5, colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    
                    elements.append(assessment_table)
                else:
                    elements.append(Paragraph("No assessments recorded for this module.", styles['Normal']))
                
                elements.append(Spacer(1, 10))
        
        # Add GPA interpretation guide
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("GPA Interpretation", styles['Heading2']))
        
        gpa_guide = [
            ['GPA Range', 'Letter Grade', 'Performance Level'],
            ['4.0 - 4.3', 'A, A+', 'Excellent'],
            ['3.7 - 3.9', 'A-', 'Very Good'],
            ['3.3 - 3.6', 'B+', 'Good'],
            ['3.0 - 3.2', 'B', 'Above Average'],
            ['2.7 - 2.9', 'B-', 'Average'],
            ['2.3 - 2.6', 'C+', 'Fair'],
            ['2.0 - 2.2', 'C', 'Satisfactory'],
            ['1.7 - 1.9', 'C-', 'Below Average'],
            ['1.0 - 1.6', 'D+, D, D-', 'Poor'],
            ['0.0 - 0.9', 'F', 'Failing']
        ]
        
        gpa_table = Table(gpa_guide, colWidths=[100, 100, 300])
        gpa_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (2, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (2, 0), 'CENTER'),
            ('ALIGN', (0, 1), (1, -1), 'CENTER'),
            ('GRID', (0, 0), (2, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(gpa_table)
        
        # Add footer
        elements.append(Spacer(1, 30))
        footer_text = "This transcript is an unofficial record of academic performance. " + \
                      "An official transcript must bear the seal and signature of the University Registrar."
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=1  # Center alignment
        )
        elements.append(Paragraph(footer_text, footer_style))
        
        # Build the PDF
        doc.build(elements)
        return True
        
    except Exception as e:
        print(f"Error creating transcript: {e}")
        return False

def letter_to_gpa(letter_grade):
    """Convert a letter grade to a GPA value"""
    if letter_grade in GRADE_SYSTEMS["letter"]:
        return GRADE_SYSTEMS["letter"][letter_grade]
    
    return 0  # Default to 0 if no match or F

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

def calculate_assessment_statistics():
    """Calculate statistical measures for an assessment's grades"""
    print("\nCalculate Assessment Statistics")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get assessment to analyze
        assessment_id = select_assessment(cursor)
        if not assessment_id:
            conn.close()
            return
        
        # Get the assessment details
        cursor.execute('''
        SELECT assessment_name, module_code, max_points
        FROM assessments
        WHERE assessment_id = ?
        ''', (assessment_id,))
        
        assessment = cursor.fetchone()
        if not assessment:
            print("Assessment not found.")
            conn.close()
            return
        
        assessment_name, module_code, max_points = assessment
        
        # Get all grades for this assessment
        cursor.execute('''
        SELECT score
        FROM grades
        WHERE assessment_id = ?
        ''', (assessment_id,))
        
        grades = cursor.fetchall()
        
        if not grades:
            print(f"No grades found for assessment {assessment_name}.")
            conn.close()
            return
        
        # Convert to a numpy array for statistical calculations
        scores = np.array([g[0] for g in grades])
        
        # Calculate statistics
        mean = np.mean(scores)
        median = np.median(scores)
        std_dev = np.std(scores)
        min_score = np.min(scores)
        max_score = np.max(scores)
        q1 = np.percentile(scores, 25)
        q3 = np.percentile(scores, 75)
        
        # Calculate skewness and kurtosis if there are enough samples
        if len(scores) >= 3:
            skewness = stats.skew(scores)
            kurtosis = stats.kurtosis(scores)
        else:
            skewness = 0
            kurtosis = 0
        
        # Insert or update the statistics in the database
        date_calculated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if statistics already exist for this assessment
        cursor.execute('''
        SELECT stat_id
        FROM grade_statistics
        WHERE assessment_id = ?
        ''', (assessment_id,))
        
        existing_stat = cursor.fetchone()
        
        if existing_stat:
            cursor.execute('''
            UPDATE grade_statistics
            SET mean = ?, median = ?, std_dev = ?, min_score = ?, max_score = ?,
                q1 = ?, q3 = ?, skewness = ?, kurtosis = ?, date_calculated = ?
            WHERE assessment_id = ?
            ''', (mean, median, std_dev, min_score, max_score, q1, q3, skewness, kurtosis, date_calculated, assessment_id))
        else:
            cursor.execute('''
            INSERT INTO grade_statistics
            (assessment_id, mean, median, std_dev, min_score, max_score, q1, q3, skewness, kurtosis, date_calculated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (assessment_id, mean, median, std_dev, min_score, max_score, q1, q3, skewness, kurtosis, date_calculated))
        
        conn.commit()
        
        # Display the statistics
        print("\nStatistical Analysis Results:")
        print(f"Assessment: {assessment_name} [{module_code}]")
        print(f"Number of grades: {len(scores)}")
        print(f"Mean score: {mean:.2f} / {max_points} ({(mean/max_points)*100:.1f}%)")
        print(f"Median score: {median:.2f} / {max_points} ({(median/max_points)*100:.1f}%)")
        print(f"Standard deviation: {std_dev:.2f}")
        print(f"Range: {min_score:.2f} - {max_score:.2f}")
        print(f"1st quartile (Q1): {q1:.2f}")
        print(f"3rd quartile (Q3): {q3:.2f}")
        print(f"Interquartile range (IQR): {(q3-q1):.2f}")
        print(f"Skewness: {skewness:.2f}")
        print(f"Kurtosis: {kurtosis:.2f}")
        
        # Interpret the statistics
        print("\nInterpretation:")
        
        # Interpret distribution shape
        if abs(skewness) < 0.5:
            print("- The grade distribution is approximately symmetric.")
        elif skewness < -0.5:
            print("- The grade distribution is skewed to the left (more high scores).")
        else:
            print("- The grade distribution is skewed to the right (more low scores).")
        
        if kurtosis < -0.5:
            print("- The distribution is platykurtic (flatter than normal, with fewer extreme scores).")
        elif kurtosis > 0.5:
            print("- The distribution is leptokurtic (more peaked than normal, with more extreme scores).")
        else:
            print("- The distribution has a normal-like kurtosis.")
        
        # Interpret performance
        if mean > 0.7 * max_points:
            print("- Overall performance is good, with an average above 70%.")
        elif mean < 0.5 * max_points:
            print("- Overall performance is concerning, with an average below 50%.")
        
        if std_dev > 0.2 * max_points:
            print("- There is high variability in student performance.")
        elif std_dev < 0.1 * max_points:
            print("- Student performance is relatively consistent.")
        
        # Would the user like to visualize the distribution?
        visualize = input("\nWould you like to visualize the grade distribution? (y/n): ").strip().lower()
        
        if visualize == 'y':
            # Create a directory for the plots if it doesn't exist
            plots_dir = 'statistics_plots'
            if not os.path.exists(plots_dir):
                os.makedirs(plots_dir)
            
            # Generate a histogram and save it
            plt.figure(figsize=(12, 6))
            
            # Create histogram with KDE
            sns.histplot(scores, kde=True, color='skyblue')
            
            # Add vertical lines for key statistics
            plt.axvline(mean, color='r', linestyle='--', label=f'Mean: {mean:.2f}')
            plt.axvline(median, color='g', linestyle='-.', label=f'Median: {median:.2f}')
            plt.axvline(q1, color='orange', linestyle=':', label=f'Q1: {q1:.2f}')
            plt.axvline(q3, color='orange', linestyle=':', label=f'Q3: {q3:.2f}')
            
            # Add title and labels
            plt.title(f'Grade Distribution for {assessment_name}')
            plt.xlabel('Score')
            plt.ylabel('Frequency')
            plt.legend()
            
            # Add statistical annotations
            stats_text = f"Mean: {mean:.2f}\nMedian: {median:.2f}\nStd Dev: {std_dev:.2f}\nMin: {min_score:.2f}\nMax: {max_score:.2f}"
            plt.annotate(stats_text, xy=(0.02, 0.95), xycoords='axes fraction', 
                       bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8))
            
            # Ensure the x-axis covers the full range of possible scores
            plt.xlim(0, max_points)
            
            # Save the plot
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            plot_filename = f"{plots_dir}/grade_distribution_{assessment_id}_{timestamp}.png"
            plt.savefig(plot_filename)
            plt.close()
            
            print(f"\nVisualization saved to {plot_filename}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def normalize_assessment_grades():
    """Normalize grades for an assessment using z-scores and percentiles"""
    print("\nNormalize Assessment Grades")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get assessment to normalize
        assessment_id = select_assessment(cursor)
        if not assessment_id:
            conn.close()
            return
        
        # Get the assessment details
        cursor.execute('''
        SELECT assessment_name, module_code, max_points
        FROM assessments
        WHERE assessment_id = ?
        ''', (assessment_id,))
        
        assessment = cursor.fetchone()
        if not assessment:
            print("Assessment not found.")
            conn.close()
            return
        
        assessment_name, module_code, max_points = assessment
        
        # Get all grades for this assessment
        cursor.execute('''
        SELECT g.grade_id, g.student_id, s.first_name, s.last_name, g.score, g.letter_grade
        FROM grades g
        JOIN students s ON g.student_id = s.student_id
        WHERE g.assessment_id = ?
        ''', (assessment_id,))
        
        grades = cursor.fetchall()
        
        if not grades:
            print(f"No grades found for assessment {assessment_name}.")
            conn.close()
            return
        
        # Extract scores for statistical calculations
        grade_ids = [g[0] for g in grades]
        student_ids = [g[1] for g in grades]
        student_names = [f"{g[2]} {g[3]}" for g in grades]
        scores = np.array([g[4] for g in grades])
        letter_grades = [g[5] for g in grades]
        
        # Calculate mean and standard deviation
        mean = np.mean(scores)
        std_dev = np.std(scores)
        
        if std_dev == 0:  # Handle case where all scores are the same
            print("Cannot normalize grades: all scores are identical.")
            conn.close()
            return
        
        # Calculate z-scores
        z_scores = [(score - mean) / std_dev for score in scores]
        
        # Calculate percentiles
        percentiles = [stats.percentileofscore(scores, score) for score in scores]
        
        # Ask about curve method
        print("\nCurve Methods:")
        print("1. Z-score to percentage (mean becomes target %, maintain spread)")
        print("2. Linear scaling (stretch to fill range)")
        print("3. Bell curve (redistribute based on normal distribution)")
        curve_method = input("Select curve method (1-3), or 0 to skip curving: ")
        
        curved_scores = []
        curved_letters = []
        
        if curve_method == "1":
            # Z-score to percentage
            target_mean = float(input("Enter target mean percentage (e.g., 75): "))
            target_mean = min(max(target_mean, 0), 100)  # Constrain between 0 and 100
            target_std = float(input("Enter target standard deviation (e.g., 10): "))
            
            curved_scores = [(z * target_std + target_mean) * max_points / 100 for z in z_scores]
            # Constrain to valid range
            curved_scores = [min(max(score, 0), max_points) for score in curved_scores]
            # Calculate letter grades
            curved_letters = [percentage_to_letter((score / max_points) * 100) for score in curved_scores]
            
        elif curve_method == "2":
            # Linear scaling
            min_score = min(scores)
            max_score = max(scores)
            
            if max_score == min_score:
                print("Cannot apply linear scaling: all scores are identical.")
                conn.close()
                return
            
            target_min = float(input("Enter target minimum percentage (e.g., 50): "))
            target_min = min(max(target_min, 0), 100)  # Constrain between 0 and 100
            target_max = float(input("Enter target maximum percentage (e.g., 100): "))
            target_max = min(max(target_max, target_min), 100)  # Constrain between target_min and 100
            
            # Linear transformation
            curved_scores = []
            for score in scores:
                normalized = (score - min_score) / (max_score - min_score)  # 0 to 1
                scaled = normalized * (target_max - target_min) + target_min  # target_min to target_max
                curved_scores.append(scaled * max_points / 100)
            
            # Calculate letter grades
            curved_letters = [percentage_to_letter((score / max_points) * 100) for score in curved_scores]
            
        elif curve_method == "3":
            # Bell curve
            target_mean = float(input("Enter target mean grade (e.g., 75): "))
            target_mean = min(max(target_mean, 0), 100)  # Constrain between 0 and 100
            target_std = float(input("Enter target standard deviation (e.g., 10): "))
            
            # Select grade distribution
            print("\nGrade Distribution:")
            print("1. Custom percentages for each grade")
            print("2. Normal distribution based on target mean and std dev")
            dist_method = input("Select distribution method (1-2): ")
            
            if dist_method == "1":
                # Custom percentages
                percentages = {}
                grades = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]
                total = 0
                
                print("\nEnter percentage for each grade (total must equal 100%):")
                for grade in grades:
                    while True:
                        try:
                            pct = float(input(f"{grade}: "))
                            if pct < 0:
                                print("Percentage cannot be negative.")
                                continue
                            percentages[grade] = pct
                            total += pct
                            break
                        except ValueError:
                            print("Please enter a valid number.")
                
                if abs(total - 100) > 0.01:
                    print(f"Error: Percentages sum to {total}%, not 100%.")
                    conn.close()
                    return
                
                # Sort scores and assign grades based on percentiles
                sorted_indices = np.argsort(scores)
                curved_letters = [""] * len(scores)
                
                current_percentile = 0
                for grade in reversed(grades):  # Start with highest grade
                    grade_percentile = percentages[grade]
                    count = int(round(len(scores) * grade_percentile / 100))
                    
                    # Assign this grade to the next 'count' students in sorted order
                    for i in range(count):
                        if current_percentile + i < len(sorted_indices):
                            idx = sorted_indices[-(current_percentile + i + 1)]  # Reverse to get highest scores first
                            curved_letters[idx] = grade
                    
                    current_percentile += count
                
                # Fill any unassigned (due to rounding) with F
                for i in range(len(curved_letters)):
                    if curved_letters[i] == "":
                        curved_letters[i] = "F"
                
                # Back-calculate scores from letters (midpoint of letter range)
                curved_scores = []
                for letter in curved_letters:
                    percentage = letter_to_percentage(letter)
                    curved_scores.append(percentage * max_points / 100)
                
            else:
                # Normal distribution
                # Compute the z-scores needed for the desired grade cutoffs
                grade_cutoffs = {
                    "A+": 97,
                    "A": 93,
                    "A-": 90,
                    "B+": 87,
                    "B": 83,
                    "B-": 80,
                    "C+": 77,
                    "C": 73,
                    "C-": 70,
                    "D+": 67,
                    "D": 63,
                    "D-": 60,
                    "F": 0
                }
                
                # Adjust cutoffs based on target mean and std dev
                adjusted_cutoffs = {}
                for grade, cutoff in grade_cutoffs.items():
                    z = (cutoff - target_mean) / target_std
                    adjusted_cutoffs[grade] = z
                
                # Assign grades based on z-scores
                curved_letters = []
                for z in z_scores:
                    assigned_grade = "F"
                    for grade, cutoff in sorted(adjusted_cutoffs.items(), key=lambda x: x[1], reverse=True):
                        if z >= cutoff:
                            assigned_grade = grade
                            break
                    curved_letters.append(assigned_grade)
                
                # Back-calculate scores from letters (midpoint of letter range)
                curved_scores = []
                for letter in curved_letters:
                    percentage = letter_to_percentage(letter)
                    curved_scores.append(percentage * max_points / 100)
        
        # Display the results
        if curve_method in ["1", "2", "3"]:
            print("\nNormalization Results:")
            print(f"{'Student':<30} {'Original Score':<15} {'Original Grade':<15} {'Z-Score':<10} {'Percentile':<12} {'Curved Score':<15} {'Curved Grade':<15}")
            print("-" * 100)
            
            for i in range(len(grades)):
                print(f"{student_names[i]:<30} {scores[i]:<15.2f} {letter_grades[i]:<15} {z_scores[i]:<10.2f} {percentiles[i]:<12.2f} {curved_scores[i]:<15.2f} {curved_letters[i]:<15}")
            
            # Save to database?
            save = input("\nSave these normalized grades to the database? (y/n): ").strip().lower()
            
            if save == 'y':
                # Clear any existing normalized grades for this assessment
                cursor.execute('''
                DELETE FROM normalized_grades WHERE grade_id IN (
                    SELECT grade_id FROM grades WHERE assessment_id = ?
                )
                ''', (assessment_id,))
                
                # Insert new normalized grades
                for i in range(len(grades)):
                    cursor.execute('''
                    INSERT INTO normalized_grades
                    (grade_id, z_score, percentile, curved_score, curved_letter)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (grade_ids[i], z_scores[i], percentiles[i], curved_scores[i], curved_letters[i]))
                
                # Update the actual grades?
                update_actual = input("Update the actual grades with the curved values? (y/n): ").strip().lower()
                
                if update_actual == 'y':
                    for i in range(len(grades)):
                        cursor.execute('''
                        UPDATE grades
                        SET score = ?, letter_grade = ?
                        WHERE grade_id = ?
                        ''', (curved_scores[i], curved_letters[i], grade_ids[i]))
                    
                    print("Actual grades updated with curved values.")
                    
                    # Update module grades for affected students
                    for student_id in set(student_ids):
                        # Get the module code for this assessment
                        cursor.execute('''
                        SELECT module_code FROM assessments WHERE assessment_id = ?
                        ''', (assessment_id,))
                        module_code = cursor.fetchone()[0]
                        
                        # Update the module grade
                        update_module_grade(cursor, student_id, module_code)
                
                conn.commit()
                print("Normalized grades saved to database.")
        else:
            # Just display z-scores and percentiles without curving
            print("\nNormalization Results (no curving applied):")
            print(f"{'Student':<30} {'Original Score':<15} {'Original Grade':<15} {'Z-Score':<10} {'Percentile':<12}")
            print("-" * 85)
            
            for i in range(len(grades)):
                print(f"{student_names[i]:<30} {scores[i]:<15.2f} {letter_grades[i]:<15} {z_scores[i]:<10.2f} {percentiles[i]:<12.2f}")
            
            # Save to database?
            save = input("\nSave these normalization statistics to the database? (y/n): ").strip().lower()
            
            if save == 'y':
                # Clear any existing normalized grades for this assessment
                cursor.execute('''
                DELETE FROM normalized_grades WHERE grade_id IN (
                    SELECT grade_id FROM grades WHERE assessment_id = ?
                )
                ''', (assessment_id,))
                
                # Insert new normalized grades (without curved values)
                for i in range(len(grades)):
                    cursor.execute('''
                    INSERT INTO normalized_grades
                    (grade_id, z_score, percentile, curved_score, curved_letter)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (grade_ids[i], z_scores[i], percentiles[i], scores[i], letter_grades[i]))
                
                conn.commit()
                print("Normalization statistics saved to database.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def view_grade_distribution():
    """Visualize grade distribution for an assessment or module"""
    print("\nView Grade Distribution")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Choose to view assessment or module distribution
        print("\nView distribution for:")
        print("1. Assessment")
        print("2. Module")
        choice = input("Enter your choice (1-2): ")
        
        if choice == '1':
            # View assessment distribution
            assessment_id = select_assessment(cursor)
            if not assessment_id:
                conn.close()
                return
            
            # Get the assessment details
            cursor.execute('''
            SELECT assessment_name, module_code, max_points
            FROM assessments
            WHERE assessment_id = ?
            ''', (assessment_id,))
            
            assessment = cursor.fetchone()
            if not assessment:
                print("Assessment not found.")
                conn.close()
                return
            
            assessment_name, module_code, max_points = assessment
            
            # Get all grades for this assessment
            cursor.execute('''
            SELECT g.score, g.letter_grade
            FROM grades g
            WHERE g.assessment_id = ?
            ''', (assessment_id,))
            
            grades = cursor.fetchall()
            
            if not grades:
                print(f"No grades found for assessment {assessment_name}.")
                conn.close()
                return
            
            scores = [float(g[0]) for g in grades]
            letters = [g[1] for g in grades]
            
            # Generate visualizations
            create_grade_visualizations(
                scores, 
                letters, 
                max_points, 
                f"Assessment: {assessment_name} [{module_code}]", 
                "assessment", 
                assessment_id
            )
            
        elif choice == '2':
            # View module distribution
            # Get list of modules
            cursor.execute('''
            SELECT DISTINCT m.module_code, m.module_name
            FROM modules m
            JOIN module_grades mg ON m.module_code = mg.module_code
            ORDER BY m.module_name
            ''')
            
            modules = cursor.fetchall()
            
            if not modules:
                print("No modules with grades found.")
                conn.close()
                return
            
            print("\nAvailable Modules:")
            for i, (code, name) in enumerate(modules):
                print(f"{i+1}. {code} - {name}")
            
            module_index = input("Enter module number: ")
            
            try:
                index = int(module_index) - 1
                if index < 0 or index >= len(modules):
                    print("Invalid module number.")
                    conn.close()
                    return
                
                module_code = modules[index][0]
                module_name = modules[index][1]
                
                # Get all final grades for this module
                cursor.execute('''
                SELECT mg.final_score, mg.final_grade
                FROM module_grades mg
                WHERE mg.module_code = ?
                ''', (module_code,))
                
                grades = cursor.fetchall()
                
                if not grades:
                    print(f"No grades found for module {module_name}.")
                    conn.close()
                    return
                
                scores = [float(g[0]) for g in grades]
                letters = [g[1] for g in grades]
                
                # Generate visualizations
                create_grade_visualizations(
                    scores, 
                    letters, 
                    100,  # Module grades are typically percentages
                    f"Module: {module_name} [{module_code}]", 
                    "module", 
                    module_code
                )
                
            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return
        else:
            print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def create_grade_visualizations(scores, letters, max_points, title, entity_type, entity_id):
    """Create visualizations for grade distribution"""
    try:
        # Create a directory for the plots if it doesn't exist
        plots_dir = 'statistics_plots'
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Calculate statistics
        scores_array = np.array(scores)
        mean = np.mean(scores_array)
        median = np.median(scores_array)
        std_dev = np.std(scores_array)
        
        # Convert scores to percentages for consistency
        percentages = [(score / max_points) * 100 for score in scores]
        
        # 1. Histogram of scores with density curve
        plt.figure(figsize=(12, 8))
        plt.subplot(2, 2, 1)
        sns.histplot(percentages, kde=True, color='skyblue')
        plt.axvline(mean / max_points * 100, color='r', linestyle='--', label=f'Mean: {mean:.2f}')
        plt.axvline(median / max_points * 100, color='g', linestyle='-.', label=f'Median: {median:.2f}')
        plt.title(f'Score Distribution - {title}')
        plt.xlabel('Percentage Score')
        plt.ylabel('Frequency')
        plt.legend()
        
        # 2. Letter grade distribution
        plt.subplot(2, 2, 2)
        letter_counts = {}
        for letter in letters:
            if letter in letter_counts:
                letter_counts[letter] += 1
            else:
                letter_counts[letter] = 1
        
        # Sort the letter grades in descending order (A+, A, A-, B+, etc.)
        sorted_letters = sorted(letter_counts.keys(), 
                                key=lambda x: float('inf') if x not in GRADE_SYSTEMS["letter"] else -GRADE_SYSTEMS["letter"][x])
        sorted_counts = [letter_counts[letter] for letter in sorted_letters]
        
        bars = plt.bar(sorted_letters, sorted_counts, color='lightgreen')
        plt.title(f'Letter Grade Distribution - {title}')
        plt.xlabel('Letter Grade')
        plt.ylabel('Count')
        
        # Add count labels on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.0f}', ha='center', va='bottom')
        
        # 3. Box plot of scores
        plt.subplot(2, 2, 3)
        plt.boxplot(percentages, vert=False, patch_artist=True, 
                   boxprops=dict(facecolor='lightblue'))
        plt.title(f'Box Plot of Scores - {title}')
        plt.xlabel('Percentage Score')
        plt.yticks([])  # Hide y-tick labels
        
        # 4. Normal probability plot (Q-Q plot)
        plt.subplot(2, 2, 4)
        stats.probplot(percentages, dist="norm", plot=plt)
        plt.title(f'Normal Probability Plot - {title}')
        
        # Adjust layout and save
        plt.tight_layout()
        
        plot_filename = f"{plots_dir}/grade_distribution_{entity_type}_{entity_id}_{timestamp}.png"
        plt.savefig(plot_filename)
        plt.close()
        
        print(f"\nVisualization saved to {plot_filename}")
        
        # Display statistics
        print("\nGrade Statistics:")
        print(f"Total Grades: {len(scores)}")
        print(f"Mean: {mean:.2f} ({mean/max_points*100:.1f}%)")
        print(f"Median: {median:.2f} ({median/max_points*100:.1f}%)")
        print(f"Standard Deviation: {std_dev:.2f} ({std_dev/max_points*100:.1f}%)")
        print(f"Min: {min(scores):.2f} ({min(scores)/max_points*100:.1f}%)")
        print(f"Max: {max(scores):.2f} ({max(scores)/max_points*100:.1f}%)")
        
        print("\nLetter Grade Distribution:")
        total = len(letters)
        for letter in sorted_letters:
            count = letter_counts[letter]
            percentage = (count / total) * 100
            print(f"{letter}: {count} ({percentage:.1f}%)")
        
    except Exception as e:
        print(f"Error creating visualizations: {e}")

def generate_assessment_stats_report(cursor, assessment_id, reports_dir, timestamp):
    """Generate a statistical report for a specific assessment"""
    try:
        # Get assessment details
        cursor.execute('''
        SELECT assessment_name, module_code, assessment_type, max_points, weight
        FROM assessments
        WHERE assessment_id = ?
        ''', (assessment_id,))
        
        assessment = cursor.fetchone()
        if not assessment:
            print("Assessment not found.")
            return
        
        assessment_name, module_code, assessment_type, max_points, weight = assessment
        
        # Get module name
        cursor.execute('''
        SELECT module_name
        FROM modules
        WHERE module_code = ?
        ''', (module_code,))
        
        module_name = cursor.fetchone()[0]
        
        # Get all grades for this assessment
        cursor.execute('''
        SELECT g.score, g.letter_grade
        FROM grades g
        WHERE g.assessment_id = ?
        ''', (assessment_id,))
        
        grades = cursor.fetchall()
        
        if not grades:
            print(f"No grades found for assessment {assessment_name}.")
            return
        
        scores = [float(g[0]) for g in grades]
        letters = [g[1] for g in grades]
        
        # Calculate statistics
        total_students = len(scores)
        mean = np.mean(scores)
        median = np.median(scores)
        std_dev = np.std(scores)
        min_score = min(scores)
        max_score = max(scores)
        q1 = np.percentile(scores, 25)
        q3 = np.percentile(scores, 75)
        
        # Calculate grade distribution
        grade_counts = {}
        for letter in letters:
            if letter in grade_counts:
                grade_counts[letter] += 1
            else:
                grade_counts[letter] = 1
        
        # Sort the letter grades in descending order (A+, A, A-, B+, etc.)
        sorted_letters = sorted(grade_counts.keys(), 
                               key=lambda x: float('inf') if x not in GRADE_SYSTEMS["letter"] else -GRADE_SYSTEMS["letter"][x])
        
        # Calculate passing rate
        passing_count = sum(1 for letter in letters if letter != 'F')
        passing_rate = (passing_count / total_students) * 100 if total_students > 0 else 0
        
        # Generate visualizations
        # Create a figure with a 2x2 grid
        plt.figure(figsize=(12, 10))
        
        # 1. Histogram with density curve
        plt.subplot(2, 2, 1)
        sns.histplot([s / max_points * 100 for s in scores], kde=True, color='skyblue')
        plt.axvline(mean / max_points * 100, color='r', linestyle='--', label=f'Mean: {mean:.2f}')
        plt.axvline(median / max_points * 100, color='g', linestyle='-.', label=f'Median: {median:.2f}')
        plt.title('Score Distribution')
        plt.xlabel('Percentage Score')
        plt.ylabel('Frequency')
        plt.legend()
        
        # 2. Letter grade distribution
        plt.subplot(2, 2, 2)
        sorted_counts = [grade_counts[letter] for letter in sorted_letters]
        
        bars = plt.bar(sorted_letters, sorted_counts, color='lightgreen')
        plt.title('Letter Grade Distribution')
        plt.xlabel('Letter Grade')
        plt.ylabel('Count')
        
        # Add count labels on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.0f}', ha='center', va='bottom')
        
        # 3. Box plot
        plt.subplot(2, 2, 3)
        plt.boxplot([s / max_points * 100 for s in scores], vert=False, patch_artist=True, 
                   boxprops=dict(facecolor='lightblue'))
        plt.title('Box Plot of Scores')
        plt.xlabel('Percentage Score')
        plt.yticks([])  # Hide y-tick labels
        
        # 4. Normal probability plot (Q-Q plot)
        plt.subplot(2, 2, 4)
        stats.probplot([s / max_points * 100 for s in scores], dist="norm", plot=plt)
        plt.title('Normal Probability Plot')
        
        plt.tight_layout()
        
        # Save the figure
        plots_filename = f"{reports_dir}/assessment_stats_{assessment_id}_{timestamp}_plots.png"
        plt.savefig(plots_filename)
        plt.close()
        
        # Generate report in PDF format
        report_filename = f"{reports_dir}/assessment_stats_{assessment_id}_{timestamp}.pdf"
        
        doc = SimpleDocTemplate(report_filename, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            alignment=1,  # Center alignment
            spaceAfter=12
        )
        elements.append(Paragraph(f"Assessment Statistical Report", title_style))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))
        
        # Assessment details
        elements.append(Paragraph("Assessment Details", styles['Heading2']))
        
        assessment_info = [
            ['Assessment Name:', assessment_name],
            ['Module:', f"{module_code} - {module_name}"],
            ['Type:', assessment_type],
            ['Weight:', f"{weight}%"],
            ['Maximum Points:', str(max_points)]
        ]
        
        assessment_table = Table(assessment_info, colWidths=[150, 350])
        assessment_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))
        
        elements.append(assessment_table)
        elements.append(Spacer(1, 12))
        
        # Statistics summary
        elements.append(Paragraph("Statistical Summary", styles['Heading2']))
        
        stats_info = [
            ['Total Students:', str(total_students)],
            ['Mean Score:', f"{mean:.2f} ({mean/max_points*100:.1f}%)"],
            ['Median Score:', f"{median:.2f} ({median/max_points*100:.1f}%)"],
            ['Standard Deviation:', f"{std_dev:.2f} ({std_dev/max_points*100:.1f}%)"],
            ['Minimum Score:', f"{min_score:.2f} ({min_score/max_points*100:.1f}%)"],
            ['Maximum Score:', f"{max_score:.2f} ({max_score/max_points*100:.1f}%)"],
            ['1st Quartile (Q1):', f"{q1:.2f} ({q1/max_points*100:.1f}%)"],
            ['3rd Quartile (Q3):', f"{q3:.2f} ({q3/max_points*100:.1f}%)"],
            ['Interquartile Range:', f"{(q3-q1):.2f} ({(q3-q1)/max_points*100:.1f}%)"],
            ['Passing Rate:', f"{passing_rate:.1f}%"]
        ]
        
        stats_table = Table(stats_info, colWidths=[150, 350])
        stats_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 12))
        
        # Grade distribution
        elements.append(Paragraph("Grade Distribution", styles['Heading2']))
        
        grade_data = [['Grade', 'Count', 'Percentage']]
        for letter in sorted_letters:
            count = grade_counts[letter]
            percentage = (count / total_students) * 100
            grade_data.append([letter, str(count), f"{percentage:.1f}%"])
        
        grade_table = Table(grade_data, colWidths=[100, 100, 100])
        grade_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (2, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (2, 0), 'CENTER'),
            ('ALIGN', (1, 1), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (2, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(grade_table)
        elements.append(Spacer(1, 12))
        
        # Add visualizations
        elements.append(Paragraph("Visual Analysis", styles['Heading2']))
        elements.append(Spacer(1, 6))
        
        if os.path.exists(plots_filename):
            img = Image(plots_filename, width=7*inch, height=6*inch)
            elements.append(img)
        
        # Interpretation
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Interpretation", styles['Heading2']))
        
        # Grade spread interpretation
        if std_dev < 0.1 * max_points:
            spread = "The scores are tightly clustered, indicating consistent performance across students."
        elif std_dev > 0.2 * max_points:
            spread = "The scores show significant variability, indicating diverse performance levels among students."
        else:
            spread = "The scores show moderate variability in student performance."
        
        # Performance level interpretation
        if mean > 0.8 * max_points:
            performance = "Overall performance is excellent, with most students achieving high scores."
        elif mean > 0.7 * max_points:
            performance = "Overall performance is good, with many students achieving above-average scores."
        elif mean > 0.6 * max_points:
            performance = "Overall performance is satisfactory, with most students achieving passing scores."
        elif mean > 0.5 * max_points:
            performance = "Overall performance is adequate but could be improved, with some students struggling."
        else:
            performance = "Overall performance is concerning, with many students struggling to achieve passing scores."
        
        # Distribution shape interpretation
        skewness = stats.skew(scores) if len(scores) >= 3 else 0
        if abs(skewness) < 0.5:
            distribution = "The grade distribution is approximately symmetric."
        elif skewness < -0.5:
            distribution = "The grade distribution is skewed to the left (more high scores than low scores)."
        else:
            distribution = "The grade distribution is skewed to the right (more low scores than high scores)."
        
        elements.append(Paragraph(spread, styles['Normal']))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(performance, styles['Normal']))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(distribution, styles['Normal']))
        
        # Build the PDF
        doc.build(elements)
        
        print(f"Assessment statistical report generated: {report_filename}")
        
    except Exception as e:
        print(f"Error generating assessment report: {e}")

def map_assessments_to_outcomes():
    """Map assessments to learning outcomes with weights"""
    print("\nMap Assessments to Learning Outcomes")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Select an assessment
        assessment_id = select_assessment(cursor)
        if not assessment_id:
            conn.close()
            return
        
        # Get assessment details
        cursor.execute('''
        SELECT assessment_name, module_code, assessment_type
        FROM assessments
        WHERE assessment_id = ?
        ''', (assessment_id,))
        
        assessment = cursor.fetchone()
        if not assessment:
            print("Assessment not found.")
            conn.close()
            return
        
        assessment_name, module_code, assessment_type = assessment
        
        # Get current outcome mappings
        cursor.execute('''
        SELECT ao.id, lo.outcome_id, lo.outcome_code, lo.description, ao.weight
        FROM assessment_outcomes ao
        JOIN learning_outcomes lo ON ao.outcome_id = lo.outcome_id
        WHERE ao.assessment_id = ?
        ORDER BY ao.weight DESC
        ''', (assessment_id,))
        
        mappings = cursor.fetchall()
        
        print(f"\nAssessment: {assessment_name} [{module_code}] ({assessment_type})")
        
        if mappings:
            print("\nCurrent Learning Outcome Mappings:")
            print("-" * 80)
            print(f"{'Mapping ID':<12} {'Outcome ID':<12} {'Code':<15} {'Weight':<10} {'Description'}")
            print("-" * 80)
            
            for mapping in mappings:
                mapping_id, outcome_id, outcome_code, description, weight = mapping
                # Truncate long descriptions for display
                short_desc = description[:40] + "..." if len(description) > 40 else description
                print(f"{mapping_id:<12} {outcome_id:<12} {outcome_code:<15} {weight:<10.1f} {short_desc}")
        else:
            print("\nNo learning outcomes are currently mapped to this assessment.")
        
        # Get the module's course
        cursor.execute('''
        SELECT course
        FROM modules
        WHERE module_code = ?
        ''', (module_code,))
        
        course_result = cursor.fetchone()
        course = course_result[0] if course_result else None
        
        # Get available learning outcomes for this course
        if course:
            cursor.execute('''
            SELECT outcome_id, outcome_code, description, category, importance
            FROM learning_outcomes
            WHERE course = ? OR course = 'ALL'
            ORDER BY importance DESC, outcome_code
            ''', (course,))
        else:
            cursor.execute('''
            SELECT outcome_id, outcome_code, description, category, importance
            FROM learning_outcomes
            ORDER BY importance DESC, outcome_code
            ''')
        
        outcomes = cursor.fetchall()
        
        if not outcomes:
            print("\nNo learning outcomes available for mapping.")
            conn.close()
            return
        
        print("\nAvailable Learning Outcomes:")
        print("-" * 80)
        print(f"{'ID':<5} {'Code':<15} {'Category':<15} {'Importance':<10} {'Description'}")
        print("-" * 80)
        
        for outcome in outcomes:
            id, code, description, category, importance = outcome
            # Truncate long descriptions for display
            short_desc = description[:40] + "..." if len(description) > 40 else description
            print(f"{id:<5} {code:<15} {category:<15} {importance:<10} {short_desc}")
        
        # Mapping operations
        while True:
            print("\nMapping Operations:")
            print("1. Add new outcome mapping")
            print("2. Update existing mapping")
            print("3. Delete mapping")
            print("4. Return to previous menu")
            
            op_choice = input("Enter your choice (1-4): ")
            
            if op_choice == '1':
                # Add new mapping
                outcome_id = input("\nEnter Outcome ID to map to this assessment: ").strip()
                
                try:
                    outcome_id = int(outcome_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue
                
                # Check if outcome exists
                cursor.execute('''
                SELECT outcome_id, outcome_code, description
                FROM learning_outcomes
                WHERE outcome_id = ?
                ''', (outcome_id,))
                
                outcome = cursor.fetchone()
                
                if not outcome:
                    print(f"No outcome found with ID {outcome_id}.")
                    continue
                
                # Check if mapping already exists
                cursor.execute('''
                SELECT id
                FROM assessment_outcomes
                WHERE assessment_id = ? AND outcome_id = ?
                ''', (assessment_id, outcome_id))
                
                existing = cursor.fetchone()
                
                if existing:
                    print(f"This outcome is already mapped to this assessment (Mapping ID: {existing[0]}).")
                    print("Use the update option to change the weight.")
                    continue
                
                # Get weight
                while True:
                    try:
                        weight = float(input("Enter weight for this outcome (0-100): ").strip())
                        if 0 <= weight <= 100:
                            break
                        else:
                            print("Weight must be between 0 and 100.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                # Add the mapping
                cursor.execute('''
                INSERT INTO assessment_outcomes
                (assessment_id, outcome_id, weight)
                VALUES (?, ?, ?)
                ''', (assessment_id, outcome_id, weight))
                
                conn.commit()
                print(f"Learning outcome '{outcome[1]}' successfully mapped to assessment.")
                
            elif op_choice == '2':
                # Update existing mapping
                mapping_id = input("\nEnter Mapping ID to update: ").strip()
                
                try:
                    mapping_id = int(mapping_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue
                
                # Check if mapping exists
                cursor.execute('''
                SELECT ao.id, lo.outcome_code, ao.weight
                FROM assessment_outcomes ao
                JOIN learning_outcomes lo ON ao.outcome_id = lo.outcome_id
                WHERE ao.id = ? AND ao.assessment_id = ?
                ''', (mapping_id, assessment_id))
                
                mapping = cursor.fetchone()
                
                if not mapping:
                    print(f"No mapping found with ID {mapping_id} for this assessment.")
                    continue
                
                # Get new weight
                print(f"Current weight for outcome '{mapping[1]}': {mapping[2]}")
                
                while True:
                    try:
                        weight = float(input("Enter new weight (0-100): ").strip())
                        if 0 <= weight <= 100:
                            break
                        else:
                            print("Weight must be between 0 and 100.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                # Update the mapping
                cursor.execute('''
                UPDATE assessment_outcomes
                SET weight = ?
                WHERE id = ?
                ''', (weight, mapping_id))
                
                conn.commit()
                print(f"Weight for outcome '{mapping[1]}' updated successfully.")
                
            elif op_choice == '3':
                # Delete mapping
                mapping_id = input("\nEnter Mapping ID to delete: ").strip()
                
                try:
                    mapping_id = int(mapping_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue
                
                # Check if mapping exists
                cursor.execute('''
                SELECT ao.id, lo.outcome_code
                FROM assessment_outcomes ao
                JOIN learning_outcomes lo ON ao.outcome_id = lo.outcome_id
                WHERE ao.id = ? AND ao.assessment_id = ?
                ''', (mapping_id, assessment_id))
                
                mapping = cursor.fetchone()
                
                if not mapping:
                    print(f"No mapping found with ID {mapping_id} for this assessment.")
                    continue
                
                confirm = input(f"Are you sure you want to delete mapping for outcome '{mapping[1]}'? (y/n): ").strip().lower()
                
                if confirm == 'y':
                    cursor.execute('''
                    DELETE FROM assessment_outcomes
                    WHERE id = ?
                    ''', (mapping_id,))
                    
                    conn.commit()
                    print(f"Mapping for outcome '{mapping[1]}' deleted successfully.")
                else:
                    print("Deletion cancelled.")
                
            elif op_choice == '4':
                # Return to previous menu
                break
                
            else:
                print("Invalid choice. Please try again.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

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

def map_assessments_to_competencies():
    """Map assessments to competencies with weights"""
    print("\nMap Assessments to Competencies")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Select an assessment
        assessment_id = select_assessment(cursor)
        if not assessment_id:
            conn.close()
            return
        
        # Get assessment details
        cursor.execute('''
        SELECT assessment_name, module_code, assessment_type
        FROM assessments
        WHERE assessment_id = ?
        ''', (assessment_id,))
        
        assessment = cursor.fetchone()
        if not assessment:
            print("Assessment not found.")
            conn.close()
            return
        
        assessment_name, module_code, assessment_type = assessment
        
        # Get current competency mappings
        cursor.execute('''
        SELECT ac.id, c.competency_id, c.name, c.category, ac.weight
        FROM assessment_competencies ac
        JOIN competencies c ON ac.competency_id = c.competency_id
        WHERE ac.assessment_id = ?
        ORDER BY ac.weight DESC
        ''', (assessment_id,))
        
        mappings = cursor.fetchall()
        
        print(f"\nAssessment: {assessment_name} [{module_code}] ({assessment_type})")
        
        if mappings:
            print("\nCurrent Competency Mappings:")
            print("-" * 80)
            print(f"{'Mapping ID':<12} {'Comp ID':<12} {'Name':<25} {'Category':<15} {'Weight':<10}")
            print("-" * 80)
            
            for mapping in mappings:
                mapping_id, competency_id, name, category, weight = mapping
                print(f"{mapping_id:<12} {competency_id:<12} {name[:25]:<25} {category[:15]:<15} {weight:<10.1f}")
        else:
            print("\nNo competencies are currently mapped to this assessment.")
        
        # Get available competencies
        cursor.execute('''
        SELECT competency_id, name, category, description
        FROM competencies
        ORDER BY category, name
        ''')
        
        competencies = cursor.fetchall()
        
        if not competencies:
            print("\nNo competencies available for mapping. Please add competencies first.")
            conn.close()
            return
        
        print("\nAvailable Competencies:")
        print("-" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Category':<15} {'Description'}")
        print("-" * 80)
        
        for competency in competencies:
            id, name, category, description = competency
            # Truncate long descriptions and names for display
            short_name = name[:25] if len(name) > 25 else name
            short_desc = description[:35] + "..." if len(description) > 35 else description
            print(f"{id:<5} {short_name:<25} {category[:15]:<15} {short_desc}")
        
        # Mapping operations
        while True:
            print("\nMapping Operations:")
            print("1. Add new competency mapping")
            print("2. Update existing mapping")
            print("3. Delete mapping")
            print("4. Return to previous menu")
            
            op_choice = input("Enter your choice (1-4): ")
            
            if op_choice == '1':
                # Add new mapping
                competency_id = input("\nEnter Competency ID to map to this assessment: ").strip()
                
                try:
                    competency_id = int(competency_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue
                
                # Check if competency exists
                cursor.execute('''
                SELECT competency_id, name
                FROM competencies
                WHERE competency_id = ?
                ''', (competency_id,))
                
                competency = cursor.fetchone()
                
                if not competency:
                    print(f"No competency found with ID {competency_id}.")
                    continue
                
                # Check if mapping already exists
                cursor.execute('''
                SELECT id
                FROM assessment_competencies
                WHERE assessment_id = ? AND competency_id = ?
                ''', (assessment_id, competency_id))
                
                existing = cursor.fetchone()
                
                if existing:
                    print(f"This competency is already mapped to this assessment (Mapping ID: {existing[0]}).")
                    print("Use the update option to change the weight.")
                    continue
                
                # Get weight
                while True:
                    try:
                        weight = float(input("Enter weight for this competency (0-100): ").strip())
                        if 0 <= weight <= 100:
                            break
                        else:
                            print("Weight must be between 0 and 100.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                # Add the mapping
                cursor.execute('''
                INSERT INTO assessment_competencies
                (assessment_id, competency_id, weight)
                VALUES (?, ?, ?)
                ''', (assessment_id, competency_id, weight))
                
                conn.commit()
                print(f"Competency '{competency[1]}' successfully mapped to assessment.")
                
            elif op_choice == '2':
                # Update existing mapping
                mapping_id = input("\nEnter Mapping ID to update: ").strip()
                
                try:
                    mapping_id = int(mapping_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue
                
                # Check if mapping exists
                cursor.execute('''
                SELECT ac.id, c.name, ac.weight
                FROM assessment_competencies ac
                JOIN competencies c ON ac.competency_id = c.competency_id
                WHERE ac.id = ? AND ac.assessment_id = ?
                ''', (mapping_id, assessment_id))
                
                mapping = cursor.fetchone()
                
                if not mapping:
                    print(f"No mapping found with ID {mapping_id} for this assessment.")
                    continue
                
                # Get new weight
                print(f"Current weight for competency '{mapping[1]}': {mapping[2]}")
                
                while True:
                    try:
                        weight = float(input("Enter new weight (0-100): ").strip())
                        if 0 <= weight <= 100:
                            break
                        else:
                            print("Weight must be between 0 and 100.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                # Update the mapping
                cursor.execute('''
                UPDATE assessment_competencies
                SET weight = ?
                WHERE id = ?
                ''', (weight, mapping_id))
                
                conn.commit()
                print(f"Weight for competency '{mapping[1]}' updated successfully.")
                
            elif op_choice == '3':
                # Delete mapping
                mapping_id = input("\nEnter Mapping ID to delete: ").strip()
                
                try:
                    mapping_id = int(mapping_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue
                
                # Check if mapping exists
                cursor.execute('''
                SELECT ac.id, c.name
                FROM assessment_competencies ac
                JOIN competencies c ON ac.competency_id = c.competency_id
                WHERE ac.id = ? AND ac.assessment_id = ?
                ''', (mapping_id, assessment_id))
                
                mapping = cursor.fetchone()
                
                if not mapping:
                    print(f"No mapping found with ID {mapping_id} for this assessment.")
                    continue
                
                confirm = input(f"Are you sure you want to delete mapping for competency '{mapping[1]}'? (y/n): ").strip().lower()
                
                if confirm == 'y':
                    cursor.execute('''
                    DELETE FROM assessment_competencies
                    WHERE id = ?
                    ''', (mapping_id,))
                    
                    conn.commit()
                    print(f"Mapping for competency '{mapping[1]}' deleted successfully.")
                else:
                    print("Deletion cancelled.")
                
            elif op_choice == '4':
                # Return to previous menu
                break
                
            else:
                print("Invalid choice. Please try again.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def assessment_performance_summary():
    """Generate assessment performance summary"""
    print("\nAssessment Performance Summary")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get assessment type preference
        print("\nAnalyze by:")
        print("1. Specific Assessment")
        print("2. Assessment Type")
        print("3. All Assessments")
        
        choice = input("Enter choice (1-3): ").strip()
        
        if choice == '1':
            assess_id = select_assessment(cursor)
            if assess_id:
                analyze_specific_assessment(cursor, assess_id)
        elif choice == '2':
            analyze_by_assessment_type(cursor)
        else:
            analyze_all_assessments(cursor)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def analyze_specific_assessment(cursor, assessment_id):
    """Analyze a specific assessment"""
    # Get assessment details
    cursor.execute('''
    SELECT a.assessment_name, a.assessment_type, a.module_code, 
           m.module_name, a.max_points, a.weight
    FROM assessments a
    JOIN modules m ON a.module_code = m.module_code
    WHERE a.assessment_id = ?
    ''', (assessment_id,))
    
    assessment = cursor.fetchone()
    if not assessment:
        print("Assessment not found.")
        return
    
    name, type, module_code, module_name, max_points, weight = assessment
    
    # Get all grades
    cursor.execute('''
    SELECT score, letter_grade
    FROM grades
    WHERE assessment_id = ?
    ''', (assessment_id,))
    
    grades = cursor.fetchall()
    
    if not grades:
        print("No grades found for this assessment.")
        return
    
    # Calculate statistics
    scores = [score for score, _ in grades]
    percentages = [(score/max_points)*100 for score in scores]
    
    avg_score = np.mean(scores)
    avg_percentage = np.mean(percentages)
    median_percentage = np.median(percentages)
    std_dev = np.std(percentages)
    
    # Grade distribution
    grade_counts = {}
    for _, grade in grades:
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
    
    # Display results
    print(f"\n{name} ({type})")
    print(f"Module: {module_code} - {module_name}")
    print(f"Weight: {weight}%, Max Points: {max_points}")
    print("-" * 60)
    print(f"Total Students: {len(grades)}")
    print(f"Average Score: {avg_score:.1f}/{max_points} ({avg_percentage:.1f}%)")
    print(f"Median: {median_percentage:.1f}%")
    print(f"Standard Deviation: {std_dev:.1f}%")
    print(f"Highest Score: {max(scores):.1f}/{max_points} ({max(percentages):.1f}%)")
    print(f"Lowest Score: {min(scores):.1f}/{max_points} ({min(percentages):.1f}%)")
    
    print("\nGrade Distribution:")
    sorted_grades = sorted(grade_counts.items(), 
                          key=lambda x: letter_to_gpa(x[0]), reverse=True)
    for grade, count in sorted_grades:
        percentage = (count / len(grades)) * 100
        print(f"  {grade}: {count} ({percentage:.1f}%)")

def grade_distribution_analysis():
    """Analyze grade distributions across different dimensions"""
    print("\nGrade Distribution Analysis")
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Local imports to avoid circular dependencies with grade_curve_analysis
        from university_system.modules.students.grade_curve_analysis import (
            analyze_distribution_by_course,
            analyze_distribution_by_module_type,
            analyze_overall_distribution,
        )

        print("\nAnalysis Type:")
        print("1. By Course")
        print("2. By Module Type")
        print("3. By Assessment Type")
        print("4. Overall Distribution")

        choice = input("Enter choice (1-4): ").strip()

        if choice == '1':
            analyze_distribution_by_course(cursor)
        elif choice == '2':
            analyze_distribution_by_module_type(cursor)
        elif choice == '3':
            analyze_distribution_by_assessment_type(cursor)  # this one is defined here
        else:
            analyze_overall_distribution(cursor)

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def student_risk_assessment():
    """Assess risk levels for all students"""
    print("\nStudent Risk Assessment")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all students with grades
        cursor.execute('''
        SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course
        FROM students s
        JOIN module_grades mg ON s.student_id = mg.student_id
        ORDER BY s.last_name, s.first_name
        ''')
        
        students = cursor.fetchall()
        
        if not students:
            print("No students with grades found.")
            conn.close()
            return
        
        print(f"Assessing risk for {len(students)} students...")
        
        risk_assessments = []
        
        for student_id, first_name, last_name, course in students:
            risk_data = assess_student_risk(cursor, student_id, first_name, last_name, course)
            if risk_data:
                risk_assessments.append(risk_data)
        
        # Sort by risk score (highest first)
        risk_assessments.sort(key=lambda x: x['risk_score'], reverse=True)
        
        # Display results
        display_risk_assessment_results(risk_assessments)
        
        # Save to database
        save_risk_assessments(cursor, risk_assessments)
        conn.commit()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def display_risk_assessment_results(risk_assessments):
    """Display risk assessment results"""
    print("\n" + "="*100)
    print("STUDENT RISK ASSESSMENT RESULTS")
    print("="*100)
    
    # Summary by risk level
    risk_counts = {'High': 0, 'Medium': 0, 'Low': 0, 'Minimal': 0}
    for assessment in risk_assessments:
        risk_counts[assessment['risk_level']] += 1
    
    print(f"\nRisk Level Summary:")
    print(f"High Risk: {risk_counts['High']} students")
    print(f"Medium Risk: {risk_counts['Medium']} students")
    print(f"Low Risk: {risk_counts['Low']} students")
    print(f"Minimal Risk: {risk_counts['Minimal']} students")
    
    # Show high-risk students in detail
    high_risk = [a for a in risk_assessments if a['risk_level'] == 'High']
    if high_risk:
        print(f"\nHIGH RISK STUDENTS ({len(high_risk)}):")
        print("-" * 80)
        for student in high_risk:
            print(f"{student['name']} ({student['course']})")
            print(f"  Risk Score: {student['risk_score']}")
            print(f"  GPA: {student['gpa']:.2f}" if student['gpa'] else "  GPA: N/A")
            print(f"  Risk Factors: {', '.join(student['risk_factors'])}")
            print()

def save_risk_assessments(cursor, risk_assessments):
    """Save risk assessments to database"""
    assessment_date = datetime.now().strftime('%Y-%m-%d')
    
    for assessment in risk_assessments:
        # Clear existing assessment for this student
        cursor.execute('''
        DELETE FROM student_risk_assessment
        WHERE student_id = ?
        ''', (assessment['student_id'],))
        
        # Insert new assessment
        cursor.execute('''
        INSERT INTO student_risk_assessment
        (student_id, risk_score, risk_level, assessment_date, prediction_model, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (assessment['student_id'], assessment['risk_score'], assessment['risk_level'],
              assessment_date, 'Rule-based Model', 0.85))

def analyze_overall_grade_trends(cursor):
    """Analyze overall grade trends across time"""
    print("\nOverall Grade Trends Analysis")
    
    # Get grades over time
    cursor.execute('''
    SELECT DATE(g.submission_date) as date,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY DATE(g.submission_date)
    ORDER BY date
    ''')
    
    daily_trends = cursor.fetchall()
    
    if not daily_trends:
        print("Insufficient data for trend analysis.")
        return
    
    # Process data for analysis
    dates = [row[0] for row in daily_trends]
    averages = [row[1] for row in daily_trends]
    counts = [row[2] for row in daily_trends]
    
    # Calculate monthly trends
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    ORDER BY month
    ''')
    
    monthly_trends = cursor.fetchall()
    
    # Display results
    print(f"\nDaily Trend Summary:")
    print(f"Total days with grades: {len(daily_trends)}")
    print(f"Date range: {dates[0]} to {dates[-1]}")
    print(f"Overall average: {np.mean(averages):.1f}%")
    print(f"Trend slope: {calculate_trend_slope(averages):.3f}% per day")
    
    print(f"\nMonthly Trend Summary:")
    for month, avg_perc, count in monthly_trends:
        print(f"{month}: {avg_perc:.1f}% average ({count} grades)")
    
    # Identify trends
    if len(averages) >= 5:
        recent_avg = np.mean(averages[-5:])
        early_avg = np.mean(averages[:5])
        trend_direction = "improving" if recent_avg > early_avg else "declining"
        trend_magnitude = abs(recent_avg - early_avg)
        
        print(f"\nTrend Analysis:")
        print(f"Performance is {trend_direction} by {trend_magnitude:.1f}% over time")
        
        if trend_magnitude > 5:
            print("⚠️  Significant trend detected - requires attention")
        elif trend_magnitude > 2:
            print("📊 Moderate trend detected - monitor closely")
        else:
            print("✅ Performance is relatively stable")
    
    # Create visualization
    create_trend_visualization(daily_trends, monthly_trends, "overall_trends")

def analyze_by_assessment_type(cursor):
    """Analyze performance by assessment type"""
    print("\nAssessment Type Performance Analysis")
    
    # Get all assessment types
    cursor.execute('''
    SELECT DISTINCT assessment_type
    FROM assessments
    ORDER BY assessment_type
    ''')
    
    assessment_types = [row[0] for row in cursor.fetchall()]
    
    if not assessment_types:
        print("No assessment types found.")
        return
    
    print("\nAssessment Type Performance Summary:")
    print("-" * 80)
    print(f"{'Type':<20} {'Assessments':<12} {'Avg Score':<12} {'Pass Rate':<12}")
    print("-" * 80)
    
    for assess_type in assessment_types:
        # Get performance statistics for this type
        cursor.execute('''
        SELECT AVG(g.score / a.max_points * 100) as avg_percentage,
               COUNT(*) as total_grades
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        WHERE a.assessment_type = ?
        ''', (assess_type,))
        
        result = cursor.fetchone()
        if result and result[1] > 0:
            avg_percentage, total_grades = result
            
            # Calculate passing rate
            cursor.execute('''
            SELECT COUNT(*) as passing_count
            FROM grades g
            JOIN assessments a ON g.assessment_id = a.assessment_id
            WHERE a.assessment_type = ? AND g.letter_grade != 'F'
            ''', (assess_type,))
            
            passing_count = cursor.fetchone()[0]
            passing_rate = (passing_count / total_grades) * 100
            
            print(f"{assess_type:<20} {total_grades:<12} {avg_percentage:<12.1f}% {passing_rate:<12.1f}%")

def analyze_all_assessments(cursor):
    """Analyze all assessments performance"""
    print("\nAll Assessments Performance Analysis")
    
    # Get overall statistics
    cursor.execute('''
    SELECT COUNT(DISTINCT a.assessment_id) as total_assessments,
           COUNT(g.grade_id) as total_grades,
           AVG(g.score / a.max_points * 100) as overall_avg
    FROM assessments a
    LEFT JOIN grades g ON a.assessment_id = g.assessment_id
    ''')
    
    overall_stats = cursor.fetchone()
    total_assessments, total_grades, overall_avg = overall_stats
    
    print(f"\nOverall Assessment Statistics:")
    print(f"Total Assessments: {total_assessments}")
    print(f"Total Grades: {total_grades}")
    print(f"Overall Average: {overall_avg:.1f}%" if overall_avg else "Overall Average: N/A")
    
    # Get top and bottom performing assessments
    cursor.execute('''
    SELECT a.assessment_name, a.module_code, a.assessment_type,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(g.grade_id) as grade_count
    FROM assessments a
    JOIN grades g ON a.assessment_id = g.assessment_id
    GROUP BY a.assessment_id
    HAVING grade_count >= 3
    ORDER BY avg_percentage DESC
    ''')
    
    assessment_performance = cursor.fetchall()
    
    if assessment_performance:
        print(f"\nTop Performing Assessments:")
        print("-" * 80)
        print(f"{'Assessment':<30} {'Module':<12} {'Type':<15} {'Avg Score':<12}")
        print("-" * 80)
        
        for i, (name, module, type, avg, count) in enumerate(assessment_performance[:5]):
            print(f"{name[:30]:<30} {module:<12} {type:<15} {avg:<12.1f}%")
        
        print(f"\nLowest Performing Assessments:")
        print("-" * 80)
        print(f"{'Assessment':<30} {'Module':<12} {'Type':<15} {'Avg Score':<12}")
        print("-" * 80)
        
        for i, (name, module, type, avg, count) in enumerate(assessment_performance[-5:]):
            print(f"{name[:30]:<30} {module:<12} {type:<15} {avg:<12.1f}%")

def analyze_distribution_by_assessment_type(cursor):
    """Analyze grade distribution by assessment type"""
    print("\nGrade Distribution by Assessment Type")
    
    cursor.execute('''
    SELECT a.assessment_type, g.letter_grade, COUNT(*) as count
    FROM assessments a
    JOIN grades g ON a.assessment_id = g.assessment_id
    GROUP BY a.assessment_type, g.letter_grade
    ORDER BY a.assessment_type, g.letter_grade
    ''')
    
    distribution_data = cursor.fetchall()
    
    if not distribution_data:
        print("No grade distribution data found.")
        return
    
    # Organize data by assessment type
    type_distributions = {}
    for assess_type, grade, count in distribution_data:
        if assess_type not in type_distributions:
            type_distributions[assess_type] = {}
        type_distributions[assess_type][grade] = count
    
    # Display results
    print("\nGrade Distribution by Assessment Type:")
    print("="*100)
    
    for assess_type, grade_dist in type_distributions.items():
        print(f"\n{assess_type}:")
        print("-" * 60)
        
        total_grades = sum(grade_dist.values())
        sorted_grades = sorted(grade_dist.items(), 
                              key=lambda x: letter_to_gpa(x[0]), reverse=True)
        
        for grade, count in sorted_grades:
            percentage = (count / total_grades) * 100
            print(f"  {grade}: {count} ({percentage:.1f}%)")
        
        print(f"  Total: {total_grades} grades")

def compare_by_grade_threshold(cursor):
    """Compare students above and below a grade threshold"""
    print("\nGrade Threshold Comparison")
    
    threshold = input("Enter GPA threshold for comparison (e.g., 3.0): ").strip()
    
    try:
        threshold = float(threshold)
    except ValueError:
        print("Invalid threshold. Please enter a number.")
        return
    
    # Get students above and below threshold
    cursor.execute('SELECT DISTINCT student_id FROM module_grades')
    students = [row[0] for row in cursor.fetchall()]
    
    above_threshold = []
    below_threshold = []
    
    for student_id in students:
        gpa, _, _ = calculate_student_gpa(cursor, student_id)
        if gpa is not None:
            if gpa >= threshold:
                above_threshold.append(student_id)
            else:
                below_threshold.append(student_id)
    
    print(f"\nComparison Results (Threshold: {threshold}):")
    print(f"Students above threshold: {len(above_threshold)}")
    print(f"Students below threshold: {len(below_threshold)}")
    
    if len(above_threshold) == 0 or len(below_threshold) == 0:
        print("Cannot perform comparison - one group is empty.")
        return
    
    # Calculate group statistics
    above_gpas = []
    below_gpas = []
    
    for student_id in above_threshold:
        gpa, _, _ = calculate_student_gpa(cursor, student_id)
        if gpa is not None:
            above_gpas.append(gpa)
    
    for student_id in below_threshold:
        gpa, _, _ = calculate_student_gpa(cursor, student_id)
        if gpa is not None:
            below_gpas.append(gpa)
    
    print(f"\nGroup Statistics:")
    print(f"Above threshold - Avg GPA: {np.mean(above_gpas):.2f}, Std: {np.std(above_gpas):.2f}")
    print(f"Below threshold - Avg GPA: {np.mean(below_gpas):.2f}, Std: {np.std(below_gpas):.2f}")

def analyze_assessment_performance_trends(cursor):
    """Analyze performance trends by assessment type over time"""
    print("\nAssessment Performance Trends Analysis")
    
    # Get available assessment types
    cursor.execute('SELECT DISTINCT assessment_type FROM assessments ORDER BY assessment_type')
    assessment_types = [row[0] for row in cursor.fetchall()]
    
    if not assessment_types:
        print("No assessment types found.")
        return
    
    print(f"\nAvailable assessment types: {', '.join(assessment_types)}")
    
    assess_type = input("Enter assessment type to analyze (or 'ALL' for all types): ").strip()
    
    if assess_type == 'ALL':
        # Analyze all assessment types
        for type_name in assessment_types:
            analyze_single_assessment_type_trends(cursor, type_name)
    elif assess_type in assessment_types:
        analyze_single_assessment_type_trends(cursor, assess_type)
    else:
        print("Invalid assessment type selection.")

def analyze_single_assessment_type_trends(cursor, assess_type):
    """Analyze trends for a single assessment type"""
    print(f"\n--- Trend Analysis for {assess_type} Assessments ---")
    
    # Get monthly performance data for this assessment type
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE a.assessment_type = ? AND g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    HAVING grade_count >= 3
    ORDER BY month
    ''', (assess_type,))
    
    monthly_data = cursor.fetchall()
    
    if len(monthly_data) < 3:
        print(f"Insufficient data for trend analysis (need at least 3 months)")
        return
    
    # Calculate trend
    months = [data[0] for data in monthly_data]
    averages = [data[1] for data in monthly_data]
    
    trend_slope = calculate_trend_slope(averages)
    
    print(f"Period: {months[0]} to {months[-1]}")
    print(f"Average Performance: {np.mean(averages):.1f}%")
    print(f"Trend: {trend_slope:+.2f}% per month")
    
    if trend_slope > 1:
        print("Status: Improving 📈")
    elif trend_slope < -1:
        print("Status: Declining 📉")
    else:
        print("Status: Stable 📊")

def batch_grade_predictions(cursor):
    """Perform batch grade predictions for multiple students"""
    print("\nBatch Grade Predictions")
    
    print("\nPrediction Options:")
    print("1. Predict next assessment grades for all students")
    print("2. Predict final module grades for specific module")
    print("3. Predict end-of-term GPAs")
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice == '1':
        batch_predict_next_assessments(cursor)
    elif choice == '2':
        batch_predict_module_grades(cursor)
    elif choice == '3':
        batch_predict_end_term_gpas(cursor)
    else:
        print("Invalid choice.")

def batch_predict_next_assessments(cursor):
    """Predict next assessment grades for all students"""
    print("\nBatch Next Assessment Predictions")
    
    # Get all students with sufficient assessment history
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course
    FROM students s
    JOIN grades g ON s.student_id = g.student_id
    GROUP BY s.student_id
    HAVING COUNT(g.grade_id) >= 3
    ORDER BY s.last_name, s.first_name
    ''')
    
    students = cursor.fetchall()
    
    if not students:
        print("No students with sufficient assessment history found.")
        return
    
    print(f"Generating predictions for {len(students)} students...")
    
    predictions = []
    
    for student_id, first_name, last_name, course in students:
        prediction = predict_student_next_grade(cursor, student_id)
        if prediction:
            predictions.append({
                'student_id': student_id,
                'name': f"{first_name} {last_name}",
                'course': course,
                'predicted_score': prediction['score'],
                'predicted_grade': prediction['grade'],
                'confidence': prediction['confidence']
            })
    
    # Display results
    print(f"\nNext Assessment Grade Predictions:")
    print("="*90)
    print(f"{'Name':<25} {'Course':<10} {'Predicted Score':<15} {'Grade':<8} {'Confidence'}")
    print("-"*90)
    
    for pred in predictions:
        print(f"{pred['name']:<25} {pred['course']:<10} {pred['predicted_score']:<15.1f}% "
              f"{pred['predicted_grade']:<8} {pred['confidence']}")
    
    # Export option
    export = input("\nExport predictions to CSV? (y/n): ").strip().lower()
    if export == 'y':
        export_batch_predictions(predictions, "next_assessment_predictions")

def predict_student_next_grade(cursor, student_id):
    """Predict next grade for a specific student"""
    # Get recent assessment history
    cursor.execute('''
    SELECT g.score / a.max_points * 100 as percentage
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date DESC
    LIMIT 5
    ''', (student_id,))
    
    recent_scores = [r[0] for r in cursor.fetchall()]
    
    if len(recent_scores) < 3:
        return None
    
    # Simple prediction based on moving average and trend
    moving_avg = np.mean(recent_scores)
    
    # Calculate trend
    x = list(range(len(recent_scores)))
    trend_slope = np.polyfit(x, recent_scores[::-1], 1)[0]  # Reverse for chronological order
    
    # Predict next score
    predicted_score = moving_avg + trend_slope
    predicted_score = max(0, min(100, predicted_score))  # Bound between 0-100
    
    # Convert to letter grade
    predicted_grade = percentage_to_letter(predicted_score)
    
    # Calculate confidence based on consistency
    score_std = np.std(recent_scores)
    if score_std < 5:
        confidence = "High"
    elif score_std < 10:
        confidence = "Medium"
    else:
        confidence = "Low"
    
    return {
        'score': predicted_score,
        'grade': predicted_grade,
        'confidence': confidence
    }

def batch_predict_module_grades(cursor):
    """Predict final module grades for a specific module"""
    print("\nBatch Module Grade Predictions")
    
    # Get available modules
    cursor.execute('''
    SELECT DISTINCT m.module_code, m.module_name
    FROM modules m
    JOIN student_modules sm ON m.module_code = sm.module_code
    ORDER BY m.module_name
    ''')
    
    modules = cursor.fetchall()
    
    if not modules:
        print("No modules found.")
        return
    
    print("\nAvailable Modules:")
    for i, (code, name) in enumerate(modules):
        print(f"{i+1}. {code} - {name}")
    
    choice = input("Enter module number: ").strip()
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(modules):
            module_code, module_name = modules[idx]
        else:
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return
    
    print(f"\nPredicting final grades for module: {module_code} - {module_name}")
    
    # Get students enrolled in this module
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.first_name, s.last_name
    FROM students s
    JOIN student_modules sm ON s.student_id = sm.student_id
    WHERE sm.module_code = ?
    ORDER BY s.last_name, s.first_name
    ''', (module_code,))
    
    students = cursor.fetchall()
    
    if not students:
        print("No students found for this module.")
        return
    
    predictions = []
    
    for student_id, first_name, last_name in students:
        prediction = predict_module_final_grade(cursor, student_id, module_code)
        if prediction:
            predictions.append({
                'student_id': student_id,
                'name': f"{first_name} {last_name}",
                'predicted_score': prediction['score'],
                'predicted_grade': prediction['grade'],
                'current_progress': prediction['progress']
            })
    
    # Display results
    print(f"\nFinal Grade Predictions for {module_code}:")
    print("="*80)
    print(f"{'Name':<30} {'Current Progress':<15} {'Predicted Score':<15} {'Grade'}")
    print("-"*80)
    
    for pred in predictions:
        print(f"{pred['name']:<30} {pred['current_progress']:<15.1f}% "
              f"{pred['predicted_score']:<15.1f}% {pred['predicted_grade']}")

def predict_module_final_grade(cursor, student_id, module_code):
    """Predict final module grade for a student"""
    # Get all assessments for this module
    cursor.execute('''
    SELECT assessment_id, weight, max_points
    FROM assessments
    WHERE module_code = ?
    ''', (module_code,))
    
    assessments = cursor.fetchall()
    
    if not assessments:
        return None
    
    # Get current grades
    total_weighted_score = 0
    total_weight_completed = 0
    
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
            total_weight_completed += weight
    
    if total_weight_completed == 0:
        return None
    
    # Calculate current progress
    current_progress = total_weighted_score
    
    # Predict final score based on current performance
    if total_weight_completed < 100:
        # Assume remaining assessments will perform at current average
        avg_performance = total_weighted_score / (total_weight_completed / 100)
        remaining_weight = 100 - total_weight_completed
        predicted_remaining = avg_performance * (remaining_weight / 100)
        predicted_final = total_weighted_score + predicted_remaining
    else:
        predicted_final = total_weighted_score
    
    predicted_final = max(0, min(100, predicted_final))
    predicted_grade = percentage_to_letter(predicted_final)
    
    return {
        'score': predicted_final,
        'grade': predicted_grade,
        'progress': current_progress
    }

def batch_predict_end_term_gpas(cursor):
    """Predict end-of-term GPAs for all students"""
    print("\nBatch End-of-Term GPA Predictions")
    
    # Get all students with current grades
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    ORDER BY s.last_name, s.first_name
    ''')
    
    students = cursor.fetchall()
    
    if not students:
        print("No students with grades found.")
        return
    
    print(f"Predicting end-of-term GPAs for {len(students)} students...")
    
    predictions = []
    
    for student_id, first_name, last_name, course in students:
        prediction = predict_end_term_gpa(cursor, student_id)
        if prediction:
            predictions.append({
                'student_id': student_id,
                'name': f"{first_name} {last_name}",
                'course': course,
                'current_gpa': prediction['current_gpa'],
                'predicted_gpa': prediction['predicted_gpa'],
                'trend': prediction['trend']
            })
    
    # Sort by predicted GPA (lowest first for attention)
    predictions.sort(key=lambda x: x['predicted_gpa'])
    
    # Display results
    print(f"\nEnd-of-Term GPA Predictions:")
    print("="*80)
    print(f"{'Name':<25} {'Course':<10} {'Current GPA':<12} {'Predicted GPA':<15} {'Trend'}")
    print("-"*80)
    
    for pred in predictions:
        trend_symbol = "📈" if pred['trend'] > 0.1 else "📉" if pred['trend'] < -0.1 else "📊"
        print(f"{pred['name']:<25} {pred['course']:<10} {pred['current_gpa']:<12.2f} "
              f"{pred['predicted_gpa']:<15.2f} {trend_symbol}")
    
    # Identify students needing attention
    at_risk_predictions = [p for p in predictions if p['predicted_gpa'] < 2.0]
    
    if at_risk_predictions:
        print(f"\n⚠️  Students predicted to have GPA < 2.0 ({len(at_risk_predictions)}):")
        for pred in at_risk_predictions:
            print(f"   - {pred['name']} ({pred['course']}): {pred['predicted_gpa']:.2f}")

def predict_end_term_gpa(cursor, student_id):
    """Predict end-of-term GPA for a student"""
    # Get current GPA
    current_gpa, credits, _ = calculate_student_gpa(cursor, student_id)
    
    if not current_gpa:
        return None
    
    # Get recent performance trend
    cursor.execute('''
    SELECT g.score / a.max_points * 100, g.submission_date
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date DESC
    LIMIT 10
    ''', (student_id,))
    
    recent_scores = cursor.fetchall()
    
    if len(recent_scores) < 5:
        # Not enough data for trend analysis
        return {
            'current_gpa': current_gpa,
            'predicted_gpa': current_gpa,
            'trend': 0
        }
    
    # Calculate performance trend
    scores = [score for score, _ in recent_scores]
    x = list(range(len(scores)))
    trend_slope = np.polyfit(x, scores[::-1], 1)[0]  # Reverse for chronological order
    
    # Convert trend to GPA change (simplified)
    gpa_trend = trend_slope / 25  # Rough conversion from percentage to GPA points
    
    # Predict future GPA
    predicted_gpa = current_gpa + gpa_trend
    predicted_gpa = max(0, min(4.3, predicted_gpa))  # Bound within GPA range
    
    return {
        'current_gpa': current_gpa,
        'predicted_gpa': predicted_gpa,
        'trend': gpa_trend
    }

def forecast_assessment_performance(cursor):
    """Forecast assessment performance trends"""
    print("\nAssessment Performance Forecasting")
    
    # Get assessment types with historical data
    cursor.execute('''
    SELECT a.assessment_type,
           COUNT(DISTINCT strftime('%Y-%m', g.submission_date)) as months_with_data
    FROM assessments a
    JOIN grades g ON a.assessment_id = g.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY a.assessment_type
    HAVING months_with_data >= 6
    ORDER BY a.assessment_type
    ''')
    
    assessment_types = cursor.fetchall()
    
    if not assessment_types:
        print("No assessment types with sufficient historical data found.")
        return
    
    print(f"\nForecasting performance trends for {len(assessment_types)} assessment types...")
    
    for assess_type, months_count in assessment_types:
        forecast_assessment_type_performance(cursor, assess_type)

def forecast_assessment_type_performance(cursor, assess_type):
    """Forecast performance for a specific assessment type"""
    print(f"\n--- {assess_type} Assessment Forecast ---")
    
    # Get monthly performance data
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE a.assessment_type = ? AND g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    HAVING grade_count >= 5
    ORDER BY month
    ''', (assess_type,))
    
    monthly_data = cursor.fetchall()
    
    if len(monthly_data) < 6:
        print(f"Insufficient data for forecasting")
        return
    
    # Analyze and forecast
    months = [data[0] for data in monthly_data]
    averages = [data[1] for data in monthly_data]
    
    # Calculate trend
    x = np.arange(len(averages))
    trend_slope = np.polyfit(x, averages, 1)[0]
    
    # Project forward
    future_performance = averages[-1] + (trend_slope * 3)
    future_performance = max(0, min(100, future_performance))
    
    print(f"Current Average: {np.mean(averages[-3:]):.1f}%")
    print(f"Trend: {trend_slope:+.2f}% per month")
    print(f"3-Month Projection: {future_performance:.1f}%")
    
    if trend_slope > 1:
        print("Status: Improving performance expected 📈")
    elif trend_slope < -1:
        print("Status: Declining performance expected 📉")
    else:
        print("Status: Stable performance expected 📊")

def build_assessment_prediction_model(cursor):
    """Build a model to predict assessment performance"""
    print("\nBuilding Assessment Performance Prediction Model...")
    
    # This would predict likely assessment scores based on historical performance
    print("Assessment prediction model building - would use historical performance patterns")
    print("Features would include: recent scores, assessment type, time since last assessment, etc.")

def validate_grade_data_integrity(cursor):
    """Validate the integrity of grade data in the system"""
    print("\nValidating Grade Data Integrity...")
    
    issues_found = []
    
    # Check for grades without corresponding assessments
    cursor.execute('''
    SELECT COUNT(*) FROM grades g
    LEFT JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE a.assessment_id IS NULL
    ''')
    
    orphaned_grades = cursor.fetchone()[0]
    if orphaned_grades > 0:
        issues_found.append(f"Found {orphaned_grades} grades without corresponding assessments")
    
    # Check for students without any grades
    cursor.execute('''
    SELECT COUNT(*) FROM students s
    LEFT JOIN grades g ON s.student_id = g.student_id
    WHERE g.student_id IS NULL
    ''')
    
    students_no_grades = cursor.fetchone()[0]
    if students_no_grades > 0:
        issues_found.append(f"Found {students_no_grades} students without any grades")
    
    # Check for invalid grade ranges
    cursor.execute('''
    SELECT COUNT(*) FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.score < 0 OR g.score > a.max_points
    ''')
    
    invalid_scores = cursor.fetchone()[0]
    if invalid_scores > 0:
        issues_found.append(f"Found {invalid_scores} grades with invalid score ranges")
    
    # Display results
    if issues_found:
        print("Data integrity issues found:")
        for issue in issues_found:
            print(f"  ⚠️  {issue}")
    else:
        print("✅ No data integrity issues found")
    
    return len(issues_found) == 0

def build_gpa_prediction_model(cursor):
    """Build a simple GPA prediction model"""
    print("\nBuilding GPA Prediction Model...")
    
    # Collect training data
    training_data = []
    
    cursor.execute('SELECT DISTINCT student_id FROM module_grades')
    students = cursor.fetchall()
    
    for (student_id,) in students:
        # Get student features
        features = extract_student_features(cursor, student_id)
        if features:
            gpa, _, _ = calculate_student_gpa(cursor, student_id)
            if gpa is not None:
                features['target_gpa'] = gpa
                training_data.append(features)
    
    if len(training_data) < 10:
        print("Insufficient data for model training (need at least 10 students).")
        return
    
    print(f"Training model with {len(training_data)} student records...")
    
    # Prepare data for modeling
    X = []
    y = []
    
    feature_names = ['avg_score', 'submission_rate', 'assessment_count', 'failed_count']
    
    for record in training_data:
        features_vector = [
            record.get('avg_score', 0),
            record.get('submission_rate', 0),
            record.get('assessment_count', 0),
            record.get('failed_count', 0)
        ]
        X.append(features_vector)
        y.append(record['target_gpa'])
    
    X = np.array(X)
    y = np.array(y)
    
    # Simple linear regression model
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_squared_error, r2_score
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # Make predictions
    y_pred = model.predict(X_test)
    
    # Evaluate model
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    print(f"\nModel Performance:")
    print(f"Mean Squared Error: {mse:.3f}")
    print(f"R² Score: {r2:.3f}")
    print(f"Model Accuracy: {r2*100:.1f}%")
    
    # Feature importance
    print(f"\nFeature Importance:")
    for i, feature in enumerate(feature_names):
        importance = abs(model.coef_[i])
        print(f"  {feature}: {importance:.3f}")
    
    # Make prediction for a new student
    predict_new = input("\nPredict GPA for a specific student? (y/n): ").strip().lower()
    if predict_new == 'y':
        student_id = select_student(cursor)
        if student_id:
            predict_student_gpa(cursor, model, student_id, feature_names)

def predict_student_gpa(cursor, model, student_id, feature_names):
    """Predict GPA for a specific student"""
    # Get student info
    cursor.execute('''
    SELECT first_name, last_name
    FROM students
    WHERE student_id = ?
    ''', (student_id,))
    
    student = cursor.fetchone()
    if not student:
        print("Student not found.")
        return
    
    first_name, last_name = student
    
    # Extract features
    features = extract_student_features(cursor, student_id)
    if not features:
        print("No data available for this student.")
        return
    
    # Prepare feature vector
    X = np.array([[
        features.get('avg_score', 0),
        features.get('submission_rate', 0),
        features.get('assessment_count', 0),
        features.get('failed_count', 0)
    ]])
    
    # Make prediction
    predicted_gpa = model.predict(X)[0]
    
    # Get actual GPA if available
    actual_gpa, _, _ = calculate_student_gpa(cursor, student_id)
    
    print(f"\nGPA Prediction for {first_name} {last_name}:")
    print(f"Predicted GPA: {predicted_gpa:.2f}")
    if actual_gpa:
        print(f"Actual GPA: {actual_gpa:.2f}")
        print(f"Prediction Error: {abs(predicted_gpa - actual_gpa):.2f}")
    
    print(f"\nStudent Features:")
    print(f"  Average Score: {features['avg_score']:.1f}%")
    print(f"  Submission Rate: {features['submission_rate']*100:.1f}%")
    print(f"  Assessments Taken: {features['assessment_count']}")
    print(f"  Failed Assessments: {features['failed_count']}")

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

def predict_next_assessment_grade(cursor):
    """Predict a student's next assessment grade"""
    print("\nNext Assessment Grade Prediction")
    
    student_id = select_student(cursor)
    if not student_id:
        return
    
    # Get student info
    cursor.execute('''
    SELECT first_name, last_name, course
    FROM students
    WHERE student_id = ?
    ''', (student_id,))
    
    student = cursor.fetchone()
    if not student:
        print("Student not found.")
        return
    
    first_name, last_name, course = student
    
    # Get student's assessment history
    cursor.execute('''
    SELECT g.score / a.max_points * 100 as percentage,
           a.assessment_type,
           g.submission_date
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date DESC
    ''', (student_id,))
    
    assessment_history = cursor.fetchall()
    
    if len(assessment_history) < 3:
        print("Insufficient assessment history for prediction (need at least 3 assessments).")
        return
    
    # Calculate prediction based on trend analysis
    recent_scores = [score for score, _, _ in assessment_history[:5]]  # Last 5 assessments
    
    # Simple trend-based prediction
    if len(recent_scores) >= 3:
        # Calculate moving average
        moving_avg = np.mean(recent_scores)
        
        # Calculate trend
        x = list(range(len(recent_scores)))
        trend_slope = np.polyfit(x, recent_scores[::-1], 1)[0]  # Reverse for chronological order
        
        # Predict next grade
        predicted_score = moving_avg + trend_slope
        predicted_score = max(0, min(100, predicted_score))  # Bound between 0-100
        
        # Convert to letter grade
        predicted_letter = percentage_to_letter(predicted_score)
        
        print(f"\nGrade Prediction for {first_name} {last_name}:")
        print(f"Recent Performance Average: {moving_avg:.1f}%")
        print(f"Performance Trend: {trend_slope:+.1f}% per assessment")
        print(f"Predicted Next Score: {predicted_score:.1f}%")
        print(f"Predicted Letter Grade: {predicted_letter}")
        
        # Confidence assessment
        score_std = np.std(recent_scores)
        if score_std < 5:
            confidence = "High"
        elif score_std < 10:
            confidence = "Medium"
        else:
            confidence = "Low"
        
        print(f"Prediction Confidence: {confidence} (σ = {score_std:.1f}%)")
        
        # Performance by assessment type
        type_performance = {}
        for score, assess_type, _ in assessment_history:
            if assess_type not in type_performance:
                type_performance[assess_type] = []
            type_performance[assess_type].append(score)
        
        print(f"\nPerformance by Assessment Type:")
        for assess_type, scores in type_performance.items():
            avg_score = np.mean(scores)
            print(f"  {assess_type}: {avg_score:.1f}% (n={len(scores)})")

def predict_final_module_grade(cursor):
    """Interactive wrapper to predict a student's final module grade"""
    print("\nPredict Final Module Grade")

    # 1) pick student
    student_id = select_student(cursor)
    if not student_id:
        print("No student selected.")
        return

    # 2) list only this student's modules
    cursor.execute("""
    SELECT DISTINCT m.module_code, m.module_name
      FROM modules m
      JOIN student_modules sm ON m.module_code = sm.module_code
     WHERE sm.student_id = ?
     ORDER BY m.module_name
    """, (student_id,))
    modules = cursor.fetchall() or []
    if not modules:
        print("No enrolled modules found for this student.")
        return

    print("\nStudent's Modules:")
    for i, (code, name) in enumerate(modules, start=1):
        print(f"{i}. {code} - {name}")

    choice = input("Enter module number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(modules):
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    module_code, module_name = modules[idx]

    # 3) compute prediction using existing core function
    result = predict_module_final_grade(cursor, student_id, module_code)
    if not result:
        print("Not enough data to predict final grade for this module.")
        return

    print(f"\nPrediction for {module_code} - {module_name}")
    print(f"Current Progress: {result['progress']:.1f}%")
    print(f"Predicted Final Score: {result['score']:.1f}%")
    print(f"Predicted Final Grade: {result['grade']}")
