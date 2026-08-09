import os
from datetime import datetime

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    _REPORTLAB_AVAILABLE = True
except ImportError:  # Optional dependency
    letter = None
    SimpleDocTemplate = None
    Table = None
    TableStyle = None
    Paragraph = None
    Spacer = None
    colors = None
    getSampleStyleSheet = None
    ParagraphStyle = None
    _REPORTLAB_AVAILABLE = False

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.assessment.grading.grade_calculation.utils import select_student
from education_system.systems.university.domain.assessment.grading.grade_calculation.gpa import calculate_student_gpa


def generate_transcript():
    """Generate a transcript for a student"""
    print("\nGenerate Transcript")

    try:
        if not _REPORTLAB_AVAILABLE:
            print("ReportLab is not installed; cannot generate transcript PDFs.")
            return
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        student_id = select_student(cursor)
        if not student_id:
            conn.close()
            return

        # Get student info
        cursor.execute('''
        SELECT first_name, middle_name, last_name, course, email_address, gender, dob
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()

        if not student:
            print(f"Student with ID {student_id} not found.")
            conn.close()
            return

        first_name, middle_name, last_name, course, email, gender, dob = student

        # Calculate GPA
        gpa, credits, module_grades = calculate_student_gpa(cursor, student_id)

        if gpa is None:
            print(f"No grades found for student {first_name} {last_name} (ID: {student_id}).")
            transcript_anyway = input("Generate transcript anyway? (y/n): ").strip().lower()
            if transcript_anyway != 'y':
                conn.close()
                return
            gpa = 0

        # Get all assessment grades
        cursor.execute('''
        SELECT a.module_code, m.module_name, a.assessment_name, a.assessment_type, a.weight,
               g.score, a.max_points, g.letter_grade, g.submission_date
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        JOIN modules m ON a.module_code = m.module_code
        WHERE g.student_id = ?
        ORDER BY a.module_code, a.assessment_name
        ''', (student_id,))

        assessment_grades = cursor.fetchall()

        # Create the exports directory if it doesn't exist
        exports_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'data', 'transcripts')
        exports_dir = os.path.normpath(exports_dir)
        if not os.path.exists(exports_dir):
            os.makedirs(exports_dir)

        # Generate a filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{exports_dir}/transcript_{student_id}_{timestamp}.pdf"

        # Ask for transcript format
        format_choice = input("\nTranscript format: (1) Simple or (2) Detailed? Enter 1 or 2: ").strip()

        if format_choice not in ['1', '2']:
            print("Invalid format choice. Using simple format.")
            format_choice = '1'

        # Pull APL/RPL credits awarded to this student (approved/partial
        # claims only) so the transcript surfaces recognised prior
        # learning alongside the standard module grades.
        apl_awards = []
        try:
            from education_system.systems.university.domain.admissions.prior_learning_recognition.services.prior_learning_service import (
                PriorLearningService,
            )
            apl_awards = PriorLearningService().awards_for_student(student_id)
        except Exception:
            apl_awards = []

        # Generate PDF transcript
        create_transcript_pdf(
            filename,
            student_id,
            first_name,
            middle_name,
            last_name,
            course,
            email,
            gender,
            dob,
            gpa,
            credits,
            module_grades,
            assessment_grades if format_choice == '2' else None,
            apl_awards=apl_awards,
        )

        print(f"\nTranscript generated successfully: {filename}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")


def create_transcript_pdf(filename, student_id, first_name, middle_name, last_name, course, email, gender, dob, gpa, credits, module_grades, assessment_grades=None, apl_awards=None):
    """Create a PDF transcript for a student"""
    try:
        if not _REPORTLAB_AVAILABLE:
            print("ReportLab is not installed; cannot generate transcript PDFs.")
            return
        # Create a PDF document
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Add university header
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Heading1'],
            alignment=1,  # Center alignment
            fontSize=16,
            spaceAfter=20
        )
        elements.append(Paragraph("University Student Transcript", header_style))

        # Add current date
        date_style = ParagraphStyle(
            'Date',
            parent=styles['Normal'],
            alignment=1,  # Center alignment
            fontSize=10,
            spaceAfter=20
        )
        current_date = datetime.now().strftime('%B %d, %Y')
        elements.append(Paragraph(f"Generated on {current_date}", date_style))

        # Add student information
        elements.append(Paragraph("Student Information", styles['Heading2']))

        middle_initial = middle_name[0] + ". " if middle_name else ""
        full_name = f"{first_name} {middle_initial}{last_name}"

        student_info = [
            ['Name:', full_name],
            ['ID:', student_id],
            ['Course:', course],
            ['Email:', email],
            ['Gender:', gender.capitalize() if gender else "N/A"],
            ['Date of Birth:', dob],
            ['GPA:', f"{gpa:.2f}" if gpa else "N/A"],
            ['Credits Completed:', str(credits)]
        ]

        student_table = Table(student_info, colWidths=[100, 400])
        student_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))

        elements.append(student_table)
        elements.append(Spacer(1, 20))

        # Add module grades
        elements.append(Paragraph("Module Grades", styles['Heading2']))

        if module_grades:
            module_header = [['Module Code', 'Module Name', 'Grade', 'GPA Points']]
            module_data = [[m[0], m[1], m[2], f"{m[3]:.2f}"] for m in module_grades]

            module_table = Table(module_header + module_data, colWidths=[80, 280, 60, 80])
            module_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (3, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (3, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (2, 0), (3, -1), 'CENTER'),
                ('GRID', (0, 0), (3, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            elements.append(module_table)
        else:
            elements.append(Paragraph("No module grades recorded.", styles['Normal']))

        elements.append(Spacer(1, 20))

        # Recognised Prior Learning section (APL/RPL credits) — only
        # rendered when the student has at least one approved/partial
        # claim with awarded credits.
        if apl_awards:
            elements.append(Paragraph("Recognised Prior Learning (APL/RPL)", styles['Heading2']))
            apl_header = [['Module Code', 'Module Name', 'Level', 'Credits', 'Grade']]
            apl_rows = []
            total_apl = 0
            for aw in apl_awards:
                total_apl += int(aw.get('credits_awarded') or 0)
                apl_rows.append([
                    aw.get('module_code') or '—',
                    aw.get('module_name') or '—',
                    str(aw.get('level') or '—'),
                    str(aw.get('credits_awarded') or 0),
                    aw.get('grade') or '—',
                ])
            apl_table = Table(apl_header + apl_rows, colWidths=[80, 240, 60, 60, 60])
            apl_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (4, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (4, 0), colors.lightgrey),
                ('ALIGN', (2, 0), (4, -1), 'CENTER'),
                ('GRID', (0, 0), (4, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(apl_table)
            elements.append(Paragraph(
                f"Total APL/RPL credits: {total_apl}", styles['Normal']
            ))
            elements.append(Spacer(1, 20))

        # Add assessment grades if detailed format
        if assessment_grades:
            elements.append(Paragraph("Assessment Grades", styles['Heading2']))

            # Group assessments by module
            modules = {}
            for grade in assessment_grades:
                module_code = grade[0]
                if module_code not in modules:
                    modules[module_code] = {
                        'name': grade[1],
                        'assessments': []
                    }

                # Add assessment to this module
                assessment_name = grade[2]
                assessment_type = grade[3]
                weight = grade[4]
                score = grade[5]
                max_points = grade[6]
                letter_grade = grade[7]
                submission_date = grade[8]

                percentage = (score / max_points) * 100
                score_display = f"{score}/{max_points} ({percentage:.1f}%)"

                modules[module_code]['assessments'].append([
                    assessment_name,
                    assessment_type,
                    f"{weight}%",
                    score_display,
                    letter_grade,
                    submission_date
                ])

            # Add each module's assessments to the PDF
            for module_code, module_data in modules.items():
                elements.append(Paragraph(f"{module_code} - {module_data['name']}", styles['Heading3']))

                assessment_header = [['Assessment', 'Type', 'Weight', 'Score', 'Grade', 'Date']]

                if module_data['assessments']:
                    assessment_table = Table(
                        assessment_header + module_data['assessments'],
                        colWidths=[150, 80, 50, 100, 50, 70]
                    )
                    assessment_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (5, 0), 'Helvetica-Bold'),
                        ('BACKGROUND', (0, 0), (5, 0), colors.lightgrey),
                        ('ALIGN', (2, 0), (5, -1), 'CENTER'),
                        ('GRID', (0, 0), (5, -1), 0.5, colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))

                    elements.append(assessment_table)
                else:
                    elements.append(Paragraph("No assessments recorded for this module.", styles['Normal']))

                elements.append(Spacer(1, 10))

        # Add GPA interpretation guide
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("GPA Interpretation", styles['Heading2']))

        gpa_guide = [
            ['GPA Range', 'Letter Grade', 'Performance Level'],
            ['4.0 - 4.3', 'A, A+', 'Excellent'],
            ['3.7 - 3.9', 'A-', 'Very Good'],
            ['3.3 - 3.6', 'B+', 'Good'],
            ['3.0 - 3.2', 'B', 'Above Average'],
            ['2.7 - 2.9', 'B-', 'Average'],
            ['2.3 - 2.6', 'C+', 'Fair'],
            ['2.0 - 2.2', 'C', 'Satisfactory'],
            ['1.7 - 1.9', 'C-', 'Below Average'],
            ['1.0 - 1.6', 'D+, D, D-', 'Poor'],
            ['0.0 - 0.9', 'F', 'Failing']
        ]

        gpa_table = Table(gpa_guide, colWidths=[100, 100, 300])
        gpa_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (2, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (2, 0), 'CENTER'),
            ('ALIGN', (0, 1), (1, -1), 'CENTER'),
            ('GRID', (0, 0), (2, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(gpa_table)

        # Add footer
        elements.append(Spacer(1, 30))
        footer_text = "This transcript is an unofficial record of academic performance. " + \
                      "An official transcript must bear the seal and signature of the University Registrar."
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=1  # Center alignment
        )
        elements.append(Paragraph(footer_text, footer_style))

        # Build the PDF
        doc.build(elements)
        return True

    except Exception as e:
        print(f"Error creating transcript: {e}")
        return False
