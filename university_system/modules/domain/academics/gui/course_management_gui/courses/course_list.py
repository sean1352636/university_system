# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.shared.constants import paths

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
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from university_system.modules.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from university_system.modules.domain.academics.services.course_management import (
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
    from university_system.modules.domain.academics.services.lms.lms_core import launch_lms_gui
    from university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def create_course_list_tab(self):
    """Create the course list tab"""
    course_frame = ttk.Frame(self.notebook)
    self.notebook.add(course_frame, text=_("course_management.tabs.course_list"))

    # Search and filter frame
    search_frame = ttk.LabelFrame(course_frame, text=_("course_management.labels.search_filter"), padding=10)
    search_frame.pack(fill=tk.X, padx=5, pady=5)

    # Search controls
    ttk.Label(search_frame, text=_("course_management.labels.search")).grid(row=0, column=0, sticky=tk.W)
    self.search_var = tk.StringVar()
    self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
    self.search_entry.grid(row=0, column=1, padx=5)
    self.search_entry.bind('<KeyRelease>', self.on_search_change)

    ttk.Label(search_frame, text=_("course_management.labels.department")).grid(row=0, column=2, sticky=tk.W, padx=(20,0))
    self.dept_filter = ttk.Combobox(search_frame, width=15)
    self.dept_filter.grid(row=0, column=3, padx=5)
    self.dept_filter.bind('<<ComboboxSelected>>', self.on_filter_change)

    ttk.Label(search_frame, text=_("course_management.labels.status")).grid(row=0, column=4, sticky=tk.W, padx=(20,0))
    self.status_filter = ttk.Combobox(search_frame, values=[_("common.all"), _("common.active"), _("common.inactive"), _("common.archived"), _("common.cancelled")], width=10)
    self.status_filter.set(_("common.all"))
    self.status_filter.grid(row=0, column=5, padx=5)
    self.status_filter.bind('<<ComboboxSelected>>', self.on_filter_change)
    
    # Course list with treeview
    list_frame = ttk.Frame(course_frame)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Create treeview with scrollbar
    columns = ("ID", "Code", "Name", "Department", "Level", "Credits", "Enrollment", "Status")
    column_labels = {
        "ID": _("course_management.columns.id"),
        "Code": _("course_management.columns.code"),
        "Name": _("course_management.columns.name"),
        "Department": _("course_management.columns.department"),
        "Level": _("course_management.columns.level"),
        "Credits": _("course_management.columns.credits"),
        "Enrollment": _("course_management.columns.enrollment"),
        "Status": _("course_management.columns.status")
    }
    self.course_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)

    # Configure column headings and widths
    for col in columns:
        self.course_tree.heading(col, text=column_labels.get(col, col), command=lambda c=col: self.sort_treeview(c))
        if col == "ID":
            self.course_tree.column(col, width=50)
        elif col == "Code":
            self.course_tree.column(col, width=80)
        elif col == "Name":
            self.course_tree.column(col, width=250)
        elif col in ["Department", "Level"]:
            self.course_tree.column(col, width=100)
        elif col == "Credits":
            self.course_tree.column(col, width=70)
        elif col == "Enrollment":
            self.course_tree.column(col, width=100)
        elif col == "Status":
            self.course_tree.column(col, width=80)
    
    # Scrollbar for treeview
    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
    self.course_tree.configure(yscrollcommand=scrollbar.set)
    
    # Pack treeview and scrollbar
    self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Bind double-click event
    self.course_tree.bind("<Double-1>", self.on_course_double_click)
    
    # Buttons frame - Role-based access
    buttons_frame = ttk.Frame(course_frame)
    buttons_frame.pack(fill=tk.X, padx=5, pady=5)

    is_admin = self.is_admin()
    is_staff = self.is_staff()

    # Admin and Staff can create courses
    if is_admin or is_staff:
        ttk.Button(buttons_frame, text=_("course_management.buttons.create_course"), command=self.show_create_course).pack(side=tk.LEFT, padx=5)

    # Admin and Staff can edit courses
    if is_admin or is_staff:
        ttk.Button(buttons_frame, text=_("course_management.buttons.edit_course"), command=self.edit_selected_course).pack(side=tk.LEFT, padx=5)

    # Only Admin can delete courses
    if is_admin:
        ttk.Button(buttons_frame, text=_("course_management.buttons.delete_course"), command=self.delete_selected_course).pack(side=tk.LEFT, padx=5)

    # Everyone can refresh
    ttk.Button(buttons_frame, text=_("common.refresh"), command=self.refresh_course_list).pack(side=tk.LEFT, padx=5)
    
    # Load initial data
    self.refresh_course_list()
    self.load_filter_options()


def refresh_course_list(self):
    """FIXED: Enhanced error handling for course list refresh"""
    try:
        # Clear existing items
        for item in self.course_tree.get_children():
            self.course_tree.delete(item)
        
        # Get courses from database
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            # Check if courses table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
            if not cursor.fetchone():
                self.update_status("Courses table not found - please check database initialization", error=True)
                return

            # Get table schema to handle missing columns gracefully
            cursor.execute("PRAGMA table_info(courses)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            # Build query based on available columns - use ROW_NUMBER for sequential ID
            base_fields = "ROW_NUMBER() OVER (ORDER BY course_code) as id, course_code, course_name"
            extra_fields = []

            if 'department' in columns:
                extra_fields.append("COALESCE(department, 'N/A') as department")
            else:
                extra_fields.append("'N/A' as department")

            if 'level' in columns:
                extra_fields.append("COALESCE(level, 'N/A') as level")
            else:
                extra_fields.append("'N/A' as level")

            if 'credit_hours' in columns:
                extra_fields.append("COALESCE(credit_hours, 3.0) as credit_hours")
            else:
                extra_fields.append("3.0 as credit_hours")

            if 'current_enrollment' in columns and 'max_enrollment' in columns:
                extra_fields.append("COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment")
            else:
                extra_fields.append("'0/30' as enrollment")

            if 'status' in columns:
                extra_fields.append("COALESCE(status, 'Active') as status")
            else:
                extra_fields.append("'Active' as status")

            query = f"SELECT {base_fields}, {', '.join(extra_fields)} FROM courses WHERE course_code IS NOT NULL ORDER BY course_code"

            cursor.execute(query)
            courses = cursor.fetchall()

            # Populate treeview
            for course in courses:
                self.course_tree.insert("", tk.END, values=course)

            self.update_status(f"Loaded {len(courses)} courses")
        
    except sqlite3.Error as e:
        self.update_status(f"Database error: {e}", error=True)
        print(_("course_management.errors.db_refresh", error=str(e)))
    except Exception as e:
        self.update_status(f"Error loading courses: {e}", error=True)
        print(_("course_management.errors.refresh_courses", error=str(e)))


def on_search_change(self, event=None):
    """Handle search text change"""
    self.filter_courses()


def on_filter_change(self, event=None):
    """Handle filter change"""
    self.filter_courses()


def filter_courses(self):
    """Filter courses based on search and filter criteria"""
    try:
        # Clear existing items
        for item in self.course_tree.get_children():
            self.course_tree.delete(item)
        
        # Build query
        search_text = self.search_var.get().strip()
        dept_filter = self.dept_filter.get()
        status_filter = self.status_filter.get()

        query = """
        SELECT ROW_NUMBER() OVER (ORDER BY course_code) as id, course_code, course_name,
               COALESCE(department, 'N/A') as department,
               COALESCE(level, 'N/A') as level,
               COALESCE(credit_hours, 3.0) as credit_hours,
               COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment,
               COALESCE(status, 'Active') as status
        FROM courses WHERE course_code IS NOT NULL
        """
        params = []
        
        if search_text:
            query += " AND (course_code LIKE ? OR course_name LIKE ? OR description LIKE ?)"
            search_param = f"%{search_text}%"
            params.extend([search_param, search_param, search_param])
        
        if dept_filter and dept_filter != "All":
            query += " AND department = ?"
            params.append(dept_filter)
        
        if status_filter and status_filter != "All":
            query += " AND status = ?"
            params.append(status_filter)
        
        query += " ORDER BY course_code"

        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            courses = cursor.fetchall()

        # Populate filtered results
        for course in courses:
            self.course_tree.insert("", tk.END, values=course)
        
        self.update_status(f"Found {len(courses)} courses")
        
    except sqlite3.Error as e:
        messagebox.showerror(_("common.database_error"), _("course_management.messages.search_failed").format(error=e))


def load_filter_options(self):
    """Load options for filter dropdowns"""
    try:
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            # Load departments
            cursor.execute("SELECT DISTINCT department FROM courses WHERE course_code IS NOT NULL AND department IS NOT NULL ORDER BY department")
            departments = ["All"] + [row[0] for row in cursor.fetchall()]
            self.dept_filter['values'] = departments
            self.dept_filter.set("All")
        
    except sqlite3.Error:
        pass


def on_course_double_click(self, event):
    """Handle double-click on course item"""
    selection = self.course_tree.selection()
    if selection:
        item = self.course_tree.item(selection[0])
        course_id = item['values'][0]
        self.show_course_details(course_id)


def sort_treeview(self, col):
    """Sort treeview by column"""
    data = [(self.course_tree.set(child, col), child) for child in self.course_tree.get_children('')]
    
    # Determine if we're sorting numbers or text
    try:
        # Try to convert to float for numeric sorting
        data.sort(key=lambda x: float(x[0]) if x[0].replace('.', '').replace('/', '').isdigit() else float('inf'))
    except Exception:
        # Fall back to string sorting
        data.sort(key=lambda x: x[0].lower())
    
    # Rearrange items in sorted positions
    for ix, item in enumerate(data):
        self.course_tree.move(item[1], '', ix)
