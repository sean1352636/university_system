"""Assessment management"""

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
from university_system.modules.domain.academics.services.assessment_service import AssessmentAssignmentService

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




class AssessmentManager:
    """Assessment management"""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.auth = app.auth

    @property
    def content_frame(self):
        """Dynamically get content frame from layout"""
        if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'content_frame'):
            return self.app.layout.content_frame
        return None

    def create_assessment_content(self):
        """Create assessment management content"""
        # Assessment management controls
        control_frame = ttk.Frame(self.content_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
            
        ttk.Button(control_frame, text="Add Assessment",
                  command=self.add_assessment_dialog).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Edit Assessment",
                  command=self.edit_assessment_dialog).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Delete Assessment",
                  command=self.delete_assessment).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Copy Assessment",
                  command=self.copy_assessment).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self.refresh_assessments).pack(side='left', padx=5)
        ttk.Button(control_frame, text="🔄 Load from Assignments",
                  command=self.sync_from_assignments).pack(side='right', padx=5)
            
        # Filter frame
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill='x', padx=10, pady=5)
            
        ttk.Label(filter_frame, text="Filter by Module:").pack(side='left', padx=5)
        self.assessment_module_filter_var = tk.StringVar()
        self.assessment_module_combo = ttk.Combobox(filter_frame, 
                                                   textvariable=self.assessment_module_filter_var, 
                                                   width=20, state='readonly')
        self.assessment_module_combo.pack(side='left', padx=5)
        self.assessment_module_combo.bind('<<ComboboxSelected>>', self.filter_assessments)
            
        # Assessment list
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
            
        columns = ('ID', 'Name', 'Type', 'Module', 'Max Points', 'Weight %', 'Due Date')
        self.assessment_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=25)
            
        for col in columns:
            self.assessment_tree.heading(col, text=col)
            self.assessment_tree.column(col, width=120, anchor='center')
            
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.assessment_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=self.assessment_tree.xview)
        self.assessment_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
        self.assessment_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
    
        # Load assessment data
        self.refresh_assessments()
    
        # Populate filter combos now that they exist
        self.populate_filter_combos()
    

    def generate_assessment_analysis(self):
        """Generate assessment analysis"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT 
                a.assessment_id,
                a.assessment_name,
                a.module_code,
                a.assessment_type,
                a.max_points,
                COUNT(g.grade_id) AS submissions,
                AVG(
                    CASE 
                        WHEN a.max_points IS NOT NULL AND a.max_points > 0 
                        THEN (g.score / a.max_points) * 100 
                    END
                ) AS avg_percentage,
                SUM(CASE WHEN g.letter_grade = 'F' THEN 1 ELSE 0 END) AS fail_count
            FROM assessments a
            LEFT JOIN grades g ON a.assessment_id = g.assessment_id
            GROUP BY a.assessment_id, a.assessment_name, a.module_code, a.assessment_type, a.max_points
            ''')
            assessment_rows = cursor.fetchall()
    
            if not assessment_rows:
                self._display_report(
                    "Assessment Analysis Report",
                    [("Summary", ["No assessments have been recorded."])],
                    None
                )
                return
    
            summary_lines = [
                f"Total Assessments: {len(assessment_rows)}",
                f"Assessments With Submitted Grades: {sum(1 for row in assessment_rows if row[5] > 0)}",
                f"Average Submission Count: "
                f"{(sum(row[5] for row in assessment_rows) / len(assessment_rows)):.1f}",
                f"Average Assessment Score: "
                f"{(sum(row[6] for row in assessment_rows if row[6] is not None) / max(1, sum(1 for row in assessment_rows if row[6] is not None))):.1f}%"
                if any(row[6] is not None for row in assessment_rows) else "Average Assessment Score: N/A"
            ]
    
            top_assessments = sorted(
                [row for row in assessment_rows if row[6] is not None],
                key=lambda r: r[6],
                reverse=True
            )[:5]
    
            top_lines = [
                f"{idx + 1}. {row[1]} [{row[2]}] - Avg Score {row[6]:.1f}% "
                f"(Submissions: {row[5]})"
                for idx, row in enumerate(top_assessments)
            ]
    
            challenging_assessments = sorted(
                [row for row in assessment_rows if row[6] is not None and row[5] > 0],
                key=lambda r: (r[6], -r[5])
            )[:5]
    
            challenging_lines = [
                f"{idx + 1}. {row[1]} [{row[2]}] - Avg Score {row[6]:.1f}% "
                f"(Fail Count: {row[7]})"
                for idx, row in enumerate(challenging_assessments)
            ]
    
            missing_lines = [
                f"{row[1]} [{row[2]}] - No submissions recorded"
                for row in assessment_rows if row[5] == 0
            ][:5]
    
            sections = [
                ("Assessment Overview", summary_lines),
                ("High Performing Assessments", top_lines),
                ("Assessments Requiring Review", challenging_lines),
                ("Assessments Awaiting Grades", missing_lines)
            ]
    
            footer = (
                "Consider reviewing assessments with low average scores or high failure counts to adjust support "
                "resources or re-examine assessment design."
            )
    
            self._display_report("Assessment Analysis Report", sections, footer)
    
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate assessment analysis: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate assessment analysis: {e}")
        finally:
            if conn:
                conn.close()

    def add_assessment_dialog(self):
        """Open dialog to add a new assessment"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Assessment")
        dialog.geometry("600x700")

        # Make dialog modal
        dialog.transient(self.root)
        safe_grab_set(dialog)

        # Assessment name
        ttk.Label(dialog, text="Assessment Name:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=40)
        name_entry.grid(row=0, column=1, padx=10, pady=10)

        # Assessment type
        ttk.Label(dialog, text="Assessment Type:").grid(row=1, column=0, padx=10, pady=10, sticky='w')
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(dialog, textvariable=type_var, width=38, state='readonly')
        type_combo['values'] = ['Exam', 'Quiz', 'Assignment', 'Project', 'Lab', 'Presentation', 'Essay', 'Other']
        type_combo.grid(row=1, column=1, padx=10, pady=10)

        # Module selection
        ttk.Label(dialog, text="Module:").grid(row=2, column=0, padx=10, pady=10, sticky='w')
        module_var = tk.StringVar()
        module_combo = ttk.Combobox(dialog, textvariable=module_var, width=38, state='readonly')
        module_combo.grid(row=2, column=1, padx=10, pady=10)

        # Load modules from database
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
            modules = cursor.fetchall()
            module_list = [f"{m[0]} - {m[1]}" for m in modules]
            module_combo['values'] = module_list
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading modules: {e}")
            dialog.destroy()
            return

        # Max points
        ttk.Label(dialog, text="Max Points:").grid(row=3, column=0, padx=10, pady=10, sticky='w')
        max_points_var = tk.StringVar()
        max_points_entry = ttk.Entry(dialog, textvariable=max_points_var, width=40)
        max_points_entry.grid(row=3, column=1, padx=10, pady=10)

        # Weight (percentage)
        ttk.Label(dialog, text="Weight (%):").grid(row=4, column=0, padx=10, pady=10, sticky='w')
        weight_var = tk.StringVar()
        weight_entry = ttk.Entry(dialog, textvariable=weight_var, width=40)
        weight_entry.grid(row=4, column=1, padx=10, pady=10)

        # Due date
        ttk.Label(dialog, text="Due Date (YYYY-MM-DD):").grid(row=5, column=0, padx=10, pady=10, sticky='w')
        due_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        due_date_entry = ttk.Entry(dialog, textvariable=due_date_var, width=40)
        due_date_entry.grid(row=5, column=1, padx=10, pady=10)

        # Description
        ttk.Label(dialog, text="Description:").grid(row=6, column=0, padx=10, pady=10, sticky='nw')
        description_text = scrolledtext.ScrolledText(dialog, width=38, height=5)
        description_text.grid(row=6, column=1, padx=10, pady=10)

        # Rubric
        ttk.Label(dialog, text="Rubric:").grid(row=7, column=0, padx=10, pady=10, sticky='nw')
        rubric_text = scrolledtext.ScrolledText(dialog, width=38, height=5)
        rubric_text.grid(row=7, column=1, padx=10, pady=10)

        # Save button
        def save_assessment():
            name = name_var.get().strip()
            assessment_type = type_var.get()
            module = module_var.get()
            max_points = max_points_var.get().strip()
            weight = weight_var.get().strip()
            due_date = due_date_var.get().strip()
            description = description_text.get('1.0', 'end-1c').strip()
            rubric = rubric_text.get('1.0', 'end-1c').strip()

            # Validation
            if not name:
                messagebox.showerror("Validation Error", "Please enter an assessment name")
                return
            if not assessment_type:
                messagebox.showerror("Validation Error", "Please select an assessment type")
                return
            if not module:
                messagebox.showerror("Validation Error", "Please select a module")
                return
            if not max_points:
                messagebox.showerror("Validation Error", "Please enter max points")
                return
            if not weight:
                messagebox.showerror("Validation Error", "Please enter weight percentage")
                return

            try:
                max_points_float = float(max_points)
                weight_float = float(weight)

                if max_points_float <= 0:
                    messagebox.showerror("Validation Error", "Max points must be greater than 0")
                    return
                if weight_float < 0 or weight_float > 100:
                    messagebox.showerror("Validation Error", "Weight must be between 0 and 100")
                    return

                # Extract module code
                module_code = module.split(' - ')[0]

                # Insert assessment
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO assessments (assessment_name, assessment_type, module_code,
                                           max_points, weight, due_date, description, rubric)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, assessment_type, module_code, max_points_float, weight_float,
                      due_date, description, rubric))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Assessment added successfully!")
                dialog.destroy()
                self.refresh_assessments()
                if hasattr(self.app, 'populate_filter_combos'):
                    self.app.populate_filter_combos()

            except ValueError:
                messagebox.showerror("Validation Error", "Max points and weight must be valid numbers")
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error saving assessment: {e}")

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Save", command=save_assessment).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def edit_assessment_dialog(self):
        """Open dialog to edit an existing assessment"""
        # Get selected assessment
        selection = self.assessment_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an assessment to edit")
            return

        item = self.assessment_tree.item(selection[0])
        assessment_id = item['values'][0]

        # Load assessment data
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT assessment_name, assessment_type, module_code, max_points,
                       weight, due_date, description, rubric
                FROM assessments
                WHERE assessment_id = ?
            """, (assessment_id,))
            assessment_data = cursor.fetchone()

            if not assessment_data:
                messagebox.showerror("Error", "Assessment not found")
                return

            # Create edit dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Assessment")
            dialog.geometry("600x700")
            dialog.transient(self.root)
            safe_grab_set(dialog)

            # Assessment name
            ttk.Label(dialog, text="Assessment Name:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
            name_var = tk.StringVar(value=assessment_data[0])
            name_entry = ttk.Entry(dialog, textvariable=name_var, width=40)
            name_entry.grid(row=0, column=1, padx=10, pady=10)

            # Assessment type
            ttk.Label(dialog, text="Assessment Type:").grid(row=1, column=0, padx=10, pady=10, sticky='w')
            type_var = tk.StringVar(value=assessment_data[1])
            type_combo = ttk.Combobox(dialog, textvariable=type_var, width=38, state='readonly')
            type_combo['values'] = ['Exam', 'Quiz', 'Assignment', 'Project', 'Lab', 'Presentation', 'Essay', 'Other']
            type_combo.grid(row=1, column=1, padx=10, pady=10)

            # Module selection
            ttk.Label(dialog, text="Module:").grid(row=2, column=0, padx=10, pady=10, sticky='w')
            module_var = tk.StringVar()
            module_combo = ttk.Combobox(dialog, textvariable=module_var, width=38, state='readonly')
            module_combo.grid(row=2, column=1, padx=10, pady=10)

            # Load modules and set current
            cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
            modules = cursor.fetchall()
            module_list = [f"{m[0]} - {m[1]}" for m in modules]
            module_combo['values'] = module_list

            # Set current module
            current_module = assessment_data[2]
            for module in modules:
                if module[0] == current_module:
                    module_var.set(f"{module[0]} - {module[1]}")
                    break

            # Max points
            ttk.Label(dialog, text="Max Points:").grid(row=3, column=0, padx=10, pady=10, sticky='w')
            max_points_var = tk.StringVar(value=str(assessment_data[3]))
            max_points_entry = ttk.Entry(dialog, textvariable=max_points_var, width=40)
            max_points_entry.grid(row=3, column=1, padx=10, pady=10)

            # Weight
            ttk.Label(dialog, text="Weight (%):").grid(row=4, column=0, padx=10, pady=10, sticky='w')
            weight_var = tk.StringVar(value=str(assessment_data[4]))
            weight_entry = ttk.Entry(dialog, textvariable=weight_var, width=40)
            weight_entry.grid(row=4, column=1, padx=10, pady=10)

            # Due date
            ttk.Label(dialog, text="Due Date (YYYY-MM-DD):").grid(row=5, column=0, padx=10, pady=10, sticky='w')
            due_date_var = tk.StringVar(value=assessment_data[5] or '')
            due_date_entry = ttk.Entry(dialog, textvariable=due_date_var, width=40)
            due_date_entry.grid(row=5, column=1, padx=10, pady=10)

            # Description
            ttk.Label(dialog, text="Description:").grid(row=6, column=0, padx=10, pady=10, sticky='nw')
            description_text = scrolledtext.ScrolledText(dialog, width=38, height=5)
            description_text.grid(row=6, column=1, padx=10, pady=10)
            description_text.insert('1.0', assessment_data[6] or '')

            # Rubric
            ttk.Label(dialog, text="Rubric:").grid(row=7, column=0, padx=10, pady=10, sticky='nw')
            rubric_text = scrolledtext.ScrolledText(dialog, width=38, height=5)
            rubric_text.grid(row=7, column=1, padx=10, pady=10)
            rubric_text.insert('1.0', assessment_data[7] or '')

            # Save button
            def update_assessment():
                name = name_var.get().strip()
                assessment_type = type_var.get()
                module = module_var.get()
                max_points = max_points_var.get().strip()
                weight = weight_var.get().strip()
                due_date = due_date_var.get().strip()
                description = description_text.get('1.0', 'end-1c').strip()
                rubric = rubric_text.get('1.0', 'end-1c').strip()

                # Validation
                if not name:
                    messagebox.showerror("Validation Error", "Please enter an assessment name")
                    return
                if not assessment_type:
                    messagebox.showerror("Validation Error", "Please select an assessment type")
                    return
                if not module:
                    messagebox.showerror("Validation Error", "Please select a module")
                    return
                if not max_points:
                    messagebox.showerror("Validation Error", "Please enter max points")
                    return
                if not weight:
                    messagebox.showerror("Validation Error", "Please enter weight percentage")
                    return

                try:
                    max_points_float = float(max_points)
                    weight_float = float(weight)

                    if max_points_float <= 0:
                        messagebox.showerror("Validation Error", "Max points must be greater than 0")
                        return
                    if weight_float < 0 or weight_float > 100:
                        messagebox.showerror("Validation Error", "Weight must be between 0 and 100")
                        return

                    # Extract module code
                    module_code = module.split(' - ')[0]

                    # Update assessment
                    update_conn = get_connection()
                    update_cursor = update_conn.cursor()
                    update_cursor.execute("""
                        UPDATE assessments
                        SET assessment_name = ?, assessment_type = ?, module_code = ?,
                            max_points = ?, weight = ?, due_date = ?, description = ?, rubric = ?
                        WHERE assessment_id = ?
                    """, (name, assessment_type, module_code, max_points_float, weight_float,
                          due_date, description, rubric, assessment_id))
                    update_conn.commit()
                    update_conn.close()

                    messagebox.showinfo("Success", "Assessment updated successfully!")
                    dialog.destroy()
                    self.refresh_assessments()
                    if hasattr(self.app, 'populate_filter_combos'):
                        self.app.populate_filter_combos()

                except ValueError:
                    messagebox.showerror("Validation Error", "Max points and weight must be valid numbers")
                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Error updating assessment: {e}")

            button_frame = ttk.Frame(dialog)
            button_frame.grid(row=8, column=0, columnspan=2, pady=20)
            ttk.Button(button_frame, text="Update", command=update_assessment).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading assessment: {e}")
        finally:
            if conn:
                conn.close()

    def delete_assessment(self):
        """Delete selected assessment"""
        selection = self.assessment_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an assessment to delete")
            return

        item = self.assessment_tree.item(selection[0])
        assessment_id = item['values'][0]
        assessment_name = item['values'][1]

        # Confirm deletion
        if not messagebox.askyesno("Confirm Deletion",
                                   f"Are you sure you want to delete '{assessment_name}'?\n\n"
                                   "This will also delete all associated grades!"):
            return

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Delete associated grades first (foreign key constraint)
            cursor.execute("DELETE FROM grades WHERE assessment_id = ?", (assessment_id,))

            # Delete the assessment
            cursor.execute("DELETE FROM assessments WHERE assessment_id = ?", (assessment_id,))

            conn.commit()
            messagebox.showinfo("Success", "Assessment deleted successfully!")
            self.refresh_assessments()
            if hasattr(self.app, 'populate_filter_combos'):
                self.app.populate_filter_combos()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error deleting assessment: {e}")
        finally:
            if conn:
                conn.close()

    def copy_assessment(self):
        """Copy selected assessment"""
        selection = self.assessment_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an assessment to copy")
            return

        item = self.assessment_tree.item(selection[0])
        assessment_id = item['values'][0]

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Load original assessment
            cursor.execute("""
                SELECT assessment_name, assessment_type, module_code, max_points,
                       weight, due_date, description, rubric
                FROM assessments
                WHERE assessment_id = ?
            """, (assessment_id,))
            assessment_data = cursor.fetchone()

            if not assessment_data:
                messagebox.showerror("Error", "Assessment not found")
                return

            # Create copy with "Copy of" prefix
            new_name = f"Copy of {assessment_data[0]}"

            # Insert the copy
            cursor.execute("""
                INSERT INTO assessments (assessment_name, assessment_type, module_code,
                                       max_points, weight, due_date, description, rubric)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_name, assessment_data[1], assessment_data[2], assessment_data[3],
                  assessment_data[4], assessment_data[5], assessment_data[6], assessment_data[7]))

            conn.commit()
            messagebox.showinfo("Success", f"Assessment copied successfully as '{new_name}'!")
            self.refresh_assessments()
            if hasattr(self.app, 'populate_filter_combos'):
                self.app.populate_filter_combos()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error copying assessment: {e}")
        finally:
            if conn:
                conn.close()

    def refresh_assessments(self):
        """Refresh the assessments list from database (includes both assessments and assignments)"""
        if not hasattr(self, 'assessment_tree'):
            return

        conn = None
        try:
            # Clear existing items
            for item in self.assessment_tree.get_children():
                self.assessment_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            # Get filter value if it exists
            filter_module = None
            if hasattr(self, 'assessment_module_filter_var'):
                filter_value = self.assessment_module_filter_var.get()
                if filter_value and filter_value != 'All':
                    filter_module = filter_value

            # Build query with optional filter for assessments table
            if filter_module:
                cursor.execute('''
                    SELECT assessment_id, assessment_name, assessment_type, module_code,
                           max_points, weight, due_date
                    FROM assessments
                    WHERE module_code = ?
                    ORDER BY due_date DESC, assessment_name
                ''', (filter_module,))
            else:
                cursor.execute('''
                    SELECT assessment_id, assessment_name, assessment_type, module_code,
                           max_points, weight, due_date
                    FROM assessments
                    ORDER BY due_date DESC, assessment_name
                ''')

            assessments_from_assessments = cursor.fetchall()

            # Build query for assignments table (created via assignment GUI)
            if filter_module:
                cursor.execute('''
                    SELECT 'A' || id as assessment_id, title as assessment_name,
                           'assignment' as assessment_type, module_code,
                           COALESCE(max_marks, 100) as max_points, 0 as weight, due_date
                    FROM assignments
                    WHERE module_code = ?
                    ORDER BY due_date DESC, title
                ''', (filter_module,))
            else:
                cursor.execute('''
                    SELECT 'A' || id as assessment_id, title as assessment_name,
                           'assignment' as assessment_type, module_code,
                           COALESCE(max_marks, 100) as max_points, 0 as weight, due_date
                    FROM assignments
                    ORDER BY due_date DESC, title
                ''')

            assessments_from_assignments = cursor.fetchall()

            # Combine and display all assessments
            all_assessments = list(assessments_from_assessments) + list(assessments_from_assignments)

            for row in all_assessments:
                assessment_id, name, atype, module, max_points, weight, due_date = row
                self.assessment_tree.insert('', 'end', values=(
                    assessment_id,
                    name,
                    atype or 'N/A',
                    module,
                    max_points or 0,
                    f"{weight or 0}%",
                    due_date or 'N/A'
                ))

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load assessments: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assessments: {e}")
        finally:
            if conn:
                conn.close()

    def filter_assessments(self, event=None):
        """Filter assessments by selected module"""
        self.refresh_assessments()

    def populate_filter_combos(self):
        """Populate filter comboboxes with current data"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Load modules for assessment filter
            if hasattr(self, 'assessment_module_combo'):
                cursor.execute("""
                    SELECT DISTINCT module_code
                    FROM modules
                    WHERE module_code IS NOT NULL AND module_code != ''
                    ORDER BY module_code
                """)
                module_results = cursor.fetchall()
                modules = ['All'] + [row[0] for row in module_results if row[0]]
                safe_combo_update(self, 'assessment_module_combo', modules)

                # Set default to 'All' if not already set
                if not self.assessment_module_filter_var.get():
                    self.assessment_module_filter_var.set('All')

        except sqlite3.Error as e:
            # Silent fail - filter combos are optional
            pass
        finally:
            if conn:
                conn.close()

    def sync_from_assignments(self):
        """Sync assessments from the assignments table"""
        try:
            # Get current user ID for creating assignments
            user_id = self.auth.current_user.get('id', 1) if hasattr(self, 'auth') and self.auth and self.auth.current_user else 1

            # Get all assessments
            assessments = AssessmentAssignmentService.get_all_assessments()

            if not assessments:
                messagebox.showinfo("Load Complete", "No assessments found to load from assignments")
                return

            loaded_count = 0
            skipped_count = 0

            for assessment in assessments:
                # Try to create assignment from assessment
                assignment_id = AssessmentAssignmentService.sync_assessment_to_assignment(
                    assessment['assessment_id'],
                    user_id
                )
                if assignment_id:
                    loaded_count += 1
                else:
                    skipped_count += 1

            # Reload the assessments display
            self.refresh_assessments()

            messagebox.showinfo(
                "Load Complete",
                f"Loaded {loaded_count} assignment(s) from assessments.\n"
                f"Skipped {skipped_count} (already exist or invalid)."
            )

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load from assignments: {e}")

