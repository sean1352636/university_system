"""Split from course_planning_gui.py — provides mixins assembled in
course_planning_gui/__init__.py into the final CoursePlanningGUI class."""
from __future__ import annotations

import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, Dict, List

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domain.academics.course_planning.services.planning_service import PlanningService
from education_system.systems.university.domain.assessment.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.systems.university.infrastructure.activity_logger import log_activity


class _ExportMixin:
    """Methods extracted from CoursePlanningGUI.export responsibility."""

    def _export_plan_pdf(self):
        """Export current plan to PDF."""
        if not self.current_plan_id or not self.current_plan_data:
            messagebox.showwarning("Warning", "Please load a plan first.")
            return

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            import datetime

        except ImportError:
            messagebox.showerror(
                "Error",
                "PDF export requires reportlab library.\n\n"
                "Install with: pip install reportlab"
            )
            return

        # Get save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"course_plan_{self.current_plan_id}.pdf"
        )

        if not filename:
            return

        try:
            plan = self.current_plan_data['plan']
            semesters = self.current_plan_data['semesters']

            # Create PDF
            doc = SimpleDocTemplate(filename, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()

            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            story.append(Paragraph(f"Course Plan: {plan['plan_name']}", title_style))
            story.append(Spacer(1, 0.3*inch))

            # Plan info
            info_data = [
                ["Student ID:", self.student_id],
                ["Program:", plan['program_code'] or 'N/A'],
                ["Start Semester:", plan['start_semester']],
                ["Total Semesters:", str(plan['total_semesters'])],
                ["Credits/Semester:", str(plan['credits_per_semester'])],
                ["Status:", plan['status']],
                ["Generated:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")]
            ]

            info_table = Table(info_data, colWidths=[2*inch, 4*inch])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            story.append(info_table)
            story.append(Spacer(1, 0.5*inch))

            # Semester breakdown
            for semester_num in sorted(semesters.keys()):
                courses = semesters[semester_num]
                if not courses:
                    continue

                total_credits = sum(c['credits'] for c in courses)

                # Semester header
                sem_header_style = ParagraphStyle(
                    'SemesterHeader',
                    parent=styles['Heading2'],
                    fontSize=14,
                    textColor=colors.HexColor('#3498db'),
                    spaceAfter=10
                )
                sem_name = courses[0]['semester_name'] if courses else f'Semester {semester_num}'
                story.append(Paragraph(
                    f"Semester {semester_num}: {sem_name} ({total_credits} Credits)",
                    sem_header_style
                ))

                # Course table
                course_data = [['Course ID', 'Course Name', 'Credits', 'Notes']]
                for course in courses:
                    notes = course['notes'] or ''
                    if course['is_locked']:
                        notes = '[LOCKED] ' + notes
                    course_data.append([
                        course['course_id'],
                        course['course_name'][:40],  # Truncate long names
                        str(course['credits']),
                        notes[:30]  # Truncate long notes
                    ])

                course_table = Table(course_data, colWidths=[1.2*inch, 2.5*inch, 0.8*inch, 1.5*inch])
                course_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(course_table)
                story.append(Spacer(1, 0.3*inch))

            # Build PDF
            doc.build(story)

            messagebox.showinfo("Success", f"Plan exported to PDF:\n{filename}")

            log_activity('export', 'semester_plan', user_id=self.student_id,
                        details={'action': 'export_pdf', 'plan_id': self.current_plan_id,
                                'filename': filename})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PDF: {e}")

    def _email_plan_to_advisor(self):
        """Email current plan to academic advisor."""
        if not self.current_plan_id or not self.current_plan_data:
            messagebox.showwarning("Warning", "Please load a plan first.")
            return

        # Create dialog to select advisor
        dialog = tk.Toplevel(self.window)
        dialog.title("Email Plan to Advisor")
        dialog.geometry("500x350")
        dialog.transient(self.window)
        dialog.grab_set()

        # Header
        ttk.Label(dialog, text="Select Academic Advisor",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        ttk.Label(dialog, text="Choose a staff member or administrator to email your course plan:",
                 font=('Arial', 10)).pack(pady=5)

        # Get staff and admin users
        with get_connection() as conn:
            staff_users = conn.execute("""
                SELECT id, username, email, role
                FROM users
                WHERE LOWER(role) IN ('staff', 'admin', 'instructor')
                AND email IS NOT NULL AND email != ''
                ORDER BY role, username
            """).fetchall()

        if not staff_users:
            messagebox.showerror("Error", "No staff/admin users found with email addresses.")
            dialog.destroy()
            return

        # List frame
        list_frame = ttk.LabelFrame(dialog, text="Available Advisors", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Create listbox with scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        advisor_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                     font=('Arial', 10), height=10)
        scrollbar.config(command=advisor_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        advisor_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Populate listbox
        advisor_data = {}
        for user in staff_users:
            display_text = f"{user['username']} ({user['role']}) - {user['email']}"
            advisor_listbox.insert(tk.END, display_text)
            advisor_data[display_text] = user

        selected_advisor = {'user': None}

        def select_and_send():
            selection = advisor_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select an advisor.")
                return

            selected_text = advisor_listbox.get(selection[0])
            selected_advisor['user'] = advisor_data[selected_text]
            dialog.destroy()

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(button_frame, text="Send Email", command=select_and_send).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Wait for dialog to close
        dialog.wait_window()

        # Check if an advisor was selected
        if not selected_advisor['user']:
            return

        advisor_email = selected_advisor['user']['email']
        advisor_name = selected_advisor['user']['username']

        try:
            # Check if email service is available
            try:
                from education_system.systems.university.infrastructure.email.email_service import queue_email
                EMAIL_AVAILABLE = True
            except ImportError:
                EMAIL_AVAILABLE = False

            if not EMAIL_AVAILABLE:
                messagebox.showerror(
                    "Error",
                    "Email service is not available.\n\n"
                    "Configure email settings in the system."
                )
                return

            plan = self.current_plan_data['plan']
            semesters = self.current_plan_data['semesters']

            # Build email body
            subject = f"Course Plan: {plan['plan_name']} - {self.current_user.get('username', 'Student')}"

            body = f"""Dear {advisor_name},

Please review my course plan for the upcoming semesters.

PLAN DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Student: {self.current_user.get('username', 'N/A')} ({self.student_id})
Plan Name: {plan['plan_name']}
Program: {plan['program_code'] or 'N/A'}
Start Semester: {plan['start_semester']}
Total Semesters: {plan['total_semesters']}
Target Credits/Semester: {plan['credits_per_semester']}
Status: {plan['status']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEMESTER BREAKDOWN
"""

            # Add semester details
            for semester_num in sorted(semesters.keys()):
                courses = semesters[semester_num]
                if not courses:
                    continue

                total_credits = sum(c['credits'] for c in courses)
                sem_name = courses[0]['semester_name'] if courses else f'Semester {semester_num}'

                body += f"\n\n{'='*60}\n"
                body += f"Semester {semester_num}: {sem_name} ({total_credits} Credits)\n"
                body += f"{'='*60}\n"

                for course in courses:
                    locked_flag = " [LOCKED]" if course['is_locked'] else ""
                    notes_text = f"\n    Notes: {course['notes']}" if course['notes'] else ""
                    body += f"  • {course['course_id']}: {course['course_name']} ({course['credits']} cr){locked_flag}{notes_text}\n"

            body += f"\n\n{'='*60}\n"
            body += f"Total Credits Planned: {sum(sum(c['credits'] for c in courses) for courses in semesters.values())}\n"
            body += f"{'='*60}\n\n"
            body += "Please let me know if you have any suggestions or concerns about this plan.\n\n"
            body += "Best regards,\n"
            body += f"{self.current_user.get('username', 'Student')}"

            # Send email
            success = queue_email(advisor_email, subject, body)

            if success:
                messagebox.showinfo(
                    "Success",
                    f"Course plan emailed to:\n{advisor_email}\n\n"
                    "Your advisor will receive the plan details shortly."
                )

                log_activity('email', 'semester_plan', user_id=self.student_id,
                            details={'action': 'email_to_advisor', 'plan_id': self.current_plan_id,
                                    'advisor_email': advisor_email})
            else:
                messagebox.showerror("Error", "Failed to queue email. Please try again.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to email plan: {e}")

    def _email_report_to_admin(self):
        """Email the current plan report to all admin users."""
        if not self.current_plan_id or not self.current_plan_data:
            messagebox.showwarning("Warning", "Please load a plan first.")
            return

        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            plan = self.current_plan_data['plan']
            semesters = self.current_plan_data['semesters']

            # Build report text
            report = f"COURSE PLAN REPORT\n{'='*60}\n\n"
            report += f"Student ID: {self.student_id}\n"
            report += f"Plan: {plan['plan_name']}\n"
            report += f"Program: {plan.get('program_code', 'N/A')}\n"
            report += f"Status: {plan.get('status', 'N/A')}\n\n"

            for sem_num in sorted(semesters.keys()):
                courses = semesters[sem_num]
                if not courses:
                    continue
                total_cr = sum(c['credits'] for c in courses)
                sem_name = courses[0].get('semester_name', f'Semester {sem_num}')
                report += f"--- {sem_name} ({total_cr} credits) ---\n"
                for c in courses:
                    report += f"  {c['course_id']}: {c['course_name']} ({c['credits']} cr)\n"
                report += "\n"

            report += f"{'='*60}\n"

            # Get admin emails
            with get_connection() as conn:
                admins = conn.execute(
                    "SELECT email FROM users WHERE LOWER(role) = 'admin' "
                    "AND email IS NOT NULL AND email != ''"
                ).fetchall()

            if not admins:
                messagebox.showinfo("No Admins", "No admin email addresses found.")
                return

            sent = 0
            for row in admins:
                try:
                    send_email(
                        recipient_email=row['email'] if hasattr(row, '__getitem__') and not isinstance(row, tuple) else row[0],
                        subject=f"Course Plan Report: {plan['plan_name']} ({self.student_id})",
                        body=report
                    )
                    sent += 1
                except Exception:
                    pass

            if sent > 0:
                messagebox.showinfo("Email Sent", f"Report emailed to {sent} admin(s).")
            else:
                messagebox.showwarning("Email Failed", "Could not send email to any admin.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to email report: {e}")

