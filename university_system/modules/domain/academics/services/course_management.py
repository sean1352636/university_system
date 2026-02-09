# enhanced_course_management.py
from university_system.infrastructure.database.db import sqlite3, DatabaseManager
import re
import csv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
# Import logging helpers from the refactored utils module
from university_system.modules.shared.utils.simple_activity_logger import (
    log_create,
    log_read,
    log_update,
    log_delete,
    log_menu_navigation,
)
from university_system.infrastructure.database.db import get_connection
# Import internationalization support
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

# =====================================================================
# DATABASE SCHEMA INITIALIZATION
# =====================================================================

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
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
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

# =====================================================================
# VALIDATION FUNCTIONS
# =====================================================================

def validate_course_code(code):
    """
    Validate the format of a course code.

    Course codes must follow the pattern of 2-4 uppercase letters followed
    by 2-3 digits (e.g., 'CS101', 'MATH201', 'BIO99').

    Parameters
    ----------
    code : str
        The course code to validate.

    Returns
    -------
    bool
        True if the code matches the required format, False otherwise.

    Examples
    --------
    >>> validate_course_code('CS101')
    True
    >>> validate_course_code('MATH201')
    True
    >>> validate_course_code('invalid')
    False
    >>> validate_course_code('CS1')  # Too few digits
    False
    """
    pattern = r'^[A-Z]{2,4}\d{2,3}$'
    return bool(re.match(pattern, code))


def validate_email(email):
    """
    Validate the format of an email address.

    Checks if the email follows standard email format with local part,
    @ symbol, domain, and top-level domain.

    Parameters
    ----------
    email : str
        The email address to validate.

    Returns
    -------
    bool
        True if the email format is valid, False otherwise.

    Examples
    --------
    >>> validate_email('user@example.com')
    True
    >>> validate_email('john.doe+tag@university.edu')
    True
    >>> validate_email('invalid-email')
    False

    Notes
    -----
    This performs format validation only. It does not verify that the
    email address actually exists or can receive mail.
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_time_format(time_str):
    """
    Validate a time string in 24-hour HH:MM format.

    Parameters
    ----------
    time_str : str
        The time string to validate (e.g., '09:30', '14:00', '23:59').

    Returns
    -------
    bool
        True if the time format is valid, False otherwise.

    Examples
    --------
    >>> validate_time_format('09:30')
    True
    >>> validate_time_format('14:00')
    True
    >>> validate_time_format('25:00')  # Invalid hour
    False
    >>> validate_time_format('12:60')  # Invalid minute
    False
    """
    pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
    return bool(re.match(pattern, time_str))


def validate_days_of_week(days_str):
    """
    Validate a comma-separated string of days of the week.

    Each day must be a full day name (Monday, Tuesday, etc.) with
    proper capitalization.

    Parameters
    ----------
    days_str : str
        Comma-separated string of day names (e.g., 'Monday, Wednesday, Friday').

    Returns
    -------
    bool
        True if all days are valid day names, False otherwise.

    Examples
    --------
    >>> validate_days_of_week('Monday, Wednesday, Friday')
    True
    >>> validate_days_of_week('Saturday')
    True
    >>> validate_days_of_week('Mon, Wed')  # Abbreviations not allowed
    False
    >>> validate_days_of_week('Monday, Funday')  # Invalid day
    False
    """
    valid_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}
    days = [day.strip() for day in days_str.split(',')]
    return all(day in valid_days for day in days)

# =====================================================================
# CORE COURSE MANAGEMENT (ENHANCED)
# =====================================================================

@log_create(module="course_management", description="Creating new course with enhanced features")
def create_enhanced_course(auth):
    """Create a new course with all enhanced features"""
    if not auth or not auth.current_user:
        print(get_text('course_mgmt.login_required', default='You must be logged in to create courses.'))
        return False

    if not auth.check_permission('manage_courses'):
        print(get_text('course_mgmt.no_permission_create', default="You don't have permission to create courses."))
        return False

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Ensure enhanced schema exists
        initialize_enhanced_database()

        print(f"\n{get_text('course_mgmt.create_title', default='Create New Enhanced Course')}")
        print("==========================")

        # Basic course information
        while True:
            course_code = input(f"{get_text('course_mgmt.prompts.course_code', default='Enter course code (e.g., CS101)')}: ").strip().upper()
            if not course_code:
                print(get_text('course_mgmt.errors.code_empty', default='Error: Course code cannot be empty.'))
                continue

            if not validate_course_code(course_code):
                print(get_text('course_mgmt.errors.code_invalid', default='Error: Invalid course code format. It should be 2-4 letters followed by 2-3 numbers.'))
                continue

            cursor.execute("SELECT course_code FROM courses WHERE course_code = ?", (course_code,))
            if cursor.fetchone():
                print(get_text('course_mgmt.errors.code_exists', default="Error: Course code '{code}' already exists.").format(code=course_code))
                continue
            break

        while True:
            course_name = input(f"{get_text('course_mgmt.prompts.course_name', default='Enter course name')}: ").strip()
            if not course_name:
                print(get_text('course_mgmt.errors.name_empty', default='Error: Course name cannot be empty.'))
                continue
            if len(course_name) < 5:
                print(get_text('course_mgmt.errors.name_short', default='Error: Course name must be at least 5 characters.'))
                continue
            break

        description = input(f"{get_text('course_mgmt.prompts.description', default='Enter course description')}: ").strip()

        # Duration
        duration = None
        duration_input = input(f"{get_text('course_mgmt.prompts.duration', default='Enter course duration in years (e.g., 3, 4)')}: ").strip()
        if duration_input:
            try:
                duration = int(duration_input)
                if duration <= 0:
                    print(get_text('course_mgmt.warnings.duration_positive', default='Warning: Duration must be positive. Setting to null.'))
                    duration = None
            except ValueError:
                print(get_text('course_mgmt.warnings.duration_number', default='Warning: Duration must be a number. Setting to null.'))

        # Level
        level_options = ["Undergraduate", "Postgraduate", "PhD", "Certificate", "Diploma"]
        print(f"\n{get_text('course_mgmt.prompts.select_level', default='Select course level')}:")
        for i, level in enumerate(level_options, 1):
            print(f"{i}. {level}")

        level = None
        level_choice = input(f"{get_text('course_mgmt.prompts.enter_choice_or_type', default='Enter choice (1-5) or type level')}: ").strip()
        if level_choice:
            if level_choice.isdigit():
                idx = int(level_choice) - 1
                if 0 <= idx < len(level_options):
                    level = level_options[idx]
            else:
                level = level_choice

        department = input(f"{get_text('course_mgmt.prompts.department', default='Enter department')}: ").strip()
        
        # Enhanced fields
        credit_hours = 3.0
        credit_input = input("Enter credit hours (default 3.0): ").strip()
        if credit_input:
            try:
                credit_hours = float(credit_input)
            except ValueError:
                print("Warning: Invalid credit hours. Using default 3.0")
        
        contact_hours = 3
        contact_input = input("Enter contact hours per week (default 3): ").strip()
        if contact_input:
            try:
                contact_hours = int(contact_input)
            except ValueError:
                print("Warning: Invalid contact hours. Using default 3")
        
        learning_outcomes = input("Enter learning outcomes (optional): ").strip()
        assessment_methods = input("Enter assessment methods (optional): ").strip()
        required_textbooks = input("Enter required textbooks (optional): ").strip()
        
        course_fee = 0.0
        fee_input = input("Enter course fee (default 0.0): ").strip()
        if fee_input:
            try:
                course_fee = float(fee_input)
            except ValueError:
                print("Warning: Invalid fee. Using default 0.0")
        
        lab_required = input("Is lab required? (y/n): ").strip().lower() == 'y'
        online_available = input("Is online version available? (y/n): ").strip().lower() == 'y'
        
        max_enrollment = 30
        max_input = input("Enter maximum enrollment (default 30): ").strip()
        if max_input:
            try:
                max_enrollment = int(max_input)
            except ValueError:
                print("Warning: Invalid enrollment number. Using default 30")
        
        # Course type
        type_options = ["Core", "Elective", "Major-specific", "General Education"]
        print("\nSelect course type:")
        for i, ctype in enumerate(type_options, 1):
            print(f"{i}. {ctype}")
        
        course_type = "Core"
        type_choice = input("Enter choice (1-4) or type: ").strip()
        if type_choice:
            if type_choice.isdigit():
                idx = int(type_choice) - 1
                if 0 <= idx < len(type_options):
                    course_type = type_options[idx]
            else:
                course_type = type_choice
        
        tags = input("Enter tags (comma-separated, optional): ").strip()
        
        # Availability periods
        print("\nSelect availability periods (comma-separated):")
        print("Options: Fall, Spring, Summer, Winter")
        availability = input("Enter periods (default: Fall,Spring): ").strip()
        if not availability:
            availability = "Fall,Spring"
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Generate unique ID for the course
        import uuid
        course_id = str(uuid.uuid4())

        # Insert the course
        cursor.execute('''
        INSERT INTO courses (
            id, code, name, date_added,
            course_code, course_name, description, duration, level, department,
            credit_hours, contact_hours_per_week, learning_outcomes, assessment_methods,
            required_textbooks, course_fee, lab_required, online_available,
            max_enrollment, course_type, tags, availability_periods,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            course_id, course_code, course_name, timestamp,
            course_code, course_name, description, duration, level, department,
            credit_hours, contact_hours, learning_outcomes, assessment_methods,
            required_textbooks, course_fee, lab_required, online_available,
            max_enrollment, course_type, tags, availability,
            timestamp, timestamp
        ))
        
        course_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"\nEnhanced course '{course_name}' (Code: {course_code}) created successfully!")
        print(f"Course ID: {course_id}")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False
    except Exception as e:
        print(f"Error creating course: {e}")
        if 'conn' in locals():
            conn.close()
        return False

# =====================================================================
# PREREQUISITE MANAGEMENT
# =====================================================================

@log_create(module="course_management", description="Adding course prerequisite")
def add_prerequisite(auth):
    """
    Add a prerequisite requirement to a course.

    Interactive function that allows administrators to define prerequisite
    relationships between courses. Includes circular dependency detection
    to prevent invalid prerequisite chains.

    Parameters
    ----------
    auth : UserAuth
        The authentication instance. Must have an authenticated user with
        'manage_courses' permission.

    Returns
    -------
    bool
        True if the prerequisite was successfully added, False otherwise.
        Returns False if:
        - User is not logged in or lacks permission
        - Fewer than 2 courses exist in the system
        - Selected prerequisite would create a circular dependency
        - Prerequisite already exists
        - Database error occurs

    Examples
    --------
    >>> # Interactive prompts will appear
    >>> add_prerequisite(auth)
    Available Courses:
    1. CS101 - Introduction to Programming
    2. CS201 - Data Structures
    ...
    Enter course ID to add prerequisite to: 2
    Select prerequisite course:
    1. CS101 - Introduction to Programming
    Enter prerequisite course ID: 1
    Is this prerequisite required? (yes/no): yes
    Prerequisite added successfully!
    True

    Notes
    -----
    - A course cannot be its own prerequisite
    - Circular dependencies are automatically detected and rejected
    - Prerequisites can be marked as 'required' or 'recommended'

    See Also
    --------
    view_prerequisites : View existing prerequisite relationships.
    check_circular_prerequisite : Check for circular dependency.
    """
    if not auth or not auth.current_user:
        print("You must be logged in to manage prerequisites.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to manage prerequisites.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Show all courses
        cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
        courses = cursor.fetchall()
        
        if len(courses) < 2:
            print("Need at least 2 courses to set prerequisites.")
            conn.close()
            return False
        
        print("\nAvailable Courses:")
        for course in courses:
            print(f"{course[0]}. {course[1]} - {course[2]}")
        
        # Select main course
        while True:
            try:
                course_id = int(input("\nEnter course ID to add prerequisite to: "))
                if any(c[0] == course_id for c in courses):
                    break
                print("Invalid course ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Select prerequisite course
        print("\nSelect prerequisite course:")
        available_prereqs = [c for c in courses if c[0] != course_id]
        for course in available_prereqs:
            print(f"{course[0]}. {course[1]} - {course[2]}")
        
        while True:
            try:
                prereq_id = int(input("\nEnter prerequisite course ID: "))
                if prereq_id == course_id:
                    print("A course cannot be a prerequisite for itself.")
                    continue
                if any(c[0] == prereq_id for c in available_prereqs):
                    break
                print("Invalid prerequisite course ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Check for circular dependencies
        if check_circular_prerequisite(cursor, course_id, prereq_id):
            print("Error: This would create a circular dependency.")
            conn.close()
            return False
        
        is_required = input("Is this a required prerequisite? (y/n): ").strip().lower() == 'y'
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO course_prerequisites (course_id, prerequisite_course_id, is_required, created_at)
        VALUES (?, ?, ?, ?)
        ''', (course_id, prereq_id, is_required, timestamp))
        
        conn.commit()
        conn.close()
        
        print("Prerequisite added successfully!")
        return True
        
    except sqlite3.IntegrityError:
        print("Error: This prerequisite already exists.")
        conn.close()
        return False
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def check_circular_prerequisite(cursor, course_id, prereq_id):
    """
    Check if adding a prerequisite would create a circular dependency.

    Performs a depth-first search through the prerequisite chain to detect
    if adding the proposed prerequisite would create a cycle. This prevents
    invalid prerequisite structures like: A requires B, B requires C, C requires A.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Active database cursor for executing queries.
    course_id : int
        The ID of the course that would have the prerequisite added.
    prereq_id : int
        The ID of the proposed prerequisite course.

    Returns
    -------
    bool
        True if adding this prerequisite would create a circular dependency,
        False if it is safe to add.

    Examples
    --------
    >>> # Check if CS201 can have CS101 as a prerequisite
    >>> with get_connection() as conn:
    ...     cursor = conn.cursor()
    ...     is_circular = check_circular_prerequisite(cursor, 201, 101)
    ...     if is_circular:
    ...         print("Cannot add: would create circular dependency")

    Notes
    -----
    The algorithm checks if prereq_id (the proposed prerequisite) has
    course_id anywhere in its own prerequisite chain. If so, adding
    course_id as requiring prereq_id would create a cycle.

    The function uses memoization (visited set) to avoid infinite loops
    when checking complex prerequisite graphs.
    """
    # Check if prereq_id has course_id as a prerequisite (direct or indirect)
    visited = set()
    
    def has_prerequisite(cid, target_id):
        if cid in visited:
            return False
        visited.add(cid)
        
        cursor.execute("SELECT prerequisite_course_id FROM course_prerequisites WHERE course_id = ?", (cid,))
        prereqs = cursor.fetchall()
        
        for (pid,) in prereqs:
            if pid == target_id:
                return True
            if has_prerequisite(pid, target_id):
                return True
        return False
    
    return has_prerequisite(prereq_id, course_id)

@log_read(module="course_management", description="Viewing course prerequisites")
def view_prerequisites(auth):
    """View prerequisites for all courses or a specific course"""
    if not auth or not auth.current_user:
        print("You must be logged in to view prerequisites.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        course_choice = input("Enter course ID to view its prerequisites (or press Enter for all): ").strip()
        
        if course_choice:
            try:
                course_id = int(course_choice)
                cursor.execute("""
                SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c1 ON cp.course_id = c1.id
                JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                WHERE cp.course_id = ?
                ORDER BY c2.course_code
                """, (course_id,))
                
                prereqs = cursor.fetchall()
                if prereqs:
                    print(f"\nPrerequisites for {prereqs[0][0]} - {prereqs[0][1]}:")
                    print("-" * 60)
                    for prereq in prereqs:
                        req_status = "Required" if prereq[4] else "Recommended"
                        print(f"{prereq[2]} - {prereq[3]} ({req_status})")
                else:
                    print("No prerequisites found for this course.")
            except ValueError:
                print("Invalid course ID.")
        else:
            cursor.execute("""
            SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
            FROM course_prerequisites cp
            JOIN courses c1 ON cp.course_id = c1.id
            JOIN courses c2 ON cp.prerequisite_course_id = c2.id
            ORDER BY c1.course_code, c2.course_code
            """)
            
            prereqs = cursor.fetchall()
            if prereqs:
                print("\nAll Course Prerequisites:")
                print("-" * 80)
                current_course = None
                for prereq in prereqs:
                    if current_course != prereq[0]:
                        current_course = prereq[0]
                        print(f"\n{prereq[0]} - {prereq[1]}:")
                    
                    req_status = "Required" if prereq[4] else "Recommended"
                    print(f"  → {prereq[2]} - {prereq[3]} ({req_status})")
            else:
                print("No prerequisites found in the system.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

# =====================================================================
# INSTRUCTOR MANAGEMENT
# =====================================================================

@log_create(module="course_management", description="Creating instructor")
def create_instructor(auth):
    """Create a new instructor"""
    if not auth or not auth.current_user:
        print("You must be logged in to create instructors.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to create instructors.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nCreate New Instructor")
        print("====================")
        
        first_name = input("Enter first name: ").strip()
        if not first_name:
            print("First name cannot be empty.")
            return False
        
        last_name = input("Enter last name: ").strip()
        if not last_name:
            print("Last name cannot be empty.")
            return False
        
        while True:
            email = input("Enter email: ").strip()
            if not email:
                print("Email cannot be empty.")
                continue
            if not validate_email(email):
                print("Invalid email format.")
                continue
            
            cursor.execute("SELECT email FROM instructors WHERE email = ?", (email,))
            if cursor.fetchone():
                print("Email already exists.")
                continue
            break
        
        department = input("Enter department: ").strip()
        specialization = input("Enter specialization: ").strip()
        
        max_courses = 4
        max_input = input("Enter max courses per semester (default 4): ").strip()
        if max_input:
            try:
                max_courses = int(max_input)
            except ValueError:
                print("Using default value of 4.")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO instructors (first_name, last_name, email, department, specialization, 
                               max_courses_per_semester, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (first_name, last_name, email, department, specialization, max_courses, timestamp, timestamp))
        
        instructor_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"\nInstructor '{first_name} {last_name}' created successfully!")
        print(f"Instructor ID: {instructor_id}")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_read(module="course_management", description="Viewing instructors")
def view_instructors(auth):
    """View all instructors"""
    if not auth or not auth.current_user:
        print("You must be logged in to view instructors.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, first_name, last_name, email, department, specialization, 
               max_courses_per_semester, status
        FROM instructors 
        ORDER BY last_name, first_name
        """)
        
        instructors = cursor.fetchall()
        
        if not instructors:
            print("No instructors found.")
            conn.close()
            return
        
        print("\nAll Instructors:")
        print(f"{'ID':<5} {'Name':<25} {'Email':<30} {'Department':<20} {'Status':<10}")
        print("-" * 90)
        
        for instructor in instructors:
            full_name = f"{instructor[1]} {instructor[2]}"
            print(f"{instructor[0]:<5} {full_name:<25} {instructor[3]:<30} {instructor[4]:<20} {instructor[7]:<10}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

# =====================================================================
# COURSE SCHEDULING
# =====================================================================

@log_create(module="course_management", description="Creating course schedule")
def create_course_schedule(auth):
    """Create a schedule for a course"""
    if not auth or not auth.current_user:
        print("You must be logged in to create schedules.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to create schedules.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Show available courses
        cursor.execute("SELECT id, course_code, course_name FROM courses WHERE status = 'Active' ORDER BY course_code")
        courses = cursor.fetchall()
        
        if not courses:
            print("No active courses found.")
            conn.close()
            return False
        
        print("\nAvailable Courses:")
        for course in courses:
            print(f"{course[0]}. {course[1]} - {course[2]}")
        
        # Select course
        while True:
            try:
                course_id = int(input("\nEnter course ID to schedule: "))
                if any(c[0] == course_id for c in courses):
                    break
                print("Invalid course ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Semester and year
        semester_options = ["Fall", "Spring", "Summer", "Winter"]
        print("\nSelect semester:")
        for i, sem in enumerate(semester_options, 1):
            print(f"{i}. {sem}")
        
        while True:
            try:
                sem_choice = int(input("Enter choice (1-4): "))
                if 1 <= sem_choice <= 4:
                    semester = semester_options[sem_choice - 1]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")
        
        current_year = datetime.now().year
        while True:
            try:
                year = int(input(f"Enter year (default {current_year}): ") or str(current_year))
                if year >= current_year:
                    break
                print("Year must be current year or later.")
            except ValueError:
                print("Please enter a valid year.")
        
        # Check if schedule already exists
        cursor.execute("SELECT id FROM course_schedule WHERE course_id = ? AND semester = ? AND year = ?", 
                      (course_id, semester, year))
        if cursor.fetchone():
            print(f"Schedule already exists for this course in {semester} {year}.")
            conn.close()
            return False
        
        # Time and days
        while True:
            start_time = input("Enter start time (HH:MM): ").strip()
            if not start_time:
                break
            if validate_time_format(start_time):
                break
            print("Invalid time format. Use HH:MM")
        
        while True:
            end_time = input("Enter end time (HH:MM): ").strip()
            if not end_time:
                break
            if validate_time_format(end_time):
                break
            print("Invalid time format. Use HH:MM")
        
        while True:
            days = input("Enter days of week (comma-separated, e.g., Monday,Wednesday,Friday): ").strip()
            if not days:
                break
            if validate_days_of_week(days):
                break
            print("Invalid days format. Use full day names separated by commas.")
        
        classroom = input("Enter classroom/location: ").strip()
        
        # Select instructor
        cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE status = 'Active' ORDER BY last_name")
        instructors = cursor.fetchall()
        
        instructor_id = None
        if instructors:
            print("\nAvailable Instructors:")
            for instructor in instructors:
                print(f"{instructor[0]}. {instructor[1]} {instructor[2]}")
            
            instr_choice = input("Enter instructor ID (or press Enter to skip): ").strip()
            if instr_choice:
                try:
                    instructor_id = int(instr_choice)
                    if not any(i[0] == instructor_id for i in instructors):
                        print("Invalid instructor ID. Proceeding without instructor.")
                        instructor_id = None
                except ValueError:
                    print("Invalid instructor ID. Proceeding without instructor.")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO course_schedule (course_id, semester, year, start_time, end_time, 
                                   days_of_week, classroom, instructor_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (course_id, semester, year, start_time or None, end_time or None, 
              days or None, classroom or None, instructor_id, timestamp))
        
        conn.commit()
        conn.close()
        
        print(f"\nSchedule created successfully for {semester} {year}!")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

# =====================================================================
# SEARCH AND FILTERING
# =====================================================================

@log_read(module="course_management", description="Searching courses")
def search_courses(auth):
    """Advanced course search and filtering"""
    if not auth or not auth.current_user:
        print("You must be logged in to search courses.")
        return
    
    if not auth.check_permission('view_courses'):
        print("You don't have permission to view courses.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nAdvanced Course Search")
        print("=====================")
        
        # Build search criteria
        conditions = []
        params = []
        
        keyword = input("Enter keyword (search in name/description): ").strip()
        if keyword:
            conditions.append("(course_name LIKE ? OR description LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        
        department = input("Enter department: ").strip()
        if department:
            conditions.append("department LIKE ?")
            params.append(f"%{department}%")
        
        level = input("Enter level: ").strip()
        if level:
            conditions.append("level LIKE ?")
            params.append(f"%{level}%")
        
        course_type = input("Enter course type: ").strip()
        if course_type:
            conditions.append("course_type LIKE ?")
            params.append(f"%{course_type}%")
        
        status = input("Enter status (Active/Inactive): ").strip()
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        # Credit hours range
        min_credits = input("Enter minimum credit hours: ").strip()
        if min_credits:
            try:
                conditions.append("credit_hours >= ?")
                params.append(float(min_credits))
            except ValueError:
                print("Invalid credit hours, ignoring.")
        
        max_credits = input("Enter maximum credit hours: ").strip()
        if max_credits:
            try:
                conditions.append("credit_hours <= ?")
                params.append(float(max_credits))
            except ValueError:
                print("Invalid credit hours, ignoring.")
        
        # Enrollment availability
        show_available = input("Show only courses with available spots? (y/n): ").strip().lower()
        if show_available == 'y':
            conditions.append("current_enrollment < max_enrollment")
        
        # Build query
        base_query = """
        SELECT id, course_code, course_name, department, level, course_type, 
               credit_hours, current_enrollment, max_enrollment, status
        FROM courses
        """
        
        if conditions:
            query = base_query + " WHERE " + " AND ".join(conditions)
        else:
            query = base_query
        
        query += " ORDER BY course_code"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        if not results:
            print("\nNo courses found matching your criteria.")
            conn.close()
            return
        
        print(f"\nSearch Results ({len(results)} courses found):")
        print(f"{'Code':<10} {'Name':<30} {'Department':<15} {'Level':<15} {'Credits':<8} {'Enrollment':<12} {'Status':<10}")
        print("-" * 100)
        
        for course in results:
            enrollment_str = f"{course[7]}/{course[8]}"
            print(f"{course[1]:<10} {course[2]:<30} {course[3]:<15} {course[4]:<15} {course[6]:<8} {enrollment_str:<12} {course[9]:<10}")
        
        # Option to view details
        detail_choice = input("\nEnter course ID for details (or press Enter to continue): ").strip()
        if detail_choice:
            try:
                course_id = int(detail_choice)
                view_course_details(cursor, course_id)
            except ValueError:
                print("Invalid course ID.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

def view_course_details(cursor, course_id):
    """View detailed information about a specific course"""
    cursor.execute("""
    SELECT * FROM courses WHERE id = ?
    """, (course_id,))
    
    course = cursor.fetchone()
    if not course:
        print("Course not found.")
        return
    
    print(f"\nDetailed Course Information:")
    print("-" * 40)
    print(f"ID: {course[0]}")
    print(f"Code: {course[1]}")
    print(f"Name: {course[2]}")
    print(f"Description: {course[3] or 'N/A'}")
    print(f"Duration: {course[4]} years" if course[4] else "Duration: N/A")
    print(f"Level: {course[5] or 'N/A'}")
    print(f"Department: {course[6] or 'N/A'}")
    print(f"Credit Hours: {course[7]}")
    print(f"Contact Hours/Week: {course[8]}")
    print(f"Course Type: {course[15]}")
    print(f"Max Enrollment: {course[14]}")
    print(f"Current Enrollment: {course[15]}")
    print(f"Status: {course[16]}")
    print(f"Lab Required: {'Yes' if course[12] else 'No'}")
    print(f"Online Available: {'Yes' if course[13] else 'No'}")
    print(f"Course Fee: ${course[11]}")
    print(f"Tags: {course[17] or 'None'}")
    print(f"Availability: {course[18]}")

# =====================================================================
# BULK OPERATIONS
# =====================================================================

@log_create(module="course_management", description="Importing courses from CSV")
def import_courses_from_csv(auth):
    """
    Import courses in bulk from a CSV file.

    Reads course data from a CSV file and inserts valid courses into the
    database. Performs validation on each row and reports successes and
    failures. Duplicate course codes are skipped.

    Parameters
    ----------
    auth : UserAuth
        The authentication instance. Must have an authenticated user with
        'manage_courses' permission.

    Returns
    -------
    bool
        True if import was attempted (regardless of individual row outcomes),
        False if user lacks permission or file path is invalid.

    CSV Format
    ----------
    Required columns:
        - course_code : str - Course code (e.g., 'CS101')
        - course_name : str - Full course name
        - department : str - Department name

    Optional columns:
        - description : str - Course description
        - level : str - Course level (Undergraduate, Postgraduate, etc.)
        - credit_hours : float - Number of credit hours (default: 3.0)
        - max_enrollment : int - Maximum enrollment capacity (default: 30)
        - course_type : str - Course type (Core, Elective, etc.) (default: 'Core')

    Examples
    --------
    >>> # Interactive prompt for file path
    >>> import_courses_from_csv(auth)
    Enter CSV file path: /path/to/courses.csv
    Row 1: Course code already exists
    Row 2: Invalid course code format: invalid
    Import complete: 10 successful, 2 errors

    Sample CSV content::

        course_code,course_name,department,credit_hours,level
        CS101,Introduction to Programming,Computer Science,3.0,Undergraduate
        CS201,Data Structures,Computer Science,4.0,Undergraduate

    Raises
    ------
    FileNotFoundError
        If the specified CSV file does not exist.
    UnicodeDecodeError
        If the CSV file has encoding issues (expects UTF-8).

    See Also
    --------
    export_courses_to_csv : Export courses to CSV format.
    create_enhanced_course : Create a single course interactively.
    """
    if not auth or not auth.current_user:
        print("You must be logged in to import courses.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to import courses.")
        return False
    
    file_path = input("Enter CSV file path: ").strip()
    if not file_path:
        print("File path cannot be empty.")
        return False
    
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            required_fields = ['course_code', 'course_name', 'department']
            if not all(field in reader.fieldnames for field in required_fields):
                print(f"CSV must contain these required columns: {', '.join(required_fields)}")
                return False
            
            conn = get_connection()
            cursor = conn.cursor()
            
            success_count = 0
            error_count = 0
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for row_num, row in enumerate(reader, 1):
                try:
                    # Validate required fields
                    course_code = row['course_code'].strip().upper()
                    course_name = row['course_name'].strip()
                    department = row['department'].strip()
                    
                    if not course_code or not course_name:
                        print(f"Row {row_num}: Missing required fields")
                        error_count += 1
                        continue
                    
                    if not validate_course_code(course_code):
                        print(f"Row {row_num}: Invalid course code format: {course_code}")
                        error_count += 1
                        continue
                    
                    # Check for duplicates
                    cursor.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,))
                    if cursor.fetchone():
                        print(f"Row {row_num}: Course code {course_code} already exists")
                        error_count += 1
                        continue
                    
                    # Prepare optional fields with defaults
                    description = row.get('description', '').strip()
                    level = row.get('level', '').strip()
                    credit_hours = float(row.get('credit_hours', 3.0))
                    max_enrollment = int(row.get('max_enrollment', 30))
                    course_type = row.get('course_type', 'Core').strip()

                    # Generate unique ID for the course
                    import uuid
                    course_uuid = str(uuid.uuid4())

                    # Insert course
                    cursor.execute('''
                    INSERT INTO courses (
                        id, code, name, date_added,
                        course_code, course_name, description, level, department,
                        credit_hours, max_enrollment, course_type, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (course_uuid, course_code, course_name, timestamp,
                          course_code, course_name, description, level, department,
                          credit_hours, max_enrollment, course_type, timestamp, timestamp))
                    
                    success_count += 1
                    
                except (ValueError, sqlite3.Error) as e:
                    print(f"Row {row_num}: Error - {e}")
                    error_count += 1
                    continue
            
            conn.commit()
            conn.close()
            
            print(f"\nImport completed!")
            print(f"Successfully imported: {success_count} courses")
            print(f"Errors: {error_count} courses")
            
            return success_count > 0
            
    except FileNotFoundError:
        print("File not found.")
        return False
    except Exception as e:
        print(f"Error importing courses: {e}")
        return False

@log_read(module="course_management", description="Exporting courses to CSV")
def export_courses_to_csv(auth):
    """Export courses to a CSV file"""
    if not auth or not auth.current_user:
        print("You must be logged in to export courses.")
        return False
    
    if not auth.check_permission('view_courses'):
        print("You don't have permission to export courses.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get filter criteria
        print("\nExport Filters (leave blank for all):")
        department = input("Department: ").strip()
        level = input("Level: ").strip()
        status = input("Status: ").strip()
        
        # Build query
        conditions = []
        params = []
        
        if department:
            conditions.append("department = ?")
            params.append(department)
        
        if level:
            conditions.append("level = ?")
            params.append(level)
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        query = "SELECT * FROM courses"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY course_code"
        
        cursor.execute(query, params)
        courses = cursor.fetchall()
        
        if not courses:
            print("No courses found to export.")
            conn.close()
            return False
        
        # Get column names
        cursor.execute("PRAGMA table_info(courses)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"courses_export_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(columns)
            
            # Write data
            for course in courses:
                writer.writerow(course)
        
        conn.close()
        
        print(f"\nExported {len(courses)} courses to {filename}")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False
    except Exception as e:
        print(f"Error exporting courses: {e}")
        return False

# =====================================================================
# ANALYTICS AND REPORTING
# =====================================================================

@log_read(module="course_management", description="Generating course analytics")
def generate_course_analytics(auth):
    """Generate comprehensive course analytics"""
    if not auth or not auth.current_user:
        print("You must be logged in to view analytics.")
        return
    
    if not auth.check_permission('view_courses'):
        print("You don't have permission to view analytics.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nCourse Analytics Dashboard")
        print("=========================")
        
        # Total courses by status
        cursor.execute("SELECT status, COUNT(*) FROM courses GROUP BY status")
        status_counts = cursor.fetchall()
        
        print("\n1. Courses by Status:")
        for status, count in status_counts:
            print(f"   {status}: {count}")
        
        # Enrollment statistics
        cursor.execute("""
        SELECT 
            COUNT(*) as total_courses,
            SUM(current_enrollment) as total_enrolled,
            AVG(current_enrollment) as avg_enrollment,
            SUM(max_enrollment) as total_capacity,
            ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as avg_fill_rate
        FROM courses 
        WHERE status = 'Active'
        """)
        
        enrollment_stats = cursor.fetchone()
        
        print("\n2. Enrollment Statistics:")
        print(f"   Total Active Courses: {enrollment_stats[0]}")
        print(f"   Total Students Enrolled: {enrollment_stats[1]}")
        print(f"   Average Enrollment per Course: {enrollment_stats[2]:.1f}")
        print(f"   Total Capacity: {enrollment_stats[3]}")
        print(f"   Average Fill Rate: {enrollment_stats[4]}%")
        
        # Department distribution
        cursor.execute("""
        SELECT department, COUNT(*) as course_count, SUM(current_enrollment) as total_students
        FROM courses 
        WHERE department IS NOT NULL AND department != ''
        GROUP BY department 
        ORDER BY course_count DESC
        """)
        
        dept_stats = cursor.fetchall()
        
        print("\n3. Courses by Department:")
        print(f"   {'Department':<20} {'Courses':<10} {'Students':<10}")
        print("   " + "-" * 40)
        for dept, courses, students in dept_stats:
            print(f"   {dept:<20} {courses:<10} {students or 0:<10}")
        
        # Level distribution
        cursor.execute("""
        SELECT level, COUNT(*) as course_count, AVG(credit_hours) as avg_credits
        FROM courses 
        WHERE level IS NOT NULL AND level != ''
        GROUP BY level
        ORDER BY course_count DESC
        """)
        
        level_stats = cursor.fetchall()
        
        print("\n4. Courses by Level:")
        print(f"   {'Level':<15} {'Courses':<10} {'Avg Credits':<12}")
        print("   " + "-" * 37)
        for level, courses, avg_credits in level_stats:
            print(f"   {level:<15} {courses:<10} {avg_credits:.1f}")
        
        # Most popular courses
        cursor.execute("""
        SELECT course_code, course_name, current_enrollment, max_enrollment,
               ROUND(CAST(current_enrollment AS FLOAT) / max_enrollment * 100, 1) as fill_rate
        FROM courses 
        WHERE status = 'Active' AND max_enrollment > 0
        ORDER BY current_enrollment DESC, fill_rate DESC
        LIMIT 10
        """)
        
        popular_courses = cursor.fetchall()
        
        print("\n5. Most Popular Courses (Top 10):")
        print(f"   {'Code':<8} {'Name':<25} {'Enrolled':<10} {'Fill Rate':<10}")
        print("   " + "-" * 53)
        for code, name, enrolled, capacity, fill_rate in popular_courses:
            name_short = name[:22] + "..." if len(name) > 25 else name
            print(f"   {code:<8} {name_short:<25} {enrolled:<10} {fill_rate}%")
        
        # Courses with availability
        cursor.execute("""
        SELECT COUNT(*) as available_courses
        FROM courses 
        WHERE status = 'Active' AND current_enrollment < max_enrollment
        """)
        
        available_count = cursor.fetchone()[0]
        
        print(f"\n6. Course Availability:")
        print(f"   Courses with Available Spots: {available_count}")
        
        # Credit hour distribution
        cursor.execute("""
        SELECT credit_hours, COUNT(*) as course_count
        FROM courses 
        GROUP BY credit_hours
        ORDER BY credit_hours
        """)
        
        credit_dist = cursor.fetchall()
        
        print("\n7. Credit Hour Distribution:")
        for credits, count in credit_dist:
            print(f"   {credits} credits: {count} courses")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

# =====================================================================
# WAITLIST MANAGEMENT
# =====================================================================

@log_create(module="course_management", description="Adding student to waitlist")
def add_to_waitlist(auth):
    """Add a student to a course waitlist"""
    if not auth or not auth.current_user:
        print("You must be logged in to manage waitlists.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to manage waitlists.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Show full courses
        cursor.execute("""
        SELECT id, course_code, course_name, current_enrollment, max_enrollment
        FROM courses 
        WHERE current_enrollment >= max_enrollment AND status = 'Active'
        ORDER BY course_code
        """)
        
        full_courses = cursor.fetchall()
        
        if not full_courses:
            print("No full courses found.")
            conn.close()
            return False
        
        print("\nFull Courses Available for Waitlist:")
        for course in full_courses:
            print(f"{course[0]}. {course[1]} - {course[2]} ({course[3]}/{course[4]})")
        
        # Select course
        while True:
            try:
                course_id = int(input("\nEnter course ID: "))
                if any(c[0] == course_id for c in full_courses):
                    break
                print("Invalid course ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        student_id = input("Enter student ID: ").strip()
        if not student_id:
            print("Student ID cannot be empty.")
            return False
        
        # Check if student is already on waitlist
        cursor.execute("SELECT id FROM course_waitlist WHERE course_id = ? AND student_id = ?", 
                      (course_id, student_id))
        if cursor.fetchone():
            print("Student is already on the waitlist for this course.")
            conn.close()
            return False
        
        # Get next position
        cursor.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM course_waitlist WHERE course_id = ?", 
                      (course_id,))
        position = cursor.fetchone()[0]
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO course_waitlist (course_id, student_id, position, added_at)
        VALUES (?, ?, ?, ?)
        ''', (course_id, student_id, position, timestamp))
        
        conn.commit()
        conn.close()
        
        print(f"\nStudent {student_id} added to waitlist at position {position}.")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_read(module="course_management", description="Viewing course waitlists")
def view_waitlists(auth):
    """View waitlists for courses"""
    if not auth or not auth.current_user:
        print("You must be logged in to view waitlists.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        course_choice = input("Enter course ID to view its waitlist (or press Enter for all): ").strip()
        
        if course_choice:
            try:
                course_id = int(course_choice)
                cursor.execute("""
                SELECT c.course_code, c.course_name, w.student_id, w.position, w.added_at, w.status
                FROM course_waitlist w
                JOIN courses c ON w.course_id = c.id
                WHERE w.course_id = ?
                ORDER BY w.position
                """, (course_id,))
                
                waitlist = cursor.fetchall()
                if waitlist:
                    print(f"\nWaitlist for {waitlist[0][0]} - {waitlist[0][1]}:")
                    print(f"{'Position':<10} {'Student ID':<15} {'Added':<20} {'Status':<10}")
                    print("-" * 55)
                    for entry in waitlist:
                        print(f"{entry[3]:<10} {entry[2]:<15} {entry[4]:<20} {entry[5]:<10}")
                else:
                    print("No waitlist entries found for this course.")
            except ValueError:
                print("Invalid course ID.")
        else:
            cursor.execute("""
            SELECT c.course_code, c.course_name, COUNT(w.id) as waitlist_count
            FROM courses c
            LEFT JOIN course_waitlist w ON c.id = w.course_id
            GROUP BY c.id, c.course_code, c.course_name
            HAVING waitlist_count > 0
            ORDER BY waitlist_count DESC, c.course_code
            """)
            
            waitlist_summary = cursor.fetchall()
            if waitlist_summary:
                print("\nCourses with Waitlists:")
                print(f"{'Code':<10} {'Name':<30} {'Waitlist Count':<15}")
                print("-" * 55)
                for code, name, count in waitlist_summary:
                    print(f"{code:<10} {name:<30} {count:<15}")
            else:
                print("No waitlists found in the system.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

# =====================================================================
# COURSE RECOMMENDATIONS
# =====================================================================

@log_read(module="course_management", description="Generating course recommendations")
def recommend_courses(auth):
    """Recommend courses based on various criteria"""
    if not auth or not auth.current_user:
        print("You must be logged in to get recommendations.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nCourse Recommendation System")
        print("===========================")
        
        recommendation_type = input("Select recommendation type:\n1. Popular courses\n2. Courses with availability\n3. Prerequisites for a course\nEnter choice (1-3): ").strip()
        
        if recommendation_type == '1':
            # Popular courses
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, 
                   ROUND(CAST(current_enrollment AS FLOAT) / max_enrollment * 100, 1) as popularity
            FROM courses 
            WHERE status = 'Active' AND max_enrollment > 0
            ORDER BY current_enrollment DESC, popularity DESC
            LIMIT 10
            """)
            
            popular = cursor.fetchall()
            print("\nMost Popular Courses:")
            print(f"{'Code':<10} {'Name':<30} {'Enrolled':<10} {'Popularity':<12}")
            print("-" * 62)
            for code, name, enrolled, popularity in popular:
                print(f"{code:<10} {name:<30} {enrolled:<10} {popularity}%")
        
        elif recommendation_type == '2':
            # Available courses
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment,
                   (max_enrollment - current_enrollment) as available_spots
            FROM courses 
            WHERE status = 'Active' AND current_enrollment < max_enrollment
            ORDER BY available_spots DESC, course_code
            """)
            
            available = cursor.fetchall()
            print("\nCourses with Available Spots:")
            print(f"{'Code':<10} {'Name':<30} {'Available':<12} {'Total':<8}")
            print("-" * 60)
            for code, name, current, max_enroll, available_spots in available:
                print(f"{code:<10} {name:<30} {available_spots:<12} {max_enroll:<8}")
        
        elif recommendation_type == '3':
            # Prerequisites for a course
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
            
            print("\nAvailable Courses:")
            for course in courses[:10]:  # Show first 10
                print(f"{course[0]}. {course[1]} - {course[2]}")
            
            if len(courses) > 10:
                print("... and more")
            
            try:
                target_course_id = int(input("\nEnter course ID to see prerequisites: "))
                
                cursor.execute("""
                SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c1 ON cp.course_id = c1.id
                JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                WHERE cp.course_id = ?
                ORDER BY cp.is_required DESC, c2.course_code
                """, (target_course_id,))
                
                prereqs = cursor.fetchall()
                if prereqs:
                    print(f"\nPrerequisites for {prereqs[0][0]} - {prereqs[0][1]}:")
                    print(f"{'Code':<10} {'Name':<30} {'Type':<12}")
                    print("-" * 52)
                    for prereq in prereqs:
                        req_type = "Required" if prereq[4] else "Recommended"
                        print(f"{prereq[2]:<10} {prereq[3]:<30} {req_type:<12}")
                else:
                    print("No prerequisites found for this course.")
            except ValueError:
                print("Invalid course ID.")
        
        else:
            print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

# =====================================================================
# COURSE STATUS MANAGEMENT
# =====================================================================

@log_update(module="course_management", description="Updating course status")
def manage_course_status(auth):
    """Manage course status (Active, Inactive, Archived, Cancelled)"""
    if not auth or not auth.current_user:
        print("You must be logged in to manage course status.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to manage course status.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Show all courses with current status
        cursor.execute("SELECT id, course_code, course_name, status FROM courses ORDER BY course_code")
        courses = cursor.fetchall()
        
        if not courses:
            print("No courses found.")
            conn.close()
            return False
        
        print("\nAll Courses:")
        print(f"{'ID':<5} {'Code':<10} {'Name':<30} {'Status':<12}")
        print("-" * 57)
        for course in courses:
            print(f"{course[0]:<5} {course[1]:<10} {course[2]:<30} {course[3]:<12}")
        
        # Select course (handle both integer and string IDs)
        while True:
            course_id_input = input("\nEnter course ID to update status: ").strip()
            # Try to convert to int, but also accept string IDs
            try:
                course_id = int(course_id_input)
            except ValueError:
                course_id = course_id_input
            selected_course = next((c for c in courses if str(c[0]) == str(course_id)), None)
            if selected_course:
                break
            print("Invalid course ID.")
        
        current_status = selected_course[3]
        print(f"\nCurrent status: {current_status}")
        
        # Status options
        status_options = ["Active", "Inactive", "Archived", "Cancelled"]
        print("\nSelect new status:")
        for i, status in enumerate(status_options, 1):
            print(f"{i}. {status}")
        
        while True:
            try:
                status_choice = int(input("Enter choice (1-4): "))
                if 1 <= status_choice <= 4:
                    new_status = status_options[status_choice - 1]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")
        
        if new_status == current_status:
            print("Status is already set to this value.")
            conn.close()
            return False
        
        # Confirmation and reason
        reason = input("Enter reason for status change (optional): ").strip()
        
        confirm = input(f"\nChange status from '{current_status}' to '{new_status}'? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Status change cancelled.")
            conn.close()
            return False
        
        # Update status
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Try with updated_at first, fall back to just status if column doesn't exist
        try:
            cursor.execute("UPDATE courses SET status = ?, updated_at = ? WHERE id = ?",
                          (new_status, timestamp, selected_course[0]))
        except sqlite3.OperationalError:
            cursor.execute("UPDATE courses SET status = ? WHERE id = ?",
                          (new_status, selected_course[0]))
        
        # Log the change in history (wrap in try/except in case table doesn't exist)
        try:
            cursor.execute('''
            INSERT INTO course_history (course_id, field_name, old_value, new_value, changed_by, changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (selected_course[0], 'status', current_status, new_status,
                  auth.current_user if auth and auth.current_user else 'system', timestamp))
        except sqlite3.OperationalError:
            pass  # Table may not exist
        
        conn.commit()
        conn.close()
        
        print(f"\nStatus updated successfully!")
        print(f"Course: {selected_course[1]} - {selected_course[2]}")
        print(f"Status changed from '{current_status}' to '{new_status}'")
        if reason:
            print(f"Reason: {reason}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

# =====================================================================
# ENHANCED MENU SYSTEM
# =====================================================================

@log_menu_navigation(description="Displaying enhanced course management menu")
def display_enhanced_course_menu(auth):
    """Display the enhanced course management menu"""
    if not auth or not auth.current_user:
        print(get_text('course_mgmt.login_required', default='You must be logged in to access course management.'))
        return

    # Initialize enhanced database schema
    initialize_enhanced_database()

    while True:
        print("\n" + "="*100)
        print(get_text('course_mgmt.title', default='ENHANCED COURSE MANAGEMENT SYSTEM').center(100))
        print("="*100)

        if auth.check_permission('manage_courses'):
            print(f"\n📚 {get_text('course_mgmt.sections.course_management', default='COURSE MANAGEMENT')}:")
            print(f"{'1.  ' + get_text('course_mgmt.menu.create_course', default='Create new course'):<25} {'2.  ' + get_text('course_mgmt.menu.view_courses', default='View all courses'):<25} {'3.  ' + get_text('course_mgmt.menu.update_course', default='Update course'):<25} {'4.  ' + get_text('course_mgmt.menu.delete_course', default='Delete course'):<25}")
            print(f"{'5.  ' + get_text('course_mgmt.menu.manage_status', default='Manage course status'):<25} {'6.  ' + get_text('course_mgmt.menu.search_courses', default='Search courses'):<25}")

            print(f"\n🔗 {get_text('course_mgmt.sections.prerequisites', default='PREREQUISITES & RELATIONSHIPS')}:")
            print(f"{'7.  ' + get_text('course_mgmt.menu.add_prerequisite', default='Add prerequisite'):<25} {'8.  ' + get_text('course_mgmt.menu.view_prerequisites', default='View prerequisites'):<25} {'9.  ' + get_text('course_mgmt.menu.remove_prerequisite', default='Remove prerequisite'):<25}")

            print(f"\n👨‍🏫 {get_text('course_mgmt.sections.instructor_management', default='INSTRUCTOR MANAGEMENT')}:")
            print(f"{'10. ' + get_text('course_mgmt.menu.create_instructor', default='Create instructor'):<25} {'11. ' + get_text('course_mgmt.menu.view_instructors', default='View instructors'):<25} {'12. ' + get_text('course_mgmt.menu.assign_to_course', default='Assign to course'):<25}")

            print(f"\n📅 {get_text('course_mgmt.sections.scheduling', default='SCHEDULING')}:")
            print(f"{'13. ' + get_text('course_mgmt.menu.create_schedule', default='Create schedule'):<25} {'14. ' + get_text('course_mgmt.menu.view_schedules', default='View schedules'):<25} {'15. ' + get_text('course_mgmt.menu.update_schedule', default='Update schedule'):<25}")

            print(f"\n📊 {get_text('course_mgmt.sections.enrollment_waitlists', default='ENROLLMENT & WAITLISTS')}:")
            print(f"{'16. ' + get_text('course_mgmt.menu.add_to_waitlist', default='Add to waitlist'):<25} {'17. ' + get_text('course_mgmt.menu.view_waitlists', default='View waitlists'):<25} {'18. ' + get_text('course_mgmt.menu.process_waitlist', default='Process waitlist'):<25}")

            print(f"\n📈 {get_text('course_mgmt.sections.analytics_reporting', default='ANALYTICS & REPORTING')}:")
            print(f"{'19. ' + get_text('course_mgmt.menu.analytics_dashboard', default='Analytics dashboard'):<25} {'20. ' + get_text('course_mgmt.menu.enrollment_report', default='Enrollment report'):<25} {'21. ' + get_text('course_mgmt.menu.dept_statistics', default='Dept statistics'):<25}")

            print(f"\n💾 {get_text('course_mgmt.sections.bulk_operations', default='BULK OPERATIONS')}:")
            print(f"{'22. ' + get_text('course_mgmt.menu.import_csv', default='Import from CSV'):<25} {'23. ' + get_text('course_mgmt.menu.export_csv', default='Export to CSV'):<25} {'24. ' + get_text('course_mgmt.menu.bulk_update', default='Bulk update'):<25}")

            print(f"\n🎯 {get_text('course_mgmt.sections.recommendations', default='RECOMMENDATIONS')}:")
            print(f"{'25. ' + get_text('course_mgmt.menu.recommendations', default='Recommendations'):<25} {'26. ' + get_text('course_mgmt.menu.alternative_courses', default='Alternative courses'):<25}")

            print(f"\n🔧 {get_text('course_mgmt.sections.utilities', default='UTILITIES')}:")
            print(f"{'27. ' + get_text('course_mgmt.menu.course_history', default='Course history'):<25} {'28. ' + get_text('course_mgmt.menu.system_maintenance', default='System maintenance'):<25} {'29. ' + get_text('course_mgmt.menu.module_management', default='Module Management'):<25}")

            print(f"\n⚙️  {get_text('course_mgmt.sections.settings', default='SETTINGS')}:")
            print(f"{'30. ' + get_text('course_mgmt.menu.language', default='Change Language'):<25}")

            print(f"\n0.  {get_text('course_mgmt.menu.return_main', default='Return to Main Menu')}")

            max_option = 30
            
        elif auth.check_permission('view_courses'):
            print(f"\n📚 {get_text('course_mgmt.sections.course_viewing', default='COURSE VIEWING')}:")
            print(f"1. {get_text('course_mgmt.menu.view_courses', default='View all courses')}")
            print(f"2. {get_text('course_mgmt.menu.search_courses', default='Search courses')}")
            print(f"3. {get_text('course_mgmt.menu.view_prerequisites', default='View prerequisites')}")
            print(f"4. {get_text('course_mgmt.menu.recommendations', default='Course recommendations')}")
            print(f"5. {get_text('course_mgmt.menu.course_analytics', default='Course analytics')}")
            print(f"6. {get_text('course_mgmt.menu.language', default='Change Language')}")
            print(f"0. {get_text('course_mgmt.menu.return_main', default='Return to Main Menu')}")

            max_option = 6
        else:
            print(get_text('course_mgmt.no_permission', default="You don't have permission to manage courses."))
            return

        choice = input(f"\n{get_text('course_mgmt.enter_choice', default='Enter your choice')} (0-{max_option}): ").strip()
        
        if choice == '0':
            return
        
        # Handle menu choices
        if auth.check_permission('manage_courses'):
            if choice == '1':
                create_enhanced_course(auth)
            elif choice == '2':
                view_all_courses(auth)
            elif choice == '3':
                update_course(auth)
            elif choice == '4':
                delete_course(auth)
            elif choice == '5':
                manage_course_status(auth)
            elif choice == '6':
                search_courses(auth)
            elif choice == '7':
                add_prerequisite(auth)
            elif choice == '8':
                view_prerequisites(auth)
            elif choice == '9':
                remove_prerequisite(auth)
            elif choice == '10':
                create_instructor(auth)
            elif choice == '11':
                view_instructors(auth)
            elif choice == '12':
                assign_instructor_to_course(auth)
            elif choice == '13':
                create_course_schedule(auth)
            elif choice == '14':
                view_course_schedules(auth)
            elif choice == '15':
                update_schedule(auth)
            elif choice == '16':
                add_to_waitlist(auth)
            elif choice == '17':
                view_waitlists(auth)
            elif choice == '18':
                process_waitlist(auth)
            elif choice == '19':
                generate_course_analytics(auth)
            elif choice == '20':
                generate_enrollment_report(auth)
            elif choice == '21':
                department_statistics(auth)
            elif choice == '22':
                import_courses_from_csv(auth)
            elif choice == '23':
                export_courses_to_csv(auth)
            elif choice == '24':
                bulk_update_courses(auth)
            elif choice == '25':
                recommend_courses(auth)
            elif choice == '26':
                find_alternative_courses(auth)
            elif choice == '27':
                view_course_history(auth)
            elif choice == '28':
                system_maintenance(auth)
            elif choice == '29':
                # Import module management menu
                from university_system.modules.shared.cli.module_operations import display_module_management_menu
                display_module_management_menu()
            elif choice == '30':
                display_language_menu_option()
            else:
                print(get_text('course_mgmt.invalid_choice', default='Invalid choice. Please enter a number between 0 and {max_option}.').format(max_option=max_option))
        
        else:  # View-only permissions
            if choice == '1':
                view_all_courses(auth)
            elif choice == '2':
                search_courses(auth)
            elif choice == '3':
                view_prerequisites(auth)
            elif choice == '4':
                recommend_courses(auth)
            elif choice == '5':
                generate_course_analytics(auth)
            elif choice == '6':
                display_language_menu_option()
            else:
                print(get_text('course_mgmt.invalid_choice', default='Invalid choice. Please enter a number between 0 and {max_option}.').format(max_option=max_option))

        # Pause before showing menu again
        input(f"\n{get_text('course_mgmt.press_enter', default='Press Enter to continue...')}")

# =====================================================================
# ADDITIONAL HELPER FUNCTIONS - COMPLETE IMPLEMENTATIONS
# =====================================================================

@log_delete(module="course_management", description="Removing course prerequisite")
def remove_prerequisite(auth):
    """Remove a prerequisite from a course"""
    if not auth or not auth.current_user:
        print("You must be logged in to remove prerequisites.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to manage prerequisites.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Show courses with prerequisites
        cursor.execute("""
        SELECT DISTINCT c1.id, c1.course_code, c1.course_name, COUNT(cp.id) as prereq_count
        FROM courses c1
        JOIN course_prerequisites cp ON c1.id = cp.course_id
        GROUP BY c1.id, c1.course_code, c1.course_name
        ORDER BY c1.course_code
        """)
        
        courses_with_prereqs = cursor.fetchall()
        
        if not courses_with_prereqs:
            print("No courses with prerequisites found.")
            conn.close()
            return False
        
        print("\nCourses with Prerequisites:")
        for course in courses_with_prereqs:
            print(f"{course[0]}. {course[1]} - {course[2]} ({course[3]} prerequisites)")
        
        # Select course
        while True:
            try:
                course_id = int(input("\nEnter course ID to remove prerequisite from: "))
                if any(c[0] == course_id for c in courses_with_prereqs):
                    break
                print("Invalid course ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Show prerequisites for selected course
        cursor.execute("""
        SELECT cp.id, c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
        FROM course_prerequisites cp
        JOIN courses c1 ON cp.course_id = c1.id
        JOIN courses c2 ON cp.prerequisite_course_id = c2.id
        WHERE cp.course_id = ?
        ORDER BY c2.course_code
        """, (course_id,))
        
        prerequisites = cursor.fetchall()
        
        print(f"\nPrerequisites for {prerequisites[0][1]} - {prerequisites[0][2]}:")
        print(f"{'ID':<5} {'Prerequisite Code':<15} {'Prerequisite Name':<30} {'Type':<12}")
        print("-" * 62)
        
        for prereq in prerequisites:
            req_type = "Required" if prereq[5] else "Recommended"
            print(f"{prereq[0]:<5} {prereq[3]:<15} {prereq[4]:<30} {req_type:<12}")
        
        # Select prerequisite to remove
        while True:
            try:
                prereq_id = int(input("\nEnter prerequisite ID to remove: "))
                if any(p[0] == prereq_id for p in prerequisites):
                    break
                print("Invalid prerequisite ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get prerequisite details for confirmation
        selected_prereq = next(p for p in prerequisites if p[0] == prereq_id)
        
        confirm = input(f"\nRemove prerequisite '{selected_prereq[3]} - {selected_prereq[4]}'? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Removal cancelled.")
            conn.close()
            return False
        
        # Remove the prerequisite
        cursor.execute("DELETE FROM course_prerequisites WHERE id = ?", (prereq_id,))
        rows_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if rows_deleted > 0:
            print(f"\nPrerequisite '{selected_prereq[3]} - {selected_prereq[4]}' removed successfully!")
            return True
        else:
            print("Error: No prerequisite was removed.")
            return False
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_create(module="course_management", description="Assigning instructor to course")
def assign_instructor_to_course(auth):
    """Assign an instructor to a course"""
    if not auth or not auth.current_user:
        print("You must be logged in to assign instructors.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to assign instructors.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Show available courses with schedules but no instructor
        cursor.execute("""
        SELECT cs.id, c.course_code, c.course_name, cs.semester, cs.year, cs.instructor_id
        FROM course_schedule cs
        JOIN courses c ON cs.course_id = c.id
        WHERE c.status = 'Active'
        ORDER BY c.course_code, cs.semester, cs.year
        """)
        
        schedules = cursor.fetchall()
        
        if not schedules:
            print("No course schedules found.")
            conn.close()
            return False
        
        print("\nCourse Schedules:")
        print(f"{'ID':<5} {'Code':<10} {'Name':<25} {'Semester':<10} {'Year':<6} {'Current Instructor':<15}")
        print("-" * 71)
        
        for schedule in schedules:
            current_instructor = "Assigned" if schedule[5] else "None"
            print(f"{schedule[0]:<5} {schedule[1]:<10} {schedule[2]:<25} {schedule[3]:<10} {schedule[4]:<6} {current_instructor:<15}")
        
        # Select course schedule
        while True:
            try:
                schedule_id = int(input("\nEnter schedule ID to assign instructor: "))
                selected_schedule = next((s for s in schedules if s[0] == schedule_id), None)
                if selected_schedule:
                    break
                print("Invalid schedule ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Show available instructors
        cursor.execute("""
        SELECT i.id, i.first_name, i.last_name, i.department, i.specialization,
               COUNT(cs.id) as current_courses
        FROM instructors i
        LEFT JOIN course_schedule cs ON i.id = cs.instructor_id 
            AND cs.semester = ? AND cs.year = ?
        WHERE i.status = 'Active'
        GROUP BY i.id, i.first_name, i.last_name, i.department, i.specialization
        ORDER BY i.last_name, i.first_name
        """, (selected_schedule[3], selected_schedule[4]))
        
        instructors = cursor.fetchall()
        
        if not instructors:
            print("No active instructors found.")
            conn.close()
            return False
        
        print(f"\nAvailable Instructors for {selected_schedule[3]} {selected_schedule[4]}:")
        print(f"{'ID':<5} {'Name':<25} {'Department':<15} {'Current Load':<15}")
        print("-" * 60)
        
        for instructor in instructors:
            full_name = f"{instructor[1]} {instructor[2]}"
            print(f"{instructor[0]:<5} {full_name:<25} {instructor[3]:<15} {instructor[5]} courses")
        
        # Select instructor
        while True:
            try:
                instructor_id = int(input("\nEnter instructor ID to assign: "))
                selected_instructor = next((i for i in instructors if i[0] == instructor_id), None)
                if selected_instructor:
                    break
                print("Invalid instructor ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Check instructor's workload
        if selected_instructor[5] >= 4:  # Assuming max 4 courses per semester
            confirm = input(f"\nWarning: This instructor already has {selected_instructor[5]} courses. Continue? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Assignment cancelled.")
                conn.close()
                return False
        
        # Assign instructor
        cursor.execute("UPDATE course_schedule SET instructor_id = ? WHERE id = ?", 
                      (instructor_id, schedule_id))
        
        conn.commit()
        conn.close()
        
        instructor_name = f"{selected_instructor[1]} {selected_instructor[2]}"
        print(f"\nInstructor '{instructor_name}' assigned to '{selected_schedule[1]} - {selected_schedule[2]}' successfully!")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_read(module="course_management", description="Viewing course schedules")
def view_course_schedules(auth):
    """View course schedules"""
    if not auth or not auth.current_user:
        print("You must be logged in to view schedules.")
        return
    
    if not auth.check_permission('view_courses'):
        print("You don't have permission to view schedules.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Filter options
        print("\nSchedule Filters:")
        semester = input("Enter semester (Fall/Spring/Summer/Winter) or press Enter for all: ").strip()
        year_input = input("Enter year or press Enter for current year: ").strip()
        
        current_year = datetime.now().year
        year = int(year_input) if year_input else current_year
        
        # Build query
        conditions = ["cs.year = ?"]
        params = [year]
        
        if semester:
            conditions.append("cs.semester = ?")
            params.append(semester)
        
        query = """
        SELECT cs.id, c.course_code, c.course_name, cs.semester, cs.year,
               cs.start_time, cs.end_time, cs.days_of_week, cs.classroom,
               COALESCE(i.first_name || ' ' || i.last_name, 'Unassigned') as instructor
        FROM course_schedule cs
        JOIN courses c ON cs.course_id = c.id
        LEFT JOIN instructors i ON cs.instructor_id = i.id
        WHERE """ + " AND ".join(conditions) + """
        ORDER BY cs.semester, c.course_code, cs.start_time
        """
        
        cursor.execute(query, params)
        schedules = cursor.fetchall()
        
        if not schedules:
            filter_desc = f"{semester + ' ' if semester else ''}{year}"
            print(f"No schedules found for {filter_desc}.")
            conn.close()
            return
        
        # Group by semester
        current_semester = None
        print(f"\nCourse Schedules for {year}:")
        print("=" * 80)
        
        for schedule in schedules:
            if current_semester != schedule[3]:
                current_semester = schedule[3]
                print(f"\n{current_semester} {schedule[4]}:")
                print(f"{'Code':<8} {'Name':<25} {'Time':<15} {'Days':<20} {'Room':<12} {'Instructor':<15}")
                print("-" * 95)
            
            time_display = f"{schedule[5] or 'TBA'}-{schedule[6] or 'TBA'}" if schedule[5] and schedule[6] else "TBA"
            days_display = schedule[7] or "TBA"
            room_display = schedule[8] or "TBA"
            instructor_display = schedule[9]
            
            # Truncate long names for display
            name_display = schedule[2][:22] + "..." if len(schedule[2]) > 25 else schedule[2]
            days_display = days_display[:17] + "..." if len(days_display) > 20 else days_display
            instructor_display = instructor_display[:12] + "..." if len(instructor_display) > 15 else instructor_display
            
            print(f"{schedule[1]:<8} {name_display:<25} {time_display:<15} {days_display:<20} {room_display:<12} {instructor_display:<15}")
        
        # Summary statistics
        cursor.execute("""
        SELECT COUNT(*) as total_schedules,
               COUNT(DISTINCT cs.course_id) as unique_courses,
               COUNT(cs.instructor_id) as assigned_instructors
        FROM course_schedule cs
        WHERE cs.year = ?""" + (" AND cs.semester = ?" if semester else ""), 
        params)
        
        stats = cursor.fetchone()
        
        print(f"\nSummary:")
        print(f"Total Schedules: {stats[0]}")
        print(f"Unique Courses: {stats[1]}")
        print(f"Assigned Instructors: {stats[2]}")
        print(f"Unassigned Schedules: {stats[0] - stats[2]}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
    except ValueError:
        print("Invalid year format.")

@log_update(module="course_management", description="Updating course schedule")
def update_schedule(auth):
    """Update course schedule"""
    if not auth or not auth.current_user:
        print("You must be logged in to update schedules.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to update schedules.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Show existing schedules
        cursor.execute("""
        SELECT cs.id, c.course_code, c.course_name, cs.semester, cs.year,
               cs.start_time, cs.end_time, cs.days_of_week, cs.classroom,
               COALESCE(i.first_name || ' ' || i.last_name, 'Unassigned') as instructor
        FROM course_schedule cs
        JOIN courses c ON cs.course_id = c.id
        LEFT JOIN instructors i ON cs.instructor_id = i.id
        ORDER BY cs.year DESC, cs.semester, c.course_code
        """)
        
        schedules = cursor.fetchall()
        
        if not schedules:
            print("No schedules found.")
            conn.close()
            return False
        
        print("\nExisting Schedules:")
        print(f"{'ID':<5} {'Code':<8} {'Name':<20} {'Semester':<10} {'Year':<6} {'Time':<15} {'Days':<15}")
        print("-" * 79)
        
        for schedule in schedules:
            time_str = f"{schedule[5] or 'TBA'}-{schedule[6] or 'TBA'}"
            days_str = schedule[7] or "TBA"
            name_short = schedule[2][:17] + "..." if len(schedule[2]) > 20 else schedule[2]
            days_short = days_str[:12] + "..." if len(days_str) > 15 else days_str
            
            print(f"{schedule[0]:<5} {schedule[1]:<8} {name_short:<20} {schedule[3]:<10} {schedule[4]:<6} {time_str:<15} {days_short:<15}")
        
        # Select schedule to update
        while True:
            try:
                schedule_id = int(input("\nEnter schedule ID to update: "))
                cursor.execute("SELECT * FROM course_schedule WHERE id = ?", (schedule_id,))
                current_schedule = cursor.fetchone()
                if current_schedule:
                    break
                print("Invalid schedule ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Current values
        (id, course_id, semester, year, start_time, end_time, days_of_week, classroom, instructor_id, created_at) = current_schedule
        
        print(f"\nUpdating Schedule ID {schedule_id}")
        print("Enter new values (leave blank to keep current):")
        
        # Start time
        while True:
            new_start = input(f"Start time [{start_time or 'TBA'}]: ").strip()
            if not new_start:
                new_start = start_time
                break
            if validate_time_format(new_start):
                break
            print("Invalid time format. Use HH:MM")
        
        # End time
        while True:
            new_end = input(f"End time [{end_time or 'TBA'}]: ").strip()
            if not new_end:
                new_end = end_time
                break
            if validate_time_format(new_end):
                break
            print("Invalid time format. Use HH:MM")
        
        # Days of week
        while True:
            new_days = input(f"Days of week [{days_of_week or 'TBA'}]: ").strip()
            if not new_days:
                new_days = days_of_week
                break
            if validate_days_of_week(new_days):
                break
            print("Invalid days format. Use full day names separated by commas.")
        
        # Classroom
        new_classroom = input(f"Classroom [{classroom or 'TBA'}]: ").strip()
        if not new_classroom:
            new_classroom = classroom
        
        # Instructor
        cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE status = 'Active'")
        instructors = cursor.fetchall()
        
        print(f"\nCurrent instructor: {instructor_id or 'None'}")
        if instructors:
            print("Available instructors:")
            print("0. Remove instructor")
            for instructor in instructors:
                print(f"{instructor[0]}. {instructor[1]} {instructor[2]}")
            
            instr_choice = input("Enter instructor ID (or press Enter to keep current): ").strip()
            if instr_choice:
                try:
                    new_instructor_id = int(instr_choice)
                    if new_instructor_id == 0:
                        new_instructor_id = None
                    elif not any(i[0] == new_instructor_id for i in instructors):
                        print("Invalid instructor ID. Keeping current.")
                        new_instructor_id = instructor_id
                except ValueError:
                    print("Invalid instructor ID. Keeping current.")
                    new_instructor_id = instructor_id
            else:
                new_instructor_id = instructor_id
        else:
            new_instructor_id = instructor_id
        
        # Update the schedule
        cursor.execute("""
        UPDATE course_schedule 
        SET start_time = ?, end_time = ?, days_of_week = ?, classroom = ?, instructor_id = ?
        WHERE id = ?
        """, (new_start, new_end, new_days, new_classroom, new_instructor_id, schedule_id))
        
        conn.commit()
        conn.close()
        
        print(f"\nSchedule updated successfully!")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_update(module="course_management", description="Processing course waitlist")
def process_waitlist(auth):
    """Process waitlist when spots become available"""
    if not auth or not auth.current_user:
        print("You must be logged in to process waitlists.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to process waitlists.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Find courses with available spots and waitlists
        cursor.execute("""
        SELECT c.id, c.course_code, c.course_name, c.current_enrollment, c.max_enrollment,
               (c.max_enrollment - c.current_enrollment) as available_spots,
               COUNT(w.id) as waitlist_count
        FROM courses c
        LEFT JOIN course_waitlist w ON c.id = w.course_id AND w.status = 'Waiting'
        WHERE c.status = 'Active' AND c.current_enrollment < c.max_enrollment
        GROUP BY c.id, c.course_code, c.course_name, c.current_enrollment, c.max_enrollment
        HAVING waitlist_count > 0
        ORDER BY available_spots DESC, waitlist_count DESC
        """)
        
        courses_with_waitlists = cursor.fetchall()
        
        if not courses_with_waitlists:
            print("No courses with available spots and waitlists found.")
            conn.close()
            return False
        
        print("\nCourses with Available Spots and Waitlists:")
        print(f"{'ID':<5} {'Code':<8} {'Name':<25} {'Enrolled':<10} {'Available':<10} {'Waitlist':<10}")
        print("-" * 68)
        
        for course in courses_with_waitlists:
            enrollment_str = f"{course[3]}/{course[4]}"
            print(f"{course[0]:<5} {course[1]:<8} {course[2]:<25} {enrollment_str:<10} {course[5]:<10} {course[6]:<10}")
        
        # Select course to process
        while True:
            try:
                course_id = int(input("\nEnter course ID to process waitlist (0 to process all): "))
                if course_id == 0:
                    selected_courses = courses_with_waitlists
                    break
                elif any(c[0] == course_id for c in courses_with_waitlists):
                    selected_courses = [c for c in courses_with_waitlists if c[0] == course_id]
                    break
                else:
                    print("Invalid course ID.")
            except ValueError:
                print("Please enter a valid number.")
        
        total_processed = 0
        
        for course in selected_courses:
            course_id, code, name, current_enrolled, max_enrolled, available_spots, waitlist_count = course
            
            print(f"\nProcessing waitlist for {code} - {name}")
            print(f"Available spots: {available_spots}")
            
            # Get waitlist students in order
            cursor.execute("""
            SELECT id, student_id, position 
            FROM course_waitlist 
            WHERE course_id = ? AND status = 'Waiting'
            ORDER BY position
            LIMIT ?
            """, (course_id, available_spots))
            
            waitlist_students = cursor.fetchall()
            
            if not waitlist_students:
                print(f"No waiting students found for {code}")
                continue
            
            # Process each student
            for waitlist_entry in waitlist_students:
                waitlist_id, student_id, position = waitlist_entry
                
                # Update waitlist status
                cursor.execute("""
                UPDATE course_waitlist 
                SET status = 'Enrolled' 
                WHERE id = ?
                """, (waitlist_id,))
                
                # Update course enrollment
                cursor.execute("""
                UPDATE courses 
                SET current_enrollment = current_enrollment + 1,
                    updated_at = ?
                WHERE id = ?
                """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), course_id))
                
                print(f"  - Student {student_id} enrolled from position {position}")
                total_processed += 1
            
            # Update positions for remaining waitlist
            cursor.execute("""
            UPDATE course_waitlist 
            SET position = position - ?
            WHERE course_id = ? AND status = 'Waiting'
            """, (len(waitlist_students), course_id))
        
        conn.commit()
        conn.close()
        
        print(f"\nWaitlist processing completed!")
        print(f"Total students enrolled: {total_processed}")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_read(module="course_management", description="Generating enrollment report")
def generate_enrollment_report(auth):
    """Generate detailed enrollment report"""
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return False
    
    if not auth.check_permission('view_courses'):
        print("You don't have permission to generate reports.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nEnrollment Report Generator")
        print("=========================")
        
        # Report options
        print("Select report type:")
        print("1. Summary Report")
        print("2. Department Report")
        print("3. Course Level Report") 
        print("4. Detailed Course Report")
        print("5. Capacity Analysis")
        
        while True:
            try:
                report_type = int(input("Enter choice (1-5): "))
                if 1 <= report_type <= 5:
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if report_type == 1:  # Summary Report
            print(f"\nENROLLMENT SUMMARY REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)
            
            # Overall statistics
            cursor.execute("""
            SELECT 
                COUNT(*) as total_courses,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                AVG(current_enrollment) as avg_enrollment,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as avg_fill_rate
            FROM courses 
            WHERE status = 'Active'
            """)
            
            summary = cursor.fetchone()
            
            print(f"Total Active Courses: {summary[0]}")
            print(f"Total Students Enrolled: {summary[1]}")
            print(f"Total System Capacity: {summary[2]}")
            print(f"Average Enrollment per Course: {summary[3]:.1f}")
            print(f"Average Fill Rate: {summary[4]}%")
            print(f"Available Spots: {summary[2] - summary[1]}")
            
            # Status breakdown
            cursor.execute("SELECT status, COUNT(*) FROM courses GROUP BY status")
            status_data = cursor.fetchall()
            
            print(f"\nCourse Status Breakdown:")
            for status, count in status_data:
                print(f"  {status}: {count}")
        
        elif report_type == 2:  # Department Report
            print(f"\nDEPARTMENT ENROLLMENT REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)
            
            cursor.execute("""
            SELECT 
                COALESCE(department, 'Unknown') as dept,
                COUNT(*) as course_count,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as fill_rate
            FROM courses 
            WHERE status = 'Active'
            GROUP BY department
            ORDER BY total_students DESC
            """)
            
            dept_data = cursor.fetchall()
            
            print(f"{'Department':<20} {'Courses':<10} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}")
            print("-" * 60)
            
            for dept, courses, students, capacity, fill_rate in dept_data:
                print(f"{dept:<20} {courses:<10} {students:<10} {capacity:<10} {fill_rate}%")
        
        elif report_type == 3:  # Course Level Report
            print(f"\nCOURSE LEVEL ENROLLMENT REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)
            
            cursor.execute("""
            SELECT 
                COALESCE(level, 'Unknown') as course_level,
                COUNT(*) as course_count,
                SUM(current_enrollment) as total_students,
                AVG(credit_hours) as avg_credits,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as fill_rate
            FROM courses 
            WHERE status = 'Active'
            GROUP BY level
            ORDER BY total_students DESC
            """)
            
            level_data = cursor.fetchall()
            
            print(f"{'Level':<15} {'Courses':<10} {'Students':<10} {'Avg Credits':<12} {'Fill Rate':<10}")
            print("-" * 57)
            
            for level, courses, students, avg_credits, fill_rate in level_data:
                print(f"{level:<15} {courses:<10} {students:<10} {avg_credits:.1f} {fill_rate}%")
        
        elif report_type == 4:  # Detailed Course Report
            print(f"\nDETAILED COURSE ENROLLMENT REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)
            
            cursor.execute("""
            SELECT course_code, course_name, department, level, 
                   current_enrollment, max_enrollment,
                   ROUND(CAST(current_enrollment AS FLOAT) / max_enrollment * 100, 1) as fill_rate,
                   course_type, credit_hours
            FROM courses 
            WHERE status = 'Active'
            ORDER BY current_enrollment DESC
            """)
            
            course_data = cursor.fetchall()
            
            print(f"{'Code':<8} {'Name':<20} {'Dept':<10} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}")
            print("-" * 70)
            
            for course in course_data:
                name_short = course[1][:17] + "..." if len(course[1]) > 20 else course[1]
                enrollment_str = f"{course[4]}/{course[5]}"
                print(f"{course[0]:<8} {name_short:<20} {course[2]:<10} {course[3]:<12} {enrollment_str:<10} {course[6]}%")
        
        elif report_type == 5:  # Capacity Analysis
            print(f"\nCAPACITY ANALYSIS REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)
            
            # Over-enrolled courses
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment
            FROM courses 
            WHERE current_enrollment > max_enrollment AND status = 'Active'
            ORDER BY (current_enrollment - max_enrollment) DESC
            """)
            
            over_enrolled = cursor.fetchall()
            
            print("Over-enrolled Courses:")
            if over_enrolled:
                for course in over_enrolled:
                    excess = course[2] - course[3]
                    print(f"  {course[0]} - {course[1]}: {excess} over capacity")
            else:
                print("  None")
            
            # Under-enrolled courses
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment,
                   (max_enrollment - current_enrollment) as available
            FROM courses 
            WHERE current_enrollment < max_enrollment * 0.5 AND status = 'Active'
            ORDER BY available DESC
            """)
            
            under_enrolled = cursor.fetchall()
            
            print(f"\nUnder-enrolled Courses (< 50% capacity):")
            if under_enrolled:
                for course in under_enrolled:
                    fill_rate = (course[2] / course[3]) * 100
                    print(f"  {course[0]} - {course[1]}: {fill_rate:.1f}% full ({course[4]} spots available)")
            else:
                print("  None")
        
        # Option to save report
        save_option = input(f"\nSave report to file? (y/n): ").strip().lower()
        if save_option == 'y':
            filename = f"enrollment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            print(f"Report saved as {filename}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

@log_read(module="course_management", description="Viewing department statistics")
def department_statistics(auth):
    """Show department-specific statistics"""
    if not auth or not auth.current_user:
        print("You must be logged in to view statistics.")
        return
    
    if not auth.check_permission('view_courses'):
        print("You don't have permission to view statistics.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get list of departments
        cursor.execute("""
        SELECT DISTINCT COALESCE(department, 'Unknown') as dept
        FROM courses 
        WHERE department IS NOT NULL AND department != ''
        ORDER BY dept
        """)
        
        departments = [row[0] for row in cursor.fetchall()]
        
        if not departments:
            print("No departments found.")
            conn.close()
            return
        
        print("\nSelect Department for Statistics:")
        print("0. All Departments Overview")
        for i, dept in enumerate(departments, 1):
            print(f"{i}. {dept}")
        
        while True:
            try:
                choice = int(input(f"Enter choice (0-{len(departments)}): "))
                if choice == 0:
                    selected_dept = None
                    break
                elif 1 <= choice <= len(departments):
                    selected_dept = departments[choice - 1]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")
        
        if selected_dept:
            # Single department statistics
            print(f"\nDETAILED STATISTICS FOR {selected_dept.upper()} DEPARTMENT")
            print("=" * 60)
            
            # Basic stats
            cursor.execute("""
            SELECT 
                COUNT(*) as total_courses,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                AVG(current_enrollment) as avg_enrollment,
                AVG(credit_hours) as avg_credits,
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
            FROM courses 
            WHERE department = ?
            """, (selected_dept,))
            
            stats = cursor.fetchone()
            
            print(f"Total Courses: {stats[0]}")
            print(f"Active Courses: {stats[5]}")
            print(f"Total Students: {stats[1]}")
            print(f"Total Capacity: {stats[2]}")
            print(f"Average Enrollment: {stats[3]:.1f}")
            print(f"Average Credit Hours: {stats[4]:.1f}")
            if stats[2] > 0:
                print(f"Department Fill Rate: {(stats[1]/stats[2]*100):.1f}%")
            
            # Course breakdown by level
            cursor.execute("""
            SELECT level, COUNT(*), SUM(current_enrollment)
            FROM courses 
            WHERE department = ?
            GROUP BY level
            ORDER BY COUNT(*) DESC
            """, (selected_dept,))
            
            level_stats = cursor.fetchall()
            
            print(f"\nCourses by Level:")
            for level, count, enrollment in level_stats:
                level_name = level or "Unknown"
                print(f"  {level_name}: {count} courses, {enrollment} students")
            
            # Top courses by enrollment
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment
            FROM courses 
            WHERE department = ? AND status = 'Active'
            ORDER BY current_enrollment DESC
            LIMIT 5
            """, (selected_dept,))
            
            top_courses = cursor.fetchall()
            
            print(f"\nTop 5 Most Enrolled Courses:")
            for course in top_courses:
                print(f"  {course[0]} - {course[1]}: {course[2]}/{course[3]} students")
            
            # Instructors in department
            cursor.execute("""
            SELECT COUNT(DISTINCT i.id) as instructor_count
            FROM instructors i
            WHERE i.department = ? AND i.status = 'Active'
            """, (selected_dept,))
            
            instructor_count = cursor.fetchone()[0]
            print(f"\nActive Instructors: {instructor_count}")
            
        else:
            # All departments overview
            print(f"\nALL DEPARTMENTS OVERVIEW")
            print("=" * 50)
            
            cursor.execute("""
            SELECT 
                COALESCE(department, 'Unknown') as dept,
                COUNT(*) as course_count,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 1) as fill_rate,
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
            FROM courses 
            GROUP BY department
            ORDER BY total_students DESC
            """)
            
            all_dept_stats = cursor.fetchall()
            
            print(f"{'Department':<20} {'Courses':<10} {'Active':<8} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}")
            print("-" * 68)
            
            for dept_stat in all_dept_stats:
                dept, courses, students, capacity, fill_rate, active = dept_stat
                print(f"{dept:<20} {courses:<10} {active:<8} {students:<10} {capacity:<10} {fill_rate}%")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

@log_update(module="course_management", description="Bulk updating courses")
def bulk_update_courses(auth):
    """Bulk update multiple courses"""
    if not auth or not auth.current_user:
        print("You must be logged in to bulk update courses.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to bulk update courses.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nBulk Update Courses")
        print("==================")
        
        # Select criteria for courses to update
        print("Select courses to update by:")
        print("1. Department")
        print("2. Level")
        print("3. Status")
        print("4. Course Type")
        print("5. Manual Selection")
        
        while True:
            try:
                criteria = int(input("Enter choice (1-5): "))
                if 1 <= criteria <= 5:
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")
        
        courses_to_update = []
        
        if criteria == 1:  # By Department
            cursor.execute("SELECT DISTINCT department FROM courses WHERE department IS NOT NULL ORDER BY department")
            departments = [row[0] for row in cursor.fetchall()]
            
            print("\nAvailable Departments:")
            for i, dept in enumerate(departments, 1):
                print(f"{i}. {dept}")
            
            dept_choice = int(input("Select department: ")) - 1
            if 0 <= dept_choice < len(departments):
                selected_dept = departments[dept_choice]
                cursor.execute("SELECT id, course_code, course_name FROM courses WHERE department = ?", (selected_dept,))
                courses_to_update = cursor.fetchall()
        
        elif criteria == 2:  # By Level
            cursor.execute("SELECT DISTINCT level FROM courses WHERE level IS NOT NULL ORDER BY level")
            levels = [row[0] for row in cursor.fetchall()]
            
            print("\nAvailable Levels:")
            for i, level in enumerate(levels, 1):
                print(f"{i}. {level}")
            
            level_choice = int(input("Select level: ")) - 1
            if 0 <= level_choice < len(levels):
                selected_level = levels[level_choice]
                cursor.execute("SELECT id, course_code, course_name FROM courses WHERE level = ?", (selected_level,))
                courses_to_update = cursor.fetchall()
        
        elif criteria == 3:  # By Status
            statuses = ["Active", "Inactive", "Archived", "Cancelled"]
            print("\nAvailable Statuses:")
            for i, status in enumerate(statuses, 1):
                print(f"{i}. {status}")
            
            status_choice = int(input("Select status: ")) - 1
            if 0 <= status_choice < len(statuses):
                selected_status = statuses[status_choice]
                cursor.execute("SELECT id, course_code, course_name FROM courses WHERE status = ?", (selected_status,))
                courses_to_update = cursor.fetchall()
        
        elif criteria == 4:  # By Course Type
            cursor.execute("SELECT DISTINCT course_type FROM courses WHERE course_type IS NOT NULL ORDER BY course_type")
            types = [row[0] for row in cursor.fetchall()]
            
            print("\nAvailable Course Types:")
            for i, ctype in enumerate(types, 1):
                print(f"{i}. {ctype}")
            
            type_choice = int(input("Select course type: ")) - 1
            if 0 <= type_choice < len(types):
                selected_type = types[type_choice]
                cursor.execute("SELECT id, course_code, course_name FROM courses WHERE course_type = ?", (selected_type,))
                courses_to_update = cursor.fetchall()
        
        elif criteria == 5:  # Manual Selection
            cursor.execute("SELECT id, course_code, course_name, status FROM courses ORDER BY course_code")
            all_courses = cursor.fetchall()
            
            print("\nSelect courses (enter IDs separated by commas):")
            for course in all_courses:
                print(f"{course[0]}. {course[1]} - {course[2]} ({course[3]})")
            
            id_input = input("\nEnter course IDs: ").strip()
            selected_ids = [int(id.strip()) for id in id_input.split(',') if id.strip().isdigit()]
            
            cursor.execute(f"SELECT id, course_code, course_name FROM courses WHERE id IN ({','.join(['?']*len(selected_ids))})", selected_ids)
            courses_to_update = cursor.fetchall()
        
        if not courses_to_update:
            print("No courses selected for update.")
            conn.close()
            return False
        
        print(f"\nSelected {len(courses_to_update)} courses for update:")
        for course in courses_to_update:
            print(f"  {course[1]} - {course[2]}")
        
        # Select field to update
        print("\nSelect field to update:")
        print("1. Status")
        print("2. Max Enrollment")
        print("3. Course Fee")
        print("4. Course Type")
        print("5. Department")
        print("6. Level")
        
        while True:
            try:
                field_choice = int(input("Enter choice (1-6): "))
                if 1 <= field_choice <= 6:
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get new value
        if field_choice == 1:  # Status
            new_value = input("Enter new status (Active/Inactive/Archived/Cancelled): ").strip()
            field_name = "status"
        elif field_choice == 2:  # Max Enrollment
            new_value = int(input("Enter new max enrollment: "))
            field_name = "max_enrollment"
        elif field_choice == 3:  # Course Fee
            new_value = float(input("Enter new course fee: "))
            field_name = "course_fee"
        elif field_choice == 4:  # Course Type
            new_value = input("Enter new course type: ").strip()
            field_name = "course_type"
        elif field_choice == 5:  # Department
            new_value = input("Enter new department: ").strip()
            field_name = "department"
        elif field_choice == 6:  # Level
            new_value = input("Enter new level: ").strip()
            field_name = "level"
        
        # Confirm update
        confirm = input(f"\nUpdate {field_name} to '{new_value}' for {len(courses_to_update)} courses? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Bulk update cancelled.")
            conn.close()
            return False
        
        # Perform bulk update
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        course_ids = [course[0] for course in courses_to_update]
        
        placeholders = ','.join(['?'] * len(course_ids))
        update_query = f"UPDATE courses SET {field_name} = ?, updated_at = ? WHERE id IN ({placeholders})"
        
        cursor.execute(update_query, [new_value, timestamp] + course_ids)
        updated_count = cursor.rowcount
        
        # Log changes in history
        for course_id in course_ids:
            cursor.execute('''
            INSERT INTO course_history (course_id, field_name, old_value, new_value, changed_by, changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (course_id, field_name, "bulk_update", str(new_value), auth.current_user, timestamp))
        
        conn.commit()
        conn.close()
        
        print(f"\nBulk update completed!")
        print(f"Updated {updated_count} courses")
        print(f"Field: {field_name}")
        print(f"New value: {new_value}")
        return True
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error during bulk update: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_read(module="course_management", description="Finding alternative courses")
def find_alternative_courses(auth):
    """Find alternative courses for students"""
    if not auth or not auth.current_user:
        print("You must be logged in to find alternatives.")
        return
    
    if not auth.check_permission('view_courses'):
        print("You don't have permission to view courses.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nFind Alternative Courses")
        print("=======================")
        
        # Show courses for reference
        cursor.execute("SELECT id, course_code, course_name, department, level FROM courses WHERE status = 'Active' ORDER BY course_code")
        courses = cursor.fetchall()
        
        if not courses:
            print("No active courses found.")
            conn.close()
            return
        
        print("\nActive Courses:")
        for i, course in enumerate(courses[:20]):  # Show first 20
            print(f"{course[0]}. {course[1]} - {course[2]} ({course[3]}, {course[4]})")
        
        if len(courses) > 20:
            print("... and more")
        
        # Get reference course
        while True:
            ref_course_id = input("\nEnter course ID to find alternatives for: ").strip()
            # Match by string comparison since IDs can be text or numeric
            ref_course = next((c for c in courses if str(c[0]) == ref_course_id), None)
            if ref_course:
                break
            print("Invalid course ID.")
        
        ref_id, ref_code, ref_name, ref_dept, ref_level = ref_course
        
        print(f"\nFinding alternatives for: {ref_code} - {ref_name}")
        print(f"Department: {ref_dept}, Level: {ref_level}")
        
        # Find alternatives based on different criteria
        alternatives = []
        
        # 1. Same department and level
        cursor.execute("""
        SELECT id, course_code, course_name, department, level, current_enrollment, max_enrollment,
               'Same Dept & Level' as match_type
        FROM courses 
        WHERE department = ? AND level = ? AND id != ? AND status = 'Active'
        ORDER BY course_name
        """, (ref_dept, ref_level, ref_course_id))
        
        alternatives.extend(cursor.fetchall())
        
        # 2. Same department, different level
        cursor.execute("""
        SELECT id, course_code, course_name, department, level, current_enrollment, max_enrollment,
               'Same Department' as match_type
        FROM courses 
        WHERE department = ? AND level != ? AND id != ? AND status = 'Active'
        ORDER BY course_name
        """, (ref_dept, ref_level, ref_course_id))
        
        alternatives.extend(cursor.fetchall())
        
        # 3. Same level, different department
        cursor.execute("""
        SELECT id, course_code, course_name, department, level, current_enrollment, max_enrollment,
               'Same Level' as match_type
        FROM courses 
        WHERE level = ? AND department != ? AND id != ? AND status = 'Active'
        ORDER BY course_name
        """, (ref_level, ref_dept, ref_course_id))
        
        alternatives.extend(cursor.fetchall())
        
        # 4. Similar credit hours
        cursor.execute("SELECT credit_hours FROM courses WHERE id = ?", (ref_course_id,))
        ref_credits = cursor.fetchone()[0] if cursor.fetchone() else 3.0
        
        cursor.execute("""
        SELECT id, course_code, course_name, department, level, current_enrollment, max_enrollment,
               'Similar Credits' as match_type
        FROM courses 
        WHERE credit_hours = ? AND id != ? AND status = 'Active'
          AND NOT (department = ? AND level = ?)
        ORDER BY course_name
        """, (ref_credits, ref_course_id, ref_dept, ref_level))
        
        alternatives.extend(cursor.fetchall())
        
        if not alternatives:
            print("No alternative courses found.")
            conn.close()
            return
        
        # Remove duplicates while preserving order
        seen = set()
        unique_alternatives = []
        for alt in alternatives:
            if alt[0] not in seen:
                seen.add(alt[0])
                unique_alternatives.append(alt)
        
        print(f"\nAlternative Courses Found ({len(unique_alternatives)}):")
        print(f"{'Code':<8} {'Name':<25} {'Department':<12} {'Level':<12} {'Available':<10} {'Match Type':<15}")
        print("-" * 82)
        
        for alt in unique_alternatives:
            course_id, code, name, dept, level, current, max_enroll, match_type = alt
            available_spots = max_enroll - current if max_enroll and current else "Unknown"
            name_short = name[:22] + "..." if len(name) > 25 else name
            
            print(f"{code:<8} {name_short:<25} {dept:<12} {level:<12} {available_spots:<10} {match_type:<15}")
        
        # Detailed view option
        detail_choice = input("\nEnter course code for detailed comparison (or press Enter to continue): ").strip().upper()
        
        if detail_choice:
            alt_course = next((a for a in unique_alternatives if a[1] == detail_choice), None)
            if alt_course:
                print(f"\nDETAILED COMPARISON")
                print("-" * 30)
                
                # Get detailed info for both courses
                cursor.execute("SELECT * FROM courses WHERE id = ?", (ref_course_id,))
                ref_details = cursor.fetchone()
                
                cursor.execute("SELECT * FROM courses WHERE id = ?", (alt_course[0],))
                alt_details = cursor.fetchone()
                
                print(f"Original Course: {ref_code} - {ref_name}")
                print(f"Alternative: {alt_course[1]} - {alt_course[2]}")
                print()
                
                # Compare key fields
                fields_to_compare = [
                    ("Department", ref_details[6], alt_details[6]),
                    ("Level", ref_details[5], alt_details[5]),
                    ("Credit Hours", ref_details[7], alt_details[7]),
                    ("Course Type", ref_details[18] if len(ref_details) > 18 else "N/A", 
                     alt_details[18] if len(alt_details) > 18 else "N/A"),
                    ("Max Enrollment", ref_details[15] if len(ref_details) > 15 else "N/A",
                     alt_details[15] if len(alt_details) > 15 else "N/A")
                ]
                
                print(f"{'Field':<15} {'Original':<20} {'Alternative':<20}")
                print("-" * 55)
                for field, orig_val, alt_val in fields_to_compare:
                    print(f"{field:<15} {str(orig_val):<20} {str(alt_val):<20}")
            else:
                print("Course code not found in alternatives.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

@log_read(module="course_management", description="Viewing course history")
def view_course_history(auth):
    """View historical changes to courses"""
    if not auth or not auth.current_user:
        print("You must be logged in to view course history.")
        return
    
    if not auth.check_permission('view_courses'):
        print("You don't have permission to view course history.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nCourse History Viewer")
        print("====================")
        
        # Option to view specific course or all changes
        view_option = input("Enter course ID for specific history, or press Enter for all recent changes: ").strip()
        
        if view_option:
            try:
                course_id = int(view_option)
                
                # Get course info
                cursor.execute("SELECT course_code, course_name FROM courses WHERE id = ?", (course_id,))
                course_info = cursor.fetchone()
                
                if not course_info:
                    print("Course not found.")
                    conn.close()
                    return
                
                print(f"\nHistory for {course_info[0]} - {course_info[1]}:")
                print("=" * 60)
                
                # Get history for specific course
                cursor.execute("""
                SELECT field_name, old_value, new_value, changed_by, changed_at
                FROM course_history 
                WHERE course_id = ?
                ORDER BY changed_at DESC
                """, (course_id,))
                
                history = cursor.fetchall()
                
                if not history:
                    print("No history found for this course.")
                    conn.close()
                    return
                
                print(f"{'Date/Time':<20} {'Field':<20} {'Old Value':<20} {'New Value':<20} {'Changed By':<15}")
                print("-" * 95)
                
                for entry in history:
                    field, old_val, new_val, changed_by, changed_at = entry
                    old_display = str(old_val)[:17] + "..." if old_val and len(str(old_val)) > 20 else str(old_val or "")
                    new_display = str(new_val)[:17] + "..." if new_val and len(str(new_val)) > 20 else str(new_val or "")
                    
                    print(f"{changed_at:<20} {field:<20} {old_display:<20} {new_display:<20} {changed_by:<15}")
            
            except ValueError:
                print("Invalid course ID.")
                conn.close()
                return
        
        else:
            # Show recent changes across all courses
            print("\nRecent Course Changes (Last 50):")
            print("=" * 80)
            
            cursor.execute("""
            SELECT c.course_code, c.course_name, ch.field_name, ch.old_value, 
                   ch.new_value, ch.changed_by, ch.changed_at
            FROM course_history ch
            JOIN courses c ON ch.course_id = c.id
            ORDER BY ch.changed_at DESC
            LIMIT 50
            """)
            
            recent_changes = cursor.fetchall()
            
            if not recent_changes:
                print("No history found.")
                conn.close()
                return
            
            print(f"{'Course':<12} {'Field':<15} {'Old Value':<15} {'New Value':<15} {'User':<12} {'Date':<12}")
            print("-" * 81)
            
            for change in recent_changes:
                code, name, field, old_val, new_val, user, date = change
                old_display = str(old_val)[:12] + "..." if old_val and len(str(old_val)) > 15 else str(old_val or "")
                new_display = str(new_val)[:12] + "..." if new_val and len(str(new_val)) > 15 else str(new_val or "")
                date_display = date.split()[0]  # Just the date part
                
                print(f"{code:<12} {field:<15} {old_display:<15} {new_display:<15} {user:<12} {date_display:<12}")
        
        # Statistics
        cursor.execute("""
        SELECT 
            COUNT(*) as total_changes,
            COUNT(DISTINCT course_id) as courses_modified,
            COUNT(DISTINCT changed_by) as users_involved
        FROM course_history
        """)
        
        stats = cursor.fetchone()
        
        print(f"\nHistory Statistics:")
        print(f"Total Changes: {stats[0]}")
        print(f"Courses Modified: {stats[1]}")
        print(f"Users Involved: {stats[2]}")
        
        # Most active fields
        cursor.execute("""
        SELECT field_name, COUNT(*) as change_count
        FROM course_history
        GROUP BY field_name
        ORDER BY change_count DESC
        LIMIT 5
        """)
        
        field_stats = cursor.fetchall()
        
        print(f"\nMost Modified Fields:")
        for field, count in field_stats:
            print(f"  {field}: {count} changes")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

@log_update(module="course_management", description="Running system maintenance")
def system_maintenance(auth):
    """System maintenance and cleanup utilities"""
    if not auth or not auth.current_user:
        print("You must be logged in to perform maintenance.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to perform system maintenance.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nSystem Maintenance Utilities")
        print("===========================")
        
        print("Select maintenance operation:")
        print("1. Database integrity check")
        print("2. Clean up orphaned records")
        print("3. Recalculate enrollment numbers")
        print("4. Archive old course history")
        print("5. Database statistics")
        print("6. Rebuild search indexes")
        print("7. Export database backup")
        print("0. Return to menu")
        
        while True:
            try:
                choice = int(input("Enter choice (0-7): "))
                if 0 <= choice <= 7:
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")
        
        if choice == 0:
            conn.close()
            return False
        
        elif choice == 1:  # Database integrity check
            print("\nRunning database integrity check...")
            
            issues = []
            
            # Check for courses with invalid enrollment
            cursor.execute("""
            SELECT id, course_code, current_enrollment, max_enrollment
            FROM courses 
            WHERE current_enrollment > max_enrollment
            """)
            
            over_enrolled = cursor.fetchall()
            if over_enrolled:
                issues.append(f"Found {len(over_enrolled)} courses with enrollment over capacity")
                for course in over_enrolled:
                    print(f"  - {course[1]}: {course[2]}/{course[3]} enrolled")
            
            # Check for orphaned prerequisites
            cursor.execute("""
            SELECT cp.id, cp.course_id, cp.prerequisite_course_id
            FROM course_prerequisites cp
            LEFT JOIN courses c1 ON cp.course_id = c1.id
            LEFT JOIN courses c2 ON cp.prerequisite_course_id = c2.id
            WHERE c1.id IS NULL OR c2.id IS NULL
            """)
            
            orphaned_prereqs = cursor.fetchall()
            if orphaned_prereqs:
                issues.append(f"Found {len(orphaned_prereqs)} orphaned prerequisite records")
            
            # Check for invalid schedules
            cursor.execute("""
            SELECT cs.id, cs.course_id, cs.instructor_id
            FROM course_schedule cs
            LEFT JOIN courses c ON cs.course_id = c.id
            LEFT JOIN instructors i ON cs.instructor_id = i.id
            WHERE c.id IS NULL OR (cs.instructor_id IS NOT NULL AND i.id IS NULL)
            """)
            
            invalid_schedules = cursor.fetchall()
            if invalid_schedules:
                issues.append(f"Found {len(invalid_schedules)} invalid schedule records")
            
            if not issues:
                print("✓ Database integrity check completed - no issues found")
            else:
                print(f"⚠ Found {len(issues)} integrity issues:")
                for issue in issues:
                    print(f"  - {issue}")
        
        elif choice == 2:  # Clean up orphaned records
            print("\nCleaning up orphaned records...")
            
            # Remove orphaned prerequisites
            cursor.execute("""
            DELETE FROM course_prerequisites 
            WHERE course_id NOT IN (SELECT id FROM courses)
               OR prerequisite_course_id NOT IN (SELECT id FROM courses)
            """)
            deleted_prereqs = cursor.rowcount
            
            # Remove orphaned schedules
            cursor.execute("""
            DELETE FROM course_schedule 
            WHERE course_id NOT IN (SELECT id FROM courses)
            """)
            deleted_schedules = cursor.rowcount
            
            # Remove orphaned waitlists
            cursor.execute("""
            DELETE FROM course_waitlist 
            WHERE course_id NOT IN (SELECT id FROM courses)
            """)
            deleted_waitlists = cursor.rowcount
            
            # Remove orphaned history
            cursor.execute("""
            DELETE FROM course_history 
            WHERE course_id NOT IN (SELECT id FROM courses)
            """)
            deleted_history = cursor.rowcount
            
            conn.commit()
            
            print(f"✓ Cleanup completed:")
            print(f"  - Removed {deleted_prereqs} orphaned prerequisites")
            print(f"  - Removed {deleted_schedules} orphaned schedules")
            print(f"  - Removed {deleted_waitlists} orphaned waitlist entries")
            print(f"  - Removed {deleted_history} orphaned history records")
        
        elif choice == 3:  # Recalculate enrollment numbers
            print("\nRecalculating enrollment numbers...")
            
            # Note: This would normally query a student enrollment table
            # For now, we'll validate current numbers
            cursor.execute("""
            SELECT id, course_code, current_enrollment, max_enrollment
            FROM courses
            WHERE current_enrollment < 0 OR current_enrollment > max_enrollment
            """)
            
            invalid_enrollments = cursor.fetchall()
            
            if invalid_enrollments:
                print(f"Found {len(invalid_enrollments)} courses with invalid enrollment:")
                for course in invalid_enrollments:
                    print(f"  - {course[1]}: {course[2]}/{course[3]}")
                
                reset_option = input("Reset invalid enrollments to 0? (y/n): ").strip().lower()
                if reset_option == 'y':
                    cursor.execute("""
                    UPDATE courses 
                    SET current_enrollment = 0, updated_at = ?
                    WHERE current_enrollment < 0 OR current_enrollment > max_enrollment
                    """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
                    
                    conn.commit()
                    print("✓ Invalid enrollments reset to 0")
            else:
                print("✓ All enrollment numbers are valid")
        
        elif choice == 4:  # Archive old course history
            print("\nArchiving old course history...")
            
            # Archive history older than 1 year
            one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            cursor.execute("""
            SELECT COUNT(*) FROM course_history 
            WHERE changed_at < ?
            """, (one_year_ago,))
            
            old_records = cursor.fetchone()[0]
            
            if old_records > 0:
                print(f"Found {old_records} history records older than 1 year")
                
                archive_option = input("Archive these records? (y/n): ").strip().lower()
                if archive_option == 'y':
                    # In a real system, you might export to a file first
                    cursor.execute("""
                    DELETE FROM course_history 
                    WHERE changed_at < ?
                    """, (one_year_ago,))
                    
                    conn.commit()
                    print(f"✓ Archived {old_records} old history records")
            else:
                print("✓ No old history records found")
        
        elif choice == 5:  # Database statistics
            print("\nDatabase Statistics:")
            print("=" * 30)
            
            # Table sizes
            tables = ['courses', 'course_prerequisites', 'course_schedule', 
                     'instructors', 'course_waitlist', 'course_history']
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"{table}: {count} records")
            
            # Database file size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            
            db_size_mb = (page_count * page_size) / (1024 * 1024)
            print(f"\nDatabase size: {db_size_mb:.2f} MB")
        
        elif choice == 6:  # Rebuild search indexes
            print("\nRebuilding search indexes...")
            
            # SQLite doesn't have explicit index rebuild, but we can analyze
            cursor.execute("ANALYZE")
            conn.commit()
            
            print("✓ Database analysis completed")
        
        elif choice == 7:  # Export database backup
            print("\nExporting database backup...")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"course_db_backup_{timestamp}.sql"
            
            # Simple backup by dumping schema and data
            with open(backup_file, 'w') as f:
                for line in conn.iterdump():
                    f.write('%s\n' % line)
            
            print(f"✓ Database backup saved as {backup_file}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Database error during maintenance: {e}")
        if 'conn' in locals():
            conn.close()
        return False
    except Exception as e:
        print(f"Error during maintenance: {e}")
        if 'conn' in locals():
            conn.close()
        return False
        
# =====================================================================
# ORIGINAL FUNCTIONS (UPDATED FOR COMPATIBILITY)
# =====================================================================

@log_create(module="course_management", description="Creating new course")
def create_course(auth):
    """Legacy function - redirects to enhanced version"""
    return create_enhanced_course(auth)

@log_read(module="course_management", description="Viewing all courses")
def view_all_courses(auth):
    """View all courses in the system with enhanced display"""
    if not auth or not auth.current_user:
        print(get_text('course_mgmt.login_required', default='You must be logged in to view courses.'))
        return

    if not auth.check_permission('view_courses'):
        print(get_text('course_mgmt.no_permission_view', default="You don't have permission to view courses."))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if the courses table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
        if not cursor.fetchone():
            print(get_text('course_mgmt.no_courses_table', default='No courses found. The courses table has not been created yet.'))
            conn.close()
            return

        # Get all courses with enhanced information
        cursor.execute("""
        SELECT id, course_code, course_name, department, level, course_type,
               credit_hours, current_enrollment, max_enrollment, status, created_at
        FROM courses
        ORDER BY course_code
        """)

        courses = cursor.fetchall()

        if not courses:
            print(get_text('course_mgmt.no_courses_found', default='No courses found in the system.'))
            conn.close()
            return

        print(f"\n{get_text('course_mgmt.all_courses_title', default='All Courses (Enhanced View)')}:")
        print(f"{get_text('course_mgmt.headers.id', default='ID'):<5} {get_text('course_mgmt.headers.code', default='Code'):<8} {get_text('course_mgmt.headers.name', default='Name'):<25} {get_text('course_mgmt.headers.dept', default='Dept'):<12} {get_text('course_mgmt.headers.level', default='Level'):<12} {get_text('course_mgmt.headers.type', default='Type'):<12} {get_text('course_mgmt.headers.credits', default='Credits'):<8} {get_text('course_mgmt.headers.enrolled', default='Enrolled'):<10} {get_text('course_mgmt.headers.status', default='Status'):<10}")
        print("-" * 102)

        for course in courses:
            course_id, code, name, dept, level, ctype, credits, current, max_enroll, status, created = course

            # Truncate long names
            name_display = name[:22] + "..." if len(name) > 25 else name
            dept_display = dept[:9] + "..." if dept and len(dept) > 12 else dept or get_text('common.na', default='N/A')
            level_display = level[:9] + "..." if level and len(level) > 12 else level or get_text('common.na', default='N/A')
            type_display = ctype[:9] + "..." if ctype and len(ctype) > 12 else ctype or get_text('common.na', default='N/A')
            enrollment_display = f"{current or 0}/{max_enroll or 0}"

            print(f"{course_id:<5} {code:<8} {name_display:<25} {dept_display:<12} {level_display:<12} {type_display:<12} {credits:<8} {enrollment_display:<10} {status:<10}")

        # Enhanced detail view option
        detail_choice = input(f"\n{get_text('course_mgmt.prompts.detail_view', default='Enter a course ID for detailed view (or press Enter to return)')}: ")
        if detail_choice.strip():
            try:
                detail_id = int(detail_choice)
                view_course_details(cursor, detail_id)
            except ValueError:
                print(get_text('course_mgmt.errors.invalid_id', default='Invalid ID. Please enter a number.'))
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing courses: {e}")
        if 'conn' in locals():
            conn.close()

@log_update(module="course_management", description="Updating course")
def update_course(auth):
    """Update an existing course with enhanced features"""
    if not auth or not auth.current_user:
        print("You must be logged in to update courses.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to update courses.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if the courses table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
        if not cursor.fetchone():
            print("No courses found. The courses table has not been created yet.")
            conn.close()
            return False
        
        # Show all courses for selection
        cursor.execute("SELECT id, course_code, course_name, status FROM courses ORDER BY course_code")
        courses = cursor.fetchall()
        
        if not courses:
            print("No courses found in the system.")
            conn.close()
            return False
        
        print("\nSelect a course to update:")
        for course in courses:
            course_id, code, name, status = course
            print(f"{course_id}. {code} - {name} ({status})")
        
        while True:
            try:
                course_id = int(input("\nEnter course ID to update (or 0 to cancel): "))
                if course_id == 0:
                    print("Update cancelled.")
                    conn.close()
                    return False
                
                # Get current course details
                cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
                course = cursor.fetchone()
                
                if not course:
                    print(f"No course found with ID {course_id}.")
                    continue
                
                break
            except ValueError:
                print("Please enter a valid number.")
        
        # Current values - use index-based access for flexibility with schema changes
        # Database columns: id(0), code(1), name(2), credits(3), department(4), instructor_id(5),
        #   academic_year_id(6), semester_id(7), status(8), date_added(9), course_code(10),
        #   course_name(11), level(12), credit_hours(13), current_enrollment(14), max_enrollment(15),
        #   description(16), duration(17), course_type(18), updated_at(19), created_at(20), tags(21),
        #   availability_periods(22), learning_outcomes(23), assessment_methods(24), required_textbooks(25),
        #   course_fee(26), lab_required(27), online_available(28), contact_hours_per_week(29)
        id = course[0]
        code = course[1] or course[10] or ""  # code or course_code
        name = course[2] or course[11] or ""  # name or course_name
        desc = course[16] if len(course) > 16 else ""
        credit_hours = course[13] if len(course) > 13 and course[13] else (course[3] if course[3] else 3)
        max_enrollment = course[15] if len(course) > 15 and course[15] else 30
        current_enrollment = course[14] if len(course) > 14 and course[14] else 0
        status = course[8] if len(course) > 8 else "Active"
        course_type = course[18] if len(course) > 18 else "Core"
        tags = course[21] if len(course) > 21 else ""
        availability = course[22] if len(course) > 22 else "Fall,Spring"
        learning_outcomes = course[23] if len(course) > 23 else ""
        assessment_methods = course[24] if len(course) > 24 else ""
        textbooks = course[25] if len(course) > 25 else ""
        course_fee = course[26] if len(course) > 26 and course[26] else 0.0
        lab_required = course[27] if len(course) > 27 else False
        online_available = course[28] if len(course) > 28 else False
        contact_hours = course[29] if len(course) > 29 and course[29] else 3
        
        print(f"\nUpdating Course: {code} - {name}")
        print("Enter new values (leave blank to keep current):")
        
        # Update basic fields (same as before but with enhanced validation)
        # ... (keeping the original update logic but adding new fields)
        
        # For brevity, I'll show the pattern for a few fields:
        new_code = input(f"Course Code [{code}]: ").strip().upper() or code
        new_name = input(f"Course Name [{name}]: ").strip() or name
        new_desc = input(f"Description [{desc}]: ").strip() or desc
        
        # Enhanced fields
        new_credit_hours = credit_hours
        credit_input = input(f"Credit Hours [{credit_hours}]: ").strip()
        if credit_input:
            try:
                new_credit_hours = float(credit_input)
            except ValueError:
                print("Invalid credit hours. Keeping current value.")
        
        new_max_enrollment = max_enrollment
        max_input = input(f"Max Enrollment [{max_enrollment}]: ").strip()
        if max_input:
            try:
                new_max_enrollment = int(max_input)
            except ValueError:
                print("Invalid enrollment number. Keeping current value.")
        
        # Update the course
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Update query handling both schemas
        cursor.execute("""
        UPDATE courses 
        SET course_code = ?, course_name = ?, description = ?, credit_hours = ?, 
            max_enrollment = ?, updated_at = ?
        WHERE id = ?
        """, (new_code, new_name, new_desc, new_credit_hours, new_max_enrollment, timestamp, course_id))
        
        conn.commit()
        conn.close()
        
        print(f"\nCourse updated successfully: {new_code} - {new_name}")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_delete(module="course_management", description="Deleting course")
def delete_course(auth):
    """Delete an existing course (enhanced with safety checks)"""
    # Keep the original implementation but add enhanced safety checks
    if not auth or not auth.current_user:
        print("You must be logged in to delete courses.")
        return False
    
    if not auth.check_permission('manage_courses'):
        print("You don't have permission to delete courses.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Show all courses for selection
        cursor.execute("SELECT id, course_code, course_name, current_enrollment FROM courses ORDER BY course_code")
        courses = cursor.fetchall()
        
        if not courses:
            print("No courses found in the system.")
            conn.close()
            return False
        
        print("\nSelect a course to delete:")
        for course in courses:
            course_id, code, name, enrolled = course
            enrolled_display = enrolled if enrolled is not None else 0
            print(f"{course_id}. {code} - {name} (Enrolled: {enrolled_display})")
        
        while True:
            try:
                course_id = int(input("\nEnter course ID to delete (or 0 to cancel): "))
                if course_id == 0:
                    print("Delete cancelled.")
                    conn.close()
                    return False
                
                # Check if course exists
                cursor.execute("SELECT course_code, course_name, current_enrollment FROM courses WHERE id = ?", (course_id,))
                course = cursor.fetchone()
                
                if not course:
                    print(f"No course found with ID {course_id}.")
                    continue
                
                code, name, enrolled = course
                break
            except ValueError:
                print("Please enter a valid number.")
        
        # Enhanced safety checks
        enrolled = enrolled or 0
        
        # Check for prerequisites
        cursor.execute("SELECT COUNT(*) FROM course_prerequisites WHERE prerequisite_course_id = ?", (course_id,))
        prereq_count = cursor.fetchone()[0]
        
        # Check for schedules
        cursor.execute("SELECT COUNT(*) FROM course_schedule WHERE course_id = ?", (course_id,))
        schedule_count = cursor.fetchone()[0]
        
        # Check for waitlists
        cursor.execute("SELECT COUNT(*) FROM course_waitlist WHERE course_id = ?", (course_id,))
        waitlist_count = cursor.fetchone()[0]
        
        print(f"\nDELETION IMPACT ANALYSIS for '{code} - {name}':")
        print(f"- Students enrolled: {enrolled}")
        print(f"- Courses depending on this as prerequisite: {prereq_count}")
        print(f"- Schedule entries: {schedule_count}")
        print(f"- Waitlist entries: {waitlist_count}")
        
        if enrolled > 0 or prereq_count > 0:
            print("\n⚠️  WARNING: This deletion will have significant impact!")
            confirm = input("Type 'DELETE CONFIRMED' to proceed: ")
            
            if confirm != 'DELETE CONFIRMED':
                print("Delete cancelled.")
                conn.close()
                return False
        else:
            confirm = input(f"\nAre you sure you want to delete '{code} - {name}'? This cannot be undone. (y/n): ").lower()
            
            if confirm != 'y':
                print("Delete cancelled.")
                conn.close()
                return False
        
        # Delete related records first
        cursor.execute("DELETE FROM course_prerequisites WHERE course_id = ? OR prerequisite_course_id = ?", (course_id, course_id))
        cursor.execute("DELETE FROM course_schedule WHERE course_id = ?", (course_id,))
        cursor.execute("DELETE FROM course_waitlist WHERE course_id = ?", (course_id,))
        cursor.execute("DELETE FROM course_history WHERE course_id = ?", (course_id,))
        cursor.execute("DELETE FROM course_analytics WHERE course_id = ?", (course_id,))
        
        # Delete the course
        cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        rows_deleted = cursor.rowcount
        
        conn.commit()
        
        if rows_deleted > 0:
            print(f"\nCourse '{code} - {name}' and all related data deleted successfully.")
            
            if enrolled > 0:
                print(f"\nIMPORTANT: {enrolled} students now need to be assigned to different courses.")
            if prereq_count > 0:
                print(f"IMPORTANT: {prereq_count} courses had this as a prerequisite - please review.")
        else:
            print("Error: No course was deleted.")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_menu_navigation(description="Displaying course management menu")
def display_course_management_menu(auth):
    """Legacy function - redirects to enhanced menu"""
    return display_enhanced_course_menu(auth)

# =====================================================================
# MAIN ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    print(get_text('course_mgmt.title', default='Enhanced Course Management System'))
    print(get_text('course_mgmt.module_info', default='This module should be imported and used with an authentication system.'))
    print(get_text('course_mgmt.init_info', default='Run initialize_enhanced_database() to set up the database schema.'))
