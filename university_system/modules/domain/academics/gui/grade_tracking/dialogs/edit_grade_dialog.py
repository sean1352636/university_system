import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.scrolledtext as scrolledtext
from university_system.infrastructure.database.db import sqlite3
import os
from pathlib import Path
import csv
import numpy as np
import math
from scipy import stats
from datetime import datetime, timedelta
import json
from university_system.modules.shared.constants import paths

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
    from university_system.infrastructure.database.db import get_connection
from university_system.modules.domain.academics.gui.grade_tracking.utils import ensure_column_exists
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



class EditGradeDialog:
    def __init__(self, parent, grade_id, student_id, assessment_id, current_score, 
                 current_grade, max_points, current_feedback, callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Grade")
        self.dialog.geometry("400x350")
        safe_grab_set(self.dialog)
        
        self.grade_id = grade_id
        self.student_id = student_id
        self.assessment_id = assessment_id
        self.max_points = max_points
        self.callback = callback
        
        self.setup_dialog(current_score, current_grade, current_feedback)
    
    def setup_dialog(self, current_score, current_grade, current_feedback):
        """Setup the edit grade dialog"""
        # Title
        ttk.Label(self.dialog, text="Edit Grade", 
                 font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Score entry
        score_frame = ttk.Frame(self.dialog)
        score_frame.pack(pady=10)
        
        ttk.Label(score_frame, text=f"Score (max {self.max_points}):").pack(side=tk.LEFT, padx=5)
        
        self.score_var = tk.StringVar(value=str(current_score))
        self.score_entry = ttk.Entry(score_frame, textvariable=self.score_var, width=10)
        self.score_entry.pack(side=tk.LEFT, padx=5)
        
        # Grade entry
        grade_frame = ttk.Frame(self.dialog)
        grade_frame.pack(pady=10)
        
        ttk.Label(grade_frame, text="Letter Grade:").pack(side=tk.LEFT, padx=5)
        
        self.grade_var = tk.StringVar(value=current_grade)
        grade_values = list(GRADE_SYSTEMS["letter"].keys())
        self.grade_combo = ttk.Combobox(grade_frame, textvariable=self.grade_var, 
                                       values=grade_values, width=5)
        self.grade_combo.pack(side=tk.LEFT, padx=5)
        
        # Feedback entry
        feedback_frame = ttk.LabelFrame(self.dialog, text="Feedback")
        feedback_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.feedback_text = tk.Text(feedback_frame, height=6)
        self.feedback_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        if current_feedback:
            self.feedback_text.insert(1.0, current_feedback)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Update", 
                  command=self.update_grade).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", 
                  command=self.dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def update_grade(self):
        """Update the grade in the database"""
        try:
            score = float(self.score_var.get())
            letter_grade = self.grade_var.get()
            feedback = self.feedback_text.get(1.0, tk.END).strip()
            
            if not (0 <= score <= self.max_points):
                messagebox.showerror("Error", f"Score must be between 0 and {self.max_points}")
                return
            
            if letter_grade not in GRADE_SYSTEMS["letter"]:
                messagebox.showerror("Error", "Please select a valid letter grade")
                return
            
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE grades
            SET score = ?, letter_grade = ?, comments = ?, submission_date = ?
            WHERE grade_id = ?
            ''', (score, letter_grade, feedback, datetime.now().strftime('%Y-%m-%d'), self.grade_id))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", "Grade updated successfully")
            
            if self.callback:
                self.callback()
            
            self.dialog.destroy()
            
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid numeric score")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error updating grade: {e}")

