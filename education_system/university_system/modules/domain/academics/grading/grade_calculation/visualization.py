import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

matplotlib.use('Agg')

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.academics.grading.grade_calculation.constants import GRADE_SYSTEMS
from education_system.university_system.modules.domain.academics.grading.grade_calculation.utils import select_assessment


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
