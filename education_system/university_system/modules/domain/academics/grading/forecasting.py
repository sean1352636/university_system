from __future__ import annotations

import csv
import os
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.grading.grade_calculation.conversions import letter_to_gpa
from education_system.university_system.core.i18n import get_text

def export_batch_predictions(predictions, prediction_type):
    """Export batch predictions to CSV"""
    exports_dir = 'prediction_exports'
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{exports_dir}/{prediction_type}_{timestamp}.csv"

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        if prediction_type == "next_assessment_predictions":
            writer.writerow(['Student ID', 'Name', 'Course', 'Predicted Score (%)',
                           'Predicted Grade', 'Confidence'])

            for pred in predictions:
                writer.writerow([
                    pred['student_id'],
                    pred['name'],
                    pred['course'],
                    f"{pred['predicted_score']:.1f}",
                    pred['predicted_grade'],
                    pred['confidence']
                ])

    print(get_text("academics.forecasting.batch_predictions_exported", filename=filename))

def forecast_single_course(cursor, course):
    """Forecast performance for a single course"""
    print("\n--- " + get_text("academics.forecasting.performance_forecast_title", course=course) + " ---")

    # Get historical monthly performance data
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.id
    JOIN student_modules sm ON a.module_code = sm.module_code
    JOIN students s ON sm.student_id = s.student_id
    WHERE s.course = ? AND g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    ORDER BY month
    ''', (course,))

    historical_data = cursor.fetchall()

    if len(historical_data) < 6:
        print(get_text("academics.forecasting.insufficient_data"))
        return

    # Prepare data for forecasting
    months = [data[0] for data in historical_data]
    averages = [data[1] for data in historical_data]

    # Simple linear trend forecasting
    x = np.arange(len(averages))
    coefficients = np.polyfit(x, averages, 1)
    trend_line = np.poly1d(coefficients)

    # Forecast next 3 months
    forecast_periods = 3
    future_x = np.arange(len(averages), len(averages) + forecast_periods)
    forecasted_values = trend_line(future_x)

    print(get_text("academics.forecasting.historical_period", start=months[0], end=months[-1]))
    print(get_text("academics.forecasting.current_average", avg=f"{np.mean(averages):.1f}"))
    print(get_text("academics.forecasting.trend_per_month", trend=f"{coefficients[0]:+.2f}"))

    print("\n" + get_text("academics.forecasting.forecast_next_months", periods=forecast_periods))
    for i, forecast in enumerate(forecasted_values, 1):
        bounded_forecast = max(0, min(100, forecast))
        print(get_text("academics.forecasting.month_forecast", month=i, value=f"{bounded_forecast:.1f}"))

    # Forecast confidence
    residuals = averages - trend_line(x)
    mse = np.mean(residuals**2)
    print("\n" + get_text("academics.forecasting.forecast_accuracy"))
    print(get_text("academics.forecasting.standard_error", error=f"{np.sqrt(mse):.1f}"))

def forecast_module_difficulty(cursor):
    """Forecast module difficulty trends"""
    print("\n" + get_text("academics.forecasting.module_difficulty_title"))

    # Get modules with sufficient historical data
    cursor.execute('''
    SELECT m.module_code, m.module_name,
           COUNT(DISTINCT strftime('%Y-%m', g.submission_date)) as months_with_data
    FROM modules m
    JOIN assessments a ON m.module_code = a.module_code
    JOIN grades g ON a.id = g.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY m.module_code
    HAVING months_with_data >= 6
    ORDER BY m.module_name
    ''')

    modules = cursor.fetchall()

    if not modules:
        print(get_text("academics.forecasting.no_modules_with_data"))
        return

    print("\n" + get_text("academics.forecasting.analyzing_difficulty_trends", count=len(modules)))

    difficulty_forecasts = []

    for module_code, module_name, months_count in modules:
        forecast = forecast_module_difficulty_single(cursor, module_code, module_name)
        if forecast:
            difficulty_forecasts.append(forecast)

    # Sort by projected difficulty (hardest first)
    difficulty_forecasts.sort(key=lambda x: x['projected_difficulty'], reverse=True)

    # Display results
    print("\n" + get_text("academics.forecasting.module_difficulty_forecasts"))
    print("="*80)
    print(f"{get_text('academics.forecasting.header_module'):<15} {get_text('academics.forecasting.header_current_avg'):<12} {get_text('academics.forecasting.header_trend'):<10} {get_text('academics.forecasting.header_projected'):<12} {get_text('academics.forecasting.header_status')}")
    print("-"*80)

    for forecast in difficulty_forecasts:
        status = get_text("academics.forecasting.status_getting_harder") if forecast['trend'] < -1 else get_text("academics.forecasting.status_getting_easier") if forecast['trend'] > 1 else get_text("academics.forecasting.status_stable")
        print(f"{forecast['code']:<15} {forecast['current_avg']:<12.1f}% "
              f"{forecast['trend']:<10.2f} {forecast['projected_difficulty']:<12.1f}% {status}")

def forecast_module_difficulty_single(cursor, module_code, module_name):
    """Forecast difficulty for a single module"""
    # Get monthly average scores (lower scores = higher difficulty)
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.id
    WHERE a.module_code = ? AND g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    ORDER BY month
    ''', (module_code,))

    monthly_data = cursor.fetchall()

    if len(monthly_data) < 6:
        return None

    # Analyze trend
    averages = [data[1] for data in monthly_data]

    # Calculate trend (negative trend = getting harder)
    x = np.arange(len(averages))
    trend_slope = np.polyfit(x, averages, 1)[0]

    # Project forward 3 months
    projected_avg = averages[-1] + (trend_slope * 3)
    projected_avg = max(0, min(100, projected_avg))

    return {
        'code': module_code,
        'name': module_name,
        'current_avg': np.mean(averages[-3:]),  # Recent 3-month average
        'trend': trend_slope,
        'projected_difficulty': 100 - projected_avg  # Invert for difficulty scale
    }

def forecast_success_rates(cursor):
    """Forecast student success rate trends"""
    print("\n" + get_text("academics.forecasting.success_rate_title"))

    # Get monthly success rates (passing grades)
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           COUNT(*) as total_grades,
           SUM(CASE WHEN g.letter_grade != 'F' THEN 1 ELSE 0 END) as passing_grades
    FROM grades g
    WHERE g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    HAVING total_grades >= 10
    ORDER BY month
    ''')

    monthly_success_data = cursor.fetchall()

    if len(monthly_success_data) < 6:
        print(get_text("academics.forecasting.insufficient_success_rate_data"))
        return

    # Calculate success rates
    months = []
    success_rates = []

    for month, total, passing in monthly_success_data:
        success_rate = (passing / total) * 100
        months.append(month)
        success_rates.append(success_rate)

    # Analyze trend
    x = np.arange(len(success_rates))
    trend_slope = np.polyfit(x, success_rates, 1)[0]

    # Project forward
    current_rate = np.mean(success_rates[-3:])
    projected_rate = current_rate + (trend_slope * 3)
    projected_rate = max(0, min(100, projected_rate))

    print(f"\nSuccess Rate Forecast:")
    print(f"Period: {months[0]} to {months[-1]}")
    print(f"Current Success Rate: {current_rate:.1f}%")
    print(f"Trend: {trend_slope:+.2f}% per month")
    print(f"3-Month Projection: {projected_rate:.1f}%")

    # Risk assessment
    if projected_rate < 70:
        print("⚠️  Warning: Low success rate projected - intervention needed")
    elif projected_rate > 85:
        print("✅ Excellent success rate projected")
    else:
        print("📊 Moderate success rate projected")

    # Course-specific success rate forecasting
    print(f"\nSuccess Rate Forecast by Course:")
    print("-" * 60)
    print(f"{'Course':<15} {'Current Rate':<15} {'Trend':<10} {'Projected'}")
    print("-" * 60)

    cursor.execute('SELECT DISTINCT course FROM students ORDER BY course')
    courses = [row[0] for row in cursor.fetchall()]

    for course in courses:
        course_forecast = forecast_course_success_rate(cursor, course)
        if course_forecast:
            print(f"{course:<15} {course_forecast['current']:<15.1f}% "
                  f"{course_forecast['trend']:<10.2f} {course_forecast['projected']:.1f}%")

def forecast_course_success_rate(cursor, course):
    """Forecast success rate for a specific course"""
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           COUNT(*) as total_grades,
           SUM(CASE WHEN g.letter_grade != 'F' THEN 1 ELSE 0 END) as passing_grades
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.id
    JOIN student_modules sm ON a.module_code = sm.module_code
    JOIN students s ON sm.student_id = s.student_id
    WHERE s.course = ? AND g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    HAVING total_grades >= 5
    ORDER BY month
    ''', (course,))

    monthly_data = cursor.fetchall()

    if len(monthly_data) < 6:
        return None

    # Calculate success rates
    success_rates = []
    for month, total, passing in monthly_data:
        success_rate = (passing / total) * 100
        success_rates.append(success_rate)

    # Analyze trend
    x = np.arange(len(success_rates))
    trend_slope = np.polyfit(x, success_rates, 1)[0]

    current_rate = np.mean(success_rates[-3:])
    projected_rate = current_rate + (trend_slope * 3)
    projected_rate = max(0, min(100, projected_rate))

    return {
        'current': current_rate,
        'trend': trend_slope,
        'projected': projected_rate
    }

def extract_comprehensive_student_features(cursor, student_id):
    """Extract comprehensive features for machine learning"""
    features = {}

    # Get assessment grades
    cursor.execute('''
    SELECT g.score / a.max_points * 100, g.submission_date
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.id
    WHERE g.student_id = ?
    ORDER BY g.submission_date
    ''', (student_id,))

    grade_data = cursor.fetchall()

    if not grade_data:
        return None

    scores = [score for score, _ in grade_data]

    # Basic performance features
    features['avg_score'] = np.mean(scores)
    features['assessment_count'] = len(grade_data)
    features['consistency_score'] = 100 - np.std(scores)  # Higher is more consistent

    # Calculate trend
    if len(scores) >= 3:
        x = list(range(len(scores)))
        features['score_trend'] = np.polyfit(x, scores, 1)[0]
    else:
        features['score_trend'] = 0

    # Failed assessments
    cursor.execute('''
    SELECT COUNT(*) FROM grades
    WHERE student_id = ? AND letter_grade = 'F'
    ''', (student_id,))

    features['failed_count'] = cursor.fetchone()[0]

    # Submission rate
    cursor.execute('''
    SELECT COUNT(DISTINCT a.id) as total,
           COUNT(g.id) as submitted
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.id = g.assessment_id AND g.student_id = sm.student_id
    WHERE sm.student_id = ?
    ''', (student_id,))

    result = cursor.fetchone()
    if result and result[0] > 0:
        features['submission_rate'] = result[1] / result[0]
    else:
        features['submission_rate'] = 0

    return features

def build_module_success_model(cursor):
    """Build a model to predict module success"""
    print("\nBuilding Module Success Prediction Model...")

    # This would be similar to the at-risk model but focused on module completion
    # Implementation would follow similar patterns to build_at_risk_prediction_model
    print("Module success model building - implementation would follow similar pattern to at-risk model")
    print("Features would include: early assessment performance, attendance, prerequisite completion, etc.")

def create_dashboard_visualizations(dashboard_data):
    """Create comprehensive dashboard visualizations"""
    viz_dir = 'dashboard_visualizations'
    if not os.path.exists(viz_dir):
        os.makedirs(viz_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Create a comprehensive dashboard figure
    fig = plt.figure(figsize=(16, 12))

    # Extract data from flat DataBag format
    total_students = dashboard_data.get('total_students', 0)
    total_courses = dashboard_data.get('total_courses', 0)
    total_grades = dashboard_data.get('total_grades', 0)
    grade_dist = dashboard_data.get('grade_distribution', {})
    course_avgs = dashboard_data.get('course_averages', [])
    at_risk = dashboard_data.get('at_risk_students', [])
    monthly = dashboard_data.get('monthly_trends', [])

    at_risk_count = len(at_risk) if isinstance(at_risk, list) else 0
    safe_count = max(0, total_students - at_risk_count)

    # 1. Grade Distribution (top left)
    ax1 = plt.subplot(2, 3, 1)
    if isinstance(grade_dist, dict) and grade_dist:
        grades = list(grade_dist.keys())
        counts = [(v or 0) for v in grade_dist.values()]
        if any(c > 0 for c in counts):
            bars = ax1.bar(grades, counts, color='lightgreen', alpha=0.7)
            ax1.set_title('Grade Distribution')
            ax1.set_xlabel('Grade')
            ax1.set_ylabel('Count')
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                            f'{int(height)}', ha='center', va='bottom')

    # 2. Course Performance (top center)
    ax2 = plt.subplot(2, 3, 2)
    if course_avgs:
        courses = [c.get('course', '?') for c in course_avgs[:8]]
        avg_scores = [c.get('avg_score', 0) or 0 for c in course_avgs[:8]]
        bars = ax2.bar(courses, avg_scores, color='gold', alpha=0.7)
        ax2.set_title('Course Performance')
        ax2.set_xlabel('Course')
        ax2.set_ylabel('Average Score (%)')
        ax2.tick_params(axis='x', rotation=45)

    # 3. Risk Assessment Pie Chart (top right)
    ax3 = plt.subplot(2, 3, 3)
    labels = ['Safe', 'At Risk']
    sizes = [safe_count, at_risk_count]
    pie_colors = ['green', 'red']
    non_zero = [(l, s, c) for l, s, c in zip(labels, sizes, pie_colors) if s > 0]
    if non_zero:
        labels, sizes, pie_colors = zip(*non_zero)
        ax3.pie(sizes, labels=labels, colors=pie_colors, autopct='%1.1f%%', startangle=90)
    ax3.set_title('Student Risk Distribution')

    # 4. System Overview (bottom left)
    ax4 = plt.subplot(2, 3, 4)
    categories = ['Students', 'Courses', 'Grades']
    values = [total_students, total_courses, total_grades]
    bars = ax4.bar(categories, values, color=['skyblue', 'lightcoral', 'lightgreen'])
    ax4.set_title('System Overview')
    ax4.set_ylabel('Count')
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax4.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                    f'{int(height)}', ha='center', va='bottom')

    # 5. Monthly Trends (bottom center)
    ax5 = plt.subplot(2, 3, 5)
    if monthly:
        months = [t.get('month', '') for t in monthly]
        scores = [t.get('avg_score', 0) or 0 for t in monthly]
        ax5.plot(months, scores, 'b-', marker='o', markersize=4)
        ax5.set_title('Monthly Performance Trends')
        ax5.set_xlabel('Month')
        ax5.set_ylabel('Avg Score (%)')
        ax5.tick_params(axis='x', rotation=45)
        ax5.grid(True, alpha=0.3)
    else:
        ax5.text(0.5, 0.5, 'No trend data', ha='center', va='center', transform=ax5.transAxes)
        ax5.set_title('Monthly Performance Trends')

    # 6. Placeholder
    ax6 = plt.subplot(2, 3, 6)
    ax6.text(0.5, 0.5, 'Grade Trends\n(Placeholder)', ha='center', va='center',
             transform=ax6.transAxes, fontsize=12)
    ax6.set_title('Grade Trends Over Time')

    plt.tight_layout()

    # Save the dashboard
    dashboard_filename = f"{viz_dir}/performance_dashboard_{timestamp}.png"
    plt.savefig(dashboard_filename, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Performance dashboard visualization saved: {dashboard_filename}")

def generate_dashboard_report(dashboard_data):
    """Generate a comprehensive dashboard report"""
    reports_dir = 'dashboard_reports'
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"{reports_dir}/performance_dashboard_report_{timestamp}.pdf"

    doc = SimpleDocTemplate(report_filename, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        alignment=1,
        spaceAfter=12
    )
    elements.append(Paragraph("Performance Dashboard Report", title_style))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Executive Summary
    elements.append(Paragraph("Executive Summary", styles['Heading2']))

    total_students = dashboard_data.get('total_students', 0)
    total_courses = dashboard_data.get('total_courses', 0)
    total_grades = dashboard_data.get('total_grades', 0)
    summary_text = f"""
    This report provides a comprehensive overview of academic performance across {total_students} students,
    {total_courses} courses/modules, and {total_grades} grades recorded in the system.
    """

    elements.append(Paragraph(summary_text, styles['Normal']))
    elements.append(Spacer(1, 12))

    # Key Metrics
    elements.append(Paragraph("Key Performance Indicators", styles['Heading2']))

    kpi_data = [['Metric', 'Value', 'Status']]

    avg_score = dashboard_data.get('avg_score')
    if avg_score is not None:
        score_status = "Excellent" if avg_score >= 80 else "Good" if avg_score >= 60 else "Needs Improvement"
        kpi_data.append(['Average Score', f"{avg_score:.1f}%", score_status])

    # Calculate passing rate from grade distribution
    grade_dist = dashboard_data.get('grade_distribution', {})
    if isinstance(grade_dist, dict):
        total = sum((grade_dist.get(g, 0) or 0) for g in ["A", "B", "C", "D", "F"])
        passing = sum((grade_dist.get(g, 0) or 0) for g in ["A", "B", "C", "D"])
        passing_rate = (passing / total * 100) if total > 0 else 0
    else:
        passing_rate = 0
    pass_status = "Excellent" if passing_rate >= 90 else "Good" if passing_rate >= 80 else "Needs Improvement"
    kpi_data.append(['Passing Rate', f"{passing_rate:.1f}%", pass_status])

    at_risk = dashboard_data.get('at_risk_students', [])
    at_risk_count = len(at_risk) if isinstance(at_risk, list) else 0
    at_risk_pct = (at_risk_count / total_students * 100) if total_students > 0 else 0
    risk_status = "Good" if at_risk_pct < 10 else "Moderate" if at_risk_pct < 20 else "High Concern"
    kpi_data.append(['At-Risk Students', f"{at_risk_pct:.1f}%", risk_status])

    kpi_table = Table(kpi_data, colWidths=[150, 100, 150])
    kpi_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(kpi_table)
    elements.append(Spacer(1, 20))

    # Course Performance Section
    elements.append(Paragraph("Course Performance Analysis", styles['Heading2']))

    course_avgs = dashboard_data.get('course_averages', [])
    if course_avgs:
        course_data = [['Course', 'Grades', 'Average Score', 'Performance Level']]

        for entry in course_avgs:
            course_name = entry.get('course', 'N/A')
            count = entry.get('count', 0)
            avg = entry.get('avg_score', 0) or 0
            if avg >= 85:
                level = "Excellent"
            elif avg >= 75:
                level = "Good"
            elif avg >= 65:
                level = "Satisfactory"
            else:
                level = "Needs Improvement"
            course_data.append([course_name, str(count), f"{avg:.1f}%", level])

        course_table = Table(course_data, colWidths=[100, 80, 100, 120])
        course_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (1, 1), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(course_table)

    elements.append(Spacer(1, 20))

    # Risk Assessment Section
    elements.append(Paragraph("Risk Assessment Summary", styles['Heading2']))

    risk_summary = f"""
    Current risk assessment indicates {at_risk_count} students requiring attention
    ({at_risk_pct:.1f}% of total student population).
    """

    elements.append(Paragraph(risk_summary, styles['Normal']))
    elements.append(Spacer(1, 20))

    # Recommendations Section
    elements.append(Paragraph("Strategic Recommendations", styles['Heading2']))

    recommendations = generate_dashboard_recommendations(dashboard_data)

    for i, recommendation in enumerate(recommendations, 1):
        elements.append(Paragraph(f"{i}. {recommendation}", styles['Normal']))

    # Build the PDF
    doc.build(elements)

    print(f"Dashboard report generated: {report_filename}")

def generate_dashboard_recommendations(dashboard_data):
    """Generate strategic recommendations based on dashboard data"""
    recommendations = []

    # Score-based recommendations
    avg_score = dashboard_data.get('avg_score')
    if avg_score is not None:
        if avg_score < 50:
            recommendations.append("Implement comprehensive academic support program - average score indicates systemic issues")
        elif avg_score < 65:
            recommendations.append("Enhance tutoring services and academic advising to improve overall performance")

    # Passing rate recommendations
    grade_dist = dashboard_data.get('grade_distribution', {})
    if isinstance(grade_dist, dict):
        total = sum((grade_dist.get(g, 0) or 0) for g in ["A", "B", "C", "D", "F"])
        passing = sum((grade_dist.get(g, 0) or 0) for g in ["A", "B", "C", "D"])
        passing_rate = (passing / total * 100) if total > 0 else 100
    else:
        passing_rate = 100

    if passing_rate < 75:
        recommendations.append("Review curriculum difficulty and assessment standards - low passing rate detected")
    elif passing_rate < 85:
        recommendations.append("Strengthen student support services to improve success rates")

    # Risk-based recommendations
    at_risk = dashboard_data.get('at_risk_students', [])
    total_students = dashboard_data.get('total_students', 0)
    risk_pct = (len(at_risk) / total_students * 100) if total_students > 0 else 0

    if risk_pct > 20:
        recommendations.append("Deploy emergency intervention protocols - high percentage of at-risk students")
    elif risk_pct > 10:
        recommendations.append("Expand early warning systems and proactive student outreach")

    # Course performance recommendations
    course_avgs = dashboard_data.get('course_averages', [])
    if course_avgs:
        lowest = min(course_avgs, key=lambda x: x.get('avg_score', 0) or 0)
        if (lowest.get('avg_score', 0) or 0) < 70:
            recommendations.append(f"Conduct detailed review of {lowest.get('course', 'unknown')} course - lowest performance detected")

    # General recommendations
    recommendations.extend([
        "Establish monthly performance review meetings with department heads",
        "Implement data-driven decision making processes",
        "Create student success dashboard for real-time monitoring",
        "Develop faculty training program on student engagement strategies"
    ])

    return recommendations[:8]

def generate_dashboard_alerts(dashboard_data):
    """Generate alerts and recommendations based on dashboard data"""
    alerts = []

    # Calculate passing rate from grade distribution
    grade_dist = dashboard_data.get('grade_distribution', {})
    if isinstance(grade_dist, dict):
        # Handle flat DataBag format (keys: A, B, C, D, F)
        if 'passing_rate' in grade_dist:
            passing_rate = grade_dist['passing_rate']
        else:
            total = sum((grade_dist.get(g, 0) or 0) for g in ["A", "B", "C", "D", "F"])
            passing = sum((grade_dist.get(g, 0) or 0) for g in ["A", "B", "C", "D"])
            passing_rate = (passing / total * 100) if total > 0 else 100

        if passing_rate < 70:
            alerts.append(f"Low passing rate ({passing_rate:.1f}%) - consider curriculum review")
        elif passing_rate < 80:
            alerts.append(f"Moderate passing rate ({passing_rate:.1f}%) - monitor closely")

    # Check at-risk percentage
    at_risk = dashboard_data.get('at_risk_students', [])
    total_students = dashboard_data.get('total_students', 0)
    if isinstance(at_risk, list) and total_students > 0:
        at_risk_pct = (len(at_risk) / total_students) * 100
    elif isinstance(dashboard_data.get('risk_stats'), dict):
        at_risk_pct = dashboard_data['risk_stats'].get('at_risk_percentage', 0)
    else:
        at_risk_pct = 0

    if at_risk_pct > 20:
        alerts.append(f"High percentage of at-risk students ({at_risk_pct:.1f}%) - immediate intervention needed")
    elif at_risk_pct > 10:
        alerts.append(f"Elevated at-risk student percentage ({at_risk_pct:.1f}%) - enhance support services")

    # Check average score
    avg_score = dashboard_data.get('avg_score')
    if avg_score is not None:
        if avg_score < 50:
            alerts.append(f"Low average score ({avg_score:.1f}%) - academic support needed")
        elif avg_score > 80:
            alerts.append(f"Excellent average score ({avg_score:.1f}%) - maintain current standards")

    # Display alerts
    if alerts:
        for alert in alerts:
            print(f"   {alert}")
    else:
        print("   No critical alerts - performance within acceptable ranges")

def extract_student_features(cursor, student_id):
    """Extract features for a student for machine learning"""
    features = {}

    # Get assessment grades
    cursor.execute('''
    SELECT g.score / a.max_points * 100, g.letter_grade
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.id
    WHERE g.student_id = ?
    ''', (student_id,))

    grade_data = cursor.fetchall()

    if not grade_data:
        return None

    scores = [score for score, _ in grade_data]
    grades = [grade for _, grade in grade_data]

    # Calculate features
    features['avg_score'] = np.mean(scores)
    features['assessment_count'] = len(grade_data)
    features['failed_count'] = sum(1 for grade in grades if grade == 'F')

    # Calculate submission rate
    cursor.execute('''
    SELECT COUNT(DISTINCT a.id) as total_assessments,
           COUNT(g.id) as submitted_assessments
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.id = g.assessment_id AND g.student_id = sm.student_id
    WHERE sm.student_id = ?
    ''', (student_id,))

    result = cursor.fetchone()
    if result and result[0] > 0:
        features['submission_rate'] = result[1] / result[0]
    else:
        features['submission_rate'] = 0

    return features

def export_comparison_data(comparison_data, comparison_type):
    """Export comparison data to CSV"""
    exports_dir = 'comparison_exports'
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{exports_dir}/{comparison_type}_{timestamp}.csv"

    with open(filename, 'w', newline='') as csvfile:
        if comparison_type == "course_comparison":
            writer = csv.writer(csvfile)
            writer.writerow(['Course', 'Student Count', 'Avg GPA', 'Avg Score (%)',
                           'Passing Rate (%)', 'Excellence Rate (%)', 'Std Deviation', 'Performance Level'])

            for data in comparison_data:
                writer.writerow([
                    data['course'],
                    data['student_count'],
                    f"{data['avg_gpa']:.2f}",
                    f"{data['avg_score']:.1f}",
                    f"{data['passing_rate']:.1f}",
                    f"{data['excellence_rate']:.1f}",
                    f"{data['std_dev']:.1f}",
                    data['performance_level']
                ])

    print(f"Comparison data exported: {filename}")
