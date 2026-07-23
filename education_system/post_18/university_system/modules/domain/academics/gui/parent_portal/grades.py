from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.post_18.university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.post_18.university_system.modules.domain.academics.gui.parent_portal.base import ParentPortalGUI

def view_child_grades(self, child):
    """View grades for a specific child"""
    self.clear_content()
    self.update_status(f"Viewing grades for {child[1]} {child[3]}")

    title = ttk.Label(self.content_frame, text=f"Grades for {child[1]} {child[3]}",
                     style='Title.TLabel', font=('Arial', 18, 'bold'))
    title.pack(pady=20)

    # Create grades table
    grades_frame = ttk.Frame(self.content_frame)
    grades_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    # Table headers
    columns = ('Module', 'Assessment', 'Grade', 'Date', 'Comments')
    tree = ttk.Treeview(grades_frame, columns=columns, show='headings', height=15)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150)

    # Load real grades data from database
    student_id = child[0]  # Get student ID from child tuple
    try:
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()
            # First try to get assignment submission grades (grades stored in assignment_submissions table)
            cursor.execute("""
                SELECT COALESCE(m.module_code, m.module_id, 'N/A') as module,
                       COALESCE(a.title, 'Assignment') as assignment,
                       s.grade,
                       s.submission_date,
                       COALESCE(s.feedback, '')
                FROM assignment_submissions s
                LEFT JOIN assignments a ON s.assignment_id = a.id
                LEFT JOIN modules m ON a.module_code = m.module_code OR a.module_code = m.module_id
                WHERE s.student_id = ? AND s.grade IS NOT NULL
                ORDER BY s.submission_date DESC LIMIT 10
            """, (student_id,))
            grades = cursor.fetchall()

            # If no assignment grades, try getting grades from the grades table
            if not grades:
                cursor.execute("""
                    SELECT COALESCE(m.module_code, m.module_id, 'N/A') as module_code,
                           COALESCE(a.assessment_name, 'Assessment') as assignment_name,
                           COALESCE(g.letter_grade, CAST(g.score AS TEXT)) as grade,
                           g.submission_date as date_recorded,
                           COALESCE(g.comments, '')
                    FROM grades g
                    LEFT JOIN assessments a ON g.assessment_id = a.assessment_id
                    LEFT JOIN modules m ON a.module_code = m.module_code OR a.module_code = m.module_id
                    WHERE g.student_id = ?
                    ORDER BY g.submission_date DESC LIMIT 10
                """, (student_id,))
                grades = cursor.fetchall()

            # If still no grades, check for any student record to show they exist
            if not grades:
                cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
                if cursor.fetchone():
                    tree.insert('', tk.END, values=('N/A', 'No grades available yet', '', '', 'Grades will appear here once assignments are graded'))
                else:
                    tree.insert('', tk.END, values=('ERROR', 'Student not found in database', '', '', ''))
            else:
                for grade in grades:
                    tree.insert('', tk.END, values=grade)

    except Exception as e:
        tree.insert('', tk.END, values=('ERROR', f'Database error: {str(e)}', '', '', 'Unable to load grades'))

    # Scrollbar
    scrollbar = ttk.Scrollbar(grades_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Button frame for actions
    btn_frame = ttk.Frame(self.content_frame)
    btn_frame.pack(pady=10)

    # Link to Grade Tracking GUI for detailed view
    def open_grade_tracking():
        try:
            from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking_management_gui import GradeTrackingManagementGUI
            grade_gui = GradeTrackingManagementGUI(self.root, self.auth)
            grade_gui.show_grade_tracking_gui()
        except ImportError as e:
            messagebox.showinfo("Info", f"Grade Tracking GUI not available: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Grade Tracking: {e}")

    ttk.Button(btn_frame, text="📊 Open Full Grade Tracking", command=open_grade_tracking).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="← Back", command=self.show_children).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.view_child_grades = view_child_grades

def view_teacher_reports(self, child):
    """View teacher reports for a specific child"""
    self.clear_content()
    self.update_status(f"Viewing reports for {child[1]} {child[3]}")

    title = ttk.Label(self.content_frame, text=f"Instructor Reports for {child[1]} {child[3]}",
                     style='Title.TLabel', font=('Arial', 18, 'bold'))
    title.pack(pady=20)

    # Reports list
    reports_frame = ttk.Frame(self.content_frame)
    reports_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    # Left side - report list
    list_frame = ttk.LabelFrame(reports_frame, text="Available Reports", padding=10)
    list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

    reports_listbox = tk.Listbox(list_frame, width=40, height=15)
    reports_listbox.pack(fill=tk.BOTH, expand=True)

    # Load reports from database
    student_id = child[0]
    reports_data = []

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Load teacher reports from database
        cursor.execute("""
            SELECT tr.id, tr.created_date, tr.module_code, tr.report_type, tr.report_content,
                   COALESCE(i.first_name || ' ' || i.last_name, 'Unknown Instructor') as instructor_name
            FROM teacher_reports tr
            LEFT JOIN instructors i ON tr.teacher_id = i.id
            WHERE tr.student_id = ?
            ORDER BY tr.created_date DESC
            LIMIT 50
        """, (student_id,))

        reports = cursor.fetchall()
        conn.close()

        if reports:
            for report in reports:
                report_id, date, module, report_type, content, teacher = report
                display_text = f"{date or 'N/A'} - {module or 'General'} - {report_type or 'Report'}"
                reports_listbox.insert(tk.END, display_text)
                reports_data.append({
                    'id': report_id,
                    'date': date,
                    'module': module,
                    'type': report_type,
                    'content': content,
                    'teacher': teacher
                })
        else:
            reports_listbox.insert(tk.END, "No reports available")

    except Exception as e:
        reports_listbox.insert(tk.END, f"Error loading reports: {str(e)}")

    # Right side - report content
    content_frame = ttk.LabelFrame(reports_frame, text="Report Content", padding=10)
    content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    report_text = scrolledtext.ScrolledText(content_frame, width=50, height=15)
    report_text.pack(fill=tk.BOTH, expand=True)

    def show_report(event):
        selection = reports_listbox.curselection()
        if selection and reports_data:
            idx = selection[0]
            if idx < len(reports_data):
                report = reports_data[idx]
                report_text.delete(1.0, tk.END)
                report_text.insert(tk.END, f"Date: {report['date'] or 'N/A'}\n")
                report_text.insert(tk.END, f"Module: {report['module'] or 'General'}\n")
                report_text.insert(tk.END, f"Type: {report['type'] or 'Report'}\n")
                report_text.insert(tk.END, f"Instructor: {report['teacher']}\n")
                report_text.insert(tk.END, "-" * 40 + "\n\n")
                report_text.insert(tk.END, report['content'] or "No content available.")

    reports_listbox.bind('<<ListboxSelect>>', show_report)

    # Back button
    back_btn = ttk.Button(self.content_frame, text="← Back", command=self.show_children)
    back_btn.pack(pady=10)
ParentPortalGUI.view_teacher_reports = view_teacher_reports

def _get_student_instructors(self, student_id):
    """Get instructors for a student based on their enrolled courses"""
    instructors = []
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        cursor = conn.cursor()

        # Get instructors from student's enrolled courses
        cursor.execute('''
            SELECT DISTINCT i.id, i.first_name, i.last_name, i.email, i.department,
                   COALESCE(c.course_code, m.module_code, 'N/A') as course
            FROM instructors i
            LEFT JOIN courses c ON c.instructor_id = i.id
            LEFT JOIN modules m ON m.instructor_id = i.id
            LEFT JOIN enrollments e ON (e.course_id = c.id OR e.module_id = m.id)
            WHERE e.student_id = ? AND i.is_active = 1 AND i.email IS NOT NULL
            ORDER BY i.last_name, i.first_name
        ''', (student_id,))
        instructors = cursor.fetchall()

        # If no instructors found via enrollments, get all active instructors
        if not instructors:
            cursor.execute('''
                SELECT id, first_name, last_name, email, department, 'General' as course
                FROM instructors
                WHERE (is_active = 1 OR is_active IS NULL) AND email IS NOT NULL AND email != ''
                ORDER BY last_name, first_name
                LIMIT 50
            ''')
            instructors = cursor.fetchall()

        # Final fallback - get any instructors regardless of status
        if not instructors:
            cursor.execute('''
                SELECT id, first_name, last_name, email, COALESCE(department, ''), 'General' as course
                FROM instructors
                WHERE email IS NOT NULL AND email != ''
                ORDER BY last_name, first_name
                LIMIT 50
            ''')
            instructors = cursor.fetchall()

        conn.close()
    except Exception as e:
        print(f"Error loading instructors: {e}")
    return instructors
ParentPortalGUI._get_student_instructors = _get_student_instructors

def show_grades_interface(self):
    """Show grades interface"""
    self.clear_content()
    self.update_status("Grades Interface")

    title = ttk.Label(self.content_frame, text="Grade Management", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Child selection
    if self.children:
        child_var = tk.StringVar()
        child_frame = ttk.LabelFrame(self.content_frame, text="Select Student", padding=10)
        child_frame.pack(fill=tk.X, padx=20, pady=10)

        child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=50)
        child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
        child_combo.pack(pady=5)
        child_combo.set(child_combo['values'][0] if child_combo['values'] else "")

        def view_selected_grades():
            if child_var.get():
                selected_index = child_combo.current()
                if selected_index >= 0:
                    self.view_child_grades(self.children[selected_index])

        view_btn = ttk.Button(child_frame, text="View Grades", command=view_selected_grades)
        view_btn.pack(pady=5)
    else:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
ParentPortalGUI.show_grades_interface = show_grades_interface

def show_reports_interface(self):
    """Show reports interface"""
    self.clear_content()
    self.update_status("Instructor Reports")

    title = ttk.Label(self.content_frame, text="Instructor Reports", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if self.children:
        for child in self.children:
            child_frame = ttk.LabelFrame(self.content_frame, text=f"{child[1]} {child[3]}", padding=15)
            child_frame.pack(fill=tk.X, padx=20, pady=10)

            info_label = ttk.Label(child_frame, text=f"Student ID: {child[0]} | Course: {child[4]}")
            info_label.pack()

            view_btn = ttk.Button(child_frame, text="View Reports",
                                 command=lambda c=child: self.view_teacher_reports(c))
            view_btn.pack(pady=5)
    else:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
ParentPortalGUI.show_reports_interface = show_reports_interface

def show_analytics_interface(self):
    """Show analytics interface"""
    self.clear_content()
    self.update_status("Grade Analytics")

    title = ttk.Label(self.content_frame, text="Grade Analytics", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Analytics notebook
    analytics_notebook = ttk.Notebook(self.content_frame)
    analytics_notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Performance Overview Tab
    overview_frame = ttk.Frame(analytics_notebook, padding=10)
    analytics_notebook.add(overview_frame, text="Performance Overview")

    # Grade Distribution Tab
    distribution_frame = ttk.Frame(analytics_notebook, padding=10)
    analytics_notebook.add(distribution_frame, text="Grade Distribution")

    # Trends Tab
    trends_frame = ttk.Frame(analytics_notebook, padding=10)
    analytics_notebook.add(trends_frame, text="Trends")

    def load_analytics():
        selected_child = child_var.get()
        if not selected_child:
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Load grades - first try assignment_submissions, then grades table
            cursor.execute("""
            SELECT COALESCE(m.module_name, a.title, 'Assignment'),
                   COALESCE(s.grade, 0),
                   COALESCE(s.submission_date, '')
            FROM assignment_submissions s
            LEFT JOIN assignments a ON s.assignment_id = a.id
            LEFT JOIN modules m ON a.module_code = m.module_code OR a.module_code = m.module_id
            WHERE s.student_id = ? AND s.grade IS NOT NULL
            ORDER BY s.submission_date DESC
            LIMIT 20
            """, (student_id,))
            grades = cursor.fetchall()

            # Fallback to grades table if no assignment submissions
            if not grades:
                cursor.execute("""
                SELECT COALESCE(m.module_name, a.assessment_name, 'Unknown'),
                       COALESCE(g.score, 0),
                       COALESCE(g.submission_date, '')
                FROM grades g
                LEFT JOIN assessments a ON g.assessment_id = a.assessment_id
                LEFT JOIN modules m ON a.module_code = m.module_code OR a.module_code = m.module_id
                WHERE g.student_id = ?
                ORDER BY g.submission_date DESC
                LIMIT 20
                """, (student_id,))
                grades = cursor.fetchall()

            # Performance Overview
            for widget in overview_frame.winfo_children():
                widget.destroy()

            # Initialize grade_values at the beginning to avoid scope issues
            grade_values = []

            if grades:
                # Calculate statistics
                for g in grades:
                    try:
                        grade_values.append(float(g[1]))
                    except (ValueError, TypeError):
                        pass

                if grade_values:
                    avg_grade = sum(grade_values) / len(grade_values)
                    max_grade = max(grade_values)
                    min_grade = min(grade_values)

                    stats_frame = ttk.LabelFrame(overview_frame, text="Statistics", padding=15)
                    stats_frame.pack(fill=tk.X, pady=10)

                    ttk.Label(stats_frame, text=f"Average Grade: {avg_grade:.2f}%",
                             font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)
                    ttk.Label(stats_frame, text=f"Highest Grade: {max_grade:.2f}%",
                             font=('Arial', 11)).pack(anchor='w', pady=3)
                    ttk.Label(stats_frame, text=f"Lowest Grade: {min_grade:.2f}%",
                             font=('Arial', 11)).pack(anchor='w', pady=3)
                    ttk.Label(stats_frame, text=f"Total Grades: {len(grades)}",
                             font=('Arial', 11)).pack(anchor='w', pady=3)

                # Recent grades list
                recent_frame = ttk.LabelFrame(overview_frame, text="Recent Grades", padding=10)
                recent_frame.pack(fill=tk.BOTH, expand=True, pady=10)

                columns = ("Subject", "Grade", "Date")
                grades_tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=8)

                for col in columns:
                    grades_tree.heading(col, text=col)
                    grades_tree.column(col, width=150)

                for grade in grades[:10]:
                    grades_tree.insert('', tk.END, values=grade)

                grades_tree.pack(fill=tk.BOTH, expand=True)
            else:
                ttk.Label(overview_frame, text="No grades found for this student",
                         font=('Arial', 11)).pack(pady=50)

            # Grade Distribution
            for widget in distribution_frame.winfo_children():
                widget.destroy()

            if grade_values:
                dist_frame = ttk.LabelFrame(distribution_frame, text="Grade Distribution", padding=15)
                dist_frame.pack(fill=tk.BOTH, expand=True, pady=10)

                # Calculate distribution
                ranges = {"A (90-100)": 0, "B (80-89)": 0, "C (70-79)": 0, "D (60-69)": 0, "F (0-59)": 0}
                for gv in grade_values:
                    if gv >= 90:
                        ranges["A (90-100)"] += 1
                    elif gv >= 80:
                        ranges["B (80-89)"] += 1
                    elif gv >= 70:
                        ranges["C (70-79)"] += 1
                    elif gv >= 60:
                        ranges["D (60-69)"] += 1
                    else:
                        ranges["F (0-59)"] += 1

                # Display distribution
                for grade_range, count in ranges.items():
                    percentage = (count / len(grade_values)) * 100 if grade_values else 0
                    ttk.Label(dist_frame, text=f"{grade_range}: {count} ({percentage:.1f}%)",
                             font=('Arial', 11)).pack(anchor='w', pady=3)
            else:
                ttk.Label(distribution_frame, text="No grade data available",
                         font=('Arial', 11)).pack(pady=50)

            # Trends
            for widget in trends_frame.winfo_children():
                widget.destroy()

            if len(grade_values) >= 2:
                trends_label_frame = ttk.LabelFrame(trends_frame, text="Performance Trends", padding=15)
                trends_label_frame.pack(fill=tk.X, pady=10)

                # Simple trend analysis
                recent_avg = sum(grade_values[:5]) / min(5, len(grade_values))
                overall_avg = sum(grade_values) / len(grade_values)
                trend = "improving" if recent_avg > overall_avg else "declining" if recent_avg < overall_avg else "stable"

                ttk.Label(trends_label_frame, text=f"Overall Trend: {trend.upper()}",
                         font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)
                ttk.Label(trends_label_frame, text=f"Recent Average (last 5): {recent_avg:.2f}%",
                         font=('Arial', 11)).pack(anchor='w', pady=3)
                ttk.Label(trends_label_frame, text=f"Overall Average: {overall_avg:.2f}%",
                         font=('Arial', 11)).pack(anchor='w', pady=3)
            else:
                ttk.Label(trends_frame, text="Not enough data for trend analysis",
                         font=('Arial', 11)).pack(pady=50)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load analytics: {str(e)}")

    ttk.Button(child_frame, text="Load Analytics", command=load_analytics).pack(side=tk.LEFT, padx=5)

    # Load initial analytics
    load_analytics()
ParentPortalGUI.show_analytics_interface = show_analytics_interface
