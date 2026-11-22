
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, filedialog
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import messagebox
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import make_toplevel
import tkinter.scrolledtext as scrolledtext
from education_system.systems.university.infrastructure.database.db import sqlite3
import os
from pathlib import Path
import csv
import math
from datetime import datetime, timedelta
import json
from education_system import paths
from education_system.systems.university.infrastructure.database.schemas.modules_table import ensure_modules_table
from education_system.systems.university.infrastructure.database.schemas.modules_table import ensure_student_modules_table
from education_system.systems.university.infrastructure.database.schemas.students_table import ensure_students_table

# Use centralized path configuration
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH


# Database connection setup

_original_sqlite3_connect_grade = sqlite3.connect

def _patched_sqlite3_connect_grade(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "student_grading_system.db"):
            return _original_sqlite3_connect_grade(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return _original_sqlite3_connect_grade(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite3_connect_grade

# Import the database connection
try:
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.utils import ensure_column_exists
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
        ensure_students_table(cursor)

        # Create modules table
        ensure_modules_table(cursor)

        # Create student_modules table (enrollment)
        ensure_student_modules_table(cursor)

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
        messagebox.showerror(_t('gui.academics.grade_tracking.dialogs.module_dialog.dialogs.database_error', default="Database Error"), f"Database error: {e}")
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
        messagebox.showerror(_t('gui.academics.grade_tracking.dialogs.module_dialog.dialogs.database_error', default="Database Error"), f"Database error: {e}")
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



class ModuleDialog:
    def __init__(self, parent, title, data=None):
        self.result = None
        self.dialog = make_toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x400")
        safe_grab_set(self.dialog)

        self.setup_dialog(data)

    def setup_dialog(self, data):
        # Title
        ttk.Label(self.dialog, text=self.dialog.title(),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(self.dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Module Code
        ttk.Label(form_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.labels.module_code', default="Module Code:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_code_var = tk.StringVar(value=data[0] if data else "")
        ttk.Entry(form_frame, textvariable=self.module_code_var, width=30).grid(row=0, column=1, pady=5)

        # Module Name
        ttk.Label(form_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.labels.module_name', default="Module Name:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.module_name_var = tk.StringVar(value=data[1] if data else "")
        ttk.Entry(form_frame, textvariable=self.module_name_var, width=30).grid(row=1, column=1, pady=5)

        # Module Type
        ttk.Label(form_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.labels.module_type', default="Module Type:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.module_type_var = tk.StringVar(value=data[2] if data else "")
        type_combo = ttk.Combobox(form_frame, textvariable=self.module_type_var, width=27)
        type_combo['values'] = ("Core", "Elective", "General", "Laboratory", "Seminar")
        type_combo.grid(row=2, column=1, pady=5)

        # Credits
        ttk.Label(form_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.labels.credits', default="Credits:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.credits_var = tk.StringVar(value=str(data[3]) if data else "3")
        ttk.Spinbox(form_frame, textvariable=self.credits_var, from_=1, to=12, width=28).grid(row=3, column=1, pady=5)

        # Description
        ttk.Label(form_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.labels.description', default="Description:")).grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.description_text = tk.Text(form_frame, height=4, width=30)
        self.description_text.grid(row=4, column=1, pady=5)
        if data and len(data) > 4:
            self.description_text.insert(1.0, data[4])

        # Prerequisites
        ttk.Label(form_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.labels.prerequisites', default="Prerequisites:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.prerequisites_var = tk.StringVar(value=data[5] if data and len(data) > 5 else "")
        ttk.Entry(form_frame, textvariable=self.prerequisites_var, width=30).grid(row=5, column=1, pady=5)

        # Semester
        ttk.Label(form_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.labels.semester', default="Semester:")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.semester_var = tk.StringVar(value=data[6] if data and len(data) > 6 else "")
        semester_combo = ttk.Combobox(form_frame, textvariable=self.semester_var, width=27)
        semester_combo['values'] = ("Fall", "Spring", "Summer", "Winter")
        semester_combo.grid(row=6, column=1, pady=5)

        # Academic Year
        ttk.Label(form_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.labels.academic_year', default="Academic Year:")).grid(row=7, column=0, sticky=tk.W, pady=5)
        self.year_var = tk.StringVar(value=data[7] if data and len(data) > 7 else str(datetime.now().year))
        ttk.Entry(form_frame, textvariable=self.year_var, width=30).grid(row=7, column=1, pady=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.buttons.save', default="Save"), command=self.save_module).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.dialogs.module_dialog.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=10)

    def save_module(self):
        if not all([self.module_code_var.get(), self.module_name_var.get(),
                   self.module_type_var.get(), self.credits_var.get()]):
            messagebox.showerror(_t('gui.academics.grade_tracking.dialogs.module_dialog.dialogs.error', default="Error"), _t('gui.academics.grade_tracking.dialogs.module_dialog.dialogs.please_fill_in_all_required_fields', default="Please fill in all required fields"))
            return

        try:
            credits = int(self.credits_var.get())
        except ValueError:
            messagebox.showerror(_t('gui.academics.grade_tracking.dialogs.module_dialog.dialogs.error', default="Error"), _t('gui.academics.grade_tracking.dialogs.module_dialog.dialogs.credits_must_be_a_number', default="Credits must be a number"))
            return

        self.result = (
            self.module_code_var.get().strip(),
            self.module_name_var.get().strip(),
            self.module_type_var.get().strip(),
            credits,
            self.description_text.get(1.0, tk.END).strip(),
            self.prerequisites_var.get().strip(),
            self.semester_var.get().strip(),
            self.year_var.get().strip()
        )
        self.dialog.destroy()

