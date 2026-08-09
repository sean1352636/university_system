"""Extracted function implementation."""

from .. import reports_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
