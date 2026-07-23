import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.scrolledtext as scrolledtext
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import os
from pathlib import Path
import csv
import numpy as np
import math
from scipy import stats
from datetime import datetime, timedelta
import json
from education_system.post_18.university_system.core import paths

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

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
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
    from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.utils import ensure_column_exists
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



class RecordGradesDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Record Assessment Grades")
        self.dialog.geometry("800x600")
        safe_grab_set(self.dialog)

        self.setup_dialog()

    def setup_dialog(self):
        """Setup the record grades dialog"""
        # Title
        ttk.Label(self.dialog, text="Record Assessment Grades",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Assessment selection frame
        assess_frame = ttk.LabelFrame(self.dialog, text="Select Assessment")
        assess_frame.pack(fill=tk.X, padx=20, pady=10)

        self.assessment_var = tk.StringVar()
        self.assessment_combo = ttk.Combobox(assess_frame, textvariable=self.assessment_var, width=50)
        self.assessment_combo.pack(side=tk.LEFT, padx=10, pady=10)

        ttk.Button(assess_frame, text="Load Assessments",
                  command=self.load_assessments).pack(side=tk.LEFT, padx=10)
        ttk.Button(assess_frame, text="Select",
                  command=self.select_assessment).pack(side=tk.LEFT, padx=10)

        # Students frame
        students_frame = ttk.LabelFrame(self.dialog, text="Students")
        students_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Treeview for students and grades
        columns = ('Student ID', 'Name', 'Current Grade', 'Score', 'Letter Grade', 'Comments')
        self.students_tree = ttk.Treeview(students_frame, columns=columns, show='headings')

        for col in columns:
            self.students_tree.heading(col, text=col)
            self.students_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(students_frame, orient=tk.VERTICAL, command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=scrollbar.set)

        self.students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Grade entry frame
        entry_frame = ttk.LabelFrame(self.dialog, text="Grade Entry")
        entry_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(entry_frame, text="Select student and double-click to edit grade").pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save All Grades",
                  command=self.save_all_grades).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Close",
                  command=self.dialog.destroy).pack(side=tk.LEFT, padx=10)

        # Bind double-click event
        self.students_tree.bind('<Double-1>', self.edit_grade)

        self.assessment_id = None
        self.max_points = 0

    def load_assessments(self):
        """Load assessments into the combobox"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT assessment_id, assessment_name, module_code
                FROM assessments
                ORDER BY date_created DESC
            ''')

            assessments = cursor.fetchall()

            # Format for display
            assessment_list = [f"{a[0]} - [{a[2]}] {a[1]}" for a in assessments]

            safe_combo_update(self, 'assessment_combo', assessment_list)

            conn.close()

            if assessment_list:
                messagebox.showinfo("Success", f"Loaded {len(assessment_list)} assessments")
            else:
                messagebox.showwarning("Warning", "No assessments found")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading assessments: {e}")

    def select_assessment(self):
        """Select an assessment and load enrolled students"""
        if not self.assessment_var.get():
            messagebox.showwarning("Warning", "Please select an assessment first")
            return

        # Extract assessment ID
        self.assessment_id = int(self.assessment_var.get().split(' - ')[0])

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get assessment details
            cursor.execute('''
            SELECT a.assessment_name, a.module_code, a.max_points, m.module_name
            FROM assessments a
            JOIN modules m ON a.module_code = m.module_code
            WHERE a.assessment_id = ?
            ''', (self.assessment_id,))

            assessment = cursor.fetchone()

            if not assessment:
                messagebox.showerror("Error", "Assessment not found")
                return

            assessment_name, module_code, max_points, module_name = assessment
            self.max_points = max_points

            # Get students enrolled in this module
            cursor.execute('''
            SELECT s.student_id, s.first_name, s.middle_name, s.last_name
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code = ?
            ORDER BY s.last_name, s.first_name
            ''', (module_code,))

            students = cursor.fetchall()

            # Clear existing data
            for item in self.students_tree.get_children():
                self.students_tree.delete(item)

            # Load students with existing grades
            for student in students:
                student_id, first_name, middle_name, last_name = student
                middle_initial = middle_name[0] + ". " if middle_name else ""
                full_name = f"{first_name} {middle_initial}{last_name}"

                # Check for existing grade
                cursor.execute('''
                SELECT score, letter_grade, comments
                FROM grades
                WHERE student_id = ? AND assessment_id = ?
                ''', (student_id, self.assessment_id))

                existing_grade = cursor.fetchone()

                if existing_grade:
                    score, letter_grade, comments = existing_grade
                    current_grade = f"{letter_grade} ({score}/{max_points})"
                else:
                    score, letter_grade, comments = "", "", ""
                    current_grade = "Not graded"

                self.students_tree.insert('', 'end', values=(
                    student_id, full_name, current_grade, score, letter_grade, comments or ""
                ))

            conn.close()

            messagebox.showinfo("Success", f"Loaded {len(students)} students for {assessment_name}")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading students: {e}")

    def edit_grade(self, event):
        """Edit grade for selected student"""
        selection = self.students_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.students_tree.item(item, 'values')
        student_id = values[0]
        student_name = values[1]

        # Open grade edit dialog
        from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog import GradeEditDialog
        GradeEditDialog(self.dialog, student_id, student_name, self.max_points,
                       values[3], values[4], values[5], self.update_student_grade)

    def update_student_grade(self, student_id, score, letter_grade, comments):
        """Update student grade in the treeview"""
        for item in self.students_tree.get_children():
            values = self.students_tree.item(item, 'values')
            if values[0] == student_id:
                current_grade = f"{letter_grade} ({score}/{self.max_points})" if score else "Not graded"
                new_values = (values[0], values[1], current_grade, score, letter_grade, comments)
                self.students_tree.item(item, values=new_values)
                break

    def save_all_grades(self):
        """Save all grades to the database"""
        if not self.assessment_id:
            messagebox.showwarning("Warning", "Please select an assessment first")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            saved_count = 0
            submission_date = datetime.now().strftime('%Y-%m-%d')

            for item in self.students_tree.get_children():
                values = self.students_tree.item(item, 'values')
                student_id, _, _, score, letter_grade, comments = values

                if score and letter_grade:  # Only save if both score and grade are provided
                    # Check if grade already exists
                    cursor.execute('''
                    SELECT grade_id FROM grades
                    WHERE student_id = ? AND assessment_id = ?
                    ''', (student_id, self.assessment_id))

                    existing = cursor.fetchone()

                    if existing:
                        # Update existing grade
                        cursor.execute('''
                        UPDATE grades
                        SET score = ?, letter_grade = ?, submission_date = ?, comments = ?
                        WHERE grade_id = ?
                        ''', (float(score), letter_grade, submission_date, comments, existing[0]))
                    else:
                        # Insert new grade
                        cursor.execute('''
                        INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date, comments)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''', (student_id, self.assessment_id, float(score), letter_grade, submission_date, comments))

                    saved_count += 1

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Saved {saved_count} grades successfully")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error saving grades: {e}")
        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid score value: {e}")


