# Standard library imports
import os
import csv
import math
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Initialize logger
logger = logging.getLogger(__name__)

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
from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection

# Local imports - Common functions
from university_system.modules.domain.academics.grading.common_utilities import select_assessment

# Local imports - Grade management
from university_system.modules.domain.academics.grading.grade_calculation import (
    build_gpa_prediction_model,
    build_assessment_prediction_model,
    grade_prediction,
    calculate_student_gpa,
    letter_to_gpa,
)

# Local imports - Predictive analytics
from university_system.modules.domain.academics.grading.predictive_analytics import (
    build_at_risk_prediction_model,
)

class DataBag(dict):
    """Dict that also allows attribute-style access."""
    __getattr__ = dict.get
    def __setattr__(self, k, v): self[k] = v

def _table_exists(cur, name: str) -> bool:
    try:
        r = cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
        ).fetchone()
        return bool(r)
    except Exception:
        return False

def _cols(cur, table: str) -> set:
    try:
        return {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()

def _first_existing_table(cur, candidates: List[str]) -> str | None:
    for t in candidates:
        if _table_exists(cur, t):
            return t
    return None

def _first_existing_column(cur, table: str, candidates: List[str]) -> str | None:
    existing = _cols(cur, table)
    for c in candidates:
        if c in existing:
            return c
    return None

def collect_dashboard_data(cursor) -> DataBag:
    """
    Gather metrics for the performance dashboard across a variety of schemas.
    Returns a DataBag with common keys used by dashboards, always present.
    """
    bag = DataBag(
        total_students=0,
        total_courses=0,
        total_grades=0,
        avg_score=None,
        grade_distribution={"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
        course_averages=[],
        student_averages=[],
        at_risk_students=[],
        monthly_trends=[],
        missing_grades=0,
        notes=[],
    )

    # ---- Discover tables ----
    grades_t  = _first_existing_table(cursor, ["grades", "student_grades", "gradebook", "marks"])
    students_t = _first_existing_table(cursor, ["students", "student_profiles", "student"])
    courses_t  = _first_existing_table(cursor, ["courses", "subjects", "modules", "classes", "units"])

    if not grades_t:
        bag["notes"].append("No grades table found; returning empty dashboard.")
        return bag

    # ---- Discover columns on grades ----
    student_col = _first_existing_column(cursor, grades_t, ["student_id", "sid", "student", "user_id"])
    course_col  = _first_existing_column(cursor, grades_t, ["course_id", "subject_id", "module_id", "class_id", "course", "subject", "module", "class"])
    score_col   = _first_existing_column(cursor, grades_t, ["score", "grade", "grade_value", "percentage", "mark", "points", "score_value"])
    date_col    = _first_existing_column(cursor, grades_t, ["date", "graded_at", "recorded_at", "assessment_date", "created_at", "timestamp"])
    term_col    = _first_existing_column(cursor, grades_t, ["term", "semester", "period"])

    if not score_col:
        bag["notes"].append(f"No numeric score column on '{grades_t}'.")
        return bag

    # ---- Totals / counts ----
    try:
        bag["total_grades"] = cursor.execute(f"SELECT COUNT(*) FROM {grades_t}").fetchone()[0] or 0
    except Exception as e:
        logger.warning(f"Failed to count grades from table '{grades_t}': {e}")

    if students_t:
        try:
            bag["total_students"] = cursor.execute(f"SELECT COUNT(*) FROM {students_t}").fetchone()[0] or 0
        except Exception as e:
            logger.warning(f"Failed to count students from table '{students_t}': {e}")

    if courses_t:
        try:
            bag["total_courses"] = cursor.execute(f"SELECT COUNT(*) FROM {courses_t}").fetchone()[0] or 0
        except Exception as e:
            logger.warning(f"Failed to count courses from table '{courses_t}': {e}")

    # ---- Overall average ----
    try:
        bag["avg_score"] = cursor.execute(
            f"SELECT ROUND(AVG(CAST({score_col} AS REAL)),2) FROM {grades_t} WHERE {score_col} IS NOT NULL AND TRIM({score_col})<>''"
        ).fetchone()[0]
    except Exception as e:
        logger.warning(f"Failed to calculate average score: {e}")

    # ---- Grade distribution (A/B/C/D/F by numeric cutoffs; adjust to your scale if needed) ----
    try:
        row = cursor.execute(
            f"""
            SELECT
              SUM(CASE WHEN CAST({score_col} AS REAL) >= 85 THEN 1 ELSE 0 END) AS A_cnt,
              SUM(CASE WHEN CAST({score_col} AS REAL) BETWEEN 70 AND 84.999 THEN 1 ELSE 0 END) AS B_cnt,
              SUM(CASE WHEN CAST({score_col} AS REAL) BETWEEN 55 AND 69.999 THEN 1 ELSE 0 END) AS C_cnt,
              SUM(CASE WHEN CAST({score_col} AS REAL) BETWEEN 40 AND 54.999 THEN 1 ELSE 0 END) AS D_cnt,
              SUM(CASE WHEN CAST({score_col} AS REAL) < 40 THEN 1 ELSE 0 END) AS F_cnt
            FROM {grades_t}
            WHERE {score_col} IS NOT NULL AND TRIM({score_col}) <> ''
            """
        ).fetchone()
        if row:
            bag["grade_distribution"] = {"A": row[0], "B": row[1], "C": row[2], "D": row[3], "F": row[4]}
    except Exception as e:
        logger.warning(f"Failed to calculate grade distribution: {e}")

    # ---- Course averages ----
    if course_col:
        try:
            bag["course_averages"] = [
                {"course": r[0], "avg_score": r[1], "count": r[2]}
                for r in cursor.execute(
                    f"""
                    SELECT {course_col} AS course, ROUND(AVG(CAST({score_col} AS REAL)),2) AS avg_score, COUNT(*)
                      FROM {grades_t}
                     WHERE {score_col} IS NOT NULL AND TRIM({score_col}) <> ''
                  GROUP BY {course_col}
                  ORDER BY avg_score DESC
                     LIMIT 20
                    """
                ).fetchall()
            ]
        except Exception as e:
            logger.warning(f"Failed to calculate course averages: {e}")

    # ---- Student averages (top/bottom) ----
    if student_col:
        try:
            bag["student_averages"] = [
                {"student_id": r[0], "avg_score": r[1], "count": r[2]}
                for r in cursor.execute(
                    f"""
                    SELECT {student_col} AS student_id, ROUND(AVG(CAST({score_col} AS REAL)),2) AS avg_score, COUNT(*)
                      FROM {grades_t}
                     WHERE {score_col} IS NOT NULL AND TRIM({score_col}) <> ''
                  GROUP BY {student_col}
                  ORDER BY avg_score DESC
                     LIMIT 20
                    """
                ).fetchall()
            ]
        except Exception as e:
            logger.warning(f"Failed to calculate student averages: {e}")

    # ---- At-risk students (avg < 50) ----
    if student_col:
        try:
            bag["at_risk_students"] = [
                {"student_id": r[0], "avg_score": r[1], "count": r[2]}
                for r in cursor.execute(
                    f"""
                    SELECT {student_col} AS student_id, ROUND(AVG(CAST({score_col} AS REAL)),2) AS avg_score, COUNT(*)
                      FROM {grades_t}
                     WHERE {score_col} IS NOT NULL AND TRIM({score_col}) <> ''
                  GROUP BY {student_col}
                    HAVING avg_score < 50
                  ORDER BY avg_score ASC
                     LIMIT 50
                    """
                ).fetchall()
            ]
        except Exception as e:
            logger.warning(f"Failed to identify at-risk students: {e}")

    # ---- Monthly trends ----
    if date_col:
        try:
            bag["monthly_trends"] = [
                {"month": r[0], "avg_score": r[1], "count": r[2]}
                for r in cursor.execute(
                    f"""
                    SELECT strftime('%Y-%m', {date_col}) AS month,
                           ROUND(AVG(CAST({score_col} AS REAL)),2) AS avg_score,
                           COUNT(*)
                      FROM {grades_t}
                     WHERE {date_col} IS NOT NULL
                       AND {score_col} IS NOT NULL AND TRIM({score_col}) <> ''
                  GROUP BY strftime('%Y-%m', {date_col})
                  ORDER BY month
                    """
                ).fetchall()
            ]
        except Exception as e:
            logger.warning(f"Failed to calculate monthly trends: {e}")

    # ---- Missing grades ----
    try:
        bag["missing_grades"] = cursor.execute(
            f"SELECT COUNT(*) FROM {grades_t} WHERE {score_col} IS NULL OR TRIM({score_col})=''"
        ).fetchone()[0] or 0
    except Exception as e:
        logger.warning(f"Failed to count missing grades: {e}")

    # ---- Optional note about term/semester detection ----
    if term_col:
        bag["notes"].append(f"Detected term column: {term_col}")

    return bag

def module_performance_summary():
    """Generate module performance summary"""
    print("\nModule Performance Summary")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all modules with grades
        cursor.execute('''
        SELECT DISTINCT m.module_code, m.module_name, m.module_type
        FROM modules m
        JOIN module_grades mg ON m.module_code = mg.module_code
        ORDER BY m.module_name
        ''')
        
        modules = cursor.fetchall()
        
        if not modules:
            print("No modules with grades found.")
            conn.close()
            return
        
        # Ask for specific module or all
        print("\nAvailable Modules:")
        print("0. All Modules")
        for i, (code, name, type) in enumerate(modules, 1):
            print(f"{i}. {code} - {name} ({type})")
        
        choice = input("\nSelect module number: ").strip()
        
        try:
            if choice == '0':
                selected_modules = modules
            else:
                idx = int(choice) - 1
                if 0 <= idx < len(modules):
                    selected_modules = [modules[idx]]
                else:
                    print("Invalid selection. Analyzing all modules.")
                    selected_modules = modules
        except ValueError:
            print("Invalid input. Analyzing all modules.")
            selected_modules = modules
        
        # Analyze modules
        module_stats = []
        
        for module_code, module_name, module_type in selected_modules:
            stats = analyze_module_performance(cursor, module_code, module_name, module_type)
            if stats:
                module_stats.append(stats)
        
        # Display results
        if module_stats:
            display_module_performance_results(module_stats)
            
            # Export option
            export = input("\nExport module performance summary? (y/n): ").strip().lower()
            if export == 'y':
                export_module_performance(module_stats)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def analyze_module_performance(cursor, module_code, module_name, module_type):
    """Analyze performance for a specific module"""
    # Get all grades for this module
    cursor.execute('''
    SELECT final_grade, final_score
    FROM module_grades
    WHERE module_code = ?
    ''', (module_code,))
    
    grades = cursor.fetchall()
    
    if not grades:
        return None
    
    # Calculate statistics
    total_students = len(grades)
    scores = [score for _, score in grades if score is not None]
    
    if not scores:
        return None
    
    avg_score = np.mean(scores)
    median_score = np.median(scores)
    std_dev = np.std(scores)
    min_score = min(scores)
    max_score = max(scores)
    
    # Grade distribution
    grade_counts = {}
    for grade, _ in grades:
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
    
    # Passing rate
    passing_count = sum(1 for grade, _ in grades if grade not in ['F'])
    passing_rate = (passing_count / total_students) * 100
    
    # Performance level classification
    if avg_score >= 80:
        performance_level = "Excellent"
    elif avg_score >= 70:
        performance_level = "Good"
    elif avg_score >= 60:
        performance_level = "Satisfactory"
    else:
        performance_level = "Needs Improvement"
    
    return {
        'code': module_code,
        'name': module_name,
        'type': module_type,
        'total_students': total_students,
        'avg_score': avg_score,
        'median_score': median_score,
        'std_dev': std_dev,
        'min_score': min_score,
        'max_score': max_score,
        'passing_rate': passing_rate,
        'grade_distribution': grade_counts,
        'performance_level': performance_level
    }

def display_module_performance_results(module_stats):
    """Display module performance results"""
    print("\n" + "="*100)
    print("MODULE PERFORMANCE SUMMARY")
    print("="*100)
    
    for stats in module_stats:
        print(f"\n{stats['code']} - {stats['name']} ({stats['type']})")
        print("-" * 60)
        print(f"Total Students: {stats['total_students']}")
        print(f"Average Score: {stats['avg_score']:.1f}%")
        print(f"Median Score: {stats['median_score']:.1f}%")
        print(f"Standard Deviation: {stats['std_dev']:.1f}")
        print(f"Score Range: {stats['min_score']:.1f}% - {stats['max_score']:.1f}%")
        print(f"Passing Rate: {stats['passing_rate']:.1f}%")
        print(f"Performance Level: {stats['performance_level']}")
        
        print("\nGrade Distribution:")
        sorted_grades = sorted(stats['grade_distribution'].items(), 
                              key=lambda x: letter_to_gpa(x[0]), reverse=True)
        for grade, count in sorted_grades:
            percentage = (count / stats['total_students']) * 100
            print(f"  {grade}: {count} ({percentage:.1f}%)")

def calculate_course_statistics(cursor, course):
    """Calculate comprehensive statistics for a course"""
    # Get all students in this course
    cursor.execute('''
    SELECT s.student_id
    FROM students s
    WHERE s.course = ?
    ''', (course,))
    
    student_ids = [row[0] for row in cursor.fetchall()]
    
    if not student_ids:
        return None
    
    # Calculate average GPA
    total_gpa = 0
    gpa_count = 0
    
    for student_id in student_ids:
        gpa, _, _ = calculate_student_gpa(cursor, student_id)
        if gpa is not None:
            total_gpa += gpa
            gpa_count += 1
    
    avg_gpa = total_gpa / gpa_count if gpa_count > 0 else 0
    
    # Get module grades for this course
    cursor.execute('''
    SELECT mg.final_grade, mg.final_score
    FROM module_grades mg
    JOIN students s ON mg.student_id = s.student_id
    WHERE s.course = ?
    ''', (course,))
    
    grades = cursor.fetchall()
    
    if not grades:
        return None
    
    # Calculate statistics
    scores = [score for _, score in grades if score is not None]
    avg_score = np.mean(scores) if scores else 0
    median_score = np.median(scores) if scores else 0
    std_dev = np.std(scores) if scores else 0
    
    # Calculate passing rate
    passing_count = sum(1 for grade, _ in grades if grade not in ['F'])
    passing_rate = (passing_count / len(grades)) * 100 if grades else 0
    
    # Grade distribution
    grade_distribution = {}
    for grade, _ in grades:
        grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
    
    # Calculate excellence rate (A grades)
    excellence_count = sum(1 for grade, _ in grades if grade in ['A+', 'A', 'A-'])
    excellence_rate = (excellence_count / len(grades)) * 100 if grades else 0
    
    return {
        'course': course,
        'avg_gpa': avg_gpa,
        'avg_score': avg_score,
        'median_score': median_score,
        'std_dev': std_dev,
        'passing_rate': passing_rate,
        'excellence_rate': excellence_rate,
        'total_grades': len(grades),
        'grade_distribution': grade_distribution
    }

def generate_performance_dashboard():
    """Generate a comprehensive performance dashboard"""
    print("\nGenerating Performance Dashboard...")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Collect dashboard data
        dashboard_data = collect_dashboard_data(cursor)
        
        if not dashboard_data:
            print("Insufficient data for dashboard generation.")
            conn.close()
            return
        
        # Display dashboard
        display_performance_dashboard(dashboard_data)
        
        # Generate dashboard report
        generate_dashboard_report(dashboard_data)
        
        # Create dashboard visualizations
        create_dashboard_visualizations(dashboard_data)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def display_performance_dashboard(dashboard_data):
    """Display the performance dashboard"""
    print("\n" + "="*100)
    print("PERFORMANCE DASHBOARD")
    print("="*100)
    
    # Overview Section
    overview = dashboard_data['overview']
    print(f"\n📊 SYSTEM OVERVIEW")
    print(f"   Total Students: {overview['total_students']}")
    print(f"   Total Modules: {overview['total_modules']}")
    print(f"   Total Assessments: {overview['total_assessments']}")
    print(f"   Total Grades Recorded: {overview['total_grades']}")
    
    # GPA Statistics
    if 'gpa_stats' in dashboard_data:
        gpa_stats = dashboard_data['gpa_stats']
        print(f"\n🎓 GPA STATISTICS")
        print(f"   Average GPA: {gpa_stats['avg_gpa']:.2f}")
        print(f"   Median GPA: {gpa_stats['median_gpa']:.2f}")
        print(f"   GPA Range: {gpa_stats['min_gpa']:.2f} - {gpa_stats['max_gpa']:.2f}")
        print(f"   Students with GPA: {gpa_stats['students_with_gpa']}")
    
    # Grade Distribution
    grade_data = dashboard_data['grade_distribution']
    print(f"\n📈 GRADE DISTRIBUTION")
    print(f"   Overall Passing Rate: {grade_data['passing_rate']:.1f}%")
    print(f"   Total Module Grades: {grade_data['total_grades']}")
    
    # Top grade performers
    sorted_grades = sorted(grade_data['distribution'].items(), 
                          key=lambda x: letter_to_gpa(x[0]), reverse=True)
    print(f"   Grade Breakdown:")
    for grade, count in sorted_grades[:5]:  # Top 5 grades
        percentage = (count / grade_data['total_grades']) * 100
        print(f"     {grade}: {count} ({percentage:.1f}%)")
    
    # Course Performance
    course_perf = dashboard_data['course_performance']
    print(f"\n🏆 TOP PERFORMING COURSES")
    for i, (course, students, avg_score) in enumerate(course_perf[:3], 1):
        print(f"   {i}. {course}: {avg_score:.1f}% avg ({students} students)")
    
    # Risk Assessment
    risk_stats = dashboard_data['risk_stats']
    print(f"\n⚠️  RISK ASSESSMENT")
    print(f"   At-Risk Students: {risk_stats['at_risk_students']} ({risk_stats['at_risk_percentage']:.1f}%)")
    print(f"   High-Risk Students: {risk_stats['high_risk_students']}")
    
    # Recent Trends
    recent_trends = dashboard_data['recent_trends']
    if recent_trends:
        recent_avg = np.mean([trend[1] for trend in recent_trends])
        print(f"\n📊 RECENT PERFORMANCE (Last 30 days)")
        print(f"   Average Performance: {recent_avg:.1f}%")
        print(f"   Assessment Days: {len(recent_trends)}")
    
    # Alert Messages
    print(f"\n🚨 ALERTS & RECOMMENDATIONS")
    generate_dashboard_alerts(dashboard_data)

def export_module_performance(module_stats):
    """Export module performance summary to CSV"""
    exports_dir = 'performance_reports'
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{exports_dir}/module_performance_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Module Code', 'Module Name', 'Type', 'Total Students', 'Avg Score (%)', 
                        'Median Score (%)', 'Std Dev', 'Min Score (%)', 'Max Score (%)', 
                        'Passing Rate (%)', 'Performance Level'])
        
        for stats in module_stats:
            writer.writerow([
                stats['code'],
                stats['name'],
                stats['type'],
                stats['total_students'],
                f"{stats['avg_score']:.1f}",
                f"{stats['median_score']:.1f}",
                f"{stats['std_dev']:.1f}",
                f"{stats['min_score']:.1f}",
                f"{stats['max_score']:.1f}",
                f"{stats['passing_rate']:.1f}",
                stats['performance_level']
            ])
    
    print(f"Module performance summary exported to {filename}")

def analyze_course_performance_trends(cursor):
    """Analyze performance trends by course over time"""
    print("\nCourse Performance Trends Analysis")
    
    # Get available courses
    cursor.execute('SELECT DISTINCT course FROM students ORDER BY course')
    courses = [row[0] for row in cursor.fetchall()]
    
    if not courses:
        print("No courses found.")
        return
    
    print(f"\nAvailable courses: {', '.join(courses)}")
    
    course = input("Enter course to analyze (or 'ALL' for all courses): ").strip().upper()
    
    if course == 'ALL':
        # Analyze all courses
        for course_name in courses:
            analyze_single_course_trends(cursor, course_name)
    elif course in courses:
        analyze_single_course_trends(cursor, course)
    else:
        print("Invalid course selection.")

def forecast_course_performance(cursor):
    """Forecast course performance trends"""
    print("\nCourse Performance Forecasting")
    
    # Get available courses
    cursor.execute('SELECT DISTINCT course FROM students ORDER BY course')
    courses = [row[0] for row in cursor.fetchall()]
    
    if not courses:
        print("No courses found.")
        return
    
    print(f"\nAvailable courses: {', '.join(courses)}")
    
    course = input("Enter course to forecast (or 'ALL' for all courses): ").strip().upper()
    
    if course == 'ALL':
        for course_name in courses:
            forecast_single_course(cursor, course_name)
    elif course in courses:
        forecast_single_course(cursor, course)
    else:
        print("Invalid course selection.")

def export_performance_summary(summary_data, export_type):
    """Export performance summary data to CSV"""
    exports_dir = 'performance_exports'
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{exports_dir}/{export_type}_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write headers and data based on export type
        if export_type == "performance_summary":
            writer.writerow(['Category', 'Value', 'Status', 'Recommendations'])
            
            for item in summary_data:
                writer.writerow([
                    item.get('category', ''),
                    item.get('value', ''),
                    item.get('status', ''),
                    item.get('recommendations', '')
                ])
    
    print(f"Performance summary exported to {filename}")

def performance_prediction_models():
    """Build and use performance prediction models"""
    print("\nPerformance Prediction Models")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nPrediction Model Options:")
        print("1. GPA Prediction Model")
        print("2. Grade Prediction Model")
        print("3. At-Risk Student Prediction")
        print("4. Module Success Prediction")
        print("5. Assessment Performance Prediction")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            build_gpa_prediction_model(cursor)
        elif choice == '2':
            grade_prediction()
        elif choice == '3':
            build_at_risk_prediction_model(cursor)
        elif choice == '4':
            build_module_success_model(cursor)
        elif choice == '5':
            build_assessment_prediction_model(cursor)
        else:
            print("Invalid choice. Returning to menu.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def forecast_overall_performance(cursor):
    """Forecast overall academic performance trends"""
    print("\nOverall Performance Trend Forecasting")
    
    # Get historical performance data
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as assessment_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    HAVING assessment_count >= 10
    ORDER BY month
    ''')
    
    monthly_data = cursor.fetchall()
    
    if len(monthly_data) < 6:
        print("Insufficient historical data for trend forecasting (need at least 6 months).")
        return
    
    # Prepare data for forecasting
    months = [data[0] for data in monthly_data]
    averages = [data[1] for data in monthly_data]
    
    # Simple linear trend forecasting
    x = np.arange(len(averages))
    coefficients = np.polyfit(x, averages, 1)
    trend_line = np.poly1d(coefficients)
    
    # Forecast next 3 months
    forecast_periods = 3
    future_x = np.arange(len(averages), len(averages) + forecast_periods)
    forecasted_values = trend_line(future_x)
    
    print(f"\nHistorical Performance Trend:")
    print(f"Data Period: {months[0]} to {months[-1]}")
    print(f"Average Performance: {np.mean(averages):.1f}%")
    print(f"Trend Slope: {coefficients[0]:.2f}% per month")
    
    if coefficients[0] > 0.5:
        trend_direction = "Improving"
    elif coefficients[0] < -0.5:
        trend_direction = "Declining"
    else:
        trend_direction = "Stable"
    
    print(f"Trend Direction: {trend_direction}")
    
    print(f"\nForecasted Performance (Next {forecast_periods} months):")
    for i, forecast in enumerate(forecasted_values, 1):
        bounded_forecast = max(0, min(100, forecast))  # Bound between 0-100
        print(f"  Month +{i}: {bounded_forecast:.1f}%")
    
    # Calculate forecast confidence
    residuals = averages - trend_line(x)
    mse = np.mean(residuals**2)
    print(f"\nForecast Confidence:")
    print(f"  Mean Squared Error: {mse:.2f}")
    print(f"  Standard Error: {np.sqrt(mse):.2f}%")
    
    # Recommendations
    print(f"\nRecommendations:")
    if coefficients[0] < -1:
        print("  🚨 Declining trend detected - immediate intervention needed")
        print("  📋 Review curriculum and teaching methods")
        print("  👥 Increase student support services")
    elif coefficients[0] > 1:
        print("  🎉 Improving trend - maintain current practices")
        print("  📈 Document successful strategies for replication")
    else:
        print("  📊 Stable performance - monitor for changes")
        print("  🔍 Look for opportunities to drive improvement")

def forecast_single_course(cursor, course_name: str):
    """Forecast monthly average performance for a specific course."""
    print(f"\nForecast for course: {course_name}")
    # Historical monthly averages for the course
    cursor.execute("""
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(CASE WHEN a.max_points IS NOT NULL AND a.max_points > 0
                    THEN (CAST(g.score AS REAL) / a.max_points) * 100 END) as avg_percentage,
           COUNT(*) as assessment_count
      FROM grades g
      JOIN assessments a ON g.assessment_id = a.assessment_id
      JOIN students s ON s.student_id = g.student_id
     WHERE g.submission_date IS NOT NULL
       AND s.course = ?
     GROUP BY strftime('%Y-%m', g.submission_date)
     HAVING assessment_count >= 5
     ORDER BY month
    """, (course_name,))
    rows = cursor.fetchall() or []
    if not rows:
        print("No sufficient historical data for this course.")
        return

    months = [r[0] for r in rows]
    values = [float(r[1] or 0.0) for r in rows]

    # Encode months as sequential integers for a simple linear model
    x = np.arange(len(values))
    y = np.array(values, dtype=float)

    # Linear regression (least squares)
    if len(x) < 2:
        print("Not enough points to compute a trend.")
        return

    slope, intercept = np.polyfit(x, y, 1)

    # Forecast next 3 months
    forecast_periods = 3
    x_future = np.arange(len(values), len(values) + forecast_periods)
    y_future = intercept + slope * x_future
    y_future = np.clip(y_future, 0, 100)

    print(f"Trend Slope: {slope:.2f}% per month")
    direction = "Improving" if slope > 0.5 else ("Declining" if slope < -0.5 else "Stable")
    print(f"Trend Direction: {direction}")

    print(f"Forecasted Performance (Next {forecast_periods} months):")
    for i, v in enumerate(y_future, 1):
        print(f"  Month +{i}: {v:.1f}%")

def build_module_success_model(cursor):
    """Build a simple rule-based module success predictor and show risk modules.
    Uses per-student average % within each module as proxy for outcome.
    """
    print("\nBuilding Module Success Model (rule-based)")
    # Aggregate per student-module stats
    cursor.execute("""    SELECT g.student_id,
           a.module_code,
           AVG(CASE WHEN a.max_points IS NOT NULL AND a.max_points > 0
                    THEN (CAST(g.score AS REAL) / a.max_points) * 100 END) AS avg_pct,
           COUNT(*) as num_assessments
      FROM grades g
      JOIN assessments a ON g.assessment_id = a.assessment_id
     WHERE g.score IS NOT NULL
     GROUP BY g.student_id, a.module_code
    """)
    rows = cursor.fetchall() or []
    if not rows:
        print("No grade data available.")
        return

    # Label success via threshold (>=50% pass)
    from collections import defaultdict
    records = []
    for sid, module_code, avg_pct, n in rows:
        avg_pct = float(avg_pct or 0.0)
        success = 1 if avg_pct >= 50.0 else 0
        records.append((module_code, avg_pct, int(n or 0), success))

    # Module-level summary
    mod_totals = defaultdict(lambda: {'count':0,'fails':0,'avg':0.0,'n_sum':0})
    for module_code, avg_pct, n, success in records:
        d = mod_totals[module_code]
        d['count'] += 1
        d['fails'] += (1 - success)
        d['avg'] += avg_pct
        d['n_sum'] += n
    summary = []
    for mcode, d in mod_totals.items():
        cnt = d['count']
        fail_rate = (d['fails']/cnt*100.0) if cnt else 0.0
        avg_pct = (d['avg']/cnt) if cnt else 0.0
        avg_items = (d['n_sum']/cnt) if cnt else 0.0
        summary.append((mcode, cnt, fail_rate, avg_pct, avg_items))

    # Sort by highest failure rate
    summary.sort(key=lambda t: (-t[2], t[3]))

    print("\nModules ranked by estimated failure risk:")
    print(f"{'Module':<12} {'Samples':>8} {'Fail %':>8} {'Avg %':>8} {'Items':>8}")
    for mcode, cnt, fail, avgp, items in summary[:15]:
        print(f"{mcode:<12} {cnt:>8} {fail:>7.1f}% {avgp:>8.1f} {items:>8.1f}")

    print("\nRule-based predictor: if current module average < 50% and <3 assessments completed → at-risk.")
