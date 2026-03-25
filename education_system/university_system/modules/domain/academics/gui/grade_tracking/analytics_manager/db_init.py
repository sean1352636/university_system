"""Database initialization for analytics manager."""

from tkinter import messagebox

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.academics.gui.grade_tracking.utils import ensure_column_exists
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.constants import get_connection


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
