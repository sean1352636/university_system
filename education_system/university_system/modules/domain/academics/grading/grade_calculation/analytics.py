import numpy as np
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.academics.grading.grade_calculation.conversions import letter_to_gpa
from education_system.university_system.modules.domain.academics.grading.grade_calculation.utils import (
    select_assessment,
    calculate_trend_slope,
)
from education_system.university_system.modules.domain.academics.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.university_system.modules.domain.academics.grading.grade_calculation.visualization import create_trend_visualization


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
        from education_system.university_system.modules.students.grade_curve_analysis import (
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
            print("Significant trend detected - requires attention")
        elif trend_magnitude > 2:
            print("Moderate trend detected - monitor closely")
        else:
            print("Performance is relatively stable")

    # Create visualization
    create_trend_visualization(daily_trends, monthly_trends, "overall_trends")


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
        print("Status: Improving")
    elif trend_slope < -1:
        print("Status: Declining")
    else:
        print("Status: Stable")
