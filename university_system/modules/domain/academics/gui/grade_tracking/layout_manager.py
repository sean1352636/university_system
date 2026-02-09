"""UI layout and navigation"""

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
from university_system.modules.domain.academics.gui.grade_tracking.utils import ensure_column_exists

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

class LayoutManager:
    """UI layout and navigation"""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.auth = app.auth
        self.conn = app.conn
        self.sidebar_canvas = None  # Will store canvas reference for cleanup

    def setup_ui(self):
        """Setup the main user interface with sidebar"""
        # Create main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create sidebar frame
        sidebar_frame = ttk.Frame(main_container, width=200)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sidebar_frame.pack_propagate(False)  # Maintain fixed width

        # Add header label to sidebar
        header_label = ttk.Label(sidebar_frame, text="📋 Navigation",
                                font=('Arial', 10, 'bold'),
                                anchor='center')
        header_label.pack(fill=tk.X, pady=(0, 5))

        # Create scrollable area for buttons
        canvas = tk.Canvas(sidebar_frame, width=180, highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        # Configure scroll region when frame size changes
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Add mouse wheel scrolling support
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        # Bind mouse wheel events (works for Windows/Mac)
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Bind for Linux
        canvas.bind_all("<Button-4>", _on_mousewheel_linux)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux)

        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store canvas reference for potential cleanup
        self.sidebar_canvas = canvas

        # Create content area
        self.content_frame = ttk.Frame(main_container)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Current view tracking
        self.current_view = None

        # Get user role
        is_admin = self.app.is_admin()
        is_staff = self.app.is_staff()
        is_student = self.app.is_student()

        # Define buttons based on role - Role-based access control
        self.view_buttons = []

        # Admin gets all features
        if is_admin:
            self.view_buttons = [
                ("Students", self.show_student_view),
                ("Modules", self.show_module_view),
                ("Assessments", self.show_assessment_view),
                ("Grades", self.show_grades_view),
                ("Grade Management", self.show_grade_management_view),
                ("View Grades", self.show_view_grades_view),
                ("Statistics & Analysis", self.show_statistics_view),
                ("Transcripts", self.show_transcript_view),
                ("Grade Curve Analysis", self.show_curve_analysis_view),
                ("Learning Outcomes", self.show_learning_outcomes_view),
                ("Competencies", self.show_competency_view),
                ("Predictive Analytics", self.show_predictive_analytics_view),
                ("Performance Analysis", self.show_performance_analysis_view),
                ("Analytics", self.show_analytics_view),
                ("Reports", self.show_reports_view),
                ("🏠 Return to Main Menu", self.return_to_main_menu)
            ]
        # Staff/Instructor gets grading and analytics features
        elif is_staff:
            self.view_buttons = [
                ("Students", self.show_student_view),
                ("Modules", self.show_module_view),
                ("Assessments", self.show_assessment_view),
                ("Grades", self.show_grades_view),
                ("Grade Management", self.show_grade_management_view),
                ("View Grades", self.show_view_grades_view),
                ("Statistics & Analysis", self.show_statistics_view),
                ("Transcripts", self.show_transcript_view),
                ("Analytics", self.show_analytics_view),
                ("Reports", self.show_reports_view),
                ("🏠 Return to Main Menu", self.return_to_main_menu)
            ]
        # Students get limited read-only features
        elif is_student:
            self.view_buttons = [
                ("View Grades", self.show_view_grades_view),
                ("Transcripts", self.show_transcript_view),
                ("🏠 Return to Main Menu", self.return_to_main_menu)
            ]
        # Default (no auth or unknown role) - show basic features
        else:
            self.view_buttons = [
                ("Students", self.show_student_view),
                ("Modules", self.show_module_view),
                ("Assessments", self.show_assessment_view),
                ("Grades", self.show_grades_view),
                ("Grade Management", self.show_grade_management_view),
                ("View Grades", self.show_view_grades_view),
                ("Statistics & Analysis", self.show_statistics_view),
                ("Transcripts", self.show_transcript_view),
                ("Analytics", self.show_analytics_view),
                ("Reports", self.show_reports_view),
                ("🏠 Return to Main Menu", self.return_to_main_menu)
            ]

        # Create buttons
        self.buttons = {}
        for text, command in self.view_buttons:
            btn = ttk.Button(scrollable_frame, text=text, command=command, width=20)
            btn.pack(fill=tk.X, pady=2, padx=5)
            self.buttons[text] = btn

        # Initialize with appropriate default view based on role
        if is_student:
            # Students start with their grades view
            self.show_view_grades_view()
        else:
            # Admin and Staff start with student management view
            self.show_student_view()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = tk.Label(self.root, textvariable=self.status_var, 
                             relief='sunken', anchor='w', bg='#ecf0f1')
        status_bar.pack(side='bottom', fill='x')
    

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def _clear_content(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_student_view(self):
        """Show student management view"""
        self._clear_content()
        self.current_view = "Students"
        if hasattr(self.app, 'students'):
            # Call the nested function if it exists
            if hasattr(self.app.students, 'create_student_content'):
                self.app.students.create_student_content()

    def show_module_view(self):
        """Show module management view"""
        self._clear_content()
        self.current_view = "Modules"
        if hasattr(self.app, 'modules'):
            if hasattr(self.app.modules, 'create_module_content'):
                self.app.modules.create_module_content()

    def show_assessment_view(self):
        """Show assessment management view"""
        self._clear_content()
        self.current_view = "Assessments"
        if hasattr(self.app, 'assessments'):
            if hasattr(self.app.assessments, 'create_assessment_content'):
                self.app.assessments.create_assessment_content()

    def show_grades_view(self):
        """Show grades view - Main grade entry and editing interface"""
        self._clear_content()
        self.current_view = "Grades"
        if hasattr(self.app, 'grades'):
            if hasattr(self.app.grades, 'create_grades_content'):
                self.app.grades.create_grades_content()

    def show_grade_management_view(self):
        """Show grade management view - Analytics, bulk operations, and management tools"""
        self._clear_content()
        self.current_view = "Grade Management"
        if hasattr(self.app, 'analytics'):
            if hasattr(self.app.analytics, 'create_analytics_content'):
                self.app.analytics.create_analytics_content()
            else:
                messagebox.showinfo("Info", "Analytics features are not available")
        else:
            messagebox.showinfo("Info", "Grade management features are not available")

    def show_view_grades_view(self):
        """Show view grades view - Read-only grade statistics and reports"""
        self._clear_content()
        self.current_view = "View Grades"
        if hasattr(self.app, 'grades'):
            if hasattr(self.app.grades, 'show_grade_statistics'):
                self.app.grades.show_grade_statistics()
            elif hasattr(self.app.analytics, 'create_reports_content'):
                # Fallback to reports if statistics not available
                self.app.analytics.create_reports_content()
            else:
                messagebox.showinfo("Info", "Grade viewing features are not available")
        else:
            messagebox.showinfo("Info", "Grade viewing features are not available")

    def show_statistics_view(self):
        """Show statistics view"""
        self._clear_content()
        self.current_view = "Statistics"
        if hasattr(self.app, 'analytics'):
            if hasattr(self.app.analytics, 'create_analytics_content'):
                self.app.analytics.create_analytics_content()

    def show_transcript_view(self):
        """Show transcript view"""
        self._clear_content()
        self.current_view = "Transcripts"
        # This might be in students manager
        if hasattr(self.app, 'students'):
            if hasattr(self.app.students, 'generate_individual_transcript'):
                self.app.students.generate_individual_transcript()

    def show_curve_analysis_view(self):
        """Show grade curve analysis view"""
        self.show_analytics_view()

    def show_learning_outcomes_view(self):
        """Show learning outcomes view"""
        self.show_analytics_view()

    def show_competency_view(self):
        """Show competency view"""
        self._clear_content()
        self.current_view = "Competencies"
        if hasattr(self.app, 'analytics'):
            if hasattr(self.app.analytics, 'create_competency_content'):
                self.app.analytics.create_competency_content()

    def show_predictive_analytics_view(self):
        """Show predictive analytics view"""
        self._clear_content()
        self.current_view = "Predictive Analytics"
        if hasattr(self.app, 'analytics'):
            if hasattr(self.app.analytics, 'create_prediction_content'):
                self.app.analytics.create_prediction_content()

    def show_performance_analysis_view(self):
        """Show performance analysis view"""
        self.show_analytics_view()

    def show_analytics_view(self):
        """Show analytics view"""
        self._clear_content()
        self.current_view = "Analytics"
        if hasattr(self.app, 'analytics'):
            if hasattr(self.app.analytics, 'create_analytics_content'):
                self.app.analytics.create_analytics_content()

    def show_reports_view(self):
        """Show reports view"""
        self._clear_content()
        self.current_view = "Reports"
        if hasattr(self.app, 'analytics'):
            if hasattr(self.app.analytics, 'create_reports_content'):
                self.app.analytics.create_reports_content()

    def _widget_exists(self, widget):
        """Return True if widget exists and is not destroyed."""
        if widget is None:
            return False
        try:
            return bool(widget.winfo_exists())
        except Exception:
            return False
    

    def update_status(self, message):
        """Update status bar message"""
        if hasattr(self, 'status_var'):
            self.status_var.set(message)
            if hasattr(self, 'root'):
                self.root.update_idletasks()
    
