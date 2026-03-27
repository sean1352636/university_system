from __future__ import annotations

import os
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.grading.utils import calculate_trend_slope, select_student

_DATA_REPORTS_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'reports'
)

def analyze_individual_student_trends(cursor):
    """Analyze performance trends for individual students"""
    print("\nIndividual Student Trends Analysis")

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

    # Get student's grades over time
    cursor.execute('''
    SELECT g.submission_date,
           g.score / a.max_points * 100 as percentage,
           a.assessment_name,
           a.module_code,
           a.assessment_type
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date
    ''', (student_id,))

    student_grades = cursor.fetchall()

    if not student_grades:
        print("No grades found for this student.")
        return

    print(f"\nTrend Analysis for {first_name} {last_name} ({course})")
    print(f"Total assessments: {len(student_grades)}")

    # Analyze trends
    percentages = [grade[1] for grade in student_grades]
    dates = [grade[0] for grade in student_grades]

    if len(percentages) >= 3:
        # Calculate rolling average
        window_size = min(3, len(percentages))
        rolling_avg = []
        for i in range(len(percentages) - window_size + 1):
            avg = np.mean(percentages[i:i + window_size])
            rolling_avg.append(avg)

        # Trend analysis
        slope = calculate_trend_slope(percentages)

        print(f"Overall average: {np.mean(percentages):.1f}%")
        print(f"Trend slope: {slope:.3f}% per assessment")

        if slope > 1:
            print("📈 Student showing improvement trend")
        elif slope < -1:
            print("📉 Student showing declining trend - intervention needed")
        else:
            print("📊 Student performance is stable")

        # Performance by assessment type
        type_performance = {}
        for grade in student_grades:
            assess_type = grade[4]
            if assess_type not in type_performance:
                type_performance[assess_type] = []
            type_performance[assess_type].append(grade[1])

        print(f"\nPerformance by Assessment Type:")
        for assess_type, scores in type_performance.items():
            avg_score = np.mean(scores)
            print(f"  {assess_type}: {avg_score:.1f}% (n={len(scores)})")

        # Recent vs. early performance
        if len(percentages) >= 6:
            recent_avg = np.mean(percentages[-3:])
            early_avg = np.mean(percentages[:3])
            change = recent_avg - early_avg

            print(f"\nPerformance Change:")
            print(f"Early average (first 3): {early_avg:.1f}%")
            print(f"Recent average (last 3): {recent_avg:.1f}%")
            print(f"Change: {change:+.1f}%")

    # Create individual trend visualization
    create_individual_trend_visualization(student_grades, student_id, first_name, last_name)

def analyze_single_course_trends(cursor, course):
    """Analyze trends for a single course"""
    print(f"\n--- Trend Analysis for {course} ---")

    # Get monthly performance data for this course
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    JOIN student_modules sm ON a.module_code = sm.module_code
    JOIN students s ON sm.student_id = s.student_id
    WHERE s.course = ? AND g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    HAVING grade_count >= 3
    ORDER BY month
    ''', (course,))

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

def analyze_seasonal_trends(cursor):
    """Analyze seasonal/time-based performance trends"""
    print("\nSeasonal Trends Analysis")

    print("\nAnalysis Options:")
    print("1. Monthly patterns")
    print("2. Day of week patterns")
    print("3. Academic term patterns")

    choice = input("Enter your choice (1-3): ").strip()

    if choice == '1':
        analyze_monthly_patterns(cursor)
    elif choice == '2':
        analyze_day_of_week_patterns(cursor)
    elif choice == '3':
        analyze_academic_term_patterns(cursor)
    else:
        print("Invalid choice.")

def analyze_monthly_patterns(cursor):
    """Analyze performance patterns by month"""
    cursor.execute('''
    SELECT strftime('%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY strftime('%m', g.submission_date)
    HAVING grade_count >= 10
    ORDER BY month
    ''')

    monthly_patterns = cursor.fetchall()

    if not monthly_patterns:
        print("Insufficient data for monthly pattern analysis.")
        return

    print("\nMonthly Performance Patterns:")
    print("-" * 50)
    print(f"{'Month':<10} {'Avg Score':<12} {'Assessments':<12}")
    print("-" * 50)

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    for month, avg_score, count in monthly_patterns:
        month_name = month_names[int(month) - 1]
        print(f"{month_name:<10} {avg_score:<12.1f}% {count:<12}")

def analyze_day_of_week_patterns(cursor):
    """Analyze performance patterns by day of week"""
    cursor.execute('''
    SELECT strftime('%w', g.submission_date) as day_of_week,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY strftime('%w', g.submission_date)
    HAVING grade_count >= 5
    ORDER BY day_of_week
    ''')

    daily_patterns = cursor.fetchall()

    if not daily_patterns:
        print("Insufficient data for daily pattern analysis.")
        return

    print("\nDay of Week Performance Patterns:")
    print("-" * 50)
    print(f"{'Day':<10} {'Avg Score':<12} {'Assessments':<12}")
    print("-" * 50)

    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 
                 'Thursday', 'Friday', 'Saturday']

    for day_num, avg_score, count in daily_patterns:
        day_name = day_names[int(day_num)]
        print(f"{day_name:<10} {avg_score:<12.1f}% {count:<12}")

def analyze_academic_term_patterns(cursor):
    """Analyze performance patterns by academic terms"""
    print("\nAcademic Term Pattern Analysis")

    # This is a simplified version - in practice, you'd need term/semester information
    cursor.execute('''
    SELECT strftime('%Y', g.submission_date) as year,
           CASE 
               WHEN strftime('%m', g.submission_date) IN ('01','02','03','04','05') THEN 'Spring'
               WHEN strftime('%m', g.submission_date) IN ('06','07','08') THEN 'Summer'
               ELSE 'Fall'
           END as term,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY year, term
    HAVING grade_count >= 10
    ORDER BY year, term
    ''')

    term_patterns = cursor.fetchall()

    if not term_patterns:
        print("Insufficient data for term pattern analysis.")
        return

    print("\nTerm Performance Patterns:")
    print("-" * 60)
    print(f"{'Year':<6} {'Term':<10} {'Avg Score':<12} {'Assessments':<12}")
    print("-" * 60)

    for year, term, avg_score, count in term_patterns:
        print(f"{year:<6} {term:<10} {avg_score:<12.1f}% {count:<12}")

def trend_forecasting():
    """Forecast academic trends"""
    print("\nTrend Forecasting System")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nForecasting Options:")
        print("1. Overall Performance Trends")
        print("2. Course Performance Forecasting")
        print("3. Module Difficulty Trends")
        print("4. Assessment Performance Forecasting")
        print("5. Student Success Rate Trends")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == '1':
            try:
                from education_system.university_system.modules.domain.academics.grading.performance_analytics import forecast_overall_performance
                forecast_overall_performance(cursor)
            except Exception as e:
                print(f"(overall forecast unavailable: {e})")

        elif choice == '2':
            try:
                from education_system.university_system.modules.domain.academics.grading.performance_analytics import forecast_course_performance
                forecast_course_performance(cursor)
            except Exception as e:
                print(f"(course forecast unavailable: {e})")

        elif choice == '3':
            try:
                from education_system.university_system.modules.domain.academics.grading.forecasting import forecast_module_difficulty
                forecast_module_difficulty(cursor)
            except Exception as e:
                print(f"(module difficulty forecast unavailable: {e})")

        elif choice == '4':
            try:
                from education_system.university_system.modules.domain.academics.grading.grade_calculation import forecast_assessment_performance
                forecast_assessment_performance(cursor)
            except Exception as e:
                print(f"(assessment forecast unavailable: {e})")

        elif choice == '5':
            forecast_success_rates(cursor)
        else:
            print("Invalid choice. Returning to menu.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def create_trend_visualization(daily_trends, monthly_trends, chart_type):
    """Create trend visualization charts"""
    try:
        viz_dir = os.path.join(_DATA_REPORTS_DIR, 'trend_visualizations')
        if not os.path.exists(viz_dir):
            os.makedirs(viz_dir)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # Daily trends
        if daily_trends:
            dates = [trend[0] for trend in daily_trends]
            averages = [trend[1] for trend in daily_trends]

            ax1.plot(dates, averages, 'b-', marker='o', markersize=4)
            ax1.set_title('Daily Performance Trends')
            ax1.set_xlabel('Date')
            ax1.set_ylabel('Average Performance (%)')
            ax1.grid(True, alpha=0.3)

            # Add trend line
            x = np.arange(len(averages))
            z = np.polyfit(x, averages, 1)
            p = np.poly1d(z)
            ax1.plot(dates, p(x), "r--", alpha=0.8, label=f'Trend: {z[0]:.2f}%/day')
            ax1.legend()

            # Rotate x-axis labels for better readability
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Monthly trends
        if monthly_trends:
            months = [trend[0] for trend in monthly_trends]
            monthly_averages = [trend[1] for trend in monthly_trends]

            ax2.bar(months, monthly_averages, color='skyblue', alpha=0.7)
            ax2.set_title('Monthly Performance Trends')
            ax2.set_xlabel('Month')
            ax2.set_ylabel('Average Performance (%)')
            ax2.grid(True, alpha=0.3, axis='y')

            # Rotate x-axis labels
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()

        # Save the visualization
        viz_filename = f"{viz_dir}/{chart_type}_{timestamp}.png"
        plt.savefig(viz_filename, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"Trend visualization saved: {viz_filename}")
    except Exception as e:
        print(f"Error creating trend visualization: {e}")

def create_individual_trend_visualization(student_grades, student_id, first_name, last_name):
    """Create individual student trend visualization"""
    viz_dir = os.path.join(_DATA_REPORTS_DIR, 'student_trends')
    if not os.path.exists(viz_dir):
        os.makedirs(viz_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Prepare data
    dates = [grade[0] for grade in student_grades]
    percentages = [grade[1] for grade in student_grades]
    assessment_names = [grade[2] for grade in student_grades]

    # Create visualization
    plt.figure(figsize=(12, 8))

    # Main trend line
    plt.plot(range(len(percentages)), percentages, 'b-', marker='o', markersize=6, linewidth=2)

    # Add trend line
    x = np.arange(len(percentages))
    z = np.polyfit(x, percentages, 1)
    p = np.poly1d(z)
    plt.plot(x, p(x), "r--", alpha=0.8, linewidth=2, label=f'Trend: {z[0]:.2f}%/assessment')

    # Add rolling average
    if len(percentages) >= 3:
        window_size = min(3, len(percentages))
        rolling_avg = []
        rolling_x = []
        for i in range(len(percentages) - window_size + 1):
            avg = np.mean(percentages[i:i + window_size])
            rolling_avg.append(avg)
            rolling_x.append(i + window_size - 1)

        plt.plot(rolling_x, rolling_avg, 'g-', alpha=0.7, linewidth=2, label='3-Assessment Moving Average')

    # Formatting
    plt.title(f'Performance Trend: {first_name} {last_name}', fontsize=16, fontweight='bold')
    plt.xlabel('Assessment Number', fontsize=12)
    plt.ylabel('Performance (%)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()

    # Add assessment labels on x-axis (abbreviated)
    if len(assessment_names) <= 15:  # Only if not too many assessments
        abbreviated_names = [name[:10] + '...' if len(name) > 10 else name for name in assessment_names]
        plt.xticks(range(len(abbreviated_names)), abbreviated_names, rotation=45, ha='right')

    plt.tight_layout()

    # Save the visualization
    viz_filename = f"{viz_dir}/student_trend_{student_id}_{timestamp}.png"
    plt.savefig(viz_filename, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Individual trend visualization saved: {viz_filename}")

def create_course_comparison_charts(comparison_data):
    """Create course comparison charts"""
    try:
        viz_dir = os.path.join(_DATA_REPORTS_DIR, 'course_comparisons')
        if not os.path.exists(viz_dir):
            os.makedirs(viz_dir)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Create figure with multiple subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

        courses = [data['course'] for data in comparison_data]

        # 1. Average GPA comparison
        gpas = [data['avg_gpa'] for data in comparison_data]
        ax1.bar(courses, gpas, color='skyblue', alpha=0.7)
        ax1.set_title('Average GPA by Course')
        ax1.set_ylabel('Average GPA')
        ax1.set_ylim(0, 4.5)
        for i, gpa in enumerate(gpas):
            ax1.text(i, gpa + 0.05, f'{gpa:.2f}', ha='center', va='bottom')
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # 2. Passing rate comparison
        passing_rates = [data['passing_rate'] for data in comparison_data]
        ax2.bar(courses, passing_rates, color='lightgreen', alpha=0.7)
        ax2.set_title('Passing Rate by Course')
        ax2.set_ylabel('Passing Rate (%)')
        ax2.set_ylim(0, 105)
        for i, rate in enumerate(passing_rates):
            ax2.text(i, rate + 1, f'{rate:.1f}%', ha='center', va='bottom')
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        # 3. Excellence rate comparison
        excellence_rates = [data['excellence_rate'] for data in comparison_data]
        ax3.bar(courses, excellence_rates, color='gold', alpha=0.7)
        ax3.set_title('Excellence Rate by Course (A grades)')
        ax3.set_ylabel('Excellence Rate (%)')
        ax3.set_ylim(0, max(excellence_rates) + 10 if excellence_rates else 10)
        for i, rate in enumerate(excellence_rates):
            ax3.text(i, rate + 0.5, f'{rate:.1f}%', ha='center', va='bottom')
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)

        # 4. Standard deviation comparison
        std_devs = [data['std_dev'] for data in comparison_data]
        ax4.bar(courses, std_devs, color='salmon', alpha=0.7)
        ax4.set_title('Performance Variability by Course')
        ax4.set_ylabel('Standard Deviation')
        for i, std in enumerate(std_devs):
            ax4.text(i, std + 0.2, f'{std:.1f}', ha='center', va='bottom')
        plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()

        # Save the visualization
        viz_filename = f"{viz_dir}/course_comparison_{timestamp}.png"
        plt.savefig(viz_filename, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"Course comparison charts saved: {viz_filename}")
    except Exception as e:
        print(f"Error creating course comparison charts: {e}")
