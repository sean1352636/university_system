from __future__ import annotations

import os
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

_DATA_REPORTS_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'reports'
)

import numpy as np

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.i18n import get_text

# Lazy imports to avoid circular dependencies
def _get_grading_imports():
    from education_system.post_18.university_system.modules.domain.academics.grading.common_utilities import select_assessment
    from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation import calculate_student_gpa, GRADE_SYSTEMS
    return select_assessment, calculate_student_gpa, GRADE_SYSTEMS

def generate_statistical_report():
    """Generate a statistical report for assessments and/or modules"""
    select_assessment, calculate_student_gpa, GRADE_SYSTEMS = _get_grading_imports()
    from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.visualization import generate_assessment_stats_report

    print("\n" + get_text("academics.reports.generate_statistical_report"))

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Choose report type
        print("\n" + get_text("academics.reports.report_type"))
        print(get_text("academics.reports.option_assessment_statistics"))
        print(get_text("academics.reports.option_module_statistics"))
        print(get_text("academics.reports.option_course_statistics"))
        print(get_text("academics.reports.option_comprehensive_statistics"))

        report_type = input("Select report type (1-4): ")

        # Create the reports directory if it doesn't exist
        reports_dir = os.path.join(_DATA_REPORTS_DIR, 'statistical_reports')
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if report_type == "1":
            # Assessment Statistics
            assessment_id = select_assessment(cursor)
            if not assessment_id:
                conn.close()
                return

            generate_assessment_stats_report(cursor, assessment_id, reports_dir, timestamp)

        elif report_type == "2":
            # Module Statistics
            # Get list of modules
            cursor.execute('''
            SELECT module_code, module_name
            FROM modules
            WHERE module_code IN (SELECT DISTINCT module_code FROM module_grades)
            ORDER BY module_name
            ''')

            modules = cursor.fetchall()

            if not modules:
                print(get_text("academics.reports.no_modules_with_grades"))
                conn.close()
                return

            print("\n" + get_text("academics.reports.available_modules"))
            for i, (code, name) in enumerate(modules):
                print(f"{i+1}. {code} - {name}")

            module_index = input("Enter module number (or 0 for all modules): ")

            try:
                if module_index == "0":
                    # Generate report for all modules
                    generate_all_modules_stats_report(cursor, modules, reports_dir, timestamp)
                else:
                    index = int(module_index) - 1
                    if index < 0 or index >= len(modules):
                        print("Invalid module number.")
                        conn.close()
                        return

                    module_code = modules[index][0]
                    generate_module_stats_report(cursor, module_code, reports_dir, timestamp)

            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return

        elif report_type == "3":
            # Course Statistics
            # Get list of courses
            cursor.execute('''
            SELECT DISTINCT course
            FROM students
            WHERE student_id IN (SELECT DISTINCT student_id FROM module_grades)
            ORDER BY course
            ''')

            courses = cursor.fetchall()

            if not courses:
                print("No courses with grades found.")
                conn.close()
                return

            print("\nAvailable Courses:")
            for i, (course,) in enumerate(courses):
                print(f"{i+1}. {course}")

            course_index = input("Enter course number (or 0 for all courses): ")

            try:
                if course_index == "0":
                    # Generate report for all courses
                    courses_list = [c[0] for c in courses]
                    generate_all_courses_stats_report(cursor, courses_list, reports_dir, timestamp)
                else:
                    index = int(course_index) - 1
                    if index < 0 or index >= len(courses):
                        print("Invalid course number.")
                        conn.close()
                        return

                    course = courses[index][0]
                    generate_course_stats_report(cursor, course, reports_dir, timestamp)

            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return

        elif report_type == "4":
            # Comprehensive Statistics
            # This will include stats for all assessments, modules, and courses
            generate_comprehensive_stats_report(cursor, reports_dir, timestamp)

        else:
            print("Invalid report type.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def generate_module_stats_report(cursor, module_code, reports_dir, timestamp):
    """Generate a statistical report for a specific module"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image
    from reportlab.platypus import Paragraph
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.platypus import Spacer
    from reportlab.platypus import Table
    from reportlab.platypus import TableStyle
    import matplotlib.pyplot as plt
    import seaborn as sns
    _, calculate_student_gpa, GRADE_SYSTEMS = _get_grading_imports()
    try:
        # Get module details
        cursor.execute('''
        SELECT module_name, module_type
        FROM modules
        WHERE module_code = ?
        ''', (module_code,))

        module = cursor.fetchone()
        if not module:
            print("Module not found.")
            return

        module_name, module_type = module

        # Get all grades for this module
        cursor.execute('''
        SELECT mg.final_score, mg.final_grade
        FROM module_grades mg
        WHERE mg.module_code = ?
        ''', (module_code,))

        grades = cursor.fetchall()

        if not grades:
            print(f"No grades found for module {module_name}.")
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

        # Get assessment details for this module
        cursor.execute('''
        SELECT a.assessment_id, a.assessment_name, a.assessment_type, a.weight,
               COUNT(g.grade_id) as grade_count,
               AVG(g.score / a.max_points * 100) as avg_percentage
        FROM assessments a
        LEFT JOIN grades g ON a.assessment_id = g.assessment_id
        WHERE a.module_code = ?
        GROUP BY a.assessment_id
        ORDER BY a.assessment_name
        ''', (module_code,))

        assessments = cursor.fetchall()

        # Generate report in PDF format
        report_filename = f"{reports_dir}/module_stats_{module_code}_{timestamp}.pdf"

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
        elements.append(Paragraph("Module Statistical Report", title_style))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Module details
        elements.append(Paragraph("Module Details", styles['Heading2']))

        module_info = [
            ['Module Code:', module_code],
            ['Module Name:', module_name],
            ['Module Type:', module_type],
            ['Total Students:', str(total_students)]
        ]

        module_table = Table(module_info, colWidths=[150, 350])
        module_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))

        elements.append(module_table)
        elements.append(Spacer(1, 12))

        # Grade statistics
        elements.append(Paragraph("Grade Statistics", styles['Heading2']))

        stats_info = [
            ['Mean Score:', f"{mean:.2f}%"],
            ['Median Score:', f"{median:.2f}%"],
            ['Standard Deviation:', f"{std_dev:.2f}%"],
            ['Minimum Score:', f"{min_score:.2f}%"],
            ['Maximum Score:', f"{max_score:.2f}%"],
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

        # Assessment statistics
        if assessments:
            elements.append(Paragraph("Assessment Performance", styles['Heading2']))

            assessment_data = [
                ['Assessment', 'Type', 'Weight', 'Students', 'Avg. Score']
            ]

            for assessment in assessments:
                assessment_id, name, type, weight, count, avg = assessment
                assessment_data.append([
                    name,
                    type,
                    f"{weight}%",
                    str(count) if count else "0",
                    f"{avg:.1f}%" if avg else "N/A"
                ])

            assessment_table = Table(assessment_data, colWidths=[150, 80, 60, 60, 80])
            assessment_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            elements.append(assessment_table)
            elements.append(Spacer(1, 12))

        # Generate visualizations
        # Create a figure with a 2x2 grid
        plt.figure(figsize=(12, 10))

        # 1. Histogram with density curve
        plt.subplot(2, 2, 1)
        sns.histplot(scores, kde=True, color='skyblue')
        plt.axvline(mean, color='r', linestyle='--', label=f'Mean: {mean:.2f}')
        plt.axvline(median, color='g', linestyle='-.', label=f'Median: {median:.2f}')
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
        plt.boxplot(scores, vert=False, patch_artist=True,
                   boxprops=dict(facecolor='lightblue'))
        plt.title('Box Plot of Scores')
        plt.xlabel('Percentage Score')
        plt.yticks([])  # Hide y-tick labels

        # 4. Assessment comparison (if available)
        plt.subplot(2, 2, 4)
        if assessments:
            assessment_names = [a[1] for a in assessments if a[5]]
            assessment_avgs = [a[5] for a in assessments if a[5]]

            if assessment_names:
                # Truncate long assessment names
                assessment_names = [name[:15] + '...' if len(name) > 15 else name for name in assessment_names]

                y_pos = np.arange(len(assessment_names))
                plt.barh(y_pos, assessment_avgs, color='salmon')
                plt.yticks(y_pos, assessment_names)
                plt.xlabel('Average Score (%)')
                plt.title('Assessment Performance Comparison')
            else:
                plt.text(0.5, 0.5, 'No assessment data available',
                        horizontalalignment='center', verticalalignment='center')
                plt.title('Assessment Performance Comparison')
                plt.axis('off')
        else:
            plt.text(0.5, 0.5, 'No assessment data available',
                    horizontalalignment='center', verticalalignment='center')
            plt.title('Assessment Performance Comparison')
            plt.axis('off')

        plt.tight_layout()

        # Save the figure
        plots_filename = f"{reports_dir}/module_stats_{module_code}_{timestamp}_plots.png"
        plt.savefig(plots_filename)
        plt.close()

        # Add visualizations to PDF
        elements.append(Paragraph("Visual Analysis", styles['Heading2']))
        elements.append(Spacer(1, 6))

        if os.path.exists(plots_filename):
            img = Image(plots_filename, width=7*inch, height=6*inch)
            elements.append(img)

        # Interpretation
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Interpretation", styles['Heading2']))

        # Grade spread interpretation
        if std_dev < 10:
            spread = "The grades are tightly clustered, indicating consistent performance across students."
        elif std_dev > 20:
            spread = "The grades show significant variability, indicating diverse performance levels among students."
        else:
            spread = "The grades show moderate variability in student performance."

        # Performance level interpretation
        if mean > 80:
            performance = "Overall performance is excellent, with most students achieving high grades."
        elif mean > 70:
            performance = "Overall performance is good, with many students achieving above-average grades."
        elif mean > 60:
            performance = "Overall performance is satisfactory, with most students achieving passing grades."
        elif mean > 50:
            performance = "Overall performance is adequate but could be improved, with some students struggling."
        else:
            performance = "Overall performance is concerning, with many students struggling to achieve passing grades."

        # Passing rate interpretation
        if passing_rate > 90:
            passing = "The passing rate is very high, with almost all students successfully completing the module."
        elif passing_rate > 80:
            passing = "The passing rate is good, with most students successfully completing the module."
        elif passing_rate > 70:
            passing = "The passing rate is satisfactory, with many students successfully completing the module."
        else:
            passing = "The passing rate is concerning, with a significant number of students failing the module."

        elements.append(Paragraph(spread, styles['Normal']))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(performance, styles['Normal']))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(passing, styles['Normal']))

        # Build the PDF
        doc.build(elements)

        print(f"Module statistical report generated: {report_filename}")

    except Exception as e:
        print(f"Error generating module report: {e}")

def generate_all_modules_stats_report(cursor, modules, reports_dir, timestamp):
    """Generate a statistical report for all modules"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.platypus import Spacer
    from reportlab.platypus import Table
    from reportlab.platypus import TableStyle
    _, calculate_student_gpa, GRADE_SYSTEMS = _get_grading_imports()
    try:
        # Prepare the PDF document
        report_filename = f"{reports_dir}/all_modules_stats_{timestamp}.pdf"
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
        elements.append(Paragraph("All Modules Statistical Report", title_style))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Gather statistics for each module
        module_stats = []
        for module_code, module_name in modules:
            cursor.execute('''
            SELECT mg.final_score, mg.final_grade
            FROM module_grades mg
            WHERE mg.module_code = ?
            ''', (module_code,))

            grades = cursor.fetchall()
            if not grades:
                continue

            scores = [float(g[0]) for g in grades]
            letters = [g[1] for g in grades]
            total_students = len(scores)

            mean = np.mean(scores)
            std_dev = np.std(scores)
            passing_count = sum(1 for letter in letters if letter != 'F')
            passing_rate = (passing_count / total_students) * 100 if total_students > 0 else 0

            module_stats.append({
                'code': module_code,
                'name': module_name,
                'mean': mean,
                'std_dev': std_dev,
                'passing_rate': passing_rate,
            })

        if not module_stats:
            print("No module grade data found to generate a report.")
            return

        # Summary comparison table
        elements.append(Paragraph("Module Comparison", styles['Heading2']))

        summary_data = [['Module', 'Name', 'Mean', 'Passing Rate', 'Std Dev']]
        for m in module_stats:
            summary_data.append([
                m['code'],
                m['name'],
                f"{m['mean']:.1f}%",
                f"{m['passing_rate']:.1f}%",
                f"{m['std_dev']:.1f}%",
            ])

        summary_table = Table(summary_data, colWidths=[70, 150, 70, 90, 70])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 12))

        # Key findings across modules
        highest_passing = max(module_stats, key=lambda m: m['passing_rate'])
        lowest_passing = min(module_stats, key=lambda m: m['passing_rate'])
        lowest_variability = min(module_stats, key=lambda m: m['std_dev'])
        highest_variability = max(module_stats, key=lambda m: m['std_dev'])

        elements.append(Paragraph("Key Findings", styles['Heading2']))

        elements.append(Paragraph(
            f"- Highest passing rate: <b>{highest_passing['code']} - {highest_passing['name']}</b> " +
            f"with {highest_passing['passing_rate']:.1f}%",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Lowest passing rate: <b>{lowest_passing['code']} - {lowest_passing['name']}</b> " +
            f"with {lowest_passing['passing_rate']:.1f}%",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Most consistent student performance (lowest variability): <b>{lowest_variability['code']} - " +
            f"{lowest_variability['name']}</b> with a standard deviation of {lowest_variability['std_dev']:.1f}%",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Most variable student performance (highest variability): <b>{highest_variability['code']} - " +
            f"{highest_variability['name']}</b> with a standard deviation of {highest_variability['std_dev']:.1f}%",
            styles['Normal']))

        # Calculate average statistics across all modules
        avg_mean = sum(m['mean'] for m in module_stats) / len(module_stats)
        avg_passing = sum(m['passing_rate'] for m in module_stats) / len(module_stats)
        avg_std_dev = sum(m['std_dev'] for m in module_stats) / len(module_stats)

        elements.append(Spacer(1, 12))
        elements.append(Paragraph("<b>Overall Statistics:</b>", styles['Normal']))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph(
            f"- Average mean score across all modules: {avg_mean:.1f}%",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Average passing rate across all modules: {avg_passing:.1f}%",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Average standard deviation across all modules: {avg_std_dev:.1f}%",
            styles['Normal']))

        # Add recommendations
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Recommendations:", styles['Heading2']))

        # Identify potential issues
        low_performance_modules = [m for m in module_stats if m['mean'] < 60]
        high_failure_modules = [m for m in module_stats if m['passing_rate'] < 70]
        high_variability_modules = [m for m in module_stats if m['std_dev'] > 20]

        if low_performance_modules:
            elements.append(Paragraph(
                "- Review teaching methods and materials for modules with low average scores: " +
                ", ".join([f"<b>{m['code']}</b>" for m in low_performance_modules]),
                styles['Normal']))

        if high_failure_modules:
            elements.append(Paragraph(
                "- Investigate reasons for high failure rates in: " +
                ", ".join([f"<b>{m['code']}</b>" for m in high_failure_modules]),
                styles['Normal']))

        if high_variability_modules:
            elements.append(Paragraph(
                "- Address inconsistent student performance in: " +
                ", ".join([f"<b>{m['code']}</b>" for m in high_variability_modules]),
                styles['Normal']))

        elements.append(Paragraph(
            "- Consider standardizing assessment practices across modules to ensure consistent evaluation.",
            styles['Normal']))

        elements.append(Paragraph(
            "- Share best practices from high-performing modules with instructors of lower-performing modules.",
            styles['Normal']))

        # Build the PDF
        doc.build(elements)

        print(f"All modules statistical report generated: {report_filename}")

    except Exception as e:
        print(f"Error generating all modules report: {e}")

def generate_course_stats_report(cursor, course, reports_dir, timestamp):
    """Generate a statistical report for a specific course"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image
    from reportlab.platypus import Paragraph
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.platypus import Spacer
    from reportlab.platypus import Table
    from reportlab.platypus import TableStyle
    import matplotlib.pyplot as plt
    _, calculate_student_gpa, GRADE_SYSTEMS = _get_grading_imports()
    try:
        # Get all students in this course
        cursor.execute('''
        SELECT student_id, first_name, middle_name, last_name
        FROM students
        WHERE course = ?
        ''', (course,))

        students = cursor.fetchall()

        if not students:
            print(f"No students found for course {course}.")
            return

        student_ids = [s[0] for s in students]
        total_students = len(student_ids)

        # Get all modules taken by these students
        cursor.execute('''
        SELECT mg.module_code, m.module_name, m.module_type,
               COUNT(mg.student_id) as student_count,
               AVG(mg.final_score) as avg_score,
               SUM(CASE WHEN mg.final_grade != 'F' THEN 1 ELSE 0 END) as passing_count
        FROM module_grades mg
        JOIN modules m ON mg.module_code = m.module_code
        WHERE mg.student_id IN ({})
        GROUP BY mg.module_code
        ORDER BY avg_score DESC
        '''.format(','.join(['?'] * len(student_ids))), student_ids)

        modules = cursor.fetchall()

        # Get overall GPA for each student
        student_gpas = []
        for student_id in student_ids:
            gpa, credits, _ = calculate_student_gpa(cursor, student_id)
            if gpa is not None:
                student_gpas.append((student_id, gpa, credits))

        # Calculate course statistics
        if student_gpas:
            gpas = [g[1] for g in student_gpas]
            avg_gpa = sum(gpas) / len(gpas)
            median_gpa = sorted(gpas)[len(gpas) // 2]
            min_gpa = min(gpas)
            max_gpa = max(gpas)
            std_dev_gpa = np.std(gpas)

            # Count students in each GPA range
            gpa_ranges = {
                "4.0-4.3": 0,
                "3.7-3.9": 0,
                "3.3-3.6": 0,
                "3.0-3.2": 0,
                "2.7-2.9": 0,
                "2.3-2.6": 0,
                "2.0-2.2": 0,
                "1.7-1.9": 0,
                "1.0-1.6": 0,
                "0.0-0.9": 0
            }

            for gpa in gpas:
                if gpa >= 4.0:
                    gpa_ranges["4.0-4.3"] += 1
                elif gpa >= 3.7:
                    gpa_ranges["3.7-3.9"] += 1
                elif gpa >= 3.3:
                    gpa_ranges["3.3-3.6"] += 1
                elif gpa >= 3.0:
                    gpa_ranges["3.0-3.2"] += 1
                elif gpa >= 2.7:
                    gpa_ranges["2.7-2.9"] += 1
                elif gpa >= 2.3:
                    gpa_ranges["2.3-2.6"] += 1
                elif gpa >= 2.0:
                    gpa_ranges["2.0-2.2"] += 1
                elif gpa >= 1.7:
                    gpa_ranges["1.7-1.9"] += 1
                elif gpa >= 1.0:
                    gpa_ranges["1.0-1.6"] += 1
                else:
                    gpa_ranges["0.0-0.9"] += 1
        else:
            avg_gpa = 0
            median_gpa = 0
            min_gpa = 0
            max_gpa = 0
            std_dev_gpa = 0
            gpa_ranges = {k: 0 for k in ["4.0-4.3", "3.7-3.9", "3.3-3.6", "3.0-3.2", "2.7-2.9",
                                         "2.3-2.6", "2.0-2.2", "1.7-1.9", "1.0-1.6", "0.0-0.9"]}

        # Get student genders for demographic analysis
        cursor.execute('''
        SELECT gender, COUNT(*) as count
        FROM students
        WHERE course = ?
        GROUP BY gender
        ''', (course,))

        gender_counts = dict(cursor.fetchall())

        # Get at-risk students (GPA < 2.0)
        at_risk_students = [s for s in student_gpas if s[1] < 2.0]
        at_risk_percentage = (len(at_risk_students) / len(student_gpas)) * 100 if student_gpas else 0

        # Generate report in PDF format
        report_filename = f"{reports_dir}/course_stats_{course}_{timestamp}.pdf"

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
        elements.append(Paragraph(f"{course} Course Statistical Report", title_style))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Course overview
        elements.append(Paragraph("Course Overview", styles['Heading2']))

        overview_info = [
            ['Total Students:', str(total_students)],
            ['Average GPA:', f"{avg_gpa:.2f}"],
            ['Median GPA:', f"{median_gpa:.2f}"],
            ['GPA Range:', f"{min_gpa:.2f} - {max_gpa:.2f}"],
            ['At-Risk Students:', f"{len(at_risk_students)} ({at_risk_percentage:.1f}%)"]
        ]

        overview_table = Table(overview_info, colWidths=[150, 350])
        overview_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))

        elements.append(overview_table)
        elements.append(Spacer(1, 12))

        # Demographics
        elements.append(Paragraph("Student Demographics", styles['Heading2']))

        gender_data = [['Gender', 'Count', 'Percentage']]
        for gender, count in gender_counts.items():
            percentage = (count / total_students) * 100
            gender_data.append([gender.capitalize(), str(count), f"{percentage:.1f}%"])

        gender_table = Table(gender_data, colWidths=[100, 100, 100])
        gender_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (2, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (2, 0), 'CENTER'),
            ('ALIGN', (1, 1), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (2, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(gender_table)
        elements.append(Spacer(1, 12))

        # GPA Distribution
        elements.append(Paragraph("GPA Distribution", styles['Heading2']))

        gpa_data = [['GPA Range', 'Count', 'Percentage', 'Performance Level']]
        performance_levels = {
            "4.0-4.3": "Excellent",
            "3.7-3.9": "Very Good",
            "3.3-3.6": "Good",
            "3.0-3.2": "Above Average",
            "2.7-2.9": "Average",
            "2.3-2.6": "Fair",
            "2.0-2.2": "Satisfactory",
            "1.7-1.9": "Below Average",
            "1.0-1.6": "Poor",
            "0.0-0.9": "Failing"
        }

        for gpa_range, count in gpa_ranges.items():
            percentage = (count / len(student_gpas)) * 100 if student_gpas else 0
            gpa_data.append([
                gpa_range,
                str(count),
                f"{percentage:.1f}%",
                performance_levels[gpa_range]
            ])

        gpa_table = Table(gpa_data, colWidths=[80, 60, 80, 280])
        gpa_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (3, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (3, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (3, 0), 'CENTER'),
            ('ALIGN', (1, 1), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (3, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(gpa_table)
        elements.append(Spacer(1, 12))

        # Module Performance
        if modules:
            elements.append(Paragraph("Module Performance", styles['Heading2']))

            module_data = [
                ['Module', 'Type', 'Students', 'Avg. Score', 'Passing Rate']
            ]

            for module in modules:
                module_code, module_name, module_type, student_count, avg_score, passing_count = module
                passing_rate = (passing_count / student_count) * 100 if student_count > 0 else 0

                module_data.append([
                    f"{module_code} - {module_name}",
                    module_type,
                    str(student_count),
                    f"{avg_score:.1f}%",
                    f"{passing_rate:.1f}%"
                ])

            module_table = Table(module_data, colWidths=[250, 60, 60, 80, 80])
            module_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            elements.append(module_table)
            elements.append(Spacer(1, 12))

        # Generate visualizations
        plt.figure(figsize=(12, 10))

        # 1. GPA Distribution
        plt.subplot(2, 2, 1)

        ranges = list(gpa_ranges.keys())
        counts = [gpa_ranges[r] for r in ranges]

        # Shorten the range labels for better display
        short_ranges = ["4.0+", "3.7-3.9", "3.3-3.6", "3.0-3.2", "2.7-2.9",
                       "2.3-2.6", "2.0-2.2", "1.7-1.9", "1.0-1.6", "<1.0"]

        bars = plt.bar(short_ranges, counts, color='skyblue')
        plt.title('GPA Distribution')
        plt.xlabel('GPA Range')
        plt.ylabel('Number of Students')
        plt.xticks(rotation=45)

        # Add count labels on top of bars
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{height:.0f}', ha='center', va='bottom')

        # 2. Gender Distribution
        plt.subplot(2, 2, 2)

        if gender_counts:
            labels = [g.capitalize() for g in gender_counts.keys()]
            sizes = list(gender_counts.values())
            pie_colors = ['lightblue', 'lightpink', 'lightgreen']
            plt.pie(sizes, labels=labels, colors=pie_colors, autopct='%1.1f%%', startangle=90)
            plt.axis('equal')
            plt.title('Gender Distribution')
        else:
            plt.text(0.5, 0.5, 'No gender data available',
                    horizontalalignment='center', verticalalignment='center')
            plt.title('Gender Distribution')
            plt.axis('off')

        # 3. Module Performance Comparison
        plt.subplot(2, 2, 3)

        if modules:
            # Sort modules by average score
            sorted_modules = sorted(modules, key=lambda x: x[4], reverse=True)
            module_codes = [m[0] for m in sorted_modules]
            avg_scores = [m[4] for m in sorted_modules]

            y_pos = np.arange(len(module_codes))
            bars = plt.barh(y_pos, avg_scores, color='lightgreen')
            plt.yticks(y_pos, module_codes)
            plt.xlabel('Average Score (%)')
            plt.title('Module Performance Comparison')

            # Add value labels
            for i, bar in enumerate(bars):
                width = bar.get_width()
                plt.text(width + 1, bar.get_y() + bar.get_height()/2,
                        f'{width:.1f}%', ha='left', va='center')
        else:
            plt.text(0.5, 0.5, 'No module data available',
                    horizontalalignment='center', verticalalignment='center')
            plt.title('Module Performance Comparison')
            plt.axis('off')

        # 4. Top vs. Bottom Students
        plt.subplot(2, 2, 4)

        if student_gpas:
            # Sort students by GPA
            sorted_students = sorted(student_gpas, key=lambda x: x[1], reverse=True)

            # Get top 5 and bottom 5 (if available)
            top_students = sorted_students[:min(5, len(sorted_students))]
            bottom_students = sorted_students[-min(5, len(sorted_students)):]

            # Combine into one chart
            all_students = top_students + bottom_students
            student_ids = [s[0] for s in all_students]
            gpas = [s[1] for s in all_students]

            # Get student names
            student_names = {}
            for student_id in student_ids:
                cursor.execute('''
                SELECT first_name, last_name
                FROM students
                WHERE student_id = ?
                ''', (student_id,))

                first, last = cursor.fetchone()
                student_names[student_id] = f"{first} {last}"

            # Create bar chart
            y_pos = np.arange(len(all_students))
            bars = plt.barh(y_pos, gpas, color=['green'] * len(top_students) + ['red'] * len(bottom_students))
            plt.yticks(y_pos, [student_names[s_id] for s_id in student_ids])
            plt.xlabel('GPA')
            plt.title('Top and Bottom Students by GPA')

            # Add value labels
            for i, bar in enumerate(bars):
                width = bar.get_width()
                plt.text(width + 0.05, bar.get_y() + bar.get_height()/2,
                        f'{width:.2f}', ha='left', va='center')
        else:
            plt.text(0.5, 0.5, 'No GPA data available',
                    horizontalalignment='center', verticalalignment='center')
            plt.title('Top and Bottom Students by GPA')
            plt.axis('off')

        plt.tight_layout()

        # Save the figure
        plots_filename = f"{reports_dir}/course_stats_{course}_{timestamp}_plots.png"
        plt.savefig(plots_filename)
        plt.close()

        # Add visualizations to PDF
        elements.append(Paragraph("Visual Analysis", styles['Heading2']))
        elements.append(Spacer(1, 6))

        if os.path.exists(plots_filename):
            img = Image(plots_filename, width=7*inch, height=6*inch)
            elements.append(img)

        # Analysis and Recommendations
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Analysis and Recommendations", styles['Heading2']))

        # GPA Analysis
        if avg_gpa >= 3.5:
            gpa_analysis = "The course demonstrates excellent overall academic performance with a high average GPA."
        elif avg_gpa >= 3.0:
            gpa_analysis = "The course shows good overall academic performance with a solid average GPA."
        elif avg_gpa >= 2.5:
            gpa_analysis = "The course exhibits satisfactory overall academic performance."
        else:
            gpa_analysis = "The course's overall academic performance needs improvement, as indicated by the below-average GPA."

        elements.append(Paragraph(gpa_analysis, styles['Normal']))
        elements.append(Spacer(1, 6))

        # At-risk analysis
        if at_risk_percentage > 20:
            at_risk_analysis = f"There is a concerning percentage ({at_risk_percentage:.1f}%) of students at academic risk with GPAs below 2.0."
            elements.append(Paragraph(at_risk_analysis, styles['Normal']))
            elements.append(Spacer(1, 6))

            # Recommendations for high at-risk percentage
            elements.append(Paragraph("<b>Recommendations:</b>", styles['Normal']))
            elements.append(Paragraph("1. Implement an early intervention program for at-risk students.", styles['Normal']))
            elements.append(Paragraph("2. Provide additional tutoring and support resources.", styles['Normal']))
            elements.append(Paragraph("3. Review entry requirements and prerequisite knowledge for the course.", styles['Normal']))
            elements.append(Paragraph("4. Consider revising teaching approaches for core modules.", styles['Normal']))

        elif at_risk_percentage > 10:
            at_risk_analysis = f"There is a moderate percentage ({at_risk_percentage:.1f}%) of students at academic risk with GPAs below 2.0."
            elements.append(Paragraph(at_risk_analysis, styles['Normal']))
            elements.append(Spacer(1, 6))

            # Recommendations for moderate at-risk percentage
            elements.append(Paragraph("<b>Recommendations:</b>", styles['Normal']))
            elements.append(Paragraph("1. Identify and provide support for students showing signs of academic struggle.", styles['Normal']))
            elements.append(Paragraph("2. Offer additional review sessions for challenging topics.", styles['Normal']))
            elements.append(Paragraph("3. Encourage peer-to-peer learning and study groups.", styles['Normal']))

        else:
            at_risk_analysis = f"The percentage of at-risk students ({at_risk_percentage:.1f}%) is relatively low."
            elements.append(Paragraph(at_risk_analysis, styles['Normal']))
            elements.append(Spacer(1, 6))

            # Recommendations for low at-risk percentage
            elements.append(Paragraph("<b>Recommendations:</b>", styles['Normal']))
            elements.append(Paragraph("1. Continue monitoring student performance to maintain low at-risk rates.", styles['Normal']))
            elements.append(Paragraph("2. Provide personalized support for the small number of at-risk students.", styles['Normal']))
            elements.append(Paragraph("3. Document successful practices for potential application to other courses.", styles['Normal']))

        # Add module-specific recommendations if applicable
        if modules:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("<b>Module-Specific Insights:</b>", styles['Normal']))

            # Identify top and bottom performing modules
            sorted_modules = sorted(modules, key=lambda x: x[4], reverse=True)
            top_module = sorted_modules[0]
            bottom_module = sorted_modules[-1]

            elements.append(Paragraph(
                f"- Highest performing module: <b>{top_module[0]} - {top_module[1]}</b> with an average of {top_module[4]:.1f}%",
                styles['Normal']))

            elements.append(Paragraph(
                f"- Lowest performing module: <b>{bottom_module[0]} - {bottom_module[1]}</b> with an average of {bottom_module[4]:.1f}%",
                styles['Normal']))

            # If there's a significant gap, note it
            if top_module[4] - bottom_module[4] > 20:
                elements.append(Paragraph(
                    f"- There is a significant performance gap of {top_module[4] - bottom_module[4]:.1f}% between the highest and lowest modules.",
                    styles['Normal']))

                elements.append(Paragraph(
                    "- Consider reviewing the content, teaching methods, and assessment strategies for the lower-performing modules.",
                    styles['Normal']))

        # Build the PDF
        doc.build(elements)

        print(f"Course statistical report generated: {report_filename}")

    except Exception as e:
        print(f"Error generating course report: {e}")

def generate_all_courses_stats_report(cursor, courses, reports_dir, timestamp):
    """Generate a statistical report comparing all courses"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image
    from reportlab.platypus import Paragraph
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.platypus import Spacer
    from reportlab.platypus import Table
    from reportlab.platypus import TableStyle
    import matplotlib.pyplot as plt
    _, calculate_student_gpa, GRADE_SYSTEMS = _get_grading_imports()
    try:
        # Create a pandas DataFrame to store course statistics
        course_stats = []

        # Collect statistics for each course
        for course in courses:
            # Get all students in this course
            cursor.execute('''
            SELECT student_id
            FROM students
            WHERE course = ?
            ''', (course,))

            students = cursor.fetchall()

            if not students:
                # Skip courses with no students
                continue

            student_ids = [s[0] for s in students]
            total_students = len(student_ids)

            # Get overall GPA for each student
            student_gpas = []
            for student_id in student_ids:
                gpa, credits, _ = calculate_student_gpa(cursor, student_id)
                if gpa is not None:
                    student_gpas.append((student_id, gpa, credits))

            # Calculate average GPA and other statistics
            if student_gpas:
                gpas = [g[1] for g in student_gpas]
                avg_gpa = sum(gpas) / len(gpas)
                median_gpa = sorted(gpas)[len(gpas) // 2]
                min_gpa = min(gpas)
                max_gpa = max(gpas)
                std_dev_gpa = np.std(gpas)

                # Calculate passing rate (GPA >= 2.0)
                passing_count = sum(1 for gpa in gpas if gpa >= 2.0)
                passing_rate = (passing_count / len(gpas)) * 100

                # Calculate retention rate (approximated by percentage of students with grades)
                retention_rate = (len(student_gpas) / total_students) * 100
            else:
                avg_gpa = 0
                median_gpa = 0
                min_gpa = 0
                max_gpa = 0
                std_dev_gpa = 0
                passing_rate = 0
                retention_rate = 0

            # Get gender distribution
            cursor.execute('''
            SELECT gender, COUNT(*) as count
            FROM students
            WHERE course = ?
            GROUP BY gender
            ''', (course,))

            gender_counts = dict(cursor.fetchall())
            male_pct = (gender_counts.get('male', 0) / total_students) * 100 if total_students > 0 else 0
            female_pct = (gender_counts.get('female', 0) / total_students) * 100 if total_students > 0 else 0
            other_pct = (gender_counts.get('other', 0) / total_students) * 100 if total_students > 0 else 0

            # Create a dictionary for this course's statistics
            course_stat = {
                'course': course,
                'students': total_students,
                'students_with_grades': len(student_gpas),
                'avg_gpa': avg_gpa,
                'median_gpa': median_gpa,
                'min_gpa': min_gpa,
                'max_gpa': max_gpa,
                'std_dev_gpa': std_dev_gpa,
                'passing_rate': passing_rate,
                'retention_rate': retention_rate,
                'male_pct': male_pct,
                'female_pct': female_pct,
                'other_pct': other_pct
            }

            course_stats.append(course_stat)

        if not course_stats:
            print("No courses with student data found.")
            return

        # Sort courses by average GPA (descending)
        course_stats.sort(key=lambda x: x['avg_gpa'], reverse=True)

        # Generate report in PDF format
        report_filename = f"{reports_dir}/all_courses_stats_{timestamp}.pdf"

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
        elements.append(Paragraph("Course Comparison Report", title_style))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Summary table
        elements.append(Paragraph("Course Comparison Summary", styles['Heading2']))

        summary_data = [
            ['Course', 'Students', 'Avg GPA', 'Passing Rate', 'Retention Rate']
        ]

        for course in course_stats:
            summary_data.append([
                course['course'],
                str(course['students']),
                f"{course['avg_gpa']:.2f}",
                f"{course['passing_rate']:.1f}%",
                f"{course['retention_rate']:.1f}%"
            ])

        summary_table = Table(summary_data, colWidths=[100, 100, 100, 100, 100])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 12))

        # Detailed statistics
        elements.append(Paragraph("Detailed Statistics by Course", styles['Heading2']))

        detailed_data = [
            ['Course', 'Avg GPA', 'Median GPA', 'Min GPA', 'Max GPA', 'Std Dev']
        ]

        for course in course_stats:
            detailed_data.append([
                course['course'],
                f"{course['avg_gpa']:.2f}",
                f"{course['median_gpa']:.2f}",
                f"{course['min_gpa']:.2f}",
                f"{course['max_gpa']:.2f}",
                f"{course['std_dev_gpa']:.2f}"
            ])

        detailed_table = Table(detailed_data, colWidths=[100, 80, 80, 80, 80, 80])
        detailed_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(detailed_table)
        elements.append(Spacer(1, 12))

        # Generate visualizations
        plt.figure(figsize=(12, 10))

        # 1. GPA comparison
        plt.subplot(2, 2, 1)

        courses_list = [c['course'] for c in course_stats]
        avg_gpas = [c['avg_gpa'] for c in course_stats]

        bars = plt.bar(courses_list, avg_gpas, color='skyblue')
        plt.title('Average GPA by Course')
        plt.xlabel('Course')
        plt.ylabel('Average GPA')
        plt.ylim(0, 4.5)  # GPA typically ranges from 0 to 4.3

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.2f}', ha='center', va='bottom')

        # 2. Passing rate comparison
        plt.subplot(2, 2, 2)

        passing_rates = [c['passing_rate'] for c in course_stats]

        bars = plt.bar(courses_list, passing_rates, color='lightgreen')
        plt.title('Passing Rate by Course')
        plt.xlabel('Course')
        plt.ylabel('Passing Rate (%)')
        plt.ylim(0, 105)  # Percentage from 0 to 100

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{height:.1f}%', ha='center', va='bottom')

        # 3. Gender distribution comparison
        plt.subplot(2, 2, 3)

        X = np.arange(len(courses_list))
        width = 0.25

        male_pcts = [c['male_pct'] for c in course_stats]
        female_pcts = [c['female_pct'] for c in course_stats]
        other_pcts = [c['other_pct'] for c in course_stats]

        plt.bar(X - width, male_pcts, width, label='Male', color='lightblue')
        plt.bar(X, female_pcts, width, label='Female', color='lightpink')
        plt.bar(X + width, other_pcts, width, label='Other', color='lightgreen')

        plt.title('Gender Distribution by Course')
        plt.xlabel('Course')
        plt.ylabel('Percentage (%)')
        plt.xticks(X, courses_list)
        plt.legend()
        plt.ylim(0, 105)  # Percentage from 0 to 100

        # 4. Retention rate comparison
        plt.subplot(2, 2, 4)

        retention_rates = [c['retention_rate'] for c in course_stats]

        bars = plt.bar(courses_list, retention_rates, color='salmon')
        plt.title('Retention Rate by Course')
        plt.xlabel('Course')
        plt.ylabel('Retention Rate (%)')
        plt.ylim(0, 105)  # Percentage from 0 to 100

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{height:.1f}%', ha='center', va='bottom')

        plt.tight_layout()

        # Save the figure
        plots_filename = f"{reports_dir}/all_courses_stats_{timestamp}_plots.png"
        plt.savefig(plots_filename)
        plt.close()

        # Add visualizations to PDF
        elements.append(Paragraph("Visual Comparison", styles['Heading2']))
        elements.append(Spacer(1, 6))

        if os.path.exists(plots_filename):
            img = Image(plots_filename, width=7*inch, height=6*inch)
            elements.append(img)

        # Analysis and comparison
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Comparative Analysis", styles['Heading2']))

        # Find best and worst performing courses
        best_gpa = max(course_stats, key=lambda x: x['avg_gpa'])
        worst_gpa = min(course_stats, key=lambda x: x['avg_gpa'])

        best_passing = max(course_stats, key=lambda x: x['passing_rate'])
        worst_passing = min(course_stats, key=lambda x: x['passing_rate'])

        best_retention = max(course_stats, key=lambda x: x['retention_rate'])
        worst_retention = min(course_stats, key=lambda x: x['retention_rate'])

        # Analysis text
        elements.append(Paragraph("<b>Performance Highlights:</b>", styles['Normal']))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph(
            f"- Highest average GPA: <b>{best_gpa['course']}</b> with {best_gpa['avg_gpa']:.2f}",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Lowest average GPA: <b>{worst_gpa['course']}</b> with {worst_gpa['avg_gpa']:.2f}",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Highest passing rate: <b>{best_passing['course']}</b> with {best_passing['passing_rate']:.1f}%",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Lowest passing rate: <b>{worst_passing['course']}</b> with {worst_passing['passing_rate']:.1f}%",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Highest retention rate: <b>{best_retention['course']}</b> with {best_retention['retention_rate']:.1f}%",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Lowest retention rate: <b>{worst_retention['course']}</b> with {worst_retention['retention_rate']:.1f}%",
            styles['Normal']))

        # Calculate average statistics across all courses
        avg_all_gpa = sum(c['avg_gpa'] for c in course_stats) / len(course_stats)
        avg_all_passing = sum(c['passing_rate'] for c in course_stats) / len(course_stats)
        avg_all_retention = sum(c['retention_rate'] for c in course_stats) / len(course_stats)

        elements.append(Spacer(1, 12))
        elements.append(Paragraph("<b>Overall Statistics:</b>", styles['Normal']))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph(
            f"- Average GPA across all courses: {avg_all_gpa:.2f}",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Average passing rate across all courses: {avg_all_passing:.1f}%",
            styles['Normal']))

        elements.append(Paragraph(
            f"- Average retention rate across all courses: {avg_all_retention:.1f}%",
            styles['Normal']))

        # Add recommendations
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Recommendations:", styles['Heading2']))

        # Identify potential issues
        low_gpa_courses = [c for c in course_stats if c['avg_gpa'] < 2.5]
        low_passing_courses = [c for c in course_stats if c['passing_rate'] < 70]
        low_retention_courses = [c for c in course_stats if c['retention_rate'] < 80]

        if low_gpa_courses:
            elements.append(Paragraph(
                "- Review academic support and teaching methods for courses with low average GPAs: " +
                ", ".join([f"<b>{c['course']}</b>" for c in low_gpa_courses]),
                styles['Normal']))

        if low_passing_courses:
            elements.append(Paragraph(
                "- Investigate reasons for low passing rates in: " +
                ", ".join([f"<b>{c['course']}</b>" for c in low_passing_courses]),
                styles['Normal']))

        if low_retention_courses:
            elements.append(Paragraph(
                "- Address retention issues in: " +
                ", ".join([f"<b>{c['course']}</b>" for c in low_retention_courses]),
                styles['Normal']))

        elements.append(Paragraph(
            "- Consider adopting practices from high-performing courses across the curriculum.",
            styles['Normal']))

        elements.append(Paragraph(
            "- Implement standardized performance monitoring across all courses for early intervention.",
            styles['Normal']))

        # Build the PDF
        doc.build(elements)

        print(f"All courses comparison report generated: {report_filename}")

    except Exception as e:
        print(f"Error generating courses comparison report: {e}")

def generate_comprehensive_stats_report(cursor, reports_dir, timestamp):
    """Generate a comprehensive statistical report covering all aspects of student performance"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image
    from reportlab.platypus import Paragraph
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.platypus import Spacer
    from reportlab.platypus import Table
    from reportlab.platypus import TableStyle
    import matplotlib.pyplot as plt
    _, calculate_student_gpa, GRADE_SYSTEMS = _get_grading_imports()
    try:
        # Get overview of database
        cursor.execute('SELECT COUNT(*) FROM students')
        total_students = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM modules')
        total_modules = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM assessments')
        total_assessments = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM grades')
        total_grades = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT student_id) FROM module_grades')
        students_with_grades = cursor.fetchone()[0]

        # Get course statistics
        cursor.execute('''
        SELECT course, COUNT(*) as count
        FROM students
        GROUP BY course
        ''')

        course_counts = dict(cursor.fetchall())

        # Get module type statistics
        cursor.execute('''
        SELECT module_type, COUNT(*) as count
        FROM modules
        GROUP BY module_type
        ''')

        module_type_counts = dict(cursor.fetchall())

        # Get assessment type statistics
        cursor.execute('''
        SELECT assessment_type, COUNT(*) as count
        FROM assessments
        GROUP BY assessment_type
        ''')

        assessment_type_counts = dict(cursor.fetchall())

        # Get grade distribution
        cursor.execute('''
        SELECT mg.final_grade, COUNT(*) as count
        FROM module_grades mg
        GROUP BY mg.final_grade
        ''')

        grade_counts = dict(cursor.fetchall())

        # Calculate overall GPA statistics
        student_gpas = []
        cursor.execute('SELECT DISTINCT student_id FROM module_grades')
        students_with_module_grades = [s[0] for s in cursor.fetchall()]

        for student_id in students_with_module_grades:
            gpa, credits, _ = calculate_student_gpa(cursor, student_id)
            if gpa is not None:
                student_gpas.append((student_id, gpa))

        if student_gpas:
            gpas = [g[1] for g in student_gpas]
            avg_gpa = sum(gpas) / len(gpas)
            median_gpa = sorted(gpas)[len(gpas) // 2]
            min_gpa = min(gpas)
            max_gpa = max(gpas)
            std_dev_gpa = np.std(gpas)
        else:
            avg_gpa = 0
            median_gpa = 0
            min_gpa = 0
            max_gpa = 0
            std_dev_gpa = 0

        # Get top performing modules
        cursor.execute('''
        SELECT mg.module_code, m.module_name,
               AVG(mg.final_score) as avg_score,
               COUNT(mg.student_id) as student_count
        FROM module_grades mg
        JOIN modules m ON mg.module_code = m.module_code
        GROUP BY mg.module_code
        ORDER BY avg_score DESC
        LIMIT 5
        ''')

        top_modules = cursor.fetchall()

        # Get lowest performing modules
        cursor.execute('''
        SELECT mg.module_code, m.module_name,
               AVG(mg.final_score) as avg_score,
               COUNT(mg.student_id) as student_count
        FROM module_grades mg
        JOIN modules m ON mg.module_code = m.module_code
        GROUP BY mg.module_code
        ORDER BY avg_score ASC
        LIMIT 5
        ''')

        bottom_modules = cursor.fetchall()

        # Get top performing assessments
        cursor.execute('''
        SELECT a.assessment_id, a.assessment_name, a.module_code,
               AVG(g.score / a.max_points * 100) as avg_percentage,
               COUNT(g.grade_id) as student_count
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        GROUP BY a.assessment_id
        HAVING student_count >= 5  -- Minimum sample size
        ORDER BY avg_percentage DESC
        LIMIT 5
        ''')

        top_assessments = cursor.fetchall()

        # Get lowest performing assessments
        cursor.execute('''
        SELECT a.assessment_id, a.assessment_name, a.module_code,
               AVG(g.score / a.max_points * 100) as avg_percentage,
               COUNT(g.grade_id) as student_count
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        GROUP BY a.assessment_id
        HAVING student_count >= 5  -- Minimum sample size
        ORDER BY avg_percentage ASC
        LIMIT 5
        ''')

        bottom_assessments = cursor.fetchall()

        # Generate report in PDF format
        report_filename = f"{reports_dir}/comprehensive_stats_{timestamp}.pdf"

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
        elements.append(Paragraph("Comprehensive Performance Analysis", title_style))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Overview
        elements.append(Paragraph("System Overview", styles['Heading2']))

        overview_info = [
            ['Total Students:', str(total_students)],
            ['Students with Grades:', str(students_with_grades)],
            ['Total Modules:', str(total_modules)],
            ['Total Assessments:', str(total_assessments)],
            ['Total Grades Recorded:', str(total_grades)]
        ]

        overview_table = Table(overview_info, colWidths=[150, 350])
        overview_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))

        elements.append(overview_table)
        elements.append(Spacer(1, 12))

        # Course Distribution
        elements.append(Paragraph("Course Distribution", styles['Heading2']))

        course_data = [['Course', 'Students', 'Percentage']]
        for course, count in course_counts.items():
            percentage = (count / total_students) * 100 if total_students > 0 else 0
            course_data.append([course, str(count), f"{percentage:.1f}%"])

        course_table = Table(course_data, colWidths=[100, 100, 100])
        course_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (2, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (2, 0), 'CENTER'),
            ('ALIGN', (1, 1), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (2, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(course_table)
        elements.append(Spacer(1, 12))

        # Overall GPA Statistics
        if student_gpas:
            elements.append(Paragraph("Overall GPA Statistics", styles['Heading2']))

            gpa_info = [
                ['Average GPA:', f"{avg_gpa:.2f}"],
                ['Median GPA:', f"{median_gpa:.2f}"],
                ['Minimum GPA:', f"{min_gpa:.2f}"],
                ['Maximum GPA:', f"{max_gpa:.2f}"],
                ['Standard Deviation:', f"{std_dev_gpa:.2f}"]
            ]

            gpa_table = Table(gpa_info, colWidths=[150, 350])
            gpa_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('BOTTOMPADDING', (0, 0), (1, -1), 6),
            ]))

            elements.append(gpa_table)
            elements.append(Spacer(1, 12))

        # Grade Distribution
        if grade_counts:
            elements.append(Paragraph("Overall Grade Distribution", styles['Heading2']))

            # Sort the grade keys
            sorted_grades = sorted(grade_counts.keys(),
                                  key=lambda x: float('inf') if x not in GRADE_SYSTEMS["letter"] else -GRADE_SYSTEMS["letter"][x])

            grade_data = [['Grade', 'Count', 'Percentage']]
            total_grades_count = sum(grade_counts.values())

            for grade in sorted_grades:
                count = grade_counts[grade]
                percentage = (count / total_grades_count) * 100 if total_grades_count > 0 else 0
                grade_data.append([grade, str(count), f"{percentage:.1f}%"])

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

        # Top Performing Modules
        if top_modules:
            elements.append(Paragraph("Top Performing Modules", styles['Heading2']))

            top_modules_data = [['Module', 'Avg. Score', 'Students']]
            for module in top_modules:
                module_code, module_name, avg_score, student_count = module
                top_modules_data.append([
                    f"{module_code} - {module_name}",
                    f"{avg_score:.1f}%",
                    str(student_count)
                ])

            top_modules_table = Table(top_modules_data, colWidths=[300, 100, 100])
            top_modules_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (2, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (2, 0), 'CENTER'),
                ('ALIGN', (1, 1), (2, -1), 'CENTER'),
                ('GRID', (0, 0), (2, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            elements.append(top_modules_table)
            elements.append(Spacer(1, 12))

        # Lowest Performing Modules
        if bottom_modules:
            elements.append(Paragraph("Lowest Performing Modules", styles['Heading2']))

            bottom_modules_data = [['Module', 'Avg. Score', 'Students']]
            for module in bottom_modules:
                module_code, module_name, avg_score, student_count = module
                bottom_modules_data.append([
                    f"{module_code} - {module_name}",
                    f"{avg_score:.1f}%",
                    str(student_count)
                ])

            bottom_modules_table = Table(bottom_modules_data, colWidths=[300, 100, 100])
            bottom_modules_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (2, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (2, 0), 'CENTER'),
                ('ALIGN', (1, 1), (2, -1), 'CENTER'),
                ('GRID', (0, 0), (2, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            elements.append(bottom_modules_table)
            elements.append(Spacer(1, 12))

        # Generate visualizations
        plt.figure(figsize=(12, 10))

        # 1. Course Distribution
        plt.subplot(2, 2, 1)

        courses = list(course_counts.keys())
        counts = list(course_counts.values())

        plt.pie(counts, labels=courses, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
        plt.title('Course Distribution')

        # 2. Grade Distribution
        plt.subplot(2, 2, 2)

        if grade_counts:
            sorted_grades = sorted(grade_counts.keys(),
                                  key=lambda x: float('inf') if x not in GRADE_SYSTEMS["letter"] else -GRADE_SYSTEMS["letter"][x])

            grade_values = [grade_counts[grade] for grade in sorted_grades]

            bars = plt.bar(sorted_grades, grade_values, color='lightgreen')
            plt.title('Grade Distribution')
            plt.xlabel('Grade')
            plt.ylabel('Count')

            # Add count labels on top of bars
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{height:.0f}', ha='center', va='bottom')
        else:
            plt.text(0.5, 0.5, 'No grade data available',
                    horizontalalignment='center', verticalalignment='center')
            plt.title('Grade Distribution')
            plt.axis('off')

        # 3. GPA Distribution
        plt.subplot(2, 2, 3)

        if student_gpas:
            gpa_values = [g[1] for g in student_gpas]

            plt.hist(gpa_values, bins=10, color='skyblue', edgecolor='black')
            plt.title('GPA Distribution')
            plt.xlabel('GPA')
            plt.ylabel('Number of Students')
            plt.xlim(0, 4.5)  # GPA typically ranges from 0 to 4.3
        else:
            plt.text(0.5, 0.5, 'No GPA data available',
                    horizontalalignment='center', verticalalignment='center')
            plt.title('GPA Distribution')
            plt.axis('off')

        # 4. Module Performance Comparison
        plt.subplot(2, 2, 4)

        if top_modules and bottom_modules:
            # Combine top and bottom modules
            all_modules = top_modules + bottom_modules
            module_names = [f"{m[0]}" for m in all_modules]  # Just use code for brevity
            avg_scores = [m[2] for m in all_modules]
            bar_colors = ['green'] * len(top_modules) + ['red'] * len(bottom_modules)

            y_pos = np.arange(len(all_modules))
            bars = plt.barh(y_pos, avg_scores, color=bar_colors)
            plt.yticks(y_pos, module_names)
            plt.xlabel('Average Score (%)')
            plt.title('Top and Bottom Performing Modules')

            # Add value labels
            for i, bar in enumerate(bars):
                width = bar.get_width()
                plt.text(width + 1, bar.get_y() + bar.get_height()/2,
                        f'{width:.1f}%', ha='left', va='center')
        else:
            plt.text(0.5, 0.5, 'No module performance data available',
                    horizontalalignment='center', verticalalignment='center')
            plt.title('Module Performance Comparison')
            plt.axis('off')

        plt.tight_layout()

        # Save the figure
        plots_filename = f"{reports_dir}/comprehensive_stats_{timestamp}_plots.png"
        plt.savefig(plots_filename)
        plt.close()

        # Add visualizations to PDF
        elements.append(Paragraph("Visual Summary", styles['Heading2']))
        elements.append(Spacer(1, 6))

        if os.path.exists(plots_filename):
            img = Image(plots_filename, width=7*inch, height=6*inch)
            elements.append(img)

        # Key Insights
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Key Insights", styles['Heading2']))

        # Calculate general statistics
        passing_grade_count = sum(grade_counts.get(g, 0) for g in GRADE_SYSTEMS["letter"].keys() if g != 'F')
        total_grade_count = sum(grade_counts.values()) if grade_counts else 0
        overall_passing_rate = (passing_grade_count / total_grade_count * 100) if total_grade_count > 0 else 0

        at_risk_count = sum(1 for gpa in (g[1] for g in student_gpas) if gpa < 2.0)
        at_risk_percentage = (at_risk_count / len(student_gpas) * 100) if student_gpas else 0

        # Add insights
        elements.append(Paragraph("<b>Overall Academic Performance:</b>", styles['Normal']))

        if avg_gpa >= 3.5:
            elements.append(Paragraph("The overall academic performance is excellent, with a high average GPA.", styles['Normal']))
        elif avg_gpa >= 3.0:
            elements.append(Paragraph("The overall academic performance is good, with a solid average GPA.", styles['Normal']))
        elif avg_gpa >= 2.5:
            elements.append(Paragraph("The overall academic performance is satisfactory.", styles['Normal']))
        else:
            elements.append(Paragraph("The overall academic performance needs improvement.", styles['Normal']))

        elements.append(Spacer(1, 6))
        elements.append(Paragraph("<b>Student Achievement:</b>", styles['Normal']))
        elements.append(Paragraph(f"Overall passing rate: {overall_passing_rate:.1f}%", styles['Normal']))
        elements.append(Paragraph(f"At-risk students (GPA < 2.0): {at_risk_count} ({at_risk_percentage:.1f}%)", styles['Normal']))

        if at_risk_percentage > 20:
            elements.append(Paragraph("There is a concerning percentage of at-risk students that requires immediate attention.", styles['Normal']))
        elif at_risk_percentage > 10:
            elements.append(Paragraph("There is a moderate percentage of at-risk students that should be monitored.", styles['Normal']))
        else:
            elements.append(Paragraph("The percentage of at-risk students is relatively low.", styles['Normal']))

        # Add module-specific insights if available
        if top_modules and bottom_modules:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("<b>Module Performance:</b>", styles['Normal']))

            # Performance gap between top and bottom modules
            top_avg = top_modules[0][2]
            bottom_avg = bottom_modules[0][2]
            gap = top_avg - bottom_avg

            elements.append(Paragraph(f"Performance gap between highest and lowest modules: {gap:.1f}%", styles['Normal']))

            if gap > 30:
                elements.append(Paragraph("There is a significant performance gap between modules that requires investigation.", styles['Normal']))
            elif gap > 20:
                elements.append(Paragraph("There is a notable performance gap between modules.", styles['Normal']))
            else:
                elements.append(Paragraph("The performance across modules is relatively consistent.", styles['Normal']))

        # Recommendations
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Recommendations", styles['Heading2']))

        # Add targeted recommendations
        if at_risk_percentage > 15:
            elements.append(Paragraph("1. Implement an early intervention program for at-risk students.", styles['Normal']))
            elements.append(Paragraph("2. Provide additional academic support resources.", styles['Normal']))

        if bottom_modules:
            elements.append(Paragraph("3. Review teaching methods and materials for lowest performing modules.", styles['Normal']))
            elements.append(Paragraph("4. Consider curriculum adjustments for consistently challenging areas.", styles['Normal']))

        if top_modules:
            elements.append(Paragraph("5. Document and share best practices from top performing modules.", styles['Normal']))

        elements.append(Paragraph("6. Establish regular performance monitoring across all courses and modules.", styles['Normal']))
        elements.append(Paragraph("7. Develop targeted support strategies based on statistical analysis.", styles['Normal']))

        # Build the PDF
        doc.build(elements)

        print(f"Comprehensive statistical report generated: {report_filename}")

    except Exception as e:
        print(f"Error generating comprehensive report: {e}")
