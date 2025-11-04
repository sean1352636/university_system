"""Grade management and calculations"""

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

def ensure_column_exists(cursor, table_name, column_name, column_def):
    """Add *column_name* to *table_name* if it doesn't already exist."""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1] for row in cursor.fetchall()}
        if column_name not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
    except sqlite3.Error as exc:
        print(f"Warning: could not ensure column {column_name} on {table_name}: {exc}")


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

    def add_grade_dialog(self):
        """Open dialog to add a new grade"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Grade")
        dialog.geometry("500x600")

        # Make dialog modal
        dialog.transient(self.root)
        safe_grab_set(dialog)

        # Student selection
        ttk.Label(dialog, text="Student:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        student_var = tk.StringVar()
        student_combo = ttk.Combobox(dialog, textvariable=student_var, width=35, state='readonly')
        student_combo.grid(row=0, column=1, padx=10, pady=10)

        # Load students
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT student_id, first_name, last_name FROM students ORDER BY last_name")
            students = cursor.fetchall()
            student_list = [f"{s[0]} - {s[1]} {s[2]}" for s in students]
            student_combo['values'] = student_list
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading students: {e}")
            dialog.destroy()
            return

        # Assessment selection
        ttk.Label(dialog, text="Assessment:").grid(row=1, column=0, padx=10, pady=10, sticky='w')
        assessment_var = tk.StringVar()
        assessment_combo = ttk.Combobox(dialog, textvariable=assessment_var, width=35, state='readonly')
        assessment_combo.grid(row=1, column=1, padx=10, pady=10)

        # Load assessments (from both assessments and assignments tables)
        try:
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

        # Score entry
        ttk.Label(dialog, text="Score:").grid(row=2, column=0, padx=10, pady=10, sticky='w')
        score_var = tk.StringVar()
        score_entry = ttk.Entry(dialog, textvariable=score_var, width=37)
        score_entry.grid(row=2, column=1, padx=10, pady=10)

        # Max points display
        max_points_var = tk.StringVar(value="Select an assessment")
        ttk.Label(dialog, text="Max Points:").grid(row=3, column=0, padx=10, pady=10, sticky='w')
        max_points_label = ttk.Label(dialog, textvariable=max_points_var)
        max_points_label.grid(row=3, column=1, padx=10, pady=10, sticky='w')

        # Update max points when assessment selected
        def update_max_points(event=None):
            selected = assessment_var.get()
            if selected:
                assessment_id = selected.split(' - ')[0]
                for a in assessments:
                    if str(a[0]) == assessment_id:
                        max_points_var.set(str(a[2]))
                        break

        assessment_combo.bind('<<ComboboxSelected>>', update_max_points)

        # Submission date
        ttk.Label(dialog, text="Submission Date:").grid(row=4, column=0, padx=10, pady=10, sticky='w')
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(dialog, textvariable=date_var, width=37)
        date_entry.grid(row=4, column=1, padx=10, pady=10)

        # Comments
        ttk.Label(dialog, text="Comments:").grid(row=5, column=0, padx=10, pady=10, sticky='nw')
        comments_text = tk.Text(dialog, width=35, height=8)
        comments_text.grid(row=5, column=1, padx=10, pady=10)

        # Save button
        def save_grade():
            student_id = student_var.get().split(' - ')[0] if student_var.get() else None
            assessment_id = assessment_var.get().split(' - ')[0] if assessment_var.get() else None
            score = score_var.get()
            date = date_var.get()
            comments = comments_text.get('1.0', 'end-1c')

            # Validation
            if not student_id:
                messagebox.showerror("Validation Error", "Please select a student")
                return
            if not assessment_id:
                messagebox.showerror("Validation Error", "Please select an assessment")
                return
            if not score:
                messagebox.showerror("Validation Error", "Please enter a score")
                return

            try:
                score_float = float(score)
                max_points = float(max_points_var.get())

                if score_float < 0:
                    messagebox.showerror("Validation Error", "Score cannot be negative")
                    return
                if score_float > max_points:
                    messagebox.showerror("Validation Error", f"Score cannot exceed max points ({max_points})")
                    return

                # Calculate percentage and letter grade
                percentage = (score_float / max_points) * 100
                letter_grade = self.percentage_to_letter(percentage)

                # Insert grade
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date, comments)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (student_id, assessment_id, score_float, letter_grade, date, comments))
                self.conn.commit()

                messagebox.showinfo("Success", "Grade added successfully!")
                dialog.destroy()
                self.refresh_grades()

            except ValueError:
                messagebox.showerror("Validation Error", "Score must be a valid number")
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error saving grade: {e}")

        ttk.Button(dialog, text="Save", command=save_grade).grid(row=6, column=0, columnspan=2, pady=20)

    def edit_grade_dialog(self):
        """Open dialog to edit selected grade"""
        # Get selected grade
        selection = self.grades_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a grade to edit")
            return

        item = self.grades_tree.item(selection[0])
        grade_id = item['values'][0]

        # Fetch grade details
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT g.grade_id, g.student_id, g.assessment_id, g.score, g.submission_date, g.comments,
                       s.first_name, s.last_name, a.assessment_name, a.max_points, m.module_name
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

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Grade")
        dialog.geometry("500x550")

        # Make dialog modal
        dialog.transient(self.root)
        safe_grab_set(dialog)

        # Display student info (read-only)
        ttk.Label(dialog, text="Student:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        student_label = ttk.Label(dialog, text=f"{grade_data[1]} - {grade_data[6]} {grade_data[7]}")
        student_label.grid(row=0, column=1, padx=10, pady=10, sticky='w')

        # Display assessment info (read-only)
        ttk.Label(dialog, text="Assessment:").grid(row=1, column=0, padx=10, pady=10, sticky='w')
        assessment_label = ttk.Label(dialog, text=f"{grade_data[8]} ({grade_data[10]})")
        assessment_label.grid(row=1, column=1, padx=10, pady=10, sticky='w')

        # Max points display
        ttk.Label(dialog, text="Max Points:").grid(row=2, column=0, padx=10, pady=10, sticky='w')
        max_points_label = ttk.Label(dialog, text=str(grade_data[9]))
        max_points_label.grid(row=2, column=1, padx=10, pady=10, sticky='w')

        # Score entry (editable)
        ttk.Label(dialog, text="Score:").grid(row=3, column=0, padx=10, pady=10, sticky='w')
        score_var = tk.StringVar(value=str(grade_data[3]))
        score_entry = ttk.Entry(dialog, textvariable=score_var, width=37)
        score_entry.grid(row=3, column=1, padx=10, pady=10)

        # Submission date
        ttk.Label(dialog, text="Submission Date:").grid(row=4, column=0, padx=10, pady=10, sticky='w')
        date_var = tk.StringVar(value=grade_data[4] if grade_data[4] else datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(dialog, textvariable=date_var, width=37)
        date_entry.grid(row=4, column=1, padx=10, pady=10)

        # Comments
        ttk.Label(dialog, text="Comments:").grid(row=5, column=0, padx=10, pady=10, sticky='nw')
        comments_text = tk.Text(dialog, width=35, height=8)
        comments_text.grid(row=5, column=1, padx=10, pady=10)
        if grade_data[5]:
            comments_text.insert('1.0', grade_data[5])

        # Save button
        def update_grade():
            score = score_var.get()
            date = date_var.get()
            comments = comments_text.get('1.0', 'end-1c')

            # Validation
            if not score:
                messagebox.showerror("Validation Error", "Please enter a score")
                return

            try:
                score_float = float(score)
                max_points = float(grade_data[9])

                if score_float < 0:
                    messagebox.showerror("Validation Error", "Score cannot be negative")
                    return
                if score_float > max_points:
                    messagebox.showerror("Validation Error", f"Score cannot exceed max points ({max_points})")
                    return

                # Calculate percentage and letter grade
                percentage = (score_float / max_points) * 100
                letter_grade = self.percentage_to_letter(percentage)

                # Update grade
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE grades
                    SET score = ?, letter_grade = ?, submission_date = ?, comments = ?
                    WHERE grade_id = ?
                """, (score_float, letter_grade, date, comments, grade_id))
                self.conn.commit()

                messagebox.showinfo("Success", "Grade updated successfully!")
                dialog.destroy()
                self.refresh_grades()

            except ValueError:
                messagebox.showerror("Validation Error", "Score must be a valid number")
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error updating grade: {e}")

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Update", command=update_grade).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def delete_grade(self):
        """Delete selected grade"""
        # Get selected grade
        selection = self.grades_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a grade to delete")
            return

        item = self.grades_tree.item(selection[0])
        grade_id = item['values'][0]
        student_name = item['values'][1]
        assessment_name = item['values'][2]

        # Confirm deletion
        if not messagebox.askyesno("Confirm Deletion",
                                   f"Are you sure you want to delete the grade for:\n\n"
                                   f"Student: {student_name}\n"
                                   f"Assessment: {assessment_name}\n\n"
                                   f"This action cannot be undone."):
            return

        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM grades WHERE grade_id = ?", (grade_id,))
            self.conn.commit()

            messagebox.showinfo("Success", "Grade deleted successfully!")
            self.refresh_grades()

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

                cursor = self.conn.cursor()

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

                self.conn.commit()

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
            cursor = self.conn.cursor()
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
                cursor = self.conn.cursor()

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

                self.conn.commit()
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
        """Calculate GPAs for all students"""
        try:
            cursor = self.conn.cursor()

            # Get all students
            cursor.execute("SELECT student_id, first_name, last_name FROM students")
            students = cursor.fetchall()

            results = []
            updated_count = 0

            for student in students:
                student_id = student[0]
                name = f"{student[1]} {student[2]}"

                # Get all grades for student with module credits
                cursor.execute("""
                    SELECT g.letter_grade, m.credits
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    JOIN modules m ON a.module_code = m.module_code
                    WHERE g.student_id = ?
                """, (student_id,))

                grades = cursor.fetchall()

                if not grades:
                    results.append(f"{name}: No grades found")
                    continue

                # Calculate weighted GPA
                total_grade_points = 0
                total_credits = 0

                for grade in grades:
                    letter_grade = grade[0]
                    credits = grade[1] if grade[1] else 1

                    gpa_value = self.letter_to_gpa(letter_grade)
                    total_grade_points += gpa_value * credits
                    total_credits += credits

                if total_credits > 0:
                    gpa = total_grade_points / total_credits

                    # Update or insert module grades (using a summary approach)
                    # Note: This is a simplified version - in production you might want
                    # to calculate final grades per module instead of overall GPA
                    results.append(f"{name}: GPA = {gpa:.2f}")
                    updated_count += 1
                else:
                    results.append(f"{name}: No credits found")

            self.conn.commit()

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
        """Show comprehensive grade statistics"""
        try:
            cursor = self.conn.cursor()

            # Get overall statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_grades,
                    AVG(g.score) as avg_score,
                    MIN(g.score) as min_score,
                    MAX(g.score) as max_score
                FROM grades g
            """)
            overall_stats = cursor.fetchone()

            if not overall_stats or overall_stats[0] == 0:
                messagebox.showinfo("No Data", "No grades available for statistics")
                return

            # Create statistics dialog
            stats_dialog = tk.Toplevel(self.root)
            stats_dialog.title("Grade Statistics")
            stats_dialog.geometry("800x700")

            # Notebook for different stat views
            notebook = ttk.Notebook(stats_dialog)
            notebook.pack(fill='both', expand=True, padx=10, pady=10)

            # Overall Statistics Tab
            overall_frame = ttk.Frame(notebook)
            notebook.add(overall_frame, text="Overall Statistics")

            stats_text = scrolledtext.ScrolledText(overall_frame, width=80, height=35)
            stats_text.pack(fill='both', expand=True, padx=10, pady=10)

            stats_text.insert('end', "=== OVERALL GRADE STATISTICS ===\n\n")
            stats_text.insert('end', f"Total Grades: {overall_stats[0]}\n")
            stats_text.insert('end', f"Average Score: {overall_stats[1]:.2f}\n")
            stats_text.insert('end', f"Minimum Score: {overall_stats[2]:.2f}\n")
            stats_text.insert('end', f"Maximum Score: {overall_stats[3]:.2f}\n\n")

            # Grade distribution
            cursor.execute("""
                SELECT letter_grade, COUNT(*) as count
                FROM grades
                GROUP BY letter_grade
                ORDER BY letter_grade
            """)
            grade_dist = cursor.fetchall()

            stats_text.insert('end', "=== GRADE DISTRIBUTION ===\n\n")
            for grade, count in grade_dist:
                percentage = (count / overall_stats[0]) * 100
                stats_text.insert('end', f"{grade}: {count} ({percentage:.1f}%)\n")

            # Per-Assessment Statistics Tab
            assessment_frame = ttk.Frame(notebook)
            notebook.add(assessment_frame, text="By Assessment")

            assessment_text = scrolledtext.ScrolledText(assessment_frame, width=80, height=35)
            assessment_text.pack(fill='both', expand=True, padx=10, pady=10)

            cursor.execute("""
                SELECT
                    a.assessment_name,
                    m.module_name,
                    COUNT(g.grade_id) as num_grades,
                    AVG(g.score) as avg_score,
                    MIN(g.score) as min_score,
                    MAX(g.score) as max_score,
                    a.max_points
                FROM assessments a
                JOIN modules m ON a.module_code = m.module_code
                LEFT JOIN grades g ON a.assessment_id = g.assessment_id
                GROUP BY a.assessment_id
                HAVING num_grades > 0
                ORDER BY m.module_name, a.assessment_name
            """)
            assessment_stats = cursor.fetchall()

            assessment_text.insert('end', "=== STATISTICS BY ASSESSMENT ===\n\n")
            for stat in assessment_stats:
                assessment_text.insert('end', f"Assessment: {stat[0]}\n")
                assessment_text.insert('end', f"Module: {stat[1]}\n")
                assessment_text.insert('end', f"Number of Grades: {stat[2]}\n")
                assessment_text.insert('end', f"Average Score: {stat[3]:.2f} / {stat[6]}\n")
                assessment_text.insert('end', f"Average Percentage: {(stat[3]/stat[6]*100):.2f}%\n")
                assessment_text.insert('end', f"Min Score: {stat[4]:.2f}\n")
                assessment_text.insert('end', f"Max Score: {stat[5]:.2f}\n")
                assessment_text.insert('end', f"{'-'*60}\n\n")

            # Per-Student Statistics Tab
            student_frame = ttk.Frame(notebook)
            notebook.add(student_frame, text="By Student")

            student_text = scrolledtext.ScrolledText(student_frame, width=80, height=35)
            student_text.pack(fill='both', expand=True, padx=10, pady=10)

            cursor.execute("""
                SELECT
                    s.student_id,
                    s.first_name,
                    s.last_name,
                    COUNT(g.grade_id) as num_grades,
                    AVG(g.score) as avg_score,
                    MIN(g.score) as min_score,
                    MAX(g.score) as max_score
                FROM students s
                LEFT JOIN grades g ON s.student_id = g.student_id
                GROUP BY s.student_id
                HAVING num_grades > 0
                ORDER BY s.last_name, s.first_name
            """)
            student_stats = cursor.fetchall()

            student_text.insert('end', "=== STATISTICS BY STUDENT ===\n\n")
            for stat in student_stats:
                student_text.insert('end', f"Student: {stat[1]} {stat[2]} ({stat[0]})\n")
                student_text.insert('end', f"Number of Grades: {stat[3]}\n")
                student_text.insert('end', f"Average Score: {stat[4]:.2f}\n")
                student_text.insert('end', f"Min Score: {stat[5]:.2f}\n")
                student_text.insert('end', f"Max Score: {stat[6]:.2f}\n")

                # Calculate GPA for student
                cursor.execute("""
                    SELECT g.letter_grade, m.credits
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    JOIN modules m ON a.module_code = m.module_code
                    WHERE g.student_id = ?
                """, (stat[0],))
                grades = cursor.fetchall()

                total_grade_points = 0
                total_credits = 0
                for grade in grades:
                    gpa_value = self.letter_to_gpa(grade[0])
                    credits = grade[1] if grade[1] else 1
                    total_grade_points += gpa_value * credits
                    total_credits += credits

                if total_credits > 0:
                    gpa = total_grade_points / total_credits
                    student_text.insert('end', f"GPA: {gpa:.2f}\n")

                student_text.insert('end', f"{'-'*60}\n\n")

            # Disable editing
            stats_text.config(state='disabled')
            assessment_text.config(state='disabled')
            student_text.config(state='disabled')

            ttk.Button(stats_dialog, text="Close", command=stats_dialog.destroy).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error calculating statistics: {e}")

    def refresh_grades(self):
        """Refresh the grades list with current filters"""
        try:
            # Clear existing items
            for item in self.grades_tree.get_children():
                self.grades_tree.delete(item)

            # Build query based on filters
            query = """
                SELECT
                    g.grade_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    a.assessment_name,
                    g.score,
                    a.max_points,
                    ROUND((g.score / a.max_points) * 100, 2) as percentage,
                    g.letter_grade,
                    g.submission_date
                FROM grades g
                JOIN students s ON g.student_id = s.student_id
                JOIN assessments a ON g.assessment_id = a.assessment_id
                WHERE 1=1
            """

            params = []

            # Apply student filter
            if hasattr(self, 'grade_student_filter_var'):
                student_filter = self.grade_student_filter_var.get()
                if student_filter and student_filter != "All Students":
                    student_id = student_filter.split(' - ')[0]
                    query += " AND s.student_id = ?"
                    params.append(student_id)

            # Apply assessment filter
            if hasattr(self, 'grade_assessment_filter_var'):
                assessment_filter = self.grade_assessment_filter_var.get()
                if assessment_filter and assessment_filter != "All Assessments":
                    assessment_id = assessment_filter.split(' - ')[0]
                    query += " AND a.assessment_id = ?"
                    params.append(assessment_id)

            query += " ORDER BY g.submission_date DESC, s.last_name, s.first_name"

            cursor = self.get_safe_cursor()
            cursor.execute(query, params)
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

            # Populate student filter
            if hasattr(self, 'grade_student_combo'):
                cursor.execute("""
                    SELECT DISTINCT s.student_id, s.first_name, s.last_name
                    FROM students s
                    JOIN grades g ON s.student_id = g.student_id
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

                # Combine both sources
                all_assessments = list(assessments_from_assessments) + list(assessments_from_assignments)
                assessment_list = ["All Assessments"] + [f"{a[0]} - {a[1]} ({a[2]})" for a in all_assessments]
                safe_combo_update(self, 'grade_assessment_combo', assessment_list)

        except (ConnectionError, sqlite3.Error) as e:
            # Silently fail - filters just won't be populated
            pass

