"""Extracted function implementation."""

from .. import reports_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
