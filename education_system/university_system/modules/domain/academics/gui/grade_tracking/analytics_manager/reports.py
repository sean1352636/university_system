"""Reporting and transcript methods for AnalyticsManager."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.scrolledtext as scrolledtext
import csv
import json
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.constants import get_connection
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.utils import safe_grab_set

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except ImportError:
    plt = None
    FigureCanvasTkAgg = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
except ImportError:
    SimpleDocTemplate = None


class ReportsMixin:
    """Mixin providing reporting methods."""

    def _display_report(self, title, sections, footer=None):
        """Render report content in a separate window with email option."""
        # Create separate window for report
        report_window = tk.Toplevel(self.root)
        report_window.title(title)
        report_window.geometry("800x600")

        # Create main frame
        main_frame = ttk.Frame(report_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create scrolled text widget for report
        report_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Courier', 10))
        report_text.pack(fill=tk.BOTH, expand=True)

        # Build report content
        lines = [
            title,
            "=" * len(title),
            f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
            ""
        ]

        for heading, content_lines in sections:
            heading = heading.strip() or "Details"
            lines.append(heading)
            lines.append("-" * len(heading))
            if content_lines:
                lines.extend(content_lines)
            else:
                lines.append("No data available.")
            lines.append("")

        if footer:
            lines.append(footer)

        report_content = "\n".join(lines).rstrip() + "\n"
        report_text.insert('1.0', report_content)
        report_text.config(state='disabled')

        # Button frame at bottom
        button_frame = ttk.Frame(report_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        # Email to Admin button
        def email_to_admin():
            try:
                # Get admin email from database - try multiple tables/columns
                conn = get_connection()
                cursor = conn.cursor()

                admin_email = None
                # Try users table with case-insensitive role check
                try:
                    cursor.execute("""
                        SELECT email FROM users
                        WHERE LOWER(role) IN ('admin', 'administrator')
                        AND email IS NOT NULL AND email != ''
                        LIMIT 1
                    """)
                    admin_row = cursor.fetchone()
                    if admin_row and admin_row[0]:
                        admin_email = admin_row[0]
                except sqlite3.Error:
                    pass

                # Try email_address column as fallback (some schemas may use this)
                if not admin_email:
                    try:
                        cursor.execute("""
                            SELECT email_address FROM users
                            WHERE LOWER(role) IN ('admin', 'administrator')
                            AND email_address IS NOT NULL AND email_address != ''
                            LIMIT 1
                        """)
                        admin_row = cursor.fetchone()
                        if admin_row and admin_row[0]:
                            admin_email = admin_row[0]
                    except sqlite3.Error:
                        pass

                conn.close()

                if not admin_email:
                    messagebox.showwarning("No Admin", "No administrator email found in the database.\nPlease ensure an admin user exists with a valid email address.")
                    return

                # Try to use email service
                try:
                    from education_system.university_system.infrastructure.email.email_service import send_email

                    # Send email with report content
                    success = send_email(
                        recipient_email=admin_email,
                        subject=f"Grade Tracking Report: {title}",
                        body=f"Please find the attached report:\n\n{report_content}"
                    )

                    if success:
                        messagebox.showinfo("Success", f"Report emailed to administrator at {admin_email}")
                    else:
                        messagebox.showerror("Error", "Failed to send email. Please check email service configuration.")
                except ImportError as ie:
                    messagebox.showerror("Error", f"Email service import error: {ie}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to send email: {e}")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to retrieve admin email: {e}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to email report: {e}")

        ttk.Button(button_frame, text="Email to Admin", command=email_to_admin).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)


    def export_risk_results(self, tree):
        """Export risk analysis results"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx")],
                title="Export Risk Results"
            )

            if filename:
                # Get data from treeview
                data = []
                for item in tree.get_children():
                    data.append(tree.item(item, 'values'))

                if filename.endswith('.xlsx'):
                    # Export to Excel (if available)
                    try:
                        import pandas as pd
                        df = pd.DataFrame(data, columns=['Student ID', 'Name', 'Course', 'Risk Score',
                                        'Risk Level', 'Factors', 'GPA', 'Failed Assessments'])
                        df.to_excel(filename, index=False)
                    except ImportError:
                        messagebox.showerror("Error", "pandas library required for Excel export")
                        return
                else:
                    # Export to CSV
                    with open(filename, 'w', newline='', encoding='utf-8') as file:
                        writer = csv.writer(file)
                        writer.writerow(['Student ID', 'Name', 'Course', 'Risk Score',
                                       'Risk Level', 'Factors', 'GPA', 'Failed Assessments'])
                        writer.writerows(data)

                messagebox.showinfo("Success", f"Risk results exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export results: {e}")

    def show_grade_trends_chart(self):
        """Show grade trends in a visual chart"""
        if plt is None:
            messagebox.showinfo("Feature Unavailable", "Matplotlib is required for chart visualization.")
            return

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Query both data sources
            cursor.execute("""
                SELECT submission_date, AVG(percentage) AS avg_score
                FROM (
                    -- Traditional assessments
                    SELECT submission_date, (score / max_points * 100) AS percentage
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    WHERE submission_date IS NOT NULL

                    UNION ALL

                    -- Assignment submissions
                    SELECT graded_date AS submission_date, grade AS percentage
                    FROM assignment_submissions
                    WHERE graded_date IS NOT NULL AND grade IS NOT NULL
                ) AS combined_grades
                GROUP BY submission_date
                ORDER BY submission_date
            """)

            data = cursor.fetchall()
            if not data:
                messagebox.showinfo("Grade Trends", "No data available for trend chart.")
                return

            dates = [row[0] for row in data]
            scores = [row[1] for row in data]

            # Create chart window
            chart_window = tk.Toplevel(self.root)
            chart_window.title("Grade Trends Chart")
            chart_window.geometry("900x600")

            fig, ax = plt.subplots(figsize=(11, 6))
            ax.plot(range(len(dates)), scores, marker='o', linestyle='-', linewidth=2, markersize=6, color='#2E86AB')
            ax.fill_between(range(len(dates)), scores, alpha=0.2, color='#2E86AB')
            ax.axhline(y=70, color='orange', linestyle='--', alpha=0.7, label='Passing Grade (70%)')
            ax.axhline(y=90, color='green', linestyle='--', alpha=0.7, label='Excellence (90%)')
            ax.set_xlabel("Time Period", fontsize=12)
            ax.set_ylabel("Average Score (%)", fontsize=12)
            ax.set_title("Grade Trends Over Time (All Students)", fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            ax.set_ylim(0, 105)

            canvas = FigureCanvasTkAgg(fig, chart_window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Add statistics
            avg_overall = sum(scores) / len(scores)
            stats_frame = ttk.Frame(chart_window)
            stats_frame.pack(fill='x', padx=10, pady=5)
            stats_text = f"Data Points: {len(data)} | Overall Average: {avg_overall:.1f}% | Trend: {'Improving' if scores[-1] > scores[0] else 'Declining' if scores[-1] < scores[0] else 'Stable'}"
            ttk.Label(stats_frame, text=stats_text, font=('Arial', 10, 'bold')).pack()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to show trends: {e}")
        finally:
            if conn:
                conn.close()

    def student_progress_charts(self):
        """Show student progress charts"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get all students
            cursor.execute("SELECT student_id, first_name || ' ' || last_name FROM students ORDER BY last_name")
            students = cursor.fetchall()

            if not students:
                messagebox.showinfo("No Students", "No students found.")
                return

            # Selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Student for Progress Charts")
            dialog.geometry("400x500")
            safe_grab_set(dialog)

            ttk.Label(dialog, text="Select a student:", font=('Arial', 12, 'bold')).pack(pady=10)

            list_frame = ttk.Frame(dialog)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)

            for student_id, name in students:
                listbox.insert(tk.END, f"{student_id} - {name}")

            def show_charts():
                selection = listbox.curselection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a student.")
                    return

                student_id = students[selection[0]][0]
                student_name = students[selection[0]][1]
                dialog.destroy()
                self._show_student_progress_charts(student_id, student_name)

            ttk.Button(dialog, text="Show Progress Charts", command=show_charts).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load students: {e}")
        finally:
            if conn:
                conn.close()

    def _show_student_progress_charts(self, student_id, student_name):
        """Display progress charts for a specific student"""
        if plt is None:
            messagebox.showinfo("Feature Unavailable",
                              "Matplotlib is required for chart visualization.\n"
                              "Install it with: pip install matplotlib")
            return

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student grades from both sources
            cursor.execute("""
                SELECT
                    submission_date,
                    percentage,
                    letter_grade,
                    assessment_name
                FROM (
                    -- Traditional assessments
                    SELECT
                        g.submission_date,
                        (g.score / a.max_points * 100) AS percentage,
                        g.letter_grade,
                        a.assessment_name
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    WHERE g.student_id = ?

                    UNION ALL

                    -- Assignment submissions
                    SELECT
                        sub.graded_date AS submission_date,
                        sub.grade AS percentage,
                        CASE
                            WHEN sub.grade >= 93 THEN 'A+'
                            WHEN sub.grade >= 90 THEN 'A'
                            WHEN sub.grade >= 87 THEN 'A-'
                            WHEN sub.grade >= 83 THEN 'B+'
                            WHEN sub.grade >= 80 THEN 'B'
                            WHEN sub.grade >= 77 THEN 'B-'
                            WHEN sub.grade >= 73 THEN 'C+'
                            WHEN sub.grade >= 70 THEN 'C'
                            WHEN sub.grade >= 67 THEN 'C-'
                            WHEN sub.grade >= 63 THEN 'D+'
                            WHEN sub.grade >= 60 THEN 'D'
                            WHEN sub.grade >= 57 THEN 'D-'
                            ELSE 'F'
                        END AS letter_grade,
                        asn.title AS assessment_name
                    FROM assignment_submissions sub
                    JOIN assignments asn ON sub.assignment_id = asn.id
                    WHERE sub.student_id = ? AND sub.grade IS NOT NULL
                ) AS combined_grades
                WHERE submission_date IS NOT NULL
                ORDER BY submission_date
            """, (student_id, student_id))

            data = cursor.fetchall()

            if not data:
                messagebox.showinfo("No Data", f"No grades found for {student_name}")
                return

            dates = [row[0] for row in data]
            scores = [row[1] for row in data]

            # Create chart window
            chart_window = tk.Toplevel(self.root)
            chart_window.title(f"Progress Charts - {student_name}")
            chart_window.geometry("1000x700")

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

            # Chart 1: Score progression over time
            ax1.plot(range(len(dates)), scores, marker='o', linestyle='-', linewidth=2, markersize=8, color='#2E86AB')
            ax1.axhline(y=70, color='orange', linestyle='--', label='Passing Grade (70%)')
            ax1.axhline(y=90, color='green', linestyle='--', label='Excellence (90%)')
            ax1.fill_between(range(len(dates)), scores, alpha=0.3, color='#2E86AB')
            ax1.set_xlabel("Assessment Number", fontsize=12)
            ax1.set_ylabel("Score (%)", fontsize=12)
            ax1.set_title(f"{student_name} - Grade Progression Over Time", fontsize=14, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            ax1.set_ylim(0, 105)

            # Chart 2: Grade distribution (bar chart)
            grade_counts = {}
            for row in data:
                letter = row[2]
                grade_counts[letter] = grade_counts.get(letter, 0) + 1

            grades_order = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']
            grade_labels = [g for g in grades_order if g in grade_counts]
            grade_values = [grade_counts[g] for g in grade_labels]

            colors = ['#2ECC40' if g.startswith('A') else '#FFDC00' if g.startswith('B')
                     else '#FF851B' if g.startswith('C') else '#FF4136' for g in grade_labels]

            ax2.bar(grade_labels, grade_values, color=colors, alpha=0.7)
            ax2.set_xlabel("Letter Grade", fontsize=12)
            ax2.set_ylabel("Count", fontsize=12)
            ax2.set_title(f"{student_name} - Grade Distribution", fontsize=14, fontweight='bold')
            ax2.grid(True, alpha=0.3, axis='y')

            plt.tight_layout()

            canvas = FigureCanvasTkAgg(fig, chart_window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Add statistics text
            avg_score = sum(scores) / len(scores)
            stats_frame = ttk.Frame(chart_window)
            stats_frame.pack(fill='x', padx=10, pady=5)

            stats_text = f"Total Assessments: {len(data)} | Average Score: {avg_score:.1f}% | Highest: {max(scores):.1f}% | Lowest: {min(scores):.1f}%"
            ttk.Label(stats_frame, text=stats_text, font=('Arial', 10, 'bold')).pack()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate charts: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create charts: {e}")
        finally:
            if conn:
                conn.close()

    def generate_individual_transcript(self):
        """Generate official transcript for a student"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get all students
            cursor.execute("SELECT student_id, first_name || ' ' || last_name FROM students ORDER BY last_name")
            students = cursor.fetchall()

            if not students:
                messagebox.showinfo("No Students", "No students found.")
                return

            # Selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Student for Transcript")
            dialog.geometry("400x500")
            safe_grab_set(dialog)

            ttk.Label(dialog, text="Select a student:", font=('Arial', 12, 'bold')).pack(pady=10)

            list_frame = ttk.Frame(dialog)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)

            for student_id, name in students:
                listbox.insert(tk.END, f"{student_id} - {name}")

            # Export format selection
            format_frame = ttk.LabelFrame(dialog, text="Export Format", padding=10)
            format_frame.pack(fill='x', padx=10, pady=10)

            format_var = tk.StringVar(value="display")
            ttk.Radiobutton(format_frame, text="Display in Window", variable=format_var, value="display").pack(anchor='w')
            ttk.Radiobutton(format_frame, text="Save as Text (.txt)", variable=format_var, value="txt").pack(anchor='w')
            ttk.Radiobutton(format_frame, text="Save as PDF (.pdf)", variable=format_var, value="pdf").pack(anchor='w')
            ttk.Radiobutton(format_frame, text="Save as JSON (.json)", variable=format_var, value="json").pack(anchor='w')

            def generate_transcript():
                selection = listbox.curselection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a student.")
                    return

                student_id = students[selection[0]][0]
                export_format = format_var.get()
                dialog.destroy()
                self._generate_transcript_for_student(student_id, export_format)

            ttk.Button(dialog, text="Generate", command=generate_transcript).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load students: {e}")
        finally:
            if conn:
                conn.close()

    def _generate_transcript_for_student(self, student_id, export_format="display"):
        """Helper to generate transcript"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student info
            cursor.execute("""
                SELECT first_name, last_name, course, enrollment_date
                FROM students
                WHERE student_id = ?
            """, (student_id,))
            student_info = cursor.fetchone()

            if not student_info:
                messagebox.showerror("Error", f"Student {student_id} not found")
                return

            # Get grades from both sources with type information
            cursor.execute("""
                SELECT
                    module_code,
                    module_name,
                    assessment_name,
                    assessment_type,
                    score,
                    max_points,
                    letter_grade,
                    submission_date
                FROM (
                    -- Traditional assessments from grades table
                    SELECT
                        m.module_code,
                        m.module_name,
                        a.assessment_name,
                        COALESCE(a.assessment_type, 'Assessment') AS assessment_type,
                        g.score,
                        a.max_points,
                        g.letter_grade,
                        g.submission_date
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    JOIN modules m ON a.module_code = m.module_code
                    WHERE g.student_id = ?

                    UNION ALL

                    -- Assignment submissions from assignment_submissions table
                    SELECT
                        m.module_code,
                        m.module_name,
                        asn.title AS assessment_name,
                        'Assignment' AS assessment_type,
                        ROUND((sub.grade * COALESCE(asn.max_marks, 100) / 100), 2) AS score,
                        COALESCE(asn.max_marks, 100) AS max_points,
                        CASE
                            WHEN sub.grade >= 93 THEN 'A+'
                            WHEN sub.grade >= 90 THEN 'A'
                            WHEN sub.grade >= 87 THEN 'A-'
                            WHEN sub.grade >= 83 THEN 'B+'
                            WHEN sub.grade >= 80 THEN 'B'
                            WHEN sub.grade >= 77 THEN 'B-'
                            WHEN sub.grade >= 73 THEN 'C+'
                            WHEN sub.grade >= 70 THEN 'C'
                            WHEN sub.grade >= 67 THEN 'C-'
                            WHEN sub.grade >= 63 THEN 'D+'
                            WHEN sub.grade >= 60 THEN 'D'
                            WHEN sub.grade >= 57 THEN 'D-'
                            ELSE 'F'
                        END AS letter_grade,
                        sub.graded_date AS submission_date
                    FROM assignment_submissions sub
                    JOIN assignments asn ON sub.assignment_id = asn.id
                    JOIN modules m ON asn.module_code = m.module_code
                    WHERE sub.student_id = ? AND sub.grade IS NOT NULL
                ) AS combined_grades
                ORDER BY module_code, submission_date
            """, (student_id, student_id))
            grades = cursor.fetchall()

            # Calculate GPA
            grade_points = {
                'A+': 4.3, 'A': 4.0, 'A-': 3.7,
                'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                'C+': 2.3, 'C': 2.0, 'C-': 1.7,
                'D+': 1.3, 'D': 1.0, 'D-': 0.7,
                'F': 0.0
            }
            gpa = sum(grade_points.get(g[6], 0) for g in grades) / len(grades) if grades else 0

            first_name, last_name, course, enrollment_date = student_info
            full_name = f"{first_name} {last_name}"

            # Handle different export formats
            if export_format == "txt":
                self._export_transcript_txt(student_id, full_name, course, enrollment_date, grades, gpa)
            elif export_format == "pdf":
                self._export_transcript_pdf(student_id, full_name, course, enrollment_date, grades, gpa)
            elif export_format == "json":
                self._export_transcript_json(student_id, full_name, course, enrollment_date, grades, gpa)
            else:  # display
                grade_lines = [
                    f"{module_code} - {module_name}\n"
                    f"  [{assess_type}] {assessment}: {score}/{max_points} ({letter}) - {date}"
                    for module_code, module_name, assessment, assess_type, score, max_points, letter, date in grades
                ]

                sections = [
                    ("Student Information", [
                        f"Name: {full_name}",
                        f"Student ID: {student_id}",
                        f"Course: {course}",
                        f"Enrollment Date: {enrollment_date}"
                    ]),
                    ("Academic Record", grade_lines if grade_lines else ["No grades recorded"]),
                    ("Summary", [
                        f"Total Assessments: {len(grades)}",
                        f"Cumulative GPA: {gpa:.2f}"
                    ])
                ]

                self._display_report(f"Official Transcript - {full_name}", sections,
                                   "This is an unofficial transcript for internal use only.")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate transcript: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate transcript: {e}")
        finally:
            if conn:
                conn.close()

    def _export_transcript_txt(self, student_id, full_name, course, enrollment_date, grades, gpa):
        """Export transcript as text file"""
        filename = filedialog.asksaveasfilename(
            title="Save Transcript as Text",
            defaultextension=".txt",
            initialfile=f"transcript_{student_id}.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not filename:
            return

        try:
            with open(filename, 'w') as f:
                f.write("=" * 70 + "\n")
                f.write("OFFICIAL TRANSCRIPT\n")
                f.write("=" * 70 + "\n\n")

                f.write("STUDENT INFORMATION\n")
                f.write("-" * 70 + "\n")
                f.write(f"Name: {full_name}\n")
                f.write(f"Student ID: {student_id}\n")
                f.write(f"Course: {course}\n")
                f.write(f"Enrollment Date: {enrollment_date}\n\n")

                f.write("ACADEMIC RECORD\n")
                f.write("-" * 70 + "\n")
                if grades:
                    current_module = None
                    for module_code, module_name, assessment, assess_type, score, max_points, letter, date in grades:
                        if module_code != current_module:
                            f.write(f"\n{module_code} - {module_name}\n")
                            current_module = module_code
                        f.write(f"  [{assess_type}] {assessment}: {score}/{max_points} ({letter}) - {date}\n")
                else:
                    f.write("No grades recorded\n")

                f.write("\n" + "=" * 70 + "\n")
                f.write("SUMMARY\n")
                f.write("=" * 70 + "\n")
                f.write(f"Total Assessments: {len(grades)}\n")
                f.write(f"Cumulative GPA: {gpa:.2f}\n\n")
                f.write("This is an unofficial transcript for internal use only.\n")
                f.write("Generated on: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")

            messagebox.showinfo("Success", f"Transcript saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save transcript: {e}")

    def _export_transcript_pdf(self, student_id, full_name, course, enrollment_date, grades, gpa):
        """Export transcript as PDF file"""
        if SimpleDocTemplate is None:
            messagebox.showerror("Error", "PDF export requires reportlab library. Please install it with: pip install reportlab")
            return

        filename = filedialog.asksaveasfilename(
            title="Save Transcript as PDF",
            defaultextension=".pdf",
            initialfile=f"transcript_{student_id}.pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not filename:
            return

        try:
            from reportlab.platypus import Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch

            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Title
            title_style = styles['Title']
            story.append(Paragraph("OFFICIAL TRANSCRIPT", title_style))
            story.append(Spacer(1, 0.3 * inch))

            # Student Information
            heading_style = styles['Heading2']
            story.append(Paragraph("Student Information", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            info_text = f"""
            <b>Name:</b> {full_name}<br/>
            <b>Student ID:</b> {student_id}<br/>
            <b>Course:</b> {course}<br/>
            <b>Enrollment Date:</b> {enrollment_date}
            """
            story.append(Paragraph(info_text, styles['Normal']))
            story.append(Spacer(1, 0.3 * inch))

            # Academic Record
            story.append(Paragraph("Academic Record", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            if grades:
                current_module = None
                for module_code, module_name, assessment, assess_type, score, max_points, letter_grade, date in grades:
                    if module_code != current_module:
                        module_text = f"<b>{module_code} - {module_name}</b>"
                        story.append(Paragraph(module_text, styles['Normal']))
                        story.append(Spacer(1, 0.05 * inch))
                        current_module = module_code

                    grade_text = f"&nbsp;&nbsp;&nbsp;&nbsp;[{assess_type}] {assessment}: {score}/{max_points} ({letter_grade}) - {date}"
                    story.append(Paragraph(grade_text, styles['Normal']))
            else:
                story.append(Paragraph("No grades recorded", styles['Normal']))

            story.append(Spacer(1, 0.3 * inch))

            # Summary
            story.append(Paragraph("Summary", heading_style))
            story.append(Spacer(1, 0.1 * inch))
            summary_text = f"""
            <b>Total Assessments:</b> {len(grades)}<br/>
            <b>Cumulative GPA:</b> {gpa:.2f}
            """
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 0.3 * inch))

            # Footer
            footer_text = "This is an unofficial transcript for internal use only.<br/>"
            footer_text += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            story.append(Paragraph(footer_text, styles['Italic']))

            doc.build(story)
            messagebox.showinfo("Success", f"Transcript saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save PDF: {e}")

    def _export_transcript_json(self, student_id, full_name, course, enrollment_date, grades, gpa):
        """Export transcript as JSON file"""
        filename = filedialog.asksaveasfilename(
            title="Save Transcript as JSON",
            defaultextension=".json",
            initialfile=f"transcript_{student_id}.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filename:
            return

        try:
            transcript_data = {
                "student_information": {
                    "student_id": student_id,
                    "name": full_name,
                    "course": course,
                    "enrollment_date": enrollment_date
                },
                "academic_record": [
                    {
                        "module_code": grade[0],
                        "module_name": grade[1],
                        "assessment_name": grade[2],
                        "assessment_type": grade[3],
                        "score": float(grade[4]) if grade[4] else None,
                        "max_points": float(grade[5]) if grade[5] else None,
                        "letter_grade": grade[6],
                        "submission_date": grade[7]
                    }
                    for grade in grades
                ],
                "summary": {
                    "total_assessments": len(grades),
                    "cumulative_gpa": round(gpa, 2)
                },
                "metadata": {
                    "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "note": "This is an unofficial transcript for internal use only."
                }
            }

            with open(filename, 'w') as f:
                json.dump(transcript_data, f, indent=2)

            messagebox.showinfo("Success", f"Transcript saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save JSON: {e}")

    def generate_student_progress_report(self):
        """Generate comprehensive student progress report with statistics and insights"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student progress data
            cursor.execute('''
            SELECT
                s.student_id,
                s.first_name,
                s.last_name,
                s.course,
                COUNT(DISTINCT a.module_code) AS module_count,
                COUNT(g.grade_id) AS grade_count,
                AVG(
                    CASE
                        WHEN a.max_points IS NOT NULL AND a.max_points > 0
                        THEN (g.score / a.max_points) * 100
                    END
                ) AS avg_percentage,
                SUM(CASE WHEN g.letter_grade = 'F' THEN 1 ELSE 0 END) AS fail_count
            FROM students s
            LEFT JOIN grades g ON s.student_id = g.student_id
            LEFT JOIN assessments a ON g.assessment_id = a.assessment_id
            GROUP BY s.student_id, s.first_name, s.last_name, s.course
            ORDER BY s.last_name, s.first_name
            ''')
            rows = cursor.fetchall()

            # Get GPA data (calculate grade points from final_grade)
            cursor.execute('''
            SELECT student_id, AVG(
                CASE final_grade
                    WHEN 'A+' THEN 4.0
                    WHEN 'A' THEN 4.0
                    WHEN 'A-' THEN 3.7
                    WHEN 'B+' THEN 3.3
                    WHEN 'B' THEN 3.0
                    WHEN 'B-' THEN 2.7
                    WHEN 'C+' THEN 2.3
                    WHEN 'C' THEN 2.0
                    WHEN 'C-' THEN 1.7
                    WHEN 'D+' THEN 1.3
                    WHEN 'D' THEN 1.0
                    WHEN 'D-' THEN 0.7
                    WHEN 'F' THEN 0.0
                    ELSE NULL
                END
            ) AS avg_gpa
            FROM module_grades
            WHERE final_grade IS NOT NULL
            GROUP BY student_id
            ''')
            gpa_map = {row[0]: row[1] for row in cursor.fetchall()}

            # Process student records
            progress_records = []
            for row in rows:
                student_id, first_name, last_name, course, modules, grades_count, avg_percent, fail_count = row
                name = " ".join(part for part in (first_name, last_name) if part)
                progress_records.append({
                    "student_id": student_id,
                    "name": name or student_id,
                    "course": course or "Unassigned",
                    "modules": modules or 0,
                    "grades": grades_count or 0,
                    "avg_percent": avg_percent if avg_percent is not None else None,
                    "failures": fail_count or 0,
                    "gpa": gpa_map.get(student_id)
                })

            # Calculate statistics
            total_students = len(progress_records)
            graded_students = sum(1 for r in progress_records if r["grades"] > 0)
            avg_scores = [r["avg_percent"] for r in progress_records if r["avg_percent"] is not None]
            avg_gpas = [r["gpa"] for r in progress_records if r["gpa"] is not None]
            low_participation = sum(1 for r in progress_records if r["grades"] < 3)

            overall_avg = sum(avg_scores) / len(avg_scores) if avg_scores else None
            overall_gpa = sum(avg_gpas) / len(avg_gpas) if avg_gpas else None

            # Identify high performers
            high_performers = [
                r for r in progress_records
                if (r["avg_percent"] is not None and r["avg_percent"] >= 85) or
                   (r["gpa"] is not None and r["gpa"] >= 3.5)
            ]

            # Identify students needing support
            support_candidates = [
                r for r in progress_records
                if r["failures"] >= 2 or (r["avg_percent"] is not None and r["avg_percent"] < 60)
            ]

            # Top 5 students
            top_students = sorted(
                progress_records,
                key=lambda r: ((r["avg_percent"] or 0), (r["gpa"] or 0)),
                reverse=True
            )[:5]

            # Priority support list
            support_priority = sorted(
                support_candidates,
                key=lambda r: (-r["failures"], r["avg_percent"] if r["avg_percent"] is not None else 101)
            )[:5]

            # Course summary
            course_summary = {}
            for record in progress_records:
                course = record["course"]
                summary = course_summary.setdefault(course, {"count": 0, "scores": [], "fails": 0})
                summary["count"] += 1
                if record["avg_percent"] is not None:
                    summary["scores"].append(record["avg_percent"])
                summary["fails"] += record["failures"]

            # Top 5 courses
            course_lines = []
            for course, data in sorted(
                course_summary.items(),
                key=lambda item: (
                    (sum(item[1]["scores"]) / len(item[1]["scores"])) if item[1]["scores"] else 0
                ),
                reverse=True
            )[:5]:
                avg_course_score = (sum(data["scores"]) / len(data["scores"])) if data["scores"] else None
                course_lines.append(
                    f"{course}: {data['count']} students, "
                    f"Avg Score: {avg_course_score:.1f}%"
                    if avg_course_score is not None else
                    f"{course}: {data['count']} students, Avg Score: N/A"
                )

            # Build report sections
            summary_lines = [
                f"Total Students: {total_students}",
                f"Students With Recorded Grades: {graded_students}",
                f"Students With Limited Activity (<3 assessments): {low_participation}",
                f"Average Assessment Score: {overall_avg:.1f}%"
                if overall_avg is not None else "Average Assessment Score: N/A",
                f"Average GPA: {overall_gpa:.2f}" if overall_gpa is not None else "Average GPA: N/A",
                f"High-Performing Students (≥85% or GPA ≥3.5): {len(high_performers)}",
                f"Students Requiring Support: {len(support_candidates)}"
            ]

            top_lines = [
                f"{idx + 1}. {record['name']} ({record['course']}) - "
                f"Avg Score: {record['avg_percent']:.1f}%"
                if record["avg_percent"] is not None else
                f"{idx + 1}. {record['name']} ({record['course']}) - Avg Score: N/A"
                for idx, record in enumerate(top_students)
            ]

            # Add GPA to top students
            if top_lines:
                for idx, record in enumerate(top_students):
                    if record["gpa"] is not None:
                        top_lines[idx] += f", GPA: {record['gpa']:.2f}"
                    else:
                        top_lines[idx] += ", GPA: N/A"

            support_lines = [
                f"{idx + 1}. {record['name']} ({record['course']}) - "
                f"Fails: {record['failures']}, "
                f"Avg Score: {record['avg_percent']:.1f}%"
                if record["avg_percent"] is not None else
                f"{idx + 1}. {record['name']} ({record['course']}) - Fails: {record['failures']}, Avg Score: N/A"
                for idx, record in enumerate(support_priority)
            ]

            sections = [
                ("Progress Overview", summary_lines),
                ("Top Performing Students", top_lines),
                ("Courses Snapshot", course_lines),
                ("Support Priorities", support_lines)
            ]

            footer = (
                "Tip: Track students appearing in Support Priorities for targeted interventions "
                "and encourage low-activity students to engage with upcoming assessments."
            )

            self._display_report("Student Progress Report", sections, footer)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate student progress report: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate student progress report: {e}")
        finally:
            if conn:
                conn.close()

    def generate_competency_profile(self):
        """Generate competency profile based on assessment types"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name AS name,
                    a.assessment_type,
                    AVG(g.score / a.max_points * 100) AS avg_performance
                FROM students s
                JOIN grades g ON s.student_id = g.student_id
                JOIN assessments a ON g.assessment_id = a.assessment_id
                GROUP BY s.student_id, s.first_name, s.last_name, a.assessment_type
                ORDER BY s.student_id, a.assessment_type
            """)

            profiles = cursor.fetchall()

            if not profiles:
                messagebox.showinfo("Competency Profiles", "No data available for competency analysis.")
                return

            # Group by student
            student_profiles = {}
            for student_id, name, assessment_type, avg in profiles:
                if student_id not in student_profiles:
                    student_profiles[student_id] = (name, [])
                student_profiles[student_id][1].append(f"{assessment_type}: {avg:.1f}%")

            profile_lines = [
                f"{name} ({student_id})\n" + "\n".join(f"  • {comp}" for comp in competencies)
                for student_id, (name, competencies) in student_profiles.items()
            ]

            sections = [
                ("Competency Profiles by Assessment Type", profile_lines)
            ]

            self._display_report("Student Competency Profiles", sections)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate competency profiles: {e}")
        finally:
            if conn:
                conn.close()

    def generate_at_risk_report(self):
        """Generate comprehensive at-risk student report"""
        # Leverage identify_at_risk_students logic
        self.identify_at_risk_students()

    def generate_module_grade_report(self):
        """Generate grade report for a specific module"""
        self.analyze_module_performance()

    def generate_module_outcome_report(self):
        """Generate learning outcome report for modules"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    m.module_code,
                    m.module_name,
                    COUNT(DISTINCT sm.student_id) AS enrolled_students,
                    COUNT(DISTINCT g.student_id) AS active_students,
                    AVG(g.score / a.max_points * 100) AS avg_outcome
                FROM modules m
                LEFT JOIN student_modules sm ON m.module_code = sm.module_code
                LEFT JOIN assessments a ON m.module_code = a.module_code
                LEFT JOIN grades g ON a.assessment_id = g.assessment_id
                GROUP BY m.module_code, m.module_name
                ORDER BY m.module_code
            """)

            modules = cursor.fetchall()

            outcome_lines = [
                f"{code} - {name}\n"
                f"  Enrolled: {enrolled} | Active: {active} | Avg Outcome: {avg:.1f}%" if avg else
                f"{code} - {name}\n  Enrolled: {enrolled} | Active: {active} | Avg Outcome: N/A"
                for code, name, enrolled, active, avg in modules
            ]

            sections = [
                ("Module Learning Outcomes", outcome_lines)
            ]

            self._display_report("Module Outcome Report", sections)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate outcome report: {e}")
        finally:
            if conn:
                conn.close()

    def generate_assessment_analysis(self):
        """Generate comprehensive assessment analysis report"""
        # This method already exists in assessment_manager - delegate or implement simplified version
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    a.assessment_name,
                    a.assessment_type,
                    m.module_name,
                    COUNT(g.grade_id) AS submissions,
                    AVG(g.score / a.max_points * 100) AS avg_percentage
                FROM assessments a
                LEFT JOIN modules m ON a.module_code = m.module_code
                LEFT JOIN grades g ON a.assessment_id = g.assessment_id
                GROUP BY a.assessment_id, a.assessment_name, a.assessment_type, m.module_name
                ORDER BY m.module_name, a.assessment_name
            """)

            assessments = cursor.fetchall()

            assessment_lines = [
                f"{name} ({atype}) - {module}\n"
                f"  Submissions: {submissions} | Avg: {avg:.1f}%" if avg else
                f"{name} ({atype}) - {module}\n  Submissions: {submissions} | Avg: N/A"
                for name, atype, module, submissions, avg in assessments
            ]

            sections = [
                ("Assessment Analysis", assessment_lines)
            ]

            self._display_report("Assessment Analysis Report", sections)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate assessment analysis: {e}")
        finally:
            if conn:
                conn.close()

    def generate_institution_summary(self):
        """Generate institution-wide summary report"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Overall stats
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT student_id) AS total_students,
                    COUNT(DISTINCT CASE WHEN status = 'Active' THEN student_id END) AS active_students
                FROM students
            """)
            student_stats = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM modules")
            total_modules = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM assessments")
            total_assessments = cursor.fetchone()[0]

            cursor.execute("""
                SELECT AVG(score / max_points * 100)
                FROM grades g
                JOIN assessments a ON g.assessment_id = a.assessment_id
            """)
            overall_avg = cursor.fetchone()[0]

            sections = [
                ("Institution Summary", [
                    f"Total Students: {student_stats[0]}",
                    f"Active Students: {student_stats[1]}",
                    f"Total Modules: {total_modules}",
                    f"Total Assessments: {total_assessments}",
                    f"Overall Average Performance: {overall_avg:.1f}%" if overall_avg else "Overall Average Performance: N/A"
                ])
            ]

            self._display_report("Institution Summary Report", sections)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate summary: {e}")
        finally:
            if conn:
                conn.close()

    def generate_performance_analytics(self):
        """Generate detailed performance analytics"""
        self.generate_performance_dashboard()

    def generate_trend_analysis_report(self):
        """Generate trend analysis report"""
        self.analyze_performance_trends()

    def generate_comprehensive_risk_report(self):
        """Generate comprehensive risk analysis report"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Combine multiple risk analyses
            cursor.execute("""
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name AS name,
                    AVG(g.score / a.max_points * 100) AS avg_percentage,
                    COUNT(g.grade_id) AS total_grades,
                    SUM(CASE WHEN g.letter_grade = 'F' THEN 1 ELSE 0 END) AS failures
                FROM students s
                LEFT JOIN grades g ON s.student_id = g.student_id
                LEFT JOIN assessments a ON g.assessment_id = a.assessment_id
                WHERE s.status = 'Active'
                GROUP BY s.student_id, s.first_name, s.last_name
            """)

            students = cursor.fetchall()
            risk_summary = {
                'critical': [],
                'high': [],
                'medium': [],
                'low': []
            }

            for student_id, name, avg, total, failures in students:
                risk_score = 0
                if avg and avg < 50:
                    risk_score = 90
                elif avg and avg < 60:
                    risk_score = 60
                elif avg and avg < 70:
                    risk_score = 40

                if failures >= 3:
                    risk_score += 30
                elif failures >= 1:
                    risk_score += 15

                if total < 3:
                    risk_score += 20

                if risk_score >= 70:
                    risk_summary['critical'].append((student_id, name, risk_score))
                elif risk_score >= 50:
                    risk_summary['high'].append((student_id, name, risk_score))
                elif risk_score >= 30:
                    risk_summary['medium'].append((student_id, name, risk_score))
                else:
                    risk_summary['low'].append((student_id, name, risk_score))

            sections = [
                ("Risk Summary", [
                    f"Critical Risk: {len(risk_summary['critical'])} students",
                    f"High Risk: {len(risk_summary['high'])} students",
                    f"Medium Risk: {len(risk_summary['medium'])} students",
                    f"Low Risk: {len(risk_summary['low'])} students"
                ]),
                ("Critical Risk Students", [f"• {name} ({sid}) - Score: {score}"
                                           for sid, name, score in risk_summary['critical']]
                 if risk_summary['critical'] else ["None"]),
                ("High Risk Students", [f"• {name} ({sid}) - Score: {score}"
                                        for sid, name, score in risk_summary['high']]
                 if risk_summary['high'] else ["None"])
            ]

            self._display_report("Comprehensive Risk Report", sections,
                               "Immediate action required for critical and high-risk students.")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate risk report: {e}")
        finally:
            if conn:
                conn.close()
