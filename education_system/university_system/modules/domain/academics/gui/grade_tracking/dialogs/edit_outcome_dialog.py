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
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.academics.gui.grade_tracking.utils import ensure_column_exists
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



class EditLearningOutcomeDialog:
    def __init__(self, parent, outcome_id, callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Learning Outcome")
        self.dialog.geometry("500x400")
        safe_grab_set(self.dialog)

        self.outcome_id = outcome_id
        self.callback = callback
        self.setup_dialog()
        self.load_outcome_data()

    def setup_dialog(self):
        """Setup the edit learning outcome dialog"""
        # Title
        ttk.Label(self.dialog, text="Edit Learning Outcome",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(self.dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Course
        ttk.Label(form_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.course_var = tk.StringVar()
        self.course_entry = ttk.Entry(form_frame, textvariable=self.course_var, width=30)
        self.course_entry.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Outcome Code
        ttk.Label(form_frame, text="Outcome Code:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(form_frame, textvariable=self.code_var, width=30)
        self.code_entry.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Category
        ttk.Label(form_frame, text="Category:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=self.category_var, width=27)
        category_combo['values'] = ("Knowledge", "Skills", "Attitudes", "Application", "Analysis", "Synthesis")
        category_combo.grid(row=2, column=1, sticky=tk.W, pady=5)

        # Importance
        ttk.Label(form_frame, text="Importance (1-5):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.importance_var = tk.StringVar()
        importance_spin = ttk.Spinbox(form_frame, textvariable=self.importance_var, from_=1, to=5, width=28)
        importance_spin.grid(row=3, column=1, sticky=tk.W, pady=5)

        # Description
        ttk.Label(form_frame, text="Description:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.description_text = tk.Text(form_frame, height=6, width=40)
        self.description_text.grid(row=4, column=1, sticky=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Update Outcome", command=self.update_outcome).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=10)

    def load_outcome_data(self):
        """Load existing outcome data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT course, outcome_code, description, category, importance
            FROM learning_outcomes
            WHERE outcome_id = ?
            ''', (self.outcome_id,))

            data = cursor.fetchone()
            conn.close()

            if data:
                course, code, description, category, importance = data
                self.course_var.set(course)
                self.code_var.set(code)
                self.category_var.set(category)
                self.importance_var.set(str(importance))
                self.description_text.insert(1.0, description)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading outcome: {e}")

    def update_outcome(self):
        """Update the learning outcome in the database"""
        course = self.course_var.get().strip().upper()
        code = self.code_var.get().strip()
        category = self.category_var.get().strip()
        importance = self.importance_var.get()
        description = self.description_text.get(1.0, tk.END).strip()

        if not all([course, code, category, importance, description]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE learning_outcomes
            SET course = ?, outcome_code = ?, description = ?, category = ?, importance = ?
            WHERE outcome_id = ?
            ''', (course, code, description, category, int(importance), self.outcome_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Learning outcome updated successfully")

            if self.callback:
                self.callback()

            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error updating outcome: {e}")

