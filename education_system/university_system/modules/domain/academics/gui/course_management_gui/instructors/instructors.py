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


def create_instructors_tab(self):
    """Create the instructors tab with role-based access"""
    instructors_frame = ttk.Frame(self.notebook)
    self.notebook.add(instructors_frame, text=_("course_management.tabs.instructors"))

    is_admin = self.is_admin()
    is_staff = self.is_staff()

    # Instructor controls - Admin and Staff only
    if is_admin or is_staff:
        controls_frame = ttk.LabelFrame(instructors_frame, text=_("course_management.labels.instructor_management"), padding=10)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Admin only - Add instructor
        if is_admin:
            ttk.Button(controls_frame, text=_("course_management.buttons.add_instructor"), command=self.show_add_instructor).pack(side=tk.LEFT, padx=5)

        # Admin and Staff can view instructors
        ttk.Button(controls_frame, text=_("course_management.buttons.view_instructors"), command=self.refresh_instructor_list).pack(side=tk.LEFT, padx=5)

        # Admin only - Assign to course
        if is_admin:
            ttk.Button(controls_frame, text=_("course_management.buttons.assign_to_course"), command=self.show_assign_instructor).pack(side=tk.LEFT, padx=5)

    # Instructor list
    self.instructor_text = ScrolledText(instructors_frame, wrap=tk.WORD, height=25)
    self.instructor_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


def show_add_instructor(self):
    """Show add instructor dialog"""
    dialog = InstructorCreateDialog(self.root, self.auth)
    if dialog.result:
        self.refresh_instructor_list()
        self.update_status(f"Instructor '{dialog.result}' added successfully")


def refresh_instructor_list(self):
    """Refresh the instructor list"""
    try:
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            # Check if instructors table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
            if not cursor.fetchone():
                instructor_text = "INSTRUCTORS\n"
                instructor_text += "=" * 50 + "\n\n"
                instructor_text += "No instructors table found. Please create instructors first.\n"
            else:
                cursor.execute("""
                SELECT id, first_name, last_name, email, department, specialization,
                       max_courses_per_semester, status
                FROM instructors
                ORDER BY last_name, first_name
                """)

                instructors = cursor.fetchall()

                instructor_text = "INSTRUCTORS\n"
                instructor_text += "=" * 50 + "\n\n"

                if instructors:
                    instructor_text += f"{'ID':<5} {'Name':<25} {'Email':<30} {'Department':<15} {'Status':<10}\n"
                    instructor_text += "-" * 85 + "\n"

                    for instructor in instructors:
                        id, first_name, last_name, email, dept, spec, max_courses, status = instructor
                        full_name = f"{first_name} {last_name}"
                        dept_display = dept[:12] + "..." if dept and len(dept) > 15 else dept or "N/A"
                        instructor_text += f"{id:<5} {full_name:<25} {email:<30} {dept_display:<15} {status:<10}\n"

                    instructor_text += f"\nTotal Instructors: {len(instructors)}\n"
                else:
                    instructor_text += "No instructors found in the system.\n"

        # Update instructor tab
        self.instructor_text.delete(1.0, tk.END)
        self.instructor_text.insert(1.0, instructor_text)

    except sqlite3.Error as e:
        messagebox.showerror(_("common.database_error"), f"Failed to load instructors: {e}")


def show_assign_instructor(self):
    """Show assign instructor to course dialog"""
    dialog = AssignInstructorDialog(self.root, self.auth)
    if dialog.result:
        self.update_status("Instructor assigned successfully")


def create_instructor_wrapper(self):
    """
    Create a new instructor profile.
    Calls the existing show_add_instructor() method.
    """
    self.show_add_instructor()


def view_instructors_wrapper(self):
    """
    View all instructors in the system.
    Refreshes the instructor list and switches to instructors tab.
    """
    self.refresh_instructor_list()
    # Find and select the instructors tab (usually tab 3)
    for i in range(self.notebook.index('end')):
        if 'Instructor' in self.notebook.tab(i, 'text'):
            self.notebook.select(i)
            break
    self.update_status("Instructor list refreshed")


def assign_instructor_to_course_wrapper(self):
    """
    Assign an instructor to a course.
    Calls the existing show_assign_instructor() method.
    """
    self.show_assign_instructor()


class InstructorCreateDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Instructor")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Personal Information
        personal_frame = ttk.LabelFrame(main_frame, text="Personal Information", padding=10)
        personal_frame.pack(fill=tk.X, pady=5)

        ttk.Label(personal_frame, text="First Name:").grid(row=0, column=0, sticky=tk.W)
        self.first_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.first_name_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Last Name:").grid(row=1, column=0, sticky=tk.W)
        self.last_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.last_name_var, width=25).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Email:").grid(row=2, column=0, sticky=tk.W)
        self.email_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.email_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)

        # Professional Information
        prof_frame = ttk.LabelFrame(main_frame, text="Professional Information", padding=10)
        prof_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prof_frame, text="Department:").grid(row=0, column=0, sticky=tk.W)
        self.department_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.department_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Specialization:").grid(row=1, column=0, sticky=tk.W)
        self.specialization_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.specialization_var, width=35).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Max Courses/Semester:").grid(row=2, column=0, sticky=tk.W)
        self.max_courses_var = tk.StringVar(value="4")
        ttk.Entry(prof_frame, textvariable=self.max_courses_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Max Hours/Week:").grid(row=3, column=0, sticky=tk.W)
        self.max_hours_var = tk.StringVar(value="40")
        ttk.Entry(prof_frame, textvariable=self.max_hours_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Scheduling Preferences
        sched_frame = ttk.LabelFrame(main_frame, text="Scheduling Preferences", padding=10)
        sched_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sched_frame, text="Preferred Days:").grid(row=0, column=0, sticky=tk.W)
        self.preferred_days_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_days_var, width=35).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text="(comma-separated, e.g., Monday,Tuesday)", font=('Arial', 8)).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(sched_frame, text="Preferred Times:").grid(row=2, column=0, sticky=tk.W)
        self.preferred_times_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_times_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text="(comma-separated, e.g., 09:00,10:00)", font=('Arial', 8)).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add Instructor", command=self.add_instructor).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def add_instructor(self):
        try:
            # Validate inputs
            first_name = self.first_name_var.get().strip()
            last_name = self.last_name_var.get().strip()
            email = self.email_var.get().strip()

            if not first_name or not last_name or not email:
                messagebox.showerror(_("common.validation_error"), "First name, last name, and email are required.")
                return

            # Validate email format
            email_pattern = r'^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$'
            if not re.match(email_pattern, email):
                messagebox.showerror(_("common.validation_error"), "Please enter a valid email address.")
                return

            department = self.department_var.get().strip()
            specialization = self.specialization_var.get().strip()

            try:
                max_courses = int(self.max_courses_var.get())
            except ValueError:
                messagebox.showerror(_("common.validation_error"), "Max courses must be a number.")
                return

            try:
                max_hours = int(self.max_hours_var.get())
            except ValueError:
                messagebox.showerror(_("common.validation_error"), "Max hours must be a number.")
                return

            preferred_days = self.preferred_days_var.get().strip()
            preferred_times = self.preferred_times_var.get().strip()

            # Create instructors table if it doesn't exist
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS instructors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    department TEXT DEFAULT '',
                    specialization TEXT DEFAULT '',
                    max_courses_per_semester INTEGER DEFAULT 4,
                    max_hours_per_week INTEGER DEFAULT 40,
                    preferred_days TEXT,
                    preferred_times TEXT,
                    status TEXT DEFAULT 'Active',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                ''')

                # Check for duplicate email
                cursor.execute("SELECT email FROM instructors WHERE email = ?", (email,))
                if cursor.fetchone():
                    messagebox.showerror(_("common.duplicate_error"), f"Email '{email}' already exists.")
                    return

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO instructors (first_name, last_name, email, department, specialization,
                                       max_courses_per_semester, max_hours_per_week, preferred_days,
                                       preferred_times, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (first_name, last_name, email, department, specialization, max_courses,
                      max_hours, preferred_days, preferred_times, timestamp, timestamp))

                conn.commit()

            messagebox.showinfo(_("common.success"), f"Instructor {first_name} {last_name} added successfully.")
            self.result = f"{first_name} {last_name}"
            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to add instructor: {e}")


class AssignInstructorDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Assign Instructor to Course")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Assign Instructor to Course", font=("Arial", 12, "bold")).pack(pady=10)

        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding=10)
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text="Course:").pack(anchor=tk.W)
        self.course_combo = ttk.Combobox(course_frame, width=50)
        self.course_combo.pack(fill=tk.X, pady=2)

        # Instructor selection
        instructor_frame = ttk.LabelFrame(main_frame, text="Select Instructor", padding=10)
        instructor_frame.pack(fill=tk.X, pady=5)

        ttk.Label(instructor_frame, text="Instructor:").pack(anchor=tk.W)
        self.instructor_combo = ttk.Combobox(instructor_frame, width=50)
        self.instructor_combo.pack(fill=tk.X, pady=2)

        # Schedule information
        schedule_frame = ttk.LabelFrame(main_frame, text="Schedule Information", padding=10)
        schedule_frame.pack(fill=tk.X, pady=5)

        ttk.Label(schedule_frame, text="Semester:").grid(row=0, column=0, sticky=tk.W)
        self.semester_var = tk.StringVar(value="Fall")
        semester_combo = ttk.Combobox(schedule_frame, textvariable=self.semester_var,
                                     values=["Fall", "Spring", "Summer", "Winter"])
        semester_combo.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(schedule_frame, text="Year:").grid(row=1, column=0, sticky=tk.W)
        self.year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(schedule_frame, textvariable=self.year_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Assign", command=self.assign_instructor).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Load courses (case-insensitive status check)
            cursor.execute(
                "SELECT id, course_code, course_name FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "AND LOWER(COALESCE(status, 'active')) = 'active' "
                "ORDER BY course_code"
            )
            courses = cursor.fetchall()
            course_options = [f"{c[1] or 'N/A'} - {c[2] or 'Unnamed'}" for c in courses]
            self.course_combo['values'] = course_options
            self.course_id_map = {opt: c[0] for opt, c in zip(course_options, courses)}

            # Load instructors
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
            if cursor.fetchone():
                cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE LOWER(COALESCE(status, 'active')) = 'active' ORDER BY last_name")
                instructors = cursor.fetchall()
                instructor_options = [f"{i[1] or ''} {i[2] or ''}".strip() or f"Instructor {i[0]}" for i in instructors]
                self.instructor_combo['values'] = instructor_options
                self.instructor_id_map = {opt: i[0] for opt, i in zip(instructor_options, instructors)}
            else:
                self.instructor_combo['values'] = ["No instructors found"]
                self.instructor_id_map = {}

            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load data: {e}")

    def assign_instructor(self):
        try:
            course_text = self.course_combo.get()
            instructor_text = self.instructor_combo.get()
            semester = self.semester_var.get()
            year = self.year_var.get()

            if not course_text or not instructor_text:
                messagebox.showwarning(_("common.selection_required"), "Please select both course and instructor.")
                return

            course_id = self.course_id_map.get(course_text)
            instructor_id = self.instructor_id_map.get(instructor_text)

            if not course_id or not instructor_id:
                messagebox.showerror(_("common.error"), "Invalid selection.")
                return

            try:
                year_int = int(year)
            except ValueError:
                messagebox.showerror(_("common.error"), "Please enter a valid year.")
                return

            # Create schedule table if it doesn't exist and assign instructor
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.cursor()

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    semester TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    days_of_week TEXT,
                    classroom TEXT,
                    instructor_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    UNIQUE(course_id, semester, year)
                )
                ''')

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Check if schedule exists
                cursor.execute("SELECT id FROM course_schedule WHERE course_id = ? AND semester = ? AND year = ?",
                              (course_id, semester, year_int))
                existing = cursor.fetchone()

                if existing:
                    # Update existing schedule
                    cursor.execute("UPDATE course_schedule SET instructor_id = ? WHERE id = ?",
                                  (instructor_id, existing[0]))
                else:
                    # Create new schedule
                    cursor.execute('''
                    INSERT INTO course_schedule (course_id, semester, year, instructor_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (course_id, semester, year_int, instructor_id, timestamp))

                conn.commit()
            finally:
                conn.close()

            messagebox.showinfo(_("common.success"), f"Instructor assigned to {course_text} for {semester} {year}")
            self.result = True
            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to assign instructor: {e}")
