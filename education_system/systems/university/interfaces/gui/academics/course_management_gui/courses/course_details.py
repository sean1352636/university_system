# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure import paths

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
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from education_system.systems.university.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from education_system.systems.university.domain.academics.services.course_management import (
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
    from education_system.systems.university.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.systems.university.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def create_course_details_tab(self):
    """Create the course details tab"""
    details_frame = ttk.Frame(self.notebook)
    self.notebook.add(details_frame, text=_("course_management.tabs.course_details"))

    # Course selection frame
    selection_frame = ttk.LabelFrame(details_frame, text=_("course_management.labels.select_course"), padding=10)
    selection_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(selection_frame, text=_("course_management.labels.course")).pack(side=tk.LEFT)
    self.course_selector = ttk.Combobox(selection_frame, width=50)
    self.course_selector.pack(side=tk.LEFT, padx=5)
    self.course_selector.bind('<<ComboboxSelected>>', self.on_course_select)

    # Details display frame
    self.details_frame = ttk.LabelFrame(details_frame, text=_("course_management.labels.course_information"), padding=10)
    self.details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Create scrolled text for details
    self.details_text = ScrolledText(self.details_frame, wrap=tk.WORD, height=20)
    self.details_text.pack(fill=tk.BOTH, expand=True)

    # Load course options
    self.load_course_selector_options()




def show_course_details(self, event):
    selection = self.results_tree.selection()
    if selection:
        values = self.results_tree.item(selection[0])['values']
        course_code = values[0]

        # Find course ID and show details
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,))
            result = cursor.fetchone()
            if result:
                # Use existing course details method from main GUI
                self.parent.view_course_details(cursor, result[0])
            conn.close()
        except sqlite3.Error:
            pass


def format_course_details(self, course):
    """Format course data for display."""

    def get(i, default="N/A"):
        return course[i] if len(course) > i and course[i] not in (None, "") else default

    def years(i):
        v = course[i] if len(course) > i else None
        return f"{v} years" if v not in (None, "") else "N/A"

    def money(i):
        v = course[i] if len(course) > i else None
        if isinstance(v, (int, float)):
            return f"£{v:,.2f}"
        return "N/A" if v in (None, "") else str(v)

    def yesno(i):
        if len(course) <= i:
            return "N/A"
        v = course[i]
        return "Yes" if bool(v) else "No" if v in (False, 0) else "N/A"

    def avail_spots():
        max_e = course[15] if len(course) > 15 else None
        cur_e = course[16] if len(course) > 16 else None
        if isinstance(max_e, (int, float)) and isinstance(cur_e, (int, float)):
            return max_e - cur_e
        return "N/A"

    if len(course) < 10:
        # Basic format for legacy schema
        details = f"""COURSE DETAILS
{'='*50}

Course ID: {get(0)}
Course Code: {get(1)}
Course Name: {get(2)}
Description: {get(3)}
Duration: {years(4)}
Level: {get(5)}
Department: {get(6)}
"""
    else:
        # Enhanced format for full schema
        details = f"""COURSE DETAILS
{'='*50}

BASIC INFORMATION:
Course ID: {get(0)}
Course Code: {get(1)}
Course Name: {get(2)}
Description: {get(3)}
Department: {get(6)}
Level: {get(5)}
Course Type: {get(18)}
Status: {get(17)}

ACADEMIC DETAILS:
Credit Hours: {get(7)}
Contact Hours/Week: {get(8)}
Duration: {years(4)}
Lab Required: {yesno(13)}
Online Available: {yesno(14)}

ENROLLMENT:
Max Enrollment: {get(15)}
Current Enrollment: {get(16)}
Available Spots: {avail_spots()}

ADDITIONAL INFORMATION:
Learning Outcomes: {get(9)}
Assessment Methods: {get(10)}
Required Textbooks: {get(11)}
Course Fee: {money(12)}
Tags: {get(19)}
Availability: {get(20)}

TIMESTAMPS:
Created: {get(21)}
Last Updated: {get(22)}
"""
    return details


def load_course_selector_options(self):
    """Load course options for the selector"""
    try:
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, "
                "       COALESCE(course_code, code) AS course_code, "
                "       COALESCE(course_name, name) AS course_name "
                "FROM courses "
                "WHERE COALESCE(course_code, code) IS NOT NULL "
                "AND COALESCE(course_name, name) IS NOT NULL "
                "ORDER BY course_code"
            )
            courses = cursor.fetchall()

            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.course_selector['values'] = course_options

            # Store course IDs for mapping
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}

    except sqlite3.Error:
        pass


def on_course_select(self, event=None):
    """Handle course selection from dropdown"""
    selected_text = self.course_selector.get()
    if selected_text in self.course_id_map:
        course_id = self.course_id_map[selected_text]
        self.show_course_details(course_id)


def view_course_details(self, cursor, course_id):
    """Enhanced course details viewer"""
    cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
    course = cursor.fetchone()

    if not course:
        messagebox.showerror(_("common.error"), "Course not found")
        return

    # Create details window
    details_window = tk.Toplevel(self.root)
    details_window.title(f"Course Details: {course[1]}")
    details_window.geometry("600x700")
    details_window.transient(self.root)

    # Create notebook for different views
    notebook = ttk.Notebook(details_window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Basic Info Tab
    basic_frame = ttk.Frame(notebook)
    notebook.add(basic_frame, text="Basic Info")

    basic_text = ScrolledText(basic_frame, wrap=tk.WORD)
    basic_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    basic_text.insert(tk.END, self.format_course_details(course))
    basic_text.config(state=tk.DISABLED)

    # Prerequisites Tab
    prereq_frame = ttk.Frame(notebook)
    notebook.add(prereq_frame, text="Prerequisites")

    prereq_text = ScrolledText(prereq_frame, wrap=tk.WORD)
    prereq_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Load prerequisites
    cursor.execute("""
    SELECT c.course_code, c.course_name, cp.is_required
    FROM course_prerequisites cp
    JOIN courses c ON cp.prerequisite_course_id = c.id
    WHERE cp.course_id = ?
    ORDER BY c.course_code
    """, (course_id,))

    prereqs = cursor.fetchall()
    if prereqs:
        prereq_text.insert(tk.END, "PREREQUISITES:\n\n")
        for code, name, required in prereqs:
            req_type = "Required" if required else "Recommended"
            prereq_text.insert(tk.END, f"• {code} - {name} ({req_type})\n")
    else:
        prereq_text.insert(tk.END, "No prerequisites for this course.")

    prereq_text.config(state=tk.DISABLED)

    # Schedule Tab
    schedule_frame = ttk.Frame(notebook)
    notebook.add(schedule_frame, text="Schedule")

    schedule_text = ScrolledText(schedule_frame, wrap=tk.WORD)
    schedule_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Load schedule
    cursor.execute("""
    SELECT cs.semester, cs.year, cs.start_time, cs.end_time, cs.days_of_week, cs.classroom,
           COALESCE(i.first_name || ' ' || i.last_name, 'Unassigned') as instructor
    FROM course_schedule cs
    LEFT JOIN instructors i ON cs.instructor_id = i.id
    WHERE cs.course_id = ?
    ORDER BY cs.year DESC, cs.semester
    """, (course_id,))

    schedules = cursor.fetchall()
    if schedules:
        schedule_text.insert(tk.END, "COURSE SCHEDULES:\n\n")
        for schedule in schedules:
            semester, year, start, end, days, room, instructor = schedule
            schedule_text.insert(tk.END, f"Semester: {semester} {year}\n")
            if start and end:
                schedule_text.insert(tk.END, f"Time: {start} - {end}\n")
            if days:
                schedule_text.insert(tk.END, f"Days: {days}\n")
            if room:
                schedule_text.insert(tk.END, f"Room: {room}\n")
            schedule_text.insert(tk.END, f"Instructor: {instructor}\n\n")
    else:
        schedule_text.insert(tk.END, "No schedule information available.")

    schedule_text.config(state=tk.DISABLED)

    # Close button
    ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=10)
