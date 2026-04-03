"""Student management functionality"""

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
from education_system.university_system.modules.shared.constants import paths
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
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

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
        base_dir = Path(__file__).resolve().parents[1]  # Fixed indentation here
        db_path = base_dir / "db_files" / str(DEFAULT_DB_PATH)

        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

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

class StudentManager:
    """Student management functionality"""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.auth = app.auth
        self.conn = app.conn
        self.cursor = app.conn.cursor() if app.conn else None

    @property
    def content_frame(self):
        """Dynamically get content frame from layout"""
        if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'content_frame'):
            return self.app.layout.content_frame
        return None

    def get_cursor(self):
        """Get a valid database cursor, creating connection if needed"""
        try:
            # First try to use existing cursor
            if self.cursor:
                return self.cursor

            # Try to use app's connection
            if self.app.conn:
                self.conn = self.app.conn
                self.cursor = self.conn.cursor()
                return self.cursor

            # Create new connection
            self.conn = get_connection()
            self.cursor = self.conn.cursor()

            # Update app's connection too
            if hasattr(self.app, 'conn'):
                self.app.conn = self.conn

            return self.cursor
        except Exception as e:
            print(f"Error getting database cursor: {e}")
            return None

    def populate_filter_combos(self):
        """
        Populate filter combo boxes

        Populates the course filter combobox with available courses
        from the students table. Adds an "All Courses" option for
        showing all students regardless of their course.
        """
        try:
            # Check if combo exists
            if not hasattr(self, 'course_filter_combo'):
                return

            # Get database cursor
            cursor = self.get_cursor()
            if not cursor:
                return

            # Query distinct courses from students table
            cursor.execute('''
                SELECT DISTINCT course
                FROM students
                WHERE course IS NOT NULL AND course != ''
                ORDER BY course
            ''')

            courses = cursor.fetchall()

            # Build course list with "All Courses" option
            course_list = ['All Courses']
            course_list.extend([course[0] for course in courses])

            # Update combobox values
            self.course_filter_combo['values'] = course_list

            # Set default to "All Courses"
            if course_list:
                self.course_filter_var.set('All Courses')

        except Exception as e:
            print(f"Error populating filter combos: {e}")

    def update_status(self, message):
        """Update status bar"""
        if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'status_var'):
            self.app.layout.status_var.set(message)

    def filter_students(self, event=None):
        """Filter students by course"""
        self.refresh_students()

    def create_student_content(self):
        """Create student management content"""
        # Student management controls
        control_frame = ttk.Frame(self.content_frame)
        control_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(control_frame, text="Import Students",
                  command=self.import_students).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Export Students",
                  command=self.export_students).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self.refresh_students).pack(side='left', padx=5)

        # Search frame
        search_frame = ttk.Frame(self.content_frame)
        search_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
        self.student_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.student_search_var, width=30)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<KeyRelease>', self.search_students)

        # Filter frame
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(filter_frame, text="Filter by Course:").pack(side='left', padx=5)
        self.course_filter_var = tk.StringVar()
        self.course_filter_combo = ttk.Combobox(filter_frame, textvariable=self.course_filter_var,
                                               width=20, state='readonly')
        self.course_filter_combo.pack(side='left', padx=5)
        self.course_filter_combo.bind('<<ComboboxSelected>>', self.filter_students)

        # Student list
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Treeview for students
        columns = ('ID', 'Name', 'Email', 'Course', 'Registration Date')
        self.student_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)

        for col in columns:
            self.student_tree.heading(col, text=col)
            self.student_tree.column(col, width=120, anchor='center')

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.student_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=self.student_tree.xview)
        self.student_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.student_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')

        # Load students data
        self.refresh_students()

        # Populate filter combos now that they exist
        self.populate_filter_combos()


    def show_student_management_message(self):
        """Display message directing users to main GUI for student management"""
        messagebox.showinfo(
            "Student Management",
            "Student creation, editing, and deletion have been centralized in the main GUI.\n\n"
            "Please use the main student management interface to:\n"
            "• Create new students\n"
            "• Edit student information\n"
            "• Delete student records\n\n"
            "This ensures consistent student data across all modules."
        )


    def add_student_dialog(self):
        """Redirect to main GUI student management"""
        self.show_student_management_message()


    def edit_student_dialog(self):
        """Redirect to main GUI student management"""
        self.show_student_management_message()


    def update_student_dialog(self, student_id):
        """Redirect to main GUI student management"""
        self.show_student_management_message()


    def delete_student(self):
        """Redirect to main GUI student management"""
        self.show_student_management_message()


    def delete_student_dialog(self, student_id=None):
        """Redirect to main GUI student management"""
        self.show_student_management_message()


    def import_students(self):
        """Import students from CSV file"""
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if file_path:
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
                                    'student_import',
                                    filename=original_filename,
                                    reason=validation['error']
                                )
                            return
                    except Exception as e:
                        print(f"⚠️ File validation warning: {e}")

                # Get database cursor
                cursor = self.get_cursor()
                if not cursor:
                    messagebox.showerror("Error", "Failed to connect to database")
                    return

                import csv
                with open(file_path, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    imported_count = 0

                    for row in reader:
                        try:
                            student_data = (
                                row.get('student_id', ''),
                                row.get('first_name', ''),
                                row.get('middle_name', ''),
                                row.get('last_name', ''),
                                row.get('course', ''),
                                row.get('email_address', ''),
                                row.get('phone_number', ''),
                                row.get('address', ''),
                                row.get('enrollment_date', datetime.now().strftime('%Y-%m-%d')),
                                row.get('status', 'Active'),
                                row.get('date_of_birth', ''),
                                row.get('gender', ''),
                                row.get('nationality', '')
                            )

                            cursor.execute('''
                            INSERT INTO students (student_id, first_name, middle_name, last_name, course,
                                                email_address, phone_number, address, enrollment_date,
                                                status, date_of_birth, gender, nationality)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', student_data)
                            imported_count += 1
                        except sqlite3.IntegrityError:
                            print(f"Skipped duplicate student: {row.get('student_id', 'Unknown')}")
                            continue

                    self.conn.commit()
                    self.refresh_students()
                    self.populate_filter_combos()
                    self.update_status(f"Imported {imported_count} students")
                    messagebox.showinfo("Success", f"Successfully imported {imported_count} students!")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to import students: {e}")


    def export_students(self):
        """Export students to CSV file"""
        file_path = filedialog.asksaveasfilename(
            title="Save CSV file",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if file_path:
            try:
                # Get database cursor
                cursor = self.get_cursor()
                if not cursor:
                    messagebox.showerror("Error", "Failed to connect to database")
                    return

                import csv
                cursor.execute('''
                SELECT student_id, first_name, middle_name, last_name, course, email_address,
                       phone_number, address, enrollment_date, status, date_of_birth, gender, nationality
                FROM students ORDER BY last_name, first_name
                ''')

                students = cursor.fetchall()

                with open(file_path, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(['student_id', 'first_name', 'middle_name', 'last_name', 'course',
                                   'email_address', 'phone_number', 'address', 'enrollment_date',
                                   'status', 'date_of_birth', 'gender', 'nationality'])
                    writer.writerows(students)

                self.update_status(f"Exported {len(students)} students")
                messagebox.showinfo("Success", f"Successfully exported {len(students)} students!")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export students: {e}")


    def refresh_students(self):
        """Refresh student list display"""
        try:
            # Check if student_tree exists before accessing it
            if not hasattr(self, 'student_tree') or not self.student_tree:
                return

            # Get database cursor
            cursor = self.get_cursor()
            if not cursor:
                print("Failed to get database cursor")
                return

            # Clear existing items
            for item in self.student_tree.get_children():
                self.student_tree.delete(item)

            # Get students data
            cursor.execute('''
            SELECT student_id, first_name, middle_name, last_name, course, email_address,
                   COALESCE(registration_datetime, enrollment_date) as registration_date
            FROM students ORDER BY last_name, first_name
            ''')

            students = cursor.fetchall()

            # Insert into treeview with formatted data
            for student in students:
                student_id, first_name, middle_name, last_name, course, email, reg_date = student

                # Combine names into single field
                full_name = f"{first_name or ''}"
                if middle_name:
                    full_name += f" {middle_name}"
                if last_name:
                    full_name += f" {last_name}"
                full_name = full_name.strip()

                # Format data for new column structure: ('ID', 'Name', 'Email', 'Course', 'Registration Date')
                formatted_data = (
                    student_id,
                    full_name,
                    email or '',
                    course or '',
                    reg_date or ''
                )

                self.student_tree.insert('', 'end', values=formatted_data)

            self.update_status(f"Loaded {len(students)} students")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh students: {e}")


    def search_students(self, event):
        """Search students based on text input"""
        try:
            # Get database cursor
            cursor = self.get_cursor()
            if not cursor:
                print("Failed to get database cursor for search")
                return

            search_term = self.student_search_var.get().lower()

            # Clear existing items
            for item in self.student_tree.get_children():
                self.student_tree.delete(item)

            if search_term:
                cursor.execute('''
                SELECT student_id, first_name, last_name, course, email_address, enrollment_date
                FROM students
                WHERE LOWER(student_id) LIKE ? OR LOWER(first_name) LIKE ? OR
                      LOWER(last_name) LIKE ? OR LOWER(course) LIKE ? OR LOWER(email_address) LIKE ?
                ORDER BY last_name, first_name
                ''', tuple(f'%{search_term}%' for _ in range(5)))
            else:
                cursor.execute('''
                SELECT student_id, first_name, last_name, course, email_address, enrollment_date
                FROM students ORDER BY last_name, first_name
                ''')

            students = cursor.fetchall()

            for student in students:
                self.student_tree.insert('', 'end', values=student)

        except Exception as e:
            print(f"Error searching students: {e}")


    def generate_individual_transcript(self):
        """Generate individual student transcript"""
        try:
            # Delegate to analytics manager which has full transcript generation capability
            if hasattr(self.app, 'analytics') and hasattr(self.app.analytics, 'generate_individual_transcript'):
                self.app.analytics.generate_individual_transcript()
            else:
                messagebox.showerror("Error", "Transcript generation functionality not available.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate transcript: {e}")


    def generate_student_progress_report(self):
        """Generate student progress report"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

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

            cursor.execute('''
            SELECT student_id, AVG(
                CASE final_grade
                    WHEN 'A+' THEN 4.0 WHEN 'A' THEN 4.0 WHEN 'A-' THEN 3.7
                    WHEN 'B+' THEN 3.3 WHEN 'B' THEN 3.0 WHEN 'B-' THEN 2.7
                    WHEN 'C+' THEN 2.3 WHEN 'C' THEN 2.0 WHEN 'C-' THEN 1.7
                    WHEN 'D+' THEN 1.3 WHEN 'D' THEN 1.0 WHEN 'D-' THEN 0.7
                    WHEN 'F' THEN 0.0 ELSE NULL
                END
            ) AS avg_gpa
            FROM module_grades
            WHERE final_grade IS NOT NULL
            GROUP BY student_id
            ''')
            gpa_map = {row[0]: row[1] for row in cursor.fetchall()}

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

            total_students = len(progress_records)
            graded_students = sum(1 for r in progress_records if r["grades"] > 0)
            avg_scores = [r["avg_percent"] for r in progress_records if r["avg_percent"] is not None]
            avg_gpas = [r["gpa"] for r in progress_records if r["gpa"] is not None]
            low_participation = sum(1 for r in progress_records if r["grades"] < 3)

            overall_avg = sum(avg_scores) / len(avg_scores) if avg_scores else None
            overall_gpa = sum(avg_gpas) / len(avg_gpas) if avg_gpas else None

            high_performers = [
                r for r in progress_records
                if (r["avg_percent"] is not None and r["avg_percent"] >= 85) or
                   (r["gpa"] is not None and r["gpa"] >= 3.5)
            ]

            support_candidates = [
                r for r in progress_records
                if r["failures"] >= 2 or (r["avg_percent"] is not None and r["avg_percent"] < 60)
            ]

            top_students = sorted(
                progress_records,
                key=lambda r: ((r["avg_percent"] or 0), (r["gpa"] or 0)),
                reverse=True
            )[:5]

            support_priority = sorted(
                support_candidates,
                key=lambda r: (-r["failures"], r["avg_percent"] if r["avg_percent"] is not None else 101)
            )[:5]

            course_summary = {}
            for record in progress_records:
                course = record["course"]
                summary = course_summary.setdefault(course, {"count": 0, "scores": [], "fails": 0})
                summary["count"] += 1
                if record["avg_percent"] is not None:
                    summary["scores"].append(record["avg_percent"])
                summary["fails"] += record["failures"]

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
        """Generate competency profile"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM competencies')
            total_competencies = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(DISTINCT student_id) FROM student_competencies')
            students_tracked = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM student_competencies')
            total_records = cursor.fetchone()[0]

            cursor.execute('''
            SELECT c.competency_id, c.name, COALESCE(c.category, 'Uncategorized') AS category,
                   COUNT(sc.id) AS evidence_count,
                   AVG(cl.level_value) AS avg_level
            FROM competencies c
            LEFT JOIN student_competencies sc ON c.competency_id = sc.competency_id
            LEFT JOIN competency_levels cl ON sc.level_id = cl.level_id
            GROUP BY c.competency_id, c.name, c.category
            ''')
            competency_rows = cursor.fetchall()

            cursor.execute('''
            SELECT COALESCE(c.category, 'Uncategorized') AS category,
                   COUNT(DISTINCT c.competency_id) AS competency_count,
                   COUNT(sc.id) AS evidence_records
            FROM competencies c
            LEFT JOIN student_competencies sc ON c.competency_id = sc.competency_id
            GROUP BY c.category
            ORDER BY competency_count DESC
            ''')
            category_rows = cursor.fetchall()

            cursor.execute('''
            SELECT s.course,
                   COUNT(DISTINCT sc.student_id) AS students,
                   AVG(cl.level_value) AS avg_level
            FROM student_competencies sc
            JOIN students s ON sc.student_id = s.student_id
            LEFT JOIN competency_levels cl ON sc.level_id = cl.level_id
            GROUP BY s.course
            ORDER BY avg_level DESC
            ''')
            course_rows = cursor.fetchall()

            summary_lines = [
                f"Total Competencies Defined: {total_competencies}",
                f"Students With Competency Evidence: {students_tracked}",
                f"Total Competency Records: {total_records}",
            ]

            avg_levels = [row[4] for row in competency_rows if row[4] is not None]
            if avg_levels:
                summary_lines.append(f"Average Achievement Level: {sum(avg_levels) / len(avg_levels):.2f}")
            else:
                summary_lines.append("Average Achievement Level: N/A")

            top_competencies = [
                row for row in competency_rows if row[3] and row[4] is not None
            ]
            top_competencies = sorted(
                top_competencies,
                key=lambda r: (r[4], r[3]),
                reverse=True
            )[:5]

            top_lines = [
                f"{idx + 1}. {row[1]} ({row[2]}) - Avg Level: {row[4]:.2f} across {row[3]} records"
                for idx, row in enumerate(top_competencies)
            ]

            development_targets = [
                row for row in competency_rows
                if row[3] and row[4] is not None and row[4] < 2.5
            ]
            development_targets = sorted(
                development_targets,
                key=lambda r: (r[4], -r[3])
            )[:5]

            development_lines = [
                f"{idx + 1}. {row[1]} ({row[2]}) - Avg Level: {row[4]:.2f}, Evidence: {row[3]}"
                for idx, row in enumerate(development_targets)
            ]

            category_lines = [
                f"{row[0]}: {row[1]} competencies, {row[2]} evidence records"
                for row in category_rows
            ]

            course_lines = [
                f"{row[0]}: {row[1]} students, Avg Level: {row[2]:.2f}"
                if row[2] is not None else
                f"{row[0]}: {row[1]} students, Avg Level: N/A"
                for row in course_rows
            ]

            sections = [
                ("Competency Overview", summary_lines),
                ("Category Distribution", category_lines),
                ("Top Demonstrated Competencies", top_lines),
                ("Development Priorities", development_lines),
                ("Courses With Strong Competency Evidence", course_lines)
            ]

            footer = (
                "Use the development priorities list to coordinate targeted competency-building activities "
                "and ensure evidence is captured consistently across courses."
            )

            self._display_report("Competency Profile Summary", sections, footer)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate competency profile: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate competency profile: {e}")
        finally:
            if conn:
                conn.close()


    def generate_at_risk_report(self):
        """Generate at-risk students report"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ra.student_id, ra.id
            FROM student_risk_assessment ra
            JOIN (
                SELECT student_id, MAX(id) AS max_id
                FROM student_risk_assessment
                GROUP BY student_id
            ) latest ON ra.id = latest.max_id
            ''')
            latest_ids = [row[1] for row in cursor.fetchall()]

            if not latest_ids:
                self._display_report(
                    "At-Risk Student Report",
                    [("Risk Overview", ["No risk assessments have been recorded."])],
                    None
                )
                return

            placeholders = ",".join("?" for _ in latest_ids)
            cursor.execute('''
            SELECT s.student_id,
                   s.first_name || ' ' || COALESCE(s.last_name, '') AS name,
                   s.course,
                   ra.risk_score,
                   ra.risk_level,
                   COALESCE(ra.assessment_date, 'Unknown')
            FROM student_risk_assessment ra
            JOIN students s ON ra.student_id = s.student_id
            WHERE ra.id IN (''' + placeholders + ''')
            ORDER BY ra.risk_score DESC
            ''', latest_ids)
            risk_rows = cursor.fetchall()

            cursor.execute('''
            SELECT student_id, COUNT(*) AS fail_count
            FROM grades
            WHERE letter_grade = 'F'
            GROUP BY student_id
            ''')
            fail_map = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute('''
            SELECT student_id, AVG(
                CASE final_grade
                    WHEN 'A+' THEN 4.0 WHEN 'A' THEN 4.0 WHEN 'A-' THEN 3.7
                    WHEN 'B+' THEN 3.3 WHEN 'B' THEN 3.0 WHEN 'B-' THEN 2.7
                    WHEN 'C+' THEN 2.3 WHEN 'C' THEN 2.0 WHEN 'C-' THEN 1.7
                    WHEN 'D+' THEN 1.3 WHEN 'D' THEN 1.0 WHEN 'D-' THEN 0.7
                    WHEN 'F' THEN 0.0 ELSE NULL
                END
            ) AS avg_gpa
            FROM module_grades
            WHERE final_grade IS NOT NULL
            GROUP BY student_id
            ''')
            gpa_map = {row[0]: row[1] for row in cursor.fetchall()}

            level_counts = {"High": 0, "Medium": 0, "Low": 0, "Unknown": 0}
            risk_scores = []
            high_risk_lines = []
            monitor_lines = []

            for idx, row in enumerate(risk_rows):
                student_id, name, course, risk_score, risk_level, assessed_on = row
                risk_scores.append(risk_score)

                level = risk_level or "Unknown"
                level_counts[level] = level_counts.get(level, 0) + 1

                fail_count = fail_map.get(student_id, 0)
                gpa = gpa_map.get(student_id)

                line = (
                    f"{idx + 1}. {name} ({course}) - Risk Score: {risk_score:.2f} "
                    f"[{level}], Fails: {fail_count}, "
                    f"GPA: {gpa:.2f} | Assessed: {assessed_on}"
                ) if gpa is not None else (
                    f"{idx + 1}. {name} ({course}) - Risk Score: {risk_score:.2f} "
                    f"[{level}], Fails: {fail_count}, GPA: N/A | Assessed: {assessed_on}"
                )

                if level == "High":
                    high_risk_lines.append(line)
                else:
                    monitor_lines.append(line)

            cursor.execute('''
            SELECT
                substr(COALESCE(assessment_date, ''), 1, 7) AS period,
                COUNT(*) AS assessments,
                AVG(risk_score) AS avg_score
            FROM student_risk_assessment
            WHERE assessment_date IS NOT NULL AND assessment_date != ''
            GROUP BY substr(assessment_date, 1, 7)
            ORDER BY period DESC
            LIMIT 6
            ''')
            trend_rows = cursor.fetchall()

            trend_lines = [
                f"{row[0]}: {row[1]} assessments, Avg Risk Score: {row[2]:.2f}"
                for row in trend_rows
            ]

            average_risk = sum(risk_scores) / len(risk_scores) if risk_scores else None

            summary_lines = [
                f"Students With Current Risk Assessments: {len(risk_rows)}",
                f"High Risk: {level_counts.get('High', 0)}",
                f"Medium Risk: {level_counts.get('Medium', 0)}",
                f"Low Risk: {level_counts.get('Low', 0)}",
                f"Average Risk Score: {average_risk:.2f}" if average_risk is not None else "Average Risk Score: N/A"
            ]

            sections = [
                ("Risk Overview", summary_lines),
                ("High Risk Students", high_risk_lines[:10]),
                ("Students To Monitor", monitor_lines[:10]),
                ("Recent Risk Trend (Last 6 Periods)", trend_lines)
            ]

            footer = (
                "Prioritize outreach for high risk students and monitor trend changes to evaluate "
                "the effectiveness of support interventions."
            )

            self._display_report("At-Risk Student Report", sections, footer)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate at-risk report: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate at-risk report: {e}")
        finally:
            if conn:
                conn.close()


    def load_students_for_reports(self, combo):
        """Load students for report generation"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT student_id, first_name, last_name, course
            FROM students
            ORDER BY last_name, first_name
            ''')

            students = cursor.fetchall()
            student_list = [f"{s[0]} - {s[1]} {s[2]} ({s[3]})" for s in students]
            combo['values'] = student_list

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error loading students: {e}")

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error loading students: {e}")

        finally:
            if conn:
                conn.close()


    def generate_performance_dashboard(self):
        """Generate a comprehensive performance dashboard"""
        try:
            # Create dashboard window
            dashboard_window = tk.Toplevel(self.root)
            dashboard_window.title("Performance Dashboard")
            dashboard_window.geometry("1200x800")
            safe_grab_set(dashboard_window)

            # Title
            ttk.Label(dashboard_window, text="Performance Dashboard",
                     font=('Arial', 16, 'bold')).pack(pady=10)

            # Dashboard content
            dashboard_text = scrolledtext.ScrolledText(dashboard_window, height=30, width=100)
            dashboard_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Generate dashboard content
            conn = get_connection()
            cursor = conn.cursor()

            dashboard_content = "PERFORMANCE DASHBOARD\n" + "="*50 + "\n\n"

            # Overall statistics
            cursor.execute('SELECT COUNT(*) FROM students')
            total_students = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM grades')
            total_grades = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM assessments')
            total_assessments = cursor.fetchone()[0]

            dashboard_content += f"OVERVIEW:\n"
            dashboard_content += f"Total Students: {total_students}\n"
            dashboard_content += f"Total Assessments: {total_assessments}\n"
            dashboard_content += f"Total Grades Recorded: {total_grades}\n\n"

            # Grade distribution
            cursor.execute('''
            SELECT letter_grade, COUNT(*) as count
            FROM grades
            GROUP BY letter_grade
            ORDER BY letter_grade
            ''')

            grade_dist = cursor.fetchall()
            dashboard_content += "GRADE DISTRIBUTION:\n"
            for grade, count in grade_dist:
                percentage = (count / total_grades) * 100 if total_grades > 0 else 0
                dashboard_content += f"{grade}: {count} ({percentage:.1f}%)\n"

            dashboard_text.insert(1.0, dashboard_content)
            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate dashboard: {e}")


    def show_grade_trends_chart(self):
        """Show grade trends chart"""
        try:
            # Create trends window
            trends_window = tk.Toplevel(self.root)
            trends_window.title("Grade Trends Chart")
            trends_window.geometry("800x600")
            safe_grab_set(trends_window)

            ttk.Label(trends_window, text="Grade Trends Chart",
                     font=('Arial', 16, 'bold')).pack(pady=10)

            # Chart placeholder
            chart_frame = ttk.Frame(trends_window)
            chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Label(chart_frame, text="Grade trends visualization would appear here.\n"
                                      "This feature requires matplotlib integration.",
                     font=('Arial', 12)).pack(expand=True)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show trends chart: {e}")


    def student_progress_charts(self):
        """Show student progress charts"""
        try:
            # Create progress charts window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Student Progress Charts")
            progress_window.geometry("800x600")
            safe_grab_set(progress_window)

            ttk.Label(progress_window, text="Student Progress Charts",
                     font=('Arial', 16, 'bold')).pack(pady=10)

            # Chart placeholder
            chart_frame = ttk.Frame(progress_window)
            chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Label(chart_frame, text="Student progress charts would appear here.\n"
                                      "This feature requires matplotlib integration.",
                     font=('Arial', 12)).pack(expand=True)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show progress charts: {e}")

