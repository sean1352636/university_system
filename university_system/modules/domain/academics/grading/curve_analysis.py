# Standard library imports
import os
import csv
import math
from datetime import datetime, timedelta

# Third-party imports
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
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

# Set matplotlib backend
matplotlib.use('Agg')

# Local imports - Database
from university_system.infrastructure.database.db import get_connection, sqlite3

# Local imports - Grade management
from university_system.modules.domain.academics.grading.grade_calculation import (select_assessment,
    percentage_to_letter,
    letter_to_gpa,
    grade_distribution_analysis,
    analyze_assessment_performance_trends,
    assessment_performance_summary,
    update_module_grade,
    analyze_overall_grade_trends,
)

from university_system.modules.domain.academics.grading.comparisons import (
    compare_by_course,
    compare_by_gender,
    compare_by_module_type,
    compare_by_time_period,
    custom_group_comparison,
    compare_by_assessment_type,
)
from university_system.modules.domain.academics.grading.trends import (
    analyze_individual_student_trends,
    analyze_seasonal_trends,
)
from university_system.modules.domain.academics.grading.progress import (
    student_progress_tracking,
)



# Local imports - Predictive analytics
from university_system.modules.domain.academics.grading.predictive_analytics import (
    identify_high_dropout_risk,
    calculate_dropout_risk_score,
    analyze_dropout_risk_factors,
    build_dropout_prediction_model,
    generate_dropout_interventions,
    identify_at_risk_students,
)

# Local imports - Performance analysis
from university_system.modules.domain.academics.grading.performance_analytics import (module_performance_summary,
    analyze_course_performance_trends,
)

def apply_grading_curve():
    """Apply a grading curve to an assessment"""
    print("\nApply Grading Curve")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get assessment to curve
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
        
        # Extract data
        grade_ids = [g[0] for g in grades]
        student_ids = [g[1] for g in grades]
        student_names = [f"{g[2]} {g[3]}" for g in grades]
        scores = [g[4] for g in grades]
        letter_grades = [g[5] for g in grades]
        
        # Choose curve method
        print("\nCurving Methods:")
        print("1. Add points to all scores")
        print("2. Multiply all scores by a factor")
        print("3. Set highest score to maximum points")
        print("4. Adjust to target mean")
        print("5. Set grade boundaries")
        
        method = input("Select curving method (1-5): ")
        
        curved_scores = []
        curved_letters = []
        
        if method == "1":
            # Add points
            points_to_add = float(input("Enter points to add to all scores: "))
            
            # Apply curve
            curved_scores = [min(score + points_to_add, max_points) for score in scores]
            curved_letters = [percentage_to_letter((score / max_points) * 100) for score in curved_scores]
            
        elif method == "2":
            # Multiply by factor
            factor = float(input("Enter multiplication factor: "))
            
            # Apply curve
            curved_scores = [min(score * factor, max_points) for score in scores]
            curved_letters = [percentage_to_letter((score / max_points) * 100) for score in curved_scores]
            
        elif method == "3":
            # Set highest score to maximum
            high_score = max(scores)
            if high_score <= 0:
                print("Cannot apply curve: highest score is zero or negative.")
                conn.close()
                return
            
            factor = max_points / high_score
            
            # Apply curve
            curved_scores = [min(score * factor, max_points) for score in scores]
            curved_letters = [percentage_to_letter((score / max_points) * 100) for score in curved_scores]
            
        elif method == "4":
            # Adjust to target mean
            current_mean = sum(scores) / len(scores)
            target_mean = float(input(f"Current mean is {current_mean:.2f}. Enter target mean: "))
            target_mean = min(target_mean, max_points)
            
            shift = target_mean - current_mean
            
            # Apply curve
            curved_scores = [min(score + shift, max_points) for score in scores]
            curved_letters = [percentage_to_letter((score / max_points) * 100) for score in curved_scores]
            
        elif method == "5":
            # Set grade boundaries
            print("\nSet minimum percentage for each grade:")
            
            grade_boundaries = {}
            grades_list = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]
            
            for grade in grades_list:
                if grade == "F":
                    grade_boundaries[grade] = 0
                else:
                    boundary = float(input(f"Minimum percentage for {grade}: "))
                    grade_boundaries[grade] = boundary
            
            # Apply curve
            curved_scores = []
            curved_letters = []
            
            for score in scores:
                percentage = (score / max_points) * 100
                
                # Find appropriate grade
                assigned_grade = "F"
                for grade, boundary in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
                    if percentage >= boundary:
                        assigned_grade = grade
                        break
                
                curved_letters.append(assigned_grade)
                
                # Keep original score
                curved_scores.append(score)
        
        else:
            print("Invalid method.")
            conn.close()
            return
        
        # Display the results
        print("\nCurving Results:")
        print(f"{'Student':<30} {'Original Score':<15} {'Original Grade':<15} {'Curved Score':<15} {'Curved Grade':<15}")
        print("-" * 90)
        
        for i in range(len(grades)):
            print(f"{student_names[i]:<30} {scores[i]:<15.2f} {letter_grades[i]:<15} {curved_scores[i]:<15.2f} {curved_letters[i]:<15}")
        
        # Apply the curve?
        apply = input("\nApply this curve to the database? (y/n): ").strip().lower()
        
        if apply == 'y':
            # Update grades
            for i in range(len(grades)):
                cursor.execute('''
                UPDATE grades
                SET score = ?, letter_grade = ?
                WHERE grade_id = ?
                ''', (curved_scores[i], curved_letters[i], grade_ids[i]))
            
            # Update module grades for affected students
            for student_id in set(student_ids):
                update_module_grade(cursor, student_id, module_code)
            
            conn.commit()
            print("Curve applied successfully.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

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

def comparative_performance_analysis():
    """Compare performance across different groups"""
    print("\nComparative Performance Analysis")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nComparison Options:")
        print("1. Compare by Course")
        print("2. Compare by Gender")
        print("3. Compare by Module Type")
        print("4. Compare by Assessment Type")
        print("5. Compare by Academic Year/Term")
        print("6. Custom Group Comparison")
        
        choice = input("Enter your choice (1-6): ").strip()
        
        if choice == '1':
            compare_by_course(cursor)
        elif choice == '2':
            compare_by_gender(cursor)
        elif choice == '3':
            compare_by_module_type(cursor)
        elif choice == '4':
            compare_by_assessment_type(cursor)
        elif choice == '5':
            compare_by_time_period(cursor)
        elif choice == '6':
            custom_group_comparison(cursor)
        else:
            print("Invalid choice. Returning to menu.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def performance_trends_analysis():
    """Analyze performance trends over time"""
    print("\nPerformance Trends Analysis")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nTrend Analysis Options:")
        print("1. Overall Grade Trends")
        print("2. Individual Student Trends")
        print("3. Course Performance Trends")
        print("4. Assessment Performance Trends")
        print("5. Seasonal/Time-based Trends")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            analyze_overall_grade_trends(cursor)
        elif choice == '2':
            analyze_individual_student_trends(cursor)
        elif choice == '3':
            analyze_course_performance_trends(cursor)
        elif choice == '4':
            analyze_assessment_performance_trends(cursor)
        elif choice == '5':
            analyze_seasonal_trends(cursor)
        else:
            print("Invalid choice. Returning to menu.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def analyze_distribution_by_course(cursor):
    """Analyze grade distribution by course"""
    print("\nGrade Distribution by Course")
    
    cursor.execute('''
    SELECT s.course, mg.final_grade, COUNT(*) as count
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    GROUP BY s.course, mg.final_grade
    ORDER BY s.course, mg.final_grade
    ''')
    
    distribution_data = cursor.fetchall()
    
    if not distribution_data:
        print("No grade distribution data found.")
        return
    
    # Organize data by course
    course_distributions = {}
    for course, grade, count in distribution_data:
        if course not in course_distributions:
            course_distributions[course] = {}
        course_distributions[course][grade] = count
    
    # Display results
    print("\nGrade Distribution by Course:")
    print("="*100)
    
    for course, grade_dist in course_distributions.items():
        print(f"\n{course}:")
        print("-" * 60)
        
        total_grades = sum(grade_dist.values())
        sorted_grades = sorted(grade_dist.items(), 
                              key=lambda x: letter_to_gpa(x[0]), reverse=True)
        
        for grade, count in sorted_grades:
            percentage = (count / total_grades) * 100
            print(f"  {grade}: {count} ({percentage:.1f}%)")
        
        print(f"  Total: {total_grades} grades")

def analyze_distribution_by_module_type(cursor):
    """Analyze grade distribution by module type"""
    print("\nGrade Distribution by Module Type")
    
    cursor.execute('''
    SELECT m.module_type, mg.final_grade, COUNT(*) as count
    FROM modules m
    JOIN module_grades mg ON m.module_code = mg.module_code
    GROUP BY m.module_type, mg.final_grade
    ORDER BY m.module_type, mg.final_grade
    ''')
    
    distribution_data = cursor.fetchall()
    
    if not distribution_data:
        print("No grade distribution data found.")
        return
    
    # Organize data by module type
    type_distributions = {}
    for module_type, grade, count in distribution_data:
        if module_type not in type_distributions:
            type_distributions[module_type] = {}
        type_distributions[module_type][grade] = count
    
    # Display results
    print("\nGrade Distribution by Module Type:")
    print("="*100)
    
    for module_type, grade_dist in type_distributions.items():
        print(f"\n{module_type}:")
        print("-" * 60)
        
        total_grades = sum(grade_dist.values())
        sorted_grades = sorted(grade_dist.items(), 
                              key=lambda x: letter_to_gpa(x[0]), reverse=True)
        
        for grade, count in sorted_grades:
            percentage = (count / total_grades) * 100
            print(f"  {grade}: {count} ({percentage:.1f}%)")
        
        print(f"  Total: {total_grades} grades")

def analyze_overall_distribution(cursor):
    """Analyze overall grade distribution"""
    print("\nOverall Grade Distribution Analysis")
    
    # Module grades distribution
    cursor.execute('''
    SELECT final_grade, COUNT(*) as count
    FROM module_grades
    GROUP BY final_grade
    ORDER BY final_grade
    ''')
    
    module_grade_dist = cursor.fetchall()
    
    # Assessment grades distribution
    cursor.execute('''
    SELECT letter_grade, COUNT(*) as count
    FROM grades
    GROUP BY letter_grade
    ORDER BY letter_grade
    ''')
    
    assessment_grade_dist = cursor.fetchall()
    
    # Display module grades
    if module_grade_dist:
        print("\nModule Final Grades Distribution:")
        print("-" * 60)
        
        total_module_grades = sum(count for _, count in module_grade_dist)
        sorted_grades = sorted(module_grade_dist, 
                              key=lambda x: letter_to_gpa(x[0]), reverse=True)
        
        for grade, count in sorted_grades:
            percentage = (count / total_module_grades) * 100
            print(f"  {grade}: {count} ({percentage:.1f}%)")
        
        print(f"  Total Module Grades: {total_module_grades}")
    
    # Display assessment grades
    if assessment_grade_dist:
        print("\nAssessment Grades Distribution:")
        print("-" * 60)
        
        total_assessment_grades = sum(count for _, count in assessment_grade_dist)
        sorted_grades = sorted(assessment_grade_dist, 
                              key=lambda x: letter_to_gpa(x[0]), reverse=True)
        
        for grade, count in sorted_grades:
            percentage = (count / total_assessment_grades) * 100
            print(f"  {grade}: {count} ({percentage:.1f}%)")
        
        print(f"  Total Assessment Grades: {total_assessment_grades}")

def dropout_risk_analysis():
    """Analyze dropout risk factors"""
    print("\nDropout Risk Analysis")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nDropout Risk Analysis Options:")
        print("1. Identify High Dropout Risk Students")
        print("2. Analyze Dropout Risk Factors")
        print("3. Dropout Risk Prediction Model")
        print("4. Early Intervention Recommendations")
        
        choice = input("Enter your choice (1-4): ").strip()
        
        if choice == '1':
            identify_high_dropout_risk(cursor)
        elif choice == '2':
            analyze_dropout_risk_factors(cursor)
        elif choice == '3':
            build_dropout_prediction_model(cursor)
        elif choice == '4':
            generate_dropout_interventions(cursor)
        else:
            print("Invalid choice. Returning to menu.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
