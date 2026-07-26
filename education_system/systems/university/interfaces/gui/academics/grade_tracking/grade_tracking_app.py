"""Main Grade Tracking Application"""

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
from education_system.systems.university.interfaces.gui.academics.grade_tracking.utils import ensure_column_exists

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
            grade_points REAL,
            completion_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Ensure grade_points column exists for legacy databases
        ensure_column_exists(cursor, 'module_grades', 'grade_points', 'REAL')

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

from education_system.systems.university.interfaces.gui.academics.grade_tracking.layout_manager import LayoutManager
from education_system.systems.university.interfaces.gui.academics.grade_tracking.student_manager import StudentManager
from education_system.systems.university.interfaces.gui.academics.grade_tracking.module_manager import ModuleManager
from education_system.systems.university.interfaces.gui.academics.grade_tracking.assessment_manager import AssessmentManager
from education_system.systems.university.interfaces.gui.academics.grade_tracking.grade_manager import GradeManager
from education_system.systems.university.interfaces.gui.academics.grade_tracking.analytics_manager import AnalyticsManager

class GradeTrackingApp:
    """Main Grade Tracking Application"""

    def __init__(self, root, auth=None):
        self.root = root
        self.auth = auth
        self.conn = None

        # Initialize managers
        self.layout = LayoutManager(self)
        self.students = StudentManager(self)
        self.modules = ModuleManager(self)
        self.assessments = AssessmentManager(self)
        self.grades = GradeManager(self)
        self.analytics = AnalyticsManager(self)
        from education_system.systems.university.interfaces.gui.academics.grade_tracking.integrations_manager import (
            GradeIntegrationsManager,
        )
        self.integrations = GradeIntegrationsManager(self)

        # Initialize database
        self.initialize_database()
        self.create_database_tables()
        self.populate_initial_data()

        # Setup UI
        self.layout.setup_ui()
        self.refresh_all_data()

        # Live refresh: when sibling GUIs add/update assessments, exams,
        # assignments, or enrolments, re-pull our data so cached lists
        # don't go stale.
        try:
            from education_system.systems.university.interfaces.gui.academics._event_bus import (
                subscribe_tk,
                EVENT_ASSESSMENT_CHANGED,
                EVENT_EXAM_CHANGED,
                EVENT_ASSIGNMENT_CHANGED,
                EVENT_ENROLMENT_CHANGED,
                EVENT_GRADE_CHANGED,
            )

            def _on_external_change(**_payload):
                if hasattr(self, "refresh_all_data"):
                    self.refresh_all_data()

            for evt in (EVENT_ASSESSMENT_CHANGED, EVENT_EXAM_CHANGED,
                        EVENT_ASSIGNMENT_CHANGED, EVENT_ENROLMENT_CHANGED,
                        EVENT_GRADE_CHANGED):
                subscribe_tk(evt, self.root, _on_external_change)

            # Term, selection, calendar, and staff availability — Grade
            # joins the same broadcast channel the four scheduling GUIs
            # already use (#9). Calendar/staff changes can move the
            # submission window or grey out a grader's queue, so a
            # refresh keeps everything coherent.
            from education_system.systems.university.interfaces.gui.academics._event_bus import (
                EVENT_TERM_CHANGED, EVENT_SELECTION_CHANGED,
                EVENT_CALENDAR_CHANGED, EVENT_STAFF_AVAILABILITY_CHANGED,
            )

            for evt in (EVENT_TERM_CHANGED, EVENT_CALENDAR_CHANGED,
                        EVENT_STAFF_AVAILABILITY_CHANGED):
                subscribe_tk(evt, self.root, _on_external_change)

            def _on_selection(**payload):
                # Soft pointer — pre-filter the module dropdown to the
                # selected module if the GUI has one. We don't navigate
                # away from whatever tab the user is on.
                target = payload.get("module_code")
                if not target:
                    return
                try:
                    if (hasattr(self, "modules") and
                            hasattr(self.modules, "filter_module_var")):
                        self.modules.filter_module_var.set(target)
                        if hasattr(self.modules, "filter_modules"):
                            self.modules.filter_modules()
                except Exception:
                    pass

            subscribe_tk(EVENT_SELECTION_CHANGED, self.root, _on_selection)
        except Exception:
            pass

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if self.auth:
                if hasattr(self.auth, 'current_user') and self.auth.current_user:
                    role = self.auth.current_user.get('role', '').lower()
                    return role
                elif hasattr(self.auth, 'user_role'):
                    return self.auth.user_role.lower()
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff/instructor/faculty"""
        role = self.get_user_role()
        return role in ['staff', 'instructor', 'faculty']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def initialize_database(self):
        """Initialize database connection"""
        try:
            # Use get_connection to follow proper architecture
            self.conn = get_connection()
            self.cursor = self.conn.cursor()
            # Enable foreign keys
            self.cursor.execute("PRAGMA foreign_keys = ON")
            self.conn.commit()
        except Exception as e:
            error_msg = f"Error initializing database: {e}"
            print(error_msg)
            messagebox.showerror("Database Error",
                               f"Failed to connect to database:\n{e}\n\nPlease check the database path and permissions.")
            # Set to None but we need to handle this in methods
            self.conn = None
            self.cursor = None

    def get_cursor(self):
        """Get a valid database cursor, creating connection if needed"""
        try:
            # First try to use existing cursor
            if self.cursor:
                return self.cursor

            # Try to recreate connection
            if not self.conn:
                self.conn = sqlite3.connect(str(DEFAULT_DB_PATH))

            self.cursor = self.conn.cursor()
            return self.cursor
        except Exception as e:
            print(f"Error getting database cursor: {e}")
            return None

    def create_database_tables(self):
        """Create all necessary database tables"""
        # Get valid cursor
        cursor = self.get_cursor()
        if not cursor:
            print("Failed to get database cursor for table creation")
            return

        # Students table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            last_name TEXT NOT NULL,
            course TEXT NOT NULL,
            email_address TEXT UNIQUE,
            phone_number TEXT,
            address TEXT,
            enrollment_date TEXT,
            status TEXT DEFAULT 'Active',
            date_of_birth TEXT,
            gender TEXT,
            nationality TEXT
        )
        ''')

        # Modules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            module_code TEXT PRIMARY KEY,
            module_name TEXT NOT NULL,
            module_type TEXT NOT NULL,
            credits INTEGER NOT NULL,
            description TEXT,
            course TEXT,
            prerequisites TEXT,
            semester TEXT,
            academic_year TEXT
        )
        ''')

        # Assessments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_name TEXT NOT NULL,
            assessment_type TEXT NOT NULL,
            module_code TEXT NOT NULL,
            max_points REAL NOT NULL,
            weight REAL NOT NULL,
            due_date TEXT,
            description TEXT,
            rubric TEXT,
            FOREIGN KEY (module_code) REFERENCES modules(module_code)
        )
        ''')

        ensure_column_exists(cursor, 'assessments', 'rubric', 'TEXT')

        # Grades table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grades (
            grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            assessment_id INTEGER NOT NULL,
            score REAL NOT NULL,
            letter_grade TEXT,
            submission_date TEXT,
            comments TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id)
        )
        ''')

        # Student modules enrollment table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            enrollment_date TEXT,
            status TEXT DEFAULT 'Enrolled',
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code)
        )
        ''')

        # Module grades table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS module_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            final_grade TEXT,
            final_score REAL,
            grade_points REAL,
            completion_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code)
        )
        ''')

        # Learning outcomes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_outcomes (
            outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
            outcome_code TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT,
            level INTEGER
        )
        ''')

        # Assessment outcomes mapping table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            outcome_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
            FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
        )
        ''')

        # Outcome results table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS outcome_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            outcome_id INTEGER NOT NULL,
            achievement_level REAL,
            assessment_date TEXT,
            evidence TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
        )
        ''')

        # Competencies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competencies (
            competency_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT
        )
        ''')

        # Competency levels table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competency_levels (
            level_id INTEGER PRIMARY KEY AUTOINCREMENT,
            competency_id INTEGER NOT NULL,
            level_name TEXT NOT NULL,
            level_value INTEGER NOT NULL,
            description TEXT,
            FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
        )
        ''')

        # Assessment competencies mapping table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_competencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            competency_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
            FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
        )
        ''')

        # Student competencies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_competencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            competency_id INTEGER NOT NULL,
            level_id INTEGER NOT NULL,
            assessment_date TEXT,
            evidence TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (competency_id) REFERENCES competencies(competency_id),
            FOREIGN KEY (level_id) REFERENCES competency_levels(level_id)
        )
        ''')

        # Risk assessment table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_risk_assessment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            risk_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            assessment_date TEXT,
            prediction_model TEXT,
            confidence REAL,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        self.conn.commit()


    def populate_initial_data(self):
        """Populate database with initial sample data if empty"""
        # Get valid cursor
        cursor = self.get_cursor()
        if not cursor:
            print("Failed to get database cursor for populating data")
            return

        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM students")
        if cursor.fetchone()[0] > 0:
            return

        # Sample students
        # Note: Sample student data insertion removed - students must be created via main GUI or CLI
        # for centralized management

        # Sample modules
        sample_modules = [
            ('CS101', 'Introduction to Programming', 'Core', 3, 'Basic programming concepts and problem-solving techniques', '', 'Fall', '2024'),
            ('CS201', 'Data Structures and Algorithms', 'Core', 4, 'Fundamental data structures and algorithmic thinking', 'CS101', 'Spring', '2024'),
            ('MATH101', 'Calculus I', 'Core', 4, 'Differential and integral calculus', '', 'Fall', '2024'),
            ('ENG101', 'Technical Writing', 'General', 2, 'Professional communication and technical documentation', '', 'Fall', '2024'),
            ('PHYS101', 'Physics I', 'Core', 4, 'Mechanics and thermodynamics', 'MATH101', 'Spring', '2024')
        ]

        cursor.executemany('''
        INSERT INTO modules (module_code, module_name, module_type, credits, description, prerequisites, semester, academic_year)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_modules)

        # Sample assessments
        sample_assessments = [
            ('Programming Assignment 1', 'Assignment', 'CS101', 100, 20, '2024-10-15', 'Basic programming exercises', ''),
            ('Midterm Exam', 'Exam', 'CS101', 150, 30, '2024-11-01', 'Comprehensive midterm examination', ''),
            ('Final Project', 'Project', 'CS101', 200, 50, '2024-12-15', 'Capstone programming project', ''),
            ('Calculus Quiz 1', 'Quiz', 'MATH101', 50, 10, '2024-10-01', 'Limits and derivatives quiz', ''),
            ('Calculus Midterm', 'Exam', 'MATH101', 100, 40, '2024-11-15', 'Midterm examination covering derivatives', ''),
            ('Essay Assignment', 'Assignment', 'ENG101', 100, 30, '2024-10-30', 'Technical writing essay', ''),
            ('Lab Report 1', 'Lab', 'PHYS101', 75, 25, '2024-09-30', 'Mechanics laboratory report', '')
        ]

        cursor.executemany('''
        INSERT INTO assessments (assessment_name, assessment_type, module_code, max_points, weight, due_date, description, rubric)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_assessments)

        # Sample enrollments and grades are intentionally not seeded here:
        # sample students are no longer created (see note above) - students must
        # be created via the main GUI or CLI for centralized management, and
        # enrollments/grades that referenced them would violate foreign keys.

        # Sample competencies
        sample_competencies = [
            ('Programming Fundamentals', 'Basic programming concepts and syntax', 'Technical'),
            ('Problem Solving', 'Analytical and critical thinking skills', 'Cognitive'),
            ('Communication', 'Written and verbal communication abilities', 'Soft Skills'),
            ('Teamwork', 'Collaboration and interpersonal skills', 'Soft Skills'),
            ('Mathematical Reasoning', 'Quantitative analysis and mathematical thinking', 'Technical')
        ]

        cursor.executemany('''
        INSERT INTO competencies (name, description, category)
        VALUES (?, ?, ?)
        ''', sample_competencies)

        # Sample competency levels
        competency_levels = [
            (1, 'Beginner', 1, 'Basic understanding and application'),
            (1, 'Intermediate', 2, 'Moderate proficiency with guidance'),
            (1, 'Advanced', 3, 'High proficiency and independence'),
            (1, 'Expert', 4, 'Mastery and ability to teach others'),
            (2, 'Novice', 1, 'Basic problem identification'),
            (2, 'Developing', 2, 'Can solve simple problems'),
            (2, 'Proficient', 3, 'Solves complex problems systematically'),
            (2, 'Advanced', 4, 'Creates innovative solutions'),
        ]

        for comp_id, level_name, level_value, description in competency_levels:
            cursor.execute('''
            INSERT INTO competency_levels (competency_id, level_name, level_value, description)
            VALUES (?, ?, ?, ?)
            ''', (comp_id, level_name, level_value, description))

        self.conn.commit()


    def refresh_all_data(self):
        """Refresh all data displays"""
        # Delegate to managers if they have refresh methods
        if hasattr(self.students, 'refresh_students'):
            self.students.refresh_students()
        if hasattr(self, 'refresh_modules'):
            self.refresh_modules()
        if hasattr(self, 'refresh_assessments'):
            self.refresh_assessments()
        if hasattr(self, 'refresh_grades'):
            self.refresh_grades()
        if hasattr(self, 'refresh_competencies'):
            self.refresh_competencies()
        if hasattr(self, 'refresh_competency_mappings'):
            self.refresh_competency_mappings()


    def populate_filter_combos(self):
        """Populate filter comboboxes with current data"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Always fetch raw values so counts reflect database state even if widgets are not yet created
            cursor.execute(
                "SELECT DISTINCT course FROM students WHERE course IS NOT NULL AND course != '' ORDER BY course"
            )
            course_results = cursor.fetchall()
            courses = ['All'] + [row[0] for row in course_results if row[0]]

            cursor.execute(
                "SELECT DISTINCT module_code FROM modules WHERE module_code IS NOT NULL AND module_code != '' ORDER BY module_code"
            )
            module_results = cursor.fetchall()
            modules = ['All'] + [row[0] for row in module_results if row[0]]

            cursor.execute(
                """
                SELECT student_id, first_name || ' ' || last_name AS full_name
                FROM students
                WHERE student_id IS NOT NULL AND first_name IS NOT NULL AND last_name IS NOT NULL
                ORDER BY last_name, first_name
                """
            )
            students_data = cursor.fetchall()
            students = ['All'] + [f"{row[0]} - {row[1]}" for row in students_data if row[0] and row[1]]

            cursor.execute(
                """
                SELECT assessment_id, assessment_name || ' (' || module_code || ')' AS full_name
                FROM assessments
                WHERE assessment_id IS NOT NULL AND assessment_name IS NOT NULL AND module_code IS NOT NULL
                ORDER BY assessment_name
                """
            )
            assessments_data = cursor.fetchall()
            assessments = ['All'] + [f"{row[0]} - {row[1]}" for row in assessments_data if row[0] and row[1]]

            # Cache for later use when widgets are created asynchronously
            self._filter_cache = {
                'courses': courses,
                'modules': modules,
                'students': students,
                'assessments': assessments,
            }

            if self._widget_exists(getattr(self, 'course_filter_combo', None)):
                self.course_filter_combo['values'] = courses
                self.course_filter_var.set('All')

            if self._widget_exists(getattr(self, 'assessment_module_combo', None)):
                self.assessment_module_combo['values'] = modules
                self.assessment_module_filter_var.set('All')

            if self._widget_exists(getattr(self, 'grade_student_combo', None)):
                self.grade_student_combo['values'] = students
                self.grade_student_filter_var.set('All')

            if self._widget_exists(getattr(self, 'grade_assessment_combo', None)):
                self.grade_assessment_combo['values'] = assessments
                self.grade_assessment_filter_var.set('All')

            if self._widget_exists(getattr(self, 'comp_student_combo', None)):
                self.comp_student_combo['values'] = students
                self.comp_student_filter_var.set('All')

            course_count = max(len(courses) - 1, 0)
            module_count = max(len(modules) - 1, 0)
            student_count = max(len(students) - 1, 0)
            assessment_count = max(len(assessments) - 1, 0)
            print(
                "Filter combos populated: "
                f"{course_count} courses, {module_count} modules, {student_count} students, {assessment_count} assessments"
            )

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error populating filter combos: {e}")
            # Set default values to prevent blank dropdowns
            self._set_default_combo_values()

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error populating filter combos: {e}")
            # Set default values to prevent blank dropdowns
            self._set_default_combo_values()

        finally:
            if conn:
                conn.close()


    def _set_default_combo_values(self):
        """Set default values for combos when data loading fails"""
        try:
            default_values = ['All', 'No Data Available']

            if self._widget_exists(getattr(self, 'course_filter_combo', None)):
                self.course_filter_combo['values'] = default_values
                self.course_filter_var.set('All')

            if self._widget_exists(getattr(self, 'assessment_module_combo', None)):
                self.assessment_module_combo['values'] = default_values
                self.assessment_module_filter_var.set('All')

            if self._widget_exists(getattr(self, 'grade_student_combo', None)):
                self.grade_student_combo['values'] = default_values
                self.grade_student_filter_var.set('All')

            if self._widget_exists(getattr(self, 'grade_assessment_combo', None)):
                self.grade_assessment_combo['values'] = default_values
                self.grade_assessment_filter_var.set('All')

            if self._widget_exists(getattr(self, 'comp_student_combo', None)):
                self.comp_student_combo['values'] = default_values
                self.comp_student_filter_var.set('All')

        except Exception as e:
            print(f"Error setting default combo values: {e}")


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


    def return_to_main_menu(self):
        """Return to main menu"""
        return self.layout.return_to_main_menu()
