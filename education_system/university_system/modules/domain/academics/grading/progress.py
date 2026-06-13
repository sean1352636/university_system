from __future__ import annotations

import os
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.grading.utils import select_student
from education_system.university_system.core.i18n import get_text

def student_progress_tracking():
    """Track individual student progress over time"""
    print("\n" + get_text("academics.progress.title"))

    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = select_student(cursor)
        if not student_id:
            conn.close()
            return

        # Get student info
        cursor.execute('''
        SELECT first_name, last_name, course
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()
        if not student:
            print(get_text("academics.progress.student_not_found"))
            conn.close()
            return

        first_name, last_name, course = student
        print("\n" + get_text("academics.progress.tracking_for", first_name=first_name, last_name=last_name, course=course))

        # Get grades over time
        cursor.execute('''
        SELECT g.score / a.max_points * 100 as percentage,
               g.letter_grade, g.submission_date, a.assessment_name,
               a.module_code, a.assessment_type
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.id
        WHERE g.student_id = ?
        ORDER BY g.submission_date
        ''', (student_id,))

        grades = cursor.fetchall()

        if not grades:
            print(get_text("academics.progress.no_grades_found"))
            conn.close()
            return

        # Analyze progress
        analyze_student_progress(grades, first_name, last_name)

        # Visualize if requested
        visualize = input("\n" + get_text("academics.progress.generate_visualization_prompt") + " ").strip().lower()
        if visualize == 'y':
            create_progress_visualization(grades, student_id, first_name, last_name)

        conn.close()

    except sqlite3.Error as e:
        print(get_text("academics.progress.database_error", error=e))

def analyze_student_progress(grades, first_name, last_name):
    """Analyze a student's academic progress"""
    percentages = [g[0] for g in grades]
    dates = [g[2] for g in grades]

    # Calculate trends
    if len(percentages) >= 3:
        # Simple linear trend
        x = list(range(len(percentages)))
        slope = np.polyfit(x, percentages, 1)[0]

        if slope > 1:
            trend = get_text("academics.progress.trend_improving")
        elif slope < -1:
            trend = get_text("academics.progress.trend_declining")
        else:
            trend = get_text("academics.progress.trend_stable")
    else:
        trend = get_text("academics.progress.trend_insufficient_data")

    # Calculate statistics
    avg_performance = np.mean(percentages)
    recent_performance = np.mean(percentages[-3:]) if len(percentages) >= 3 else avg_performance
    early_performance = np.mean(percentages[:3]) if len(percentages) >= 3 else avg_performance

    # Performance by assessment type
    type_performance = {}
    for grade in grades:
        assess_type = grade[5]
        if assess_type not in type_performance:
            type_performance[assess_type] = []
        type_performance[assess_type].append(grade[0])

    print(f"\nProgress Analysis:")
    print(f"Total Assessments: {len(grades)}")
    print(f"Overall Average: {avg_performance:.1f}%")
    print(f"Recent Performance (last 3): {recent_performance:.1f}%")
    print(f"Trend: {trend}")

    if len(percentages) >= 3:
        change = recent_performance - early_performance
        print(f"Performance Change: {change:+.1f}%")

    print(f"\nPerformance by Assessment Type:")
    for assess_type, scores in type_performance.items():
        avg_score = np.mean(scores)
        print(f"  {assess_type}: {avg_score:.1f}% (n={len(scores)})")

def success_probability_calculator():
    """Calculate probability of academic success for students"""
    print("\nSuccess Probability Calculator")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Choose calculation method
        print("\nCalculation Method:")
        print("1. Individual Student")
        print("2. All Students")

        choice = input("Enter choice (1-2): ").strip()

        if choice == '1':
            student_id = select_student(cursor)
            if student_id:
                calculate_individual_success_probability(cursor, student_id)
        else:
            calculate_all_students_success_probability(cursor)

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def calculate_individual_success_probability(cursor, student_id):
    """Calculate success probability for individual student"""
    from education_system.university_system.modules.domain.academics.grading.grade_calculation import calculate_student_gpa

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

    # Calculate various factors
    gpa, _, _ = calculate_student_gpa(cursor, student_id)

    # Get submission rate
    cursor.execute('''
    SELECT COUNT(DISTINCT a.id) as total,
           COUNT(g.id) as submitted
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.id = g.assessment_id AND g.student_id = sm.student_id
    WHERE sm.student_id = ?
    ''', (student_id,))

    result = cursor.fetchone()
    submission_rate = result[1] / result[0] if result and result[0] > 0 else 0

    # Get performance trend
    cursor.execute('''
    SELECT g.score / a.max_points * 100
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.id
    WHERE g.student_id = ?
    ORDER BY g.submission_date DESC
    LIMIT 5
    ''', (student_id,))

    recent_scores = [r[0] for r in cursor.fetchall()]
    recent_avg = np.mean(recent_scores) if recent_scores else 0

    # Calculate success probability using weighted factors
    probability = 0
    factors = []

    # GPA factor (40% weight)
    if gpa:
        gpa_factor = min(gpa / 4.0, 1.0)
        probability += gpa_factor * 0.4
        factors.append(f"GPA: {gpa:.2f} (contributes {gpa_factor*40:.1f}%)")

    # Submission rate factor (25% weight)
    probability += submission_rate * 0.25
    factors.append(f"Submission Rate: {submission_rate*100:.1f}% (contributes {submission_rate*25:.1f}%)")

    # Recent performance factor (25% weight)
    recent_factor = min(recent_avg / 100, 1.0)
    probability += recent_factor * 0.25
    factors.append(f"Recent Performance: {recent_avg:.1f}% (contributes {recent_factor*25:.1f}%)")

    # Consistency factor (10% weight)
    if len(recent_scores) >= 3:
        consistency = 1 - (np.std(recent_scores) / 100)
        consistency = max(0, consistency)
        probability += consistency * 0.1
        factors.append(f"Consistency: {consistency*100:.1f}% (contributes {consistency*10:.1f}%)")

    probability = min(probability, 1.0)  # Cap at 100%

    # Display results
    print(f"\nSuccess Probability for {first_name} {last_name}:")
    print(f"Overall Probability: {probability*100:.1f}%")
    print(f"\nFactor Breakdown:")
    for factor in factors:
        print(f"  • {factor}")

    # Interpretation
    if probability >= 0.8:
        interpretation = "High likelihood of academic success"
    elif probability >= 0.6:
        interpretation = "Good likelihood of success with continued effort"
    elif probability >= 0.4:
        interpretation = "Moderate success probability - intervention recommended"
    else:
        interpretation = "Low success probability - immediate intervention required"

    print(f"\nInterpretation: {interpretation}")

def calculate_all_students_success_probability(cursor):
    """Calculate success probability for all students"""
    print("\nSuccess Probability for All Students")

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
        return

    print(f"Calculating success probabilities for {len(students)} students...")

    success_data = []

    for student_id, first_name, last_name, course in students:
        probability = calculate_student_success_probability(cursor, student_id)

        if probability is not None:
            success_data.append({
                'student_id': student_id,
                'name': f"{first_name} {last_name}",
                'course': course,
                'probability': probability
            })

    # Sort by probability (lowest first - most at risk)
    success_data.sort(key=lambda x: x['probability'])

    # Display results
    print("\nSuccess Probability Results:")
    print("="*80)
    print(f"{'Name':<25} {'Course':<10} {'Success Prob':<15} {'Risk Level'}")
    print("-"*80)

    for data in success_data:
        prob = data['probability']

        if prob < 0.4:
            risk_level = "Very High Risk"
        elif prob < 0.6:
            risk_level = "High Risk"
        elif prob < 0.8:
            risk_level = "Moderate Risk"
        else:
            risk_level = "Low Risk"

        print(f"{data['name']:<25} {data['course']:<10} {prob*100:<15.1f}% {risk_level}")

    # Summary statistics
    probabilities = [d['probability'] for d in success_data]
    avg_prob = np.mean(probabilities)

    print(f"\nSummary Statistics:")
    print(f"Average Success Probability: {avg_prob*100:.1f}%")
    print(f"Students with <60% probability: {sum(1 for p in probabilities if p < 0.6)}")
    print(f"Students with >80% probability: {sum(1 for p in probabilities if p > 0.8)}")

def calculate_student_success_probability(cursor, student_id):
    """Calculate success probability for a single student"""
    from education_system.university_system.modules.domain.academics.grading.grade_calculation import calculate_student_gpa

    # Get student features
    gpa, _, _ = calculate_student_gpa(cursor, student_id)

    if not gpa:
        return None

    # Get submission rate
    cursor.execute('''
    SELECT COUNT(DISTINCT a.id) as total,
           COUNT(g.id) as submitted
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.id = g.assessment_id AND g.student_id = sm.student_id
    WHERE sm.student_id = ?
    ''', (student_id,))

    result = cursor.fetchone()
    submission_rate = result[1] / result[0] if result and result[0] > 0 else 0

    # Get recent performance
    cursor.execute('''
    SELECT g.score / a.max_points * 100
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.id
    WHERE g.student_id = ?
    ORDER BY g.submission_date DESC
    LIMIT 5
    ''', (student_id,))

    recent_scores = [r[0] for r in cursor.fetchall()]
    recent_avg = np.mean(recent_scores) if recent_scores else 0

    # Calculate probability using weighted factors
    probability = 0

    # GPA factor (40% weight)
    gpa_factor = min(gpa / 4.0, 1.0)
    probability += gpa_factor * 0.4

    # Submission rate factor (30% weight)
    probability += submission_rate * 0.3

    # Recent performance factor (30% weight)
    recent_factor = min(recent_avg / 100, 1.0)
    probability += recent_factor * 0.3

    return min(probability, 1.0)

def collect_dashboard_data(cursor):
    """Collect comprehensive data for the dashboard"""
    from education_system.university_system.modules.domain.academics.grading.grade_calculation import calculate_student_gpa

    dashboard_data = {}

    # 1. Overall Statistics
    cursor.execute('SELECT COUNT(*) FROM students')
    total_students = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM modules')
    total_modules = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM assessments')
    total_assessments = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM grades')
    total_grades = cursor.fetchone()[0]

    dashboard_data['overview'] = {
        'total_students': total_students,
        'total_modules': total_modules,
        'total_assessments': total_assessments,
        'total_grades': total_grades
    }

    # 2. GPA Statistics
    student_gpas = []
    cursor.execute('SELECT DISTINCT student_id FROM module_grades')
    students = cursor.fetchall()

    for (student_id,) in students:
        gpa, _, _ = calculate_student_gpa(cursor, student_id)
        if gpa is not None:
            student_gpas.append(gpa)

    if student_gpas:
        dashboard_data['gpa_stats'] = {
            'avg_gpa': np.mean(student_gpas),
            'median_gpa': np.median(student_gpas),
            'std_gpa': np.std(student_gpas),
            'min_gpa': min(student_gpas),
            'max_gpa': max(student_gpas),
            'students_with_gpa': len(student_gpas)
        }

    # 3. Grade Distribution
    cursor.execute('''
    SELECT final_grade, COUNT(*) as count
    FROM module_grades
    GROUP BY final_grade
    ''')

    grade_dist = dict(cursor.fetchall())
    total_module_grades = sum(grade_dist.values())

    dashboard_data['grade_distribution'] = {
        'distribution': grade_dist,
        'total_grades': total_module_grades,
        'passing_rate': ((total_module_grades - grade_dist.get('F', 0)) / total_module_grades * 100) if total_module_grades > 0 else 0
    }

    # 4. Course Performance
    cursor.execute('''
    SELECT s.course,
           COUNT(DISTINCT s.student_id) as students,
           AVG(mg.final_score) as avg_score
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    GROUP BY s.course
    ORDER BY avg_score DESC
    ''')

    dashboard_data['course_performance'] = cursor.fetchall()

    # 5. At-Risk Students
    at_risk_count = 0
    high_risk_count = 0

    for (student_id,) in students:
        gpa, _, _ = calculate_student_gpa(cursor, student_id)
        if gpa is not None:
            if gpa < 2.0:
                high_risk_count += 1
                at_risk_count += 1
            elif gpa < 2.5:
                at_risk_count += 1

    dashboard_data['risk_stats'] = {
        'at_risk_students': at_risk_count,
        'high_risk_students': high_risk_count,
        'at_risk_percentage': (at_risk_count / len(students) * 100) if students else 0
    }

    # 6. Recent Performance Trends
    cursor.execute('''
    SELECT DATE(g.submission_date) as date,
           AVG(g.score / a.max_points * 100) as avg_percentage
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.id
    WHERE g.submission_date >= date('now', '-30 days')
    GROUP BY DATE(g.submission_date)
    ORDER BY date
    ''')

    recent_trends = cursor.fetchall()
    dashboard_data['recent_trends'] = recent_trends

    return dashboard_data

def create_progress_visualization(grades, student_id, first_name, last_name):
    """Create progress visualization for a student"""
    viz_dir = 'student_progress'
    if not os.path.exists(viz_dir):
        os.makedirs(viz_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Prepare data
    percentages = [g[0] for g in grades]
    dates = [g[2] for g in grades]
    assessment_names = [g[3] for g in grades]
    modules = [g[4] for g in grades]

    # Create visualization
    plt.figure(figsize=(14, 8))

    # Main progress line
    plt.plot(range(len(percentages)), percentages, 'b-', marker='o',
             markersize=6, linewidth=2, label='Performance')

    # Add trend line
    if len(percentages) >= 3:
        x = np.arange(len(percentages))
        z = np.polyfit(x, percentages, 1)
        p = np.poly1d(z)
        plt.plot(x, p(x), "r--", alpha=0.8, linewidth=2,
                label=f'Trend: {z[0]:.2f}%/assessment')

    # Add moving average
    if len(percentages) >= 3:
        window_size = min(3, len(percentages))
        moving_avg = []
        for i in range(len(percentages) - window_size + 1):
            avg = np.mean(percentages[i:i + window_size])
            moving_avg.append(avg)

        # Plot moving average
        start_idx = window_size - 1
        x_avg = range(start_idx, start_idx + len(moving_avg))
        plt.plot(x_avg, moving_avg, 'g-', alpha=0.7, linewidth=2,
                label=f'{window_size}-Assessment Moving Average')

    # Formatting
    plt.title(f'Academic Progress: {first_name} {last_name}',
              fontsize=16, fontweight='bold')
    plt.xlabel('Assessment Number', fontsize=12)
    plt.ylabel('Performance (%)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()

    # Add horizontal reference lines
    plt.axhline(y=70, color='orange', linestyle=':', alpha=0.7, label='Pass Threshold')
    plt.axhline(y=85, color='green', linestyle=':', alpha=0.7, label='Excellence Threshold')

    # Set y-axis limits
    plt.ylim(0, 105)

    # Color code points by performance level
    colors = []
    for perc in percentages:
        if perc >= 85:
            colors.append('green')
        elif perc >= 70:
            colors.append('blue')
        elif perc >= 50:
            colors.append('orange')
        else:
            colors.append('red')

    plt.scatter(range(len(percentages)), percentages, c=colors, s=50, alpha=0.7, zorder=3)

    plt.tight_layout()

    # Save the visualization
    viz_filename = f"{viz_dir}/progress_{student_id}_{timestamp}.png"
    plt.savefig(viz_filename, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Progress visualization saved: {viz_filename}")

def save_intervention_recommendations(cursor, recommendations):
    """Save intervention recommendations to database"""
    for rec in recommendations:
        # Get or create risk assessment record
        cursor.execute('''
        SELECT id FROM student_risk_assessment
        WHERE student_id = ?
        ORDER BY assessment_date DESC
        LIMIT 1
        ''', (rec['student_id'],))

        risk_assessment = cursor.fetchone()

        if risk_assessment:
            risk_assessment_id = risk_assessment[0]

            # Clear existing recommendations
            cursor.execute('''
            DELETE FROM recommended_interventions
            WHERE risk_assessment_id = ?
            ''', (risk_assessment_id,))

            # Insert new recommendations
            for i, intervention in enumerate(rec['interventions'], 1):
                # Get intervention type ID
                cursor.execute('''
                SELECT type_id FROM intervention_types
                WHERE name = ?
                ''', (intervention['type'],))

                intervention_type = cursor.fetchone()
                if intervention_type:
                    cursor.execute('''
                    INSERT INTO recommended_interventions
                    (risk_assessment_id, intervention_type_id, priority, notes)
                    VALUES (?, ?, ?, ?)
                    ''', (risk_assessment_id, intervention_type[0],
                          intervention['priority'], intervention['description']))
