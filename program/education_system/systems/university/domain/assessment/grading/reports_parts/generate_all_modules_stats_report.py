"""Extracted function implementation."""

from .. import reports_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
