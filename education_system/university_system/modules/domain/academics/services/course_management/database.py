from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.core.sql_safety import validate_table_name, validate_identifier


def initialize_enhanced_database():
    """Initialize all database tables for the enhanced course management system"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Enhanced courses table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT UNIQUE NOT NULL,
            course_name TEXT NOT NULL,
            description TEXT,
            duration INTEGER,
            level TEXT,
            department TEXT,
            credit_hours REAL DEFAULT 3.0,
            contact_hours_per_week INTEGER DEFAULT 3,
            learning_outcomes TEXT,
            assessment_methods TEXT,
            required_textbooks TEXT,
            course_fee REAL DEFAULT 0.0,
            lab_required BOOLEAN DEFAULT 0,
            online_available BOOLEAN DEFAULT 0,
            max_enrollment INTEGER DEFAULT 30,
            current_enrollment INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            course_type TEXT DEFAULT 'Core',
            tags TEXT,
            availability_periods TEXT DEFAULT 'Fall,Spring',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')

        # Course prerequisites table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_prerequisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            prerequisite_course_id INTEGER NOT NULL,
            is_required BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id),
            FOREIGN KEY (prerequisite_course_id) REFERENCES courses (id),
            UNIQUE(course_id, prerequisite_course_id)
        )
        ''')

        # Course schedule table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            semester TEXT NOT NULL,
            year INTEGER NOT NULL,
            start_time TEXT,
            end_time TEXT,
            days_of_week TEXT,
            classroom TEXT,
            instructor_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id),
            UNIQUE(course_id, semester, year)
        )
        ''')

        # Instructors table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            department TEXT,
            specialization TEXT,
            max_courses_per_semester INTEGER DEFAULT 4,
            status TEXT DEFAULT 'Active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')

        # Course history table for versioning
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_by TEXT,
            changed_at TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        )
        ''')

        # Course waitlist table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            added_at TEXT NOT NULL,
            status TEXT DEFAULT 'Waiting',
            FOREIGN KEY (course_id) REFERENCES courses (id),
            UNIQUE(course_id, student_id)
        )
        ''')

        # Course categories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            color_code TEXT,
            created_at TEXT NOT NULL
        )
        ''')

        # Course analytics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            semester TEXT NOT NULL,
            year INTEGER NOT NULL,
            total_enrolled INTEGER DEFAULT 0,
            total_completed INTEGER DEFAULT 0,
            average_grade REAL DEFAULT 0.0,
            completion_rate REAL DEFAULT 0.0,
            calculated_at TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        )
        ''')

        conn.commit()

        # Add missing columns to existing tables (migration for older databases)
        migration_columns = [
            ("courses", "duration", "INTEGER"),
            ("courses", "course_type", "TEXT DEFAULT 'Core'"),
            ("courses", "updated_at", "TEXT"),
            ("courses", "created_at", "TEXT"),
            ("courses", "tags", "TEXT"),
            ("courses", "availability_periods", "TEXT DEFAULT 'Fall,Spring'"),
            ("courses", "learning_outcomes", "TEXT"),
            ("courses", "assessment_methods", "TEXT"),
            ("courses", "required_textbooks", "TEXT"),
            ("courses", "course_fee", "REAL DEFAULT 0.0"),
            ("courses", "lab_required", "BOOLEAN DEFAULT 0"),
            ("courses", "online_available", "BOOLEAN DEFAULT 0"),
            ("courses", "contact_hours_per_week", "INTEGER DEFAULT 3"),
            ("instructors", "updated_at", "TEXT"),
        ]

        for table, column, col_type in migration_columns:
            try:
                safe_table = validate_table_name(table)
                safe_column = validate_identifier(column, "column")
                cursor.execute("ALTER TABLE [" + safe_table + "] ADD COLUMN [" + safe_column + "] " + col_type)
            except sqlite3.OperationalError:
                pass  # Column already exists

        conn.commit()
        conn.close()
        print("Enhanced database schema initialized successfully!")
        return True

    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
        if 'conn' in locals():
            conn.close()
        return False
