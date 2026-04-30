# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.constants import paths

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this GUI. Many database calls within this
# module reference 'courses.db' or str(DEFAULT_DB_PATH) directly. Without
# overriding, these calls would create separate database files in the
# working directory, leading to inconsistencies and missing tables. By
# redirecting those names to the central student_records.db located in
# university_system/data/db_files, we ensure a single database file is
# used across the entire application. Only connections specifying no
# database or targeting courses.db/student_records.db are redirected;
# all other database paths are left untouched.

_original_sqlite_connect = sqlite3.connect

def _patched_sqlite_connect(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "courses.db"):
            return _original_sqlite_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect
import re
import csv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading
import os
import logging

# Import chart generation utility
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import seaborn as sns
    import numpy as np
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    plt = None
    Figure = None
    FigureCanvasTkAgg = None
    sns = None
    np = None

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from education_system.university_system.modules.domain.academics.services.course_management import (
        add_prerequisite, create_course, create_enhanced_course,
        display_enhanced_course_menu, find_alternative_courses,
        generate_course_analytics, generate_enrollment_report,
        initialize_enhanced_database, remove_prerequisite, search_courses,
        update_course, update_schedule, view_all_courses, view_course_details
    )
    ORIGINAL_MODULE_AVAILABLE = True
except ImportError:
    ORIGINAL_MODULE_AVAILABLE = False
    print(_("course_management.warnings.original_module_not_found"))

# Import academic system launchers
try:
    from education_system.university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def create_analytics_tab(self):
    """Create the analytics tab with role-based access"""
    analytics_frame = ttk.Frame(self.notebook)
    self.analytics_frame = analytics_frame
    self.notebook.add(analytics_frame, text=_("course_management.tabs.analytics"))

    is_admin = self.is_admin()
    is_staff = self.is_staff()

    # Analytics controls - Admin and Staff only
    if is_admin or is_staff:
        controls_frame = ttk.LabelFrame(analytics_frame, text=_("course_management.labels.analytics_controls"), padding=10)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(controls_frame, text=_("course_management.buttons.generate_course_analytics"), command=self.generate_analytics).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_("course_management.buttons.enrollment_report"), command=self.show_enrollment_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_("course_management.buttons.department_stats"), command=self.show_department_stats).pack(side=tk.LEFT, padx=5)

    # Analytics display
    self.analytics_text = ScrolledText(analytics_frame, wrap=tk.WORD, height=25)
    self.analytics_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


def generate_analytics(self):
    """Generate and display course analytics"""
    try:
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            analytics_text = "COURSE ANALYTICS DASHBOARD\n"
            analytics_text += "=" * 50 + "\n\n"

            # Get total enrolled from student_modules
            cursor.execute("SELECT COUNT(*) FROM student_modules WHERE status = 'Enrolled'")
            total_enrolled = cursor.fetchone()[0] or 0

            # Overall statistics
            cursor.execute("""
            SELECT
                COUNT(*) as total_courses,
                SUM(COALESCE(max_enrollment, 0)) as total_capacity
            FROM courses
            WHERE COALESCE(course_code, code) IS NOT NULL
              AND COALESCE(course_name, name) IS NOT NULL
              AND LOWER(COALESCE(status, 'active')) = 'active'
            """)

            stats = cursor.fetchone()
            if stats:
                total_courses = stats[0] or 0
                total_capacity = stats[1] or 0
                avg_enrollment = total_enrolled / max(total_courses, 1)
                analytics_text += "OVERALL STATISTICS:\n"
                analytics_text += f"Total Active Courses: {total_courses}\n"
                analytics_text += f"Total Students Enrolled: {total_enrolled}\n"
                analytics_text += f"Total System Capacity: {total_capacity}\n"
                analytics_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                if total_capacity > 0:
                    fill_rate = (total_enrolled / total_capacity) * 100
                    analytics_text += f"System Fill Rate: {fill_rate:.1f}%\n"
                analytics_text += f"Available Spots: {total_capacity - total_enrolled}\n\n"

            # Department breakdown
            cursor.execute("""
            SELECT
                COALESCE(c.department, 'Unknown') as dept,
                COUNT(DISTINCT c.id) as course_count,
                COUNT(DISTINCT sm.student_id) as total_students
            FROM courses c
            LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
            WHERE COALESCE(c.course_code, c.code) IS NOT NULL
              AND COALESCE(c.course_name, c.name) IS NOT NULL
              AND LOWER(COALESCE(c.status, 'active')) = 'active'
            GROUP BY c.department
            ORDER BY total_students DESC
            """)

            dept_stats = cursor.fetchall()
            if dept_stats:
                analytics_text += "COURSES BY DEPARTMENT:\n"
                analytics_text += f"{'Department':<20} {'Courses':<10} {'Students':<10}\n"
                analytics_text += "-" * 40 + "\n"
                for dept, courses, students in dept_stats:
                    analytics_text += f"{dept:<20} {courses:<10} {students:<10}\n"
                analytics_text += "\n"

            # Most popular courses
            cursor.execute("""
            SELECT COALESCE(c.course_code, c.code), COALESCE(c.course_name, c.name),
                   COUNT(sm.student_id) as enrolled
            FROM courses c
            LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
            WHERE COALESCE(c.course_code, c.code) IS NOT NULL
              AND COALESCE(c.course_name, c.name) IS NOT NULL
              AND LOWER(COALESCE(c.status, 'active')) = 'active'
            GROUP BY c.id
            ORDER BY enrolled DESC
            LIMIT 10
            """)

            popular = cursor.fetchall()
            if popular:
                analytics_text += "MOST POPULAR COURSES (Top 10):\n"
                analytics_text += f"{'Code':<10} {'Name':<30} {'Enrolled':<10}\n"
                analytics_text += "-" * 50 + "\n"
                for code, name, enrolled in popular:
                    code = code or "N/A"
                    name = name or "N/A"
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    analytics_text += f"{code:<10} {name_short:<30} {enrolled:<10}\n"
                analytics_text += "\n"

            # Courses with availability
            cursor.execute("""
            SELECT COUNT(*)
            FROM courses
            WHERE COALESCE(course_code, code) IS NOT NULL
              AND COALESCE(course_name, name) IS NOT NULL
              AND LOWER(COALESCE(status, 'active')) = 'active'
              AND COALESCE(max_enrollment, 0) > 0
            """)
            available_count = cursor.fetchone()[0]
            analytics_text += f"COURSE AVAILABILITY:\n"
            analytics_text += f"Courses with Available Spots: {available_count}\n\n"

            # Status breakdown
            cursor.execute("""
            SELECT status, COUNT(*) FROM courses
            WHERE COALESCE(course_code, code) IS NOT NULL
              AND COALESCE(course_name, name) IS NOT NULL
            GROUP BY status
            """)
            status_data = cursor.fetchall()
            if status_data:
                analytics_text += "COURSE STATUS BREAKDOWN:\n"
                for status, count in status_data:
                    analytics_text += f"  {status}: {count}\n"

        # Display in analytics tab
        self.notebook.select(2)  # Analytics tab
        self.analytics_text.delete(1.0, tk.END)
        self.analytics_text.insert(1.0, analytics_text)

        self.update_status("Analytics generated successfully")

    except sqlite3.Error as e:
        messagebox.showerror(_("common.database_error"), f"Failed to generate analytics: {e}")


def show_analytics(self):
    """
    Entry point for the 'Course Analytics' menu item - redirects to detailed analytics.
    """
    # Use the existing detailed analytics function
    self.show_course_analytics_detailed()


def show_course_analytics_detailed(self):
    """Show detailed analytics dialog"""
    CourseAnalyticsDialog(self.root, self.auth)


def show_enrollment_report(self):
    """Show enrollment report dialog"""
    dialog = EnrollmentReportDialog(self.root)
    self.root.wait_window(dialog.dialog)
    if dialog.result:
        # Generate selected report type
        report_type = dialog.result
        self.generate_enrollment_report(report_type)


def generate_enrollment_report(self, report_type):
    """Generate specific enrollment report"""
    try:
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            report_text = f"ENROLLMENT REPORT - {report_type.upper()}\n"
            report_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            report_text += "=" * 60 + "\n\n"

            if report_type == "Summary":
                cursor.execute("SELECT COUNT(*) FROM student_modules WHERE status = 'Enrolled'")
                total_enrolled = cursor.fetchone()[0] or 0
                cursor.execute("""
                SELECT COUNT(*) as total_courses,
                       SUM(COALESCE(max_enrollment, 0)) as total_capacity
                FROM courses
                WHERE COALESCE(course_code, code) IS NOT NULL
                  AND COALESCE(course_name, name) IS NOT NULL
                  AND LOWER(COALESCE(status, 'active')) = 'active'
                """)
                summary = cursor.fetchone()
                total_courses = summary[0] or 0
                total_capacity = summary[1] or 0
                avg_enrollment = total_enrolled / max(total_courses, 1)
                report_text += f"Total Active Courses: {total_courses}\n"
                report_text += f"Total Students Enrolled: {total_enrolled}\n"
                report_text += f"Total System Capacity: {total_capacity}\n"
                report_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                if total_capacity > 0:
                    report_text += f"System Fill Rate: {(total_enrolled/total_capacity*100):.1f}%\n"
                report_text += f"Available Spots: {total_capacity - total_enrolled}\n"

            elif report_type == "Department":
                cursor.execute("""
                SELECT
                    COALESCE(c.department, 'Unknown') as dept,
                    COUNT(DISTINCT c.id) as course_count,
                    COUNT(DISTINCT sm.student_id) as total_students,
                    SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
                FROM courses c
                LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
                WHERE COALESCE(c.course_code, c.code) IS NOT NULL
                  AND COALESCE(c.course_name, c.name) IS NOT NULL
                  AND LOWER(COALESCE(c.status, 'active')) = 'active'
                GROUP BY c.department
                ORDER BY total_students DESC
                """)

                dept_data = cursor.fetchall()
                report_text += f"{'Department':<20} {'Courses':<10} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n"
                report_text += "-" * 60 + "\n"

                for dept, courses, students, capacity in dept_data:
                    fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                    report_text += f"{dept:<20} {courses:<10} {students:<10} {capacity:<10} {fill_rate:<10}\n"

            elif report_type == "Detailed":
                cursor.execute("""
                SELECT COALESCE(c.course_code, c.code), COALESCE(c.course_name, c.name),
                       c.department, c.level,
                       COUNT(sm.student_id) as enrolled, COALESCE(c.max_enrollment, 0) as capacity
                FROM courses c
                LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
                WHERE COALESCE(c.course_code, c.code) IS NOT NULL
                  AND COALESCE(c.course_name, c.name) IS NOT NULL
                  AND LOWER(COALESCE(c.status, 'active')) = 'active'
                GROUP BY c.id
                ORDER BY enrolled DESC
                """)

                course_data = cursor.fetchall()
                report_text += f"{'Code':<8} {'Name':<25} {'Dept':<12} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}\n"
                report_text += "-" * 77 + "\n"

                for code, name, dept, level, enrolled, capacity in course_data:
                    code = code or "N/A"
                    name = name or "N/A"
                    name_short = name[:22] + "..." if len(name) > 25 else name
                    dept_short = dept[:9] + "..." if dept and len(dept) > 12 else dept or "N/A"
                    level_short = level[:9] + "..." if level and len(level) > 12 else level or "N/A"
                    fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "N/A"
                    enrollment_str = f"{enrolled}/{capacity}"

                    report_text += f"{code:<8} {name_short:<25} {dept_short:<12} {level_short:<12} {enrollment_str:<10} {fill_rate:<10}\n"

            elif report_type == "Capacity":
                cursor.execute("""
                SELECT COALESCE(c.course_code, c.code), COALESCE(c.course_name, c.name),
                       c.department,
                       COUNT(sm.student_id) as enrolled,
                       COALESCE(c.max_enrollment, 0) as capacity
                FROM courses c
                LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
                WHERE COALESCE(c.course_code, c.code) IS NOT NULL
                  AND COALESCE(c.course_name, c.name) IS NOT NULL
                  AND LOWER(COALESCE(c.status, 'active')) = 'active'
                GROUP BY c.id
                ORDER BY (COALESCE(c.max_enrollment, 0) - COUNT(sm.student_id)) DESC
                """)

                capacity_data = cursor.fetchall()
                report_text += f"{'Code':<8} {'Name':<30} {'Department':<15} {'Enrolled':<10} {'Capacity':<10} {'Available':<10}\n"
                report_text += "-" * 83 + "\n"

                for code, name, dept, enrolled, capacity in capacity_data:
                    code = code or "N/A"
                    name = name or "N/A"
                    available = capacity - enrolled
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    dept_short = dept[:12] + "..." if dept and len(dept) > 15 else dept or "N/A"
                    report_text += f"{code:<8} {name_short:<30} {dept_short:<15} {enrolled:<10} {capacity:<10} {available:<10}\n"

        # Store report data for visualization and email
        self.last_report_data = {
            'type': report_type,
            'text': report_text,
            'conn': conn
        }

        # Display report in analytics tab
        self.notebook.select(2)  # Analytics tab
        self.analytics_text.delete(1.0, tk.END)
        self.analytics_text.insert(1.0, report_text)

        # Add visualization and email buttons (create if they don't exist)
        if not hasattr(self, 'report_action_frame'):
            self.report_action_frame = ttk.Frame(self.analytics_frame)
            self.report_action_frame.pack(fill=tk.X, pady=5)

            ttk.Button(self.report_action_frame, text="📊 Visualize Report",
                      command=self.visualize_report).pack(side=tk.LEFT, padx=5)
            ttk.Button(self.report_action_frame, text="📧 Email Report to Admin",
                      command=self.email_report).pack(side=tk.LEFT, padx=5)

        self.update_status(f"{report_type} enrollment report generated")

    except sqlite3.Error as e:
        messagebox.showerror(_("common.database_error"), f"Failed to generate report: {e}")


def visualize_report(self):
    """Generate and display visual charts for the current report"""
    if not hasattr(self, 'last_report_data'):
        messagebox.showwarning("No Report", "Please generate a report first.")
        return

    if not CHARTS_AVAILABLE:
        messagebox.showerror("Charts Unavailable",
                           "Chart generation requires matplotlib and seaborn.\n"
                           "Install with: pip install matplotlib seaborn")
        return

    report_type = self.last_report_data['type']

    try:
        # Create chart window
        chart_window = tk.Toplevel(self.root)
        chart_window.title(f"Course Management - {report_type} Report Visualization")
        chart_window.geometry("1200x800")
        chart_window.transient(self.root)

        # Create main frame
        main_frame = ttk.Frame(chart_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"{report_type} Report - Visual Charts",
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Create notebook for multiple charts
        chart_notebook = ttk.Notebook(main_frame)
        chart_notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Fetch data from database
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            if report_type == "Summary":
                self._create_summary_charts(chart_notebook, cursor)
            elif report_type == "Department":
                self._create_department_charts(chart_notebook, cursor)
            elif report_type == "Detailed":
                self._create_detailed_charts(chart_notebook, cursor)
            elif report_type == "Capacity":
                self._create_capacity_charts(chart_notebook, cursor)

        # Close button
        ttk.Button(main_frame, text="Close", command=chart_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror("Visualization Error", f"Failed to create charts: {e}")
        print(_("course_management.errors.chart_generation", error=str(e)))


def _create_summary_charts(self, notebook, cursor):
    """Create summary report charts"""
    cursor.execute("SELECT COUNT(*) FROM student_modules WHERE status = 'Enrolled'")
    total_enrolled = cursor.fetchone()[0] or 0
    cursor.execute("""
    SELECT COUNT(*) as total_courses,
           SUM(COALESCE(max_enrollment, 0)) as total_capacity
    FROM courses
    WHERE COALESCE(course_code, code) IS NOT NULL
      AND COALESCE(course_name, name) IS NOT NULL
      AND LOWER(COALESCE(status, 'active')) = 'active'
    """)
    row = cursor.fetchone()
    summary = (row[0], total_enrolled, row[1] or 0, total_enrolled / max(row[0], 1))

    # Chart 1: Enrollment Overview (Bar Chart)
    frame1 = ttk.Frame(notebook)
    notebook.add(frame1, text="Enrollment Overview")

    fig1 = Figure(figsize=(10, 6), dpi=100)
    ax1 = fig1.add_subplot(111)

    categories = ['Total Courses', 'Total Enrolled', 'Total Capacity', 'Available Spots']
    values = [summary[0], summary[1], summary[2], summary[2] - summary[1]]
    colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']

    ax1.bar(categories, values, color=colors, alpha=0.8)
    ax1.set_ylabel('Count')
    ax1.set_title('Course Enrollment Summary', fontweight='bold', fontsize=14)
    ax1.grid(axis='y', alpha=0.3)

    for i, v in enumerate(values):
        ax1.text(i, v, f'{int(v)}', ha='center', va='bottom', fontweight='bold')

    canvas1 = FigureCanvasTkAgg(fig1, frame1)
    canvas1.draw()
    canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # Chart 2: Fill Rate Pie Chart
    frame2 = ttk.Frame(notebook)
    notebook.add(frame2, text="Capacity Fill Rate")

    fig2 = Figure(figsize=(10, 6), dpi=100)
    ax2 = fig2.add_subplot(111)

    enrolled = summary[1]
    available = summary[2] - summary[1]

    ax2.pie([enrolled, available], labels=['Enrolled', 'Available'],
           autopct='%1.1f%%', startangle=90, colors=['#2ecc71', '#ecf0f1'])
    ax2.set_title(f'System Capacity Utilization\n({enrolled}/{summary[2]} spots filled)',
                 fontweight='bold', fontsize=14)

    canvas2 = FigureCanvasTkAgg(fig2, frame2)
    canvas2.draw()
    canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)


def _create_department_charts(self, notebook, cursor):
    """Create department report charts"""
    cursor.execute("""
    SELECT
        COALESCE(c.department, 'Unknown') as dept,
        COUNT(DISTINCT c.id) as course_count,
        COUNT(DISTINCT sm.student_id) as total_students,
        SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
    FROM courses c
    LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
    WHERE COALESCE(c.course_code, c.code) IS NOT NULL
      AND COALESCE(c.course_name, c.name) IS NOT NULL
      AND LOWER(COALESCE(c.status, 'active')) = 'active'
    GROUP BY c.department
    ORDER BY total_students DESC
    """)
    dept_data = cursor.fetchall()

    # Chart 1: Students by Department (Bar Chart)
    frame1 = ttk.Frame(notebook)
    notebook.add(frame1, text="Students by Department")

    fig1 = Figure(figsize=(12, 6), dpi=100)
    ax1 = fig1.add_subplot(111)

    departments = [row[0] for row in dept_data]
    students = [row[2] for row in dept_data]

    ax1.barh(departments, students, color='#3498db', alpha=0.8)
    ax1.set_xlabel('Number of Students')
    ax1.set_title('Student Enrollment by Department', fontweight='bold', fontsize=14)
    ax1.grid(axis='x', alpha=0.3)

    for i, v in enumerate(students):
        ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

    fig1.tight_layout()
    canvas1 = FigureCanvasTkAgg(fig1, frame1)
    canvas1.draw()
    canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # Chart 2: Course Count by Department (Pie Chart)
    frame2 = ttk.Frame(notebook)
    notebook.add(frame2, text="Courses by Department")

    fig2 = Figure(figsize=(10, 6), dpi=100)
    ax2 = fig2.add_subplot(111)

    course_counts = [row[1] for row in dept_data]

    ax2.pie(course_counts, labels=departments, autopct='%1.1f%%', startangle=90)
    ax2.set_title('Course Distribution by Department', fontweight='bold', fontsize=14)

    canvas2 = FigureCanvasTkAgg(fig2, frame2)
    canvas2.draw()
    canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # Chart 3: Fill Rate by Department
    frame3 = ttk.Frame(notebook)
    notebook.add(frame3, text="Fill Rate by Department")

    fig3 = Figure(figsize=(12, 6), dpi=100)
    ax3 = fig3.add_subplot(111)

    fill_rates = [(row[2] / row[3] * 100) if row[3] > 0 else 0 for row in dept_data]

    ax3.barh(departments, fill_rates, color='#2ecc71', alpha=0.8)
    ax3.set_xlabel('Fill Rate (%)')
    ax3.set_title('Capacity Fill Rate by Department', fontweight='bold', fontsize=14)
    ax3.grid(axis='x', alpha=0.3)

    for i, v in enumerate(fill_rates):
        ax3.text(v, i, f' {v:.1f}%', va='center', fontweight='bold')

    fig3.tight_layout()
    canvas3 = FigureCanvasTkAgg(fig3, frame3)
    canvas3.draw()
    canvas3.get_tk_widget().pack(fill=tk.BOTH, expand=True)


def _create_detailed_charts(self, notebook, cursor):
    """Create detailed report charts"""
    cursor.execute("""
    SELECT COALESCE(c.course_code, c.code), COALESCE(c.course_name, c.name), c.department,
           COUNT(sm.student_id) as enrolled, COALESCE(c.max_enrollment, 0) as capacity
    FROM courses c
    LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
    WHERE COALESCE(c.course_code, c.code) IS NOT NULL
      AND COALESCE(c.course_name, c.name) IS NOT NULL
      AND LOWER(COALESCE(c.status, 'active')) = 'active'
    GROUP BY c.id
    ORDER BY enrolled DESC
    LIMIT 15
    """)
    course_data = cursor.fetchall()

    # Chart 1: Top 15 Courses by Enrollment
    frame1 = ttk.Frame(notebook)
    notebook.add(frame1, text="Top Courses")

    fig1 = Figure(figsize=(12, 8), dpi=100)
    ax1 = fig1.add_subplot(111)

    course_names = [f"{row[0]}\n{row[1][:20]}" for row in course_data]
    enrollments = [row[3] for row in course_data]

    ax1.barh(course_names, enrollments, color='#e74c3c', alpha=0.8)
    ax1.set_xlabel('Enrolled Students')
    ax1.set_title('Top 15 Courses by Enrollment', fontweight='bold', fontsize=14)
    ax1.grid(axis='x', alpha=0.3)

    for i, v in enumerate(enrollments):
        ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

    fig1.tight_layout()
    canvas1 = FigureCanvasTkAgg(fig1, frame1)
    canvas1.draw()
    canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # Chart 2: Enrollment vs Capacity
    frame2 = ttk.Frame(notebook)
    notebook.add(frame2, text="Enrollment vs Capacity")

    fig2 = Figure(figsize=(12, 8), dpi=100)
    ax2 = fig2.add_subplot(111)

    x = np.arange(len(course_data))
    width = 0.35

    enrolled = [row[3] for row in course_data]
    capacity = [row[4] for row in course_data]
    course_codes = [row[0] for row in course_data]

    ax2.bar(x - width/2, enrolled, width, label='Enrolled', color='#3498db', alpha=0.8)
    ax2.bar(x + width/2, capacity, width, label='Capacity', color='#95a5a6', alpha=0.8)

    ax2.set_xlabel('Course Code')
    ax2.set_ylabel('Students')
    ax2.set_title('Enrollment vs Capacity - Top 15 Courses', fontweight='bold', fontsize=14)
    ax2.set_xticks(x)
    ax2.set_xticklabels(course_codes, rotation=45, ha='right')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

    fig2.tight_layout()
    canvas2 = FigureCanvasTkAgg(fig2, frame2)
    canvas2.draw()
    canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)


def _create_capacity_charts(self, notebook, cursor):
    """Create capacity report charts"""
    cursor.execute("""
    SELECT COALESCE(c.course_code, c.code), COALESCE(c.course_name, c.name), c.department,
           COUNT(sm.student_id) as enrolled,
           COALESCE(c.max_enrollment, 0) as capacity,
           (COALESCE(c.max_enrollment, 0) - COUNT(sm.student_id)) as available
    FROM courses c
    LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
    WHERE COALESCE(c.course_code, c.code) IS NOT NULL
      AND COALESCE(c.course_name, c.name) IS NOT NULL
      AND LOWER(COALESCE(c.status, 'active')) = 'active'
    GROUP BY c.id
    ORDER BY available DESC
    LIMIT 15
    """)
    capacity_data = cursor.fetchall()

    # Chart 1: Available Spots by Course
    frame1 = ttk.Frame(notebook)
    notebook.add(frame1, text="Available Spots")

    fig1 = Figure(figsize=(12, 8), dpi=100)
    ax1 = fig1.add_subplot(111)

    course_names = [f"{row[0]}\n{row[1][:20]}" for row in capacity_data]
    available = [row[5] for row in capacity_data]

    ax1.barh(course_names, available, color='#f39c12', alpha=0.8)
    ax1.set_xlabel('Available Spots')
    ax1.set_title('Top 15 Courses by Available Capacity', fontweight='bold', fontsize=14)
    ax1.grid(axis='x', alpha=0.3)

    for i, v in enumerate(available):
        ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

    fig1.tight_layout()
    canvas1 = FigureCanvasTkAgg(fig1, frame1)
    canvas1.draw()
    canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # Chart 2: Capacity Utilization Breakdown
    frame2 = ttk.Frame(notebook)
    notebook.add(frame2, text="Utilization Breakdown")

    fig2 = Figure(figsize=(12, 8), dpi=100)
    ax2 = fig2.add_subplot(111)

    course_codes = [row[0] for row in capacity_data]
    enrolled = [row[3] for row in capacity_data]
    available = [row[5] for row in capacity_data]

    x = np.arange(len(capacity_data))
    ax2.bar(x, enrolled, label='Enrolled', color='#2ecc71', alpha=0.8)
    ax2.bar(x, available, bottom=enrolled, label='Available', color='#ecf0f1', alpha=0.8)

    ax2.set_xlabel('Course Code')
    ax2.set_ylabel('Spots')
    ax2.set_title('Capacity Utilization - Top 15 Courses', fontweight='bold', fontsize=14)
    ax2.set_xticks(x)
    ax2.set_xticklabels(course_codes, rotation=45, ha='right')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

    fig2.tight_layout()
    canvas2 = FigureCanvasTkAgg(fig2, frame2)
    canvas2.draw()
    canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)


def email_report(self):
    """Email the current report to admin"""
    if not hasattr(self, 'last_report_data'):
        messagebox.showwarning("No Report", "Please generate a report first.")
        return

    if not EMAIL_AVAILABLE:
        messagebox.showerror("Email Service Unavailable",
                           "Email service is not configured.\n"
                           "Please set up email settings.")
        return

    # Create email dialog
    email_dialog = tk.Toplevel(self.root)
    email_dialog.title("📧 Email Report to Admin")
    email_dialog.geometry("1000x750")
    email_dialog.transient(self.root)
    email_dialog.grab_set()

    frame = ttk.Frame(email_dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Email Course Management Report",
             font=("Arial", 14, "bold")).pack(pady=(0, 20))

    # Get admin email from database
    try:
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1")
            admin_row = cursor.fetchone()
            default_email = admin_row[0] if admin_row else "admin@university.edu"
    except Exception as e:
        print(_("course_management.warnings.admin_email_fetch_failed", error=str(e)))
        default_email = "admin@university.edu"

    ttk.Label(frame, text="Admin Email Address:").pack(anchor='w', pady=(0, 5))
    email_var = tk.StringVar(value=default_email)

    # Create email input frame with refresh button
    email_frame = ttk.Frame(frame)
    email_frame.pack(fill='x', pady=(0, 10))

    email_entry = ttk.Entry(email_frame, textvariable=email_var, width=40)
    email_entry.pack(side='left', fill='x', expand=True)

    def refresh_admin_email():
        """Refresh admin email from database"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username, email FROM users WHERE LOWER(role) = 'admin' ORDER BY username")
                admins = cursor.fetchall()

            if admins:
                if len(admins) > 1:
                    # Show selection dialog
                    admin_select_dialog = tk.Toplevel(email_dialog)
                    admin_select_dialog.title("Select Admin")
                    admin_select_dialog.geometry("900x700")
                    admin_select_dialog.transient(email_dialog)
                    admin_select_dialog.grab_set()

                    ttk.Label(admin_select_dialog, text="Select Admin User:",
                             font=('Arial', 12, 'bold')).pack(pady=10)

                    admin_listbox = tk.Listbox(admin_select_dialog, height=10)
                    admin_listbox.pack(fill='both', expand=True, padx=20, pady=10)

                    for username, email in admins:
                        admin_listbox.insert(tk.END, f"{username} ({email})")

                    def select_admin():
                        selection = admin_listbox.curselection()
                        if selection:
                            selected_email = admins[selection[0]][1]
                            email_var.set(selected_email)
                        admin_select_dialog.destroy()

                    ttk.Button(admin_select_dialog, text="Select",
                              command=select_admin).pack(pady=10)
                else:
                    email_var.set(admins[0][1])
                    messagebox.showinfo("Admin Email", f"Using admin email: {admins[0][1]}")
            else:
                messagebox.showwarning("No Admins", "No admin users found in database.")
        except Exception as e:
            messagebox.showerror(_("common.database_error"), f"Could not fetch admin emails: {str(e)}")

    ttk.Button(email_frame, text="🔄", command=refresh_admin_email, width=3).pack(side='left', padx=(5, 0))

    ttk.Label(frame, text="Subject:").pack(anchor='w', pady=(10, 5))
    subject_var = tk.StringVar(value=f"Course Management Report - {self.last_report_data['type']}")
    ttk.Entry(frame, textvariable=subject_var, width=60).pack(fill='x', pady=(0, 10))

    ttk.Label(frame, text="Message (optional):").pack(anchor='w', pady=(10, 5))
    message_text = ScrolledText(frame, height=8, wrap=tk.WORD)
    message_text.pack(fill='both', expand=True, pady=(0, 10))
    message_text.insert('1.0', "Please find the course management report below.\n\n"
                               "This report was automatically generated from the Course Management GUI.")

    ttk.Label(frame, text="Report Preview:").pack(anchor='w', pady=(10, 5))
    preview_text = ScrolledText(frame, height=10, wrap=tk.WORD)
    preview_text.pack(fill='both', expand=True, pady=(0, 20))
    preview_text.insert('1.0', self.last_report_data['text'])
    preview_text.config(state='disabled')

    def send_email_report():
        try:
            admin_email = email_var.get().strip()
            subject = subject_var.get().strip()
            message = message_text.get('1.0', tk.END).strip()

            if not admin_email or '@' not in admin_email:
                messagebox.showwarning("Invalid Email", "Please enter a valid admin email address.")
                return

            # Render email from template
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_subject, template_body = render_template('academics/course_management_report', {
                'custom_message': message,
                'separator': '=' * 80,
                'report_content': self.last_report_data['text'],
                'report_type': self.last_report_data['type'],
                'generated_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            # Use template if available, otherwise fallback to hardcoded
            if template_subject and template_body:
                subject = template_subject
                body = template_body
            else:
                # Fallback to hardcoded format
                body = f"""{message}

{'=' * 80}
{self.last_report_data['text']}
{'=' * 80}

Report Type: {self.last_report_data['type']}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This email was sent from the Course Management GUI.
"""

            # Send email
            send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body
            )

            messagebox.showinfo("Email Sent",
                              f"✅ Report sent successfully to {admin_email}\n\n"
                              f"Report Type: {self.last_report_data['type']}")
            email_dialog.destroy()

        except Exception as e:
            messagebox.showerror("Email Error",
                               f"Failed to send email: {str(e)}\n\n"
                               f"Please check email configuration.")
            print(_("course_management.errors.email", error=str(e)))

    # Buttons
    button_frame = ttk.Frame(frame)
    button_frame.pack(fill='x', pady=(10, 0))
    ttk.Button(button_frame, text="📧 Send Email",
              command=send_email_report).pack(side='left', padx=(0, 10))
    ttk.Button(button_frame, text="❌ Cancel",
              command=email_dialog.destroy).pack(side='right')


def show_department_stats(self):
    """Show department statistics dialog with enhanced GUI display"""
    try:
        # Create department stats window
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Department Statistics")
        stats_window.geometry("800x600")
        stats_window.transient(self.root)

        main_frame = ttk.Frame(stats_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Department selection
        selection_frame = ttk.Frame(main_frame)
        selection_frame.pack(fill=tk.X, pady=5)

        ttk.Label(selection_frame, text="Department:").pack(side=tk.LEFT)
        dept_var = tk.StringVar()

        # Get departments list
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT COALESCE(department, 'Unknown') as dept FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "ORDER BY dept"
            )
            departments = ["All Departments"] + [row[0] for row in cursor.fetchall()]

        dept_combo = ttk.Combobox(selection_frame, textvariable=dept_var, values=departments)
        dept_combo.pack(side=tk.LEFT, padx=5)
        dept_combo.set("All Departments")

        # Statistics display
        stats_text = ScrolledText(main_frame, wrap=tk.WORD)
        stats_text.pack(fill=tk.BOTH, expand=True, pady=5)

        def update_stats():
            selected_dept = dept_var.get()
            stats_text.delete(1.0, tk.END)

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                if selected_dept == "All Departments":
                    # All departments overview
                    cursor.execute("""
                    SELECT
                        COALESCE(c.department, 'Unknown') as dept,
                        COUNT(DISTINCT c.id) as course_count,
                        COUNT(DISTINCT sm.student_id) as total_students,
                        SUM(COALESCE(c.max_enrollment, 0)) as total_capacity,
                        COUNT(DISTINCT CASE WHEN LOWER(COALESCE(c.status, 'active')) = 'active' THEN c.id END) as active_courses
                    FROM courses c
                    LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
                    WHERE COALESCE(c.course_code, c.code) IS NOT NULL
                      AND COALESCE(c.course_name, c.name) IS NOT NULL
                    GROUP BY c.department
                    ORDER BY total_students DESC
                    """)

                    all_dept_stats = cursor.fetchall()
                    stats_text.insert(tk.END, "ALL DEPARTMENTS OVERVIEW\n")
                    stats_text.insert(tk.END, "=" * 50 + "\n\n")
                    stats_text.insert(tk.END, f"{'Department':<20} {'Courses':<10} {'Active':<8} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n")
                    stats_text.insert(tk.END, "-" * 68 + "\n")

                    for dept_stat in all_dept_stats:
                        dept, courses, students, capacity, active = dept_stat
                        fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        stats_text.insert(tk.END, f"{dept:<20} {courses:<10} {active:<8} {students:<10} {capacity:<10} {fill_rate:<10}\n")
                else:
                    # Single department stats
                    cursor.execute("""
                    SELECT
                        COUNT(DISTINCT c.id) as total_courses,
                        COUNT(DISTINCT sm.student_id) as total_students,
                        SUM(COALESCE(c.max_enrollment, 0)) as total_capacity,
                        AVG(COALESCE(c.credit_hours, c.credits, 0)) as avg_credits,
                        COUNT(DISTINCT CASE WHEN LOWER(COALESCE(c.status, 'active')) = 'active' THEN c.id END) as active_courses
                    FROM courses c
                    LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
                    WHERE COALESCE(c.course_code, c.code) IS NOT NULL
                      AND COALESCE(c.course_name, c.name) IS NOT NULL
                      AND c.department = ?
                    """, (selected_dept,))

                    stats = cursor.fetchone()
                    total_courses = stats[0] or 0
                    total_students = stats[1] or 0
                    total_capacity = stats[2] or 0
                    avg_credits = stats[3] or 0.0
                    active_courses = stats[4] or 0
                    avg_enrollment = total_students / max(total_courses, 1)

                    stats_text.insert(tk.END, f"STATISTICS FOR {selected_dept.upper()} DEPARTMENT\n")
                    stats_text.insert(tk.END, "=" * 60 + "\n\n")
                    stats_text.insert(tk.END, f"Total Courses: {total_courses}\n")
                    stats_text.insert(tk.END, f"Active Courses: {active_courses}\n")
                    stats_text.insert(tk.END, f"Total Students: {total_students}\n")
                    stats_text.insert(tk.END, f"Total Capacity: {total_capacity}\n")
                    stats_text.insert(tk.END, f"Average Enrollment: {avg_enrollment:.1f}\n")
                    stats_text.insert(tk.END, f"Average Credit Hours: {avg_credits:.1f}\n")
                    if total_capacity > 0:
                        stats_text.insert(tk.END, f"Department Fill Rate: {(total_students/total_capacity*100):.1f}%\n")

        ttk.Button(selection_frame, text="Update", command=update_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(main_frame, text="Close", command=stats_window.destroy).pack(pady=10)

        # Initial load
        update_stats()

    except sqlite3.Error as e:
        messagebox.showerror(_("common.database_error"), f"Failed to load department statistics: {e}")


class CourseAnalyticsDialog:
    """Standalone analytics dialog with charts and detailed statistics"""
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Analytics Dashboard")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)

        self.create_widgets()
        self.dialog.focus_set()

        # Live refresh: when assignment grading or grade tracking writes
        # land, repull the analytics so cohort metrics don't drift from
        # what the gradebook shows.
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                subscribe_tk,
                EVENT_GRADE_CHANGED,
                EVENT_ASSIGNMENT_CHANGED,
                EVENT_ASSESSMENT_CHANGED,
                EVENT_ENROLMENT_CHANGED,
            )

            def _on_external_change(**_payload):
                if hasattr(self, "refresh_all_data"):
                    self.refresh_all_data()

            for evt in (EVENT_GRADE_CHANGED, EVENT_ASSIGNMENT_CHANGED,
                        EVENT_ASSESSMENT_CHANGED, EVENT_ENROLMENT_CHANGED):
                subscribe_tk(evt, self.dialog, _on_external_change)
        except Exception:
            pass

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create notebook for different analytics views
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Overview Tab
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text="Overview")
        self.create_overview_tab(overview_frame)

        # Department Analysis Tab
        dept_frame = ttk.Frame(notebook)
        notebook.add(dept_frame, text="Department Analysis")
        self.create_department_tab(dept_frame)

        # Trends Tab
        trends_frame = ttk.Frame(notebook)
        notebook.add(trends_frame, text="Trends")
        self.create_trends_tab(trends_frame)

        # Controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=10)

        ttk.Button(controls_frame, text="Refresh Data", command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Load initial data
        self.refresh_all_data()

    def create_overview_tab(self, parent):
        # Key metrics frame
        metrics_frame = ttk.LabelFrame(parent, text="Key Metrics", padding=10)
        metrics_frame.pack(fill=tk.X, pady=5)

        # Create metric labels
        self.total_courses_label = ttk.Label(metrics_frame, text="Total Courses: -", font=("Arial", 12, "bold"))
        self.total_courses_label.grid(row=0, column=0, padx=20, pady=5)

        self.total_students_label = ttk.Label(metrics_frame, text="Total Students: -", font=("Arial", 12, "bold"))
        self.total_students_label.grid(row=0, column=1, padx=20, pady=5)

        self.avg_fill_rate_label = ttk.Label(metrics_frame, text="Avg Fill Rate: -", font=("Arial", 12, "bold"))
        self.avg_fill_rate_label.grid(row=0, column=2, padx=20, pady=5)

        self.available_spots_label = ttk.Label(metrics_frame, text="Available Spots: -", font=("Arial", 12, "bold"))
        self.available_spots_label.grid(row=1, column=0, padx=20, pady=5)

        self.active_courses_label = ttk.Label(metrics_frame, text="Active Courses: -", font=("Arial", 12, "bold"))
        self.active_courses_label.grid(row=1, column=1, padx=20, pady=5)

        # Charts frame (simplified text-based charts since GUI doesn't have matplotlib)
        charts_frame = ttk.LabelFrame(parent, text="Status Distribution", padding=10)
        charts_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.status_text = ScrolledText(charts_frame, height=15)
        self.status_text.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(
            button_frame,
            text="Email Overview to Admin",
            command=self.email_overview_report,
        ).pack(side=tk.RIGHT, padx=5)

    def create_department_tab(self, parent):
        # Department selector
        selector_frame = ttk.Frame(parent)
        selector_frame.pack(fill=tk.X, pady=5)

        ttk.Label(selector_frame, text="Department:").pack(side=tk.LEFT)
        self.dept_selector = ttk.Combobox(selector_frame, width=30)
        self.dept_selector.pack(side=tk.LEFT, padx=5)
        self.dept_selector.bind('<<ComboboxSelected>>', self.update_department_data)

        # Department details
        self.dept_details = ScrolledText(parent, height=25)
        self.dept_details.pack(fill=tk.BOTH, expand=True, pady=5)

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(
            button_frame,
            text="Email Department Report to Admin",
            command=self.email_department_report,
        ).pack(side=tk.RIGHT, padx=5)

    def create_trends_tab(self, parent):
        # Trends analysis
        trends_label = ttk.Label(parent, text="Course Trends Analysis", font=("Arial", 14, "bold"))
        trends_label.pack(pady=10)

        self.trends_text = ScrolledText(parent, height=25)
        self.trends_text.pack(fill=tk.BOTH, expand=True, pady=5)

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(
            button_frame,
            text="Email Trends Report to Admin",
            command=self.email_trends_report,
        ).pack(side=tk.RIGHT, padx=5)

    def _get_admin_email(self):
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT email FROM users
                    WHERE LOWER(role) = 'admin'
                      AND email IS NOT NULL
                      AND email != ''
                    LIMIT 1
                """)
                result = cursor.fetchone()
                return result[0] if result else None
        except sqlite3.Error:
            return None

    def _send_report_to_admin(self, report_title, report_body):
        if not EMAIL_AVAILABLE:
            messagebox.showerror("Email Service Unavailable", "Email service is not configured.")
            return

        admin_email = self._get_admin_email()
        if not admin_email:
            admin_email = simpledialog.askstring(
                "Admin Email",
                "Enter admin email address:",
                parent=self.dialog,
            )

        if not admin_email:
            return

        subject = f"Course Analytics - {report_title}"
        body = (
            f"{report_body}\n\n"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        try:
            send_email(admin_email, subject, body)
            messagebox.showinfo("Email Sent", f"Report sent to {admin_email}.")
        except Exception as exc:
            messagebox.showerror("Email Error", f"Failed to send email: {exc}")

    def email_overview_report(self):
        metrics = [
            self.total_courses_label.cget("text"),
            self.total_students_label.cget("text"),
            self.avg_fill_rate_label.cget("text"),
            self.available_spots_label.cget("text"),
            self.active_courses_label.cget("text"),
        ]
        status_text = self.status_text.get(1.0, tk.END).strip()
        report_body = "OVERVIEW REPORT\n" + "=" * 40 + "\n" + "\n".join(metrics) + "\n\n" + status_text
        self._send_report_to_admin("Overview", report_body)

    def email_department_report(self):
        report_body = self.dept_details.get(1.0, tk.END).strip()
        if not report_body:
            messagebox.showwarning("No Report", "Department report is empty.")
            return
        self._send_report_to_admin("Department Analysis", report_body)

    def email_trends_report(self):
        report_body = self.trends_text.get(1.0, tk.END).strip()
        if not report_body:
            messagebox.showwarning("No Report", "Trends report is empty.")
            return
        self._send_report_to_admin("Trends Analysis", report_body)

    def refresh_all_data(self):
        self.load_overview_data()
        self.load_department_selector()
        self.load_trends_data()

    def load_overview_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Get total enrolled from student_modules
            cursor.execute("SELECT COUNT(*) FROM student_modules WHERE status = 'Enrolled'")
            total_students = cursor.fetchone()[0] or 0

            # Get key metrics
            cursor.execute("""
            SELECT
                COUNT(*) as total_courses,
                SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                COUNT(CASE WHEN LOWER(COALESCE(status, 'active')) = 'active' THEN 1 END) as active_courses
            FROM courses
            WHERE COALESCE(course_code, code) IS NOT NULL
            AND COALESCE(course_name, name) IS NOT NULL
            """)

            metrics = cursor.fetchone()
            if metrics:
                total_courses, total_capacity, active_courses = metrics
                total_capacity = total_capacity or 0
                avg_enrollment = total_students / max(total_courses, 1)
                available_spots = total_capacity - total_students if total_capacity else 0
                avg_fill_rate = (total_students / total_capacity * 100) if total_capacity > 0 else 0

                self.total_courses_label.config(text=f"Total Courses: {total_courses}")
                self.total_students_label.config(text=f"Total Students: {total_students or 0}")
                self.avg_fill_rate_label.config(text=f"Avg Fill Rate: {avg_fill_rate:.1f}%")
                self.available_spots_label.config(text=f"Available Spots: {available_spots}")
                self.active_courses_label.config(text=f"Active Courses: {active_courses}")

            # Status distribution
            cursor.execute(
                "SELECT status, COUNT(*) FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "GROUP BY status ORDER BY COUNT(*) DESC"
            )
            status_data = cursor.fetchall()

            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(tk.END, "COURSE STATUS DISTRIBUTION\n")
            self.status_text.insert(tk.END, "=" * 40 + "\n\n")

            for status, count in status_data:
                percentage = (count / total_courses * 100) if total_courses > 0 else 0
                bar = "█" * int(percentage / 5)  # Simple text bar chart
                self.status_text.insert(tk.END, f"{status:<12} {count:<6} {percentage:>6.1f}% {bar}\n")

            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load overview data: {e}")

    def load_department_selector(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute(
                "SELECT DISTINCT COALESCE(department, 'Unknown') as dept FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "ORDER BY dept"
            )
            departments = [row[0] for row in cursor.fetchall()]

            self.dept_selector['values'] = departments
            if departments:
                self.dept_selector.set(departments[0])
                self.update_department_data()

            conn.close()
        except sqlite3.Error:
            pass

    def update_department_data(self, event=None):
        selected_dept = self.dept_selector.get()
        if not selected_dept:
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            self.dept_details.delete(1.0, tk.END)
            self.dept_details.insert(tk.END, f"DEPARTMENT ANALYSIS: {selected_dept.upper()}\n")
            self.dept_details.insert(tk.END, "=" * 50 + "\n\n")

            # Department statistics
            cursor.execute("""
            SELECT
                COUNT(DISTINCT c.id) as total_courses,
                COUNT(DISTINCT sm.student_id) as total_students,
                SUM(COALESCE(c.max_enrollment, 0)) as total_capacity,
                CAST(COUNT(DISTINCT sm.student_id) AS REAL) / MAX(COUNT(DISTINCT c.id), 1) as avg_enrollment,
                AVG(COALESCE(c.credit_hours, c.credits, 0)) as avg_credits,
                COUNT(DISTINCT CASE WHEN LOWER(COALESCE(c.status, 'active')) = 'active' THEN c.id END) as active_courses
            FROM courses c
            LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
            WHERE COALESCE(c.course_code, c.code) IS NOT NULL
              AND COALESCE(c.course_name, c.name) IS NOT NULL
              AND COALESCE(c.department, 'Unknown') = ?
            """, (selected_dept,))

            stats = cursor.fetchone()
            if stats:
                total, students, capacity, avg_enroll, avg_credits, active = stats
                fill_rate = (students / capacity * 100) if capacity > 0 else 0

                self.dept_details.insert(tk.END, f"Total Courses: {total}\n")
                self.dept_details.insert(tk.END, f"Active Courses: {active}\n")
                self.dept_details.insert(tk.END, f"Total Students: {students or 0}\n")
                self.dept_details.insert(tk.END, f"Total Capacity: {capacity or 0}\n")
                self.dept_details.insert(tk.END, f"Fill Rate: {fill_rate:.1f}%\n")
                self.dept_details.insert(tk.END, f"Average Enrollment: {avg_enroll:.1f}\n")
                self.dept_details.insert(tk.END, f"Average Credits: {avg_credits:.1f}\n\n")

            # Top courses in department
            cursor.execute("""
            SELECT COALESCE(c.course_code, c.code), COALESCE(c.course_name, c.name),
                   COUNT(sm.student_id) as enrolled,
                   COALESCE(c.max_enrollment, 0) as capacity
            FROM courses c
            LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
            WHERE COALESCE(c.course_code, c.code) IS NOT NULL
              AND COALESCE(c.course_name, c.name) IS NOT NULL
              AND COALESCE(c.department, 'Unknown') = ?
              AND LOWER(COALESCE(c.status, 'active')) = 'active'
            GROUP BY c.id
            ORDER BY enrolled DESC
            LIMIT 5
            """, (selected_dept,))

            popular_courses = cursor.fetchall()
            self.dept_details.insert(tk.END, "Most Popular Courses:\n")
            for code, name, enrolled, capacity in popular_courses:
                fill_rate = (enrolled / capacity * 100) if capacity > 0 else 0
                self.dept_details.insert(tk.END, f"  {code} - {name}: {enrolled}/{capacity} ({fill_rate:.1f}%)\n")

            self.dept_details.insert(tk.END, "\nCourses with Low Enrollment:\n")
            cursor.execute("""
            SELECT COALESCE(c.course_code, c.code), COALESCE(c.course_name, c.name),
                   COUNT(sm.student_id) as enrolled,
                   COALESCE(c.max_enrollment, 0) as capacity
            FROM courses c
            LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code) AND sm.status = 'Enrolled'
            WHERE COALESCE(c.course_code, c.code) IS NOT NULL
              AND COALESCE(c.course_name, c.name) IS NOT NULL
              AND COALESCE(c.department, 'Unknown') = ?
              AND LOWER(COALESCE(c.status, 'active')) = 'active'
              AND COALESCE(c.max_enrollment, 0) > 0
            GROUP BY c.id
            HAVING COUNT(sm.student_id) < (COALESCE(c.max_enrollment, 0) * 0.3)
            ORDER BY enrolled ASC
            LIMIT 5
            """, (selected_dept,))

            low_enrollment = cursor.fetchall()
            for code, name, enrolled, capacity in low_enrollment:
                fill_rate = (enrolled / capacity * 100) if capacity > 0 else 0
                self.dept_details.insert(tk.END, f"  {code} - {name}: {enrolled}/{capacity} ({fill_rate:.1f}%)\n")

            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load department data: {e}")

    def load_trends_data(self):
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
            cursor = conn.cursor()

            self.trends_text.delete(1.0, tk.END)
            self.trends_text.insert(tk.END, "COURSE TRENDS ANALYSIS\n")
            self.trends_text.insert(tk.END, "=" * 40 + "\n\n")

            # Most/least popular courses
            self.trends_text.insert(tk.END, "ENROLLMENT TRENDS:\n\n")

            cursor.execute("""
            SELECT COALESCE(c.course_code, c.code), COALESCE(c.course_name, c.name),
                   COUNT(s.student_id) as enrollment
            FROM courses c
            LEFT JOIN students s ON UPPER(s.course) = UPPER(COALESCE(c.course_code, c.code))
            WHERE COALESCE(c.course_code, c.code) IS NOT NULL
              AND COALESCE(c.course_name, c.name) IS NOT NULL
              AND COALESCE(c.course_type, '') = 'Degree Program'
              AND LOWER(COALESCE(c.status, 'active')) = 'active'
            GROUP BY c.id
            ORDER BY enrollment DESC
            LIMIT 10
            """)

            popular_courses = cursor.fetchall()
            if popular_courses:
                self.trends_text.insert(tk.END, "Most Popular Courses:\n")
                for code, name, enrollment in popular_courses:
                    self.trends_text.insert(tk.END, f"  {code} - {name}: {enrollment} students\n")

            self.trends_text.insert(tk.END, "\nCourses with Available Seats:\n")
            cursor.execute("""
            SELECT COALESCE(c.course_code, c.code), COALESCE(c.course_name, c.name),
                   COUNT(s.student_id) as enrolled,
                   COALESCE(c.max_enrollment, 0) as capacity,
                   (COALESCE(c.max_enrollment, 0) - COUNT(s.student_id)) as available
            FROM courses c
            LEFT JOIN students s ON UPPER(s.course) = UPPER(COALESCE(c.course_code, c.code))
            WHERE COALESCE(c.course_code, c.code) IS NOT NULL
              AND COALESCE(c.course_name, c.name) IS NOT NULL
              AND COALESCE(c.course_type, '') = 'Degree Program'
              AND LOWER(COALESCE(c.status, 'active')) = 'active'
              AND COALESCE(c.max_enrollment, 0) > 0
            GROUP BY c.id
            HAVING COUNT(s.student_id) < COALESCE(c.max_enrollment, 0)
            ORDER BY available DESC
            LIMIT 10
            """)

            available_courses = cursor.fetchall()
            for code, name, enrolled, capacity, available in available_courses:
                self.trends_text.insert(tk.END, f"  {code} - {name}: {available} seats available ({enrolled}/{capacity})\n")

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load trends data: {e}")
        finally:
            if conn:
                conn.close()

    def export_report(self):
        filename = filedialog.asksaveasfilename(
            title="Export Analytics Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("COURSE ANALYTICS REPORT\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                    # Export overview data
                    f.write("OVERVIEW METRICS:\n")
                    f.write(f"{self.total_courses_label.cget('text')}\n")
                    f.write(f"{self.total_students_label.cget('text')}\n")
                    f.write(f"{self.avg_fill_rate_label.cget('text')}\n")
                    f.write(f"{self.available_spots_label.cget('text')}\n")
                    f.write(f"{self.active_courses_label.cget('text')}\n\n")

                    # Export status distribution
                    f.write(self.status_text.get(1.0, tk.END))
                    f.write("\n")

                    # Export trends
                    f.write(self.trends_text.get(1.0, tk.END))

                messagebox.showinfo(_("common.export_complete"), f"Report exported to {filename}")

            except Exception as e:
                messagebox.showerror(_("common.export_error"), f"Failed to export report: {e}")


class EnrollmentReportDialog:
    def __init__(self, parent):
        self.parent = parent
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Generate Enrollment Report")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()
        self.dialog.wait_window()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Select Report Type", font=("Arial", 12, "bold")).pack(pady=10)

        self.report_type = tk.StringVar(value="Summary")

        report_frame = ttk.LabelFrame(main_frame, text="Report Options", padding=10)
        report_frame.pack(fill=tk.X, pady=10)

        ttk.Radiobutton(report_frame, text="Summary Report", variable=self.report_type,
                       value="Summary").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text="Department Report", variable=self.report_type,
                       value="Department").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text="Detailed Course Report", variable=self.report_type,
                       value="Detailed").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text="Capacity Analysis", variable=self.report_type,
                       value="Capacity").pack(anchor=tk.W, pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Generate", command=self.generate_report).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def generate_report(self):
        self.result = self.report_type.get()
        self.dialog.destroy()
