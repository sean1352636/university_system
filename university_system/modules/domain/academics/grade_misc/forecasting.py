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

from university_system.infrastructure.database.db import get_connection

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

    print(f"Batch predictions exported to {filename}")

def forecast_single_course(cursor, course):
    """Forecast performance for a single course"""
    print(f"\n--- Performance Forecast for {course} ---")

    # Get historical monthly performance data
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    JOIN student_modules sm ON a.module_code = sm.module_code
    JOIN students s ON sm.student_id = s.student_id
    WHERE s.course = ? AND g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    ORDER BY month
    ''', (course,))

    historical_data = cursor.fetchall()

    if len(historical_data) < 6:
        print(f"Insufficient historical data for forecasting (need at least 6 months)")
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

    print(f"Historical Period: {months[0]} to {months[-1]}")
    print(f"Current Average: {np.mean(averages):.1f}%")
    print(f"Trend: {coefficients[0]:+.2f}% per month")

    print(f"\nForecast (Next {forecast_periods} months):")
    for i, forecast in enumerate(forecasted_values, 1):
        bounded_forecast = max(0, min(100, forecast))
        print(f"  Month +{i}: {bounded_forecast:.1f}%")

    # Forecast confidence
    residuals = averages - trend_line(x)
    mse = np.mean(residuals**2)
    print(f"\nForecast Accuracy:")
    print(f"  Standard Error: ±{np.sqrt(mse):.1f}%")

def forecast_module_difficulty(cursor):
    """Forecast module difficulty trends"""
    print("\nModule Difficulty Trend Forecasting")

    # Get modules with sufficient historical data
    cursor.execute('''
    SELECT m.module_code, m.module_name,
           COUNT(DISTINCT strftime('%Y-%m', g.submission_date)) as months_with_data
    FROM modules m
    JOIN assessments a ON m.module_code = a.module_code
    JOIN grades g ON a.assessment_id = g.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY m.module_code
    HAVING months_with_data >= 6
    ORDER BY m.module_name
    ''')

    modules = cursor.fetchall()

    if not modules:
        print("No modules with sufficient historical data found.")
        return

    print(f"\nAnalyzing difficulty trends for {len(modules)} modules...")

    difficulty_forecasts = []

    for module_code, module_name, months_count in modules:
        forecast = forecast_module_difficulty_single(cursor, module_code, module_name)
        if forecast:
            difficulty_forecasts.append(forecast)

    # Sort by projected difficulty (hardest first)
    difficulty_forecasts.sort(key=lambda x: x['projected_difficulty'], reverse=True)

    # Display results
    print(f"\nModule Difficulty Forecasts:")
    print("="*80)
    print(f"{'Module':<15} {'Current Avg':<12} {'Trend':<10} {'Projected':<12} {'Status'}")
    print("-"*80)

    for forecast in difficulty_forecasts:
        status = "Getting Harder" if forecast['trend'] < -1 else "Getting Easier" if forecast['trend'] > 1 else "Stable"
        print(f"{forecast['code']:<15} {forecast['current_avg']:<12.1f}% "
              f"{forecast['trend']:<10.2f} {forecast['projected_difficulty']:<12.1f}% {status}")

def forecast_module_difficulty_single(cursor, module_code, module_name):
    """Forecast difficulty for a single module"""
    # Get monthly average scores (lower scores = higher difficulty)
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
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
    print("\nStudent Success Rate Forecasting")

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
        print("Insufficient data for success rate forecasting.")
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
    JOIN assessments a ON g.assessment_id = a.assessment_id
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
    JOIN assessments a ON g.assessment_id = a.assessment_id
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
    SELECT COUNT(DISTINCT a.assessment_id) as total,
           COUNT(g.grade_id) as submitted
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = sm.student_id
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

    # 1. GPA Distribution (top left)
    if 'gpa_stats' in dashboard_data:
        ax1 = plt.subplot(3, 3, 1)

        # Create sample GPA distribution for visualization
        gpa_stats = dashboard_data['gpa_stats']
        mean_gpa = gpa_stats['avg_gpa']
        std_gpa = gpa_stats['std_gpa']

        # Generate sample data for histogram
        sample_gpas = np.random.normal(mean_gpa, std_gpa, 1000)
        sample_gpas = np.clip(sample_gpas, 0, 4.3)  # Clip to valid GPA range

        ax1.hist(sample_gpas, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        ax1.axvline(mean_gpa, color='red', linestyle='--', label=f'Mean: {mean_gpa:.2f}')
        ax1.set_title('GPA Distribution')
        ax1.set_xlabel('GPA')
        ax1.set_ylabel('Count')
        ax1.legend()

    # 2. Grade Distribution (top center)
    ax2 = plt.subplot(3, 3, 2)
    grade_dist = dashboard_data['grade_distribution']['distribution']

    if grade_dist:
        grades = list(grade_dist.keys())
        counts = list(grade_dist.values())

        # Sort grades properly
        sorted_items = sorted(zip(grades, counts), 
                            key=lambda x: letter_to_gpa(x[0]), reverse=True)
        grades, counts = zip(*sorted_items)

        bars = ax2.bar(grades, counts, color='lightgreen', alpha=0.7)
        ax2.set_title('Grade Distribution')
        ax2.set_xlabel('Grade')
        ax2.set_ylabel('Count')

        # Add count labels
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{int(height)}', ha='center', va='bottom')

    # 3. Course Performance (top right)
    ax3 = plt.subplot(3, 3, 3)
    course_perf = dashboard_data['course_performance']

    if course_perf:
        courses = [c[0] for c in course_perf]
        avg_scores = [c[2] for c in course_perf]

        bars = ax3.bar(courses, avg_scores, color='gold', alpha=0.7)
        ax3.set_title('Course Performance')
        ax3.set_xlabel('Course')
        ax3.set_ylabel('Average Score (%)')
        ax3.tick_params(axis='x', rotation=45)

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            if height:  # Check if height is not None
                ax3.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{height:.1f}%', ha='center', va='bottom')

    # 4. Risk Assessment Pie Chart (middle left)
    ax4 = plt.subplot(3, 3, 4)
    risk_stats = dashboard_data['risk_stats']

    total_students = dashboard_data['overview']['total_students']
    at_risk = risk_stats['at_risk_students']
    high_risk = risk_stats['high_risk_students']
    low_risk = at_risk - high_risk
    safe = total_students - at_risk

    labels = ['Safe', 'Low Risk', 'High Risk']
    sizes = [safe, low_risk, high_risk]
    colors = ['green', 'orange', 'red']

    # Only include non-zero segments
    non_zero_data = [(label, size, color) for label, size, color in zip(labels, sizes, colors) if size > 0]
    if non_zero_data:
        labels, sizes, colors = zip(*non_zero_data)
        ax4.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)

    ax4.set_title('Student Risk Distribution')

    # 5. Recent Trends (middle center)
    ax5 = plt.subplot(3, 3, 5)
    recent_trends = dashboard_data['recent_trends']

    if recent_trends:
        dates = [trend[0] for trend in recent_trends]
        performances = [trend[1] for trend in recent_trends]

        ax5.plot(dates, performances, 'b-', marker='o', markersize=4)
        ax5.set_title('Recent Performance Trends (30 days)')
        ax5.set_xlabel('Date')
        ax5.set_ylabel('Performance (%)')
        ax5.tick_params(axis='x', rotation=45)
        ax5.grid(True, alpha=0.3)

    # 6. System Overview (middle right)
    ax6 = plt.subplot(3, 3, 6)
    overview = dashboard_data['overview']

    categories = ['Students', 'Modules', 'Assessments', 'Grades']
    values = [overview['total_students'], overview['total_modules'], 
              overview['total_assessments'], overview['total_grades']]

    bars = ax6.bar(categories, values, color=['skyblue', 'lightcoral', 'lightgreen', 'gold'])
    ax6.set_title('System Overview')
    ax6.set_ylabel('Count')

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax6.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                f'{int(height)}', ha='center', va='bottom')

    # 7. Performance Metrics (bottom left)
    ax7 = plt.subplot(3, 3, 7)

    # Create a simple metrics display
    if 'gpa_stats' in dashboard_data:
        metrics = [
            ('Avg GPA', dashboard_data['gpa_stats']['avg_gpa'], 'good' if dashboard_data['gpa_stats']['avg_gpa'] >= 3.0 else 'poor'),
            ('Pass Rate', dashboard_data['grade_distribution']['passing_rate'], 'good' if dashboard_data['grade_distribution']['passing_rate'] >= 80 else 'poor'),
            ('At Risk %', dashboard_data['risk_stats']['at_risk_percentage'], 'poor' if dashboard_data['risk_stats']['at_risk_percentage'] >= 20 else 'good')
        ]

        metric_names = [m[0] for m in metrics]
        metric_values = [m[1] for m in metrics]
        metric_colors = ['green' if m[2] == 'good' else 'red' for m in metrics]

        bars = ax7.bar(metric_names, metric_values, color=metric_colors, alpha=0.7)
        ax7.set_title('Key Performance Metrics')
        ax7.set_ylabel('Value')

        # Add value labels
        for i, bar in enumerate(bars):
            height = bar.get_height()
            label = f'{height:.1f}%' if i > 0 else f'{height:.2f}'
            ax7.text(bar.get_x() + bar.get_width()/2., height + max(metric_values)*0.01,
                    label, ha='center', va='bottom')

    # 8. Grade Trends (bottom center) - placeholder for future enhancement
    ax8 = plt.subplot(3, 3, 8)
    ax8.text(0.5, 0.5, 'Grade Trends\n(Placeholder)', ha='center', va='center', 
             transform=ax8.transAxes, fontsize=12)
    ax8.set_title('Grade Trends Over Time')

    # 9. Alert Summary (bottom right)
    ax9 = plt.subplot(3, 3, 9)

    # Create alert summary
    alert_data = {
        'Critical': high_risk,
        'Warning': low_risk,
        'Info': max(0, total_students - at_risk - 5)  # Some info alerts
    }

    alert_types = list(alert_data.keys())
    alert_counts = list(alert_data.values())
    alert_colors = ['red', 'orange', 'blue']

    bars = ax9.bar(alert_types, alert_counts, color=alert_colors, alpha=0.7)
    ax9.set_title('Active Alerts')
    ax9.set_ylabel('Count')

    # Add count labels
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax9.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{int(height)}', ha='center', va='bottom')

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

    overview = dashboard_data['overview']
    summary_text = f"""
    This report provides a comprehensive overview of academic performance across {overview['total_students']} students, 
    {overview['total_modules']} modules, and {overview['total_assessments']} assessments. 
    A total of {overview['total_grades']} grades have been recorded in the system.
    """

    elements.append(Paragraph(summary_text, styles['Normal']))
    elements.append(Spacer(1, 12))

    # Key Metrics
    elements.append(Paragraph("Key Performance Indicators", styles['Heading2']))

    kpi_data = [['Metric', 'Value', 'Status']]

    if 'gpa_stats' in dashboard_data:
        gpa_stats = dashboard_data['gpa_stats']
        gpa_status = "Excellent" if gpa_stats['avg_gpa'] >= 3.5 else "Good" if gpa_stats['avg_gpa'] >= 3.0 else "Needs Improvement"
        kpi_data.append(['Average GPA', f"{gpa_stats['avg_gpa']:.2f}", gpa_status])

    grade_data = dashboard_data['grade_distribution']
    pass_status = "Excellent" if grade_data['passing_rate'] >= 90 else "Good" if grade_data['passing_rate'] >= 80 else "Needs Improvement"
    kpi_data.append(['Passing Rate', f"{grade_data['passing_rate']:.1f}%", pass_status])

    risk_stats = dashboard_data['risk_stats']
    risk_status = "Good" if risk_stats['at_risk_percentage'] < 10 else "Moderate" if risk_stats['at_risk_percentage'] < 20 else "High Concern"
    kpi_data.append(['At-Risk Students', f"{risk_stats['at_risk_percentage']:.1f}%", risk_status])

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

    course_perf = dashboard_data['course_performance']
    if course_perf:
        course_data = [['Course', 'Students', 'Average Score', 'Performance Level']]

        for course, students, avg_score in course_perf:
            if avg_score:  # Check if avg_score is not None
                if avg_score >= 85:
                    level = "Excellent"
                elif avg_score >= 75:
                    level = "Good"
                elif avg_score >= 65:
                    level = "Satisfactory"
                else:
                    level = "Needs Improvement"

                course_data.append([course, str(students), f"{avg_score:.1f}%", level])

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
    Current risk assessment indicates {risk_stats['at_risk_students']} students requiring attention 
    ({risk_stats['at_risk_percentage']:.1f}% of total student population). Of these, 
    {risk_stats['high_risk_students']} students are classified as high-risk and require 
    immediate intervention.
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

    # GPA-based recommendations
    if 'gpa_stats' in dashboard_data:
        avg_gpa = dashboard_data['gpa_stats']['avg_gpa']
        if avg_gpa < 2.5:
            recommendations.append("Implement comprehensive academic support program - average GPA indicates systemic issues")
        elif avg_gpa < 3.0:
            recommendations.append("Enhance tutoring services and academic advising to improve overall GPA")

    # Passing rate recommendations
    passing_rate = dashboard_data['grade_distribution']['passing_rate']
    if passing_rate < 75:
        recommendations.append("Review curriculum difficulty and assessment standards - low passing rate detected")
    elif passing_rate < 85:
        recommendations.append("Strengthen student support services to improve success rates")

    # Risk-based recommendations
    risk_pct = dashboard_data['risk_stats']['at_risk_percentage']
    if risk_pct > 20:
        recommendations.append("Deploy emergency intervention protocols - high percentage of at-risk students")
    elif risk_pct > 10:
        recommendations.append("Expand early warning systems and proactive student outreach")

    # Course performance recommendations
    course_perf = dashboard_data['course_performance']
    if course_perf:
        lowest_performing = min(course_perf, key=lambda x: x[2] if x[2] else 0)
        if lowest_performing[2] and lowest_performing[2] < 70:
            recommendations.append(f"Conduct detailed review of {lowest_performing[0]} course - lowest performance detected")

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

    # Check passing rate
    passing_rate = dashboard_data['grade_distribution']['passing_rate']
    if passing_rate < 70:
        alerts.append(f"⚠️  Low passing rate ({passing_rate:.1f}%) - consider curriculum review")
    elif passing_rate < 80:
        alerts.append(f"📊 Moderate passing rate ({passing_rate:.1f}%) - monitor closely")

    # Check at-risk percentage
    at_risk_pct = dashboard_data['risk_stats']['at_risk_percentage']
    if at_risk_pct > 20:
        alerts.append(f"🚨 High percentage of at-risk students ({at_risk_pct:.1f}%) - immediate intervention needed")
    elif at_risk_pct > 10:
        alerts.append(f"⚠️  Elevated at-risk student percentage ({at_risk_pct:.1f}%) - enhance support services")

    # Check GPA statistics
    if 'gpa_stats' in dashboard_data:
        avg_gpa = dashboard_data['gpa_stats']['avg_gpa']
        if avg_gpa < 2.5:
            alerts.append(f"📉 Low average GPA ({avg_gpa:.2f}) - academic support needed")
        elif avg_gpa > 3.5:
            alerts.append(f"🎉 Excellent average GPA ({avg_gpa:.2f}) - maintain current standards")

    # Display alerts
    if alerts:
        for alert in alerts:
            print(f"   {alert}")
    else:
        print("   ✅ No critical alerts - performance within acceptable ranges")

def extract_student_features(cursor, student_id):
    """Extract features for a student for machine learning"""
    features = {}

    # Get assessment grades
    cursor.execute('''
    SELECT g.score / a.max_points * 100, g.letter_grade
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
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
    SELECT COUNT(DISTINCT a.assessment_id) as total_assessments,
           COUNT(g.grade_id) as submitted_assessments
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = sm.student_id
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
