# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.core import paths

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
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from education_system.post_18.university_system.modules.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from education_system.post_18.university_system.modules.domain.academics.services.course_management import (
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
    from education_system.post_18.university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.post_18.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
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

    # Instructor list - displayed as a sortable table
    list_frame = ttk.LabelFrame(instructors_frame, text=_("course_management.tabs.instructors"), padding=5)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    columns = ("id", "name", "email", "department", "specialization", "max_courses", "status")
    headings = {
        "id": "ID",
        "name": "Name",
        "email": "Email",
        "department": "Department",
        "specialization": "Specialization",
        "max_courses": "Max Courses",
        "status": "Status",
    }
    widths = {
        "id": 50,
        "name": 180,
        "email": 240,
        "department": 150,
        "specialization": 170,
        "max_courses": 90,
        "status": 90,
    }

    tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
    for col in columns:
        tree.heading(col, text=headings[col])
        anchor = tk.CENTER if col in ("id", "max_courses", "status") else tk.W
        tree.column(col, width=widths[col], anchor=anchor, stretch=(col in ("name", "email", "specialization")))

    # Zebra striping for readability
    tree.tag_configure("oddrow", background="#f5f5f5")
    tree.tag_configure("evenrow", background="#ffffff")

    vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    list_frame.rowconfigure(0, weight=1)
    list_frame.columnconfigure(0, weight=1)

    self.instructor_tree = tree

    # Status/count line beneath the table
    self.instructor_count_label = ttk.Label(instructors_frame, text="")
    self.instructor_count_label.pack(fill=tk.X, padx=5, pady=(0, 5))


def show_add_instructor(self):
    """Show add instructor dialog"""
    dialog = InstructorCreateDialog(self.root, self.auth)
    if dialog.result:
        self.refresh_instructor_list()
        self.update_status(f"Instructor '{dialog.result}' added successfully")


def refresh_instructor_list(self):
    """Refresh the instructor list"""
    try:
        tree = self.instructor_tree
        # Clear existing rows
        for item in tree.get_children():
            tree.delete(item)

        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            # Check if instructors table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
            if not cursor.fetchone():
                self.instructor_count_label.config(
                    text="No instructors table found. Please add an instructor first."
                )
                return

            cursor.execute("""
            SELECT id, first_name, last_name, email, department, specialization,
                   max_courses_per_semester, status
            FROM instructors
            ORDER BY last_name, first_name
            """)

            instructors = cursor.fetchall()

        if instructors:
            for idx, instructor in enumerate(instructors):
                id, first_name, last_name, email, dept, spec, max_courses, status = instructor
                full_name = f"{first_name or ''} {last_name or ''}".strip() or "N/A"
                tag = "evenrow" if idx % 2 == 0 else "oddrow"
                tree.insert("", tk.END, values=(
                    id,
                    full_name,
                    email or "N/A",
                    dept or "N/A",
                    spec or "N/A",
                    max_courses if max_courses is not None else "N/A",
                    status or "N/A",
                ), tags=(tag,))
            self.instructor_count_label.config(text=f"Total Instructors: {len(instructors)}")
        else:
            self.instructor_count_label.config(text="No instructors found in the system.")

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
        self.dialog.geometry("640x760")
        self.dialog.minsize(600, 680)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def _update_university_email(self, *args):
        """Auto-generate university email when name fields change."""
        first = self.first_name_var.get().strip()
        last = self.last_name_var.get().strip()
        if first and last:
            try:
                from education_system.post_18.university_system.core.defaults import UNIVERSITY_EMAIL_DOMAIN
            except ImportError:
                UNIVERSITY_EMAIL_DOMAIN = "university.edu"
            clean_first = first.lower().replace(' ', '')
            clean_last = last.lower().replace(' ', '')
            self.university_email_var.set(f"{clean_first}.{clean_last}@{UNIVERSITY_EMAIL_DOMAIN}")
        else:
            self.university_email_var.set("")

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Personal Information
        personal_frame = ttk.LabelFrame(main_frame, text="Personal Information", padding=10)
        personal_frame.pack(fill=tk.X, pady=5)

        ttk.Label(personal_frame, text="First Name:").grid(row=0, column=0, sticky=tk.W)
        self.first_name_var = tk.StringVar()
        self.first_name_var.trace_add('write', self._update_university_email)
        ttk.Entry(personal_frame, textvariable=self.first_name_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Last Name:").grid(row=1, column=0, sticky=tk.W)
        self.last_name_var = tk.StringVar()
        self.last_name_var.trace_add('write', self._update_university_email)
        ttk.Entry(personal_frame, textvariable=self.last_name_var, width=25).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="University Email:").grid(row=2, column=0, sticky=tk.W)
        self.university_email_var = tk.StringVar()
        uni_email_entry = ttk.Entry(personal_frame, textvariable=self.university_email_var, width=35, state='readonly')
        uni_email_entry.grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(personal_frame, text="(auto-generated from name)", font=('Arial', 8)).grid(row=3, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Personal Email:").grid(row=4, column=0, sticky=tk.W)
        self.personal_email_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.personal_email_var, width=35).grid(row=4, column=1, sticky=tk.W, padx=5)
        ttk.Label(personal_frame, text="(optional)", font=('Arial', 8)).grid(row=5, column=1, sticky=tk.W, padx=5)

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

            if not first_name or not last_name:
                messagebox.showerror(_("common.validation_error"), "First name and last name are required.")
                return

            university_email = self.university_email_var.get().strip()
            if not university_email:
                messagebox.showerror(_("common.validation_error"), "University email could not be generated. Please enter first and last name.")
                return

            personal_email = self.personal_email_var.get().strip()
            if personal_email:
                email_pattern = r'^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$'
                if not re.match(email_pattern, personal_email):
                    messagebox.showerror(_("common.validation_error"), "Please enter a valid personal email address.")
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

            # Delegate to the unified service so this dialog, the module-scheduling
            # dialog and the CLI all create instructors through one code path.
            from education_system.post_18.university_system.modules.domain.academics.services.course_management.instructor_service import (
                create_instructor as create_instructor_service,
            )

            result = create_instructor_service(
                first_name=first_name,
                last_name=last_name,
                email=None,  # auto-generate the university email
                department=department,
                specialization=specialization,
                max_courses=max_courses,
                max_hours=max_hours,
                preferred_days=preferred_days,
                preferred_times=preferred_times,
                auth=self.auth,
            )

            if not result.ok:
                messagebox.showerror(_("common.error"), result.error or "Failed to add instructor.")
                return

            if result.account_created:
                account_msg = (f"\n\nLogin Account Created:\n  Username: {result.username}"
                               f"\n  Temporary Password: {result.temp_password}")
            else:
                account_msg = (f"\n\nLogin account could not be created automatically."
                               f"\n  Suggested username: {result.username}"
                               f"\n  Temporary password: {result.temp_password}")

            email_msg = (f"\n\nWelcome email sent to {result.email}" if result.welcome_email_sent
                         else "\n\nWelcome email could not be sent. Please notify instructor manually.")

            messagebox.showinfo(
                _("common.success"),
                f"Instructor {first_name} {last_name} added successfully!\n"
                f"University Email: {result.email}"
                f"{account_msg}{email_msg}"
            )
            self.result = f"{first_name} {last_name}"
            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to add instructor: {e}")
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Error: {e}")


class InstructorDetailsDialog:
    """Pop-up shown when an instructor row is double-clicked.

    Presents the instructor's details in an editable form and a section for
    assigning them to a course. When ``editable`` is False (non-admin users)
    the form is read-only and the assignment controls are hidden, so staff can
    still inspect an instructor without being able to change anything.
    """

    def __init__(self, parent, auth, instructor_id, editable=True):
        self.parent = parent
        self.auth = auth
        self.instructor_id = instructor_id
        self.editable = editable
        self.result = None  # set to True if details/assignment were changed

        self.instructor = self._load_instructor()
        if not self.instructor:
            messagebox.showerror(_("common.error"), "Instructor not found.")
            return

        self.dialog = tk.Toplevel(parent)
        name = f"{self.instructor['first_name'] or ''} {self.instructor['last_name'] or ''}".strip()
        self.dialog.title(f"Instructor: {name}" if name else "Instructor Details")
        self.dialog.geometry("640x720")
        self.dialog.minsize(600, 640)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def _load_instructor(self):
        """Fetch the instructor row as a dict, or None if it is missing."""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, first_name, last_name, email, department, specialization,
                           max_courses_per_semester, max_hours_per_week,
                           preferred_days, preferred_times, status
                    FROM instructors WHERE id = ?
                    """,
                    (self.instructor_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load instructor: {e}")
            return None

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        details_tab = ttk.Frame(notebook)
        notebook.add(details_tab, text="Details")
        self._build_details_tab(details_tab)

        # Course assignment is an admin-only action, mirroring the tab buttons.
        if self.editable:
            assign_tab = ttk.Frame(notebook)
            notebook.add(assign_tab, text="Assign to Course")
            self._build_assign_tab(assign_tab)

    # ---- Details tab -------------------------------------------------
    def _build_details_tab(self, tab):
        entry_state = "normal" if self.editable else "readonly"
        ins = self.instructor

        personal_frame = ttk.LabelFrame(tab, text="Personal Information", padding=10)
        personal_frame.pack(fill=tk.X, pady=5)

        ttk.Label(personal_frame, text="First Name:").grid(row=0, column=0, sticky=tk.W)
        self.first_name_var = tk.StringVar(value=ins["first_name"] or "")
        ttk.Entry(personal_frame, textvariable=self.first_name_var, width=25, state=entry_state).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Last Name:").grid(row=1, column=0, sticky=tk.W)
        self.last_name_var = tk.StringVar(value=ins["last_name"] or "")
        ttk.Entry(personal_frame, textvariable=self.last_name_var, width=25, state=entry_state).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Email:").grid(row=2, column=0, sticky=tk.W)
        self.email_var = tk.StringVar(value=ins["email"] or "")
        # Email is the login/account key — always read-only here.
        ttk.Entry(personal_frame, textvariable=self.email_var, width=35, state="readonly").grid(row=2, column=1, sticky=tk.W, padx=5)

        prof_frame = ttk.LabelFrame(tab, text="Professional Information", padding=10)
        prof_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prof_frame, text="Department:").grid(row=0, column=0, sticky=tk.W)
        self.department_var = tk.StringVar(value=ins["department"] or "")
        ttk.Entry(prof_frame, textvariable=self.department_var, width=25, state=entry_state).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Specialization:").grid(row=1, column=0, sticky=tk.W)
        self.specialization_var = tk.StringVar(value=ins["specialization"] or "")
        ttk.Entry(prof_frame, textvariable=self.specialization_var, width=35, state=entry_state).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Max Courses/Semester:").grid(row=2, column=0, sticky=tk.W)
        self.max_courses_var = tk.StringVar(value=str(ins["max_courses_per_semester"] if ins["max_courses_per_semester"] is not None else 4))
        ttk.Entry(prof_frame, textvariable=self.max_courses_var, width=10, state=entry_state).grid(row=2, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Max Hours/Week:").grid(row=3, column=0, sticky=tk.W)
        self.max_hours_var = tk.StringVar(value=str(ins["max_hours_per_week"] if ins["max_hours_per_week"] is not None else 40))
        ttk.Entry(prof_frame, textvariable=self.max_hours_var, width=10, state=entry_state).grid(row=3, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Status:").grid(row=4, column=0, sticky=tk.W)
        self.status_var = tk.StringVar(value=ins["status"] or "Active")
        status_state = "readonly" if self.editable else "disabled"
        ttk.Combobox(prof_frame, textvariable=self.status_var, width=15, state=status_state,
                     values=["Active", "Inactive", "On Leave"]).grid(row=4, column=1, sticky=tk.W, padx=5)

        sched_frame = ttk.LabelFrame(tab, text="Scheduling Preferences", padding=10)
        sched_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sched_frame, text="Preferred Days:").grid(row=0, column=0, sticky=tk.W)
        self.preferred_days_var = tk.StringVar(value=ins["preferred_days"] or "")
        ttk.Entry(sched_frame, textvariable=self.preferred_days_var, width=35, state=entry_state).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(sched_frame, text="Preferred Times:").grid(row=1, column=0, sticky=tk.W)
        self.preferred_times_var = tk.StringVar(value=ins["preferred_times"] or "")
        ttk.Entry(sched_frame, textvariable=self.preferred_times_var, width=35, state=entry_state).grid(row=1, column=1, sticky=tk.W, padx=5)

        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=10)
        if self.editable:
            ttk.Button(button_frame, text="Save Changes", command=self.save_details).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def save_details(self):
        first_name = self.first_name_var.get().strip()
        last_name = self.last_name_var.get().strip()

        if not first_name or not last_name:
            messagebox.showerror(_("common.validation_error"), "First name and last name are required.")
            return

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

        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE instructors
                    SET first_name = ?, last_name = ?, department = ?, specialization = ?,
                        max_courses_per_semester = ?, max_hours_per_week = ?,
                        preferred_days = ?, preferred_times = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        first_name, last_name,
                        self.department_var.get().strip(),
                        self.specialization_var.get().strip(),
                        max_courses, max_hours,
                        self.preferred_days_var.get().strip(),
                        self.preferred_times_var.get().strip(),
                        self.status_var.get().strip() or "Active",
                        timestamp, self.instructor_id,
                    ),
                )
                conn.commit()

            self.result = True
            messagebox.showinfo(_("common.success"), f"Instructor {first_name} {last_name} updated successfully.")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to update instructor: {e}")

    # ---- Assign tab --------------------------------------------------
    def _build_assign_tab(self, tab):
        name = f"{self.instructor['first_name'] or ''} {self.instructor['last_name'] or ''}".strip()
        ttk.Label(tab, text=f"Assign {name or 'this instructor'} to a course",
                  font=("Arial", 11, "bold")).pack(pady=10)

        course_frame = ttk.LabelFrame(tab, text="Select Course", padding=10)
        course_frame.pack(fill=tk.X, pady=5)
        ttk.Label(course_frame, text="Course:").pack(anchor=tk.W)
        self.course_combo = ttk.Combobox(course_frame, width=50, state="readonly")
        self.course_combo.pack(fill=tk.X, pady=2)

        schedule_frame = ttk.LabelFrame(tab, text="Schedule Information", padding=10)
        schedule_frame.pack(fill=tk.X, pady=5)
        ttk.Label(schedule_frame, text="Semester:").grid(row=0, column=0, sticky=tk.W)
        self.semester_var = tk.StringVar(value="Fall")
        ttk.Combobox(schedule_frame, textvariable=self.semester_var,
                     values=["Fall", "Spring", "Summer", "Winter"]).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(schedule_frame, text="Year:").grid(row=1, column=0, sticky=tk.W)
        self.year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(schedule_frame, textvariable=self.year_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)

        current_frame = ttk.LabelFrame(tab, text="Current Assignments", padding=10)
        current_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.assignments_list = tk.Listbox(current_frame, height=6)
        self.assignments_list.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=10)
        ttk.Button(button_frame, text="Assign", command=self.assign_to_course).pack(side=tk.RIGHT, padx=5)

        self._load_assign_data()
        self._refresh_assignments()

    def _load_assign_data(self):
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, course_code, course_name FROM courses "
                    "WHERE course_code IS NOT NULL AND course_name IS NOT NULL "
                    "AND LOWER(COALESCE(status, 'active')) = 'active' "
                    "ORDER BY course_code"
                )
                courses = cursor.fetchall()
            course_options = [f"{c[1] or 'N/A'} - {c[2] or 'Unnamed'}" for c in courses]
            self.course_combo['values'] = course_options
            self.course_id_map = {opt: c[0] for opt, c in zip(course_options, courses)}
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
            self.course_id_map = {}

    def _refresh_assignments(self):
        """List the courses this instructor is currently scheduled for."""
        self.assignments_list.delete(0, tk.END)
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='course_schedule'"
                )
                if not cursor.fetchone():
                    self.assignments_list.insert(tk.END, "No assignments yet.")
                    return
                cursor.execute(
                    """
                    SELECT c.course_code, c.course_name, s.semester, s.year
                    FROM course_schedule s
                    JOIN courses c ON c.id = s.course_id
                    WHERE s.instructor_id = ?
                    ORDER BY s.year DESC, s.semester
                    """,
                    (self.instructor_id,),
                )
                rows = cursor.fetchall()
            if rows:
                for code, cname, semester, year in rows:
                    self.assignments_list.insert(tk.END, f"{code or 'N/A'} - {cname or 'Unnamed'}  ({semester} {year})")
            else:
                self.assignments_list.insert(tk.END, "No assignments yet.")
        except sqlite3.Error:
            self.assignments_list.insert(tk.END, "Could not load assignments.")

    def assign_to_course(self):
        course_text = self.course_combo.get()
        if not course_text:
            messagebox.showwarning(_("common.selection_required"), "Please select a course.")
            return
        course_id = self.course_id_map.get(course_text)
        if not course_id:
            messagebox.showerror(_("common.error"), "Invalid course selection.")
            return
        try:
            year_int = int(self.year_var.get())
        except ValueError:
            messagebox.showerror(_("common.error"), "Please enter a valid year.")
            return
        semester = self.semester_var.get()

        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
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
                cursor.execute(
                    "SELECT id FROM course_schedule WHERE course_id = ? AND semester = ? AND year = ?",
                    (course_id, semester, year_int),
                )
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("UPDATE course_schedule SET instructor_id = ? WHERE id = ?",
                                   (self.instructor_id, existing[0]))
                else:
                    cursor.execute(
                        "INSERT INTO course_schedule (course_id, semester, year, instructor_id, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (course_id, semester, year_int, self.instructor_id, timestamp),
                    )
                conn.commit()

            self.result = True
            self._refresh_assignments()
            messagebox.showinfo(_("common.success"), f"Assigned to {course_text} for {semester} {year_int}.")
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to assign instructor: {e}")


class AssignInstructorDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Assign Instructor to Course")
        self.dialog.geometry("640x560")
        self.dialog.minsize(600, 500)
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
                "SELECT id, course_code, course_name, department FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "AND LOWER(COALESCE(status, 'active')) = 'active' "
                "ORDER BY course_code"
            )
            courses = cursor.fetchall()
            course_options = [f"{c[1] or 'N/A'} - {c[2] or 'Unnamed'}" for c in courses]
            self.course_combo['values'] = course_options
            self.course_id_map = {opt: c[0] for opt, c in zip(course_options, courses)}
            # Richer course details keyed by option, for the assignment email
            self.course_info_map = {
                opt: {"id": c[0], "code": c[1], "name": c[2], "department": c[3]}
                for opt, c in zip(course_options, courses)
            }

            # Load instructors
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
            if cursor.fetchone():
                cursor.execute("SELECT id, first_name, last_name, email FROM instructors WHERE LOWER(COALESCE(status, 'active')) = 'active' ORDER BY last_name")
                instructors = cursor.fetchall()
                instructor_options = [f"{i[1] or ''} {i[2] or ''}".strip() or f"Instructor {i[0]}" for i in instructors]
                self.instructor_combo['values'] = instructor_options
                self.instructor_id_map = {opt: i[0] for opt, i in zip(instructor_options, instructors)}
                # Richer instructor details keyed by option, for the assignment email
                self.instructor_info_map = {
                    opt: {
                        "id": i[0],
                        "name": f"{i[1] or ''} {i[2] or ''}".strip() or f"Instructor {i[0]}",
                        "email": i[3],
                    }
                    for opt, i in zip(instructor_options, instructors)
                }
            else:
                self.instructor_combo['values'] = ["No instructors found"]
                self.instructor_id_map = {}
                self.instructor_info_map = {}

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

            # Notify the instructor by email that they've been assigned
            email_msg = self._send_assignment_email(instructor_text, course_text, semester, year_int)

            messagebox.showinfo(
                _("common.success"),
                f"Instructor assigned to {course_text} for {semester} {year}{email_msg}"
            )
            self.result = True
            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to assign instructor: {e}")

    def _send_assignment_email(self, instructor_text, course_text, semester, year):
        """Email the instructor to let them know which course they've been assigned to.

        Returns a short status string (appended to the success dialog). Failure to
        send never blocks the assignment itself.
        """
        try:
            instructor = getattr(self, "instructor_info_map", {}).get(instructor_text, {})
            course = getattr(self, "course_info_map", {}).get(course_text, {})

            recipient = (instructor.get("email") or "").strip()
            if not recipient:
                return "\n\n(No email on file for this instructor — notification not sent.)"

            try:
                from education_system.post_18.university_system.core.defaults import UNIVERSITY_EMAIL_DOMAIN
            except ImportError:
                UNIVERSITY_EMAIL_DOMAIN = "university.edu"

            from education_system.post_18.university_system.infrastructure.email import send_template_email

            template_vars = {
                "instructor_name": instructor.get("name") or "Instructor",
                "course_code": course.get("code") or "N/A",
                "course_name": course.get("name") or "N/A",
                "department": course.get("department") or "Not specified",
                "semester": semester,
                "year": str(year),
                "email_domain": UNIVERSITY_EMAIL_DOMAIN,
                "assigned_timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

            sent = send_template_email(
                "academics/course_assignment_notification",
                recipient,
                template_vars,
            )
            if sent:
                return f"\n\nNotification email sent to {recipient}"
            return f"\n\nNotification email could not be sent to {recipient}."
        except Exception as e:
            return f"\n\nNotification email could not be sent: {e}"
