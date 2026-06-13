"""Grade management and calculations"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.scrolledtext as scrolledtext
from education_system.university_system.infrastructure.database.db import sqlite3
import os
from pathlib import Path
import csv
import numpy as np
import math
from scipy import stats
from datetime import datetime, timedelta
import json
from education_system.university_system.core import paths
from education_system.university_system.modules.domain.academics.gui.grade_tracking.utils import ensure_column_exists

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import secure file upload handler
try:
    from education_system.university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    def secure_filename(x):
        return x

# Import activity logger
try:
    from education_system.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_gui_context,
    )
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Optional imports with fallbacks
try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except ImportError:
    plt = None
    sns = None
    FigureCanvasTkAgg = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
except ImportError:
    # ReportLab not available - PDF features will be disabled
    SimpleDocTemplate = None

# Database connection setup

_original_sqlite3_connect_grade = sqlite3.connect

def _patched_sqlite3_connect_grade(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "student_grading_system.db"):
            return _original_sqlite3_connect_grade(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite3_connect_grade(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite3_connect_grade

# Import the database connection
try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    def get_connection():
        """Fallback database connection function"""
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        return sqlite3.connect(str(DEFAULT_DB_PATH))

# Global variables for grade systems
GRADE_SYSTEMS = {
    "letter": {
        "A+": 4.3, "A": 4.0, "A-": 3.7,
        "B+": 3.3, "B": 3.0, "B-": 2.7,
        "C+": 2.3, "C": 2.0, "C-": 1.7,
        "D+": 1.3, "D": 1.0, "D-": 0.7,
        "F": 0.0
    },
    "percentage": {
        "range": (0, 100),
        "conversion": {
        (90, 100): "A+", (85, 89.99): "A", (80, 84.99): "A-",
        (75, 79.99): "B+", (70, 74.99): "B", (65, 69.99): "B-",
        (60, 64.99): "C+", (55, 59.99): "C", (50, 54.99): "C-",
        (45, 49.99): "D+", (40, 44.99): "D", (35, 39.99): "D-",
        (0, 34.99): "F"
        }
    }
}

def percentage_to_letter(percentage):
    """Convert a percentage score to a letter grade"""
    for score_range, letter in GRADE_SYSTEMS["percentage"]["conversion"].items():
        min_score, max_score = score_range
        if min_score <= percentage <= max_score:
            return letter
    return 'F'

def letter_to_percentage(letter_grade):
    """Convert a letter grade to a percentage score (midpoint of range)"""
    for score_range, letter in GRADE_SYSTEMS["percentage"]["conversion"].items():
        if letter == letter_grade:
            min_score, max_score = score_range
        return (min_score + max_score) / 2
    return 0

def letter_to_gpa(letter_grade):
    """Convert a letter grade to a GPA value"""
    if letter_grade in GRADE_SYSTEMS["letter"]:
        return GRADE_SYSTEMS["letter"][letter_grade]
    return 0

def init_basic_database():
    """Initialize the basic database tables that are missing"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create students table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        middle_name TEXT,
        last_name TEXT NOT NULL,
        course TEXT NOT NULL,
        email_address TEXT,
        gender TEXT,
        dob TEXT,
        enrollment_date TEXT DEFAULT (date('now')),
        status TEXT DEFAULT 'Active'
        )
        ''')

        # Create modules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
        module_code TEXT PRIMARY KEY,
        module_name TEXT NOT NULL,
        module_type TEXT,
        credits INTEGER DEFAULT 1,
        description TEXT,
        course TEXT,
        semester TEXT,
        year INTEGER
        )
        ''')

        # Create student_modules table (enrollment)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        module_code TEXT,
        enrollment_date TEXT DEFAULT (date('now')),
        status TEXT DEFAULT 'Enrolled',
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (module_code) REFERENCES modules (module_code),
        UNIQUE(student_id, module_code)
        )
        ''')

        # Create assessments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
        assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_name TEXT NOT NULL,
        assessment_type TEXT NOT NULL,
        module_code TEXT NOT NULL,
        max_points REAL NOT NULL,
        weight REAL NOT NULL,
        due_date TEXT,
        date_created TEXT DEFAULT (datetime('now')),
        description TEXT,
        rubric TEXT,
        FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Ensure rubric column exists for legacy databases.
        ensure_column_exists(cursor, 'assessments', 'rubric', 'TEXT')

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Database error: {e}")
        return False

def init_enhanced_grades_db():
    """Initialize the enhanced grades database with all required tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create base grade tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grades (
        grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        assessment_id INTEGER,
        score REAL,
        letter_grade TEXT,
        submission_date TEXT,
        comments TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS module_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        module_code TEXT,
        final_score REAL,
        final_grade TEXT,
        completion_date TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Enhanced tables for statistics and analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grade_statistics (
        stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER,
        mean REAL,
        median REAL,
        std_dev REAL,
        min_score REAL,
        max_score REAL,
        q1 REAL,
        q3 REAL,
        skewness REAL,
        kurtosis REAL,
        date_calculated TEXT,
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS normalized_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grade_id INTEGER,
        z_score REAL,
        percentile REAL,
        curved_score REAL,
        curved_letter TEXT,
        FOREIGN KEY (grade_id) REFERENCES grades (grade_id)
        )
        ''')

        # Predictive analytics tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_factors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        factor_name TEXT,
        factor_value REAL,
        assessment_id INTEGER,
        date_calculated TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        risk_factor_id INTEGER,
        detail TEXT,
        weight REAL,
        created_at TEXT,
        FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS intervention_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommended_interventions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        risk_factor_id INTEGER,
        intervention_type_id INTEGER,
        recommended_date TEXT,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id),
        FOREIGN KEY (intervention_type_id) REFERENCES intervention_types (id)
        )
        ''')

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Database error: {e}")
        return False

def safe_grab_set(dialog):
    """Safely set grab on dialog window, handling TclError exceptions"""
    try:
        # Ensure dialog is visible first
        dialog.update_idletasks()
        dialog.grab_set()
    except tk.TclError:
        # If grab fails, continue without modal behavior
        pass

def safe_combo_update(obj, combo_attr, values):
    """Safely update combobox values, handling widget destruction"""
    try:
        if hasattr(obj, combo_attr):
            combo = getattr(obj, combo_attr)
        if combo and combo.winfo_exists():
            combo['values'] = values
            return True
    except (tk.TclError, AttributeError):
        # Widget no longer exists or is invalid
        pass
    return False

class GradeManager:
    """Grade management and calculations"""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.auth = app.auth
        self.conn = app.conn

    @property
    def content_frame(self):
        """Dynamically get content frame from layout"""
        if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'content_frame'):
            return self.app.layout.content_frame
        return None

    def get_safe_cursor(self):
        """Get a safe database cursor, checking connection validity"""
        if self.conn is None:
            # Try to get connection from app
            if hasattr(self.app, 'conn') and self.app.conn is not None:
                self.conn = self.app.conn
            else:
                raise ConnectionError("Database connection is not available. Please restart the application.")

        try:
            return self.conn.cursor()
        except Exception as e:
            raise ConnectionError(f"Failed to create database cursor: {e}")

    def safe_commit(self):
        """Safely commit database changes"""
        if self.conn is None:
            # Try to get connection from app
            if hasattr(self.app, 'conn') and self.app.conn is not None:
                self.conn = self.app.conn
            else:
                raise ConnectionError("Database connection is not available. Please restart the application.")

        try:
            self.conn.commit()
        except Exception as e:
            raise ConnectionError(f"Failed to commit database changes: {e}")

    def create_grades_content(self):
        """Create grades management content"""
        # Top controls frame
        top_controls = ttk.Frame(self.content_frame)
        top_controls.pack(fill='x', padx=10, pady=5)

        # Left side controls
        left_controls = ttk.Frame(top_controls)
        left_controls.pack(side='left', fill='x', expand=True)

        ttk.Button(left_controls, text="Add Grade",
                  command=self.add_grade_dialog).pack(side='left', padx=5)
        ttk.Button(left_controls, text="Edit Grade",
                  command=self.edit_grade_dialog).pack(side='left', padx=5)
        ttk.Button(left_controls, text="Delete Grade",
                  command=self.delete_grade).pack(side='left', padx=5)
        ttk.Button(left_controls, text="Import Grades",
                  command=self.import_grades).pack(side='left', padx=5)
        ttk.Button(left_controls, text="Batch Entry",
                  command=self.batch_grade_entry).pack(side='left', padx=5)

        # Right side controls
        right_controls = ttk.Frame(top_controls)
        right_controls.pack(side='right')

        ttk.Button(right_controls, text="Calculate GPAs",
                  command=self.calculate_all_gpas).pack(side='left', padx=5)
        ttk.Button(right_controls, text="Grade Statistics",
                  command=self.show_grade_statistics).pack(side='left', padx=5)
        ttk.Button(right_controls, text="Refresh",
                  command=self.refresh_grades).pack(side='left', padx=5)

        # Filter frame
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(filter_frame, text="Student:").pack(side='left', padx=5)
        self.grade_student_filter_var = tk.StringVar()
        self.grade_student_combo = ttk.Combobox(filter_frame,
                                               textvariable=self.grade_student_filter_var,
                                               width=25, state='readonly')
        self.grade_student_combo.pack(side='left', padx=5)
        self.grade_student_combo.bind('<<ComboboxSelected>>', self.filter_grades)

        ttk.Label(filter_frame, text="Assessment:").pack(side='left', padx=5)
        self.grade_assessment_filter_var = tk.StringVar()
        self.grade_assessment_combo = ttk.Combobox(filter_frame,
                                                  textvariable=self.grade_assessment_filter_var,
                                                  width=25, state='readonly')
        self.grade_assessment_combo.pack(side='left', padx=5)
        self.grade_assessment_combo.bind('<<ComboboxSelected>>', self.filter_grades)

        ttk.Button(filter_frame, text="Clear Filters",
                  command=self.clear_grade_filters).pack(side='left', padx=20)

        # Grades list
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('ID', 'Student', 'Assessment', 'Score', 'Max Points', 'Percentage', 'Letter Grade', 'Date')
        self.grades_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=22)

        for col in columns:
            self.grades_tree.heading(col, text=col)
            if col == 'Student' or col == 'Assessment':
                self.grades_tree.column(col, width=150, anchor='w')
            else:
                self.grades_tree.column(col, width=100, anchor='center')

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.grades_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=self.grades_tree.xview)
        self.grades_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.grades_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')

        # Double-click on an exam-source row ('E' prefix) hands off to
        # the exam scheduler's Results dialog so re-grading goes through
        # the canonical writeback (audit log, student_modules update,
        # accommodations) instead of a generic UPDATE.
        self.grades_tree.bind("<Double-1>", self._on_grade_row_double_click)

        # Load grades data
        self.refresh_grades()

        # Populate filter combos now that they exist
        self.populate_filter_combos()


    def percentage_to_letter(self, percentage):
        """Convert percentage to letter grade"""
        if percentage >= 93:
            return 'A+'
        elif percentage >= 90:
            return 'A'
        elif percentage >= 87:
            return 'A-'
        elif percentage >= 83:
            return 'B+'
        elif percentage >= 80:
            return 'B'
        elif percentage >= 77:
            return 'B-'
        elif percentage >= 73:
            return 'C+'
        elif percentage >= 70:
            return 'C'
        elif percentage >= 67:
            return 'C-'
        elif percentage >= 63:
            return 'D+'
        elif percentage >= 60:
            return 'D'
        elif percentage >= 57:
            return 'D-'
        else:
            return 'F'


    def letter_to_gpa(self, letter_grade):
        """Convert letter grade to GPA points"""
        grade_map = {
            'A+': 4.3, 'A': 4.0, 'A-': 3.7,
            'B+': 3.3, 'B': 3.0, 'B-': 2.7,
            'C+': 2.3, 'C': 2.0, 'C-': 1.7,
            'D+': 1.3, 'D': 1.0, 'D-': 0.7,
            'F': 0.0
        }
        return grade_map.get(letter_grade, 0.0)

    def _email_grade_notification(self, student_id, assessment_name, action, score=None,
                                   letter_grade=None, percentage=None, feedback=None):
        """Email a student about a grade change (added/updated/removed)."""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            cursor = self.get_safe_cursor()
            cursor.execute(
                "SELECT first_name, last_name, email_address FROM students WHERE student_id = ?",
                (student_id,)
            )
            row = cursor.fetchone()
            if not row or not row[2]:
                return

            name = f"{row[0]} {row[1]}"
            email = row[2]

            if action == 'added':
                subject = f"Grade Released: {assessment_name}"
                body = (
                    f"Dear {name},\n\n"
                    f"A grade has been released for the following assessment:\n\n"
                    f"Assessment: {assessment_name}\n"
                    f"Score: {score} ({percentage:.1f}%)\n"
                    f"Letter Grade: {letter_grade}\n"
                )
                if feedback:
                    body += f"\nFeedback:\n{feedback}\n"
                body += "\nPlease log in to view your full results.\n\nBest regards,\nAcademic Administration"

            elif action == 'updated':
                subject = f"Grade Updated: {assessment_name}"
                body = (
                    f"Dear {name},\n\n"
                    f"Your grade has been updated for the following assessment:\n\n"
                    f"Assessment: {assessment_name}\n"
                    f"New Score: {score} ({percentage:.1f}%)\n"
                    f"Letter Grade: {letter_grade}\n"
                )
                if feedback:
                    body += f"\nFeedback:\n{feedback}\n"
                body += "\nPlease log in to view your updated results.\n\nBest regards,\nAcademic Administration"

            elif action == 'deleted':
                subject = f"Grade Removed: {assessment_name}"
                body = (
                    f"Dear {name},\n\n"
                    f"Your grade for the following assessment has been removed:\n\n"
                    f"Assessment: {assessment_name}\n\n"
                    f"If you believe this is an error, please contact your instructor.\n\n"
                    f"Best regards,\nAcademic Administration"
                )
            else:
                return

            send_email(recipient_email=email, subject=subject, body=body)

        except Exception as e:
            print(f"Grade notification email failed: {e}")

    def add_grade_dialog(self, prefill_student_id=None,
                         prefill_module_code=None, prefill_comments=None):
        """Open dialog to add a new grade — shows student's submitted assignments.

        Optional kwargs let callers (e.g. the absence tracker's grade-penalty
        workflow) jump straight to the right student/module with a pre-filled
        comment. Pass None for any to leave it blank.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Grade")
        dialog.geometry("550x650")
        dialog.transient(self.root)
        safe_grab_set(dialog)

        # Shared state for assessment data lookup
        assessments = []

        # Student selection
        ttk.Label(dialog, text="Student:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        student_var = tk.StringVar()
        student_combo = ttk.Combobox(dialog, textvariable=student_var, width=40, state='readonly')
        student_combo.grid(row=0, column=1, padx=10, pady=10)

        # Load students
        try:
            cursor = self.get_safe_cursor()
            cursor.execute("SELECT student_id, first_name, last_name FROM students ORDER BY last_name")
            students = cursor.fetchall()
            student_combo['values'] = [f"{s[0]} - {s[1]} {s[2]}" for s in students]
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading students: {e}", parent=dialog)
            dialog.destroy()
            return

        # Assessment selection (populated when student is selected)
        ttk.Label(dialog, text="Assessment:").grid(row=1, column=0, padx=10, pady=10, sticky='w')
        assessment_var = tk.StringVar()
        assessment_combo = ttk.Combobox(dialog, textvariable=assessment_var, width=40, state='readonly')
        assessment_combo.grid(row=1, column=1, padx=10, pady=10)

        # Status label to show what's loaded
        status_var = tk.StringVar(value="Select a student to see their submissions")
        ttk.Label(dialog, textvariable=status_var, foreground='#1565c0').grid(
            row=2, column=0, columnspan=2, padx=10, sticky='w')

        def on_student_selected(event=None):
            """When a student is selected, load their submitted assignments"""
            nonlocal assessments
            assessments = []
            assessment_combo.set('')
            assessment_combo['values'] = []
            max_points_var.set("Select an assessment")

            selected = student_var.get()
            if not selected:
                return

            student_id = selected.split(' - ')[0]

            try:
                cursor = self.get_safe_cursor()

                # Get assignments this student has submitted (from assignment_submissions)
                cursor.execute("""
                    SELECT
                        'A' || a.id as assessment_id,
                        a.title as name,
                        COALESCE(a.max_marks, 100) as max_points,
                        a.module_code,
                        sub.submission_date,
                        CASE WHEN sub.grade IS NOT NULL THEN 'Graded' ELSE 'Submitted' END as status
                    FROM assignment_submissions sub
                    JOIN assignments a ON sub.assignment_id = a.id
                    WHERE sub.student_id = ?
                    ORDER BY sub.submission_date DESC
                """, (student_id,))
                submitted_assignments = cursor.fetchall()

                # Also get assessments from assessments table for this student's modules
                cursor.execute("""
                    SELECT a.assessment_id, a.assessment_name, a.max_points, a.module_code,
                           a.due_date, 'Assessment' as status
                    FROM assessments a
                    JOIN student_modules sm ON a.module_code = sm.module_code
                    WHERE sm.student_id = ?
                    ORDER BY a.due_date DESC
                """, (student_id,))
                module_assessments = cursor.fetchall()

                all_items = list(submitted_assignments) + list(module_assessments)
                assessments = all_items

                if not all_items:
                    status_var.set(f"No submissions or assessments found for this student")
                    return

                # Format: "A438 - Assignment Title (CIS0001) [Submitted]"
                display_list = []
                for a in all_items:
                    aid, name, max_pts, module, date_val, st = a
                    display_list.append(f"{aid} - {name} ({module}) [{st}] - Max: {max_pts}")

                assessment_combo['values'] = display_list
                submitted_count = len(submitted_assignments)
                assessment_count = len(module_assessments)
                status_var.set(
                    f"Found {submitted_count} submission(s), {assessment_count} assessment(s)")

            except sqlite3.Error as e:
                status_var.set(f"Error loading: {e}")

        student_combo.bind('<<ComboboxSelected>>', on_student_selected)

        # Score entry
        ttk.Label(dialog, text="Score:").grid(row=3, column=0, padx=10, pady=10, sticky='w')
        score_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=score_var, width=42).grid(row=3, column=1, padx=10, pady=10)

        # Max points display
        max_points_var = tk.StringVar(value="Select an assessment")
        ttk.Label(dialog, text="Max Points:").grid(row=4, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(dialog, textvariable=max_points_var).grid(row=4, column=1, padx=10, pady=10, sticky='w')

        def update_max_points(event=None):
            selected = assessment_var.get()
            if selected:
                aid = selected.split(' - ')[0]
                for a in assessments:
                    if str(a[0]) == aid:
                        max_points_var.set(str(a[2]))
                        break

        assessment_combo.bind('<<ComboboxSelected>>', update_max_points)

        # Date
        ttk.Label(dialog, text="Date:").grid(row=5, column=0, padx=10, pady=10, sticky='w')
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(dialog, textvariable=date_var, width=42).grid(row=5, column=1, padx=10, pady=10)

        # Comments
        ttk.Label(dialog, text="Comments:").grid(row=6, column=0, padx=10, pady=10, sticky='nw')
        comments_text = tk.Text(dialog, width=40, height=8)
        comments_text.grid(row=6, column=1, padx=10, pady=10)

        def save_grade():
            student_id = student_var.get().split(' - ')[0] if student_var.get() else None
            assessment_id = assessment_var.get().split(' - ')[0] if assessment_var.get() else None
            score = score_var.get()
            date = date_var.get()
            comments = comments_text.get('1.0', 'end-1c')

            if not student_id:
                messagebox.showerror("Validation Error", "Please select a student", parent=dialog)
                return
            if not assessment_id:
                messagebox.showerror("Validation Error", "Please select an assessment", parent=dialog)
                return
            if not score:
                messagebox.showerror("Validation Error", "Please enter a score", parent=dialog)
                return

            # Submission-window gate (#5). Block grade entries outside the
            # active submission_window unless the user has an explicit
            # override permission. Soft-fails open if the calendar has
            # no submission_window defined (no period configured = no
            # restriction yet).
            try:
                from education_system.university_system.modules.domain.academics.gui._cross_services import (
                    current_period,
                )
                window_today = current_period("submission_window")
                if window_today is None:
                    # If a window exists for this term but today isn't in it,
                    # we can still detect that by querying with the entry date.
                    window_for_entry = current_period("submission_window", on_date=date)
                    if window_for_entry is None:
                        # Need to know whether *any* submission_window is on
                        # the calendar: if not, soft-fail open.
                        from education_system.university_system.infrastructure.database.db import get_connection
                        with get_connection() as conn:
                            row = conn.execute(
                                "SELECT 1 FROM academic_calendar_events "
                                "WHERE LOWER(event_type) = 'submission_window' "
                                "LIMIT 1"
                            ).fetchone()
                        if row:
                            override = False
                            try:
                                if (hasattr(self.app, 'auth') and self.app.auth
                                        and self.app.auth.current_user
                                        and self.app.auth.check_permission(
                                            'override_submission_window')):
                                    override = True
                            except Exception:
                                pass
                            if not override:
                                messagebox.showerror(
                                    "Submission window closed",
                                    "Grade entries are only allowed during "
                                    "the active submission window. Update "
                                    "the calendar or request an override.",
                                    parent=dialog,
                                )
                                return
            except Exception:
                # Never block grading on a calendar-gate failure.
                pass

            try:
                score_float = float(score)
                max_points = float(max_points_var.get())

                if score_float < 0:
                    messagebox.showerror("Validation Error", "Score cannot be negative", parent=dialog)
                    return
                if score_float > max_points:
                    messagebox.showerror("Validation Error",
                                        f"Score cannot exceed max points ({max_points})", parent=dialog)
                    return

                percentage = (score_float / max_points) * 100
                letter_grade = self.percentage_to_letter(percentage)

                cursor = self.get_safe_cursor()
                is_assignment = str(assessment_id).startswith('A')

                if is_assignment:
                    real_id = int(assessment_id[1:])

                    # Check for existing submission
                    cursor.execute(
                        "SELECT id FROM assignment_submissions WHERE assignment_id = ? AND student_id = ?",
                        (real_id, student_id))
                    existing = cursor.fetchone()

                    grader_id = None
                    if hasattr(self.app, 'auth') and self.app.auth and self.app.auth.current_user:
                        grader_id = self.app.auth.current_user.get('id')

                    if existing:
                        cursor.execute("""
                            UPDATE assignment_submissions
                            SET grade = ?, feedback = ?, graded_date = ?,
                                graded_by = ?, status = 'graded'
                            WHERE id = ?
                        """, (percentage, comments, date, grader_id, existing[0]))
                    else:
                        cursor.execute("""
                            INSERT INTO assignment_submissions
                            (assignment_id, student_id, grade, feedback, graded_date, status,
                             submission_date, file_name, file_path)
                            VALUES (?, ?, ?, ?, ?, 'graded', ?, 'grade_entry', '')
                        """, (real_id, student_id, percentage, comments, date, date))
                else:
                    cursor.execute("""
                        INSERT INTO grades (student_id, assessment_id, score, letter_grade,
                                           submission_date, comments)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (student_id, assessment_id, score_float, letter_grade, date, comments))

                self.safe_commit()

                if IMMUTABLE_AUDIT_AVAILABLE:
                    user_id, session_id = get_gui_context()
                    safe_log_security_event(
                        action=AuditAction.RECORD_CREATE,
                        user_id=user_id,
                        resource_type='grade',
                        resource_id=str(student_id),
                        session_id=session_id,
                        details={
                            'student_id': student_id,
                            'assessment_id': assessment_id,
                            'score': score_float,
                            'letter_grade': letter_grade
                        }
                    )

                # Get assessment name for email
                sel_text = assessment_var.get()
                a_name = sel_text.split(' - ')[1].split(' (')[0] if ' - ' in sel_text else sel_text

                # Broadcast to sibling GUIs.
                try:
                    from education_system.university_system.modules.domain.academics.gui._event_bus import (
                        publish, EVENT_GRADE_CHANGED,
                    )
                    publish(EVENT_GRADE_CHANGED,
                            student_id=student_id, assessment_id=assessment_id,
                            action="create")
                except Exception:
                    pass

                messagebox.showinfo("Success", "Grade added successfully!", parent=dialog)
                dialog.destroy()
                self.refresh_grades()

                # Email student about released grade
                self._email_grade_notification(
                    student_id, a_name, 'added',
                    score=score_float, letter_grade=letter_grade,
                    percentage=percentage, feedback=comments
                )

            except ValueError:
                messagebox.showerror("Validation Error", "Score must be a valid number", parent=dialog)
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error saving grade: {e}", parent=dialog)

        ttk.Button(dialog, text="Save Grade", command=save_grade).grid(row=7, column=0, columnspan=2, pady=15)

        # Prefill: pick student, load their assessments, optionally filter
        # by module, and seed the comments field. Done last so all combos
        # and bound handlers exist.
        if prefill_student_id:
            try:
                match = next(
                    (v for v in student_combo['values']
                     if v.startswith(f"{prefill_student_id} - ")),
                    None)
                if match:
                    student_var.set(match)
                    on_student_selected()
                    if prefill_module_code and assessments:
                        filtered = [
                            f"{a[0]} - {a[1]} ({a[3]}) [{a[5]}] - Max: {a[2]}"
                            for a in assessments
                            if str(a[3]) == str(prefill_module_code)
                        ]
                        if filtered:
                            assessment_combo['values'] = filtered
                            assessment_combo.set(filtered[0])
                            update_max_points()
            except Exception:
                pass
        if prefill_comments:
            try:
                comments_text.delete('1.0', 'end')
                comments_text.insert('1.0', prefill_comments)
            except Exception:
                pass

    def edit_grade_dialog(self):
        """Open dialog to edit selected grade (supports both grades and assignment_submissions)"""
        selection = self.grades_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a grade to edit")
            return

        item = self.grades_tree.item(selection[0])
        grade_id = str(item['values'][0])
        is_submission = grade_id.startswith('S')

        # Fetch grade details from the correct source
        try:
            cursor = self.get_safe_cursor()

            if is_submission:
                real_id = int(grade_id[1:])
                cursor.execute("""
                    SELECT sub.id, sub.student_id, a.id, sub.grade,
                           sub.graded_date, sub.feedback,
                           s.first_name, s.last_name, a.title,
                           COALESCE(a.max_marks, 100), a.module_code
                    FROM assignment_submissions sub
                    JOIN students s ON sub.student_id = s.student_id
                    JOIN assignments a ON sub.assignment_id = a.id
                    WHERE sub.id = ?
                """, (real_id,))
            else:
                cursor.execute("""
                    SELECT g.grade_id, g.student_id, g.assessment_id, g.score,
                           g.submission_date, g.comments,
                           s.first_name, s.last_name, a.assessment_name,
                           a.max_points, m.module_name
                    FROM grades g
                    JOIN students s ON g.student_id = s.student_id
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    JOIN modules m ON a.module_code = m.module_code
                    WHERE g.grade_id = ?
                """, (grade_id,))

            grade_data = cursor.fetchone()

            if not grade_data:
                messagebox.showerror("Error", "Grade not found")
                return

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading grade: {e}")
            return

        # For submissions, grade_data[3] is a percentage; for grades, it's a raw score
        if is_submission:
            current_score = grade_data[3] if grade_data[3] is not None else 0
            max_points = grade_data[9]
            # Convert percentage back to score for display
            display_score = round((current_score * max_points) / 100, 2) if current_score else 0
        else:
            display_score = grade_data[3]
            max_points = grade_data[9]

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Grade")
        dialog.geometry("500x550")
        dialog.transient(self.root)
        safe_grab_set(dialog)

        ttk.Label(dialog, text="Student:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(dialog, text=f"{grade_data[1]} - {grade_data[6]} {grade_data[7]}").grid(
            row=0, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(dialog, text="Assessment:").grid(row=1, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(dialog, text=f"{grade_data[8]} ({grade_data[10]})").grid(
            row=1, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(dialog, text="Max Points:").grid(row=2, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(dialog, text=str(max_points)).grid(row=2, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(dialog, text="Score:").grid(row=3, column=0, padx=10, pady=10, sticky='w')
        score_var = tk.StringVar(value=str(display_score))
        ttk.Entry(dialog, textvariable=score_var, width=37).grid(row=3, column=1, padx=10, pady=10)

        ttk.Label(dialog, text="Date:").grid(row=4, column=0, padx=10, pady=10, sticky='w')
        date_var = tk.StringVar(value=grade_data[4] if grade_data[4] else datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(dialog, textvariable=date_var, width=37).grid(row=4, column=1, padx=10, pady=10)

        ttk.Label(dialog, text="Comments:").grid(row=5, column=0, padx=10, pady=10, sticky='nw')
        comments_text = tk.Text(dialog, width=35, height=8)
        comments_text.grid(row=5, column=1, padx=10, pady=10)
        if grade_data[5]:
            comments_text.insert('1.0', grade_data[5])

        def update_grade():
            score = score_var.get()
            date = date_var.get()
            comments = comments_text.get('1.0', 'end-1c')

            if not score:
                messagebox.showerror("Validation Error", "Please enter a score", parent=dialog)
                return

            try:
                score_float = float(score)
                max_pts = float(max_points)

                if score_float < 0 or score_float > max_pts:
                    messagebox.showerror("Validation Error",
                                        f"Score must be between 0 and {max_pts}", parent=dialog)
                    return

                percentage = (score_float / max_pts) * 100
                letter_grade = self.percentage_to_letter(percentage)
                old_score = grade_data[3]

                cursor = self.get_safe_cursor()

                if is_submission:
                    cursor.execute("""
                        UPDATE assignment_submissions
                        SET grade = ?, feedback = ?, graded_date = ?, status = 'graded'
                        WHERE id = ?
                    """, (percentage, comments, date, int(grade_id[1:])))
                else:
                    cursor.execute("""
                        UPDATE grades
                        SET score = ?, letter_grade = ?, submission_date = ?, comments = ?
                        WHERE grade_id = ?
                    """, (score_float, letter_grade, date, comments, grade_id))

                self.safe_commit()

                # Immutable audit log for grade update (FERPA compliance)
                if IMMUTABLE_AUDIT_AVAILABLE:
                    user_id, session_id = get_gui_context()
                    safe_log_security_event(
                        action=AuditAction.RECORD_UPDATE,
                        user_id=user_id,
                        resource_type='grade',
                        resource_id=str(grade_id),
                        session_id=session_id,
                        details={
                            'student_id': str(grade_data[1]),
                            'assessment_id': str(grade_data[2]),
                            'old_score': old_score,
                            'new_score': score_float,
                            'new_letter_grade': letter_grade
                        }
                    )

                messagebox.showinfo("Success", "Grade updated successfully!")
                dialog.destroy()
                self.refresh_grades()

                # Email student about updated grade
                self._email_grade_notification(
                    str(grade_data[1]), str(grade_data[8]), 'updated',
                    score=score_float, letter_grade=letter_grade,
                    percentage=percentage, feedback=comments
                )

            except ValueError:
                messagebox.showerror("Validation Error", "Score must be a valid number")
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error updating grade: {e}")

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Update", command=update_grade).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def delete_grade(self):
        """Delete selected grade (supports both grades and assignment_submissions)"""
        selection = self.grades_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a grade to delete")
            return

        item = self.grades_tree.item(selection[0])
        raw_id = str(item['values'][0])
        student_name = item['values'][1]
        assessment_name = item['values'][2]
        is_submission = raw_id.startswith('S')

        if not messagebox.askyesno("Confirm Deletion",
                                   f"Are you sure you want to delete the grade for:\n\n"
                                   f"Student: {student_name}\n"
                                   f"Assessment: {assessment_name}\n\n"
                                   f"This action cannot be undone."):
            return

        try:
            cursor = self.get_safe_cursor()
            student_id_for_email = None

            if is_submission:
                real_id = int(raw_id[1:])
                cursor.execute("SELECT student_id FROM assignment_submissions WHERE id = ?", (real_id,))
                row = cursor.fetchone()
                student_id_for_email = row[0] if row else None
                # Clear the grade but keep the submission record
                cursor.execute("""
                    UPDATE assignment_submissions
                    SET grade = NULL, feedback = NULL, graded_date = NULL,
                        graded_by = NULL, status = 'submitted'
                    WHERE id = ?
                """, (real_id,))
            else:
                cursor.execute("SELECT student_id FROM grades WHERE grade_id = ?", (raw_id,))
                row = cursor.fetchone()
                student_id_for_email = row[0] if row else None
                cursor.execute("DELETE FROM grades WHERE grade_id = ?", (raw_id,))

            self.safe_commit()

            # Immutable audit log for grade deletion (FERPA compliance)
            if IMMUTABLE_AUDIT_AVAILABLE:
                user_id, session_id = get_gui_context()
                safe_log_security_event(
                    action=AuditAction.RECORD_DELETE,
                    user_id=user_id,
                    resource_type='grade',
                    resource_id=raw_id,
                    session_id=session_id,
                    details={
                        'student_id': student_id_for_email,
                        'student_name': student_name,
                        'assessment_name': assessment_name
                    }
                )

            messagebox.showinfo("Success", "Grade deleted successfully!")
            self.refresh_grades()

            # Email student about removed grade
            if student_id_for_email:
                self._email_grade_notification(student_id_for_email, assessment_name, 'deleted')

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error deleting grade: {e}")

    def import_grades(self):
        """Import grades from CSV file"""
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            original_filename = os.path.basename(file_path)

            # Security: Validate file before processing
            if SECURE_UPLOAD_AVAILABLE and validate_upload:
                try:
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    validation = validate_upload(original_filename, file_content, category='data')
                    if not validation['valid']:
                        messagebox.showerror(
                            "Security Error",
                            f"File validation failed: {validation['error']}"
                        )
                        if ACTIVITY_LOGGER_AVAILABLE:
                            log_activity(
                                'security_blocked',
                                'grade_import',
                                filename=original_filename,
                                reason=validation['error']
                            )
                        return
                except Exception as e:
                    print(f"⚠️ File validation warning: {e}")

            imported = 0
            errors = []

            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                # Expected columns: student_id, assessment_id, score, submission_date, comments
                required_columns = ['student_id', 'assessment_id', 'score']

                # Check if required columns exist
                if not all(col in reader.fieldnames for col in required_columns):
                    messagebox.showerror("Import Error",
                                       f"CSV must contain columns: {', '.join(required_columns)}\n"
                                       f"Found columns: {', '.join(reader.fieldnames)}")
                    return

                cursor = self.get_safe_cursor()

                for row_num, row in enumerate(reader, start=2):
                    try:
                        student_id = row['student_id'].strip()
                        assessment_id = row['assessment_id'].strip()
                        score = float(row['score'])
                        submission_date = row.get('submission_date', datetime.now().strftime('%Y-%m-%d')).strip()
                        comments = row.get('comments', '').strip()

                        # Verify student exists
                        cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
                        if not cursor.fetchone():
                            errors.append(f"Row {row_num}: Student {student_id} not found")
                            continue

                        # Verify assessment exists and get max points
                        cursor.execute("SELECT max_points FROM assessments WHERE assessment_id = ?", (assessment_id,))
                        result = cursor.fetchone()
                        if not result:
                            errors.append(f"Row {row_num}: Assessment {assessment_id} not found")
                            continue

                        max_points = result[0]

                        # Validate score
                        if score < 0 or score > max_points:
                            errors.append(f"Row {row_num}: Invalid score {score} (max: {max_points})")
                            continue

                        # Calculate letter grade
                        percentage = (score / max_points) * 100
                        letter_grade = self.percentage_to_letter(percentage)

                        # Check if grade already exists
                        cursor.execute("""
                            SELECT grade_id FROM grades
                            WHERE student_id = ? AND assessment_id = ?
                        """, (student_id, assessment_id))

                        if cursor.fetchone():
                            # Update existing grade
                            cursor.execute("""
                                UPDATE grades
                                SET score = ?, letter_grade = ?, submission_date = ?, comments = ?
                                WHERE student_id = ? AND assessment_id = ?
                            """, (score, letter_grade, submission_date, comments, student_id, assessment_id))
                        else:
                            # Insert new grade
                            cursor.execute("""
                                INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date, comments)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (student_id, assessment_id, score, letter_grade, submission_date, comments))

                        imported += 1

                    except ValueError as e:
                        errors.append(f"Row {row_num}: Invalid number format - {e}")
                    except sqlite3.Error as e:
                        errors.append(f"Row {row_num}: Database error - {e}")

                self.safe_commit()

                # Immutable audit log for bulk grade import (FERPA compliance)
                if IMMUTABLE_AUDIT_AVAILABLE and imported > 0:
                    user_id, session_id = get_gui_context()
                    safe_log_security_event(
                        action=AuditAction.BULK_UPDATE,
                        user_id=user_id,
                        resource_type='grade',
                        session_id=session_id,
                        details={
                            'operation': 'import_grades',
                            'count': imported,
                            'filename': original_filename,
                            'errors': len(errors)
                        }
                    )

            # Show results
            result_msg = f"Successfully imported {imported} grade(s)"
            if errors:
                result_msg += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:10])
                if len(errors) > 10:
                    result_msg += f"\n... and {len(errors) - 10} more errors"
                messagebox.showwarning("Import Completed with Errors", result_msg)
            else:
                messagebox.showinfo("Import Successful", result_msg)

            self.refresh_grades()

        except Exception as e:
            messagebox.showerror("Import Error", f"Error reading CSV file: {e}")

    def batch_grade_entry(self):
        """Open batch grade entry dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Batch Grade Entry")
        dialog.geometry("900x600")

        # Make dialog modal
        dialog.transient(self.root)
        safe_grab_set(dialog)

        # Assessment selection
        top_frame = ttk.Frame(dialog)
        top_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(top_frame, text="Assessment:").pack(side='left', padx=5)
        assessment_var = tk.StringVar()
        assessment_combo = ttk.Combobox(top_frame, textvariable=assessment_var, width=40, state='readonly')
        assessment_combo.pack(side='left', padx=5)

        # Load assessments (from both assessments and assignments tables)
        try:
            cursor = self.get_safe_cursor()
            # Query assessments table
            cursor.execute("""
                SELECT a.assessment_id, a.assessment_name, a.max_points, m.module_name
                FROM assessments a
                JOIN modules m ON a.module_code = m.module_code
                ORDER BY m.module_name, a.assessment_name
            """)
            assessments_from_assessments = cursor.fetchall()

            # Query assignments table (which might have been created via assignment GUI)
            cursor.execute("""
                SELECT
                    'A' || a.id as assessment_id,
                    a.title as assessment_name,
                    COALESCE(a.max_marks, 100) as max_points,
                    m.module_name
                FROM assignments a
                JOIN modules m ON a.module_code = m.module_code
                ORDER BY m.module_name, a.title
            """)
            assessments_from_assignments = cursor.fetchall()

            # Combine both sources
            all_assessments = list(assessments_from_assessments) + list(assessments_from_assignments)
            assessments = all_assessments
            assessment_list = [f"{a[0]} - {a[1]} ({a[3]}) - Max: {a[2]}" for a in assessments]
            assessment_combo['values'] = assessment_list
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading assessments: {e}")
            dialog.destroy()
            return

        # Max points display
        max_points_var = tk.StringVar(value="Select an assessment")
        ttk.Label(top_frame, text="Max Points:").pack(side='left', padx=10)
        ttk.Label(top_frame, textvariable=max_points_var).pack(side='left', padx=5)

        # Student list with score entry
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('Student ID', 'Name', 'Score', 'Percentage', 'Letter Grade')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Name':
                tree.column(col, width=200, anchor='w')
            else:
                tree.column(col, width=100, anchor='center')

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=v_scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')

        # Store scores
        scores_dict = {}

        def load_students():
            """Load enrolled students for selected assessment"""
            tree.delete(*tree.get_children())
            scores_dict.clear()

            selected = assessment_var.get()
            if not selected:
                return

            assessment_id = selected.split(' - ')[0]

            # Get max points
            for a in assessments:
                if str(a[0]) == assessment_id:
                    max_points_var.set(str(a[2]))
                    break

            try:
                # Get students enrolled in the module
                cursor.execute("""
                    SELECT DISTINCT s.student_id, s.first_name, s.last_name, g.score
                    FROM students s
                    JOIN student_modules sm ON s.student_id = sm.student_id
                    JOIN assessments a ON sm.module_code = a.module_code
                    LEFT JOIN grades g ON s.student_id = g.student_id AND g.assessment_id = a.assessment_id
                    WHERE a.assessment_id = ?
                    ORDER BY s.last_name, s.first_name
                """, (assessment_id,))

                students = cursor.fetchall()

                for student in students:
                    student_id = student[0]
                    name = f"{student[1]} {student[2]}"
                    score = student[3] if student[3] is not None else ''

                    # Calculate percentage and letter grade if score exists
                    percentage = ''
                    letter_grade = ''
                    if score:
                        max_pts = float(max_points_var.get())
                        percentage = f"{(score / max_pts) * 100:.2f}%"
                        letter_grade = self.percentage_to_letter((score / max_pts) * 100)

                    tree.insert('', 'end', values=(student_id, name, score, percentage, letter_grade))
                    scores_dict[student_id] = score if score else ''

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error loading students: {e}")

        assessment_combo.bind('<<ComboboxSelected>>', lambda e: load_students())

        # Edit score on double-click
        def edit_score(event):
            selection = tree.selection()
            if not selection:
                return

            item = tree.item(selection[0])
            student_id = item['values'][0]
            current_score = item['values'][2]

            # Create simple dialog to enter score
            score_dialog = tk.Toplevel(dialog)
            score_dialog.title("Enter Score")
            score_dialog.geometry("300x150")
            score_dialog.transient(dialog)
            safe_grab_set(score_dialog)

            ttk.Label(score_dialog, text=f"Student: {item['values'][1]}").pack(pady=10)
            ttk.Label(score_dialog, text=f"Max Points: {max_points_var.get()}").pack(pady=5)

            ttk.Label(score_dialog, text="Score:").pack(pady=5)
            score_var = tk.StringVar(value=str(current_score) if current_score else '')
            score_entry = ttk.Entry(score_dialog, textvariable=score_var, width=20)
            score_entry.pack(pady=5)
            score_entry.focus()

            def save_score():
                try:
                    score_text = score_var.get().strip()
                    if score_text:
                        score = float(score_text)
                        max_pts = float(max_points_var.get())

                        if score < 0 or score > max_pts:
                            messagebox.showerror("Invalid Score", f"Score must be between 0 and {max_pts}")
                            return

                        percentage = (score / max_pts) * 100
                        letter_grade = self.percentage_to_letter(percentage)

                        # Update tree
                        tree.item(selection[0], values=(
                            student_id, item['values'][1], score,
                            f"{percentage:.2f}%", letter_grade
                        ))
                        scores_dict[student_id] = score
                    else:
                        # Clear score
                        tree.item(selection[0], values=(
                            student_id, item['values'][1], '', '', ''
                        ))
                        scores_dict[student_id] = ''

                    score_dialog.destroy()

                except ValueError:
                    messagebox.showerror("Invalid Input", "Please enter a valid number")

            ttk.Button(score_dialog, text="Save", command=save_score).pack(pady=10)

        tree.bind('<Double-1>', edit_score)

        # Save all button
        def save_all_grades():
            selected = assessment_var.get()
            if not selected:
                messagebox.showwarning("No Assessment", "Please select an assessment")
                return

            assessment_id = selected.split(' - ')[0]
            max_pts = float(max_points_var.get())

            saved_count = 0
            try:
                cursor = self.get_safe_cursor()

                for student_id, score in scores_dict.items():
                    if score != '' and score is not None:
                        percentage = (float(score) / max_pts) * 100
                        letter_grade = self.percentage_to_letter(percentage)

                        # Check if grade exists
                        cursor.execute("""
                            SELECT grade_id FROM grades
                            WHERE student_id = ? AND assessment_id = ?
                        """, (student_id, assessment_id))

                        if cursor.fetchone():
                            # Update
                            cursor.execute("""
                                UPDATE grades
                                SET score = ?, letter_grade = ?, submission_date = ?
                                WHERE student_id = ? AND assessment_id = ?
                            """, (score, letter_grade, datetime.now().strftime('%Y-%m-%d'),
                                 student_id, assessment_id))
                        else:
                            # Insert
                            cursor.execute("""
                                INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
                                VALUES (?, ?, ?, ?, ?)
                            """, (student_id, assessment_id, score, letter_grade,
                                 datetime.now().strftime('%Y-%m-%d')))

                        saved_count += 1

                self.safe_commit()
                messagebox.showinfo("Success", f"Saved {saved_count} grade(s) successfully!")
                dialog.destroy()
                self.refresh_grades()

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error saving grades: {e}")

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(button_frame, text="Save All Grades", command=save_all_grades).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def calculate_all_gpas(self):
        """Calculate GPAs for all students.

        Delegates per-student GPA math to
        ``grading.grade_calculation.gpa.calculate_student_gpa`` so the
        formula stays in one place; this method only handles the loop
        and the result-dialog rendering.
        """
        try:
            from education_system.university_system.modules.domain.academics.grading.grade_calculation.gpa import (
                calculate_student_gpa,
            )
            from education_system.university_system.modules.domain.academics.gui.grade_tracking.integrations import (
                push_grade_kpi,
                notify_aid_of_gpa,
            )

            cursor = self.get_safe_cursor()
            cursor.execute("SELECT student_id, first_name, last_name FROM students")
            students = cursor.fetchall()

            results = []
            updated_count = 0
            gpa_values: list[float] = []

            for student in students:
                student_id = student[0]
                name = f"{student[1]} {student[2]}"

                gpa, credits, _ = calculate_student_gpa(cursor, student_id)
                if gpa is None:
                    results.append(f"{name}: No grades found")
                    continue

                results.append(f"{name}: GPA = {gpa:.2f} ({credits} module(s))")
                updated_count += 1
                gpa_values.append(gpa)

                # Cross-domain side-effect: tag the student's aid record(s)
                # with the latest GPA so financial_aid reviewers see the
                # number that's gating their scholarship eligibility.
                try:
                    notify_aid_of_gpa(student_id=student_id, gpa=gpa)
                except Exception:
                    pass

            self.safe_commit()

            # Best-effort KPI push — silent when no matching KPI exists
            if gpa_values:
                try:
                    push_grade_kpi(
                        "Average GPA", sum(gpa_values) / len(gpa_values),
                    )
                    pass_rate = (
                        sum(1 for g in gpa_values if g >= 2.0) / len(gpa_values) * 100.0
                    )
                    push_grade_kpi("Pass Rate %", pass_rate)
                except Exception:
                    pass

            # Show results dialog
            result_dialog = tk.Toplevel(self.root)
            result_dialog.title("GPA Calculation Results")
            result_dialog.geometry("500x600")

            ttk.Label(result_dialog, text=f"Calculated GPAs for {updated_count} students",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Results text area
            text_frame = ttk.Frame(result_dialog)
            text_frame.pack(fill='both', expand=True, padx=10, pady=10)

            text_widget = scrolledtext.ScrolledText(text_frame, width=60, height=30)
            text_widget.pack(fill='both', expand=True)

            for result in results:
                text_widget.insert('end', result + '\n')

            text_widget.config(state='disabled')

            ttk.Button(result_dialog, text="Close", command=result_dialog.destroy).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error calculating GPAs: {e}")

    def show_grade_statistics(self):
        """Show comprehensive grade statistics from both grades and assignment_submissions"""
        try:
            cursor = self.get_safe_cursor()

            # Combined view: grades table + assignment_submissions with grades
            all_grades_cte = """
                WITH all_grades AS (
                    SELECT g.score as score,
                           ROUND((g.score / a.max_points) * 100, 2) as percentage,
                           g.letter_grade,
                           s.student_id, s.first_name, s.last_name,
                           a.assessment_name as assessment_name,
                           a.max_points as max_points
                    FROM grades g
                    JOIN students s ON g.student_id = s.student_id
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    UNION ALL
                    SELECT ROUND((sub.grade * COALESCE(a.max_marks, 100) / 100), 2) as score,
                           ROUND(sub.grade, 2) as percentage,
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
                           END as letter_grade,
                           s.student_id, s.first_name, s.last_name,
                           a.title as assessment_name,
                           COALESCE(a.max_marks, 100) as max_points
                    FROM assignment_submissions sub
                    JOIN students s ON sub.student_id = s.student_id
                    JOIN assignments a ON sub.assignment_id = a.id
                    WHERE sub.grade IS NOT NULL
                )
            """

            # Get overall statistics
            cursor.execute(f"""
                {all_grades_cte}
                SELECT COUNT(*) as total_grades,
                       AVG(percentage) as avg_pct,
                       MIN(percentage) as min_pct,
                       MAX(percentage) as max_pct
                FROM all_grades
            """)
            overall_stats = cursor.fetchone()

            if not overall_stats or overall_stats[0] == 0:
                messagebox.showinfo("No Data", "No grades available for statistics")
                return

            # Create statistics dialog
            stats_dialog = tk.Toplevel(self.root)
            stats_dialog.title("Grade Statistics")
            stats_dialog.geometry("800x700")

            notebook = ttk.Notebook(stats_dialog)
            notebook.pack(fill='both', expand=True, padx=10, pady=10)

            # Overall Statistics Tab
            overall_frame = ttk.Frame(notebook)
            notebook.add(overall_frame, text="Overall Statistics")

            stats_text = scrolledtext.ScrolledText(overall_frame, width=80, height=35)
            stats_text.pack(fill='both', expand=True, padx=10, pady=10)

            stats_text.insert('end', "=== OVERALL GRADE STATISTICS ===\n\n")
            stats_text.insert('end', f"Total Grades: {overall_stats[0]}\n")
            stats_text.insert('end', f"Average Percentage: {overall_stats[1]:.2f}%\n")
            stats_text.insert('end', f"Minimum Percentage: {overall_stats[2]:.2f}%\n")
            stats_text.insert('end', f"Maximum Percentage: {overall_stats[3]:.2f}%\n\n")

            # Grade distribution
            cursor.execute(f"""
                {all_grades_cte}
                SELECT letter_grade, COUNT(*) as count
                FROM all_grades
                GROUP BY letter_grade
                ORDER BY letter_grade
            """)
            grade_dist = cursor.fetchall()

            stats_text.insert('end', "=== GRADE DISTRIBUTION ===\n\n")
            for grade, count in grade_dist:
                pct = (count / overall_stats[0]) * 100
                bar = '#' * int(pct / 2)
                stats_text.insert('end', f"{grade:>3s}: {count:3d} ({pct:5.1f}%)  {bar}\n")

            # Per-Assessment Statistics Tab
            assessment_frame = ttk.Frame(notebook)
            notebook.add(assessment_frame, text="By Assessment")

            assessment_text = scrolledtext.ScrolledText(assessment_frame, width=80, height=35)
            assessment_text.pack(fill='both', expand=True, padx=10, pady=10)

            cursor.execute(f"""
                {all_grades_cte}
                SELECT assessment_name, max_points,
                       COUNT(*) as num_grades,
                       AVG(score) as avg_score,
                       MIN(score) as min_score,
                       MAX(score) as max_score,
                       AVG(percentage) as avg_pct
                FROM all_grades
                GROUP BY assessment_name
                ORDER BY assessment_name
            """)
            assessment_stats = cursor.fetchall()

            assessment_text.insert('end', "=== STATISTICS BY ASSESSMENT ===\n\n")
            for stat in assessment_stats:
                name, max_pts, num, avg_s, min_s, max_s, avg_p = stat
                assessment_text.insert('end', f"Assessment: {name}\n")
                assessment_text.insert('end', f"Number of Grades: {num}\n")
                assessment_text.insert('end', f"Average Score: {avg_s:.2f} / {max_pts}\n")
                assessment_text.insert('end', f"Average Percentage: {avg_p:.2f}%\n")
                assessment_text.insert('end', f"Score Range: {min_s:.2f} - {max_s:.2f}\n")
                assessment_text.insert('end', f"{'-'*60}\n\n")

            # Per-Student Statistics Tab
            student_frame = ttk.Frame(notebook)
            notebook.add(student_frame, text="By Student")

            student_text = scrolledtext.ScrolledText(student_frame, width=80, height=35)
            student_text.pack(fill='both', expand=True, padx=10, pady=10)

            cursor.execute(f"""
                {all_grades_cte}
                SELECT student_id, first_name, last_name,
                       COUNT(*) as num_grades,
                       AVG(percentage) as avg_pct,
                       MIN(percentage) as min_pct,
                       MAX(percentage) as max_pct
                FROM all_grades
                GROUP BY student_id
                ORDER BY last_name, first_name
            """)
            student_stats = cursor.fetchall()

            student_text.insert('end', "=== STATISTICS BY STUDENT ===\n\n")
            for stat in student_stats:
                sid, fname, lname, num, avg_p, min_p, max_p = stat
                student_text.insert('end', f"Student: {fname} {lname} ({sid})\n")
                student_text.insert('end', f"Number of Grades: {num}\n")
                student_text.insert('end', f"Average: {avg_p:.2f}%\n")
                student_text.insert('end', f"Range: {min_p:.2f}% - {max_p:.2f}%\n")

                # Letter grade for average
                letter = self.percentage_to_letter(avg_p)
                gpa = self.letter_to_gpa(letter)
                student_text.insert('end', f"Overall Grade: {letter} (GPA: {gpa:.2f})\n")
                student_text.insert('end', f"{'-'*60}\n\n")

            # Disable editing
            stats_text.config(state='disabled')
            assessment_text.config(state='disabled')
            student_text.config(state='disabled')

            ttk.Button(stats_dialog, text="Close", command=stats_dialog.destroy).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error calculating statistics: {e}")

    def _on_grade_row_double_click(self, _event):
        """Hand exam-source rows off to the exam scheduler's Results
        dialog. Other rows fall through to whatever default editing
        path exists (currently none — leave them no-op rather than
        opening the scheduler for the wrong source).
        """
        sel = self.grades_tree.selection()
        if not sel:
            return
        values = self.grades_tree.item(sel[0]).get("values") or []
        if not values:
            return
        grade_id = str(values[0])
        if not grade_id.startswith("E"):
            return  # non-exam row — let the existing Edit button handle it
        try:
            student_grades_id = int(grade_id[1:])
        except ValueError:
            return
        self._open_exam_results_for_grade(student_grades_id)

    def _open_exam_results_for_grade(self, student_grades_id: int):
        """Look up the originating exam for a student_grades row and
        open the exam scheduler's per-exam marks dialog."""
        try:
            cursor = self.get_safe_cursor()
        except Exception:
            return

        # student_grades.assessment_name was written as
        # "{module_code} Exam ({date})" by results.apply_exam_results,
        # so we can recover the exam by matching module_code + date
        # against the exams table.
        try:
            row = cursor.execute(
                "SELECT module_code, assessment_date "
                "FROM student_grades WHERE id = ?",
                (student_grades_id,),
            ).fetchone()
        except sqlite3.Error:
            row = None
        if not row:
            messagebox.showwarning(
                "Exam grade",
                "Couldn't locate the source row in student_grades.",
            )
            return
        module_code, exam_date = row[0], row[1]

        exam_row = None
        try:
            exam_row = cursor.execute(
                "SELECT id, module_code, module_name, date, start_time, "
                "       end_time, COALESCE(room,''), instructor_id, "
                "       COALESCE(instructor_name,''), "
                "       COALESCE(students_enrolled,0), "
                "       COALESCE(enrolled_student_ids,'[]') "
                "FROM exams "
                "WHERE module_code = ? AND date = ? "
                "ORDER BY id DESC LIMIT 1",
                (module_code, exam_date),
            ).fetchone()
        except sqlite3.Error:
            pass
        if not exam_row:
            messagebox.showinfo(
                "Exam grade",
                f"No matching exam found in the scheduler for "
                f"{module_code} on {exam_date}. The exam may have been "
                "deleted; the recorded grade remains visible here.",
            )
            return

        try:
            from education_system.university_system.modules.domain.academics.gui.exam_management.models import Exam
            from education_system.university_system.modules.domain.academics.gui.exam_management.data_manager import DataManager
            from education_system.university_system.modules.domain.academics.gui.exam_management.tabs.results_tab import ResultsEntryDialog
        except Exception as exc:
            messagebox.showerror(
                "Exam grade",
                f"Exam scheduler isn't available: {exc}",
            )
            return

        try:
            ids_blob = exam_row[10]
            enrolled_ids = json.loads(ids_blob) if ids_blob else []
        except (TypeError, ValueError):
            enrolled_ids = []

        exam_obj = Exam(
            id=exam_row[0], module_code=exam_row[1], module_name=exam_row[2],
            date=exam_row[3], start_time=exam_row[4], end_time=exam_row[5],
            room=exam_row[6], instructor_id=exam_row[7],
            instructor_name=exam_row[8], students_enrolled=exam_row[9],
            enrolled_student_ids=enrolled_ids,
        )

        # ResultsEntryDialog needs a DataManager so it can read enrolled
        # students and existing grades. Spin up a fresh one — it loads
        # data lazily and shares the same DB.
        data_manager = DataManager()
        ResultsEntryDialog(
            self.content_frame, exam_obj, data_manager,
            on_saved=self.refresh_grades,
        )

    def refresh_grades(self):
        """Refresh the grades list with current filters"""
        try:
            # Clear existing items
            for item in self.grades_tree.get_children():
                self.grades_tree.delete(item)

            # Get filter values
            student_filter = None
            assessment_filter = None

            if hasattr(self, 'grade_student_filter_var'):
                student_filter = self.grade_student_filter_var.get()
                if student_filter == "All Students":
                    student_filter = None

            if hasattr(self, 'grade_assessment_filter_var'):
                assessment_filter = self.grade_assessment_filter_var.get()
                if assessment_filter == "All Assessments":
                    assessment_filter = None

            # Build UNION query to get grades from both sources
            # Part 1: Grades from grades table (traditional assessments)
            query_part1 = """
                SELECT
                    g.grade_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    a.assessment_name,
                    g.score,
                    a.max_points,
                    ROUND((g.score / a.max_points) * 100, 2) as percentage,
                    g.letter_grade,
                    g.submission_date,
                    'assessment' as source_type
                FROM grades g
                JOIN students s ON g.student_id = s.student_id
                JOIN assessments a ON g.assessment_id = a.assessment_id
                WHERE 1=1
            """

            params1 = []

            # Apply student filter to part 1
            if student_filter:
                student_id = student_filter.split(' - ')[0]
                query_part1 += " AND s.student_id = ?"
                params1.append(student_id)

            # Apply assessment filter to part 1 (only if not an assignment ID)
            if assessment_filter and not assessment_filter.startswith('A'):
                assessment_id = assessment_filter.split(' - ')[0]
                query_part1 += " AND a.assessment_id = ?"
                params1.append(assessment_id)

            # Part 2: Grades from assignment_submissions table (assignment GUI)
            query_part2 = """
                SELECT
                    'S' || sub.id as grade_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    a.title as assessment_name,
                    ROUND((sub.grade * COALESCE(a.max_marks, 100) / 100), 2) as score,
                    COALESCE(a.max_marks, 100) as max_points,
                    ROUND(sub.grade, 2) as percentage,
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
                    END as letter_grade,
                    sub.graded_date as submission_date,
                    'assignment' as source_type
                FROM assignment_submissions sub
                JOIN students s ON sub.student_id = s.student_id
                JOIN assignments a ON sub.assignment_id = a.id
                WHERE sub.grade IS NOT NULL
            """

            params2 = []

            # Apply student filter to part 2
            if student_filter:
                student_id = student_filter.split(' - ')[0]
                query_part2 += " AND s.student_id = ?"
                params2.append(student_id)

            # Apply assessment filter to part 2 (only if it's an assignment ID starting with 'A')
            if assessment_filter and assessment_filter.startswith('A'):
                assignment_id = assessment_filter.split(' - ')[0][1:]  # Remove 'A' prefix
                query_part2 += " AND a.id = ?"
                params2.append(assignment_id)

            # Part 3: Exam results from student_grades (written by the
            # exam scheduler's results.apply_exam_results — assessment_type='exam').
            # IDs are prefixed 'E' so they can be told apart from rows in
            # `grades` ('grade_id' as int) and `assignment_submissions` ('S' + id).
            query_part3 = """
                SELECT
                    'E' || sg.id as grade_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    sg.assessment_name as assessment_name,
                    ROUND(sg.percentage, 2) as score,
                    100 as max_points,
                    ROUND(sg.percentage, 2) as percentage,
                    CASE
                        WHEN sg.percentage >= 93 THEN 'A+'
                        WHEN sg.percentage >= 90 THEN 'A'
                        WHEN sg.percentage >= 87 THEN 'A-'
                        WHEN sg.percentage >= 83 THEN 'B+'
                        WHEN sg.percentage >= 80 THEN 'B'
                        WHEN sg.percentage >= 77 THEN 'B-'
                        WHEN sg.percentage >= 73 THEN 'C+'
                        WHEN sg.percentage >= 70 THEN 'C'
                        WHEN sg.percentage >= 67 THEN 'C-'
                        WHEN sg.percentage >= 63 THEN 'D+'
                        WHEN sg.percentage >= 60 THEN 'D'
                        WHEN sg.percentage >= 57 THEN 'D-'
                        ELSE 'F'
                    END as letter_grade,
                    COALESCE(sg.assessment_date, sg.grade_date) as submission_date,
                    'exam' as source_type
                FROM student_grades sg
                JOIN students s ON sg.student_id = s.student_id
                WHERE sg.assessment_type = 'exam'
                  AND sg.percentage IS NOT NULL
            """

            params3 = []
            if student_filter:
                student_id = student_filter.split(' - ')[0]
                query_part3 += " AND s.student_id = ?"
                params3.append(student_id)
            # Assessment filter: exam rows have prefix 'E'
            if assessment_filter and assessment_filter.startswith('E'):
                exam_assessment = assessment_filter.split(' - ', 1)[0][1:]
                query_part3 += " AND sg.assessment_name = ?"
                params3.append(exam_assessment)

            # Combine all three queries
            full_query = (f"{query_part1} UNION ALL {query_part2} "
                          f"UNION ALL {query_part3} "
                          "ORDER BY submission_date DESC, student_name")

            cursor = self.get_safe_cursor()

            # Execute with combined parameters
            all_params = params1 + params2 + params3
            cursor.execute(full_query, all_params)
            grades = cursor.fetchall()

            # Insert into treeview
            for grade in grades:
                self.grades_tree.insert('', 'end', values=(
                    grade[0],  # ID
                    grade[1],  # Student
                    grade[2],  # Assessment
                    grade[3],  # Score
                    grade[4],  # Max Points
                    f"{grade[5]}%",  # Percentage
                    grade[6],  # Letter Grade
                    grade[7] if grade[7] else 'N/A'  # Date
                ))

        except ConnectionError as e:
            messagebox.showerror("Database Error", str(e))
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading grades: {e}")

    def clear_grade_filters(self):
        """Clear all grade filters"""
        if hasattr(self, 'grade_student_filter_var'):
            self.grade_student_filter_var.set('')
            if hasattr(self, 'grade_student_combo'):
                self.grade_student_combo.set('')

        if hasattr(self, 'grade_assessment_filter_var'):
            self.grade_assessment_filter_var.set('')
            if hasattr(self, 'grade_assessment_combo'):
                self.grade_assessment_combo.set('')

        self.refresh_grades()

    def filter_grades(self, event=None):
        """Apply current filters to grades list"""
        self.refresh_grades()

    def populate_filter_combos(self):
        """Populate filter comboboxes with current data"""
        try:
            cursor = self.get_safe_cursor()

            # Populate student filter — include students with rows in
            # `grades`, `assignment_submissions`, or `student_grades`
            # (the latter is where exam scheduler results land).
            if hasattr(self, 'grade_student_combo'):
                cursor.execute("""
                    SELECT DISTINCT s.student_id, s.first_name, s.last_name
                    FROM students s
                    WHERE EXISTS (SELECT 1 FROM grades g
                                   WHERE g.student_id = s.student_id)
                       OR EXISTS (SELECT 1 FROM assignment_submissions sub
                                   WHERE sub.student_id = s.student_id)
                       OR EXISTS (SELECT 1 FROM student_grades sg
                                   WHERE sg.student_id = s.student_id)
                    ORDER BY s.last_name, s.first_name
                """)
                students = cursor.fetchall()
                student_list = ["All Students"] + [f"{s[0]} - {s[1]} {s[2]}" for s in students]
                safe_combo_update(self, 'grade_student_combo', student_list)

            # Populate assessment filter (from both assessments and assignments tables)
            if hasattr(self, 'grade_assessment_combo'):
                # Query assessments table
                cursor.execute("""
                    SELECT DISTINCT a.assessment_id, a.assessment_name, m.module_name
                    FROM assessments a
                    JOIN modules m ON a.module_code = m.module_code
                    JOIN grades g ON a.assessment_id = g.assessment_id
                    ORDER BY m.module_name, a.assessment_name
                """)
                assessments_from_assessments = cursor.fetchall()

                # Query assignments table
                cursor.execute("""
                    SELECT DISTINCT
                        'A' || a.id as assessment_id,
                        a.title as assessment_name,
                        m.module_name
                    FROM assignments a
                    JOIN modules m ON a.module_code = m.module_code
                    WHERE EXISTS (SELECT 1 FROM grades g WHERE CAST(g.assessment_id AS TEXT) = 'A' || CAST(a.id AS TEXT))
                    ORDER BY m.module_name, a.title
                """)
                assessments_from_assignments = cursor.fetchall()

                # Query exam-source assessments from student_grades. The
                # filter id uses an 'E' prefix + the assessment_name so
                # refresh_grades can identify and route the filter.
                cursor.execute("""
                    SELECT DISTINCT sg.assessment_name,
                           COALESCE(m.module_name, sg.module_code) AS module_name
                    FROM student_grades sg
                    LEFT JOIN modules m ON m.module_code = sg.module_code
                    WHERE sg.assessment_type = 'exam'
                      AND sg.assessment_name IS NOT NULL
                    ORDER BY module_name, sg.assessment_name
                """)
                assessments_from_exams = [
                    (f"E{name}", name, mod or "")
                    for name, mod in cursor.fetchall()
                ]

                # Combine all three sources
                all_assessments = (list(assessments_from_assessments)
                                   + list(assessments_from_assignments)
                                   + assessments_from_exams)
                assessment_list = ["All Assessments"] + [f"{a[0]} - {a[1]} ({a[2]})" for a in all_assessments]
                safe_combo_update(self, 'grade_assessment_combo', assessment_list)

        except (ConnectionError, sqlite3.Error) as e:
            # Silently fail - filters just won't be populated
            pass

