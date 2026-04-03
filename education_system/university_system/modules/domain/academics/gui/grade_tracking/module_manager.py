"""Module/course management"""

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

class ModuleManager:
    """Module/course management"""

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

    def create_module_content(self):
        """Create module management content"""
        # Module management controls
        control_frame = ttk.Frame(self.content_frame)
        control_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(control_frame, text="Add Module",
                  command=self.add_module_dialog).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Edit Module",
                  command=self.edit_module_dialog).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Delete Module",
                  command=self.delete_module).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Module Enrollments",
                  command=self.manage_module_enrollments).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self.refresh_modules).pack(side='left', padx=5)

        # Module list
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('Code', 'Name', 'Type', 'Credits', 'Description')
        self.module_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=25)

        for col in columns:
            self.module_tree.heading(col, text=col)
            if col == 'Description':
                self.module_tree.column(col, width=300)
            else:
                self.module_tree.column(col, width=120, anchor='center')

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.module_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=self.module_tree.xview)
        self.module_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.module_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')

        # Load modules data
        self.refresh_modules()


    def load_courses_for_filter(self, combo):
        """Load courses for filtering"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT DISTINCT course FROM students ORDER BY course')
            courses = ['All Courses'] + [row[0] for row in cursor.fetchall()]
            combo['values'] = courses

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error loading courses: {e}")

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error loading courses: {e}")

        finally:
            if conn:
                conn.close()


    def generate_module_grade_report(self):
        """Generate module grade report"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT
                m.module_code,
                m.module_name,
                COUNT(DISTINCT sm.student_id) AS enrolled_students,
                COUNT(mg.id) AS graded_students,
                AVG(mg.final_score) AS avg_final_score,
                AVG(
                    CASE mg.final_grade
                        WHEN 'A+' THEN 4.0 WHEN 'A' THEN 4.0 WHEN 'A-' THEN 3.7
                        WHEN 'B+' THEN 3.3 WHEN 'B' THEN 3.0 WHEN 'B-' THEN 2.7
                        WHEN 'C+' THEN 2.3 WHEN 'C' THEN 2.0 WHEN 'C-' THEN 1.7
                        WHEN 'D+' THEN 1.3 WHEN 'D' THEN 1.0 WHEN 'D-' THEN 0.7
                        WHEN 'F' THEN 0.0 ELSE NULL
                    END
                ) AS avg_grade_points,
                SUM(CASE WHEN mg.final_grade = 'F' THEN 1 ELSE 0 END) AS fail_count
            FROM modules m
            LEFT JOIN student_modules sm ON m.module_code = sm.module_code
            LEFT JOIN module_grades mg ON m.module_code = mg.module_code
            GROUP BY m.module_code, m.module_name
            ''')
            module_rows = cursor.fetchall()

            cursor.execute('''
            SELECT
                m.module_code,
                AVG(
                    CASE
                        WHEN a.max_points IS NOT NULL AND a.max_points > 0
                        THEN (g.score / a.max_points) * 100
                    END
                ) AS avg_assessment_percentage
            FROM modules m
            LEFT JOIN assessments a ON m.module_code = a.module_code
            LEFT JOIN grades g ON a.assessment_id = g.assessment_id
            GROUP BY m.module_code
            ''')
            assessment_map = {row[0]: row[1] for row in cursor.fetchall()}

            summary_lines = [
                f"Modules With Recorded Assessments: {sum(1 for r in module_rows if assessment_map.get(r[0]) is not None)}",
                f"Modules With Final Grades: {sum(1 for r in module_rows if r[3])}",
                f"Average Module Final Score: "
                f"{(sum(r[4] for r in module_rows if r[4] is not None) / max(1, sum(1 for r in module_rows if r[4] is not None))):.1f}%"
                if any(r[4] is not None for r in module_rows) else "Average Module Final Score: N/A"
            ]

            top_modules = sorted(
                [row for row in module_rows if row[4] is not None],
                key=lambda r: r[4],
                reverse=True
            )[:5]

            top_lines = [
                f"{idx + 1}. {row[0]} - {row[1]}: Avg Final Score {row[4]:.1f}%, "
                f"GPA {row[5]:.2f}" if row[5] is not None else
                f"{idx + 1}. {row[0]} - {row[1]}: Avg Final Score {row[4]:.1f}%, GPA N/A"
                for idx, row in enumerate(top_modules)
            ]

            risk_modules = []
            for row in module_rows:
                module_code, module_name, enrolled, graded, avg_score, avg_gpa, fail_count = row
                if graded:
                    fail_rate = fail_count / graded
                    if fail_rate >= 0.25 or (avg_score is not None and avg_score < 60):
                        risk_modules.append((module_code, module_name, fail_rate, avg_score))

            risk_lines = [
                f"{module_code} - {module_name}: Fail Rate {fail_rate:.0%}, Avg Final Score "
                f"{avg_score:.1f}%" if avg_score is not None else
                f"{module_code} - {module_name}: Fail Rate {fail_rate:.0%}, Avg Final Score N/A"
                for module_code, module_name, fail_rate, avg_score in sorted(
                    risk_modules,
                    key=lambda item: (-item[2], item[3] if item[3] is not None else 101)
                )[:5]
            ]

            assessment_data = [
                (row[0], row[1], assessment_map[row[0]])
                for row in module_rows
                if assessment_map.get(row[0]) is not None
            ]
            assessment_data.sort(key=lambda item: item[2], reverse=True)
            assessment_lines = [
                f"{code} - {name}: Assessment Avg {avg:.1f}%"
                for code, name, avg in assessment_data[:5]
            ]

            sections = [
                ("Module Overview", summary_lines),
                ("Top Performing Modules", top_lines),
                ("Modules Requiring Attention", risk_lines),
                ("Assessment Averages Snapshot", assessment_lines)
            ]

            footer = (
                "Investigate modules with elevated fail rates or low average scores and collaborate with "
                "module leaders to review assessment alignment."
            )

            self._display_report("Module Grade Report", sections, footer)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate module grade report: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate module grade report: {e}")
        finally:
            if conn:
                conn.close()


    def generate_module_outcome_report(self):
        """Generate module outcome report"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM learning_outcomes')
            total_outcomes = cursor.fetchone()[0]

            cursor.execute('''
            SELECT
                m.module_code,
                m.module_name,
                COUNT(DISTINCT ao.outcome_id) AS mapped_outcomes
            FROM modules m
            LEFT JOIN assessments a ON m.module_code = a.module_code
            LEFT JOIN assessment_outcomes ao ON a.assessment_id = ao.assessment_id
            GROUP BY m.module_code, m.module_name
            ''')
            module_outcome_rows = cursor.fetchall()

            cursor.execute('''
            SELECT
                lo.outcome_code,
                lo.description,
                AVG(or.achievement_level) AS avg_level,
                COUNT(DISTINCT or.student_id) AS student_count
            FROM learning_outcomes lo
            LEFT JOIN outcome_results or ON lo.outcome_id = or.outcome_id
            GROUP BY lo.outcome_id, lo.outcome_code, lo.description
            ''')
            outcome_results_rows = cursor.fetchall()

            cursor.execute('''
            SELECT
                m.module_code,
                lo.outcome_code,
                AVG(or.achievement_level) AS avg_level
            FROM modules m
            JOIN assessments a ON m.module_code = a.module_code
            JOIN assessment_outcomes ao ON a.assessment_id = ao.assessment_id
            JOIN learning_outcomes lo ON ao.outcome_id = lo.outcome_id
            LEFT JOIN outcome_results or ON lo.outcome_id = or.outcome_id
            GROUP BY m.module_code, lo.outcome_code
            ''')
            module_attainment_rows = cursor.fetchall()

            summary_lines = [
                f"Total Defined Outcomes: {total_outcomes}",
                f"Modules With Outcome Mapping: {sum(1 for row in module_outcome_rows if row[2] > 0)}",
                f"Modules Without Outcome Mapping: {sum(1 for row in module_outcome_rows if row[2] == 0)}"
            ]

            outcome_attainment_lines = [
                f"{row[0]} - {row[1][:45]}...: Avg Level {row[2]:.2f} ({row[3]} students)"
                if len(row[1]) > 50 else
                f"{row[0]} - {row[1]}: Avg Level {row[2]:.2f} ({row[3]} students)"
                if row[2] is not None else
                f"{row[0]} - {row[1]}: No achievement evidence"
                for row in outcome_results_rows
            ]

            underrepresented_outcomes = [
                row for row in outcome_results_rows
                if row[3] == 0 or row[2] is None
            ][:5]
            underrepresented_lines = [
                f"{row[0]} - {row[1][:55]}...: No evidence"
                if len(row[1]) > 58 else
                f"{row[0]} - {row[1]}: No evidence"
                for row in underrepresented_outcomes
            ]

            module_attainment_map = {}
            for module_code, outcome_code, avg_level in module_attainment_rows:
                if avg_level is not None:
                    module_attainment_map.setdefault(module_code, []).append(avg_level)

            high_alignment_lines = []
            for module_code, module_name, mapped in module_outcome_rows:
                levels = module_attainment_map.get(module_code, [])
                if levels:
                    avg_level = sum(levels) / len(levels)
                    if avg_level >= 3.0:
                        high_alignment_lines.append(
                            f"{module_code} - {module_name}: Avg Outcome Level {avg_level:.2f} across {mapped} outcomes"
                        )

            at_risk_lines = []
            for module_code, module_name, mapped in module_outcome_rows:
                levels = module_attainment_map.get(module_code, [])
                if mapped == 0:
                    at_risk_lines.append(f"{module_code} - {module_name}: No mapped outcomes")
                elif levels:
                    avg_level = sum(levels) / len(levels)
                    if avg_level < 2.0:
                        at_risk_lines.append(
                            f"{module_code} - {module_name}: Avg Outcome Level {avg_level:.2f} ({mapped} outcomes)"
                        )

            sections = [
                ("Outcome Coverage Overview", summary_lines),
                ("Outcome Achievement Highlights", outcome_attainment_lines[:10]),
                ("High Outcome Alignment Modules", high_alignment_lines[:5]),
                ("Outcome Coverage Gaps", at_risk_lines[:5] if at_risk_lines else underrepresented_lines)
            ]

            footer = (
                "Review modules without outcome evidence to ensure assessments align with intended learning goals "
                "and capture achievement data consistently."
            )

            self._display_report("Module Outcome Report", sections, footer)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate module outcome report: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate module outcome report: {e}")
        finally:
            if conn:
                conn.close()

    def add_module_dialog(self):
        """Open dialog to add a new module"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Module")
        dialog.geometry("600x550")
        dialog.transient(self.root)

        # Create form
        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill='both', expand=True)

        # Module Code (required, primary key)
        ttk.Label(form_frame, text="Module Code*:").grid(row=0, column=0, sticky='w', pady=5)
        code_entry = ttk.Entry(form_frame, width=40)
        code_entry.grid(row=0, column=1, sticky='ew', pady=5)

        # Module Name (required)
        ttk.Label(form_frame, text="Module Name*:").grid(row=1, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=40)
        name_entry.grid(row=1, column=1, sticky='ew', pady=5)

        # Module Type
        ttk.Label(form_frame, text="Module Type:").grid(row=2, column=0, sticky='w', pady=5)
        type_combo = ttk.Combobox(form_frame, width=38, values=[
            'Core', 'Elective', 'Optional', 'Lab', 'Project', 'Seminar'
        ])
        type_combo.grid(row=2, column=1, sticky='ew', pady=5)

        # Credits
        ttk.Label(form_frame, text="Credits:").grid(row=3, column=0, sticky='w', pady=5)
        credits_spinbox = ttk.Spinbox(form_frame, from_=1, to=20, width=38)
        credits_spinbox.set(1)
        credits_spinbox.grid(row=3, column=1, sticky='ew', pady=5)

        # Course
        ttk.Label(form_frame, text="Course/Program:").grid(row=4, column=0, sticky='w', pady=5)
        course_entry = ttk.Entry(form_frame, width=40)
        course_entry.grid(row=4, column=1, sticky='ew', pady=5)

        # Semester
        ttk.Label(form_frame, text="Semester:").grid(row=5, column=0, sticky='w', pady=5)
        semester_combo = ttk.Combobox(form_frame, width=38, values=[
            'Fall', 'Spring', 'Summer', 'Winter', 'Year-long'
        ])
        semester_combo.grid(row=5, column=1, sticky='ew', pady=5)

        # Year
        ttk.Label(form_frame, text="Academic Year:").grid(row=6, column=0, sticky='w', pady=5)
        year_spinbox = ttk.Spinbox(form_frame, from_=2020, to=2030, width=38)
        year_spinbox.set(datetime.now().year)
        year_spinbox.grid(row=6, column=1, sticky='ew', pady=5)

        # Description (text area)
        ttk.Label(form_frame, text="Description:").grid(row=7, column=0, sticky='nw', pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, width=40, height=8)
        desc_text.grid(row=7, column=1, sticky='ew', pady=5)

        # Configure column weights
        form_frame.columnconfigure(1, weight=1)

        # Button frame
        btn_frame = ttk.Frame(dialog, padding="10")
        btn_frame.pack(fill='x', side='bottom')

        def save_module():
            """Save the new module to database"""
            # Validate required fields
            module_code = code_entry.get().strip()
            module_name = name_entry.get().strip()

            if not module_code:
                messagebox.showerror("Validation Error", "Module Code is required", parent=dialog)
                code_entry.focus()
                return

            if not module_name:
                messagebox.showerror("Validation Error", "Module Name is required", parent=dialog)
                name_entry.focus()
                return

            # Get optional fields
            module_type = type_combo.get().strip() or None
            credits = int(credits_spinbox.get())
            course = course_entry.get().strip() or None
            semester = semester_combo.get().strip() or None
            year = int(year_spinbox.get()) if year_spinbox.get() else None
            description = desc_text.get('1.0', 'end-1c').strip() or None

            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Check if module code already exists
                cursor.execute('SELECT module_code FROM modules WHERE module_code = ?', (module_code,))
                if cursor.fetchone():
                    messagebox.showerror("Duplicate Error",
                                       f"Module code '{module_code}' already exists",
                                       parent=dialog)
                    return

                # Insert new module
                cursor.execute('''
                    INSERT INTO modules (module_code, module_name, module_type, credits,
                                       description, course, semester, year)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (module_code, module_name, module_type, credits, description,
                     course, semester, year))

                conn.commit()
                messagebox.showinfo("Success", f"Module '{module_code}' created successfully",
                                  parent=dialog)

                # Refresh the module list
                self.refresh_modules()
                dialog.destroy()

            except sqlite3.Error as e:
                if conn:
                    conn.rollback()
                messagebox.showerror("Database Error", f"Failed to create module: {e}",
                                   parent=dialog)
            except Exception as e:
                if conn:
                    conn.rollback()
                messagebox.showerror("Error", f"Failed to create module: {e}",
                                   parent=dialog)
            finally:
                if conn:
                    conn.close()

        ttk.Button(btn_frame, text="Save", command=save_module).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        # Set grab and focus
        safe_grab_set(dialog)
        code_entry.focus()

    def edit_module_dialog(self):
        """Open dialog to edit an existing module"""
        # Check if a module is selected
        selected = self.module_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a module to edit")
            return

        # Get the module code from selected row
        item = self.module_tree.item(selected[0])
        module_code = item['values'][0]

        # Load module data
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT module_code, module_name, module_type, credits,
                       description, course, semester, year
                FROM modules WHERE module_code = ?
            ''', (module_code,))

            module_data = cursor.fetchone()
            if not module_data:
                messagebox.showerror("Error", "Module not found in database")
                return

            # Unpack module data
            mod_code, mod_name, mod_type, mod_credits, mod_desc, mod_course, mod_semester, mod_year = module_data

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load module: {e}")
            return
        finally:
            if conn:
                conn.close()

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Module: {module_code}")
        dialog.geometry("600x550")
        dialog.transient(self.root)

        # Create form
        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill='both', expand=True)

        # Module Code (read-only - primary key)
        ttk.Label(form_frame, text="Module Code:").grid(row=0, column=0, sticky='w', pady=5)
        code_label = ttk.Label(form_frame, text=mod_code, font=('TkDefaultFont', 10, 'bold'))
        code_label.grid(row=0, column=1, sticky='w', pady=5)

        # Module Name (required)
        ttk.Label(form_frame, text="Module Name*:").grid(row=1, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=40)
        name_entry.insert(0, mod_name or '')
        name_entry.grid(row=1, column=1, sticky='ew', pady=5)

        # Module Type
        ttk.Label(form_frame, text="Module Type:").grid(row=2, column=0, sticky='w', pady=5)
        type_combo = ttk.Combobox(form_frame, width=38, values=[
            'Core', 'Elective', 'Optional', 'Lab', 'Project', 'Seminar'
        ])
        if mod_type:
            type_combo.set(mod_type)
        type_combo.grid(row=2, column=1, sticky='ew', pady=5)

        # Credits
        ttk.Label(form_frame, text="Credits:").grid(row=3, column=0, sticky='w', pady=5)
        credits_spinbox = ttk.Spinbox(form_frame, from_=1, to=20, width=38)
        credits_spinbox.set(mod_credits or 1)
        credits_spinbox.grid(row=3, column=1, sticky='ew', pady=5)

        # Course
        ttk.Label(form_frame, text="Course/Program:").grid(row=4, column=0, sticky='w', pady=5)
        course_entry = ttk.Entry(form_frame, width=40)
        if mod_course:
            course_entry.insert(0, mod_course)
        course_entry.grid(row=4, column=1, sticky='ew', pady=5)

        # Semester
        ttk.Label(form_frame, text="Semester:").grid(row=5, column=0, sticky='w', pady=5)
        semester_combo = ttk.Combobox(form_frame, width=38, values=[
            'Fall', 'Spring', 'Summer', 'Winter', 'Year-long'
        ])
        if mod_semester:
            semester_combo.set(mod_semester)
        semester_combo.grid(row=5, column=1, sticky='ew', pady=5)

        # Year
        ttk.Label(form_frame, text="Academic Year:").grid(row=6, column=0, sticky='w', pady=5)
        year_spinbox = ttk.Spinbox(form_frame, from_=2020, to=2030, width=38)
        year_spinbox.set(mod_year or datetime.now().year)
        year_spinbox.grid(row=6, column=1, sticky='ew', pady=5)

        # Description (text area)
        ttk.Label(form_frame, text="Description:").grid(row=7, column=0, sticky='nw', pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, width=40, height=8)
        if mod_desc:
            desc_text.insert('1.0', mod_desc)
        desc_text.grid(row=7, column=1, sticky='ew', pady=5)

        # Configure column weights
        form_frame.columnconfigure(1, weight=1)

        # Button frame
        btn_frame = ttk.Frame(dialog, padding="10")
        btn_frame.pack(fill='x', side='bottom')

        def update_module():
            """Update the module in database"""
            # Validate required fields
            module_name = name_entry.get().strip()

            if not module_name:
                messagebox.showerror("Validation Error", "Module Name is required", parent=dialog)
                name_entry.focus()
                return

            # Get field values
            module_type = type_combo.get().strip() or None
            credits = int(credits_spinbox.get())
            course = course_entry.get().strip() or None
            semester = semester_combo.get().strip() or None
            year = int(year_spinbox.get()) if year_spinbox.get() else None
            description = desc_text.get('1.0', 'end-1c').strip() or None

            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Update module
                cursor.execute('''
                    UPDATE modules
                    SET module_name = ?, module_type = ?, credits = ?,
                        description = ?, course = ?, semester = ?, year = ?
                    WHERE module_code = ?
                ''', (module_name, module_type, credits, description,
                     course, semester, year, module_code))

                conn.commit()
                messagebox.showinfo("Success", f"Module '{module_code}' updated successfully",
                                  parent=dialog)

                # Refresh the module list
                self.refresh_modules()
                dialog.destroy()

            except sqlite3.Error as e:
                if conn:
                    conn.rollback()
                messagebox.showerror("Database Error", f"Failed to update module: {e}",
                                   parent=dialog)
            except Exception as e:
                if conn:
                    conn.rollback()
                messagebox.showerror("Error", f"Failed to update module: {e}",
                                   parent=dialog)
            finally:
                if conn:
                    conn.close()

        ttk.Button(btn_frame, text="Update", command=update_module).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        # Set grab and focus
        safe_grab_set(dialog)
        name_entry.focus()

    def delete_module(self):
        """Delete a selected module"""
        # Check if a module is selected
        selected = self.module_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a module to delete")
            return

        # Get the module code from selected row
        item = self.module_tree.item(selected[0])
        module_code = item['values'][0]
        module_name = item['values'][1]

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check for dependencies
            # Check enrollments
            cursor.execute('''
                SELECT COUNT(*) FROM student_modules
                WHERE module_code = ?
            ''', (module_code,))
            enrollment_count = cursor.fetchone()[0]

            # Check assessments
            cursor.execute('''
                SELECT COUNT(*) FROM assessments
                WHERE module_code = ?
            ''', (module_code,))
            assessment_count = cursor.fetchone()[0]

            # Check module grades
            cursor.execute('''
                SELECT COUNT(*) FROM module_grades
                WHERE module_code = ?
            ''', (module_code,))
            grade_count = cursor.fetchone()[0]

            # Build dependency message
            dependencies = []
            if enrollment_count > 0:
                dependencies.append(f"{enrollment_count} student enrollment(s)")
            if assessment_count > 0:
                dependencies.append(f"{assessment_count} assessment(s)")
            if grade_count > 0:
                dependencies.append(f"{grade_count} module grade(s)")

            # If there are dependencies, warn the user
            if dependencies:
                dep_msg = ", ".join(dependencies)
                confirm = messagebox.askyesno(
                    "Dependencies Found",
                    f"Module '{module_code} - {module_name}' has:\n\n{dep_msg}\n\n"
                    "Deleting this module will also remove all related records.\n\n"
                    "Are you sure you want to continue?",
                    icon='warning'
                )
                if not confirm:
                    return
            else:
                # No dependencies, just confirm deletion
                confirm = messagebox.askyesno(
                    "Confirm Deletion",
                    f"Are you sure you want to delete module:\n\n'{module_code} - {module_name}'?\n\n"
                    "This action cannot be undone.",
                    icon='warning'
                )
                if not confirm:
                    return

            # Delete the module and related records
            # Delete in order to respect foreign key constraints
            cursor.execute('DELETE FROM module_grades WHERE module_code = ?', (module_code,))
            cursor.execute('DELETE FROM grades WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE module_code = ?)', (module_code,))
            cursor.execute('DELETE FROM assessments WHERE module_code = ?', (module_code,))
            cursor.execute('DELETE FROM student_modules WHERE module_code = ?', (module_code,))
            cursor.execute('DELETE FROM modules WHERE module_code = ?', (module_code,))

            conn.commit()
            messagebox.showinfo("Success", f"Module '{module_code}' deleted successfully")

            # Refresh the module list
            self.refresh_modules()

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Database Error", f"Failed to delete module: {e}")
        except Exception as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Error", f"Failed to delete module: {e}")
        finally:
            if conn:
                conn.close()

    def manage_module_enrollments(self):
        """Open dialog to manage student enrollments for a module"""
        # Check if a module is selected
        selected = self.module_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a module to manage enrollments")
            return

        # Get the module code from selected row
        item = self.module_tree.item(selected[0])
        module_code = item['values'][0]
        module_name = item['values'][1]

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Manage Enrollments: {module_code} - {module_name}")
        dialog.geometry("900x600")
        dialog.transient(self.root)

        # Main container
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=f"Enrollment Management\n{module_code} - {module_name}",
                               font=('TkDefaultFont', 12, 'bold'))
        title_label.pack(pady=10)

        # Create notebook for two tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True)

        # Tab 1: Enrolled Students
        enrolled_frame = ttk.Frame(notebook, padding="10")
        notebook.add(enrolled_frame, text="Enrolled Students")

        # Enrolled students list
        ttk.Label(enrolled_frame, text="Currently Enrolled Students:",
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=5)

        enrolled_list_frame = ttk.Frame(enrolled_frame)
        enrolled_list_frame.pack(fill='both', expand=True, pady=5)

        enrolled_columns = ('Student ID', 'Name', 'Course', 'Enrollment Date', 'Status')
        enrolled_tree = ttk.Treeview(enrolled_list_frame, columns=enrolled_columns,
                                     show='headings', height=15)

        for col in enrolled_columns:
            enrolled_tree.heading(col, text=col)
            if col == 'Name':
                enrolled_tree.column(col, width=200)
            else:
                enrolled_tree.column(col, width=120)

        enrolled_scrollbar = ttk.Scrollbar(enrolled_list_frame, orient='vertical',
                                          command=enrolled_tree.yview)
        enrolled_tree.configure(yscrollcommand=enrolled_scrollbar.set)

        enrolled_tree.pack(side='left', fill='both', expand=True)
        enrolled_scrollbar.pack(side='right', fill='y')

        # Enrolled students buttons
        enrolled_btn_frame = ttk.Frame(enrolled_frame)
        enrolled_btn_frame.pack(fill='x', pady=5)

        def unenroll_student():
            """Remove a student from the module"""
            selected_student = enrolled_tree.selection()
            if not selected_student:
                messagebox.showwarning("No Selection", "Please select a student to unenroll",
                                     parent=dialog)
                return

            student_item = enrolled_tree.item(selected_student[0])
            student_id = student_item['values'][0]
            student_name = student_item['values'][1]

            confirm = messagebox.askyesno(
                "Confirm Unenrollment",
                f"Are you sure you want to unenroll:\n\n{student_id} - {student_name}\n\n"
                f"from module {module_code}?",
                parent=dialog
            )

            if not confirm:
                return

            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    DELETE FROM student_modules
                    WHERE student_id = ? AND module_code = ?
                ''', (student_id, module_code))

                conn.commit()
                messagebox.showinfo("Success",
                                  f"Student {student_id} unenrolled successfully",
                                  parent=dialog)

                # Refresh both lists
                load_enrolled_students()
                load_available_students()

            except sqlite3.Error as e:
                if conn:
                    conn.rollback()
                messagebox.showerror("Database Error",
                                   f"Failed to unenroll student: {e}",
                                   parent=dialog)
            finally:
                if conn:
                    conn.close()

        def load_enrolled_students():
            """Load list of enrolled students"""
            for item in enrolled_tree.get_children():
                enrolled_tree.delete(item)

            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT s.student_id, s.first_name || ' ' || s.last_name AS name,
                           s.course, sm.enrollment_date, sm.status
                    FROM student_modules sm
                    JOIN students s ON sm.student_id = s.student_id
                    WHERE sm.module_code = ?
                    ORDER BY s.student_id
                ''', (module_code,))

                for row in cursor.fetchall():
                    enrolled_tree.insert('', 'end', values=tuple(row))

            except sqlite3.Error as e:
                messagebox.showerror("Database Error",
                                   f"Failed to load enrolled students: {e}",
                                   parent=dialog)
            finally:
                if conn:
                    conn.close()

        ttk.Button(enrolled_btn_frame, text="Unenroll Selected Student",
                  command=unenroll_student).pack(side='left', padx=5)
        ttk.Button(enrolled_btn_frame, text="Refresh",
                  command=load_enrolled_students).pack(side='left', padx=5)

        # Tab 2: Available Students
        available_frame = ttk.Frame(notebook, padding="10")
        notebook.add(available_frame, text="Enroll New Students")

        # Search frame
        search_frame = ttk.Frame(available_frame)
        search_frame.pack(fill='x', pady=5)

        ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
        search_entry = ttk.Entry(search_frame, width=30)
        search_entry.pack(side='left', padx=5)

        # Available students list
        ttk.Label(available_frame, text="Available Students (not enrolled):",
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=5)

        available_list_frame = ttk.Frame(available_frame)
        available_list_frame.pack(fill='both', expand=True, pady=5)

        available_columns = ('Student ID', 'Name', 'Course', 'Email', 'Status')
        available_tree = ttk.Treeview(available_list_frame, columns=available_columns,
                                      show='headings', height=15)

        for col in available_columns:
            available_tree.heading(col, text=col)
            if col == 'Name' or col == 'Email':
                available_tree.column(col, width=180)
            else:
                available_tree.column(col, width=120)

        available_scrollbar = ttk.Scrollbar(available_list_frame, orient='vertical',
                                           command=available_tree.yview)
        available_tree.configure(yscrollcommand=available_scrollbar.set)

        available_tree.pack(side='left', fill='both', expand=True)
        available_scrollbar.pack(side='right', fill='y')

        def load_available_students(search_term=''):
            """Load list of students not enrolled in this module"""
            for item in available_tree.get_children():
                available_tree.delete(item)

            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()

                if search_term:
                    cursor.execute('''
                        SELECT s.student_id, s.first_name || ' ' || s.last_name AS name,
                               s.course, s.email_address, s.status
                        FROM students s
                        WHERE s.student_id NOT IN (
                            SELECT student_id FROM student_modules WHERE module_code = ?
                        )
                        AND (s.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?
                             OR s.course LIKE ? OR s.email_address LIKE ?)
                        ORDER BY s.student_id
                    ''', (module_code, f'%{search_term}%', f'%{search_term}%',
                         f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                else:
                    cursor.execute('''
                        SELECT s.student_id, s.first_name || ' ' || s.last_name AS name,
                               s.course, s.email_address, s.status
                        FROM students s
                        WHERE s.student_id NOT IN (
                            SELECT student_id FROM student_modules WHERE module_code = ?
                        )
                        ORDER BY s.student_id
                    ''', (module_code,))

                for row in cursor.fetchall():
                    available_tree.insert('', 'end', values=tuple(row))

            except sqlite3.Error as e:
                messagebox.showerror("Database Error",
                                   f"Failed to load available students: {e}",
                                   parent=dialog)
            finally:
                if conn:
                    conn.close()

        def search_students():
            """Search for students"""
            search_term = search_entry.get().strip()
            load_available_students(search_term)

        def enroll_student():
            """Enroll a student in the module"""
            selected_student = available_tree.selection()
            if not selected_student:
                messagebox.showwarning("No Selection",
                                     "Please select a student to enroll",
                                     parent=dialog)
                return

            student_item = available_tree.item(selected_student[0])
            student_id = student_item['values'][0]
            student_name = student_item['values'][1]

            confirm = messagebox.askyesno(
                "Confirm Enrollment",
                f"Enroll student:\n\n{student_id} - {student_name}\n\n"
                f"in module {module_code} - {module_name}?",
                parent=dialog
            )

            if not confirm:
                return

            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO student_modules (student_id, module_code, enrollment_date, status)
                    VALUES (?, ?, date('now'), 'Enrolled')
                ''', (student_id, module_code))

                conn.commit()
                messagebox.showinfo("Success",
                                  f"Student {student_id} enrolled successfully",
                                  parent=dialog)

                # Refresh both lists
                load_enrolled_students()
                load_available_students()

            except sqlite3.IntegrityError:
                if conn:
                    conn.rollback()
                messagebox.showerror("Error",
                                   "Student is already enrolled in this module",
                                   parent=dialog)
            except sqlite3.Error as e:
                if conn:
                    conn.rollback()
                messagebox.showerror("Database Error",
                                   f"Failed to enroll student: {e}",
                                   parent=dialog)
            finally:
                if conn:
                    conn.close()

        # Available students buttons
        available_btn_frame = ttk.Frame(available_frame)
        available_btn_frame.pack(fill='x', pady=5)

        ttk.Button(search_frame, text="Search", command=search_students).pack(side='left', padx=5)
        ttk.Button(search_frame, text="Clear",
                  command=lambda: (search_entry.delete(0, 'end'), load_available_students())).pack(side='left', padx=5)

        ttk.Button(available_btn_frame, text="Enroll Selected Student",
                  command=enroll_student).pack(side='left', padx=5)
        ttk.Button(available_btn_frame, text="Refresh",
                  command=lambda: load_available_students()).pack(side='left', padx=5)

        # Bottom buttons
        bottom_frame = ttk.Frame(dialog, padding="10")
        bottom_frame.pack(fill='x', side='bottom')

        ttk.Button(bottom_frame, text="Close", command=dialog.destroy).pack(side='right')

        # Initial load
        load_enrolled_students()
        load_available_students()

        # Set grab
        safe_grab_set(dialog)

    def refresh_modules(self):
        """Refresh the modules list from database"""
        if not hasattr(self, 'module_tree'):
            return

        conn = None
        try:
            # Clear existing items
            for item in self.module_tree.get_children():
                self.module_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            # Load all modules
            cursor.execute('''
                SELECT module_code, module_name, module_type, credits, description
                FROM modules
                ORDER BY module_code
            ''')

            for row in cursor.fetchall():
                module_code, module_name, module_type, credits, description = row
                # Truncate long descriptions
                display_desc = description[:50] + '...' if description and len(description) > 50 else (description or '')
                self.module_tree.insert('', 'end', values=(
                    module_code,
                    module_name,
                    module_type or 'N/A',
                    credits or 0,
                    display_desc
                ))

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load modules: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load modules: {e}")
        finally:
            if conn:
                conn.close()

