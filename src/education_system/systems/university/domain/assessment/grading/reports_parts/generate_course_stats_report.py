"""Extracted function implementation."""

from .. import reports_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
