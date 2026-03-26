from __future__ import annotations

import csv

import numpy as np

from education_system.university_system.modules.domain.academics.grading.utils import _get_calculate_course_statistics

def compare_by_course(cursor):
    """Compare performance across different courses"""
    print("\nCourse Performance Comparison")

    # Get all courses with student data
    cursor.execute('''
    SELECT DISTINCT s.course, COUNT(s.student_id) as student_count
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    GROUP BY s.course
    ORDER BY s.course
    ''')

    courses = cursor.fetchall()

    if not courses:
        print("No course data found.")
        return

    print(f"\nAnalyzing {len(courses)} courses...")

    comparison_data = []

    for course, student_count in courses:
        # Calculate course statistics
        stats = _get_calculate_course_statistics()(cursor, course)
        if stats:
            stats['student_count'] = student_count
            comparison_data.append(stats)

    # Display results
    display_course_comparison(comparison_data)

    # Generate visualization
    visualize = input("\nGenerate comparison charts? (y/n): ").strip().lower()
    if visualize == 'y':
        create_course_comparison_charts(comparison_data)

    # Export option
    export = input("Export comparison data? (y/n): ").strip().lower()
    if export == 'y':
        export_comparison_data(comparison_data, "course_comparison")

def display_course_comparison(comparison_data):
    """Display course comparison results"""
    print("\n" + "="*100)
    print("COURSE PERFORMANCE COMPARISON")
    print("="*100)

    # Sort by average GPA
    comparison_data.sort(key=lambda x: x['avg_gpa'], reverse=True)

    print(f"{'Course':<15} {'Students':<10} {'Avg GPA':<10} {'Avg Score':<12} {'Pass Rate':<12} {'Excellence':<12} {'Std Dev':<10}")
    print("-" * 100)

    for data in comparison_data:
        print(f"{data['course']:<15} {data['student_count']:<10} {data['avg_gpa']:<10.2f} "
              f"{data['avg_score']:<12.1f}% {data['passing_rate']:<12.1f}% "
              f"{data['excellence_rate']:<12.1f}% {data['std_dev']:<10.1f}")

    # Statistical analysis
    print("\n" + "="*50)
    print("STATISTICAL ANALYSIS")
    print("="*50)

    gpas = [d['avg_gpa'] for d in comparison_data]
    scores = [d['avg_score'] for d in comparison_data]

    if not gpas:
        print("No data available for statistical analysis.")
        return

    print(f"GPA Range: {min(gpas):.2f} - {max(gpas):.2f}")
    print(f"Score Range: {min(scores):.1f}% - {max(scores):.1f}%")
    print(f"GPA Standard Deviation: {np.std(gpas):.2f}")
    print(f"Score Standard Deviation: {np.std(scores):.1f}%")

    # Identify best and worst performing courses
    best_course = max(comparison_data, key=lambda x: x['avg_gpa'])
    worst_course = min(comparison_data, key=lambda x: x['avg_gpa'])

    print(f"\nBest Performing Course: {best_course['course']} (GPA: {best_course['avg_gpa']:.2f})")
    print(f"Worst Performing Course: {worst_course['course']} (GPA: {worst_course['avg_gpa']:.2f})")

def compare_by_gender(cursor):
    """Compare performance by gender"""
    print("\nGender Performance Comparison")

    # Get performance data by gender
    cursor.execute('''
    SELECT s.gender, 
           COUNT(DISTINCT s.student_id) as student_count,
           AVG(mg.final_score) as avg_score,
           COUNT(mg.final_grade) as total_grades
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    WHERE s.gender IS NOT NULL AND s.gender != ''
    GROUP BY s.gender
    ''')

    gender_data = cursor.fetchall()

    if not gender_data:
        print("No gender data available for comparison.")
        return

    print("\nGender Performance Summary:")
    print("-" * 60)
    print(f"{'Gender':<10} {'Students':<10} {'Avg Score':<12} {'Total Grades':<12}")
    print("-" * 60)

    gender_stats = []

    for gender, student_count, avg_score, total_grades in gender_data:
        print(f"{gender.capitalize():<10} {student_count:<10} {avg_score:<12.1f}% {total_grades:<12}")

        # Get detailed statistics for this gender
        cursor.execute('''
        SELECT mg.final_grade
        FROM module_grades mg
        JOIN students s ON mg.student_id = s.student_id
        WHERE s.gender = ?
        ''', (gender,))

        grades = [row[0] for row in cursor.fetchall()]

        # Calculate passing rate
        passing_count = sum(1 for grade in grades if grade not in ['F'])
        passing_rate = (passing_count / len(grades)) * 100 if grades else 0

        # Calculate excellence rate
        excellence_count = sum(1 for grade in grades if grade in ['A+', 'A', 'A-'])
        excellence_rate = (excellence_count / len(grades)) * 100 if grades else 0

        gender_stats.append({
            'gender': gender.capitalize(),
            'student_count': student_count,
            'avg_score': avg_score,
            'passing_rate': passing_rate,
            'excellence_rate': excellence_rate,
            'total_grades': total_grades
        })

    # Display detailed comparison
    print("\nDetailed Performance Comparison:")
    print("-" * 80)
    print(f"{'Gender':<10} {'Avg Score':<12} {'Pass Rate':<12} {'Excellence Rate':<15}")
    print("-" * 80)

    for stats in gender_stats:
        print(f"{stats['gender']:<10} {stats['avg_score']:<12.1f}% "
              f"{stats['passing_rate']:<12.1f}% {stats['excellence_rate']:<15.1f}%")

    # Statistical significance test (if we have enough data)
    if len(gender_stats) == 2:
        perform_statistical_test(cursor, gender_stats)

def compare_by_module_type(cursor):
    """Compare performance by module type"""
    print("\nModule Type Performance Comparison")

    cursor.execute('''
    SELECT m.module_type,
           COUNT(mg.id) as total_enrollments,
           AVG(mg.final_score) as avg_score,
           COUNT(DISTINCT mg.student_id) as unique_students
    FROM modules m
    JOIN module_grades mg ON m.module_code = mg.module_code
    GROUP BY m.module_type
    ORDER BY avg_score DESC
    ''')

    module_type_data = cursor.fetchall()

    if not module_type_data:
        print("No module type data available.")
        return

    print("\nModule Type Performance Summary:")
    print("-" * 80)
    print(f"{'Module Type':<20} {'Enrollments':<12} {'Students':<10} {'Avg Score':<12}")
    print("-" * 80)

    for module_type, enrollments, avg_score, students in module_type_data:
        print(f"{module_type:<20} {enrollments:<12} {students:<10} {avg_score:<12.1f}%")

        # Get passing rate for this module type
        cursor.execute('''
        SELECT mg.final_grade
        FROM module_grades mg
        JOIN modules m ON mg.module_code = m.module_code
        WHERE m.module_type = ?
        ''', (module_type,))

        grades = [row[0] for row in cursor.fetchall()]
        passing_count = sum(1 for grade in grades if grade not in ['F'])
        passing_rate = (passing_count / len(grades)) * 100 if grades else 0

        print(f"{'Passing Rate:':<20} {passing_rate:.1f}%")
        print()

def compare_by_assessment_type(cursor):
    """Compare performance by assessment type"""
    print("\nAssessment Type Performance Comparison")
    # Gather per-type aggregates
    cursor.execute('''
    SELECT a.assessment_type,
           COUNT(DISTINCT a.id) AS total_assessments,
           AVG(CASE
                 WHEN g.score IS NOT NULL AND a.max_points IS NOT NULL AND a.max_points > 0
                 THEN (CAST(g.score AS REAL) / a.max_points) * 100
               END) AS avg_percentage,
           COUNT(g.id) AS grade_count
      FROM assessments a
 LEFT JOIN grades g ON a.id = g.assessment_id
     GROUP BY a.assessment_type
     ORDER BY avg_percentage DESC
    ''')
    rows = cursor.fetchall() or []
    if not rows:
        print("No assessment data found.")
        return

    results = []
    for assess_type, total_assessments, avg_pct, grade_count in rows:
        # Compute passing rate using letter grades where available
        try:
            cursor.execute('''
            SELECT g.letter_grade
              FROM assessments a
              JOIN grades g ON a.id = g.assessment_id
             WHERE a.assessment_type = ? AND g.letter_grade IS NOT NULL
            ''', (assess_type,))
            letters = [r[0] for r in cursor.fetchall()]
            denom = len(letters)
            passing = sum(1 for lg in letters if lg and lg.upper() != 'F')
            passing_rate = (passing / denom * 100.0) if denom else 0.0
        except Exception:
            passing_rate = 0.0

        results.append({
            "assessment_type": assess_type or "Unknown",
            "total_assessments": int(total_assessments or 0),
            "avg_percentage": float(avg_pct or 0.0),
            "grade_count": int(grade_count or 0),
            "passing_rate": float(passing_rate),
        })

    # Display
    print("\n" + "="*100)
    print(f"{'Assessment Type':<25} {'Assessments':>12} {'Grades':>8} {'Avg %':>8} {'Passing %':>11}")
    print("-"*100)
    for r in results:
        print(f"{r['assessment_type']:<25} {r['total_assessments']:>12} {r['grade_count']:>8} {r['avg_percentage']:>8.1f} {r['passing_rate']:>11.1f}")
    print("="*100)

    # Optional export
    export = input("Export comparison data? (y/n): ").strip().lower()
    if export == 'y':
        try:
            export_comparison_data(results, "assessment_type_comparison")
            print("Exported assessment type comparison.")
        except Exception as e:
            print(f"Export failed: {e}")

def perform_statistical_test(cursor, gender_stats):
    """Perform statistical significance test between genders"""
    if len(gender_stats) != 2:
        return

    print(f"\nStatistical Significance Test:")

    # Get raw scores for each gender
    gender1, gender2 = gender_stats[0]['gender'], gender_stats[1]['gender']

    cursor.execute('''
    SELECT mg.final_score
    FROM module_grades mg
    JOIN students s ON mg.student_id = s.student_id
    WHERE s.gender = ?
    ''', (gender1.lower(),))

    scores1 = [row[0] for row in cursor.fetchall() if row[0] is not None]

    cursor.execute('''
    SELECT mg.final_score
    FROM module_grades mg
    JOIN students s ON mg.student_id = s.student_id
    WHERE s.gender = ?
    ''', (gender2.lower(),))

    scores2 = [row[0] for row in cursor.fetchall() if row[0] is not None]

    if len(scores1) >= 10 and len(scores2) >= 10:
        # Perform t-test
        from scipy.stats import ttest_ind

        t_stat, p_value = ttest_ind(scores1, scores2)

        print(f"T-test results:")
        print(f"  {gender1} sample size: {len(scores1)}")
        print(f"  {gender2} sample size: {len(scores2)}")
        print(f"  T-statistic: {t_stat:.3f}")
        print(f"  P-value: {p_value:.3f}")

        if p_value < 0.05:
            print("  Result: Statistically significant difference (p < 0.05)")
        else:
            print("  Result: No statistically significant difference (p >= 0.05)")
    else:
        print("Insufficient sample size for statistical test (need at least 10 in each group)")

def compare_by_time_period(cursor):
    """Compare performance by time period"""
    print("\nTime Period Performance Comparison")

    # Get performance by month
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.id
    WHERE g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    HAVING grade_count >= 5
    ORDER BY month
    ''')

    monthly_data = cursor.fetchall()

    if not monthly_data:
        print("Insufficient time-based data for comparison.")
        return

    print(f"\nMonthly Performance Comparison:")
    print("-" * 60)
    print(f"{'Month':<10} {'Avg Score':<12} {'Assessments':<12}")
    print("-" * 60)

    for month, avg_score, count in monthly_data:
        print(f"{month:<10} {avg_score:<12.1f}% {count:<12}")

    # Calculate trend
    if len(monthly_data) >= 3:
        scores = [data[1] for data in monthly_data]
        trend_slope = calculate_trend_slope(scores)

        print(f"\nTrend Analysis:")
        print(f"Overall trend: {trend_slope:+.2f}% per month")

        if trend_slope > 1:
            print("📈 Performance is improving over time")
        elif trend_slope < -1:
            print("📉 Performance is declining over time")
        else:
            print("📊 Performance is relatively stable over time")

def custom_group_comparison(cursor):
    """Perform custom group comparison"""
    print("\nCustom Group Comparison")

    print("\nSelect grouping criteria:")
    print("1. By specific module codes")
    print("2. By grade threshold")
    print("3. By enrollment date range")
    print("4. By specific courses")

    choice = input("Enter your choice (1-4): ").strip()

    if choice == '1':
        compare_by_module_codes(cursor)
    elif choice == '2':
        compare_by_grade_threshold(cursor)
    elif choice == '3':
        compare_by_enrollment_date(cursor)
    elif choice == '4':
        compare_by_specific_courses(cursor)
    else:
        print("Invalid choice.")

def compare_by_module_codes(cursor):
    """Compare performance by specific module codes"""
    print("\nModule Code Comparison")

    # Get available modules
    cursor.execute('SELECT DISTINCT module_code FROM modules ORDER BY module_code')
    modules = [row[0] for row in cursor.fetchall()]

    if not modules:
        print("No modules found.")
        return

    print(f"\nAvailable modules: {', '.join(modules)}")

    module_codes = input("Enter module codes to compare (comma-separated): ").strip()
    selected_modules = [code.strip().upper() for code in module_codes.split(',')]

    # Validate modules
    valid_modules = [mod for mod in selected_modules if mod in modules]

    if len(valid_modules) < 2:
        print("Please select at least 2 valid modules for comparison.")
        return

    print(f"\nComparing modules: {', '.join(valid_modules)}")
    print("-" * 60)
    print(f"{'Module':<12} {'Students':<10} {'Avg Score':<12} {'Pass Rate':<12}")
    print("-" * 60)

    for module in valid_modules:
        cursor.execute('''
        SELECT COUNT(*) as student_count,
               AVG(final_score) as avg_score
        FROM module_grades
        WHERE module_code = ?
        ''', (module,))

        result = cursor.fetchone()
        if result and result[0] > 0:
            student_count, avg_score = result

            # Calculate passing rate
            cursor.execute('''
            SELECT COUNT(*) as passing_count
            FROM module_grades
            WHERE module_code = ? AND final_grade != 'F'
            ''', (module,))

            passing_count = cursor.fetchone()[0]
            passing_rate = (passing_count / student_count) * 100 if student_count > 0 else 0

            print(f"{module:<12} {student_count:<10} {avg_score:<12.1f}% {passing_rate:<12.1f}%")

def compare_by_enrollment_date(cursor):
    """Compare performance by enrollment date ranges"""
    print("\nEnrollment Date Range Comparison")

    # Get enrollment date range
    cursor.execute('''
    SELECT MIN(enrollment_date) as min_date, MAX(enrollment_date) as max_date
    FROM students
    WHERE enrollment_date IS NOT NULL
    ''')

    result = cursor.fetchone()
    if not result or not result[0]:
        print("No enrollment date information available.")
        return

    min_date, max_date = result
    print(f"Available enrollment date range: {min_date} to {max_date}")

    early_date = input("Enter early period end date (YYYY-MM-DD): ").strip()
    late_date = input("Enter late period start date (YYYY-MM-DD): ").strip()

    # Get students in each period
    cursor.execute('''
    SELECT s.student_id, s.enrollment_date
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    WHERE s.enrollment_date <= ?
    ''', (early_date,))

    early_students = [row[0] for row in cursor.fetchall()]

    cursor.execute('''
    SELECT s.student_id, s.enrollment_date
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    WHERE s.enrollment_date >= ?
    ''', (late_date,))

    late_students = [row[0] for row in cursor.fetchall()]

    if not early_students or not late_students:
        print("Insufficient data for comparison.")
        return

    # Calculate performance for each group
    from education_system.university_system.modules.domain.academics.grading.grade_calculation import calculate_student_gpa

    early_gpas = []
    late_gpas = []

    for student_id in early_students:
        gpa, _, _ = calculate_student_gpa(cursor, student_id)
        if gpa is not None:
            early_gpas.append(gpa)

    for student_id in late_students:
        gpa, _, _ = calculate_student_gpa(cursor, student_id)
        if gpa is not None:
            late_gpas.append(gpa)

    print(f"\nEnrollment Period Comparison:")
    print(f"Early period (≤{early_date}): {len(early_students)} students, Avg GPA: {np.mean(early_gpas):.2f}")
    print(f"Late period (≥{late_date}): {len(late_students)} students, Avg GPA: {np.mean(late_gpas):.2f}")

def compare_by_specific_courses(cursor):
    """Compare performance between specific courses"""
    print("\nSpecific Course Comparison")

    # Get available courses
    cursor.execute('SELECT DISTINCT course FROM students ORDER BY course')
    courses = [row[0] for row in cursor.fetchall()]

    if len(courses) < 2:
        print("Need at least 2 courses for comparison.")
        return

    print(f"\nAvailable courses: {', '.join(courses)}")

    course_input = input("Enter courses to compare (comma-separated): ").strip()
    selected_courses = [course.strip().upper() for course in course_input.split(',')]

    # Validate courses
    valid_courses = [course for course in selected_courses if course in courses]

    if len(valid_courses) < 2:
        print("Please select at least 2 valid courses for comparison.")
        return

    print(f"\nComparing courses: {', '.join(valid_courses)}")

    # Get performance data for each course
    calc_fn = _get_calculate_course_statistics()
    for course in valid_courses:
        try:
            stats = calc_fn(cursor, course) if calc_fn else None
            if stats:
                print(f"\n{course}:")
                print(f"  Students: {stats.get('student_count', stats.get('count', 'N/A'))}")
                print(f"  Average GPA: {stats.get('avg_gpa', 0):.2f}")
                print(f"  Average Score: {stats.get('avg_score', 0):.1f}%")
                print(f"  Passing Rate: {stats.get('passing_rate', 0):.1f}%")
        except Exception:
            print(f"\n{course}: Unable to calculate statistics")
