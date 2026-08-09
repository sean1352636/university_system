"""Extracted function implementation."""

from .. import reports_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
