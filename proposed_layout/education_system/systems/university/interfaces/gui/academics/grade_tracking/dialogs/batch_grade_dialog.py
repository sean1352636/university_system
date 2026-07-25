import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.scrolledtext as scrolledtext
from education_system.systems.university.infrastructure.database.db import sqlite3
import os
from pathlib import Path
import csv
import numpy as np
import math
from scipy import stats
from datetime import datetime, timedelta
import json
from education_system.systems.university.infrastructure import paths

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
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.interfaces.gui.academics.grade_tracking.utils import ensure_column_exists
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



class BatchGradeDialog:
    def __init__(self, parent, cursor, conn):
        self.result = None
        self.cursor = cursor
        self.conn = conn
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Batch Grade Entry")
        self.dialog.geometry("900x700")
        safe_grab_set(self.dialog)

        self.setup_dialog()

    def setup_dialog(self):
        # Title
        ttk.Label(self.dialog, text="Batch Grade Entry",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Assessment selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Assessment")
        select_frame.pack(fill=tk.X, padx=20, pady=10)

        self.assessment_var = tk.StringVar()
        assessment_combo = ttk.Combobox(select_frame, textvariable=self.assessment_var, width=50)
        assessment_combo.pack(side=tk.LEFT, padx=10, pady=10)

        ttk.Button(select_frame, text="Load Assessments",
                  command=lambda: self.load_assessments(assessment_combo)).pack(side=tk.LEFT, padx=10)
        ttk.Button(select_frame, text="Load Students",
                  command=self.load_students).pack(side=tk.LEFT, padx=10)

        # Students frame
        students_frame = ttk.LabelFrame(self.dialog, text="Students and Grades")
        students_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Treeview for students
        columns = ('Student ID', 'Name', 'Current Score', 'New Score', 'Grade', 'Comments')
        self.students_tree = ttk.Treeview(students_frame, columns=columns, show='headings')

        for col in columns:
            self.students_tree.heading(col, text=col)
            self.students_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(students_frame, orient=tk.VERTICAL, command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=scrollbar.set)

        self.students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Quick grade entry
        quick_frame = ttk.LabelFrame(self.dialog, text="Quick Grade Entry")
        quick_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(quick_frame, text="Apply to all selected:").pack(side=tk.LEFT, padx=5)
        self.quick_score_var = tk.StringVar()
        ttk.Entry(quick_frame, textvariable=self.quick_score_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_frame, text="Apply Score", command=self.apply_quick_score).pack(side=tk.LEFT, padx=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save All Grades", command=self.save_all_grades).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=10)

        # Bind double-click to edit
        self.students_tree.bind('<Double-1>', self.edit_individual_grade)

        self.assessment_id = None
        self.max_points = 0

    def load_assessments(self, combo):
        """Load assessments into combobox"""
        try:
            self.cursor.execute("SELECT assessment_id, assessment_name, module_code FROM assessments ORDER BY assessment_name")
            assessments = [f"{row[0]} - [{row[2]}] {row[1]}" for row in self.cursor.fetchall()]
            combo['values'] = assessments
            messagebox.showinfo("Success", f"Loaded {len(assessments)} assessments")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assessments: {e}")

    def load_students(self):
        """Load students for selected assessment"""
        if not self.assessment_var.get():
            messagebox.showwarning("Warning", "Please select an assessment first")
            return

        try:
            self.assessment_id = int(self.assessment_var.get().split(' - ')[0])

            # Get assessment details
            self.cursor.execute("SELECT max_points, module_code FROM assessments WHERE assessment_id = ?",
                              (self.assessment_id,))
            result = self.cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Assessment not found")
                return

            self.max_points, module_code = result

            # Get enrolled students
            self.cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code = ?
            ORDER BY s.last_name, s.first_name
            ''', (module_code,))

            students = self.cursor.fetchall()

            # Clear existing data
            for item in self.students_tree.get_children():
                self.students_tree.delete(item)

            # Load students with existing grades
            for student in students:
                student_id, first_name, last_name = student
                full_name = f"{first_name} {last_name}"

                # Check for existing grade
                self.cursor.execute('''
                SELECT score, letter_grade, comments
                FROM grades
                WHERE student_id = ? AND assessment_id = ?
                ''', (student_id, self.assessment_id))

                existing = self.cursor.fetchone()
                current_score = existing[0] if existing else ""

                self.students_tree.insert('', 'end', values=(
                    student_id, full_name, current_score, "", "", ""
                ))

            messagebox.showinfo("Success", f"Loaded {len(students)} students")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load students: {e}")

    def apply_quick_score(self):
        """Apply quick score to selected students"""
        if not self.quick_score_var.get():
            messagebox.showwarning("Warning", "Please enter a score")
            return

        try:
            score = float(self.quick_score_var.get())
            if score < 0 or score > self.max_points:
                messagebox.showerror("Error", f"Score must be between 0 and {self.max_points}")
                return

            # Calculate letter grade
            percentage = (score / self.max_points) * 100
            letter_grade = percentage_to_letter(percentage)

            # Apply to selected items (or all if none selected)
            selected_items = self.students_tree.selection()
            if not selected_items:
                selected_items = self.students_tree.get_children()

            for item in selected_items:
                values = list(self.students_tree.item(item, 'values'))
                values[3] = str(score)  # New Score
                values[4] = letter_grade  # Grade
                self.students_tree.item(item, values=values)

        except ValueError:
            messagebox.showerror("Error", "Please enter a valid numeric score")

    def edit_individual_grade(self, event):
        """Edit individual student grade"""
        selection = self.students_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.students_tree.item(item, 'values')
        student_id = values[0]
        student_name = values[1]
        current_new_score = values[3]
        current_comments = values[5]

        # Simple edit dialog
        edit_dialog = tk.Toplevel(self.dialog)
        edit_dialog.title(f"Edit Grade - {student_name}")
        edit_dialog.geometry("300x200")
        safe_grab_set(edit_dialog)

        ttk.Label(edit_dialog, text=f"Score (max {self.max_points}):").pack(pady=5)
        score_var = tk.StringVar(value=current_new_score)
        ttk.Entry(edit_dialog, textvariable=score_var, width=20).pack(pady=5)

        ttk.Label(edit_dialog, text="Comments:").pack(pady=5)
        comments_text = tk.Text(edit_dialog, height=4, width=30)
        comments_text.pack(pady=5)
        comments_text.insert(1.0, current_comments)

        def save_edit():
            try:
                score = float(score_var.get()) if score_var.get() else 0
                if score < 0 or score > self.max_points:
                    messagebox.showerror("Error", f"Score must be between 0 and {self.max_points}")
                    return

                percentage = (score / self.max_points) * 100
                letter_grade = percentage_to_letter(percentage)
                comments = comments_text.get(1.0, tk.END).strip()

                # Update treeview
                new_values = list(values)
                new_values[3] = str(score)
                new_values[4] = letter_grade
                new_values[5] = comments
                self.students_tree.item(item, values=new_values)

                edit_dialog.destroy()

            except ValueError:
                messagebox.showerror("Error", "Please enter a valid numeric score")

        ttk.Button(edit_dialog, text="Save", command=save_edit).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(edit_dialog, text="Cancel", command=edit_dialog.destroy).pack(side=tk.LEFT, padx=10, pady=10)

    def save_all_grades(self):
        """Save all grades to database"""
        if not self.assessment_id:
            messagebox.showwarning("Warning", "Please select an assessment first")
            return

        try:
            saved_count = 0
            submission_date = datetime.now().strftime('%Y-%m-%d')

            for item in self.students_tree.get_children():
                values = self.students_tree.item(item, 'values')
                student_id = values[0]
                new_score = values[3]
                letter_grade = values[4]
                comments = values[5]

                if new_score and letter_grade:  # Only save if score entered
                    # Check if grade exists
                    self.cursor.execute('''
                    SELECT grade_id FROM grades
                    WHERE student_id = ? AND assessment_id = ?
                    ''', (student_id, self.assessment_id))

                    existing = self.cursor.fetchone()

                    if existing:
                        # Update existing
                        self.cursor.execute('''
                        UPDATE grades
                        SET score = ?, letter_grade = ?, submission_date = ?, comments = ?
                        WHERE grade_id = ?
                        ''', (float(new_score), letter_grade, submission_date, comments, existing[0]))
                    else:
                        # Insert new
                        self.cursor.execute('''
                        INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date, comments)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''', (student_id, self.assessment_id, float(new_score), letter_grade, submission_date, comments))

                    saved_count += 1

            self.conn.commit()
            messagebox.showinfo("Success", f"Saved {saved_count} grades successfully")
            self.result = True
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save grades: {e}")

