# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
import os
from pathlib import Path
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.shared.constants import paths

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this GUI. Many database calls within this
# module reference 'courses.db' or str(DEFAULT_DB_PATH) directly. Without
# overriding, these calls would create separate database files in the
# working directory, leading to inconsistencies and missing tables. By
# redirecting those names to the central student_records.db located in
# university_system/data/db_files, we ensure a single database file is
# used across the entire application. Only connections specifying no
# database or targeting courses.db/student_records.db are redirected;
# all other database paths are left untouched.

_original_sqlite_connect = sqlite3.connect

def _patched_sqlite_connect(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "courses.db"):
            return _original_sqlite_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect
import re
import csv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading
import os
import logging

# Import chart generation utility
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import seaborn as sns
    import numpy as np
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    plt = None
    Figure = None
    FigureCanvasTkAgg = None
    sns = None
    np = None

# Import email service
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from university_system.modules.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from university_system.modules.domain.academics.services.course_management import (
        add_prerequisite, create_course, create_enhanced_course,
        display_enhanced_course_menu, find_alternative_courses,
        generate_course_analytics, generate_enrollment_report,
        initialize_enhanced_database, remove_prerequisite, search_courses,
        update_course, update_schedule, view_all_courses, view_course_details
    )
    ORIGINAL_MODULE_AVAILABLE = True
except ImportError:
    ORIGINAL_MODULE_AVAILABLE = False
    print("Warning: Original course_management module not found. Some features may be limited.")

# Import academic system launchers
try:
    from university_system.modules.domain.academics.services.lms.lms_core import launch_lms_gui
    from university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(f"Warning: Academic systems not fully available: {e}")

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================

class CourseManagementGUI:
    def __init__(self, parent, auth_system=None):
        self.root = parent
        self.root.title("Enhanced Course Management System")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # Initialize authentication - accept passed auth or create new instance
        if auth_system:
            self.auth = auth_system
        else:
            self.auth = UserAuth()

        # Create status bar FIRST so update_status() is safe during init
        self.status_var = tk.StringVar(value="Initializing…")
        self.status_label = ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief="sunken")
        self.status_label.pack(side="bottom", fill="x")

        # Now it's safe to touch the DB and call update_status()
        self.init_database()

        # Build the rest of the UI
        self.create_menu()
        self.create_main_interface()
    
    def update_status(self, message, error=False):
        # Defensive: if someone calls this very early, ensure widgets exist
        if not hasattr(self, "status_var"):
            self.status_var = tk.StringVar(value="")
            self.status_label = ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief="sunken")
            self.status_label.pack(side="bottom", fill="x")

        self.status_var.set(message)
        try:
            self.status_label.configure(foreground=("red" if error else "black"))
        except Exception:
            pass
        self.root.update_idletasks()

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            # Check if auth has current_user attribute and it's not None
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                user = self.auth.current_user
                # Handle both dict and object formats
                if isinstance(user, dict):
                    role = user.get('role', None)
                    if role:
                        return role.lower()
                elif hasattr(user, 'role'):
                    return user.role.lower()
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff/instructor"""
        role = self.get_user_role()
        return role in ['staff', 'instructor']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'


    def init_database(self):
        """Initialize the database schema - FIXED: Better error handling"""
        try:
            # Try original module first if available
            if ORIGINAL_MODULE_AVAILABLE:
                try:
                    initialize_enhanced_database()
                    self.update_status("Database initialized successfully")
                    return
                except (NameError, AttributeError):
                    # Function doesn't exist, fall back to our implementation
                    pass
            
            # Use our fallback implementation
            self.init_fallback_database()
            
        except Exception as e:
            # Don't crash the app, just show an error and continue
            print(f"Database initialization error: {e}")
            try:
                self.init_fallback_database()
            except Exception as e2:
                print(f"Fallback initialization also failed: {e2}")
                # Create minimal database as last resort
                self.create_minimal_database()
                
    def init_fallback_database(self):
        """FIXED: Comprehensive database initialization"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Create the main courses table with all required columns
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT UNIQUE NOT NULL,
                    course_name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    duration INTEGER DEFAULT 15,
                    level TEXT DEFAULT 'Undergraduate',
                    department TEXT DEFAULT '',
                    credit_hours REAL DEFAULT 3.0,
                    contact_hours_per_week INTEGER DEFAULT 3,
                    learning_outcomes TEXT DEFAULT '',
                    assessment_methods TEXT DEFAULT '',
                    required_textbooks TEXT DEFAULT '',
                    course_fee REAL DEFAULT 0.0,
                    lab_required BOOLEAN DEFAULT 0,
                    online_available BOOLEAN DEFAULT 0,
                    max_enrollment INTEGER DEFAULT 30,
                    current_enrollment INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'Active',
                    course_type TEXT DEFAULT 'Core',
                    tags TEXT DEFAULT '',
                    availability_periods TEXT DEFAULT 'Fall,Spring',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                ''')

                # ------------------------------------------------------------------
                # Legacy column support for interoperability
                #
                # Some parts of the application (e.g. academic_calendar) still
                # query the courses table using legacy column names like 'code',
                # 'name' and 'credits'.  Ensure these columns exist and mirror
                # our canonical values.  This avoids errors when those modules
                # run against a database created by the GUI alone.
                cursor.execute("PRAGMA table_info(courses)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                if 'code' not in existing_cols:
                    cursor.execute("ALTER TABLE courses ADD COLUMN code TEXT")
                if 'name' not in existing_cols:
                    cursor.execute("ALTER TABLE courses ADD COLUMN name TEXT")
                if 'credits' not in existing_cols:
                    cursor.execute("ALTER TABLE courses ADD COLUMN credits REAL")
                # Add optional columns used by academic calendar module
                if 'instructor_id' not in existing_cols:
                    cursor.execute("ALTER TABLE courses ADD COLUMN instructor_id INTEGER")
                if 'academic_year_id' not in existing_cols:
                    cursor.execute("ALTER TABLE courses ADD COLUMN academic_year_id TEXT")
                if 'semester_id' not in existing_cols:
                    cursor.execute("ALTER TABLE courses ADD COLUMN semester_id TEXT")
                if 'date_added' not in existing_cols:
                    cursor.execute("ALTER TABLE courses ADD COLUMN date_added TEXT")
                # Synchronise the alias columns for any preexisting rows
                cursor.execute(
                    "UPDATE courses SET code = course_code WHERE code IS NULL OR code = ''"
                )
                cursor.execute(
                    "UPDATE courses SET name = course_name WHERE name IS NULL OR name = ''"
                )
                cursor.execute(
                    "UPDATE courses SET credits = credit_hours WHERE credits IS NULL OR credits = ''"
                )

                # Create supporting tables
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS instructors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    department TEXT DEFAULT '',
                    specialization TEXT DEFAULT '',
                    max_courses_per_semester INTEGER DEFAULT 4,
                    max_hours_per_week INTEGER DEFAULT 40,
                    preferred_days TEXT,
                    preferred_times TEXT,
                    status TEXT DEFAULT 'Active',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_prerequisites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    prerequisite_course_id INTEGER NOT NULL,
                    is_required BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    FOREIGN KEY (prerequisite_course_id) REFERENCES courses (id),
                    UNIQUE(course_id, prerequisite_course_id)
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    semester TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    start_time TEXT DEFAULT '',
                    end_time TEXT DEFAULT '',
                    days_of_week TEXT DEFAULT '',
                    classroom TEXT DEFAULT '',
                    instructor_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    FOREIGN KEY (instructor_id) REFERENCES instructors (id),
                    UNIQUE(course_id, semester, year)
                )
                ''')

                # ------------------------------------------------------------------
                # Additional tables for the enhanced system
                # These tables mirror the structures defined in the CLI version
                # of the course management system. Including them here ensures
                # that when the GUI runs independently of the CLI, it still
                # creates a fully functional schema.

                # Course history table to record changes to course records
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

                # Course categories table for tagging and grouping courses
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    color_code TEXT,
                    created_at TEXT NOT NULL
                )
                ''')

                # Course analytics table for tracking enrollment and completion stats
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

                # Database tables created - ready to use existing data
                cursor.execute("SELECT COUNT(*) FROM courses")
                course_count = cursor.fetchone()[0]

                conn.commit()

                # Run database migrations after table creation
                self._migrate_database(cursor, conn)

                self.update_status(f"Database initialized successfully with {course_count} existing courses")

        except Exception as e:
            raise Exception(f"Database initialization failed: {e}")

    def create_minimal_database(self):
        """Last resort: create minimal database structure"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT UNIQUE NOT NULL,
                    course_name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    duration INTEGER DEFAULT 15,
                    level TEXT DEFAULT 'Undergraduate',
                    department TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                ''')

                conn.commit()
            self.update_status("Minimal database created", error=True)
            
        except Exception as e:
            self.update_status(f"Critical: Database creation failed: {e}", error=True)
            # App will still run but with limited functionality

    def insert_sample_data(self, cursor):
        """Insert sample course data"""
        sample_courses = [
            ('CS101', 'Introduction to Programming', 'Basic programming concepts and practices', 15, 'Undergraduate', 'Computer Science', 3.0, 3, '', '', '', 0.0, 0, 0, 30, 0, 'Active', 'Core', '', 'Fall,Spring'),
            ('MATH201', 'Calculus I', 'Differential and integral calculus', 15, 'Undergraduate', 'Mathematics', 4.0, 4, '', '', '', 0.0, 0, 0, 25, 0, 'Active', 'Core', '', 'Fall,Spring'),
            ('ENG102', 'English Composition', 'Academic writing and communication skills', 15, 'Undergraduate', 'English', 3.0, 3, '', '', '', 0.0, 0, 1, 20, 0, 'Active', 'General Education', '', 'Fall,Spring,Summer'),
            ('HIST150', 'World History', 'Survey of world civilizations', 15, 'Undergraduate', 'History', 3.0, 3, '', '', '', 0.0, 0, 1, 35, 0, 'Active', 'General Education', '', 'Fall,Spring'),
            ('BIO101', 'General Biology', 'Introduction to biological sciences with lab', 15, 'Undergraduate', 'Biology', 4.0, 6, '', '', '', 50.0, 1, 0, 28, 0, 'Active', 'Core', 'science,lab', 'Fall,Spring')
        ]
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for course_data in sample_courses:
            cursor.execute('''
            INSERT INTO courses (
                course_code, course_name, description, duration, level, department,
                credit_hours, contact_hours_per_week, learning_outcomes, assessment_methods,
                required_textbooks, course_fee, lab_required, online_available,
                max_enrollment, current_enrollment, status, course_type, tags,
                availability_periods, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', course_data + (timestamp, timestamp))
            # After inserting each sample course, update the legacy alias
            # columns.  We cannot include these columns in the INSERT
            # statement because the table may or may not contain them.
            try:
                # Retrieve last inserted row ID
                last_id = cursor.lastrowid
                # Mirror canonical values into aliases
                cursor.execute(
                    "UPDATE courses SET code = course_code, name = course_name, credits = credit_hours, date_added = COALESCE(date_added, created_at) WHERE id = ?",
                    (last_id,),
                )
            except Exception:
                # Ignore if alias columns are absent
                pass

    def _migrate_database(self, cursor, conn):
        """Migrate existing database tables to add missing columns"""
        try:
            # Check and add missing columns to instructors table
            cursor.execute("PRAGMA table_info(instructors)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            migrations = []
            if 'max_hours_per_week' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN max_hours_per_week INTEGER DEFAULT 40")
            if 'preferred_days' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN preferred_days TEXT")
            if 'preferred_times' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN preferred_times TEXT")
            if 'is_active' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN is_active BOOLEAN DEFAULT 1")

            # Check if rooms table exists and add is_active column
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(rooms)")
                existing_columns = {row[1] for row in cursor.fetchall()}
                if 'is_active' not in existing_columns:
                    migrations.append("ALTER TABLE rooms ADD COLUMN is_active BOOLEAN DEFAULT 1")

            # Execute all migrations
            for migration in migrations:
                try:
                    cursor.execute(migration)
                    print(f"Migration executed: {migration}")
                except sqlite3.Error as e:
                    print(f"Migration failed: {migration} - {e}")

            conn.commit()

        except Exception as e:
            print(f"Migration error: {e}")

    def refresh_course_list(self):
        """FIXED: Enhanced error handling for course list refresh"""
        try:
            # Clear existing items
            for item in self.course_tree.get_children():
                self.course_tree.delete(item)
            
            # Get courses from database
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Check if courses table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
                if not cursor.fetchone():
                    self.update_status("Courses table not found - please check database initialization", error=True)
                    return

                # Get table schema to handle missing columns gracefully
                cursor.execute("PRAGMA table_info(courses)")
                columns = {row[1]: row[2] for row in cursor.fetchall()}

                # Build query based on available columns - use ROW_NUMBER for sequential ID
                base_fields = "ROW_NUMBER() OVER (ORDER BY course_code) as id, course_code, course_name"
                extra_fields = []

                if 'department' in columns:
                    extra_fields.append("COALESCE(department, 'N/A') as department")
                else:
                    extra_fields.append("'N/A' as department")

                if 'level' in columns:
                    extra_fields.append("COALESCE(level, 'N/A') as level")
                else:
                    extra_fields.append("'N/A' as level")

                if 'credit_hours' in columns:
                    extra_fields.append("COALESCE(credit_hours, 3.0) as credit_hours")
                else:
                    extra_fields.append("3.0 as credit_hours")

                if 'current_enrollment' in columns and 'max_enrollment' in columns:
                    extra_fields.append("COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment")
                else:
                    extra_fields.append("'0/30' as enrollment")

                if 'status' in columns:
                    extra_fields.append("COALESCE(status, 'Active') as status")
                else:
                    extra_fields.append("'Active' as status")

                query = f"SELECT {base_fields}, {', '.join(extra_fields)} FROM courses ORDER BY course_code"

                cursor.execute(query)
                courses = cursor.fetchall()

                # Populate treeview
                for course in courses:
                    self.course_tree.insert("", tk.END, values=course)

                self.update_status(f"Loaded {len(courses)} courses")
            
        except sqlite3.Error as e:
            self.update_status(f"Database error: {e}", error=True)
            print(f"Database error in refresh_course_list: {e}")
        except Exception as e:
            self.update_status(f"Error loading courses: {e}", error=True)
            print(f"Error in refresh_course_list: {e}")
    
    # Add decorator for safe database operations
    def safe_db_operation(func):
        """Decorator to safely handle database operations"""
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except sqlite3.Error as e:
                error_msg = f"Database error in {func.__name__}: {e}"
                self.update_status(error_msg, error=True)
                messagebox.showerror("Database Error", error_msg)
                return None
            except Exception as e:
                error_msg = f"Error in {func.__name__}: {e}"
                self.update_status(error_msg, error=True)
                messagebox.showerror("Error", error_msg)
                return None
        return wrapper
    
    def create_menu(self):
        """Create the main menu bar with role-based access"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)

        # Admin and Staff can import/export
        if is_admin or is_staff:
            file_menu.add_command(label="Import CSV", command=self.show_import_csv)
            file_menu.add_command(label="Export CSV", command=self.show_export_csv)
            file_menu.add_separator()

        # Admin only - Database backup
        if is_admin:
            file_menu.add_command(label="Database Backup", command=self.backup_database)
            file_menu.add_separator()

        file_menu.add_command(label="Exit", command=self.root.quit)

        # Course menu
        course_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Courses", menu=course_menu)

        # Admin and Staff can create courses
        if is_admin or is_staff:
            course_menu.add_command(label="Create Course", command=self.show_create_course)

        # Everyone can view and search
        course_menu.add_command(label="View All Courses", command=self.refresh_course_list)
        course_menu.add_command(label="Search Courses", command=self.show_search_dialog)

        # Admin and Staff can manage prerequisites
        if is_admin or is_staff:
            course_menu.add_separator()
            course_menu.add_command(label="Manage Prerequisites", command=self.show_prerequisites_window)
            course_menu.add_command(label="Remove prerequisite", command=self.show_remove_prerequisite)

        # Everyone can find alternatives
        course_menu.add_command(label="Find Alternatives", command=self.find_alternative_courses)

        # Admin and Staff can manage status
        if is_admin or is_staff:
            course_menu.add_command(label="Manage Status", command=self.show_manage_status)

        # Scheduling menu - Admin and Staff only
        if is_admin or is_staff:
            schedule_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Scheduling", menu=schedule_menu)
            schedule_menu.add_command(label="Create Schedule", command=self.show_create_schedule)
            schedule_menu.add_command(label="Update Schedule", command=self.show_update_schedule)
            schedule_menu.add_command(label="View Schedules", command=self.show_view_schedules)
        elif is_student:
            # Students can only view schedules
            schedule_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Scheduling", menu=schedule_menu)
            schedule_menu.add_command(label="View Schedules", command=self.show_view_schedules)

        # Enrollment menu - Admin and Staff only
        if is_admin or is_staff:
            enrollment_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Enrollment", menu=enrollment_menu)
            enrollment_menu.add_command(label="Manage Waitlists", command=self.show_add_waitlist)
            enrollment_menu.add_command(label="Process Waitlists", command=self.show_process_waitlist)
            enrollment_menu.add_command(label="View Waitlists", command=self.show_view_waitlists)
        elif is_student:
            # Students can only view waitlists
            enrollment_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Enrollment", menu=enrollment_menu)
            enrollment_menu.add_command(label="View Waitlists", command=self.show_view_waitlists)

        # Analytics menu
        analytics_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Analytics", menu=analytics_menu)

        # Admin and Staff get full analytics
        if is_admin or is_staff:
            analytics_menu.add_command(label="Course Analytics", command=self.show_analytics)
            analytics_menu.add_command(label="Enrollment Report", command=self.show_enrollment_report)
            analytics_menu.add_command(label="Department Statistics", command=self.show_department_stats)
            analytics_menu.add_command(label="Course History", command=self.show_course_history)
            analytics_menu.add_command(label="Detailed Analytics", command=self.show_course_analytics_detailed)
        elif is_student:
            # Students get limited analytics
            analytics_menu.add_command(label="Course Analytics", command=self.show_analytics)
            analytics_menu.add_command(label="Course History", command=self.show_course_history)

        # Tools menu - Admin and Staff only
        if is_admin or is_staff:
            tools_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Tools", menu=tools_menu)

            # Admin only - bulk operations
            if is_admin:
                tools_menu.add_command(label="Bulk Update", command=self.show_bulk_update)
                tools_menu.add_command(label="System Maintenance", command=self.show_system_maintenance)

            tools_menu.add_command(label="Course Recommendations", command=self.show_recommend_courses)
            tools_menu.add_separator()
            tools_menu.add_command(label="Advanced Search", command=self.show_advanced_search)

            # Admin only - data validation
            if is_admin:
                tools_menu.add_command(label="Data Validation", command=self.show_data_validation)

        # Help menu - available to everyone
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="User Guide", command=self.show_help)
        
    def create_main_interface(self):
        """Create the main interface with tabs"""
        # Create toolbar frame at the top
        toolbar_frame = ttk.Frame(self.root)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        # Return to Main Menu button
        home_button = ttk.Button(toolbar_frame, text="🏠 Return to Main Menu",
                                command=self.return_to_main_menu)
        home_button.pack(side=tk.LEFT, padx=5)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Course List Tab
        self.create_course_list_tab()
        
        # Course Details Tab
        self.create_course_details_tab()
        
        # Analytics Tab
        self.create_analytics_tab()
        
        # Instructors Tab
        self.create_instructors_tab()

        # Academic Systems Tab
        self.create_academic_systems_tab()
    
    def create_course_list_tab(self):
        """Create the course list tab"""
        course_frame = ttk.Frame(self.notebook)
        self.notebook.add(course_frame, text="Course List")
        
        # Search and filter frame
        search_frame = ttk.LabelFrame(course_frame, text="Search & Filter", padding=10)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Search controls
        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, sticky=tk.W)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.grid(row=0, column=1, padx=5)
        self.search_entry.bind('<KeyRelease>', self.on_search_change)
        
        ttk.Label(search_frame, text="Department:").grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        self.dept_filter = ttk.Combobox(search_frame, width=15)
        self.dept_filter.grid(row=0, column=3, padx=5)
        self.dept_filter.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        ttk.Label(search_frame, text="Status:").grid(row=0, column=4, sticky=tk.W, padx=(20,0))
        self.status_filter = ttk.Combobox(search_frame, values=["All", "Active", "Inactive", "Archived", "Cancelled"], width=10)
        self.status_filter.set("All")
        self.status_filter.grid(row=0, column=5, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        # Course list with treeview
        list_frame = ttk.Frame(course_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview with scrollbar
        columns = ("ID", "Code", "Name", "Department", "Level", "Credits", "Enrollment", "Status")
        self.course_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
        
        # Configure column headings and widths
        for col in columns:
            self.course_tree.heading(col, text=col, command=lambda c=col: self.sort_treeview(c))
            if col == "ID":
                self.course_tree.column(col, width=50)
            elif col == "Code":
                self.course_tree.column(col, width=80)
            elif col == "Name":
                self.course_tree.column(col, width=250)
            elif col in ["Department", "Level"]:
                self.course_tree.column(col, width=100)
            elif col == "Credits":
                self.course_tree.column(col, width=70)
            elif col == "Enrollment":
                self.course_tree.column(col, width=100)
            elif col == "Status":
                self.course_tree.column(col, width=80)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack treeview and scrollbar
        self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click event
        self.course_tree.bind("<Double-1>", self.on_course_double_click)
        
        # Buttons frame - Role-based access
        buttons_frame = ttk.Frame(course_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        is_admin = self.is_admin()
        is_staff = self.is_staff()

        # Admin and Staff can create courses
        if is_admin or is_staff:
            ttk.Button(buttons_frame, text="Create Course", command=self.show_create_course).pack(side=tk.LEFT, padx=5)

        # Admin and Staff can edit courses
        if is_admin or is_staff:
            ttk.Button(buttons_frame, text="Edit Course", command=self.edit_selected_course).pack(side=tk.LEFT, padx=5)

        # Only Admin can delete courses
        if is_admin:
            ttk.Button(buttons_frame, text="Delete Course", command=self.delete_selected_course).pack(side=tk.LEFT, padx=5)

        # Everyone can refresh
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_course_list).pack(side=tk.LEFT, padx=5)
        
        # Load initial data
        self.refresh_course_list()
        self.load_filter_options()
    
    def create_course_details_tab(self):
        """Create the course details tab"""
        details_frame = ttk.Frame(self.notebook)
        self.notebook.add(details_frame, text="Course Details")
        
        # Course selection frame
        selection_frame = ttk.LabelFrame(details_frame, text="Select Course", padding=10)
        selection_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(selection_frame, text="Course:").pack(side=tk.LEFT)
        self.course_selector = ttk.Combobox(selection_frame, width=50)
        self.course_selector.pack(side=tk.LEFT, padx=5)
        self.course_selector.bind('<<ComboboxSelected>>', self.on_course_select)
        
        # Details display frame
        self.details_frame = ttk.LabelFrame(details_frame, text="Course Information", padding=10)
        self.details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create scrolled text for details
        self.details_text = ScrolledText(self.details_frame, wrap=tk.WORD, height=20)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        
        # Load course options
        self.load_course_selector_options()
    
    def create_analytics_tab(self):
        """Create the analytics tab with role-based access"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text="Analytics")

        is_admin = self.is_admin()
        is_staff = self.is_staff()

        # Analytics controls - Admin and Staff only
        if is_admin or is_staff:
            controls_frame = ttk.LabelFrame(analytics_frame, text="Analytics Controls", padding=10)
            controls_frame.pack(fill=tk.X, padx=5, pady=5)

            ttk.Button(controls_frame, text="Generate Course Analytics", command=self.generate_analytics).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text="Enrollment Report", command=self.show_enrollment_report).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text="Department Stats", command=self.show_department_stats).pack(side=tk.LEFT, padx=5)

        # Analytics display
        self.analytics_text = ScrolledText(analytics_frame, wrap=tk.WORD, height=25)
        self.analytics_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def create_instructors_tab(self):
        """Create the instructors tab with role-based access"""
        instructors_frame = ttk.Frame(self.notebook)
        self.notebook.add(instructors_frame, text="Instructors")

        is_admin = self.is_admin()
        is_staff = self.is_staff()

        # Instructor controls - Admin and Staff only
        if is_admin or is_staff:
            controls_frame = ttk.LabelFrame(instructors_frame, text="Instructor Management", padding=10)
            controls_frame.pack(fill=tk.X, padx=5, pady=5)

            # Admin only - Add instructor
            if is_admin:
                ttk.Button(controls_frame, text="Add Instructor", command=self.show_add_instructor).pack(side=tk.LEFT, padx=5)

            # Admin and Staff can view instructors
            ttk.Button(controls_frame, text="View Instructors", command=self.refresh_instructor_list).pack(side=tk.LEFT, padx=5)

            # Admin only - Assign to course
            if is_admin:
                ttk.Button(controls_frame, text="Assign to Course", command=self.show_assign_instructor).pack(side=tk.LEFT, padx=5)

        # Instructor list
        self.instructor_text = ScrolledText(instructors_frame, wrap=tk.WORD, height=25)
        self.instructor_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_academic_systems_tab(self):
        """Create the academic systems tab with LMS, Degree Audit, and Course Evaluation"""
        systems_frame = ttk.Frame(self.notebook)
        self.notebook.add(systems_frame, text="Academic Systems")

        # Title
        title_label = ttk.Label(systems_frame, text="Academic Management Systems",
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=20)

        # Description
        desc_label = ttk.Label(systems_frame,
                              text="Access comprehensive academic management tools for course delivery, evaluation, and advising.",
                              wraplength=600, justify=tk.CENTER)
        desc_label.pack(pady=10)

        # Systems container with padding
        container = ttk.Frame(systems_frame)
        container.pack(expand=True, fill=tk.BOTH, padx=50, pady=20)

        # LMS System
        lms_frame = ttk.LabelFrame(container, text="Learning Management System (LMS)", padding=20)
        lms_frame.pack(fill=tk.X, pady=10)

        lms_desc = ttk.Label(lms_frame,
                            text="Manage online courses, content delivery, video lectures, quizzes, discussions, and gradebook.",
                            wraplength=500)
        lms_desc.pack(pady=5)

        ttk.Button(lms_frame, text="Launch LMS",
                  command=self.show_lms_gui,
                  width=30).pack(pady=10)

        # Degree Audit System
        audit_frame = ttk.LabelFrame(container, text="Degree Audit & Academic Advising", padding=20)
        audit_frame.pack(fill=tk.X, pady=10)

        audit_desc = ttk.Label(audit_frame,
                              text="Track degree progress, check prerequisites, run graduation audits, and manage advising appointments.",
                              wraplength=500)
        audit_desc.pack(pady=5)

        ttk.Button(audit_frame, text="Launch Degree Audit",
                  command=self.show_degree_audit_gui,
                  width=30).pack(pady=10)

        # Course Evaluation System
        eval_frame = ttk.LabelFrame(container, text="Course Evaluation System", padding=20)
        eval_frame.pack(fill=tk.X, pady=10)

        eval_desc = ttk.Label(eval_frame,
                             text="Create evaluation templates, launch course evaluations, collect responses, and analyze results.",
                             wraplength=500)
        eval_desc.pack(pady=5)

        ttk.Button(eval_frame, text="Launch Course Evaluation",
                  command=self.show_course_evaluation_gui,
                  width=30).pack(pady=10)

        # Status message if systems not available
        if not ACADEMIC_SYSTEMS_AVAILABLE:
            warning_label = ttk.Label(container,
                                    text="⚠ Some academic systems may not be fully available. Check imports.",
                                    foreground="orange")
            warning_label.pack(pady=10)

    def show_lms_gui(self):
        """Launch the LMS GUI"""
        try:
            if ACADEMIC_SYSTEMS_AVAILABLE:
                launch_lms_gui(self.root, self.auth)
            else:
                messagebox.showerror("Error", "LMS system is not available. Please check installation.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch LMS: {e}")

    def show_degree_audit_gui(self):
        """Launch the Degree Audit GUI"""
        try:
            if ACADEMIC_SYSTEMS_AVAILABLE:
                launch_degree_audit_gui(self.root, self.auth)
            else:
                messagebox.showerror("Error", "Degree Audit system is not available. Please check installation.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Degree Audit: {e}")

    def show_course_evaluation_gui(self):
        """Launch the Course Evaluation GUI"""
        try:
            if ACADEMIC_SYSTEMS_AVAILABLE:
                launch_course_evaluation_gui(self.root, self.auth)
            else:
                messagebox.showerror("Error", "Course Evaluation system is not available. Please check installation.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Course Evaluation: {e}")

    def show_update_schedule(self):
        """Show update schedule dialog"""
        UpdateScheduleDialog(self.root, self.auth)

    def show_process_waitlist(self):
        """Show process waitlist dialog"""
        ProcessWaitlistDialog(self.root, self.auth)

    def show_remove_prerequisite(self):
        """Show remove prerequisite dialog"""
        dialog = RemovePrerequisiteDialog(self.root, self.auth)
        if dialog.result:
            self.update_status("Prerequisite removed successfully")

    def show_manage_status(self):
        """Show manage course status dialog"""
        dialog = ManageCourseStatusDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_course_list()
            self.update_status("Course status updated successfully")

    def show_import_csv(self):
        """Show import CSV dialog"""
        dialog = ImportExportDialog(self.root, self.auth, "import")
        if dialog.result:
            self.refresh_course_list()
            self.update_status("Courses imported successfully")

    def show_export_csv(self):
        """Show export CSV dialog"""
        dialog = ImportExportDialog(self.root, self.auth, "export")
        if dialog.result:
            self.update_status("Courses exported successfully")

    def show_recommend_courses(self):
        """Show course recommendations dialog"""
        RecommendCoursesDialog(self.root, self.auth)

    def show_course_history(self):
        """Show course history dialog"""
        CourseHistoryDialog(self.root, self.auth)

    def find_alternative_courses(self):
        """Show find alternative courses dialog"""
        AlternativeCourseDialog(self.root, self.auth)

    def show_system_maintenance(self):
        """Show system maintenance dialog (already exists as MaintenanceDialog)"""
        dialog = MaintenanceDialog(self.root, self.auth)
        if dialog.result:
            self.update_status("System maintenance completed")

    def show_analytics(self):
        """
        Entry point for the 'Course Analytics' menu item - redirects to detailed analytics.
        """
        # Use the existing detailed analytics function
        self.show_course_analytics_detailed()

    def show_create_schedule(self):
        """Open dialog to create a new course schedule entry"""
        CreateScheduleDialog(self.root, self.auth)

    def show_view_schedules(self):
        """Open dialog to view all schedules"""
        ViewSchedulesDialog(self.root, self.auth)

    def show_add_waitlist(self):
        """Open dialog to add a student to a course waitlist"""
        AddToWaitlistDialog(self.root, self.auth)

    def show_view_waitlists(self):
        """Open dialog to view course waitlists"""
        ViewWaitlistsDialog(self.root, self.auth)
    
    def show_create_course(self):
        """Show create course dialog"""
        dialog = CourseCreateDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_course_list()
            self.update_status(f"Course '{dialog.result}' created successfully")
    
    def edit_selected_course(self):
        """Edit the selected course"""
        selection = self.course_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a course to edit.")
            return
        
        item = self.course_tree.item(selection[0])
        course_id = item['values'][0]
        
        dialog = CourseEditDialog(self.root, self.auth, course_id)
        if dialog.result:
            self.refresh_course_list()
            self.update_status("Course updated successfully")
    
    def delete_selected_course(self):
        """Delete the selected course"""
        selection = self.course_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a course to delete.")
            return
        
        item = self.course_tree.item(selection[0])
        course_id = item['values'][0]
        course_code = item['values'][1]
        course_name = item['values'][2]
        
        # Enhanced delete confirmation with impact analysis
        if self.confirm_course_deletion(course_id, course_code, course_name):
            try:
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()

                    # Handle student reassignment before deleting course
                    self.reassign_students_from_deleted_course(cursor, course_code)

                    # Delete related records first
                    cursor.execute("DELETE FROM course_prerequisites WHERE course_id = ? OR prerequisite_course_id = ?", (course_id, course_id))
                    cursor.execute("DELETE FROM course_schedule WHERE course_id = ?", (course_id,))
                    cursor.execute("DELETE FROM course_waitlist WHERE course_id = ?", (course_id,))
                    cursor.execute("DELETE FROM course_history WHERE course_id = ?", (course_id,))

                    # Delete the course
                    cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))

                    conn.commit()

                self.refresh_course_list()
                self.update_status(f"Course '{course_code}' deleted successfully")
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to delete course: {e}")

    def reassign_students_from_deleted_course(self, cursor, course_code):
        """Reassign students from a course that's being deleted to other available courses and modules"""
        try:
            # First, delete all modules and assignments for this course
            self.delete_modules_for_course(cursor, course_code)

            # Get students enrolled in the course being deleted
            cursor.execute('''
                SELECT student_id, first_name, last_name
                FROM students
                WHERE course = ?
            ''', (course_code,))
            affected_students = cursor.fetchall()

            if not affected_students:
                return

            # Get available alternative courses (excluding the one being deleted)
            cursor.execute('''
                SELECT course_code FROM courses
                WHERE (status = 'Active' OR status = 'active') AND course_code != ?
                AND course_code IS NOT NULL AND course_code != ''
                AND max_enrollment > current_enrollment
            ''')
            alternative_courses = [row[0] for row in cursor.fetchall()]

            if not alternative_courses:
                # If no alternatives, create a default holding course
                alternative_courses = ['GENERAL']

            import random
            reassignment_count = 0

            # Reassign each student to a random alternative course
            for student_id, first_name, last_name in affected_students:
                new_course = random.choice(alternative_courses)

                # Update student's course
                cursor.execute('''
                    UPDATE students
                    SET course = ?
                    WHERE student_id = ?
                ''', (new_course, student_id))

                # Remove student from modules of the deleted course
                cursor.execute('''
                    DELETE FROM student_modules
                    WHERE student_id = ? AND module_code IN (
                        SELECT module_code FROM modules WHERE department = ?
                    )
                ''', (student_id, course_code))

                # Assign student to modules of the new course
                self.assign_student_to_course_modules(cursor, student_id, new_course)

                # Update course enrollment counts
                cursor.execute('''
                    UPDATE courses
                    SET current_enrollment = current_enrollment + 1
                    WHERE course_code = ?
                ''', (new_course,))

                reassignment_count += 1

            # Decrease enrollment count for the deleted course
            cursor.execute('''
                UPDATE courses
                SET current_enrollment = current_enrollment - ?
                WHERE course_code = ?
            ''', (reassignment_count, course_code))

            print(f"Reassigned {reassignment_count} students from {course_code} to alternative courses and modules.")

        except Exception as e:
            print(f"Error during student reassignment: {e}")

    def delete_modules_for_course(self, cursor, course_code):
        """Delete all modules and their assignments for a specific course"""
        try:
            # Get all modules for this course
            cursor.execute('SELECT module_code FROM modules WHERE department = ?', (course_code,))
            modules = [row[0] for row in cursor.fetchall()]

            for module_code in modules:
                # Delete assignments and related data for each module
                self.delete_assignments_for_module(cursor, module_code)

            # Delete all modules for this course
            cursor.execute('DELETE FROM modules WHERE department = ?', (course_code,))
            print(f"Deleted {len(modules)} modules for course {course_code}")

        except Exception as e:
            print(f"Error deleting modules for course {course_code}: {e}")

    def delete_assignments_for_module(self, cursor, module_code):
        """Delete all assignments and related data for a specific module"""
        try:
            # Get all assignment IDs for this module
            cursor.execute('SELECT id FROM assignments WHERE module_code = ?', (module_code,))
            assignment_ids = [row[0] for row in cursor.fetchall()]

            if assignment_ids:
                # Delete assignment submissions first
                for assignment_id in assignment_ids:
                    cursor.execute('DELETE FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))

                # Delete peer reviews for these assignments
                for assignment_id in assignment_ids:
                    cursor.execute('DELETE FROM peer_reviews WHERE assignment_id = ?', (assignment_id,))

                # Delete extension requests for these assignments
                for assignment_id in assignment_ids:
                    cursor.execute('DELETE FROM extension_requests WHERE assignment_id = ?', (assignment_id,))

                # Delete the assignments themselves
                cursor.execute('DELETE FROM assignments WHERE module_code = ?', (module_code,))

            # Also delete any assessments for this module
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assessments'")
            if cursor.fetchone():
                cursor.execute('DELETE FROM assessments WHERE module_code = ?', (module_code,))

        except Exception as e:
            print(f"Error deleting assignments for module {module_code}: {e}")

    def assign_student_to_course_modules(self, cursor, student_id, course_code):
        """Assign a student to random modules from their new course"""
        try:
            import random
            from datetime import datetime

            # Get available modules for the new course
            cursor.execute('''
                SELECT module_code, module_name FROM modules
                WHERE department = ? AND is_active = 1
            ''', (course_code,))
            available_modules = cursor.fetchall()

            if available_modules:
                # Randomly select 3-5 modules for the student
                num_modules = min(random.randint(3, 5), len(available_modules))
                selected_modules = random.sample(available_modules, num_modules)

                current_date = datetime.now().strftime('%Y-%m-%d')

                for module_code, module_name in selected_modules:
                    cursor.execute('''
                        INSERT OR IGNORE INTO student_modules (student_id, module_code, enrollment_date, status)
                        VALUES (?, ?, ?, ?)
                    ''', (student_id, module_code, current_date, 'Enrolled'))

                print(f"Assigned student {student_id} to {len(selected_modules)} modules in course {course_code}")

        except Exception as e:
            print(f"Error assigning student {student_id} to course modules: {e}")

    def confirm_course_deletion(self, course_id, course_code, course_name):
        """Show enhanced deletion confirmation dialog"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Get impact analysis
                cursor.execute("SELECT current_enrollment FROM courses WHERE id = ?", (course_id,))
                enrolled = cursor.fetchone()
                enrolled_count = enrolled[0] if enrolled and enrolled[0] else 0

                cursor.execute("SELECT COUNT(*) FROM course_prerequisites WHERE prerequisite_course_id = ?", (course_id,))
                prereq_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM course_schedule WHERE course_id = ?", (course_id,))
                schedule_count = cursor.fetchone()[0]
            
            # Create confirmation dialog
            message = f"Delete Course: {course_code} - {course_name}\n\n"
            message += "IMPACT ANALYSIS:\n"
            message += f"• Students enrolled: {enrolled_count}\n"
            message += f"• Courses using as prerequisite: {prereq_count}\n"
            message += f"• Schedule entries: {schedule_count}\n\n"
            
            if enrolled_count > 0 or prereq_count > 0:
                message += "⚠️ WARNING: This deletion will have significant impact!\n"
                message += "Consider setting status to 'Inactive' instead.\n\n"
            
            message += "This action cannot be undone. Continue?"
            
            return messagebox.askyesno("Confirm Deletion", message)
            
        except sqlite3.Error:
            return messagebox.askyesno("Confirm Deletion", f"Delete course '{course_code} - {course_name}'?\n\nThis action cannot be undone.")
        
    def on_search_change(self, event=None):
        """Handle search text change"""
        self.filter_courses()
    
    def on_filter_change(self, event=None):
        """Handle filter change"""
        self.filter_courses()
    
    def filter_courses(self):
        """Filter courses based on search and filter criteria"""
        try:
            # Clear existing items
            for item in self.course_tree.get_children():
                self.course_tree.delete(item)
            
            # Build query
            search_text = self.search_var.get().strip()
            dept_filter = self.dept_filter.get()
            status_filter = self.status_filter.get()

            query = """
            SELECT ROW_NUMBER() OVER (ORDER BY course_code) as id, course_code, course_name,
                   COALESCE(department, 'N/A') as department,
                   COALESCE(level, 'N/A') as level,
                   COALESCE(credit_hours, 3.0) as credit_hours,
                   COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment,
                   COALESCE(status, 'Active') as status
            FROM courses WHERE 1=1
            """
            params = []
            
            if search_text:
                query += " AND (course_code LIKE ? OR course_name LIKE ? OR description LIKE ?)"
                search_param = f"%{search_text}%"
                params.extend([search_param, search_param, search_param])
            
            if dept_filter and dept_filter != "All":
                query += " AND department = ?"
                params.append(dept_filter)
            
            if status_filter and status_filter != "All":
                query += " AND status = ?"
                params.append(status_filter)
            
            query += " ORDER BY course_code"

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                courses = cursor.fetchall()

            # Populate filtered results
            for course in courses:
                self.course_tree.insert("", tk.END, values=course)
            
            self.update_status(f"Found {len(courses)} courses")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Search failed: {e}")
    
    def load_filter_options(self):
        """Load options for filter dropdowns"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Load departments
                cursor.execute("SELECT DISTINCT department FROM courses WHERE department IS NOT NULL ORDER BY department")
                departments = ["All"] + [row[0] for row in cursor.fetchall()]
                self.dept_filter['values'] = departments
                self.dept_filter.set("All")
            
        except sqlite3.Error:
            pass
    
    def on_course_double_click(self, event):
        """Handle double-click on course item"""
        selection = self.course_tree.selection()
        if selection:
            item = self.course_tree.item(selection[0])
            course_id = item['values'][0]
            self.show_course_details(course_id)
    
    def show_course_details(self, course_id):
        """Show detailed course information"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
                course = cursor.fetchone()

                if not course:
                    messagebox.showerror("Error", "Course not found")
                    return

                # Switch to details tab and populate
                self.notebook.select(1)  # Details tab

                # Format course details
                details = self.format_course_details(course)

                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, details)
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load course details: {e}")
    
    def format_course_details(self, course):
        """Format course data for display."""

        def get(i, default="N/A"):
            return course[i] if len(course) > i and course[i] not in (None, "") else default

        def years(i):
            v = course[i] if len(course) > i else None
            return f"{v} years" if v not in (None, "") else "N/A"

        def money(i):
            v = course[i] if len(course) > i else None
            if isinstance(v, (int, float)):
                return f"${v:,.2f}"
            return "N/A" if v in (None, "") else str(v)

        def yesno(i):
            if len(course) <= i:
                return "N/A"
            v = course[i]
            return "Yes" if bool(v) else "No" if v in (False, 0) else "N/A"

        def avail_spots():
            max_e = course[15] if len(course) > 15 else None
            cur_e = course[16] if len(course) > 16 else None
            if isinstance(max_e, (int, float)) and isinstance(cur_e, (int, float)):
                return max_e - cur_e
            return "N/A"

        if len(course) < 10:
            # Basic format for legacy schema
            details = f"""COURSE DETAILS
    {'='*50}

    Course ID: {get(0)}
    Course Code: {get(1)}
    Course Name: {get(2)}
    Description: {get(3)}
    Duration: {years(4)}
    Level: {get(5)}
    Department: {get(6)}
    """
        else:
            # Enhanced format for full schema
            details = f"""COURSE DETAILS
    {'='*50}

    BASIC INFORMATION:
    Course ID: {get(0)}
    Course Code: {get(1)}
    Course Name: {get(2)}
    Description: {get(3)}
    Department: {get(6)}
    Level: {get(5)}
    Course Type: {get(18)}
    Status: {get(17)}

    ACADEMIC DETAILS:
    Credit Hours: {get(7)}
    Contact Hours/Week: {get(8)}
    Duration: {years(4)}
    Lab Required: {yesno(13)}
    Online Available: {yesno(14)}

    ENROLLMENT:
    Max Enrollment: {get(15)}
    Current Enrollment: {get(16)}
    Available Spots: {avail_spots()}

    ADDITIONAL INFORMATION:
    Learning Outcomes: {get(9)}
    Assessment Methods: {get(10)}
    Required Textbooks: {get(11)}
    Course Fee: {money(12)}
    Tags: {get(19)}
    Availability: {get(20)}

    TIMESTAMPS:
    Created: {get(21)}
    Last Updated: {get(22)}
    """
        return details

    
    def load_course_selector_options(self):
        """Load course options for the selector"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
                courses = cursor.fetchall()

                course_options = [f"{course[1]} - {course[2]}" for course in courses]
                self.course_selector['values'] = course_options

                # Store course IDs for mapping
                self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
        except sqlite3.Error:
            pass
    
    def on_course_select(self, event=None):
        """Handle course selection from dropdown"""
        selected_text = self.course_selector.get()
        if selected_text in self.course_id_map:
            course_id = self.course_id_map[selected_text]
            self.show_course_details(course_id)
    
    # =====================================================================
    # ANALYTICS FUNCTIONS
    # =====================================================================
    
    def generate_analytics(self):
        """Generate and display course analytics"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                analytics_text = "COURSE ANALYTICS DASHBOARD\n"
                analytics_text += "=" * 50 + "\n\n"

                # Overall statistics
                cursor.execute("""
                SELECT
                    COUNT(*) as total_courses,
                    SUM(COALESCE(current_enrollment, 0)) as total_students,
                    SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                    AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
                FROM courses
                WHERE status = 'Active'
                """)

                stats = cursor.fetchone()
                if stats:
                    analytics_text += "OVERALL STATISTICS:\n"
                    analytics_text += f"Total Active Courses: {stats[0]}\n"
                    analytics_text += f"Total Students Enrolled: {stats[1]}\n"
                    analytics_text += f"Total System Capacity: {stats[2]}\n"
                    analytics_text += f"Average Enrollment per Course: {stats[3]:.1f}\n"
                    if stats[2] > 0:
                        fill_rate = (stats[1] / stats[2]) * 100
                        analytics_text += f"System Fill Rate: {fill_rate:.1f}%\n"
                    analytics_text += f"Available Spots: {stats[2] - stats[1]}\n\n"

                # Department breakdown
                cursor.execute("""
                SELECT
                    COALESCE(department, 'Unknown') as dept,
                    COUNT(*) as course_count,
                    SUM(COALESCE(current_enrollment, 0)) as total_students
                FROM courses
                WHERE status = 'Active'
                GROUP BY department
                ORDER BY total_students DESC
                """)

                dept_stats = cursor.fetchall()
                if dept_stats:
                    analytics_text += "COURSES BY DEPARTMENT:\n"
                    analytics_text += f"{'Department':<20} {'Courses':<10} {'Students':<10}\n"
                    analytics_text += "-" * 40 + "\n"
                    for dept, courses, students in dept_stats:
                        analytics_text += f"{dept:<20} {courses:<10} {students:<10}\n"
                    analytics_text += "\n"

                # Most popular courses
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled
                FROM courses
                WHERE status = 'Active'
                ORDER BY enrolled DESC
                LIMIT 10
                """)

                popular = cursor.fetchall()
                if popular:
                    analytics_text += "MOST POPULAR COURSES (Top 10):\n"
                    analytics_text += f"{'Code':<10} {'Name':<30} {'Enrolled':<10}\n"
                    analytics_text += "-" * 50 + "\n"
                    for code, name, enrolled in popular:
                        name_short = name[:27] + "..." if len(name) > 30 else name
                        analytics_text += f"{code:<10} {name_short:<30} {enrolled:<10}\n"
                    analytics_text += "\n"

                # Courses with availability
                cursor.execute("""
                SELECT COUNT(*)
                FROM courses
                WHERE status = 'Active' AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
                """)
                available_count = cursor.fetchone()[0]
                analytics_text += f"COURSE AVAILABILITY:\n"
                analytics_text += f"Courses with Available Spots: {available_count}\n\n"

                # Status breakdown
                cursor.execute("SELECT status, COUNT(*) FROM courses GROUP BY status")
                status_data = cursor.fetchall()
                if status_data:
                    analytics_text += "COURSE STATUS BREAKDOWN:\n"
                    for status, count in status_data:
                        analytics_text += f"  {status}: {count}\n"

            # Display in analytics tab
            self.notebook.select(2)  # Analytics tab
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, analytics_text)

            self.update_status("Analytics generated successfully")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate analytics: {e}")
    
    def show_enrollment_report(self):
        """Show enrollment report dialog"""
        dialog = EnrollmentReportDialog(self.root)
        if dialog.result:
            # Generate selected report type
            report_type = dialog.result
            self.generate_enrollment_report(report_type)
    
    def generate_enrollment_report(self, report_type):
        """Generate specific enrollment report"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                report_text = f"ENROLLMENT REPORT - {report_type.upper()}\n"
                report_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report_text += "=" * 60 + "\n\n"

                if report_type == "Summary":
                    cursor.execute("""
                    SELECT
                        COUNT(*) as total_courses,
                        SUM(COALESCE(current_enrollment, 0)) as total_enrolled,
                        SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                        AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
                    FROM courses
                    WHERE status = 'Active'
                    """)

                    summary = cursor.fetchone()
                    report_text += f"Total Active Courses: {summary[0]}\n"
                    report_text += f"Total Students Enrolled: {summary[1]}\n"
                    report_text += f"Total System Capacity: {summary[2]}\n"
                    report_text += f"Average Enrollment per Course: {summary[3]:.1f}\n"
                    if summary[2] > 0:
                        report_text += f"System Fill Rate: {(summary[1]/summary[2]*100):.1f}%\n"
                    report_text += f"Available Spots: {summary[2] - summary[1]}\n"

                elif report_type == "Department":
                    cursor.execute("""
                    SELECT
                        COALESCE(department, 'Unknown') as dept,
                        COUNT(*) as course_count,
                        SUM(COALESCE(current_enrollment, 0)) as total_students,
                        SUM(COALESCE(max_enrollment, 0)) as total_capacity
                    FROM courses
                    WHERE status = 'Active'
                    GROUP BY department
                    ORDER BY total_students DESC
                    """)

                    dept_data = cursor.fetchall()
                    report_text += f"{'Department':<20} {'Courses':<10} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 60 + "\n"

                    for dept, courses, students, capacity in dept_data:
                        fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        report_text += f"{dept:<20} {courses:<10} {students:<10} {capacity:<10} {fill_rate:<10}\n"

                elif report_type == "Detailed":
                    cursor.execute("""
                    SELECT course_code, course_name, department, level,
                           COALESCE(current_enrollment, 0), COALESCE(max_enrollment, 0),
                           course_type, credit_hours
                    FROM courses
                    WHERE status = 'Active'
                    ORDER BY current_enrollment DESC
                    """)

                    course_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<25} {'Dept':<12} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 77 + "\n"

                    for course in course_data:
                        code, name, dept, level, enrolled, capacity = course[:6]
                        name_short = name[:22] + "..." if len(name) > 25 else name
                        dept_short = dept[:9] + "..." if dept and len(dept) > 12 else dept or "N/A"
                        level_short = level[:9] + "..." if level and len(level) > 12 else level or "N/A"
                        fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        enrollment_str = f"{enrolled}/{capacity}"

                        report_text += f"{code:<8} {name_short:<25} {dept_short:<12} {level_short:<12} {enrollment_str:<10} {fill_rate:<10}\n"

                elif report_type == "Capacity":
                    cursor.execute("""
                    SELECT course_code, course_name, department,
                           COALESCE(current_enrollment, 0) as enrolled,
                           COALESCE(max_enrollment, 0) as capacity,
                           COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0) as available
                    FROM courses
                    WHERE status = 'Active'
                    ORDER BY available DESC
                    """)

                    capacity_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<30} {'Department':<15} {'Enrolled':<10} {'Capacity':<10} {'Available':<10}\n"
                    report_text += "-" * 83 + "\n"

                    for code, name, dept, enrolled, capacity, available in capacity_data:
                        name_short = name[:27] + "..." if len(name) > 30 else name
                        dept_short = dept[:12] + "..." if dept and len(dept) > 15 else dept or "N/A"
                        report_text += f"{code:<8} {name_short:<30} {dept_short:<15} {enrolled:<10} {capacity:<10} {available:<10}\n"

            # Store report data for visualization and email
            self.last_report_data = {
                'type': report_type,
                'text': report_text,
                'conn': conn
            }

            # Display report in analytics tab
            self.notebook.select(2)  # Analytics tab
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, report_text)

            # Add visualization and email buttons (create if they don't exist)
            if not hasattr(self, 'report_action_frame'):
                self.report_action_frame = ttk.Frame(self.analytics_frame)
                self.report_action_frame.pack(fill=tk.X, pady=5)

                ttk.Button(self.report_action_frame, text="📊 Visualize Report",
                          command=self.visualize_report).pack(side=tk.LEFT, padx=5)
                ttk.Button(self.report_action_frame, text="📧 Email Report to Admin",
                          command=self.email_report).pack(side=tk.LEFT, padx=5)

            self.update_status(f"{report_type} enrollment report generated")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate report: {e}")

    def visualize_report(self):
        """Generate and display visual charts for the current report"""
        if not hasattr(self, 'last_report_data'):
            messagebox.showwarning("No Report", "Please generate a report first.")
            return

        if not CHARTS_AVAILABLE:
            messagebox.showerror("Charts Unavailable",
                               "Chart generation requires matplotlib and seaborn.\n"
                               "Install with: pip install matplotlib seaborn")
            return

        report_type = self.last_report_data['type']

        try:
            # Create chart window
            chart_window = tk.Toplevel(self.root)
            chart_window.title(f"Course Management - {report_type} Report Visualization")
            chart_window.geometry("1200x800")
            chart_window.transient(self.root)

            # Create main frame
            main_frame = ttk.Frame(chart_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=f"{report_type} Report - Visual Charts",
                     font=("Arial", 14, "bold")).pack(pady=10)

            # Create notebook for multiple charts
            chart_notebook = ttk.Notebook(main_frame)
            chart_notebook.pack(fill=tk.BOTH, expand=True, pady=10)

            # Fetch data from database
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                if report_type == "Summary":
                    self._create_summary_charts(chart_notebook, cursor)
                elif report_type == "Department":
                    self._create_department_charts(chart_notebook, cursor)
                elif report_type == "Detailed":
                    self._create_detailed_charts(chart_notebook, cursor)
                elif report_type == "Capacity":
                    self._create_capacity_charts(chart_notebook, cursor)

            # Close button
            ttk.Button(main_frame, text="Close", command=chart_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Visualization Error", f"Failed to create charts: {e}")
            print(f"Chart generation error: {e}")

    def _create_summary_charts(self, notebook, cursor):
        """Create summary report charts"""
        # Get summary data
        cursor.execute("""
        SELECT
            COUNT(*) as total_courses,
            SUM(COALESCE(current_enrollment, 0)) as total_enrolled,
            SUM(COALESCE(max_enrollment, 0)) as total_capacity,
            AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
        FROM courses
        WHERE status = 'Active'
        """)
        summary = cursor.fetchone()

        # Chart 1: Enrollment Overview (Bar Chart)
        frame1 = ttk.Frame(notebook)
        notebook.add(frame1, text="Enrollment Overview")

        fig1 = Figure(figsize=(10, 6), dpi=100)
        ax1 = fig1.add_subplot(111)

        categories = ['Total Courses', 'Total Enrolled', 'Total Capacity', 'Available Spots']
        values = [summary[0], summary[1], summary[2], summary[2] - summary[1]]
        colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']

        ax1.bar(categories, values, color=colors, alpha=0.8)
        ax1.set_ylabel('Count')
        ax1.set_title('Course Enrollment Summary', fontweight='bold', fontsize=14)
        ax1.grid(axis='y', alpha=0.3)

        for i, v in enumerate(values):
            ax1.text(i, v, f'{int(v)}', ha='center', va='bottom', fontweight='bold')

        canvas1 = FigureCanvasTkAgg(fig1, frame1)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 2: Fill Rate Pie Chart
        frame2 = ttk.Frame(notebook)
        notebook.add(frame2, text="Capacity Fill Rate")

        fig2 = Figure(figsize=(10, 6), dpi=100)
        ax2 = fig2.add_subplot(111)

        enrolled = summary[1]
        available = summary[2] - summary[1]

        ax2.pie([enrolled, available], labels=['Enrolled', 'Available'],
               autopct='%1.1f%%', startangle=90, colors=['#2ecc71', '#ecf0f1'])
        ax2.set_title(f'System Capacity Utilization\n({enrolled}/{summary[2]} spots filled)',
                     fontweight='bold', fontsize=14)

        canvas2 = FigureCanvasTkAgg(fig2, frame2)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _create_department_charts(self, notebook, cursor):
        """Create department report charts"""
        cursor.execute("""
        SELECT
            COALESCE(department, 'Unknown') as dept,
            COUNT(*) as course_count,
            SUM(COALESCE(current_enrollment, 0)) as total_students,
            SUM(COALESCE(max_enrollment, 0)) as total_capacity
        FROM courses
        WHERE status = 'Active'
        GROUP BY department
        ORDER BY total_students DESC
        """)
        dept_data = cursor.fetchall()

        # Chart 1: Students by Department (Bar Chart)
        frame1 = ttk.Frame(notebook)
        notebook.add(frame1, text="Students by Department")

        fig1 = Figure(figsize=(12, 6), dpi=100)
        ax1 = fig1.add_subplot(111)

        departments = [row[0] for row in dept_data]
        students = [row[2] for row in dept_data]

        ax1.barh(departments, students, color='#3498db', alpha=0.8)
        ax1.set_xlabel('Number of Students')
        ax1.set_title('Student Enrollment by Department', fontweight='bold', fontsize=14)
        ax1.grid(axis='x', alpha=0.3)

        for i, v in enumerate(students):
            ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

        fig1.tight_layout()
        canvas1 = FigureCanvasTkAgg(fig1, frame1)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 2: Course Count by Department (Pie Chart)
        frame2 = ttk.Frame(notebook)
        notebook.add(frame2, text="Courses by Department")

        fig2 = Figure(figsize=(10, 6), dpi=100)
        ax2 = fig2.add_subplot(111)

        course_counts = [row[1] for row in dept_data]

        ax2.pie(course_counts, labels=departments, autopct='%1.1f%%', startangle=90)
        ax2.set_title('Course Distribution by Department', fontweight='bold', fontsize=14)

        canvas2 = FigureCanvasTkAgg(fig2, frame2)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 3: Fill Rate by Department
        frame3 = ttk.Frame(notebook)
        notebook.add(frame3, text="Fill Rate by Department")

        fig3 = Figure(figsize=(12, 6), dpi=100)
        ax3 = fig3.add_subplot(111)

        fill_rates = [(row[2] / row[3] * 100) if row[3] > 0 else 0 for row in dept_data]

        ax3.barh(departments, fill_rates, color='#2ecc71', alpha=0.8)
        ax3.set_xlabel('Fill Rate (%)')
        ax3.set_title('Capacity Fill Rate by Department', fontweight='bold', fontsize=14)
        ax3.grid(axis='x', alpha=0.3)

        for i, v in enumerate(fill_rates):
            ax3.text(v, i, f' {v:.1f}%', va='center', fontweight='bold')

        fig3.tight_layout()
        canvas3 = FigureCanvasTkAgg(fig3, frame3)
        canvas3.draw()
        canvas3.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _create_detailed_charts(self, notebook, cursor):
        """Create detailed report charts"""
        cursor.execute("""
        SELECT course_code, course_name, department,
               COALESCE(current_enrollment, 0), COALESCE(max_enrollment, 0)
        FROM courses
        WHERE status = 'Active'
        ORDER BY current_enrollment DESC
        LIMIT 15
        """)
        course_data = cursor.fetchall()

        # Chart 1: Top 15 Courses by Enrollment
        frame1 = ttk.Frame(notebook)
        notebook.add(frame1, text="Top Courses")

        fig1 = Figure(figsize=(12, 8), dpi=100)
        ax1 = fig1.add_subplot(111)

        course_names = [f"{row[0]}\n{row[1][:20]}" for row in course_data]
        enrollments = [row[3] for row in course_data]

        ax1.barh(course_names, enrollments, color='#e74c3c', alpha=0.8)
        ax1.set_xlabel('Enrolled Students')
        ax1.set_title('Top 15 Courses by Enrollment', fontweight='bold', fontsize=14)
        ax1.grid(axis='x', alpha=0.3)

        for i, v in enumerate(enrollments):
            ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

        fig1.tight_layout()
        canvas1 = FigureCanvasTkAgg(fig1, frame1)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 2: Enrollment vs Capacity
        frame2 = ttk.Frame(notebook)
        notebook.add(frame2, text="Enrollment vs Capacity")

        fig2 = Figure(figsize=(12, 8), dpi=100)
        ax2 = fig2.add_subplot(111)

        x = np.arange(len(course_data))
        width = 0.35

        enrolled = [row[3] for row in course_data]
        capacity = [row[4] for row in course_data]
        course_codes = [row[0] for row in course_data]

        ax2.bar(x - width/2, enrolled, width, label='Enrolled', color='#3498db', alpha=0.8)
        ax2.bar(x + width/2, capacity, width, label='Capacity', color='#95a5a6', alpha=0.8)

        ax2.set_xlabel('Course Code')
        ax2.set_ylabel('Students')
        ax2.set_title('Enrollment vs Capacity - Top 15 Courses', fontweight='bold', fontsize=14)
        ax2.set_xticks(x)
        ax2.set_xticklabels(course_codes, rotation=45, ha='right')
        ax2.legend()
        ax2.grid(axis='y', alpha=0.3)

        fig2.tight_layout()
        canvas2 = FigureCanvasTkAgg(fig2, frame2)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _create_capacity_charts(self, notebook, cursor):
        """Create capacity report charts"""
        cursor.execute("""
        SELECT course_code, course_name, department,
               COALESCE(current_enrollment, 0) as enrolled,
               COALESCE(max_enrollment, 0) as capacity,
               COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0) as available
        FROM courses
        WHERE status = 'Active'
        ORDER BY available DESC
        LIMIT 15
        """)
        capacity_data = cursor.fetchall()

        # Chart 1: Available Spots by Course
        frame1 = ttk.Frame(notebook)
        notebook.add(frame1, text="Available Spots")

        fig1 = Figure(figsize=(12, 8), dpi=100)
        ax1 = fig1.add_subplot(111)

        course_names = [f"{row[0]}\n{row[1][:20]}" for row in capacity_data]
        available = [row[5] for row in capacity_data]

        ax1.barh(course_names, available, color='#f39c12', alpha=0.8)
        ax1.set_xlabel('Available Spots')
        ax1.set_title('Top 15 Courses by Available Capacity', fontweight='bold', fontsize=14)
        ax1.grid(axis='x', alpha=0.3)

        for i, v in enumerate(available):
            ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

        fig1.tight_layout()
        canvas1 = FigureCanvasTkAgg(fig1, frame1)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 2: Capacity Utilization Breakdown
        frame2 = ttk.Frame(notebook)
        notebook.add(frame2, text="Utilization Breakdown")

        fig2 = Figure(figsize=(12, 8), dpi=100)
        ax2 = fig2.add_subplot(111)

        course_codes = [row[0] for row in capacity_data]
        enrolled = [row[3] for row in capacity_data]
        available = [row[5] for row in capacity_data]

        x = np.arange(len(capacity_data))
        ax2.bar(x, enrolled, label='Enrolled', color='#2ecc71', alpha=0.8)
        ax2.bar(x, available, bottom=enrolled, label='Available', color='#ecf0f1', alpha=0.8)

        ax2.set_xlabel('Course Code')
        ax2.set_ylabel('Spots')
        ax2.set_title('Capacity Utilization - Top 15 Courses', fontweight='bold', fontsize=14)
        ax2.set_xticks(x)
        ax2.set_xticklabels(course_codes, rotation=45, ha='right')
        ax2.legend()
        ax2.grid(axis='y', alpha=0.3)

        fig2.tight_layout()
        canvas2 = FigureCanvasTkAgg(fig2, frame2)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def email_report(self):
        """Email the current report to admin"""
        if not hasattr(self, 'last_report_data'):
            messagebox.showwarning("No Report", "Please generate a report first.")
            return

        if not EMAIL_AVAILABLE:
            messagebox.showerror("Email Service Unavailable",
                               "Email service is not configured.\n"
                               "Please set up email settings.")
            return

        # Create email dialog
        email_dialog = tk.Toplevel(self.root)
        email_dialog.title("📧 Email Report to Admin")
        email_dialog.geometry("1000x750")
        email_dialog.transient(self.root)
        email_dialog.grab_set()

        frame = ttk.Frame(email_dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Email Course Management Report",
                 font=("Arial", 14, "bold")).pack(pady=(0, 20))

        # Get admin email from database
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1")
                admin_row = cursor.fetchone()
                default_email = admin_row[0] if admin_row else "admin@university.edu"
        except Exception as e:
            print(f"Warning: Could not fetch admin email from database: {e}")
            default_email = "admin@university.edu"

        ttk.Label(frame, text="Admin Email Address:").pack(anchor='w', pady=(0, 5))
        email_var = tk.StringVar(value=default_email)

        # Create email input frame with refresh button
        email_frame = ttk.Frame(frame)
        email_frame.pack(fill='x', pady=(0, 10))

        email_entry = ttk.Entry(email_frame, textvariable=email_var, width=40)
        email_entry.pack(side='left', fill='x', expand=True)

        def refresh_admin_email():
            """Refresh admin email from database"""
            try:
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT username, email FROM users WHERE LOWER(role) = 'admin' ORDER BY username")
                    admins = cursor.fetchall()

                if admins:
                    if len(admins) > 1:
                        # Show selection dialog
                        admin_select_dialog = tk.Toplevel(email_dialog)
                        admin_select_dialog.title("Select Admin")
                        admin_select_dialog.geometry("900x700")
                        admin_select_dialog.transient(email_dialog)
                        admin_select_dialog.grab_set()

                        ttk.Label(admin_select_dialog, text="Select Admin User:",
                                 font=('Arial', 12, 'bold')).pack(pady=10)

                        admin_listbox = tk.Listbox(admin_select_dialog, height=10)
                        admin_listbox.pack(fill='both', expand=True, padx=20, pady=10)

                        for username, email in admins:
                            admin_listbox.insert(tk.END, f"{username} ({email})")

                        def select_admin():
                            selection = admin_listbox.curselection()
                            if selection:
                                selected_email = admins[selection[0]][1]
                                email_var.set(selected_email)
                            admin_select_dialog.destroy()

                        ttk.Button(admin_select_dialog, text="Select",
                                  command=select_admin).pack(pady=10)
                    else:
                        email_var.set(admins[0][1])
                        messagebox.showinfo("Admin Email", f"Using admin email: {admins[0][1]}")
                else:
                    messagebox.showwarning("No Admins", "No admin users found in database.")
            except Exception as e:
                messagebox.showerror("Database Error", f"Could not fetch admin emails: {str(e)}")

        ttk.Button(email_frame, text="🔄", command=refresh_admin_email, width=3).pack(side='left', padx=(5, 0))

        ttk.Label(frame, text="Subject:").pack(anchor='w', pady=(10, 5))
        subject_var = tk.StringVar(value=f"Course Management Report - {self.last_report_data['type']}")
        ttk.Entry(frame, textvariable=subject_var, width=60).pack(fill='x', pady=(0, 10))

        ttk.Label(frame, text="Message (optional):").pack(anchor='w', pady=(10, 5))
        message_text = ScrolledText(frame, height=8, wrap=tk.WORD)
        message_text.pack(fill='both', expand=True, pady=(0, 10))
        message_text.insert('1.0', "Please find the course management report below.\n\n"
                                   "This report was automatically generated from the Course Management GUI.")

        ttk.Label(frame, text="Report Preview:").pack(anchor='w', pady=(10, 5))
        preview_text = ScrolledText(frame, height=10, wrap=tk.WORD)
        preview_text.pack(fill='both', expand=True, pady=(0, 20))
        preview_text.insert('1.0', self.last_report_data['text'])
        preview_text.config(state='disabled')

        def send_email_report():
            try:
                admin_email = email_var.get().strip()
                subject = subject_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()

                if not admin_email or '@' not in admin_email:
                    messagebox.showwarning("Invalid Email", "Please enter a valid admin email address.")
                    return

                # Create email body
                body = f"""{message}

{'=' * 80}
{self.last_report_data['text']}
{'=' * 80}

Report Type: {self.last_report_data['type']}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This email was sent from the Course Management GUI.
"""

                # Send email
                send_email(
                    recipient_email=admin_email,
                    subject=subject,
                    body=body
                )

                messagebox.showinfo("Email Sent",
                                  f"✅ Report sent successfully to {admin_email}\n\n"
                                  f"Report Type: {self.last_report_data['type']}")
                email_dialog.destroy()

            except Exception as e:
                messagebox.showerror("Email Error",
                                   f"Failed to send email: {str(e)}\n\n"
                                   f"Please check email configuration.")
                print(f"Email error: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(button_frame, text="📧 Send Email",
                  command=send_email_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="❌ Cancel",
                  command=email_dialog.destroy).pack(side='right')

    def show_department_stats(self):
        """Show department statistics dialog with enhanced GUI display"""
        try:
            # Create department stats window
            stats_window = tk.Toplevel(self.root)
            stats_window.title("Department Statistics")
            stats_window.geometry("800x600")
            stats_window.transient(self.root)

            main_frame = ttk.Frame(stats_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Department selection
            selection_frame = ttk.Frame(main_frame)
            selection_frame.pack(fill=tk.X, pady=5)

            ttk.Label(selection_frame, text="Department:").pack(side=tk.LEFT)
            dept_var = tk.StringVar()

            # Get departments list
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT COALESCE(department, 'Unknown') as dept FROM courses ORDER BY dept")
                departments = ["All Departments"] + [row[0] for row in cursor.fetchall()]

            dept_combo = ttk.Combobox(selection_frame, textvariable=dept_var, values=departments)
            dept_combo.pack(side=tk.LEFT, padx=5)
            dept_combo.set("All Departments")

            # Statistics display
            stats_text = ScrolledText(main_frame, wrap=tk.WORD)
            stats_text.pack(fill=tk.BOTH, expand=True, pady=5)

            def update_stats():
                selected_dept = dept_var.get()
                stats_text.delete(1.0, tk.END)

                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()

                    if selected_dept == "All Departments":
                        # All departments overview
                        cursor.execute("""
                        SELECT
                            COALESCE(department, 'Unknown') as dept,
                            COUNT(*) as course_count,
                            SUM(COALESCE(current_enrollment, 0)) as total_students,
                            SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                            COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
                        FROM courses
                        GROUP BY department
                        ORDER BY total_students DESC
                        """)

                        all_dept_stats = cursor.fetchall()
                        stats_text.insert(tk.END, "ALL DEPARTMENTS OVERVIEW\n")
                        stats_text.insert(tk.END, "=" * 50 + "\n\n")
                        stats_text.insert(tk.END, f"{'Department':<20} {'Courses':<10} {'Active':<8} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n")
                        stats_text.insert(tk.END, "-" * 68 + "\n")

                        for dept_stat in all_dept_stats:
                            dept, courses, students, capacity, active = dept_stat
                            fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                            stats_text.insert(tk.END, f"{dept:<20} {courses:<10} {active:<8} {students:<10} {capacity:<10} {fill_rate:<10}\n")
                    else:
                        # Single department stats
                        cursor.execute("""
                        SELECT
                            COUNT(*) as total_courses,
                            SUM(COALESCE(current_enrollment, 0)) as total_students,
                            SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                            AVG(COALESCE(current_enrollment, 0)) as avg_enrollment,
                            AVG(credit_hours) as avg_credits,
                            COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
                        FROM courses
                        WHERE department = ?
                        """, (selected_dept,))

                        stats = cursor.fetchone()

                        stats_text.insert(tk.END, f"STATISTICS FOR {selected_dept.upper()} DEPARTMENT\n")
                        stats_text.insert(tk.END, "=" * 60 + "\n\n")
                        stats_text.insert(tk.END, f"Total Courses: {stats[0]}\n")
                        stats_text.insert(tk.END, f"Active Courses: {stats[5]}\n")
                        stats_text.insert(tk.END, f"Total Students: {stats[1]}\n")
                        stats_text.insert(tk.END, f"Total Capacity: {stats[2]}\n")
                        stats_text.insert(tk.END, f"Average Enrollment: {stats[3]:.1f}\n")
                        stats_text.insert(tk.END, f"Average Credit Hours: {stats[4]:.1f}\n")
                        if stats[2] > 0:
                            stats_text.insert(tk.END, f"Department Fill Rate: {(stats[1]/stats[2]*100):.1f}%\n")

            ttk.Button(selection_frame, text="Update", command=update_stats).pack(side=tk.LEFT, padx=5)
            ttk.Button(main_frame, text="Close", command=stats_window.destroy).pack(pady=10)

            # Initial load
            update_stats()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load department statistics: {e}")
    
    # =====================================================================
    # INSTRUCTOR MANAGEMENT
    # =====================================================================
    
    def show_add_instructor(self):
        """Show add instructor dialog"""
        dialog = InstructorCreateDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_instructor_list()
            self.update_status(f"Instructor '{dialog.result}' added successfully")
    
    def refresh_instructor_list(self):
        """Refresh the instructor list"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Check if instructors table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
                if not cursor.fetchone():
                    instructor_text = "INSTRUCTORS\n"
                    instructor_text += "=" * 50 + "\n\n"
                    instructor_text += "No instructors table found. Please create instructors first.\n"
                else:
                    cursor.execute("""
                    SELECT id, first_name, last_name, email, department, specialization,
                           max_courses_per_semester, status
                    FROM instructors
                    ORDER BY last_name, first_name
                    """)

                    instructors = cursor.fetchall()

                    instructor_text = "INSTRUCTORS\n"
                    instructor_text += "=" * 50 + "\n\n"

                    if instructors:
                        instructor_text += f"{'ID':<5} {'Name':<25} {'Email':<30} {'Department':<15} {'Status':<10}\n"
                        instructor_text += "-" * 85 + "\n"

                        for instructor in instructors:
                            id, first_name, last_name, email, dept, spec, max_courses, status = instructor
                            full_name = f"{first_name} {last_name}"
                            dept_display = dept[:12] + "..." if dept and len(dept) > 15 else dept or "N/A"
                            instructor_text += f"{id:<5} {full_name:<25} {email:<30} {dept_display:<15} {status:<10}\n"

                        instructor_text += f"\nTotal Instructors: {len(instructors)}\n"
                    else:
                        instructor_text += "No instructors found in the system.\n"

            # Update instructor tab
            self.instructor_text.delete(1.0, tk.END)
            self.instructor_text.insert(1.0, instructor_text)
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load instructors: {e}")
    
    def show_assign_instructor(self):
        """Show assign instructor to course dialog"""
        dialog = AssignInstructorDialog(self.root, self.auth)
        if dialog.result:
            self.update_status("Instructor assigned successfully")
    
    # =====================================================================
    # UTILITY FUNCTIONS
    # =====================================================================
    
    def show_search_dialog(self):
        """Show advanced search dialog"""
        dialog = AdvancedSearchDialog(self.root)
        if dialog.result:
            # Apply search results to main course list
            self.apply_search_results(dialog.result)
    
    def apply_search_results(self, search_criteria):
        """Apply search results to course list"""
        try:
            # Clear existing items
            for item in self.course_tree.get_children():
                self.course_tree.delete(item)
            
            # Build query from search criteria
            query = """
            SELECT id, course_code, course_name, department, level, credit_hours, 
                   COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment,
                   status
            FROM courses WHERE 1=1
            """
            params = []
            
            for field, value in search_criteria.items():
                if field == "available_only" and value:
                    query += " AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)"
                elif value and (isinstance(value, str) and value.strip()):
                    if field == "keyword":
                        query += " AND (course_code LIKE ? OR course_name LIKE ? OR description LIKE ?)"
                        search_param = f"%{value}%"
                        params.extend([search_param, search_param, search_param])
                    elif field == "min_credits":
                        query += " AND credit_hours >= ?"
                        params.append(float(value))
                    elif field == "max_credits":
                        query += " AND credit_hours <= ?"
                        params.append(float(value))
                    elif field not in ["available_only"]:
                        query += f" AND {field} LIKE ?"
                        params.append(f"%{value}%")
            
            query += " ORDER BY course_code"
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute(query, params)
            courses = cursor.fetchall()
            conn.close()
            
            # Populate results
            for course in courses:
                self.course_tree.insert("", tk.END, values=course)
            
            self.update_status(f"Search completed: {len(courses)} courses found")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Search failed: {e}")
    
    def show_prerequisites_window(self):
        """Show prerequisites management window"""
        PrerequisitesWindow(self.root, self.auth)
    
    def show_bulk_update(self):
        """Show bulk update dialog"""
        dialog = BulkUpdateDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_course_list()
            self.update_status("Bulk update completed")
    
    def show_maintenance(self):
        """Show system maintenance dialog"""
        dialog = MaintenanceDialog(self.root, self.auth)
        if dialog.result:
            self.update_status("Maintenance task completed")
    
    def show_recommendations(self):
        """Show course recommendations"""
        dialog = RecommendationsDialog(self.root)
        if dialog.result:
            # Display recommendations in analytics tab
            self.notebook.select(2)  # Analytics tab
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, dialog.result)
    
    def import_csv(self):
        """Import courses from CSV file"""
        file_path = filedialog.askopenfilename(
            title="Select CSV file to import",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            imported_count = 0
            error_count = 0
            
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                required_fields = ['course_code', 'course_name', 'department']
                if not all(field in reader.fieldnames for field in required_fields):
                    messagebox.showerror("Import Error", f"CSV must contain these required columns: {', '.join(required_fields)}")
                    return
                
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        course_code = row['course_code'].strip().upper()
                        course_name = row['course_name'].strip()
                        department = row['department'].strip()
                        
                        if not course_code or not course_name:
                            error_count += 1
                            continue
                        
                        # Check for duplicates
                        cursor.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,))
                        if cursor.fetchone():
                            error_count += 1
                            continue
                        
                        # Prepare optional fields
                        description = row.get('description', '').strip()
                        level = row.get('level', '').strip()
                        credit_hours = float(row.get('credit_hours', 3.0))
                        max_enrollment = int(row.get('max_enrollment', 30))
                        course_type = row.get('course_type', 'Core').strip()
                        
                        # Insert course
                        cursor.execute('''
                        INSERT INTO courses (
                            course_code, course_name, description, level, department,
                            credit_hours, max_enrollment, course_type, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (course_code, course_name, description, level, department,
                              credit_hours, max_enrollment, course_type, timestamp, timestamp))

                        # Mirror canonical values into legacy alias columns if they exist
                        try:
                            last_id = cursor.lastrowid
                            cursor.execute(
                                "UPDATE courses SET code = course_code, name = course_name, credits = credit_hours, date_added = COALESCE(date_added, created_at) WHERE id = ?",
                                (last_id,),
                            )
                        except Exception:
                            pass

                        imported_count += 1
                        
                    except (ValueError, sqlite3.Error):
                        error_count += 1
                        continue
                
                conn.commit()
                conn.close()
            
            self.refresh_course_list()
            
            message = f"Import completed!\n\nSuccessfully imported: {imported_count} courses\nErrors: {error_count} courses"
            messagebox.showinfo("Import Results", message)
            self.update_status(f"Imported {imported_count} courses from CSV")
            
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import CSV: {e}")
    
    def export_csv(self):
        """Export courses to CSV file"""
        file_path = filedialog.asksaveasfilename(
            title="Save CSV file",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
            
            # Get column names
            cursor.execute("PRAGMA table_info(courses)")
            columns = [col[1] for col in cursor.fetchall()]
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns)
                writer.writerows(courses)
            
            conn.close()
            
            messagebox.showinfo("Export Complete", f"Exported {len(courses)} courses to {file_path}")
            self.update_status(f"Exported {len(courses)} courses to CSV")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {e}")
    
    def backup_database(self):
        """Create database backup - enhanced version"""
        file_path = filedialog.asksaveasfilename(
            title="Save database backup",
            defaultextension=".sql",
            filetypes=[("SQL files", "*.sql"), ("SQLite files", "*.db"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            
            if file_path.endswith('.sql'):
                # SQL dump backup
                with open(file_path, 'w') as f:
                    for line in conn.iterdump():
                        f.write('%s\n' % line)
            else:
                # Binary database copy
                backup_conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                conn.backup(backup_conn)
                backup_conn.close()
            
            conn.close()
            
            messagebox.showinfo("Backup Complete", f"Database backup saved to {file_path}")
            self.update_status("Database backup created")
            
        except Exception as e:
            messagebox.showerror("Backup Error", f"Failed to create backup: {e}")

    def view_course_details(self, cursor, course_id):
        """Enhanced course details viewer"""
        cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        course = cursor.fetchone()
        
        if not course:
            messagebox.showerror("Error", "Course not found")
            return
        
        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Course Details: {course[1]}")
        details_window.geometry("600x700")
        details_window.transient(self.root)
        
        # Create notebook for different views
        notebook = ttk.Notebook(details_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Basic Info Tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Info")
        
        basic_text = ScrolledText(basic_frame, wrap=tk.WORD)
        basic_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        basic_text.insert(tk.END, self.format_course_details(course))
        basic_text.config(state=tk.DISABLED)
        
        # Prerequisites Tab
        prereq_frame = ttk.Frame(notebook)
        notebook.add(prereq_frame, text="Prerequisites")
        
        prereq_text = ScrolledText(prereq_frame, wrap=tk.WORD)
        prereq_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Load prerequisites
        cursor.execute("""
        SELECT c.course_code, c.course_name, cp.is_required
        FROM course_prerequisites cp
        JOIN courses c ON cp.prerequisite_course_id = c.id
        WHERE cp.course_id = ?
        ORDER BY c.course_code
        """, (course_id,))
        
        prereqs = cursor.fetchall()
        if prereqs:
            prereq_text.insert(tk.END, "PREREQUISITES:\n\n")
            for code, name, required in prereqs:
                req_type = "Required" if required else "Recommended"
                prereq_text.insert(tk.END, f"• {code} - {name} ({req_type})\n")
        else:
            prereq_text.insert(tk.END, "No prerequisites for this course.")
        
        prereq_text.config(state=tk.DISABLED)
        
        # Schedule Tab
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text="Schedule")
        
        schedule_text = ScrolledText(schedule_frame, wrap=tk.WORD)
        schedule_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Load schedule
        cursor.execute("""
        SELECT cs.semester, cs.year, cs.start_time, cs.end_time, cs.days_of_week, cs.classroom,
               COALESCE(i.first_name || ' ' || i.last_name, 'Unassigned') as instructor
        FROM course_schedule cs
        LEFT JOIN instructors i ON cs.instructor_id = i.id
        WHERE cs.course_id = ?
        ORDER BY cs.year DESC, cs.semester
        """, (course_id,))
        
        schedules = cursor.fetchall()
        if schedules:
            schedule_text.insert(tk.END, "COURSE SCHEDULES:\n\n")
            for schedule in schedules:
                semester, year, start, end, days, room, instructor = schedule
                schedule_text.insert(tk.END, f"Semester: {semester} {year}\n")
                if start and end:
                    schedule_text.insert(tk.END, f"Time: {start} - {end}\n")
                if days:
                    schedule_text.insert(tk.END, f"Days: {days}\n")
                if room:
                    schedule_text.insert(tk.END, f"Room: {room}\n")
                schedule_text.insert(tk.END, f"Instructor: {instructor}\n\n")
        else:
            schedule_text.insert(tk.END, "No schedule information available.")
        
        schedule_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=10)

    def show_advanced_search(self):
        """Show advanced search dialog"""
        AdvancedCourseSearchDialog(self.root, self.auth)

    def show_course_analytics_detailed(self):
        """Show detailed analytics dialog"""
        CourseAnalyticsDialog(self.root, self.auth)

    def show_data_validation(self):
        """Show data validation dialog"""
        CourseValidationDialog(self.root, self.auth)
    
    def sort_treeview(self, col):
        """Sort treeview by column"""
        data = [(self.course_tree.set(child, col), child) for child in self.course_tree.get_children('')]
        
        # Determine if we're sorting numbers or text
        try:
            # Try to convert to float for numeric sorting
            data.sort(key=lambda x: float(x[0]) if x[0].replace('.', '').replace('/', '').isdigit() else float('inf'))
        except:
            # Fall back to string sorting
            data.sort(key=lambda x: x[0].lower())
        
        # Rearrange items in sorted positions
        for ix, item in enumerate(data):
            self.course_tree.move(item[1], '', ix)
        
    def show_about(self):
        """Show about dialog"""
        about_text = """Enhanced Course Management System v2.0

A comprehensive GUI-based course management system with:
• Course creation and management
• Advanced search and filtering
• Analytics and reporting
• Instructor management
• Prerequisites handling
• Import/Export capabilities
• System maintenance tools

Developed with Python and Tkinter
Backwards compatible with original CLI version"""
        
        messagebox.showinfo("About", about_text)
    
    def show_help(self):
        """Show help dialog"""
        help_text = """USER GUIDE

COURSE MANAGEMENT:
• Use the Course List tab to view and manage courses
• Double-click a course to view details
• Use search and filters to find specific courses
• Create new courses using the Create Course button

ANALYTICS:
• View system-wide analytics in the Analytics tab
• Generate various reports from the Analytics menu
• Export data for external analysis

INSTRUCTORS:
• Manage instructors in the Instructors tab
• Assign instructors to courses
• View instructor workloads

IMPORT/EXPORT:
• Import courses from CSV files (File menu)
• Export course data to CSV
• Create database backups

For more information, consult the documentation."""
        
        # Create help window
        help_window = tk.Toplevel(self.root)
        help_window.title("User Guide")
        help_window.geometry("600x400")
        
        help_text_widget = ScrolledText(help_window, wrap=tk.WORD)
        help_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        help_text_widget.insert(1.0, help_text)
        help_text_widget.config(state=tk.DISABLED)

    def return_to_main_menu(self):
        """Return to the main menu/GUI"""
        if messagebox.askyesno("Return to Main Menu", "Do you want to close this window and return to the main menu?"):
            try:
                # Try to open the main GUI if it exists
                try:
                    import subprocess
                    import sys
                    # Attempt to launch the main GUI
                    main_gui_path = Path(__file__).parent / 'main_gui.py'
                    if main_gui_path.exists():
                        subprocess.Popen([sys.executable, str(main_gui_path)])
                except Exception:
                    pass  # Main GUI may not exist or fail to launch

                # Close this window
                self.root.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to return to main menu: {str(e)}")

# =====================================================================
# DIALOG CLASSES
# =====================================================================

class AdvancedCourseSearchDialog:
    """Enhanced version of the existing AdvancedSearchDialog with more features"""
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Course Search")
        self.dialog.geometry("800x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Advanced Course Search", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Create notebook for different search types
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Basic Search Tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Search")
        self.create_basic_search(basic_frame)
        
        # Advanced Filters Tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Advanced Filters")
        self.create_advanced_filters(advanced_frame)
        
        # Results Tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="Search Results")
        self.create_results_display(results_frame)
        
        # Search buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Search", command=self.perform_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Results", command=self.export_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def create_basic_search(self, parent):
        # Keyword search
        keyword_frame = ttk.LabelFrame(parent, text="Keyword Search", padding=10)
        keyword_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(keyword_frame, text="Search in:").grid(row=0, column=0, sticky=tk.W)
        self.search_in_var = tk.StringVar(value="all")
        
        search_options = [
            ("All fields", "all"),
            ("Course name only", "name"),
            ("Description only", "description"),
            ("Course code only", "code")
        ]
        
        for i, (text, value) in enumerate(search_options):
            ttk.Radiobutton(keyword_frame, text=text, variable=self.search_in_var, 
                           value=value).grid(row=i+1, column=0, sticky=tk.W)
        
        ttk.Label(keyword_frame, text="Keywords:").grid(row=0, column=1, sticky=tk.W, padx=(20,0))
        self.keyword_var = tk.StringVar()
        ttk.Entry(keyword_frame, textvariable=self.keyword_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=(20,0))
        
        # Quick filters
        quick_frame = ttk.LabelFrame(parent, text="Quick Filters", padding=10)
        quick_frame.pack(fill=tk.X, pady=5)
        
        self.only_available = tk.BooleanVar()
        ttk.Checkbutton(quick_frame, text="Only courses with available spots", 
                       variable=self.only_available).pack(anchor=tk.W)
        
        self.only_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(quick_frame, text="Only active courses", 
                       variable=self.only_active).pack(anchor=tk.W)
        
        self.online_only = tk.BooleanVar()
        ttk.Checkbutton(quick_frame, text="Only online available courses", 
                       variable=self.online_only).pack(anchor=tk.W)
        
        self.no_lab = tk.BooleanVar()
        ttk.Checkbutton(quick_frame, text="Exclude lab courses", 
                       variable=self.no_lab).pack(anchor=tk.W)
    
    def create_advanced_filters(self, parent):
        # Academic filters
        academic_frame = ttk.LabelFrame(parent, text="Academic Criteria", padding=10)
        academic_frame.pack(fill=tk.X, pady=5)
        
        # Department multi-select
        ttk.Label(academic_frame, text="Departments:").grid(row=0, column=0, sticky=tk.NW)
        dept_frame = ttk.Frame(academic_frame)
        dept_frame.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        self.dept_vars = {}
        self.load_departments(dept_frame)
        
        # Level selection
        ttk.Label(academic_frame, text="Levels:").grid(row=1, column=0, sticky=tk.NW, pady=(10,0))
        level_frame = ttk.Frame(academic_frame)
        level_frame.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(10,0))
        
        self.level_vars = {}
        levels = ["Undergraduate", "Postgraduate", "PhD", "Certificate", "Diploma"]
        for i, level in enumerate(levels):
            var = tk.BooleanVar()
            self.level_vars[level] = var
            ttk.Checkbutton(level_frame, text=level, variable=var).grid(row=i//2, column=i%2, sticky=tk.W)
        
        # Credit hours range
        credits_frame = ttk.LabelFrame(parent, text="Credit Hours", padding=10)
        credits_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(credits_frame, text="Min:").grid(row=0, column=0, sticky=tk.W)
        self.min_credits_var = tk.StringVar()
        ttk.Entry(credits_frame, textvariable=self.min_credits_var, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(credits_frame, text="Max:").grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        self.max_credits_var = tk.StringVar()
        ttk.Entry(credits_frame, textvariable=self.max_credits_var, width=10).grid(row=0, column=3, padx=5)
        
        # Enrollment filters
        enrollment_frame = ttk.LabelFrame(parent, text="Enrollment Criteria", padding=10)
        enrollment_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(enrollment_frame, text="Fill rate:").grid(row=0, column=0, sticky=tk.W)
        self.fill_rate_var = tk.StringVar(value="any")
        
        fill_options = [
            ("Any", "any"),
            ("Under 25%", "low"),
            ("25-75%", "medium"),
            ("Over 75%", "high"),
            ("Full", "full")
        ]
        
        for i, (text, value) in enumerate(fill_options):
            ttk.Radiobutton(enrollment_frame, text=text, variable=self.fill_rate_var, 
                           value=value).grid(row=i//3, column=(i%3)+1, sticky=tk.W)
    
    def create_results_display(self, parent):
        # Results treeview
        columns = ("Code", "Name", "Department", "Level", "Credits", "Enrollment", "Fill Rate", "Status")
        self.results_tree = ttk.Treeview(parent, columns=columns, show="headings")
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            if col == "Code":
                self.results_tree.column(col, width=80)
            elif col == "Name":
                self.results_tree.column(col, width=200)
            elif col in ["Department", "Level"]:
                self.results_tree.column(col, width=120)
            elif col == "Credits":
                self.results_tree.column(col, width=70)
            elif col == "Enrollment":
                self.results_tree.column(col, width=100)
            elif col == "Fill Rate":
                self.results_tree.column(col, width=80)
            elif col == "Status":
                self.results_tree.column(col, width=80)
        
        scrollbar_v = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.results_tree.yview)
        scrollbar_h = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)
        
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_v.grid(row=0, column=1, sticky="ns")
        scrollbar_h.grid(row=1, column=0, sticky="ew")
        
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        # Results summary
        self.results_summary = ttk.Label(parent, text="No search performed yet")
        self.results_summary.grid(row=2, column=0, columnspan=2, pady=5)
        
        # Double-click for details
        self.results_tree.bind("<Double-1>", self.show_course_details)
    
    def load_departments(self, parent):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT department FROM courses WHERE department IS NOT NULL ORDER BY department")
            departments = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            for i, dept in enumerate(departments):
                var = tk.BooleanVar()
                self.dept_vars[dept] = var
                ttk.Checkbutton(parent, text=dept, variable=var).grid(row=i//3, column=i%3, sticky=tk.W)
        except sqlite3.Error:
            pass
    
    def perform_search(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Build search query
            conditions = []
            params = []
            
            # Keyword search
            keyword = self.keyword_var.get().strip()
            if keyword:
                search_in = self.search_in_var.get()
                if search_in == "all":
                    conditions.append("(course_code LIKE ? OR course_name LIKE ? OR description LIKE ?)")
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
                elif search_in == "name":
                    conditions.append("course_name LIKE ?")
                    params.append(f"%{keyword}%")
                elif search_in == "description":
                    conditions.append("description LIKE ?")
                    params.append(f"%{keyword}%")
                elif search_in == "code":
                    conditions.append("course_code LIKE ?")
                    params.append(f"%{keyword}%")
            
            # Quick filters
            if self.only_active.get():
                conditions.append("status = 'Active'")
            
            if self.only_available.get():
                conditions.append("current_enrollment < max_enrollment")
            
            if self.online_only.get():
                conditions.append("online_available = 1")
            
            if self.no_lab.get():
                conditions.append("lab_required = 0")
            
            # Department filter
            selected_depts = [dept for dept, var in self.dept_vars.items() if var.get()]
            if selected_depts:
                placeholders = ','.join(['?' for _ in selected_depts])
                conditions.append(f"department IN ({placeholders})")
                params.extend(selected_depts)
            
            # Level filter
            selected_levels = [level for level, var in self.level_vars.items() if var.get()]
            if selected_levels:
                placeholders = ','.join(['?' for _ in selected_levels])
                conditions.append(f"level IN ({placeholders})")
                params.extend(selected_levels)
            
            # Credit hours filter
            if self.min_credits_var.get():
                try:
                    min_credits = float(self.min_credits_var.get())
                    conditions.append("credit_hours >= ?")
                    params.append(min_credits)
                except ValueError:
                    pass
            
            if self.max_credits_var.get():
                try:
                    max_credits = float(self.max_credits_var.get())
                    conditions.append("credit_hours <= ?")
                    params.append(max_credits)
                except ValueError:
                    pass
            
            # Fill rate filter
            fill_rate = self.fill_rate_var.get()
            if fill_rate != "any":
                if fill_rate == "low":
                    conditions.append("CAST(current_enrollment AS FLOAT) / max_enrollment < 0.25")
                elif fill_rate == "medium":
                    conditions.append("CAST(current_enrollment AS FLOAT) / max_enrollment BETWEEN 0.25 AND 0.75")
                elif fill_rate == "high":
                    conditions.append("CAST(current_enrollment AS FLOAT) / max_enrollment > 0.75")
                elif fill_rate == "full":
                    conditions.append("current_enrollment >= max_enrollment")
            
            # Build final query
            base_query = """
            SELECT course_code, course_name, department, level, credit_hours,
                   current_enrollment, max_enrollment, status
            FROM courses
            """
            
            if conditions:
                query = base_query + " WHERE " + " AND ".join(conditions)
            else:
                query = base_query
            
            query += " ORDER BY course_code"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Populate results
            for course in results:
                code, name, dept, level, credits, current, max_enroll, status = course
                enrollment_str = f"{current or 0}/{max_enroll or 0}"
                fill_rate = f"{(current or 0)/(max_enroll or 1)*100:.1f}%" if max_enroll else "N/A"
                
                self.results_tree.insert("", tk.END, values=(
                    code, name, dept or "N/A", level or "N/A", credits or "N/A",
                    enrollment_str, fill_rate, status
                ))
            
            # Update summary
            self.results_summary.config(text=f"Found {len(results)} courses matching search criteria")
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Search failed: {e}")
    
    def clear_search(self):
        # Clear all search fields
        self.keyword_var.set("")
        self.search_in_var.set("all")
        self.only_available.set(False)
        self.only_active.set(True)
        self.online_only.set(False)
        self.no_lab.set(False)
        self.min_credits_var.set("")
        self.max_credits_var.set("")
        self.fill_rate_var.set("any")
        
        # Clear department and level selections
        for var in self.dept_vars.values():
            var.set(False)
        for var in self.level_vars.values():
            var.set(False)
        
        # Clear results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        self.results_summary.config(text="Search cleared")
    
    def export_results(self):
        if not self.results_tree.get_children():
            messagebox.showwarning("No Results", "No search results to export.")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Export Search Results",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write headers
                    headers = ["Code", "Name", "Department", "Level", "Credits", "Enrollment", "Fill Rate", "Status"]
                    writer.writerow(headers)
                    
                    # Write data
                    for item in self.results_tree.get_children():
                        values = self.results_tree.item(item)['values']
                        writer.writerow(values)
                
                messagebox.showinfo("Export Complete", f"Results exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export results: {e}")
    
    def show_course_details(self, event):
        selection = self.results_tree.selection()
        if selection:
            values = self.results_tree.item(selection[0])['values']
            course_code = values[0]
            
            # Find course ID and show details
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,))
                result = cursor.fetchone()
                if result:
                    # Use existing course details method from main GUI
                    self.parent.view_course_details(cursor, result[0])
                conn.close()
            except sqlite3.Error:
                pass

class CourseAnalyticsDialog:
    """Standalone analytics dialog with charts and detailed statistics"""
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Analytics Dashboard")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create notebook for different analytics views
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Overview Tab
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text="Overview")
        self.create_overview_tab(overview_frame)
        
        # Department Analysis Tab
        dept_frame = ttk.Frame(notebook)
        notebook.add(dept_frame, text="Department Analysis")
        self.create_department_tab(dept_frame)
        
        # Trends Tab
        trends_frame = ttk.Frame(notebook)
        notebook.add(trends_frame, text="Trends")
        self.create_trends_tab(trends_frame)
        
        # Controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(controls_frame, text="Refresh Data", command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Load initial data
        self.refresh_all_data()
    
    def create_overview_tab(self, parent):
        # Key metrics frame
        metrics_frame = ttk.LabelFrame(parent, text="Key Metrics", padding=10)
        metrics_frame.pack(fill=tk.X, pady=5)
        
        # Create metric labels
        self.total_courses_label = ttk.Label(metrics_frame, text="Total Courses: -", font=("Arial", 12, "bold"))
        self.total_courses_label.grid(row=0, column=0, padx=20, pady=5)
        
        self.total_students_label = ttk.Label(metrics_frame, text="Total Students: -", font=("Arial", 12, "bold"))
        self.total_students_label.grid(row=0, column=1, padx=20, pady=5)
        
        self.avg_fill_rate_label = ttk.Label(metrics_frame, text="Avg Fill Rate: -", font=("Arial", 12, "bold"))
        self.avg_fill_rate_label.grid(row=0, column=2, padx=20, pady=5)
        
        self.available_spots_label = ttk.Label(metrics_frame, text="Available Spots: -", font=("Arial", 12, "bold"))
        self.available_spots_label.grid(row=1, column=0, padx=20, pady=5)
        
        self.active_courses_label = ttk.Label(metrics_frame, text="Active Courses: -", font=("Arial", 12, "bold"))
        self.active_courses_label.grid(row=1, column=1, padx=20, pady=5)
        
        # Charts frame (simplified text-based charts since GUI doesn't have matplotlib)
        charts_frame = ttk.LabelFrame(parent, text="Status Distribution", padding=10)
        charts_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.status_text = ScrolledText(charts_frame, height=15)
        self.status_text.pack(fill=tk.BOTH, expand=True)
    
    def create_department_tab(self, parent):
        # Department selector
        selector_frame = ttk.Frame(parent)
        selector_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(selector_frame, text="Department:").pack(side=tk.LEFT)
        self.dept_selector = ttk.Combobox(selector_frame, width=30)
        self.dept_selector.pack(side=tk.LEFT, padx=5)
        self.dept_selector.bind('<<ComboboxSelected>>', self.update_department_data)
        
        # Department details
        self.dept_details = ScrolledText(parent, height=25)
        self.dept_details.pack(fill=tk.BOTH, expand=True, pady=5)
    
    def create_trends_tab(self, parent):
        # Trends analysis
        trends_label = ttk.Label(parent, text="Course Trends Analysis", font=("Arial", 14, "bold"))
        trends_label.pack(pady=10)
        
        self.trends_text = ScrolledText(parent, height=25)
        self.trends_text.pack(fill=tk.BOTH, expand=True, pady=5)
    
    def refresh_all_data(self):
        self.load_overview_data()
        self.load_department_selector()
        self.load_trends_data()
    
    def load_overview_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Get key metrics
            cursor.execute("""
            SELECT 
                COUNT(*) as total_courses,
                SUM(COALESCE(current_enrollment, 0)) as total_students,
                SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                AVG(COALESCE(current_enrollment, 0)) as avg_enrollment,
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
            FROM courses
            """)
            
            metrics = cursor.fetchone()
            if metrics:
                total_courses, total_students, total_capacity, avg_enrollment, active_courses = metrics
                available_spots = total_capacity - total_students if total_capacity and total_students else 0
                avg_fill_rate = (total_students / total_capacity * 100) if total_capacity > 0 else 0
                
                self.total_courses_label.config(text=f"Total Courses: {total_courses}")
                self.total_students_label.config(text=f"Total Students: {total_students or 0}")
                self.avg_fill_rate_label.config(text=f"Avg Fill Rate: {avg_fill_rate:.1f}%")
                self.available_spots_label.config(text=f"Available Spots: {available_spots}")
                self.active_courses_label.config(text=f"Active Courses: {active_courses}")
            
            # Status distribution
            cursor.execute("SELECT status, COUNT(*) FROM courses GROUP BY status ORDER BY COUNT(*) DESC")
            status_data = cursor.fetchall()
            
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(tk.END, "COURSE STATUS DISTRIBUTION\n")
            self.status_text.insert(tk.END, "=" * 40 + "\n\n")
            
            for status, count in status_data:
                percentage = (count / total_courses * 100) if total_courses > 0 else 0
                bar = "█" * int(percentage / 5)  # Simple text bar chart
                self.status_text.insert(tk.END, f"{status:<12} {count:<6} {percentage:>6.1f}% {bar}\n")
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load overview data: {e}")
    
    def load_department_selector(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT DISTINCT COALESCE(department, 'Unknown') as dept FROM courses ORDER BY dept")
            departments = [row[0] for row in cursor.fetchall()]
            
            self.dept_selector['values'] = departments
            if departments:
                self.dept_selector.set(departments[0])
                self.update_department_data()
            
            conn.close()
        except sqlite3.Error:
            pass
    
    def update_department_data(self, event=None):
        selected_dept = self.dept_selector.get()
        if not selected_dept:
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            self.dept_details.delete(1.0, tk.END)
            self.dept_details.insert(tk.END, f"DEPARTMENT ANALYSIS: {selected_dept.upper()}\n")
            self.dept_details.insert(tk.END, "=" * 50 + "\n\n")
            
            # Department statistics
            cursor.execute("""
            SELECT 
                COUNT(*) as total_courses,
                SUM(COALESCE(current_enrollment, 0)) as total_students,
                SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                AVG(COALESCE(current_enrollment, 0)) as avg_enrollment,
                AVG(credit_hours) as avg_credits,
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
            FROM courses 
            WHERE COALESCE(department, 'Unknown') = ?
            """, (selected_dept,))
            
            stats = cursor.fetchone()
            if stats:
                total, students, capacity, avg_enroll, avg_credits, active = stats
                fill_rate = (students / capacity * 100) if capacity > 0 else 0
                
                self.dept_details.insert(tk.END, f"Total Courses: {total}\n")
                self.dept_details.insert(tk.END, f"Active Courses: {active}\n")
                self.dept_details.insert(tk.END, f"Total Students: {students or 0}\n")
                self.dept_details.insert(tk.END, f"Total Capacity: {capacity or 0}\n")
                self.dept_details.insert(tk.END, f"Fill Rate: {fill_rate:.1f}%\n")
                self.dept_details.insert(tk.END, f"Average Enrollment: {avg_enroll:.1f}\n")
                self.dept_details.insert(tk.END, f"Average Credits: {avg_credits:.1f}\n\n")
            
            # Top courses in department
            cursor.execute("""
            SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                   COALESCE(max_enrollment, 0) as capacity
            FROM courses 
            WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > 0
            ORDER BY enrolled DESC
            LIMIT 5
            """)
            
            popular_courses = cursor.fetchall()
            self.dept_details.insert(tk.END, "Most Popular Courses:\n")
            for code, name, enrolled, capacity in popular_courses:
                fill_rate = (enrolled / capacity * 100) if capacity > 0 else 0
                self.dept_details.insert(tk.END, f"  {code} - {name}: {enrolled}/{capacity} ({fill_rate:.1f}%)\n")

            self.dept_details.insert(tk.END, "\nCourses with Low Enrollment:\n")
            cursor.execute("""
            SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                   COALESCE(max_enrollment, 0) as capacity
            FROM courses
            WHERE COALESCE(department, 'Unknown') = ? AND status = 'Active' AND COALESCE(max_enrollment, 0) > 0
              AND COALESCE(current_enrollment, 0) < (COALESCE(max_enrollment, 0) * 0.3)
            ORDER BY enrolled ASC
            LIMIT 5
            """, (selected_dept,))

            low_enrollment = cursor.fetchall()
            for code, name, enrolled, capacity in low_enrollment:
                fill_rate = (enrolled / capacity * 100) if capacity > 0 else 0
                self.dept_details.insert(tk.END, f"  {code} - {name}: {enrolled}/{capacity} ({fill_rate:.1f}%)\n")

            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load department data: {e}")

    def load_trends_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            self.trends_text.delete(1.0, tk.END)
            self.trends_text.insert(tk.END, "COURSE TRENDS ANALYSIS\n")
            self.trends_text.insert(tk.END, "=" * 40 + "\n\n")

            # Most/least popular courses
            self.trends_text.insert(tk.END, "ENROLLMENT TRENDS:\n\n")

            cursor.execute("""
            SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrollment
            FROM courses
            WHERE status = 'Active'
            ORDER BY enrollment DESC
            LIMIT 10
            """)

            popular_courses = cursor.fetchall()
            if popular_courses:
                self.trends_text.insert(tk.END, "Most Popular Courses:\n")
                for code, name, enrollment in popular_courses:
                    self.trends_text.insert(tk.END, f"  {code} - {name}: {enrollment} students\n")

            self.trends_text.insert(tk.END, "\nCourses with Available Seats:\n")
            cursor.execute("""
            SELECT course_code, course_name,
                   COALESCE(current_enrollment, 0) as enrolled,
                   COALESCE(max_enrollment, 0) as capacity,
                   (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
            FROM courses
            WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > COALESCE(current_enrollment, 0)
            ORDER BY available DESC
            LIMIT 10
            """)

            available_courses = cursor.fetchall()
            for code, name, enrolled, capacity, available in available_courses:
                self.trends_text.insert(tk.END, f"  {code} - {name}: {available} seats available ({enrolled}/{capacity})\n")

            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load trends data: {e}")

    def export_report(self):
        filename = filedialog.asksaveasfilename(
            title="Export Analytics Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("COURSE ANALYTICS REPORT\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    # Export overview data
                    f.write("OVERVIEW METRICS:\n")
                    f.write(f"{self.total_courses_label.cget('text')}\n")
                    f.write(f"{self.total_students_label.cget('text')}\n")
                    f.write(f"{self.avg_fill_rate_label.cget('text')}\n")
                    f.write(f"{self.available_spots_label.cget('text')}\n")
                    f.write(f"{self.active_courses_label.cget('text')}\n\n")
                    
                    # Export status distribution
                    f.write(self.status_text.get(1.0, tk.END))
                    f.write("\n")
                    
                    # Export trends
                    f.write(self.trends_text.get(1.0, tk.END))
                
                messagebox.showinfo("Export Complete", f"Report exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export report: {e}")

class CourseValidationDialog:
    """Dialog for validating course data integrity and fixing issues"""
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Data Validation")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Course Data Validation", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Validation options
        options_frame = ttk.LabelFrame(main_frame, text="Validation Checks", padding=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.check_enrollment = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Check enrollment vs capacity", 
                       variable=self.check_enrollment).pack(anchor=tk.W)
        
        self.check_codes = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Validate course code formats", 
                       variable=self.check_codes).pack(anchor=tk.W)
        
        self.check_orphans = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Find orphaned records", 
                       variable=self.check_orphans).pack(anchor=tk.W)
        
        self.check_duplicates = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Check for duplicate course codes", 
                       variable=self.check_duplicates).pack(anchor=tk.W)
        
        self.check_missing = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Find missing required data", 
                       variable=self.check_missing).pack(anchor=tk.W)
        
        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Validation Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.results_text = ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Run Validation", command=self.run_validation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Fix Issues", command=self.fix_issues).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Report", command=self.export_validation_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        self.issues_found = []
    
    def run_validation(self):
        self.results_text.delete(1.0, tk.END)
        self.issues_found = []
        
        self.results_text.insert(tk.END, "COURSE DATA VALIDATION REPORT\n")
        self.results_text.insert(tk.END, "=" * 50 + "\n")
        self.results_text.insert(tk.END, f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            total_issues = 0
            
            # Check enrollment vs capacity
            if self.check_enrollment.get():
                self.results_text.insert(tk.END, "1. Checking enrollment vs capacity...\n")
                cursor.execute("""
                SELECT id, course_code, course_name, current_enrollment, max_enrollment
                FROM courses 
                WHERE COALESCE(current_enrollment, 0) > COALESCE(max_enrollment, 0)
                """)
                
                over_enrolled = cursor.fetchall()
                if over_enrolled:
                    self.results_text.insert(tk.END, f"   ❌ Found {len(over_enrolled)} courses over capacity:\n")
                    for course in over_enrolled:
                        self.results_text.insert(tk.END, f"      {course[1]} - {course[2]}: {course[3]}/{course[4]}\n")
                        self.issues_found.append(('over_enrolled', course))
                    total_issues += len(over_enrolled)
                else:
                    self.results_text.insert(tk.END, "   ✅ All courses within capacity\n")
                self.results_text.insert(tk.END, "\n")
            
            # Check course code formats
            if self.check_codes.get():
                self.results_text.insert(tk.END, "2. Validating course code formats...\n")
                cursor.execute("SELECT id, course_code, course_name FROM courses")
                all_courses = cursor.fetchall()
                
                invalid_codes = []
                for course in all_courses:
                    # Fixed regex pattern - expects format like "CS101" or "MATH201"
                    if not re.match(r'^[A-Z]{2,4}\d{2,3}$', course[1]):
                        invalid_codes.append(course)
                
                if invalid_codes:
                    self.results_text.insert(tk.END, f"   ❌ Found {len(invalid_codes)} courses with invalid codes:\n")
                    for course in invalid_codes:
                        self.results_text.insert(tk.END, f"      {course[1]} - {course[2]}\n")
                        self.issues_found.append(('invalid_code', course))
                    total_issues += len(invalid_codes)
                else:
                    self.results_text.insert(tk.END, "   ✅ All course codes valid\n")
                self.results_text.insert(tk.END, "\n")
            
            # Check for orphaned records
            if self.check_orphans.get():
                self.results_text.insert(tk.END, "3. Checking for orphaned records...\n")
                
                # Check prerequisites
                cursor.execute("""
                SELECT cp.id, cp.course_id, cp.prerequisite_course_id
                FROM course_prerequisites cp
                LEFT JOIN courses c1 ON cp.course_id = c1.id
                LEFT JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                WHERE c1.id IS NULL OR c2.id IS NULL
                """)
                orphaned_prereqs = cursor.fetchall()
                
                # Check schedules
                cursor.execute("""
                SELECT cs.id, cs.course_id
                FROM course_schedule cs
                LEFT JOIN courses c ON cs.course_id = c.id
                WHERE c.id IS NULL
                """)
                orphaned_schedules = cursor.fetchall()
                
                orphan_count = len(orphaned_prereqs) + len(orphaned_schedules)
                if orphan_count > 0:
                    self.results_text.insert(tk.END, f"   ❌ Found {orphan_count} orphaned records:\n")
                    self.results_text.insert(tk.END, f"      Prerequisites: {len(orphaned_prereqs)}\n")
                    self.results_text.insert(tk.END, f"      Schedules: {len(orphaned_schedules)}\n")
                    self.issues_found.append(('orphaned_prereqs', orphaned_prereqs))
                    self.issues_found.append(('orphaned_schedules', orphaned_schedules))
                    total_issues += orphan_count
                else:
                    self.results_text.insert(tk.END, "   ✅ No orphaned records found\n")
                self.results_text.insert(tk.END, "\n")
            
            # Check for duplicates
            if self.check_duplicates.get():
                self.results_text.insert(tk.END, "4. Checking for duplicate course codes...\n")
                cursor.execute("""
                SELECT course_code, COUNT(*) as count
                FROM courses
                GROUP BY course_code
                HAVING COUNT(*) > 1
                """)
                duplicates = cursor.fetchall()
                
                if duplicates:
                    self.results_text.insert(tk.END, f"   ❌ Found {len(duplicates)} duplicate course codes:\n")
                    for code, count in duplicates:
                        self.results_text.insert(tk.END, f"      {code}: {count} instances\n")
                        self.issues_found.append(('duplicate_code', (code, count)))
                    total_issues += len(duplicates)
                else:
                    self.results_text.insert(tk.END, "   ✅ No duplicate course codes found\n")
                self.results_text.insert(tk.END, "\n")
            
            # Check for missing required data
            if self.check_missing.get():
                self.results_text.insert(tk.END, "5. Checking for missing required data...\n")
                
                # Missing course names
                cursor.execute("SELECT id, course_code FROM courses WHERE course_name IS NULL OR course_name = ''")
                missing_names = cursor.fetchall()
                
                # Missing departments
                cursor.execute("SELECT id, course_code FROM courses WHERE department IS NULL OR department = ''")
                missing_depts = cursor.fetchall()
                
                missing_count = len(missing_names) + len(missing_depts)
                if missing_count > 0:
                    self.results_text.insert(tk.END, f"   ❌ Found {missing_count} records with missing data:\n")
                    if missing_names:
                        self.results_text.insert(tk.END, f"      Missing names: {len(missing_names)}\n")
                        self.issues_found.append(('missing_names', missing_names))
                    if missing_depts:
                        self.results_text.insert(tk.END, f"      Missing departments: {len(missing_depts)}\n")
                        self.issues_found.append(('missing_depts', missing_depts))
                    total_issues += missing_count
                else:
                    self.results_text.insert(tk.END, "   ✅ All required data present\n")
                self.results_text.insert(tk.END, "\n")
            
            # Summary
            self.results_text.insert(tk.END, f"VALIDATION SUMMARY:\n")
            self.results_text.insert(tk.END, f"Total issues found: {total_issues}\n")
            self.results_text.insert(tk.END, f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if total_issues > 0:
                self.results_text.insert(tk.END, "\nClick 'Fix Issues' to automatically resolve fixable problems.\n")
            
            conn.close()
            
        except sqlite3.Error as e:
            self.results_text.insert(tk.END, f"❌ Database error during validation: {e}\n")

    def load_department_data(self):
        selected_dept = self.dept_var.get()
        if not selected_dept:
            return
            
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            self.dept_details.delete(1.0, tk.END)
            
            # Department statistics
            cursor.execute("""
            SELECT 
                COUNT(*) as total_courses,
                SUM(COALESCE(current_enrollment, 0)) as total_enrollment,
                AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
            FROM courses 
            WHERE department = ? AND status = 'Active'
            """, (selected_dept,))
            
            stats = cursor.fetchone()
            if stats:
                self.dept_details.insert(tk.END, f"DEPARTMENT: {selected_dept}\n")
                self.dept_details.insert(tk.END, "=" * 30 + "\n")
                self.dept_details.insert(tk.END, f"Total Courses: {stats[0]}\n")
                self.dept_details.insert(tk.END, f"Total Enrollment: {stats[1]}\n")
                self.dept_details.insert(tk.END, f"Average Enrollment: {stats[2]:.1f}\n\n")
            
            # Top enrolled courses
            cursor.execute("""
            SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled
            FROM courses 
            WHERE COALESCE(department, 'Unknown') = ? AND status = 'Active'
            ORDER BY enrolled DESC
            LIMIT 5
            """, (selected_dept,))
            
            top_courses = cursor.fetchall()
            if top_courses:
                self.dept_details.insert(tk.END, "TOP ENROLLED COURSES:\n")
                for code, name, enrolled in top_courses:
                    self.dept_details.insert(tk.END, f"  {code} - {name}: {enrolled} students\n")
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load department data: {e}")

    def fix_issues(self):
        if not self.issues_found:
            messagebox.showinfo("No Issues", "No issues found to fix. Run validation first.")
            return
        
        if not messagebox.askyesno("Confirm Fix", "This will attempt to automatically fix found issues. Continue?"):
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            fixed_count = 0
            
            for issue_type, issue_data in self.issues_found:
                if issue_type == 'over_enrolled':
                    # Reset over-enrolled courses to capacity
                    for course in issue_data:
                        cursor.execute("UPDATE courses SET current_enrollment = max_enrollment WHERE id = ?", (course[0],))
                        fixed_count += 1
                
                elif issue_type == 'orphaned_prereqs':
                    # Remove orphaned prerequisites
                    for prereq in issue_data:
                        cursor.execute("DELETE FROM course_prerequisites WHERE id = ?", (prereq[0],))
                        fixed_count += 1
                
                elif issue_type == 'orphaned_schedules':
                    # Remove orphaned schedules
                    for schedule in issue_data:
                        cursor.execute("DELETE FROM course_schedule WHERE id = ?", (schedule[0],))
                        fixed_count += 1
                
                elif issue_type == 'missing_depts':
                    # Set missing departments to 'Unknown'
                    for course in issue_data:
                        cursor.execute("UPDATE courses SET department = 'Unknown' WHERE id = ?", (course[0],))
                        fixed_count += 1
            
            conn.commit()
            conn.close()
            
            self.results_text.insert(tk.END, f"\n✅ Fixed {fixed_count} issues automatically.\n")
            self.results_text.insert(tk.END, "Some issues may require manual intervention.\n")
            
            messagebox.showinfo("Fix Complete", f"Fixed {fixed_count} issues automatically.")
            
        except sqlite3.Error as e:
            messagebox.showerror("Fix Error", f"Failed to fix issues: {e}")
    
    def export_validation_report(self):
        filename = filedialog.asksaveasfilename(
            title="Export Validation Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.results_text.get(1.0, tk.END))
                messagebox.showinfo("Export Complete", f"Validation report exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export report: {e}")

class CreateScheduleDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Course Schedule")
        self.dialog.geometry("520x520")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self._ui()

    def _ui(self):
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Course
        course_frame = ttk.LabelFrame(frm, text="Course", padding=10); course_frame.pack(fill=tk.X, pady=5)
        ttk.Label(course_frame, text="Course:").grid(row=0, column=0, sticky=tk.W)
        self.course_combo = ttk.Combobox(course_frame, width=50); self.course_combo.grid(row=0, column=1, sticky=tk.W, padx=6)
        self._load_courses()

        # Instructor (optional)
        instr_frame = ttk.LabelFrame(frm, text="Instructor (optional)", padding=10); instr_frame.pack(fill=tk.X, pady=5)
        ttk.Label(instr_frame, text="Instructor:").grid(row=0, column=0, sticky=tk.W)
        self.instructor_combo = ttk.Combobox(instr_frame, width=50); self.instructor_combo.grid(row=0, column=1, sticky=tk.W, padx=6)
        self._load_instructors()

        # Term
        term_frame = ttk.LabelFrame(frm, text="Term", padding=10); term_frame.pack(fill=tk.X, pady=5)
        ttk.Label(term_frame, text="Semester:").grid(row=0, column=0, sticky=tk.W)
        self.semester_var = tk.StringVar(value="Fall")
        ttk.Combobox(term_frame, textvariable=self.semester_var, values=["Fall","Spring","Summer","Winter"], width=12)\
           .grid(row=0, column=1, sticky=tk.W, padx=6)
        ttk.Label(term_frame, text="Year:").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
        from datetime import datetime
        self.year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(term_frame, textvariable=self.year_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=6, pady=(6,0))

        # Meeting details (optional)
        mtg = ttk.LabelFrame(frm, text="Meeting Details (optional)", padding=10); mtg.pack(fill=tk.X, pady=5)
        ttk.Label(mtg, text="Start Time (HH:MM):").grid(row=0, column=0, sticky=tk.W)
        self.start_var = tk.StringVar(); ttk.Entry(mtg, textvariable=self.start_var, width=12).grid(row=0, column=1, sticky=tk.W, padx=6)
        ttk.Label(mtg, text="End Time (HH:MM):").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
        self.end_var = tk.StringVar(); ttk.Entry(mtg, textvariable=self.end_var, width=12).grid(row=1, column=1, sticky=tk.W, padx=6, pady=(6,0))
        ttk.Label(mtg, text="Days (e.g. Mon/Wed/Fri):").grid(row=2, column=0, sticky=tk.W, pady=(6,0))
        self.days_var = tk.StringVar(); ttk.Entry(mtg, textvariable=self.days_var, width=30).grid(row=2, column=1, sticky=tk.W, padx=6, pady=(6,0))
        ttk.Label(mtg, text="Classroom:").grid(row=3, column=0, sticky=tk.W, pady=(6,0))
        self.room_var = tk.StringVar(); ttk.Entry(mtg, textvariable=self.room_var, width=20).grid(row=3, column=1, sticky=tk.W, padx=6, pady=(6,0))

        # Buttons
        btns = ttk.Frame(frm); btns.pack(fill=tk.X, pady=12)
        ttk.Button(btns, text="Create", command=self._create).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load_courses(self):
        from university_system.infrastructure.database.db import sqlite3
        self._course_id = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            cur.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            rows = cur.fetchall(); conn.close()
            vals = [f"{r[1]} - {r[2]}" for r in rows]
            self._course_id = {f"{r[1]} - {r[2]}": r[0] for r in rows}
            self.course_combo['values'] = vals
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load courses: {e}")

    def _load_instructors(self):
        from university_system.infrastructure.database.db import sqlite3
        self._instr_id = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
            if not cur.fetchone():
                self.instructor_combo['values'] = []
                return
            cur.execute("SELECT id, first_name, last_name FROM instructors ORDER BY last_name, first_name")
            rows = cur.fetchall(); conn.close()
            vals = [f"{r[1]} {r[2]} (ID:{r[0]})" for r in rows]
            self._instr_id = {f"{r[1]} {r[2]} (ID:{r[0]})": r[0] for r in rows}
            self.instructor_combo['values'] = vals
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load instructors: {e}")

    def _create(self):
        from university_system.infrastructure.database.db import sqlite3
        # Validate
        course_key = self.course_combo.get().strip()
        if course_key not in self._course_id:
            messagebox.showwarning("Validation", "Select a course."); return
        try:
            year = int(self.year_var.get().strip())
        except ValueError:
            messagebox.showwarning("Validation", "Year must be a number."); return

        course_id = self._course_id[course_key]
        instr_key = self.instructor_combo.get().strip()
        instructor_id = self._instr_id.get(instr_key) if instr_key else None

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            # ensure table exists (matches your schema)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS course_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                instructor_id INTEGER,
                semester TEXT NOT NULL,
                year INTEGER NOT NULL,
                start_time TEXT,
                end_time TEXT,
                days_of_week TEXT,
                classroom TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(course_id) REFERENCES courses(id),
                FOREIGN KEY(instructor_id) REFERENCES instructors(id),
                UNIQUE(course_id, semester, year)
            )
            """)

            cur.execute("""
            INSERT INTO course_schedule
            (course_id, instructor_id, semester, year, start_time, end_time, days_of_week, classroom)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                course_id, instructor_id, self.semester_var.get().strip(), year,
                self.start_var.get().strip() or None,
                self.end_var.get().strip() or None,
                self.days_var.get().strip() or None,
                self.room_var.get().strip() or None
            ))
            conn.commit(); conn.close()
            messagebox.showinfo("Success", "Schedule created.")
            self.dialog.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "A schedule for this course/term already exists.")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to create schedule: {e}")

class RemovePrerequisiteDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Remove Course Prerequisite")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding=10)
        course_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(course_frame, text="Course:").pack(side=tk.LEFT)
        self.course_combo = ttk.Combobox(course_frame, width=50)
        self.course_combo.pack(side=tk.LEFT, padx=5)
        self.course_combo.bind('<<ComboboxSelected>>', self.load_prerequisites)
        
        # Prerequisites display
        prereq_frame = ttk.LabelFrame(main_frame, text="Current Prerequisites", padding=10)
        prereq_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("ID", "Code", "Name", "Type")
        self.prereq_tree = ttk.Treeview(prereq_frame, columns=columns, show="headings")
        
        for col in columns:
            self.prereq_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(prereq_frame, orient=tk.VERTICAL, command=self.prereq_tree.yview)
        self.prereq_tree.configure(yscrollcommand=scrollbar.set)
        
        self.prereq_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Remove Selected", command=self.remove_prerequisite).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        self.load_courses()
    
    def load_courses(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Get courses that have prerequisites
            cursor.execute("""
            SELECT DISTINCT c.id, c.course_code, c.course_name
            FROM courses c
            JOIN course_prerequisites cp ON c.id = cp.course_id
            ORDER BY c.course_code
            """)
            courses = cursor.fetchall()
            
            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.course_combo['values'] = course_options
            
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load courses: {e}")
    
    def load_prerequisites(self, event=None):
        selected_text = self.course_combo.get()
        if selected_text not in self.course_id_map:
            return
        
        course_id = self.course_id_map[selected_text]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT cp.id, c.course_code, c.course_name, 
                   CASE WHEN cp.is_required = 1 THEN 'Required' ELSE 'Recommended' END as type
            FROM course_prerequisites cp
            JOIN courses c ON cp.prerequisite_course_id = c.id
            WHERE cp.course_id = ?
            ORDER BY c.course_code
            """, (course_id,))
            
            prerequisites = cursor.fetchall()
            
            for item in self.prereq_tree.get_children():
                self.prereq_tree.delete(item)
            
            for prereq in prerequisites:
                self.prereq_tree.insert("", tk.END, values=prereq)
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load prerequisites: {e}")
    
    def remove_prerequisite(self):
        selection = self.prereq_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a prerequisite to remove.")
            return
        
        prereq_data = self.prereq_tree.item(selection[0])['values']
        prereq_id = prereq_data[0]
        prereq_code = prereq_data[1]
        prereq_name = prereq_data[2]
        
        if messagebox.askyesno("Confirm Removal", f"Remove prerequisite '{prereq_code} - {prereq_name}'?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM course_prerequisites WHERE id = ?", (prereq_id,))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Prerequisite removed successfully!")
                self.load_prerequisites()
                self.result = True
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to remove prerequisite: {e}")

class ManageCourseStatusDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Course Status")
        self.dialog.geometry("1200x800")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Course list with status
        columns = ("ID", "Code", "Name", "Current Status", "Enrollment")
        self.course_tree = ttk.Treeview(main_frame, columns=columns, show="headings")
        
        for col in columns:
            self.course_tree.heading(col, text=col)
            if col == "ID":
                self.course_tree.column(col, width=50)
            elif col == "Code":
                self.course_tree.column(col, width=80)
            elif col == "Name":
                self.course_tree.column(col, width=250)
            elif col == "Current Status":
                self.course_tree.column(col, width=120)
            elif col == "Enrollment":
                self.course_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=scrollbar.set)
        
        self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status change controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(controls_frame, text="New Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(controls_frame, textvariable=self.status_var,
                                   values=["Active", "Inactive", "Archived", "Cancelled"])
        status_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(controls_frame, text="Reason:").pack(side=tk.LEFT, padx=(20,5))
        self.reason_var = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.reason_var, width=30).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Update Status", command=self.update_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_courses).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        self.load_courses()
    
    def load_courses(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT id, course_code, course_name, status,
                   COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment
            FROM courses
            ORDER BY course_code
            """)
            courses = cursor.fetchall()
            
            for item in self.course_tree.get_children():
                self.course_tree.delete(item)
            
            for course in courses:
                self.course_tree.insert("", tk.END, values=course)
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load courses: {e}")
    
    def update_status(self):
        selection = self.course_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a course.")
            return
        
        new_status = self.status_var.get()
        if not new_status:
            messagebox.showwarning("No Status", "Please select a new status.")
            return
        
        course_data = self.course_tree.item(selection[0])['values']
        course_id = course_data[0]
        current_status = course_data[3]
        reason = self.reason_var.get()
        
        if new_status == current_status:
            messagebox.showinfo("Same Status", "Course already has this status.")
            return
        
        if messagebox.askyesno("Confirm Change", f"Change status from '{current_status}' to '{new_status}'?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute("UPDATE courses SET status = ? WHERE id = ?",
                              (new_status, course_id))
                
                # Log in history
                cursor.execute('''
                INSERT INTO course_history (course_id, field_name, old_value, new_value, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (course_id, 'status', current_status, new_status, self.auth.current_user, timestamp))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Status updated successfully!")
                self.load_courses()
                self.result = True
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to update status: {e}")

class BulkUpdateDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Bulk Update Courses")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Bulk Update Courses", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Selection criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Select Courses to Update", padding=10)
        criteria_frame.pack(fill=tk.X, pady=5)
        
        self.selection_method = tk.StringVar(value="department")
        
        ttk.Radiobutton(criteria_frame, text="By Department", variable=self.selection_method, 
                       value="department").pack(anchor=tk.W)
        ttk.Radiobutton(criteria_frame, text="By Level", variable=self.selection_method, 
                       value="level").pack(anchor=tk.W)
        ttk.Radiobutton(criteria_frame, text="By Status", variable=self.selection_method, 
                       value="status").pack(anchor=tk.W)
        
        ttk.Label(criteria_frame, text="Value:").pack(anchor=tk.W, pady=(10,0))
        self.criteria_value_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.criteria_value_var, width=30).pack(anchor=tk.W)
        
        # Update field
        update_frame = ttk.LabelFrame(main_frame, text="Field to Update", padding=10)
        update_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(update_frame, text="Field:").pack(anchor=tk.W)
        self.update_field = tk.StringVar(value="status")
        field_combo = ttk.Combobox(update_frame, textvariable=self.update_field,
                                  values=["status", "max_enrollment", "course_fee", "course_type"])
        field_combo.pack(anchor=tk.W, pady=2)
        
        ttk.Label(update_frame, text="New Value:").pack(anchor=tk.W, pady=(10,0))
        self.new_value_var = tk.StringVar()
        ttk.Entry(update_frame, textvariable=self.new_value_var, width=30).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Preview", command=self.preview_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Update", command=self.perform_update).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def preview_update(self):
        selection_method = self.selection_method.get()
        criteria_value = self.criteria_value_var.get().strip()
        
        if not criteria_value:
            messagebox.showwarning("Input Required", "Please enter a value for the selection criteria.")
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            query = f"SELECT course_code, course_name FROM courses WHERE {selection_method} = ?"
            cursor.execute(query, (criteria_value,))
            courses = cursor.fetchall()
            conn.close()
            
            if courses:
                preview_text = f"Courses that will be updated ({len(courses)}):\n\n"
                for code, name in courses:
                    preview_text += f"• {code} - {name}\n"
                
                messagebox.showinfo("Update Preview", preview_text)
            else:
                messagebox.showinfo("No Matches", "No courses match the specified criteria.")
                
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Preview failed: {e}")
    
    def perform_update(self):
        try:
            selection_method = self.selection_method.get()
            criteria_value = self.criteria_value_var.get().strip()
            update_field = self.update_field.get()
            new_value = self.new_value_var.get().strip()
            
            if not criteria_value or not new_value:
                messagebox.showwarning("Input Required", "Please fill in all fields.")
                return
            
            if not messagebox.askyesno("Confirm Update", 
                f"Update all courses where {selection_method} = '{criteria_value}'?\n\nField: {update_field}\nNew Value: {new_value}"):
                return
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            update_query = f"UPDATE courses SET {update_field} = ? WHERE {selection_method} = ?"
            cursor.execute(update_query, (new_value, criteria_value))
            
            updated_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Update Complete", f"Successfully updated {updated_count} courses.")
            self.result = True
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Update failed: {e}")

class ImportExportDialog:
    def __init__(self, parent, auth, operation="import"):
        self.parent = parent
        self.auth = auth
        self.operation = operation
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"{operation.capitalize()} Courses")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text=f"{self.operation.capitalize()} Courses", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        if self.operation == "import":
            self.create_import_widgets(main_frame)
        else:
            self.create_export_widgets(main_frame)
    
    def create_import_widgets(self, parent):
        # File selection
        file_frame = ttk.LabelFrame(parent, text="Select CSV File", padding=10)
        file_frame.pack(fill=tk.X, pady=5)
        
        self.file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="Browse", command=self.browse_file).pack(side=tk.RIGHT, padx=(5,0))
        
        # Requirements
        req_frame = ttk.LabelFrame(parent, text="CSV Requirements", padding=10)
        req_frame.pack(fill=tk.X, pady=5)
        
        requirements = [
            "• Required columns: course_code, course_name, department",
            "• Optional columns: description, level, credit_hours, max_enrollment, course_type",
            "• Course codes must be unique and follow format (e.g., CS101)",
            "• First row should contain column headers"
        ]
        
        for req in requirements:
            ttk.Label(req_frame, text=req).pack(anchor=tk.W)
        
        # Options
        options_frame = ttk.LabelFrame(parent, text="Import Options", padding=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.skip_duplicates = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Skip duplicate course codes", 
                       variable=self.skip_duplicates).pack(anchor=tk.W)
        
        self.validate_codes = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Validate course code format", 
                       variable=self.validate_codes).pack(anchor=tk.W)
        
        # Progress display
        self.progress_text = ScrolledText(parent, height=8)
        self.progress_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Import", command=self.import_courses).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def create_export_widgets(self, parent):
        # Filter options
        filter_frame = ttk.LabelFrame(parent, text="Export Filters", padding=10)
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="Department:").grid(row=0, column=0, sticky=tk.W)
        self.dept_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.dept_var, width=20).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(filter_frame, text="Level:").grid(row=1, column=0, sticky=tk.W)
        self.level_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.level_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(filter_frame, text="Status:").grid(row=2, column=0, sticky=tk.W)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(filter_frame, textvariable=self.status_var, 
                                   values=["", "Active", "Inactive", "Archived", "Cancelled"])
        status_combo.grid(row=2, column=1, sticky=tk.W, padx=5)
        
        # File location
        file_frame = ttk.LabelFrame(parent, text="Export Location", padding=10)
        file_frame.pack(fill=tk.X, pady=5)
        
        self.export_file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.export_file_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="Browse", command=self.browse_export_file).pack(side=tk.RIGHT, padx=(5,0))
        
        # Progress display
        self.progress_text = ScrolledText(parent, height=8)
        self.progress_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Export", command=self.export_courses).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select CSV file to import",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.file_var.set(filename)
    
    def browse_export_file(self):
        filename = filedialog.asksaveasfilename(
            title="Save CSV file",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.export_file_var.set(filename)
    
    def import_courses(self):
        file_path = self.file_var.get()
        if not file_path:
            messagebox.showwarning("No File", "Please select a CSV file to import.")
            return
        
        try:
            self.progress_text.delete(1.0, tk.END)
            self.progress_text.insert(tk.END, f"Starting import from {file_path}...\n")
            
            imported_count = 0
            error_count = 0
            
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                required_fields = ['course_code', 'course_name', 'department']
                if not all(field in reader.fieldnames for field in required_fields):
                    self.progress_text.insert(tk.END, f"ERROR: CSV must contain these required columns: {', '.join(required_fields)}\n")
                    return
                
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        course_code = row['course_code'].strip().upper()
                        course_name = row['course_name'].strip()
                        department = row['department'].strip()
                        
                        if not course_code or not course_name:
                            self.progress_text.insert(tk.END, f"Row {row_num}: Missing required fields\n")
                            error_count += 1
                            continue
                        
                        if self.validate_codes.get() and not re.match(r'^[A-Z]{2,4}\d{2,3}$', course_code):
                            self.progress_text.insert(tk.END, f"Row {row_num}: Invalid course code format: {course_code}\n")
                            error_count += 1
                            continue
                        
                        if self.skip_duplicates.get():
                            cursor.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,))
                            if cursor.fetchone():
                                self.progress_text.insert(tk.END, f"Row {row_num}: Skipping duplicate course code {course_code}\n")
                                error_count += 1
                                continue
                        
                        # Insert course
                        description = row.get('description', '').strip()
                        level = row.get('level', '').strip()
                        credit_hours = float(row.get('credit_hours', 3.0))
                        max_enrollment = int(row.get('max_enrollment', 30))
                        course_type = row.get('course_type', 'Core').strip()
                        
                        cursor.execute('''
                        INSERT INTO courses (
                            course_code, course_name, description, level, department,
                            credit_hours, max_enrollment, course_type, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (course_code, course_name, description, level, department,
                              credit_hours, max_enrollment, course_type, timestamp, timestamp))
                        
                        self.progress_text.insert(tk.END, f"Row {row_num}: Imported {course_code} - {course_name}\n")
                        imported_count += 1
                        
                    except (ValueError, sqlite3.Error) as e:
                        self.progress_text.insert(tk.END, f"Row {row_num}: Error - {e}\n")
                        error_count += 1
                        continue
                
                conn.commit()
                conn.close()
            
            self.progress_text.insert(tk.END, f"\nImport completed!\n")
            self.progress_text.insert(tk.END, f"Successfully imported: {imported_count} courses\n")
            self.progress_text.insert(tk.END, f"Errors: {error_count} courses\n")
            
            self.result = imported_count > 0
            
        except FileNotFoundError:
            messagebox.showerror("File Error", "File not found.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import CSV: {e}")
    
    def export_courses(self):
        file_path = self.export_file_var.get()
        if not file_path:
            messagebox.showwarning("No File", "Please specify a location to save the CSV file.")
            return
        
        try:
            self.progress_text.delete(1.0, tk.END)
            self.progress_text.insert(tk.END, f"Starting export to {file_path}...\n")
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Build query with filters
            conditions = []
            params = []
            
            if self.dept_var.get():
                conditions.append("department = ?")
                params.append(self.dept_var.get())
            
            if self.level_var.get():
                conditions.append("level = ?")
                params.append(self.level_var.get())
            
            if self.status_var.get():
                conditions.append("status = ?")
                params.append(self.status_var.get())
            
            query = "SELECT * FROM courses"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY course_code"
            
            cursor.execute(query, params)
            courses = cursor.fetchall()
            
            if not courses:
                self.progress_text.insert(tk.END, "No courses found to export.\n")
                conn.close()
                return
            
            # Get column names
            cursor.execute("PRAGMA table_info(courses)")
            columns = [col[1] for col in cursor.fetchall()]
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns)
                writer.writerows(courses)
            
            conn.close()
            
            self.progress_text.insert(tk.END, f"Exported {len(courses)} courses to {file_path}\n")
            self.result = True
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {e}")

class RecommendCoursesDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Recommendations")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Recommendation type selection
        type_frame = ttk.LabelFrame(main_frame, text="Recommendation Type", padding=10)
        type_frame.pack(fill=tk.X, pady=5)
        
        self.rec_type = tk.StringVar(value="popular")
        
        ttk.Radiobutton(type_frame, text="Most Popular Courses", variable=self.rec_type, 
                       value="popular").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="Courses with Available Spots", variable=self.rec_type, 
                       value="available").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="Under-enrolled Courses", variable=self.rec_type, 
                       value="under_enrolled").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="Prerequisites for Course", variable=self.rec_type, 
                       value="prerequisites").pack(anchor=tk.W, pady=2)
        
        # Course selection for prerequisites (conditional)
        self.prereq_frame = ttk.LabelFrame(main_frame, text="Select Course for Prerequisites", padding=10)
        self.prereq_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.prereq_frame, text="Course:").pack(side=tk.LEFT)
        self.prereq_course_combo = ttk.Combobox(self.prereq_frame, width=50)
        self.prereq_course_combo.pack(side=tk.LEFT, padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Recommendations", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.results_text = ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Generate Recommendations", command=self.generate_recommendations).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Bind radio button changes
        for widget in type_frame.winfo_children():
            if isinstance(widget, ttk.Radiobutton):
                widget.configure(command=self.on_type_change)
        
        self.load_courses()
        self.on_type_change()
    
    def load_courses(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
            
            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.prereq_course_combo['values'] = course_options
            
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load courses: {e}")
    
    def on_type_change(self):
        if self.rec_type.get() == "prerequisites":
            self.prereq_frame.pack(fill=tk.X, pady=5, before=self.results_text.master.master)
        else:
            self.prereq_frame.pack_forget()
    
    def generate_recommendations(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            rec_type = self.rec_type.get()
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "COURSE RECOMMENDATIONS\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n\n")
            
            if rec_type == "popular":
                self.results_text.insert(tk.END, "MOST POPULAR COURSES:\n\n")
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity,
                       ROUND(CAST(COALESCE(current_enrollment, 0) AS FLOAT) / COALESCE(max_enrollment, 1) * 100, 1) as popularity
                FROM courses 
                WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > 0
                ORDER BY enrolled DESC, popularity DESC
                LIMIT 10
                """)
                
                courses = cursor.fetchall()
                self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Enrolled':<10} {'Popularity':<12}\n")
                self.results_text.insert(tk.END, "-" * 62 + "\n")
                
                for code, name, enrolled, capacity, popularity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    self.results_text.insert(tk.END, f"{code:<10} {name_short:<30} {enrolled:<10} {popularity}%\n")
            
            elif rec_type == "available":
                self.results_text.insert(tk.END, "COURSES WITH AVAILABLE SPOTS:\n\n")
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity,
                       (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
                FROM courses 
                WHERE status = 'Active' AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
                ORDER BY available DESC
                LIMIT 15
                """)
                
                courses = cursor.fetchall()
                self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Available':<10} {'Total':<10}\n")
                self.results_text.insert(tk.END, "-" * 60 + "\n")
                
                for code, name, enrolled, capacity, available in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    self.results_text.insert(tk.END, f"{code:<10} {name_short:<30} {available:<10} {capacity:<10}\n")
            
            elif rec_type == "under_enrolled":
                self.results_text.insert(tk.END, "UNDER-ENROLLED COURSES (< 50% capacity):\n\n")
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity
                FROM courses 
                WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > 0
                  AND COALESCE(current_enrollment, 0) < (COALESCE(max_enrollment, 0) * 0.5)
                ORDER BY (CAST(COALESCE(current_enrollment, 0) AS FLOAT) / COALESCE(max_enrollment, 1))
                LIMIT 15
                """)
                
                courses = cursor.fetchall()
                self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Fill Rate':<10} {'Enrolled':<10}\n")
                self.results_text.insert(tk.END, "-" * 60 + "\n")
                
                for code, name, enrolled, capacity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "0%"
                    enrollment_str = f"{enrolled}/{capacity}"
                    self.results_text.insert(tk.END, f"{code:<10} {name_short:<30} {fill_rate:<10} {enrollment_str:<10}\n")
            
            elif rec_type == "prerequisites":
                selected_text = self.prereq_course_combo.get()
                if selected_text not in self.course_id_map:
                    messagebox.showwarning("No Course Selected", "Please select a course to view prerequisites.")
                    return
                
                course_id = self.course_id_map[selected_text]
                
                cursor.execute("""
                SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c1 ON cp.course_id = c1.id
                JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                WHERE cp.course_id = ?
                ORDER BY cp.is_required DESC, c2.course_code
                """, (course_id,))
                
                prereqs = cursor.fetchall()
                
                if prereqs:
                    course_info = prereqs[0]
                    self.results_text.insert(tk.END, f"PREREQUISITES FOR {course_info[0]} - {course_info[1]}:\n\n")
                    self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Type':<12}\n")
                    self.results_text.insert(tk.END, "-" * 52 + "\n")
                    
                    for prereq in prereqs:
                        req_type = "Required" if prereq[4] else "Recommended"
                        name_short = prereq[3][:27] + "..." if len(prereq[3]) > 30 else prereq[3]
                        self.results_text.insert(tk.END, f"{prereq[2]:<10} {name_short:<30} {req_type:<12}\n")
                else:
                    self.results_text.insert(tk.END, "No prerequisites found for this course.\n")
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate recommendations: {e}")

class ViewSchedulesDialog:
    def __init__(self, parent, auth):
        self.parent = parent; self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("View Course Schedules")
        self.dialog.geometry("900x520")
        self.dialog.transient(parent); self.dialog.grab_set()
        self._ui(); self._load()

    def _ui(self):
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cols = ("ID","Code","Name","Semester","Year","Time","Days","Room","Instructor")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c)
        self.tree.column("ID", width=50); self.tree.column("Code", width=90)
        self.tree.column("Name", width=240); self.tree.column("Semester", width=90)
        self.tree.column("Year", width=60); self.tree.column("Time", width=120)
        self.tree.column("Days", width=120); self.tree.column("Room", width=90)
        self.tree.column("Instructor", width=160)
        y = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); y.pack(side=tk.RIGHT, fill=tk.Y)

        btns = ttk.Frame(self.dialog); btns.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btns, text="Refresh", command=self._load).pack(side=tk.LEFT)
        ttk.Button(btns, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load(self):
        from university_system.infrastructure.database.db import sqlite3
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()

            # Load from course_schedule table
            cur.execute("""
            SELECT cs.id,
                   c.course_code, c.course_name,
                   cs.semester, cs.year,
                   COALESCE(cs.start_time,'') || CASE WHEN cs.end_time IS NOT NULL THEN '-'||cs.end_time ELSE '' END as time_slot,
                   COALESCE(cs.days_of_week,''), COALESCE(cs.classroom,''),
                   COALESCE(i.first_name||' '||i.last_name,'')
            FROM course_schedule cs
            JOIN courses c ON cs.course_id = c.id
            LEFT JOIN instructors i ON cs.instructor_id = i.id
            ORDER BY cs.year DESC, cs.semester, c.course_code
            """)
            rows = list(cur.fetchall())

            # Also load from module_schedule table
            cur.execute("""
            SELECT ms.id,
                   ms.module_code,
                   c.course_name,
                   '', '',
                   COALESCE(ms.start_time,'') || CASE WHEN ms.end_time IS NOT NULL THEN '-'||ms.end_time ELSE '' END as time_slot,
                   COALESCE(ms.day_of_week,''),
                   '',
                   COALESCE(i.first_name||' '||i.last_name,'')
            FROM module_schedule ms
            LEFT JOIN courses c ON ms.module_code = c.course_code
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            ORDER BY ms.module_code
            """)
            module_rows = cur.fetchall()
            rows.extend(module_rows)

            conn.close()
            for i in self.tree.get_children(): self.tree.delete(i)
            for r in rows: self.tree.insert("", tk.END, values=r)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load schedules: {e}")


class AddToWaitlistDialog:
    def __init__(self, parent, auth):
        self.parent = parent; self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add to Course Waitlist")
        self.dialog.geometry("420x240")
        self.dialog.transient(parent); self.dialog.grab_set()
        self._ui()

    def _ui(self):
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(frm, text="Course:").grid(row=0, column=0, sticky=tk.W)
        self.course_combo = ttk.Combobox(frm, width=45); self.course_combo.grid(row=0, column=1, sticky=tk.W, padx=6)
        ttk.Label(frm, text="Student ID:").grid(row=1, column=0, sticky=tk.W, pady=(8,0))
        self.student_var = tk.StringVar(); ttk.Entry(frm, textvariable=self.student_var, width=20)\
            .grid(row=1, column=1, sticky=tk.W, padx=6, pady=(8,0))

        self._load_courses()
        btns = ttk.Frame(frm); btns.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=12)
        ttk.Button(btns, text="Add", command=self._add).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load_courses(self):
        from university_system.infrastructure.database.db import sqlite3
        self._course_id = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            cur.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            rows = cur.fetchall(); conn.close()
            vals = [f"{r[1]} - {r[2]}" for r in rows]
            self._course_id = {f"{r[1]} - {r[2]}": r[0] for r in rows}
            self.course_combo['values'] = vals
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load courses: {e}")

    def _add(self):
        from university_system.infrastructure.database.db import sqlite3
        course_key = self.course_combo.get().strip()
        student_id = self.student_var.get().strip()
        if course_key not in self._course_id:
            messagebox.showwarning("Validation", "Select a course."); return
        if not student_id:
            messagebox.showwarning("Validation", "Enter a student ID."); return
        course_id = self._course_id[course_key]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=10.0)
            conn.execute("PRAGMA busy_timeout = 10000")
            cur = conn.cursor()
            # ensure waitlist table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS course_waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                added_at TEXT NOT NULL,
                status TEXT DEFAULT 'Waiting',
                FOREIGN KEY(course_id) REFERENCES courses(id),
                UNIQUE(course_id, student_id)
            )
            """)
            cur.execute("SELECT COALESCE(MAX(position),0) + 1 FROM course_waitlist WHERE course_id = ?", (course_id,))
            pos = cur.fetchone()[0] or 1
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute("INSERT INTO course_waitlist (course_id, student_id, position, added_at) VALUES (?, ?, ?, ?)",
                        (course_id, student_id, pos, timestamp))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"Added student {student_id} to waitlist (position {pos}).")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to add to waitlist: {e}")


class ViewWaitlistsDialog:
    def __init__(self, parent, auth):
        self.parent = parent; self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("View Course Waitlists")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent); self.dialog.grab_set()
        self._ui(); self._load()

    def _ui(self):
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        cols = ("ID","Code","Name","Student ID","Position","Status","Added")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c)
        self.tree.column("ID", width=60); self.tree.column("Code", width=90)
        self.tree.column("Name", width=240); self.tree.column("Student ID", width=120)
        self.tree.column("Position", width=80); self.tree.column("Status", width=90)
        self.tree.column("Added", width=140)
        y = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); y.pack(side=tk.RIGHT, fill=tk.Y)

        btns = ttk.Frame(self.dialog); btns.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btns, text="Refresh", command=self._load).pack(side=tk.LEFT)
        ttk.Button(btns, text="Remove Selected", command=self._remove).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load(self):
        from university_system.infrastructure.database.db import sqlite3
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cur = conn.cursor()
                cur.execute("""
                SELECT w.id, c.course_code, c.course_name, w.student_id, w.position, w.status, w.added_at
                FROM course_waitlist w
                JOIN courses c ON w.course_id = c.id
                ORDER BY c.course_code, w.position
                """)
                rows = cur.fetchall()
            for i in self.tree.get_children(): self.tree.delete(i)
            for r in rows: self.tree.insert("", tk.END, values=r)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load waitlists: {e}")

    def _remove(self):
        from university_system.infrastructure.database.db import sqlite3
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Pick a waitlist entry to remove."); return
        row = self.tree.item(sel[0])['values']; waitlist_id = row[0]
        if not messagebox.askyesno("Confirm", "Remove selected waitlist entry?"): return
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            # capture course to fix positions
            cur.execute("SELECT course_id, position FROM course_waitlist WHERE id = ?", (waitlist_id,))
            r = cur.fetchone()
            if not r:
                conn.close(); self._load(); return
            course_id, pos = r
            cur.execute("DELETE FROM course_waitlist WHERE id = ?", (waitlist_id,))
            # close the gap in positions for remaining 'Waiting'
            cur.execute("""
                UPDATE course_waitlist
                SET position = position - 1
                WHERE course_id = ? AND status = 'Waiting' AND position > ?
            """, (course_id, pos))
            conn.commit(); conn.close()
            self._load()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to remove entry: {e}")

class AlternativeCourseDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Find Alternative Courses")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Course selection
        selection_frame = ttk.LabelFrame(main_frame, text="Select Reference Course", padding=10)
        selection_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(selection_frame, text="Course:").pack(side=tk.LEFT)
        self.course_combo = ttk.Combobox(selection_frame, width=50)
        self.course_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(selection_frame, text="Find Alternatives", 
                  command=self.find_alternatives).pack(side=tk.RIGHT, padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Alternative Courses", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Code", "Name", "Department", "Level", "Match Type", "Available")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        
        for col in columns:
            self.results_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.load_course_options()
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def load_course_options(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, course_code, course_name FROM courses WHERE status = 'Active' ORDER BY course_code")
            courses = cursor.fetchall()
            
            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.course_combo['values'] = course_options
            
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load courses: {e}")
    
    def find_alternatives(self):
        selected_text = self.course_combo.get()
        if selected_text not in self.course_id_map:
            messagebox.showwarning("Selection Required", "Please select a course.")
            return
        
        course_id = self.course_id_map[selected_text]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Get reference course details
            cursor.execute("SELECT course_code, course_name, department, level, credit_hours FROM courses WHERE id = ?", (course_id,))
            ref_course = cursor.fetchone()
            
            if not ref_course:
                return
            
            ref_code, ref_name, ref_dept, ref_level, ref_credits = ref_course
            
            # Find alternatives
            alternatives = []
            
            # Same department and level
            cursor.execute("""
            SELECT course_code, course_name, department, level, 'Same Dept & Level' as match_type,
                   (max_enrollment - current_enrollment) as available
            FROM courses 
            WHERE department = ? AND level = ? AND id != ? AND status = 'Active'
            ORDER BY course_name
            """, (ref_dept, ref_level, course_id))
            alternatives.extend(cursor.fetchall())
            
            # Same department, different level
            cursor.execute("""
            SELECT course_code, course_name, department, level, 'Same Department' as match_type,
                   (max_enrollment - current_enrollment) as available
            FROM courses 
            WHERE department = ? AND level != ? AND id != ? AND status = 'Active'
            ORDER BY course_name
            """, (ref_dept, ref_level, course_id))
            alternatives.extend(cursor.fetchall())
            
            # Same level, different department
            cursor.execute("""
            SELECT course_code, course_name, department, level, 'Same Level' as match_type,
                   (max_enrollment - current_enrollment) as available
            FROM courses 
            WHERE level = ? AND department != ? AND id != ? AND status = 'Active'
            ORDER BY course_name
            """, (ref_level, ref_dept, course_id))
            alternatives.extend(cursor.fetchall())
            
            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Remove duplicates and populate tree
            seen = set()
            for alt in alternatives:
                key = alt[0]  # course_code
                if key not in seen:
                    seen.add(key)
                    self.results_tree.insert("", tk.END, values=alt)
            
            conn.close()
            
            if not alternatives:
                messagebox.showinfo("No Results", "No alternative courses found.")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to find alternatives: {e}")

class UpdateScheduleDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Update Course Schedule")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Show existing schedules
        self.schedule_tree = ttk.Treeview(main_frame, columns=("ID", "Code", "Name", "Semester", "Year", "Time"), show="headings")
        for col in ["ID", "Code", "Name", "Semester", "Year", "Time"]:
            self.schedule_tree.heading(col, text=col)
        self.schedule_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Update Selected", command=self.update_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_schedules).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        self.load_schedules()
    
    def load_schedules(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT cs.id, c.course_code, c.course_name, cs.semester, cs.year,
                   COALESCE(cs.start_time || '-' || cs.end_time, 'TBA') as time_slot
            FROM course_schedule cs
            JOIN courses c ON cs.course_id = c.id
            ORDER BY cs.year DESC, cs.semester, c.course_code
            """)
            
            schedules = cursor.fetchall()
            
            for item in self.schedule_tree.get_children():
                self.schedule_tree.delete(item)
            
            for schedule in schedules:
                self.schedule_tree.insert("", tk.END, values=schedule)
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load schedules: {e}")
    
    def update_schedule(self):
        selection = self.schedule_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a schedule to update.")
            return
        
        schedule_data = self.schedule_tree.item(selection[0])['values']
        schedule_id = schedule_data[0]
        
        # Open update form dialog
        UpdateScheduleFormDialog(self.dialog, schedule_id, self.auth)
        self.load_schedules()

class UpdateScheduleFormDialog:
    def __init__(self, parent, schedule_id, auth):
        self.parent = parent
        self.schedule_id = schedule_id
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Update Schedule Details")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.load_current_data()
        self.create_widgets()
        self.dialog.focus_set()
    
    def load_current_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM course_schedule WHERE id = ?", (self.schedule_id,))
            self.current_data = cursor.fetchone()
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load schedule: {e}")
            self.dialog.destroy()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Time fields
        ttk.Label(main_frame, text="Start Time (HH:MM):").pack(anchor=tk.W)
        self.start_time_var = tk.StringVar(value=self.current_data[4] or "")
        ttk.Entry(main_frame, textvariable=self.start_time_var, width=30).pack(anchor=tk.W, pady=2)
        
        ttk.Label(main_frame, text="End Time (HH:MM):").pack(anchor=tk.W, pady=(10,0))
        self.end_time_var = tk.StringVar(value=self.current_data[5] or "")
        ttk.Entry(main_frame, textvariable=self.end_time_var, width=30).pack(anchor=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Days of Week:").pack(anchor=tk.W, pady=(10,0))
        self.days_var = tk.StringVar(value=self.current_data[6] or "")
        ttk.Entry(main_frame, textvariable=self.days_var, width=40).pack(anchor=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Classroom:").pack(anchor=tk.W, pady=(10,0))
        self.classroom_var = tk.StringVar(value=self.current_data[7] or "")
        ttk.Entry(main_frame, textvariable=self.classroom_var, width=30).pack(anchor=tk.W, pady=2)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, text="Update", command=self.update_schedule).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def update_schedule(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            UPDATE course_schedule 
            SET start_time = ?, end_time = ?, days_of_week = ?, classroom = ?
            WHERE id = ?
            """, (self.start_time_var.get() or None, 
                  self.end_time_var.get() or None,
                  self.days_var.get() or None,
                  self.classroom_var.get() or None,
                  self.schedule_id))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", "Schedule updated successfully!")
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to update schedule: {e}")

class ProcessWaitlistDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Process Course Waitlists")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_waitlist_data()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Courses with Available Spots and Waitlists", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Course waitlist display
        columns = ("Course ID", "Code", "Name", "Available", "Waitlist Count")
        self.waitlist_tree = ttk.Treeview(main_frame, columns=columns, show="headings")
        
        for col in columns:
            self.waitlist_tree.heading(col, text=col)
            if col == "Course ID":
                self.waitlist_tree.column(col, width=80)
            elif col == "Code":
                self.waitlist_tree.column(col, width=80)
            elif col == "Name":
                self.waitlist_tree.column(col, width=250)
            else:
                self.waitlist_tree.column(col, width=100)
        
        self.waitlist_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Process Selected", command=self.process_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Process All", command=self.process_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_waitlist_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_waitlist_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT c.id, c.course_code, c.course_name,
                   (c.max_enrollment - c.current_enrollment) as available_spots,
                   COUNT(w.id) as waitlist_count
            FROM courses c
            LEFT JOIN course_waitlist w ON c.id = w.course_id AND w.status = 'Waiting'
            WHERE c.status = 'Active' AND c.current_enrollment < c.max_enrollment
            GROUP BY c.id, c.course_code, c.course_name, c.current_enrollment, c.max_enrollment
            HAVING waitlist_count > 0
            ORDER BY available_spots DESC, waitlist_count DESC
            """)
            
            courses = cursor.fetchall()
            
            for item in self.waitlist_tree.get_children():
                self.waitlist_tree.delete(item)
            
            for course in courses:
                self.waitlist_tree.insert("", tk.END, values=course)
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load waitlist data: {e}")
    
    def process_selected(self):
        selection = self.waitlist_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a course to process.")
            return
        
        course_data = self.waitlist_tree.item(selection[0])['values']
        course_id = course_data[0]
        
        if self.process_course_waitlist(course_id):
            self.load_waitlist_data()
    
    def process_all(self):
        if messagebox.askyesno("Confirm", "Process all waitlists? This will enroll students from waitlists where spots are available."):
            processed = 0
            for item in self.waitlist_tree.get_children():
                course_data = self.waitlist_tree.item(item)['values']
                course_id = course_data[0]
                if self.process_course_waitlist(course_id, show_messages=False):
                    processed += 1
            
            messagebox.showinfo("Complete", f"Processed waitlists for {processed} courses.")
            self.load_waitlist_data()
    
    def process_course_waitlist(self, course_id, show_messages=True):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Get course info and available spots
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment
            FROM courses WHERE id = ?
            """, (course_id,))
            
            course_info = cursor.fetchone()
            if not course_info:
                return False
            
            code, name, current_enrolled, max_enrolled = course_info
            available_spots = max_enrolled - current_enrolled
            
            if available_spots <= 0:
                if show_messages:
                    messagebox.showwarning("No Spots", f"No available spots in {code}")
                return False
            
            # Get waitlist students
            cursor.execute("""
            SELECT id, student_id FROM course_waitlist 
            WHERE course_id = ? AND status = 'Waiting'
            ORDER BY position
            LIMIT ?
            """, (course_id, available_spots))
            
            waitlist_students = cursor.fetchall()
            
            if not waitlist_students:
                return False
            
            # Process each student
            enrolled_count = 0
            for waitlist_id, student_id in waitlist_students:
                # Update waitlist status
                cursor.execute("UPDATE course_waitlist SET status = 'Enrolled' WHERE id = ?", (waitlist_id,))
                enrolled_count += 1
            
            # Update course enrollment
            cursor.execute("""
            UPDATE courses SET current_enrollment = current_enrollment + ?
            WHERE id = ?
            """, (enrolled_count, course_id))
            
            # Update remaining waitlist positions
            cursor.execute("""
            UPDATE course_waitlist 
            SET position = position - ?
            WHERE course_id = ? AND status = 'Waiting'
            """, (enrolled_count, course_id))
            
            conn.commit()
            conn.close()
            
            if show_messages:
                messagebox.showinfo("Success", f"Enrolled {enrolled_count} students from waitlist for {code}")
            
            return True
            
        except sqlite3.Error as e:
            if show_messages:
                messagebox.showerror("Database Error", f"Failed to process waitlist: {e}")
            return False

class CourseHistoryDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course History Viewer")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Course selection
        selection_frame = ttk.LabelFrame(main_frame, text="Course Selection", padding=10)
        selection_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(selection_frame, text="Course:").pack(side=tk.LEFT)
        self.course_combo = ttk.Combobox(selection_frame, width=50)
        self.course_combo.pack(side=tk.LEFT, padx=5)
        self.course_combo.bind('<<ComboboxSelected>>', self.load_history)
        
        ttk.Button(selection_frame, text="Show All Recent Changes", 
                  command=self.show_recent_changes).pack(side=tk.RIGHT, padx=5)
        
        # History display
        history_frame = ttk.LabelFrame(main_frame, text="Change History", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Date/Time", "Field", "Old Value", "New Value", "Changed By")
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show="headings")
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            if col == "Date/Time":
                self.history_tree.column(col, width=150)
            elif col in ["Old Value", "New Value"]:
                self.history_tree.column(col, width=150)
            else:
                self.history_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load course options
        self.load_course_options()
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def load_course_options(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
            
            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.course_combo['values'] = course_options
            
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load courses: {e}")
    
    def load_history(self, event=None):
        selected_text = self.course_combo.get()
        if selected_text not in self.course_id_map:
            return
        
        course_id = self.course_id_map[selected_text]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT field_name, old_value, new_value, changed_by, changed_at
            FROM course_history 
            WHERE course_id = ?
            ORDER BY changed_at DESC
            """, (course_id,))
            
            history = cursor.fetchall()
            
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            for entry in history:
                self.history_tree.insert("", tk.END, values=(entry[4], entry[0], entry[1], entry[2], entry[3]))
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load history: {e}")
    
    def show_recent_changes(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT c.course_code || ' - ' || c.course_name as course, 
                   ch.field_name, ch.old_value, ch.new_value, ch.changed_by, ch.changed_at
            FROM course_history ch
            JOIN courses c ON ch.course_id = c.id
            ORDER BY ch.changed_at DESC
            LIMIT 50
            """)
            
            changes = cursor.fetchall()
            
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            for change in changes:
                self.history_tree.insert("", tk.END, values=(change[5], f"{change[0]}: {change[1]}", 
                                                           change[2], change[3], change[4]))
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load recent changes: {e}")

class CourseCreateDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create New Course")
        self.dialog.geometry("600x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        # Main frame with scrollbar
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Basic Information
        basic_frame = ttk.LabelFrame(main_frame, text="Basic Information", padding=10)
        basic_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(basic_frame, text="Course Code:").grid(row=0, column=0, sticky=tk.W)
        self.code_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.code_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(basic_frame, text="Course Name:").grid(row=1, column=0, sticky=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.name_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(basic_frame, text="Description:").grid(row=2, column=0, sticky=tk.NW)
        self.desc_text = tk.Text(basic_frame, width=40, height=3)
        self.desc_text.grid(row=2, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(basic_frame, text="Department:").grid(row=3, column=0, sticky=tk.W)
        self.dept_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.dept_var, width=20).grid(row=3, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(basic_frame, text="Level:").grid(row=4, column=0, sticky=tk.W)
        self.level_var = tk.StringVar()
        level_combo = ttk.Combobox(basic_frame, textvariable=self.level_var, 
                                  values=["Undergraduate", "Postgraduate", "PhD", "Certificate", "Diploma"])
        level_combo.grid(row=4, column=1, sticky=tk.W, padx=5)
        
        # Academic Details
        academic_frame = ttk.LabelFrame(main_frame, text="Academic Details", padding=10)
        academic_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(academic_frame, text="Credit Hours:").grid(row=0, column=0, sticky=tk.W)
        self.credits_var = tk.StringVar(value="3.0")
        ttk.Entry(academic_frame, textvariable=self.credits_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(academic_frame, text="Max Enrollment:").grid(row=1, column=0, sticky=tk.W)
        self.max_enroll_var = tk.StringVar(value="30")
        ttk.Entry(academic_frame, textvariable=self.max_enroll_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(academic_frame, text="Course Type:").grid(row=2, column=0, sticky=tk.W)
        self.type_var = tk.StringVar(value="Core")
        type_combo = ttk.Combobox(academic_frame, textvariable=self.type_var,
                                 values=["Core", "Elective", "Major-specific", "General Education"])
        type_combo.grid(row=2, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(academic_frame, text="Course Fee:").grid(row=3, column=0, sticky=tk.W)
        self.fee_var = tk.StringVar(value="0.0")
        ttk.Entry(academic_frame, textvariable=self.fee_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5)
        
        # Additional Options
        options_frame = ttk.LabelFrame(main_frame, text="Additional Options", padding=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.lab_required = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Lab Required", variable=self.lab_required).grid(row=0, column=0, sticky=tk.W)
        
        self.online_available = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Online Available", variable=self.online_available).grid(row=0, column=1, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Create Course", command=self.create_course).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def create_course(self):
        try:
            # Validate inputs
            course_code = self.code_var.get().strip().upper()
            course_name = self.name_var.get().strip()
            
            if not course_code or not course_name:
                messagebox.showerror("Validation Error", "Course code and name are required.")
                return
            
            # Validate course code format
            if not re.match(r'^[A-Z]{2,4}\d{2,3}$', course_code):
                messagebox.showerror("Validation Error", "Invalid course code format. Use 2-4 letters followed by 2-3 numbers.")
                return
            
            description = self.desc_text.get(1.0, tk.END).strip()
            department = self.dept_var.get().strip()
            level = self.level_var.get().strip()
            
            try:
                credit_hours = float(self.credits_var.get())
                max_enrollment = int(self.max_enroll_var.get())
                course_fee = float(self.fee_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Please enter valid numbers for credits, enrollment, and fee.")
                return
            
            course_type = self.type_var.get()
            lab_required = self.lab_required.get()
            online_available = self.online_available.get()
            
            # Insert into database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Check for duplicate code
            cursor.execute("SELECT course_code FROM courses WHERE course_code = ?", (course_code,))
            if cursor.fetchone():
                messagebox.showerror("Duplicate Error", f"Course code '{course_code}' already exists.")
                conn.close()
                return
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO courses (
                course_code, course_name, description, level, department,
                credit_hours, max_enrollment, course_type, course_fee,
                lab_required, online_available, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (course_code, course_name, description, level, department,
                  credit_hours, max_enrollment, course_type, course_fee,
                  lab_required, online_available, timestamp, timestamp))
            # Mirror canonical columns into legacy alias columns if they exist
            try:
                last_id = cursor.lastrowid
                cursor.execute(
                    "UPDATE courses SET code = course_code, name = course_name, credits = credit_hours, date_added = COALESCE(date_added, created_at) WHERE id = ?",
                    (last_id,),
                )
            except Exception:
                pass
            
            conn.commit()
            conn.close()
            
            self.result = f"{course_code} - {course_name}"
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to create course: {e}")

class CourseEditDialog:
    def __init__(self, parent, auth, course_id):
        self.parent = parent
        self.auth = auth
        self.course_id = course_id
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Course")
        self.dialog.geometry("600x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.load_course_data()
        self.create_widgets()
        self.dialog.focus_set()
    
    def load_course_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM courses WHERE id = ?", (self.course_id,))
            self.course_data = cursor.fetchone()
            conn.close()
            
            if not self.course_data:
                messagebox.showerror("Error", "Course not found.")
                self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load course: {e}")
            self.dialog.destroy()
    
    def create_widgets(self):
        # Similar to create dialog but pre-populate with existing data
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Basic Information
        basic_frame = ttk.LabelFrame(main_frame, text="Basic Information", padding=10)
        basic_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(basic_frame, text="Course Code:").grid(row=0, column=0, sticky=tk.W)
        self.code_var = tk.StringVar(value=self.course_data[1])
        ttk.Entry(basic_frame, textvariable=self.code_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(basic_frame, text="Course Name:").grid(row=1, column=0, sticky=tk.W)
        self.name_var = tk.StringVar(value=self.course_data[2])
        ttk.Entry(basic_frame, textvariable=self.name_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(basic_frame, text="Description:").grid(row=2, column=0, sticky=tk.NW)
        self.desc_text = tk.Text(basic_frame, width=40, height=3)
        self.desc_text.grid(row=2, column=1, sticky=tk.W, padx=5)
        if len(self.course_data) > 3 and self.course_data[3]:
            self.desc_text.insert(1.0, self.course_data[3])
        
        # Add other fields similar to create dialog...
        # (For brevity, showing key fields)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Update Course", command=self.update_course).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def update_course(self):
        try:
            # Get updated values
            course_code = self.code_var.get().strip().upper()
            course_name = self.name_var.get().strip()
            description = self.desc_text.get(1.0, tk.END).strip()
            
            if not course_code or not course_name:
                messagebox.showerror("Validation Error", "Course code and name are required.")
                return
            
            # Update database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            UPDATE courses
            SET course_code = ?, course_name = ?, description = ?
            WHERE id = ?
            ''', (course_code, course_name, description, self.course_id))
            
            conn.commit()
            conn.close()
            
            self.result = True
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to update course: {e}")

class AdvancedSearchDialog:
    def __init__(self, parent):
        self.parent = parent
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Search")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Advanced Course Search", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Search criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Search Criteria", padding=10)
        criteria_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(criteria_frame, text="Keyword:").grid(row=0, column=0, sticky=tk.W)
        self.keyword_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.keyword_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Department:").grid(row=1, column=0, sticky=tk.W)
        self.department_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.department_var, width=30).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Level:").grid(row=2, column=0, sticky=tk.W)
        self.level_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.level_var, width=30).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Course Type:").grid(row=3, column=0, sticky=tk.W)
        self.type_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.type_var, width=30).grid(row=3, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Min Credits:").grid(row=4, column=0, sticky=tk.W)
        self.min_credits_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.min_credits_var, width=15).grid(row=4, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Max Credits:").grid(row=5, column=0, sticky=tk.W)
        self.max_credits_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.max_credits_var, width=15).grid(row=5, column=1, sticky=tk.W, padx=5)
        
        # Status filter
        self.show_available_only = tk.BooleanVar()
        ttk.Checkbutton(criteria_frame, text="Show only courses with available spots", 
                       variable=self.show_available_only).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Search", command=self.perform_search).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_fields).pack(side=tk.LEFT, padx=5)
    
    def clear_fields(self):
        for var in [self.keyword_var, self.department_var, self.level_var, self.type_var, 
                   self.min_credits_var, self.max_credits_var]:
            var.set("")
        self.show_available_only.set(False)
    
    def perform_search(self):
        self.result = {
            "keyword": self.keyword_var.get(),
            "department": self.department_var.get(),
            "level": self.level_var.get(),
            "course_type": self.type_var.get(),
            "min_credits": self.min_credits_var.get(),
            "max_credits": self.max_credits_var.get(),
            "available_only": self.show_available_only.get()
        }
        self.dialog.destroy()

class EnrollmentReportDialog:
    def __init__(self, parent):
        self.parent = parent
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Generate Enrollment Report")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Select Report Type", font=("Arial", 12, "bold")).pack(pady=10)
        
        self.report_type = tk.StringVar(value="Summary")
        
        report_frame = ttk.LabelFrame(main_frame, text="Report Options", padding=10)
        report_frame.pack(fill=tk.X, pady=10)
        
        ttk.Radiobutton(report_frame, text="Summary Report", variable=self.report_type, 
                       value="Summary").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text="Department Report", variable=self.report_type, 
                       value="Department").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text="Detailed Course Report", variable=self.report_type, 
                       value="Detailed").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text="Capacity Analysis", variable=self.report_type, 
                       value="Capacity").pack(anchor=tk.W, pady=2)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Generate", command=self.generate_report).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def generate_report(self):
        self.result = self.report_type.get()
        self.dialog.destroy()

class InstructorCreateDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Instructor")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Personal Information
        personal_frame = ttk.LabelFrame(main_frame, text="Personal Information", padding=10)
        personal_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(personal_frame, text="First Name:").grid(row=0, column=0, sticky=tk.W)
        self.first_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.first_name_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(personal_frame, text="Last Name:").grid(row=1, column=0, sticky=tk.W)
        self.last_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.last_name_var, width=25).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(personal_frame, text="Email:").grid(row=2, column=0, sticky=tk.W)
        self.email_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.email_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        # Professional Information
        prof_frame = ttk.LabelFrame(main_frame, text="Professional Information", padding=10)
        prof_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(prof_frame, text="Department:").grid(row=0, column=0, sticky=tk.W)
        self.department_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.department_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(prof_frame, text="Specialization:").grid(row=1, column=0, sticky=tk.W)
        self.specialization_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.specialization_var, width=35).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(prof_frame, text="Max Courses/Semester:").grid(row=2, column=0, sticky=tk.W)
        self.max_courses_var = tk.StringVar(value="4")
        ttk.Entry(prof_frame, textvariable=self.max_courses_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Max Hours/Week:").grid(row=3, column=0, sticky=tk.W)
        self.max_hours_var = tk.StringVar(value="40")
        ttk.Entry(prof_frame, textvariable=self.max_hours_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Scheduling Preferences
        sched_frame = ttk.LabelFrame(main_frame, text="Scheduling Preferences", padding=10)
        sched_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sched_frame, text="Preferred Days:").grid(row=0, column=0, sticky=tk.W)
        self.preferred_days_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_days_var, width=35).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text="(comma-separated, e.g., Monday,Tuesday)", font=('Arial', 8)).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(sched_frame, text="Preferred Times:").grid(row=2, column=0, sticky=tk.W)
        self.preferred_times_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_times_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text="(comma-separated, e.g., 09:00,10:00)", font=('Arial', 8)).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Add Instructor", command=self.add_instructor).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def add_instructor(self):
        try:
            # Validate inputs
            first_name = self.first_name_var.get().strip()
            last_name = self.last_name_var.get().strip()
            email = self.email_var.get().strip()
            
            if not first_name or not last_name or not email:
                messagebox.showerror("Validation Error", "First name, last name, and email are required.")
                return
            
            # Validate email format
            email_pattern = r'^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$'
            if not re.match(email_pattern, email):
                messagebox.showerror("Validation Error", "Please enter a valid email address.")
                return
            
            department = self.department_var.get().strip()
            specialization = self.specialization_var.get().strip()
            
            try:
                max_courses = int(self.max_courses_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Max courses must be a number.")
                return

            try:
                max_hours = int(self.max_hours_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Max hours must be a number.")
                return

            preferred_days = self.preferred_days_var.get().strip()
            preferred_times = self.preferred_times_var.get().strip()
            
            # Create instructors table if it doesn't exist
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS instructors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    department TEXT DEFAULT '',
                    specialization TEXT DEFAULT '',
                    max_courses_per_semester INTEGER DEFAULT 4,
                    max_hours_per_week INTEGER DEFAULT 40,
                    preferred_days TEXT,
                    preferred_times TEXT,
                    status TEXT DEFAULT 'Active',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                ''')

                # Check for duplicate email
                cursor.execute("SELECT email FROM instructors WHERE email = ?", (email,))
                if cursor.fetchone():
                    messagebox.showerror("Duplicate Error", f"Email '{email}' already exists.")
                    return

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO instructors (first_name, last_name, email, department, specialization,
                                       max_courses_per_semester, max_hours_per_week, preferred_days,
                                       preferred_times, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (first_name, last_name, email, department, specialization, max_courses,
                      max_hours, preferred_days, preferred_times, timestamp, timestamp))

                conn.commit()

            messagebox.showinfo("Success", f"Instructor {first_name} {last_name} added successfully.")
            self.result = f"{first_name} {last_name}"
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to add instructor: {e}")

class BulkUpdateDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Bulk Update Courses")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Bulk Update Courses", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Selection criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Select Courses to Update", padding=10)
        criteria_frame.pack(fill=tk.X, pady=5)
        
        self.selection_method = tk.StringVar(value="department")
        
        ttk.Radiobutton(criteria_frame, text="By Department", variable=self.selection_method, 
                       value="department").pack(anchor=tk.W)
        ttk.Radiobutton(criteria_frame, text="By Level", variable=self.selection_method, 
                       value="level").pack(anchor=tk.W)
        ttk.Radiobutton(criteria_frame, text="By Status", variable=self.selection_method, 
                       value="status").pack(anchor=tk.W)
        
        ttk.Label(criteria_frame, text="Value:").pack(anchor=tk.W, pady=(10,0))
        self.criteria_value_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.criteria_value_var, width=30).pack(anchor=tk.W)
        
        # Update field
        update_frame = ttk.LabelFrame(main_frame, text="Field to Update", padding=10)
        update_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(update_frame, text="Field:").pack(anchor=tk.W)
        self.update_field = tk.StringVar(value="status")
        field_combo = ttk.Combobox(update_frame, textvariable=self.update_field,
                                  values=["status", "max_enrollment", "course_fee", "course_type"])
        field_combo.pack(anchor=tk.W, pady=2)
        
        ttk.Label(update_frame, text="New Value:").pack(anchor=tk.W, pady=(10,0))
        self.new_value_var = tk.StringVar()
        ttk.Entry(update_frame, textvariable=self.new_value_var, width=30).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Preview", command=self.preview_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Update", command=self.perform_update).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def preview_update(self):
        # Show preview of courses that will be affected
        try:
            selection_method = self.selection_method.get()
            criteria_value = self.criteria_value_var.get().strip()
            
            if not criteria_value:
                messagebox.showwarning("Input Required", "Please enter a value for the selection criteria.")
                return
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            query = f"SELECT course_code, course_name FROM courses WHERE {selection_method} = ?"
            cursor.execute(query, (criteria_value,))
            courses = cursor.fetchall()
            conn.close()
            
            if courses:
                preview_text = f"Courses that will be updated ({len(courses)}):\n\n"
                for code, name in courses:
                    preview_text += f"• {code} - {name}\n"
                
                messagebox.showinfo("Update Preview", preview_text)
            else:
                messagebox.showinfo("No Matches", "No courses match the specified criteria.")
                
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Preview failed: {e}")
    
    def perform_update(self):
        try:
            selection_method = self.selection_method.get()
            criteria_value = self.criteria_value_var.get().strip()
            update_field = self.update_field.get()
            new_value = self.new_value_var.get().strip()
            
            if not criteria_value or not new_value:
                messagebox.showwarning("Input Required", "Please fill in all fields.")
                return
            
            # Confirm update
            if not messagebox.askyesno("Confirm Update", f"Update all courses where {selection_method} = '{criteria_value}'?\n\nField: {update_field}\nNew Value: {new_value}"):
                return
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            update_query = f"UPDATE courses SET {update_field} = ? WHERE {selection_method} = ?"
            cursor.execute(update_query, (new_value, criteria_value))

            # After performing the update, resynchronise any legacy alias
            # columns for all courses.  This ensures that if the caller
            # updated a canonical field (course_code, course_name or
            # credit_hours) the corresponding alias columns (code, name,
            # credits) remain in sync.  Performing the update for all
            # rows is inexpensive given the expected table size.
            try:
                cursor.execute(
                    "UPDATE courses SET code = course_code, name = course_name, credits = credit_hours, date_added = COALESCE(date_added, created_at)"
                )
            except Exception:
                pass
            
            updated_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Update Complete", f"Successfully updated {updated_count} courses.")
            self.result = True
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Update failed: {e}")

class PrerequisitesWindow:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.window = tk.Toplevel(parent)
        self.window.title("Manage Prerequisites")
        self.window.geometry("800x600")
        self.window.transient(parent)
        
        self.create_widgets()
        self.load_data()
    
    def create_widgets(self):
        # Prerequisites management interface
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(controls_frame, text="Add Prerequisite", command=self.add_prerequisite).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Remove Prerequisite", command=self.remove_prerequisite).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Refresh", command=self.load_data).pack(side=tk.LEFT, padx=5)
        
        # Prerequisites display
        self.prereq_text = ScrolledText(main_frame, wrap=tk.WORD, height=30)
        self.prereq_text.pack(fill=tk.BOTH, expand=True, pady=5)
    
    def load_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Check if prerequisites table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_prerequisites'")
            if not cursor.fetchone():
                prereq_text = "PREREQUISITES MANAGEMENT\n"
                prereq_text += "=" * 50 + "\n\n"
                prereq_text += "No prerequisites table found. Create some prerequisites first.\n"
            else:
                cursor.execute("""
                SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c1 ON cp.course_id = c1.id
                JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                ORDER BY c1.course_code, c2.course_code
                """)
                
                prereqs = cursor.fetchall()
                
                prereq_text = "PREREQUISITES MANAGEMENT\n"
                prereq_text += "=" * 50 + "\n\n"
                
                if prereqs:
                    current_course = None
                    for prereq in prereqs:
                        if current_course != prereq[0]:
                            current_course = prereq[0]
                            prereq_text += f"\n{prereq[0]} - {prereq[1]}:\n"
                        
                        req_type = "Required" if prereq[4] else "Recommended"
                        prereq_text += f"  → {prereq[2]} - {prereq[3]} ({req_type})\n"
                else:
                    prereq_text += "No prerequisites found in the system.\n"
            
            conn.close()
            
            self.prereq_text.delete(1.0, tk.END)
            self.prereq_text.insert(1.0, prereq_text)
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load prerequisites: {e}")
    
    def add_prerequisite(self):
        dialog = AddPrerequisiteDialog(self.window, self.auth)
        if dialog.result:
            self.load_data()
    
    def remove_prerequisite(self):
        """Show remove prerequisite dialog"""
        dialog = RemovePrerequisiteDialog(self.window, self.auth)
        if dialog.result:
            self.load_data()

class AddPrerequisiteDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Prerequisite")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_courses()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Add Course Prerequisite", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding=10)
        course_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(course_frame, text="Course:").pack(anchor=tk.W)
        self.course_combo = ttk.Combobox(course_frame, width=50)
        self.course_combo.pack(fill=tk.X, pady=2)
        
        # Prerequisite selection
        prereq_frame = ttk.LabelFrame(main_frame, text="Select Prerequisite", padding=10)
        prereq_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(prereq_frame, text="Prerequisite Course:").pack(anchor=tk.W)
        self.prereq_combo = ttk.Combobox(prereq_frame, width=50)
        self.prereq_combo.pack(fill=tk.X, pady=2)
        
        # Requirement type
        self.is_required = tk.BooleanVar(value=True)
        ttk.Checkbutton(prereq_frame, text="Required (uncheck for recommended)", 
                       variable=self.is_required).pack(anchor=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Add Prerequisite", command=self.add_prerequisite).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_courses(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
            
            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.course_combo['values'] = course_options
            self.prereq_combo['values'] = course_options
            
            # Store course IDs for mapping
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load courses: {e}")
    
    def add_prerequisite(self):
        try:
            course_text = self.course_combo.get()
            prereq_text = self.prereq_combo.get()
            
            if not course_text or not prereq_text:
                messagebox.showwarning("Selection Required", "Please select both course and prerequisite.")
                return
            
            if course_text == prereq_text:
                messagebox.showerror("Invalid Selection", "A course cannot be a prerequisite for itself.")
                return
            
            course_id = self.course_id_map.get(course_text)
            prereq_id = self.course_id_map.get(prereq_text)
            
            if not course_id or not prereq_id:
                messagebox.showerror("Error", "Invalid course selection.")
                return
            
            # Create prerequisites table if it doesn't exist
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
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
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO course_prerequisites (course_id, prerequisite_course_id, is_required, created_at)
            VALUES (?, ?, ?, ?)
            ''', (course_id, prereq_id, self.is_required.get(), timestamp))
            
            conn.commit()
            conn.close()
            
            self.result = True
            self.dialog.destroy()
            
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate Error", "This prerequisite already exists.")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to add prerequisite: {e}")

class RemovePrerequisiteDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Remove Prerequisite")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_prerequisites()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Remove Course Prerequisite", font=("Arial", 12, "bold")).pack(pady=10)

        # Prerequisites list
        prereq_frame = ttk.LabelFrame(main_frame, text="Current Prerequisites", padding=10)
        prereq_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create treeview for prerequisites
        columns = ("Course", "Prerequisite", "Type")
        self.prereq_tree = ttk.Treeview(prereq_frame, columns=columns, show="headings", height=10)

        self.prereq_tree.heading("Course", text="Course")
        self.prereq_tree.heading("Prerequisite", text="Prerequisite Course")
        self.prereq_tree.heading("Type", text="Type")

        self.prereq_tree.column("Course", width=150)
        self.prereq_tree.column("Prerequisite", width=150)
        self.prereq_tree.column("Type", width=100)

        # Scrollbar
        scrollbar = ttk.Scrollbar(prereq_frame, orient=tk.VERTICAL, command=self.prereq_tree.yview)
        self.prereq_tree.configure(yscrollcommand=scrollbar.set)

        self.prereq_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Remove Selected", command=self.remove_selected).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_prerequisites(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Get all prerequisites
            cursor.execute('''
            SELECT
                cp.id,
                c1.course_code || ' - ' || c1.course_name as course,
                c2.course_code || ' - ' || c2.course_name as prerequisite,
                CASE WHEN cp.is_required = 1 THEN 'Required' ELSE 'Recommended' END as type
            FROM course_prerequisites cp
            JOIN courses c1 ON cp.course_id = c1.id
            JOIN courses c2 ON cp.prerequisite_course_id = c2.id
            ORDER BY c1.course_code, c2.course_code
            ''')

            prerequisites = cursor.fetchall()
            conn.close()

            # Clear existing items
            for item in self.prereq_tree.get_children():
                self.prereq_tree.delete(item)

            # Add prerequisites to tree
            for prereq in prerequisites:
                self.prereq_tree.insert('', tk.END, values=(prereq[1], prereq[2], prereq[3]), tags=(prereq[0],))

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load prerequisites: {e}")

    def remove_selected(self):
        selected = self.prereq_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a prerequisite to remove.")
            return

        # Confirm removal
        if not messagebox.askyesno("Confirm Removal", "Are you sure you want to remove this prerequisite?"):
            return

        try:
            prereq_id = self.prereq_tree.item(selected[0])['tags'][0]

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute('DELETE FROM course_prerequisites WHERE id = ?', (prereq_id,))

            conn.commit()
            conn.close()

            # Remove from tree
            self.prereq_tree.delete(selected[0])

            self.result = True
            messagebox.showinfo("Success", "Prerequisite removed successfully")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to remove prerequisite: {e}")

class AssignInstructorDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Assign Instructor to Course")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_data()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Assign Instructor to Course", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding=10)
        course_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(course_frame, text="Course:").pack(anchor=tk.W)
        self.course_combo = ttk.Combobox(course_frame, width=50)
        self.course_combo.pack(fill=tk.X, pady=2)
        
        # Instructor selection
        instructor_frame = ttk.LabelFrame(main_frame, text="Select Instructor", padding=10)
        instructor_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(instructor_frame, text="Instructor:").pack(anchor=tk.W)
        self.instructor_combo = ttk.Combobox(instructor_frame, width=50)
        self.instructor_combo.pack(fill=tk.X, pady=2)
        
        # Schedule information
        schedule_frame = ttk.LabelFrame(main_frame, text="Schedule Information", padding=10)
        schedule_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(schedule_frame, text="Semester:").grid(row=0, column=0, sticky=tk.W)
        self.semester_var = tk.StringVar(value="Fall")
        semester_combo = ttk.Combobox(schedule_frame, textvariable=self.semester_var,
                                     values=["Fall", "Spring", "Summer", "Winter"])
        semester_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(schedule_frame, text="Year:").grid(row=1, column=0, sticky=tk.W)
        self.year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(schedule_frame, textvariable=self.year_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Assign", command=self.assign_instructor).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Load courses
            cursor.execute("SELECT id, course_code, course_name FROM courses WHERE status = 'Active' ORDER BY course_code")
            courses = cursor.fetchall()
            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.course_combo['values'] = course_options
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
            # Load instructors
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
            if cursor.fetchone():
                cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE status = 'Active' ORDER BY last_name")
                instructors = cursor.fetchall()
                instructor_options = [f"{instructor[1]} {instructor[2]}" for instructor in instructors]
                self.instructor_combo['values'] = instructor_options
                self.instructor_id_map = {f"{instructor[1]} {instructor[2]}": instructor[0] for instructor in instructors}
            else:
                self.instructor_combo['values'] = ["No instructors found"]
                self.instructor_id_map = {}
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load data: {e}")
    
    def assign_instructor(self):
        try:
            course_text = self.course_combo.get()
            instructor_text = self.instructor_combo.get()
            semester = self.semester_var.get()
            year = self.year_var.get()
            
            if not course_text or not instructor_text:
                messagebox.showwarning("Selection Required", "Please select both course and instructor.")
                return
            
            course_id = self.course_id_map.get(course_text)
            instructor_id = self.instructor_id_map.get(instructor_text)
            
            if not course_id or not instructor_id:
                messagebox.showerror("Error", "Invalid selection.")
                return
            
            try:
                year_int = int(year)
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid year.")
                return
            
            # Create schedule table if it doesn't exist and assign instructor
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
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
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Check if schedule exists
            cursor.execute("SELECT id FROM course_schedule WHERE course_id = ? AND semester = ? AND year = ?",
                          (course_id, semester, year_int))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing schedule
                cursor.execute("UPDATE course_schedule SET instructor_id = ? WHERE id = ?",
                              (instructor_id, existing[0]))
            else:
                # Create new schedule
                cursor.execute('''
                INSERT INTO course_schedule (course_id, semester, year, instructor_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                ''', (course_id, semester, year_int, instructor_id, timestamp))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"Instructor assigned to {course_text} for {semester} {year}")
            self.result = True
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to assign instructor: {e}")

class MaintenanceDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("System Maintenance")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="System Maintenance", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Maintenance options
        options_frame = ttk.LabelFrame(main_frame, text="Maintenance Tasks", padding=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(options_frame, text="Database Integrity Check", 
                  command=self.integrity_check).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="Clean Orphaned Records", 
                  command=self.clean_orphaned).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="Recalculate Enrollment Numbers", 
                  command=self.recalculate_enrollment).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="Database Statistics", 
                  command=self.show_db_stats).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="Optimize Database", 
                  command=self.optimize_db).pack(fill=tk.X, pady=2)
        
        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.results_text = ScrolledText(results_frame, wrap=tk.WORD, height=15)
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def integrity_check(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            results = "DATABASE INTEGRITY CHECK\n"
            results += "=" * 40 + "\n\n"
            
            issues = []
            
            # Check for courses with invalid enrollment
            cursor.execute("""
            SELECT course_code, current_enrollment, max_enrollment
            FROM courses 
            WHERE COALESCE(current_enrollment, 0) > COALESCE(max_enrollment, 0)
            """)
            over_enrolled = cursor.fetchall()
            
            if over_enrolled:
                issues.append(f"Found {len(over_enrolled)} courses with enrollment over capacity")
                results += "Courses over capacity:\n"
                for code, current, max_val in over_enrolled:
                    results += f"  - {code}: {current}/{max_val}\n"
                results += "\n"
            
            # Check for negative enrollments
            cursor.execute("SELECT course_code FROM courses WHERE COALESCE(current_enrollment, 0) < 0")
            negative_enrollments = cursor.fetchall()
            
            if negative_enrollments:
                issues.append(f"Found {len(negative_enrollments)} courses with negative enrollment")
                results += "Courses with negative enrollment:\n"
                for (code,) in negative_enrollments:
                    results += f"  - {code}\n"
                results += "\n"
            
            if not issues:
                results += "✓ No integrity issues found.\n"
            else:
                results += f"⚠ Found {len(issues)} types of issues:\n"
                for issue in issues:
                    results += f"  - {issue}\n"
            
            conn.close()
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Integrity check failed: {e}")
    
    def clean_orphaned(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            results = "CLEANING ORPHANED RECORDS\n"
            results += "=" * 40 + "\n\n"
            
            total_deleted = 0
            
            # Clean orphaned prerequisites
            if self.table_exists(cursor, 'course_prerequisites'):
                cursor.execute("""
                DELETE FROM course_prerequisites 
                WHERE course_id NOT IN (SELECT id FROM courses)
                   OR prerequisite_course_id NOT IN (SELECT id FROM courses)
                """)
                deleted_prereqs = cursor.rowcount
                total_deleted += deleted_prereqs
                results += f"Removed {deleted_prereqs} orphaned prerequisites\n"
            
            # Clean orphaned schedules
            if self.table_exists(cursor, 'course_schedule'):
                cursor.execute("DELETE FROM course_schedule WHERE course_id NOT IN (SELECT id FROM courses)")
                deleted_schedules = cursor.rowcount
                total_deleted += deleted_schedules
                results += f"Removed {deleted_schedules} orphaned schedules\n"
            
            # Clean orphaned waitlists
            if self.table_exists(cursor, 'course_waitlist'):
                cursor.execute("DELETE FROM course_waitlist WHERE course_id NOT IN (SELECT id FROM courses)")
                deleted_waitlists = cursor.rowcount
                total_deleted += deleted_waitlists
                results += f"Removed {deleted_waitlists} orphaned waitlist entries\n"
            
            conn.commit()
            conn.close()
            
            results += f"\n✓ Cleanup completed. Total records removed: {total_deleted}\n"
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Cleanup failed: {e}")
    
    def recalculate_enrollment(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            results = "RECALCULATING ENROLLMENT NUMBERS\n"
            results += "=" * 40 + "\n\n"
            
            # Find courses with invalid enrollment
            cursor.execute("""
            SELECT id, course_code, current_enrollment, max_enrollment
            FROM courses
            WHERE COALESCE(current_enrollment, 0) < 0 
               OR COALESCE(current_enrollment, 0) > COALESCE(max_enrollment, 0)
            """)
            
            invalid_enrollments = cursor.fetchall()
            
            if invalid_enrollments:
                results += f"Found {len(invalid_enrollments)} courses with invalid enrollment:\n"
                for course_id, code, current, max_val in invalid_enrollments:
                    results += f"  - {code}: {current}/{max_val}\n"
                
                if messagebox.askyesno("Reset Enrollments", "Reset invalid enrollments to 0?"):
                    cursor.execute("""
                    UPDATE courses
                    SET current_enrollment = 0
                    WHERE COALESCE(current_enrollment, 0) < 0
                       OR COALESCE(current_enrollment, 0) > COALESCE(max_enrollment, 0)
                    """)
                    
                    updated = cursor.rowcount
                    conn.commit()
                    results += f"\n✓ Reset {updated} invalid enrollments to 0\n"
                else:
                    results += "\nNo changes made.\n"
            else:
                results += "✓ All enrollment numbers are valid.\n"
            
            conn.close()
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Recalculation failed: {e}")
    
    def show_db_stats(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            results = "DATABASE STATISTICS\n"
            results += "=" * 40 + "\n\n"
            
            # Table counts
            tables = ['courses', 'course_prerequisites', 'course_schedule', 'instructors']
            for table in tables:
                if self.table_exists(cursor, table):
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    results += f"{table}: {count} records\n"
                else:
                    results += f"{table}: Table not found\n"
            
            # Database size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            
            db_size_mb = (page_count * page_size) / (1024 * 1024)
            results += f"\nDatabase size: {db_size_mb:.2f} MB\n"
            
            # Additional stats
            cursor.execute("SELECT COUNT(*) FROM courses WHERE status = 'Active'")
            active_courses = cursor.fetchone()[0]
            results += f"Active courses: {active_courses}\n"
            
            cursor.execute("SELECT SUM(COALESCE(current_enrollment, 0)) FROM courses WHERE status = 'Active'")
            total_enrollment = cursor.fetchone()[0] or 0
            results += f"Total enrollment: {total_enrollment}\n"
            
            conn.close()
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Statistics failed: {e}")
    
    def optimize_db(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            results = "DATABASE OPTIMIZATION\n"
            results += "=" * 40 + "\n\n"
            
            # Vacuum database
            results += "Running VACUUM...\n"
            cursor.execute("VACUUM")
            
            # Analyze database
            results += "Running ANALYZE...\n"
            cursor.execute("ANALYZE")
            
            conn.commit()
            conn.close()
            
            results += "\n✓ Database optimization completed.\n"
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            self.result = True
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Optimization failed: {e}")
    
    def table_exists(self, cursor, table_name):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None

class RecommendationsDialog:
    def __init__(self, parent):
        self.parent = parent
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Recommendations")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Course Recommendations", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Recommendation types
        types_frame = ttk.LabelFrame(main_frame, text="Recommendation Type", padding=10)
        types_frame.pack(fill=tk.X, pady=5)
        
        self.rec_type = tk.StringVar(value="popular")
        
        ttk.Radiobutton(types_frame, text="Most Popular Courses", variable=self.rec_type, 
                       value="popular").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(types_frame, text="Courses with Available Spots", variable=self.rec_type, 
                       value="available").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(types_frame, text="Under-enrolled Courses", variable=self.rec_type, 
                       value="under_enrolled").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(types_frame, text="New Courses", variable=self.rec_type, 
                       value="new").pack(anchor=tk.W, pady=2)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Generate Recommendations", command=self.generate_recommendations).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def generate_recommendations(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            rec_type = self.rec_type.get()
            
            recommendations = "COURSE RECOMMENDATIONS\n"
            recommendations += "=" * 50 + "\n\n"
            
            if rec_type == "popular":
                recommendations += "MOST POPULAR COURSES:\n\n"
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity
                FROM courses 
                WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > 0
                ORDER BY enrolled DESC
                LIMIT 10
                """)
                
                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Enrolled':<10} {'Capacity':<10}\n"
                recommendations += "-" * 60 + "\n"
                
                for code, name, enrolled, capacity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    recommendations += f"{code:<10} {name_short:<30} {enrolled:<10} {capacity:<10}\n"
                    
            elif rec_type == "available":
                recommendations += "COURSES WITH AVAILABLE SPOTS:\n\n"
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity,
                       (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
                FROM courses 
                WHERE status = 'Active' AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
                ORDER BY available DESC
                LIMIT 15
                """)
                
                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Available':<10} {'Total':<10}\n"
                recommendations += "-" * 60 + "\n"
                
                for code, name, enrolled, capacity, available in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    recommendations += f"{code:<10} {name_short:<30} {available:<10} {capacity:<10}\n"
                    
            elif rec_type == "under_enrolled":
                recommendations += "UNDER-ENROLLED COURSES (< 50% capacity):\n\n"
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity
                FROM courses 
                WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > 0
                  AND COALESCE(current_enrollment, 0) < (COALESCE(max_enrollment, 0) * 0.5)
                ORDER BY (CAST(current_enrollment AS FLOAT) / max_enrollment)
                LIMIT 15
                """)
                
                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Fill Rate':<10} {'Enrolled':<10}\n"
                recommendations += "-" * 60 + "\n"
                
                for code, name, enrolled, capacity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "0%"
                    enrollment_str = f"{enrolled}/{capacity}"
                    recommendations += f"{code:<10} {name_short:<30} {fill_rate:<10} {enrollment_str:<10}\n"
                    
            elif rec_type == "new":
                recommendations += "RECENTLY CREATED COURSES:\n\n"
                cursor.execute("""
                SELECT course_code, course_name, created_at, status
                FROM courses 
                WHERE created_at >= date('now', '-6 months')
                ORDER BY created_at DESC
                LIMIT 10
                """)
                
                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Created':<12} {'Status':<10}\n"
                recommendations += "-" * 62 + "\n"
                
                for code, name, created, status in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    created_date = created.split()[0] if created else "Unknown"
                    recommendations += f"{code:<10} {name_short:<30} {created_date:<12} {status:<10}\n"
            
            conn.close()
            
            if not courses:
                recommendations += "No recommendations found for the selected criteria.\n"
            
            self.result = recommendations
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate recommendations: {e}")

    # =====================================================================
    # VALIDATION HELPER METHODS (Functions 2-5)
    # =====================================================================

    def validate_course_code(self, code):
        """Validate the course code format (e.g., CS101, MATH200)"""
        pattern = r'^[A-Z]{2,4}\d{2,3}$'
        return bool(re.match(pattern, code))

    def validate_email(self, email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def validate_time_format(self, time_str):
        """Validate time format (HH:MM)"""
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        return bool(re.match(pattern, time_str))

    def validate_days_of_week(self, days_str):
        """Validate days of week format"""
        valid_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}
        days = [day.strip() for day in days_str.split(',')]
        return all(day in valid_days for day in days)

    # =====================================================================
    # ENHANCED DATABASE INITIALIZATION (Function 1)
    # =====================================================================

    def initialize_enhanced_database_wrapper(self):
        """
        Wrapper for initialize_enhanced_database() from CLI module.
        This creates all advanced tables for course management.
        """
        try:
            if ORIGINAL_MODULE_AVAILABLE:
                success = initialize_enhanced_database()
                if success:
                    self.update_status("Enhanced database initialized successfully")
                    messagebox.showinfo("Success", "Enhanced database tables created successfully!")
                else:
                    self.update_status("Database initialization failed", error=True)
                    messagebox.showerror("Error", "Failed to initialize enhanced database")
            else:
                # Use fallback
                self.init_fallback_database()
                self.update_status("Database initialized with fallback")
        except Exception as e:
            self.update_status(f"Initialization error: {e}", error=True)
            messagebox.showerror("Error", f"Database initialization failed: {e}")

    # =====================================================================
    # CORE COURSE MANAGEMENT WRAPPERS (Functions 6-11)
    # =====================================================================

    def create_enhanced_course_wrapper(self):
        """
        Wrapper that opens the enhanced course creation dialog.
        Calls the existing show_create_course() method.
        """
        self.show_create_course()

    def create_course_wrapper(self):
        """
        Basic course creation wrapper (same as enhanced for GUI).
        Calls the existing show_create_course() method.
        """
        self.show_create_course()

    def view_all_courses_wrapper(self):
        """
        Display all courses in the main list.
        Refreshes the course list and switches to the first tab.
        """
        self.refresh_course_list()
        self.notebook.select(0)  # Switch to course list tab
        self.update_status("Course list refreshed")

    def update_course_wrapper(self):
        """
        Update the selected course.
        Calls the existing edit_selected_course() method.
        """
        self.edit_selected_course()

    def delete_course_wrapper(self):
        """
        Delete the selected course.
        Calls the existing delete_selected_course() method.
        """
        self.delete_selected_course()

    def view_course_details_wrapper(self):
        """
        View detailed information about the selected course.
        Switches to the course details tab.
        """
        selected = self.course_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a course to view details.")
            return

        # Switch to details tab
        self.notebook.select(1)
        self.show_course_details()
        self.update_status("Viewing course details")

    # =====================================================================
    # PREREQUISITE MANAGEMENT (Functions 12-16)
    # =====================================================================

    def add_prerequisite_gui(self):
        """
        Add a prerequisite to a course with circular dependency checking.
        Opens a dialog to select course and prerequisite.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Course Prerequisite")
        dialog.geometry("500x300")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Prerequisite to Course",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding="10")
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(course_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Prerequisite selection
        prereq_frame = ttk.LabelFrame(main_frame, text="Select Prerequisite", padding="10")
        prereq_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prereq_frame, text="Prerequisite:").grid(row=0, column=0, sticky=tk.W, pady=5)
        prereq_var = tk.StringVar()
        prereq_combo = ttk.Combobox(prereq_frame, textvariable=prereq_var, state='readonly', width=40)
        prereq_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Required checkbox
        required_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(prereq_frame, text="Required (vs. Recommended)",
                       variable=required_var).grid(row=1, column=1, sticky=tk.W, pady=5)

        # Load courses
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
            conn.close()

            course_list = [f"{code} - {name} (ID: {id})" for id, code, name in courses]
            course_combo['values'] = course_list
            prereq_combo['values'] = course_list

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load courses: {e}")
            dialog.destroy()
            return

        def save_prerequisite():
            if not course_var.get() or not prereq_var.get():
                messagebox.showwarning("Incomplete", "Please select both course and prerequisite")
                return

            try:
                # Extract IDs from selection
                course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))
                prereq_id = int(prereq_var.get().split("ID: ")[1].rstrip(")"))

                if course_id == prereq_id:
                    messagebox.showerror("Error", "A course cannot be its own prerequisite")
                    return

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Check for circular dependency
                if self.check_circular_prerequisite_db(cursor, course_id, prereq_id):
                    messagebox.showerror("Circular Dependency",
                                       "Adding this prerequisite would create a circular dependency!")
                    conn.close()
                    return

                # Check if already exists
                cursor.execute("""
                    SELECT id FROM course_prerequisites
                    WHERE course_id = ? AND prerequisite_course_id = ?
                """, (course_id, prereq_id))

                if cursor.fetchone():
                    messagebox.showwarning("Duplicate", "This prerequisite already exists")
                    conn.close()
                    return

                # Add prerequisite
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    INSERT INTO course_prerequisites (course_id, prerequisite_course_id, is_required, created_at)
                    VALUES (?, ?, ?, ?)
                """, (course_id, prereq_id, 1 if required_var.get() else 0, timestamp))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Prerequisite added successfully!")
                self.update_status("Prerequisite added successfully")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add prerequisite: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Save", command=save_prerequisite).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def check_circular_prerequisite_db(self, cursor, course_id, prereq_id):
        """
        Check if adding a prerequisite would create a circular dependency.
        Uses recursive helper function to traverse prerequisite tree.
        """
        visited = set()

        def has_prerequisite(cid, target_id):
            """Nested helper function to recursively check prerequisites"""
            if cid in visited:
                return False
            visited.add(cid)

            cursor.execute("""
                SELECT prerequisite_course_id FROM course_prerequisites
                WHERE course_id = ?
            """, (cid,))
            prereqs = cursor.fetchall()

            for (pid,) in prereqs:
                if pid == target_id:
                    return True
                if has_prerequisite(pid, target_id):
                    return True
            return False

        return has_prerequisite(prereq_id, course_id)

    def view_prerequisites_gui(self):
        """
        View prerequisites for a selected course or all courses.
        Opens a dialog with prerequisite information.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("View Course Prerequisites")
        dialog.geometry("700x500")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Course Prerequisites",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Select Course:").pack(side=tk.LEFT, padx=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(select_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Add "All Courses" option
        all_option = "-- All Courses --"

        # Text display
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set,
                             font=('Courier', 10))
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        def load_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
                courses = cursor.fetchall()
                conn.close()

                course_list = [all_option] + [f"{code} - {name} (ID: {id})" for id, code, name in courses]
                course_combo['values'] = course_list
                course_combo.current(0)

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load courses: {e}")

        def show_prerequisites(*args):
            text_widget.delete('1.0', tk.END)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                selected = course_var.get()

                if selected == all_option or not selected:
                    # Show all prerequisites
                    cursor.execute("""
                        SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                        FROM course_prerequisites cp
                        JOIN courses c1 ON cp.course_id = c1.id
                        JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                        ORDER BY c1.course_code, c2.course_code
                    """)

                    prereqs = cursor.fetchall()
                    if prereqs:
                        text_widget.insert(tk.END, "ALL COURSE PREREQUISITES\n")
                        text_widget.insert(tk.END, "=" * 70 + "\n\n")

                        current_course = None
                        for course_code, course_name, prereq_code, prereq_name, is_req in prereqs:
                            if current_course != course_code:
                                current_course = course_code
                                text_widget.insert(tk.END, f"\n{course_code} - {course_name}:\n")
                                text_widget.insert(tk.END, "-" * 70 + "\n")

                            req_status = "Required" if is_req else "Recommended"
                            text_widget.insert(tk.END, f"  → {prereq_code} - {prereq_name} ({req_status})\n")
                    else:
                        text_widget.insert(tk.END, "No prerequisites found in the system.\n")
                else:
                    # Show prerequisites for specific course
                    course_id = int(selected.split("ID: ")[1].rstrip(")"))

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
                        course_code, course_name = prereqs[0][0], prereqs[0][1]
                        text_widget.insert(tk.END, f"PREREQUISITES FOR: {course_code} - {course_name}\n")
                        text_widget.insert(tk.END, "=" * 70 + "\n\n")

                        for _, _, prereq_code, prereq_name, is_req in prereqs:
                            req_status = "Required" if is_req else "Recommended"
                            text_widget.insert(tk.END, f"{prereq_code} - {prereq_name} ({req_status})\n")
                    else:
                        text_widget.insert(tk.END, "No prerequisites found for this course.\n")

                conn.close()

            except Exception as e:
                text_widget.insert(tk.END, f"Error loading prerequisites: {e}\n")

        course_combo.bind('<<ComboboxSelected>>', show_prerequisites)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Refresh", command=show_prerequisites).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
        show_prerequisites()

    def remove_prerequisite_gui(self):
        """
        Remove a prerequisite from a course.
        Opens a dialog to select and remove prerequisites.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Remove Course Prerequisite")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Remove Course Prerequisite",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Select Course:").pack(side=tk.LEFT, padx=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(select_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Prerequisites list
        list_frame = ttk.LabelFrame(main_frame, text="Current Prerequisites", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        prereq_listbox = tk.Listbox(list_frame, height=10)
        prereq_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=prereq_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        prereq_listbox.config(yscrollcommand=scrollbar.set)

        # Store prerequisite IDs
        prereq_data = {}

        def load_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
                courses = cursor.fetchall()
                conn.close()

                course_list = [f"{code} - {name} (ID: {id})" for id, code, name in courses]
                course_combo['values'] = course_list

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load courses: {e}")

        def load_prerequisites(*args):
            prereq_listbox.delete(0, tk.END)
            prereq_data.clear()

            if not course_var.get():
                return

            try:
                course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cp.id, c.course_code, c.course_name, cp.is_required
                    FROM course_prerequisites cp
                    JOIN courses c ON cp.prerequisite_course_id = c.id
                    WHERE cp.course_id = ?
                    ORDER BY c.course_code
                """, (course_id,))

                prereqs = cursor.fetchall()
                conn.close()

                for prereq_id, code, name, is_req in prereqs:
                    req_status = "Required" if is_req else "Recommended"
                    display_text = f"{code} - {name} ({req_status})"
                    prereq_listbox.insert(tk.END, display_text)
                    prereq_data[display_text] = prereq_id

                if not prereqs:
                    prereq_listbox.insert(tk.END, "No prerequisites found")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load prerequisites: {e}")

        def remove_selected():
            selection = prereq_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a prerequisite to remove")
                return

            selected_text = prereq_listbox.get(selection[0])
            if selected_text == "No prerequisites found":
                return

            prereq_id = prereq_data.get(selected_text)
            if not prereq_id:
                return

            if messagebox.askyesno("Confirm", f"Remove prerequisite:\n{selected_text}?"):
                try:
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM course_prerequisites WHERE id = ?", (prereq_id,))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Prerequisite removed successfully!")
                    self.update_status("Prerequisite removed")
                    load_prerequisites()

                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"Failed to remove prerequisite: {e}")

        course_combo.bind('<<ComboboxSelected>>', load_prerequisites)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Remove Selected", command=remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()

    # =====================================================================
    # INSTRUCTOR MANAGEMENT WRAPPERS (Functions 17-19)
    # =====================================================================

    def create_instructor_wrapper(self):
        """
        Create a new instructor profile.
        Calls the existing show_add_instructor() method.
        """
        self.show_add_instructor()

    def view_instructors_wrapper(self):
        """
        View all instructors in the system.
        Refreshes the instructor list and switches to instructors tab.
        """
        self.refresh_instructor_list()
        # Find and select the instructors tab (usually tab 3)
        for i in range(self.notebook.index('end')):
            if 'Instructor' in self.notebook.tab(i, 'text'):
                self.notebook.select(i)
                break
        self.update_status("Instructor list refreshed")

    def assign_instructor_to_course_wrapper(self):
        """
        Assign an instructor to a course.
        Calls the existing show_assign_instructor() method.
        """
        self.show_assign_instructor()

    # =====================================================================
    # COURSE SCHEDULING (Functions 20-22)
    # =====================================================================

    def create_course_schedule_gui(self):
        """
        Create a schedule for a course - Integrated with Module Scheduling System.
        Opens a dialog to input schedule details using the module_schedule table.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Course Schedule")
        dialog.geometry("700x750")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create Course Schedule",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding="10")
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text="Course/Module:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(course_frame, textvariable=course_var, state='readonly', width=50)
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Schedule details
        schedule_frame = ttk.LabelFrame(main_frame, text="Schedule Details", padding="10")
        schedule_frame.pack(fill=tk.X, pady=5)

        # Day of week dropdown
        ttk.Label(schedule_frame, text="Day of Week:").grid(row=0, column=0, sticky=tk.W, pady=5)
        day_var = tk.StringVar()
        day_combo = ttk.Combobox(schedule_frame, textvariable=day_var,
                                values=DAYS_OF_WEEK, state='readonly', width=28)
        day_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        # Start time dropdown
        ttk.Label(schedule_frame, text="Start Time:").grid(row=1, column=0, sticky=tk.W, pady=5)
        start_time_var = tk.StringVar()
        start_time_combo = ttk.Combobox(schedule_frame, textvariable=start_time_var,
                                       values=TIME_SLOTS, state='readonly', width=28)
        start_time_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

        # End time dropdown
        ttk.Label(schedule_frame, text="End Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        end_time_var = tk.StringVar()
        end_time_combo = ttk.Combobox(schedule_frame, textvariable=end_time_var,
                                     values=TIME_SLOTS, state='readonly', width=28)
        end_time_combo.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)

        # Session type dropdown
        ttk.Label(schedule_frame, text="Session Type:").grid(row=3, column=0, sticky=tk.W, pady=5)
        session_type_var = tk.StringVar()
        session_type_combo = ttk.Combobox(schedule_frame, textvariable=session_type_var,
                                         values=SESSION_TYPES, state='readonly', width=28)
        session_type_combo.grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)
        session_type_combo.current(0)  # Default to Lecture

        # Room selection - DROPDOWN with database
        ttk.Label(schedule_frame, text="Room:").grid(row=4, column=0, sticky=tk.W, pady=5)
        room_var = tk.StringVar()
        room_combo = ttk.Combobox(schedule_frame, textvariable=room_var, state='readonly', width=28)
        room_combo.grid(row=4, column=1, sticky=tk.W, pady=5, padx=5)

        # Instructor selection
        instructor_frame = ttk.LabelFrame(main_frame, text="Instructor", padding="10")
        instructor_frame.pack(fill=tk.X, pady=5)

        ttk.Label(instructor_frame, text="Instructor:").grid(row=0, column=0, sticky=tk.W, pady=5)
        instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(instructor_frame, textvariable=instructor_var,
                                       state='readonly', width=50)
        instructor_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        def load_data():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Load active courses/modules
                cursor.execute("""
                    SELECT id, course_code, course_name
                    FROM courses
                    WHERE status = 'Active'
                    ORDER BY course_code
                """)
                courses = cursor.fetchall()
                course_list = [f"{code} - {name}" for id, code, name in courses]
                course_combo['values'] = course_list

                # Load active rooms from rooms table
                cursor.execute("""
                    SELECT id, building, room_number, capacity, room_type
                    FROM rooms
                    WHERE is_active = 1
                    ORDER BY building, room_number
                """)
                rooms = cursor.fetchall()
                room_list = [f"{room[0]} - {room[1]}-{room[2]} (Cap: {room[3]}, Type: {room[4]})"
                            for room in rooms]
                room_combo['values'] = room_list

                # Load active instructors
                cursor.execute("""
                    SELECT id, first_name, last_name
                    FROM instructors
                    WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1
                    ORDER BY last_name, first_name
                """)
                instructors = cursor.fetchall()
                instructor_list = [f"{inst[0]} - {inst[1]} {inst[2]}" for inst in instructors]
                instructor_combo['values'] = instructor_list

                conn.close()

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load data: {e}")
                dialog.destroy()

        def save_schedule():
            # Validation
            if not course_var.get():
                messagebox.showwarning("Incomplete", "Please select a course/module")
                return

            if not day_var.get():
                messagebox.showwarning("Incomplete", "Please select a day of week")
                return

            if not start_time_var.get() or not end_time_var.get():
                messagebox.showwarning("Incomplete", "Please select start and end times")
                return

            if not room_var.get():
                messagebox.showwarning("Incomplete", "Please select a room")
                return

            if not instructor_var.get():
                messagebox.showwarning("Incomplete", "Please select an instructor")
                return

            if not session_type_var.get():
                messagebox.showwarning("Incomplete", "Please select a session type")
                return

            try:
                # Extract course code
                module_code = course_var.get().split(" - ")[0]

                # Extract room ID
                room_id = int(room_var.get().split(" - ")[0])

                # Extract instructor ID
                instructor_id = int(instructor_var.get().split(" - ")[0])

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
                conn.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode for better concurrency
                cursor = conn.cursor()

                # Ensure course_schedule table exists with proper schema
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    room_id INTEGER,
                    instructor_id INTEGER,
                    session_type TEXT,
                    semester TEXT,
                    year INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    FOREIGN KEY (room_id) REFERENCES rooms(id),
                    FOREIGN KEY (instructor_id) REFERENCES instructors(id)
                )
                ''')

                # Get current semester and year
                current_semester = "Fall"  # You can make this dynamic
                current_year = datetime.now().year

                # Check for schedule conflicts
                cursor.execute("""
                    SELECT id FROM course_schedule
                    WHERE course_code = ? AND day_of_week = ? AND semester = ? AND year = ?
                    AND ((start_time <= ? AND end_time > ?) OR (start_time < ? AND end_time >= ?))
                """, (module_code, day_var.get(), current_semester, current_year,
                     start_time_var.get(), start_time_var.get(),
                     end_time_var.get(), end_time_var.get()))

                if cursor.fetchone():
                    messagebox.showerror("Schedule Conflict",
                                       f"Schedule conflict detected for {module_code} on {day_var.get()}")
                    conn.close()
                    return

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert into course_schedule table
                cursor.execute('''
                    INSERT INTO course_schedule (course_code, day_of_week, start_time, end_time,
                                               room_id, instructor_id, session_type, semester, year, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (module_code, day_var.get(), start_time_var.get(), end_time_var.get(),
                      room_id, instructor_id, session_type_var.get(), current_semester, current_year, timestamp))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success",
                                  f"Schedule created successfully!\n\n"
                                  f"Course: {module_code}\n"
                                  f"Day: {day_var.get()}\n"
                                  f"Time: {start_time_var.get()} - {end_time_var.get()}\n"
                                  f"Session: {session_type_var.get()}\n"
                                  f"Semester: {current_semester} {current_year}")
                self.update_status("Course schedule created in course_schedule table")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create schedule: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Create Schedule", command=save_schedule).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_data()

    def view_course_schedules_gui(self):
        """
        View course schedules using course_schedule table.
        Displays timetable in grid format matching Module Scheduling GUI.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("View Course Schedules - Timetable View")
        dialog.geometry("1400x900")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Course Schedules - Timetable View",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Create notebook for list and grid views
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # ==========================
        # TAB 1: LIST VIEW
        # ==========================
        list_tab = ttk.Frame(notebook)
        notebook.add(list_tab, text="📋 List View")

        # Filter frame
        filter_frame = ttk.Frame(list_tab)
        filter_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Label(filter_frame, text="Filter by Course:").pack(side=tk.LEFT, padx=5)
        course_filter_var = tk.StringVar()
        course_filter_combo = ttk.Combobox(filter_frame, textvariable=course_filter_var,
                                          state='readonly', width=40)
        course_filter_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="🔄 Refresh",
                  command=lambda: load_list_view()).pack(side=tk.LEFT, padx=5)

        # Treeview for schedules
        tree_frame = ttk.Frame(list_tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        columns = ('ID', 'Course', 'Day', 'Time', 'Room', 'Instructor', 'Type', 'Semester')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

        tree.heading('ID', text='ID')
        tree.heading('Course', text='Course Code')
        tree.heading('Day', text='Day')
        tree.heading('Time', text='Time')
        tree.heading('Room', text='Room')
        tree.heading('Instructor', text='Instructor')
        tree.heading('Type', text='Session Type')
        tree.heading('Semester', text='Semester')

        tree.column('ID', width=50)
        tree.column('Course', width=120)
        tree.column('Day', width=100)
        tree.column('Time', width=120)
        tree.column('Room', width=150)
        tree.column('Instructor', width=150)
        tree.column('Type', width=100)
        tree.column('Semester', width=120)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Buttons for list view
        list_button_frame = ttk.Frame(list_tab)
        list_button_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Button(list_button_frame, text="❌ Delete Selected",
                  command=lambda: delete_selected_schedule()).pack(side=tk.LEFT, padx=5)
        ttk.Button(list_button_frame, text="✏️ Edit Selected",
                  command=lambda: edit_selected_schedule()).pack(side=tk.LEFT, padx=5)

        # ==========================
        # TAB 2: TIMETABLE GRID VIEW
        # ==========================
        grid_tab = ttk.Frame(notebook)
        notebook.add(grid_tab, text="📅 Timetable Grid")

        # Filter for grid view
        grid_filter_frame = ttk.Frame(grid_tab)
        grid_filter_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Label(grid_filter_frame, text="Show schedule for:").pack(side=tk.LEFT, padx=5)
        grid_filter_var = tk.StringVar(value="All Courses")
        grid_filter_combo = ttk.Combobox(grid_filter_frame, textvariable=grid_filter_var,
                                        state='readonly', width=40)
        grid_filter_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(grid_filter_frame, text="🔄 Refresh Grid",
                  command=lambda: load_timetable_grid()).pack(side=tk.LEFT, padx=5)

        # Scrollable grid container
        grid_canvas_frame = ttk.Frame(grid_tab)
        grid_canvas_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)

        grid_canvas = tk.Canvas(grid_canvas_frame, bg='white')
        grid_scrollbar_v = ttk.Scrollbar(grid_canvas_frame, orient="vertical", command=grid_canvas.yview)
        grid_scrollbar_h = ttk.Scrollbar(grid_canvas_frame, orient="horizontal", command=grid_canvas.xview)

        grid_frame = tk.Frame(grid_canvas, bg='white')
        grid_frame.bind("<Configure>", lambda e: grid_canvas.configure(scrollregion=grid_canvas.bbox("all")))

        grid_canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        grid_canvas.configure(yscrollcommand=grid_scrollbar_v.set, xscrollcommand=grid_scrollbar_h.set)

        grid_canvas.pack(side="left", fill="both", expand=True)
        grid_scrollbar_v.pack(side="right", fill="y")
        grid_scrollbar_h.pack(side="bottom", fill="x")

        # ==========================
        # FUNCTIONS
        # ==========================

        def load_courses():
            """Load course filter options"""
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT course_code FROM courses WHERE status = 'Active' ORDER BY course_code")
                courses = [row[0] for row in cursor.fetchall()]
                conn.close()

                course_list = ["-- All Courses --"] + courses
                course_filter_combo['values'] = course_list
                course_filter_combo.current(0)

                grid_filter_combo['values'] = course_list
                grid_filter_combo.current(0)

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load courses: {e}")

        def load_list_view(*args):
            """Load schedules in list view"""
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Ensure table exists
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    room_id INTEGER,
                    instructor_id INTEGER,
                    session_type TEXT,
                    semester TEXT,
                    year INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    FOREIGN KEY (room_id) REFERENCES rooms(id),
                    FOREIGN KEY (instructor_id) REFERENCES instructors(id)
                )
                ''')

                filter_course = course_filter_var.get()

                if filter_course == "-- All Courses --" or not filter_course:
                    query = """
                        SELECT cs.id, cs.course_code, cs.day_of_week,
                               cs.start_time, cs.end_time,
                               r.building, r.room_number,
                               i.first_name, i.last_name,
                               cs.session_type, cs.semester, cs.year
                        FROM course_schedule cs
                        LEFT JOIN rooms r ON cs.room_id = r.id
                        LEFT JOIN instructors i ON cs.instructor_id = i.id
                        ORDER BY cs.course_code, cs.day_of_week, cs.start_time
                    """
                    cursor.execute(query)
                else:
                    query = """
                        SELECT cs.id, cs.course_code, cs.day_of_week,
                               cs.start_time, cs.end_time,
                               r.building, r.room_number,
                               i.first_name, i.last_name,
                               cs.session_type, cs.semester, cs.year
                        FROM course_schedule cs
                        LEFT JOIN rooms r ON cs.room_id = r.id
                        LEFT JOIN instructors i ON cs.instructor_id = i.id
                        WHERE cs.course_code = ?
                        ORDER BY cs.day_of_week, cs.start_time
                    """
                    cursor.execute(query, (filter_course,))

                schedules = cursor.fetchall()
                conn.close()

                for sched in schedules:
                    sched_id, course_code, day, start, end, building, room_num, first, last, session_type, semester, year = sched
                    time_str = f"{start}-{end}"
                    room_str = f"{building}-{room_num}" if building and room_num else "TBA"
                    instructor = f"{first} {last}" if first and last else "TBA"
                    semester_str = f"{semester} {year}" if semester and year else "N/A"

                    tree.insert('', tk.END, values=(
                        sched_id, course_code, day, time_str, room_str,
                        instructor, session_type or '', semester_str
                    ))

                if not schedules:
                    messagebox.showinfo("No Results", "No course schedules found")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load schedules: {e}")
                print(f"Schedule load error: {e}")

        def delete_selected_schedule():
            """Delete selected schedule from list"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a schedule to delete")
                return

            item = tree.item(selection[0])
            schedule_id = item['values'][0]
            course_code = item['values'][1]

            if not messagebox.askyesno("Confirm Delete",
                                      f"Delete schedule for {course_code}?\n\nThis action cannot be undone."):
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute("DELETE FROM course_schedule WHERE id = ?", (schedule_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Schedule deleted successfully!")
                self.update_status(f"Deleted schedule {schedule_id}")
                load_list_view()
                load_timetable_grid()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete schedule: {e}")

        def edit_selected_schedule():
            """Edit selected schedule"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a schedule to edit")
                return

            item = tree.item(selection[0])
            schedule_id = item['values'][0]

            # Call update schedule function with this ID
            self.show_update_schedule_by_id(schedule_id)
            dialog.destroy()

        def load_timetable_grid():
            """Load timetable in grid format matching Module Scheduling GUI"""
            # Clear existing grid
            for widget in grid_frame.winfo_children():
                widget.destroy()

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Ensure table exists
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    room_id INTEGER,
                    instructor_id INTEGER,
                    session_type TEXT,
                    semester TEXT,
                    year INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    FOREIGN KEY (room_id) REFERENCES rooms(id),
                    FOREIGN KEY (instructor_id) REFERENCES instructors(id)
                )
                ''')

                filter_course = grid_filter_var.get()

                if filter_course == "-- All Courses --" or not filter_course:
                    query = """
                        SELECT cs.course_code, cs.day_of_week, cs.start_time, cs.end_time,
                               r.building, r.room_number, cs.session_type
                        FROM course_schedule cs
                        LEFT JOIN rooms r ON cs.room_id = r.id
                        ORDER BY cs.day_of_week, cs.start_time
                    """
                    cursor.execute(query)
                else:
                    query = """
                        SELECT cs.course_code, cs.day_of_week, cs.start_time, cs.end_time,
                               r.building, r.room_number, cs.session_type
                        FROM course_schedule cs
                        LEFT JOIN rooms r ON cs.room_id = r.id
                        WHERE cs.course_code = ?
                        ORDER BY cs.day_of_week, cs.start_time
                    """
                    cursor.execute(query, (filter_course,))

                schedule_data = cursor.fetchall()
                conn.close()

                # Create grid data structure
                grid_data = {}
                for day in DAYS_OF_WEEK:
                    grid_data[day] = {}
                    for time_slot in TIME_SLOTS:
                        grid_data[day][time_slot] = []

                # Populate grid with schedule data
                for entry in schedule_data:
                    course_code, day, start_time, end_time, building, room_num, session_type = entry

                    if not day or not start_time:
                        continue

                    # Find the closest time slot
                    try:
                        closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
                    except:
                        continue

                    session_info = {
                        'course': course_code,
                        'type': session_type or 'Session',
                        'room': f"{building}-{room_num}" if building and room_num else "TBA",
                        'time': f"{start_time}-{end_time}"
                    }

                    if day in grid_data and closest_slot in grid_data[day]:
                        grid_data[day][closest_slot].append(session_info)

                # Create grid header - Time column
                time_header = tk.Label(grid_frame, text="Time", font=('Arial', 10, 'bold'),
                                      relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                      width=10, height=2)
                time_header.grid(row=0, column=0, padx=1, pady=1, sticky="nsew")

                # Day headers
                for col, day in enumerate(DAYS_OF_WEEK, 1):
                    day_header = tk.Label(grid_frame, text=day, font=('Arial', 10, 'bold'),
                                         relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                         width=18, height=2)
                    day_header.grid(row=0, column=col, padx=1, pady=1, sticky="nsew")

                # Create time slots and schedule cells
                for row, time_slot in enumerate(TIME_SLOTS, 1):
                    # Time label
                    time_label = tk.Label(grid_frame, text=time_slot, font=('Arial', 9, 'bold'),
                                         relief=tk.SOLID, borderwidth=2, bg='#e8f4f8',
                                         width=10, height=4)
                    time_label.grid(row=row, column=0, padx=1, pady=1, sticky="nsew")

                    # Schedule cells for each day
                    for col, day in enumerate(DAYS_OF_WEEK, 1):
                        entries = grid_data[day][time_slot]

                        # Create cell frame
                        cell_frame = tk.Frame(grid_frame, relief=tk.SOLID, borderwidth=2,
                                             bg='#d4edda' if entries else 'white',
                                             width=160, height=80)
                        cell_frame.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
                        cell_frame.grid_propagate(False)

                        if entries:
                            # Inner container
                            inner_frame = tk.Frame(cell_frame, bg='#d4edda')
                            inner_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

                            # Display entries
                            for i, entry in enumerate(entries):
                                if i < 2:  # Limit to 2 entries per cell
                                    session_box = tk.Frame(inner_frame, relief=tk.RAISED, borderwidth=1,
                                                          bg='#c3e6cb', padx=2, pady=2)
                                    session_box.pack(fill=tk.X, pady=1)

                                    # Course code
                                    course_label = tk.Label(session_box, text=entry['course'],
                                                           font=('Arial', 8, 'bold'),
                                                           bg='#c3e6cb', fg='#155724')
                                    course_label.pack(anchor='w')

                                    # Session type
                                    type_label = tk.Label(session_box, text=entry['type'],
                                                         font=('Arial', 7),
                                                         bg='#c3e6cb', fg='#155724')
                                    type_label.pack(anchor='w')

                                    # Room
                                    room_label = tk.Label(session_box, text=f"Room: {entry['room']}",
                                                         font=('Arial', 6),
                                                         bg='#c3e6cb', fg='#155724')
                                    room_label.pack(anchor='w')

                            if len(entries) > 2:
                                more_label = tk.Label(inner_frame, text=f"+ {len(entries)-2} more...",
                                                     font=('Arial', 7, 'italic'),
                                                     bg='#d4edda', fg='#155724')
                                more_label.pack(anchor='w', pady=2)

                if not schedule_data:
                    no_data_label = tk.Label(grid_frame, text="No course schedules found",
                                            font=('Arial', 12), fg='gray')
                    no_data_label.grid(row=1, column=1, columnspan=5, pady=50)

            except Exception as e:
                error_label = tk.Label(grid_frame, text=f"Error loading timetable: {e}",
                                      font=('Arial', 12), fg='red')
                error_label.grid(row=1, column=1, columnspan=5, pady=50)
                print(f"Timetable grid error: {e}")

        # Bind filter changes
        course_filter_combo.bind('<<ComboboxSelected>>', load_list_view)
        grid_filter_combo.bind('<<ComboboxSelected>>', lambda e: load_timetable_grid())

        # Main buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
        load_list_view()
        load_timetable_grid()

    def show_update_schedule_by_id(self, schedule_id):
        """Helper method to show update dialog for a specific schedule ID"""
        # For now, open the general update dialog
        # Can be enhanced later to pre-populate with schedule data
        self.show_update_schedule()
        messagebox.showinfo("Edit Schedule", f"Please select schedule ID: {schedule_id} from the list")

    def update_schedule_gui(self):
        """
        Update an existing course schedule.
        Opens a dialog to modify schedule details.
        """
        # First, show schedule selection dialog
        select_dialog = tk.Toplevel(self.root)
        select_dialog.title("Select Schedule to Update")
        select_dialog.geometry("600x400")
        select_dialog.transient(self.root)

        main_frame = ttk.Frame(select_dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Select Schedule to Update",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Listbox for schedules
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        schedule_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=15)
        schedule_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=schedule_listbox.yview)

        schedule_data = {}

        def load_schedules():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT s.id, c.course_code, c.course_name, s.semester, s.year
                    FROM course_schedule s
                    JOIN courses c ON s.course_id = c.id
                    ORDER BY s.year DESC, s.semester, c.course_code
                """)
                schedules = cursor.fetchall()
                conn.close()

                for sched_id, code, name, semester, year in schedules:
                    display_text = f"{code} - {name[:30]} ({semester} {year})"
                    schedule_listbox.insert(tk.END, display_text)
                    schedule_data[display_text] = sched_id

                if not schedules:
                    schedule_listbox.insert(tk.END, "No schedules found")

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to load schedules: {e}")

        def open_edit_dialog():
            selection = schedule_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a schedule to update")
                return

            selected_text = schedule_listbox.get(selection[0])
            if selected_text == "No schedules found":
                return

            schedule_id = schedule_data.get(selected_text)
            if not schedule_id:
                return

            select_dialog.destroy()
            self._show_schedule_edit_dialog(schedule_id)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Edit Selected", command=open_edit_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=select_dialog.destroy).pack(side=tk.RIGHT, padx=5)

        load_schedules()

    def _show_schedule_edit_dialog(self, schedule_id):
        """Helper method to show the schedule edit dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Course Schedule")
        dialog.geometry("600x500")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Update Course Schedule",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Load current schedule data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT course_id, semester, year, start_time, end_time,
                       days_of_week, classroom, instructor_id
                FROM course_schedule WHERE id = ?
            """, (schedule_id,))
            current = cursor.fetchone()
            conn.close()

            if not current:
                messagebox.showerror("Error", "Schedule not found")
                dialog.destroy()
                return

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load schedule: {e}")
            dialog.destroy()
            return

        # Create form fields with current values
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        row = 0

        # Semester
        ttk.Label(form_frame, text="Semester:").grid(row=row, column=0, sticky=tk.W, pady=5)
        semester_var = tk.StringVar(value=current[1])
        semester_combo = ttk.Combobox(form_frame, textvariable=semester_var,
                                     values=["Fall", "Spring", "Summer", "Winter"],
                                     state='readonly', width=25)
        semester_combo.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # Year
        ttk.Label(form_frame, text="Year:").grid(row=row, column=0, sticky=tk.W, pady=5)
        year_var = tk.StringVar(value=str(current[2]))
        year_entry = ttk.Entry(form_frame, textvariable=year_var, width=27)
        year_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # Start time
        ttk.Label(form_frame, text="Start Time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=5)
        start_time_var = tk.StringVar(value=current[3] or '')
        start_time_entry = ttk.Entry(form_frame, textvariable=start_time_var, width=27)
        start_time_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # End time
        ttk.Label(form_frame, text="End Time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=5)
        end_time_var = tk.StringVar(value=current[4] or '')
        end_time_entry = ttk.Entry(form_frame, textvariable=end_time_var, width=27)
        end_time_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # Days
        ttk.Label(form_frame, text="Days of Week:").grid(row=row, column=0, sticky=tk.W, pady=5)
        days_var = tk.StringVar(value=current[5] or '')
        days_entry = ttk.Entry(form_frame, textvariable=days_var, width=27)
        days_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # Classroom
        ttk.Label(form_frame, text="Classroom:").grid(row=row, column=0, sticky=tk.W, pady=5)
        classroom_var = tk.StringVar(value=current[6] or '')
        classroom_entry = ttk.Entry(form_frame, textvariable=classroom_var, width=27)
        classroom_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        def save_changes():
            # Validate inputs
            if start_time_var.get() and not self.validate_time_format(start_time_var.get()):
                messagebox.showerror("Invalid Format", "Start time must be in HH:MM format")
                return

            if end_time_var.get() and not self.validate_time_format(end_time_var.get()):
                messagebox.showerror("Invalid Format", "End time must be in HH:MM format")
                return

            if days_var.get() and not self.validate_days_of_week(days_var.get()):
                messagebox.showerror("Invalid Format", "Days must be full day names separated by commas")
                return

            try:
                year = int(year_var.get())
            except ValueError:
                messagebox.showerror("Invalid Year", "Please enter a valid year")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE course_schedule
                    SET semester = ?, year = ?, start_time = ?, end_time = ?,
                        days_of_week = ?, classroom = ?
                    WHERE id = ?
                """, (semester_var.get(), year,
                      start_time_var.get() or None, end_time_var.get() or None,
                      days_var.get() or None, classroom_var.get() or None,
                      schedule_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Schedule updated successfully!")
                self.update_status("Course schedule updated")
                dialog.destroy()

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to update schedule: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # =====================================================================
    # WAITLIST MANAGEMENT (Functions 29-31)
    # =====================================================================

    def add_to_waitlist_gui(self):
        """
        Add a student to a course waitlist.
        Opens a dialog to select full course and enter student ID.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Student to Waitlist")
        dialog.geometry("550x350")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Student to Course Waitlist",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection (full courses only)
        course_frame = ttk.LabelFrame(main_frame, text="Select Full Course", padding="10")
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(course_frame, textvariable=course_var, state='readonly', width=45)
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Student ID
        student_frame = ttk.LabelFrame(main_frame, text="Student Information", padding="10")
        student_frame.pack(fill=tk.X, pady=5)

        ttk.Label(student_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        student_id_var = tk.StringVar()
        student_id_entry = ttk.Entry(student_frame, textvariable=student_id_var, width=30)
        student_id_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        # Info label
        info_label = ttk.Label(main_frame, text="", foreground="blue", wraplength=500)
        info_label.pack(pady=10)

        def load_full_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, course_code, course_name, current_enrollment, max_enrollment
                    FROM courses
                    WHERE current_enrollment >= max_enrollment AND status = 'Active'
                    ORDER BY course_code
                """)
                courses = cursor.fetchall()
                conn.close()

                if courses:
                    course_list = [f"{code} - {name} ({enr}/{max}) (ID: {id})"
                                 for id, code, name, enr, max in courses]
                    course_combo['values'] = course_list
                    info_label.config(text=f"Found {len(courses)} full course(s)")
                else:
                    course_combo['values'] = ["No full courses available"]
                    info_label.config(text="No full courses found")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load courses: {e}")
                dialog.destroy()

        def add_student():
            if not course_var.get() or course_var.get() == "No full courses available":
                messagebox.showwarning("No Selection", "Please select a course")
                return

            if not student_id_var.get().strip():
                messagebox.showerror("Missing Data", "Please enter student ID")
                return

            try:
                course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))
                student_id = student_id_var.get().strip()

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Validate student exists in database
                cursor.execute("SELECT student_id, first_name, last_name FROM students WHERE student_id = ?", (student_id,))
                student_record = cursor.fetchone()

                if not student_record:
                    messagebox.showerror("Invalid Student",
                                       f"Student ID '{student_id}' does not exist in the database.\n\n"
                                       f"Please enter a valid student ID.")
                    conn.close()
                    return

                student_name = f"{student_record[1]} {student_record[2]}"

                # Check if already on waitlist
                cursor.execute("""
                    SELECT id FROM course_waitlist
                    WHERE course_id = ? AND student_id = ?
                """, (course_id, student_id))

                if cursor.fetchone():
                    messagebox.showerror("Duplicate", f"Student {student_name} ({student_id}) is already on the waitlist for this course")
                    conn.close()
                    return

                # Get next position
                cursor.execute("""
                    SELECT COALESCE(MAX(position), 0) + 1
                    FROM course_waitlist WHERE course_id = ?
                """, (course_id,))
                position = cursor.fetchone()[0]

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO course_waitlist (course_id, student_id, position, added_at, status)
                    VALUES (?, ?, ?, ?, 'Waiting')
                ''', (course_id, student_id, position, timestamp))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success",
                                  f"Student {student_name} ({student_id}) added to waitlist at position {position}")
                self.update_status(f"Added student {student_name} ({student_id}) to waitlist")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add to waitlist: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add to Waitlist", command=add_student).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        load_full_courses()

    def view_waitlists_gui(self):
        """
        View waitlists for all courses or a specific course.
        Opens a dialog with waitlist information.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("View Course Waitlists")
        dialog.geometry("800x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Course Waitlists",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="Filter by Course:").pack(side=tk.LEFT, padx=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Treeview for waitlist
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ('Course', 'Position', 'Student ID', 'Added Date', 'Status')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Course':
                tree.column(col, width=200)
            elif col == 'Student ID':
                tree.column(col, width=120)
            else:
                tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def load_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
                courses = cursor.fetchall()
                conn.close()

                course_list = ["-- All Courses --"] + [f"{code} - {name} (ID: {id})" for id, code, name in courses]
                course_combo['values'] = course_list
                course_combo.current(0)

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load courses: {e}")

        def load_waitlist(*args):
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                selected = course_var.get()

                if selected == "-- All Courses --" or not selected:
                    cursor.execute("""
                        SELECT c.course_code, c.course_name, w.position,
                               w.student_id, w.added_at, w.status
                        FROM course_waitlist w
                        JOIN courses c ON w.course_id = c.id
                        ORDER BY c.course_code, w.position
                    """)
                else:
                    course_id = int(selected.split("ID: ")[1].rstrip(")"))
                    cursor.execute("""
                        SELECT c.course_code, c.course_name, w.position,
                               w.student_id, w.added_at, w.status
                        FROM course_waitlist w
                        JOIN courses c ON w.course_id = c.id
                        WHERE w.course_id = ?
                        ORDER BY w.position
                    """, (course_id,))

                waitlist = cursor.fetchall()
                conn.close()

                for entry in waitlist:
                    code, name, position, student, added, status = entry
                    course = f"{code} - {name[:25]}"
                    added_date = added.split()[0] if added else "Unknown"

                    tree.insert('', tk.END, values=(
                        course, position, student, added_date, status
                    ))

                if not waitlist:
                    messagebox.showinfo("No Results", "No waitlist entries found")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load waitlist: {e}")

        course_combo.bind('<<ComboboxSelected>>', load_waitlist)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Refresh", command=load_waitlist).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
        load_waitlist()

    def process_waitlist_gui(self):
        """
        Process waitlist and enroll students when spots become available.
        Opens a dialog to select course and process waitlist.
        """
        messagebox.showinfo("Process Waitlist",
                          "This feature would automatically enroll students from the waitlist\n"
                          "when spots become available in the course.\n\n"
                          "Implementation requires integration with enrollment system.")

    # =====================================================================
    # COURSE STATUS & HISTORY (Functions 34, 36)
    # =====================================================================

    def manage_course_status_gui(self):
        """
        Manage course status (Active, Inactive, Archived, Cancelled).
        Opens a dialog to change course status.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Course Status")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Manage Course Status",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection
        select_frame = ttk.LabelFrame(main_frame, text="Select Course", padding="10")
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(select_frame, textvariable=course_var, state='readonly', width=45)
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Current status display
        current_status_var = tk.StringVar(value="No course selected")
        ttk.Label(select_frame, text="Current Status:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(select_frame, textvariable=current_status_var,
                 font=('Arial', 10, 'bold')).grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

        # New status selection
        status_frame = ttk.LabelFrame(main_frame, text="Select New Status", padding="10")
        status_frame.pack(fill=tk.X, pady=5)

        ttk.Label(status_frame, text="New Status:").grid(row=0, column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(status_frame, textvariable=status_var,
                                   values=["Active", "Inactive", "Archived", "Cancelled"],
                                   state='readonly', width=25)
        status_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        def load_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, course_code, course_name, status
                    FROM courses ORDER BY course_code
                """)
                courses = cursor.fetchall()
                conn.close()

                course_list = [f"{code} - {name} (ID: {id})" for id, code, name, status in courses]
                course_combo['values'] = course_list

                # Store course data for status display
                course_combo.course_data = {
                    f"{code} - {name} (ID: {id})": status
                    for id, code, name, status in courses
                }

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load courses: {e}")
                dialog.destroy()

        def on_course_select(*args):
            selected = course_var.get()
            if selected and hasattr(course_combo, 'course_data'):
                current_status = course_combo.course_data.get(selected, "Unknown")
                current_status_var.set(current_status)
                status_var.set(current_status)

        course_combo.bind('<<ComboboxSelected>>', on_course_select)

        def update_status():
            if not course_var.get():
                messagebox.showwarning("No Selection", "Please select a course")
                return

            if not status_var.get():
                messagebox.showwarning("No Selection", "Please select a new status")
                return

            current = current_status_var.get()
            new = status_var.get()

            if current == new:
                messagebox.showinfo("No Change", "Status is already set to " + new)
                return

            if messagebox.askyesno("Confirm Status Change",
                                  f"Change course status from {current} to {new}?"):
                try:
                    course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))

                    conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                    cursor = conn.cursor()

                    cursor.execute("""
                        UPDATE courses SET status = ?, updated_at = ?
                        WHERE id = ?
                    """, (new, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), course_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Course status updated to {new}")
                    self.update_status(f"Course status changed to {new}")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update status: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Update Status", command=update_status).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        load_courses()

    def view_course_history_gui(self):
        """
        View historical changes to courses (audit trail).
        Opens a dialog with course history information.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("View Course History")
        dialog.geometry("900x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Course Change History",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="Filter by Course:").pack(side=tk.LEFT, padx=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Treeview for history
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ('Course', 'Field', 'Old Value', 'New Value', 'Changed By', 'Date')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def load_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
                courses = cursor.fetchall()
                conn.close()

                course_list = ["-- All Courses --"] + [f"{code} - {name} (ID: {id})" for id, code, name in courses]
                course_combo['values'] = course_list
                course_combo.current(0)

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load courses: {e}")

        def load_history(*args):
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Check if course_history table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='course_history'
                """)
                if not cursor.fetchone():
                    tree.insert('', tk.END, values=(
                        "History table not found", "", "", "", "", ""
                    ))
                    conn.close()
                    return

                selected = course_var.get()

                if selected == "-- All Courses --" or not selected:
                    cursor.execute("""
                        SELECT c.course_code, h.field_name, h.old_value,
                               h.new_value, h.changed_by, h.changed_at
                        FROM course_history h
                        JOIN courses c ON h.course_id = c.id
                        ORDER BY h.changed_at DESC
                        LIMIT 100
                    """)
                else:
                    course_id = int(selected.split("ID: ")[1].rstrip(")"))
                    cursor.execute("""
                        SELECT c.course_code, h.field_name, h.old_value,
                               h.new_value, h.changed_by, h.changed_at
                        FROM course_history h
                        JOIN courses c ON h.course_id = c.id
                        WHERE h.course_id = ?
                        ORDER BY h.changed_at DESC
                    """, (course_id,))

                history = cursor.fetchall()
                conn.close()

                for entry in history:
                    code, field, old_val, new_val, changed_by, changed_at = entry
                    old_display = (old_val[:25] + "...") if old_val and len(old_val) > 25 else (old_val or "")
                    new_display = (new_val[:25] + "...") if new_val and len(new_val) > 25 else (new_val or "")
                    date_display = changed_at.split()[0] if changed_at else ""

                    tree.insert('', tk.END, values=(
                        code, field, old_display, new_display,
                        changed_by or "System", date_display
                    ))

                if not history:
                    tree.insert('', tk.END, values=(
                        "No history records found", "", "", "", "", ""
                    ))

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load history: {e}")

        course_combo.bind('<<ComboboxSelected>>', load_history)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Refresh", command=load_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
        load_history()

    # =====================================================================
    # WRAPPER FUNCTIONS FOR EXISTING FEATURES (Functions 23-28, 32-33, 35, 37)
    # =====================================================================

    def search_courses_wrapper(self):
        """Search courses with filters. Calls existing show_search_dialog()."""
        self.show_search_dialog()

    def import_courses_from_csv_wrapper(self):
        """Import courses from CSV file. Calls existing import_csv()."""
        self.import_csv()

    def export_courses_to_csv_wrapper(self):
        """Export courses to CSV file. Calls existing export_csv()."""
        self.export_csv()

    def generate_course_analytics_wrapper(self):
        """Generate course analytics. Calls existing generate_analytics()."""
        self.generate_analytics()

    def generate_enrollment_report_wrapper(self):
        """Generate enrollment report. Calls existing show_enrollment_report()."""
        self.show_enrollment_report()

    def department_statistics_wrapper(self):
        """Generate department statistics. Calls existing show_department_stats()."""
        self.show_department_stats()

    def recommend_courses_wrapper(self):
        """Recommend courses to student. Calls existing show_recommendations()."""
        self.show_recommendations()

    def find_alternative_courses_wrapper(self):
        """Find alternative courses. Calls existing find_alternative_courses()."""
        self.find_alternative_courses()

    def bulk_update_courses_wrapper(self):
        """Bulk update multiple courses. Calls existing show_bulk_update()."""
        self.show_bulk_update()

    def system_maintenance_wrapper(self):
        """System maintenance operations. Calls existing show_maintenance()."""
        self.show_maintenance()

# =====================================================================
# BACKWARDS COMPATIBILITY WRAPPER
# =====================================================================

class BackwardsCompatibilityWrapper:
    """Wrapper to provide backwards compatibility with original CLI functions"""
    
    def __init__(self, gui_app):
        self.gui_app = gui_app
        self.auth = gui_app.auth
    
    def display_enhanced_course_menu(self, auth=None):
        """Backwards compatible menu display - launches GUI instead"""
        if not auth:
            auth = self.auth
        
        # If GUI is already running, just bring it to front
        if hasattr(self.gui_app, 'root') and self.gui_app.root.winfo_exists():
            self.gui_app.root.lift()
            self.gui_app.root.focus_force()
            return
        
        # Otherwise show a message
        print("GUI Course Management System is now running.")
        print("Please use the graphical interface for course management.")
    
    def create_enhanced_course(self, auth=None):
        """Backwards compatible course creation"""
        if not auth:
            auth = self.auth
        self.gui_app.show_create_course()
        return True
    
    def view_all_courses(self, auth=None):
        """Backwards compatible course viewing"""
        if not auth:
            auth = self.auth
        self.gui_app.refresh_course_list()
        self.gui_app.notebook.select(0)  # Switch to course list tab
        return True
    
    def search_courses(self, auth=None):
        """Backwards compatible course search"""
        if not auth:
            auth = self.auth
        self.gui_app.show_search_dialog()
        return True
    
    def generate_course_analytics(self, auth=None):
        """Backwards compatible analytics"""
        if not auth:
            auth = self.auth
        self.gui_app.generate_analytics()
        return True

# =====================================================================
# MAIN APPLICATION RUNNER
# =====================================================================

def run_gui_application():
    """Main function to run the GUI application"""
    root = tk.Tk()
    app = CourseManagementGUI(root)
    
    # Create backwards compatibility wrapper
    if ORIGINAL_MODULE_AVAILABLE:
        compat_wrapper = BackwardsCompatibilityWrapper(app)
        
        # Override original functions to use GUI (optional)
        # This allows existing code to seamlessly use the GUI
        import sys
        if 'course_management' in sys.modules:
            course_management = sys.modules['course_management']
            course_management.display_enhanced_course_menu = compat_wrapper.display_enhanced_course_menu
            course_management.create_enhanced_course = compat_wrapper.create_enhanced_course
            course_management.view_all_courses = compat_wrapper.view_all_courses
            course_management.search_courses = compat_wrapper.search_courses
            course_management.generate_course_analytics = compat_wrapper.generate_course_analytics
    
    # Run the application
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        print(f"Application error: {e}")
        messagebox.showerror("Application Error", f"An unexpected error occurred: {e}")

# =====================================================================
# COMMAND LINE INTERFACE FOR BACKWARDS COMPATIBILITY
# =====================================================================

def cli_interface():
    """Command line interface for backwards compatibility"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Course Management System')
    parser.add_argument('--gui', action='store_true', help='Launch GUI interface (default)')
    parser.add_argument('--cli', action='store_true', help='Use original CLI interface')
    parser.add_argument('--import-csv', type=str, help='Import courses from CSV file')
    parser.add_argument('--export-csv', type=str, help='Export courses to CSV file')
    parser.add_argument('--backup', type=str, help='Create database backup')
    
    args = parser.parse_args()
    
    if args.cli and ORIGINAL_MODULE_AVAILABLE:
        # Use original CLI interface
        print("Launching original CLI interface...")
        try:
            # Import and use centralized authentication system
            from university_system.infrastructure.auth.user_authentication import UserAuth
            auth = UserAuth()
            display_enhanced_course_menu(auth)
        except NameError:
            print("Original CLI functions not available. Launching GUI instead.")
            run_gui_application()
    
    elif args.import_csv:
        # Handle CSV import
        print(f"Importing courses from {args.import_csv}...")
        if not os.path.exists(args.import_csv):
            print(f"Error: File '{args.import_csv}' not found.")
            return 1

        try:
            imported_count = 0
            error_count = 0

            with open(args.import_csv, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                required_fields = ['course_code', 'course_name', 'department']
                if not all(field in reader.fieldnames for field in required_fields):
                    print(f"Error: CSV must contain these required columns: {', '.join(required_fields)}")
                    return 1

                conn = sqlite3.connect(str(_CENTRALDEFAULT_DB_PATH))
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                for row_num, row in enumerate(reader, 1):
                    try:
                        course_code = row['course_code'].strip().upper()
                        course_name = row['course_name'].strip()
                        department = row['department'].strip()

                        if not course_code or not course_name:
                            print(f"  Warning: Row {row_num} missing required data, skipping")
                            error_count += 1
                            continue

                        # Check for duplicates
                        cursor.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,))
                        if cursor.fetchone():
                            print(f"  Warning: Course {course_code} already exists, skipping")
                            error_count += 1
                            continue

                        # Prepare optional fields
                        description = row.get('description', '').strip()
                        level = row.get('level', '').strip()
                        credit_hours = float(row.get('credit_hours', 3.0))
                        max_enrollment = int(row.get('max_enrollment', 30))
                        course_type = row.get('course_type', 'Core').strip()

                        # Insert course
                        cursor.execute('''
                        INSERT INTO courses (
                            course_code, course_name, description, level, department,
                            credit_hours, max_enrollment, course_type, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (course_code, course_name, description, level, department,
                              credit_hours, max_enrollment, course_type, timestamp, timestamp))

                        # Mirror canonical values into legacy alias columns if they exist
                        try:
                            last_id = cursor.lastrowid
                            cursor.execute(
                                "UPDATE courses SET code = course_code, name = course_name, credits = credit_hours, date_added = COALESCE(date_added, created_at) WHERE id = ?",
                                (last_id,),
                            )
                        except Exception:
                            pass

                        imported_count += 1
                        print(f"  ✓ Imported: {course_code} - {course_name}")

                    except (ValueError, sqlite3.Error) as e:
                        print(f"  Error: Row {row_num} failed: {e}")
                        error_count += 1
                        continue

                conn.commit()
                conn.close()

            print(f"\nImport completed!")
            print(f"  Successfully imported: {imported_count} courses")
            print(f"  Errors/Skipped: {error_count} courses")
            return 0

        except Exception as e:
            print(f"Error: Failed to import CSV: {e}")
            return 1

    elif args.export_csv:
        # Handle CSV export
        print(f"Exporting courses to {args.export_csv}...")

        try:
            conn = sqlite3.connect(str(_CENTRALDEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM courses ORDER BY course_code")
            courses = cursor.fetchall()

            if not courses:
                print("No courses found in database.")
                conn.close()
                return 1

            # Get column names
            cursor.execute("PRAGMA table_info(courses)")
            columns = [col[1] for col in cursor.fetchall()]

            with open(args.export_csv, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns)
                writer.writerows(courses)

            conn.close()

            print(f"Successfully exported {len(courses)} courses to {args.export_csv}")
            return 0

        except Exception as e:
            print(f"Error: Failed to export CSV: {e}")
            return 1

    elif args.backup:
        # Handle backup
        print(f"Creating backup at {args.backup}...")

        try:
            conn = sqlite3.connect(str(_CENTRALDEFAULT_DB_PATH))

            if args.backup.endswith('.sql'):
                # SQL dump backup
                with open(args.backup, 'w') as f:
                    for line in conn.iterdump():
                        f.write('%s\n' % line)
                print(f"SQL dump backup created at {args.backup}")
            else:
                # Binary database copy
                backup_conn = sqlite3.connect(args.backup)
                conn.backup(backup_conn)
                backup_conn.close()
                print(f"Binary database backup created at {args.backup}")

            conn.close()
            print("Backup completed successfully!")
            return 0

        except Exception as e:
            print(f"Error: Failed to create backup: {e}")
            return 1
        
    else:
        # Default to GUI
        run_gui_application()

# =====================================================================
# ENTRY POINTS
# =====================================================================

if __name__ == "__main__":
    # Check if running from command line with arguments
    import sys
    if len(sys.argv) > 1:
        cli_interface()
    else:
        run_gui_application()

# =====================================================================
# MODULE LEVEL FUNCTIONS FOR BACKWARDS COMPATIBILITY
# =====================================================================

def init_gui_mode():
    """Initialize GUI mode - can be called from original module"""
    global _gui_app_instance
    if '_gui_app_instance' not in globals():
        root = tk.Tk()
        _gui_app_instance = CourseManagementGUI(root)
        
        # Start GUI in a separate thread to avoid blocking
        import threading
        gui_thread = threading.Thread(target=root.mainloop, daemon=True)
        gui_thread.start()
    
    return _gui_app_instance

def show_gui():
    """Show the GUI interface"""
    run_gui_application()

# Convenience functions for integration
def create_course_gui(auth=None):
    """Create course using GUI"""
    app = init_gui_mode()
    app.show_create_course()

def view_courses_gui(auth=None):
    """View courses using GUI"""
    app = init_gui_mode()
    app.refresh_course_list()

def search_courses_gui(auth=None):
    """Search courses using GUI"""
    app = init_gui_mode()
    app.show_search_dialog()

def analytics_gui(auth=None):
    """Show analytics using GUI"""
    app = init_gui_mode()
    app.generate_analytics()

# =====================================================================
# DOCUMENTATION AND HELP
# =====================================================================

def print_usage():
    """Print usage information"""
    print("""
Enhanced Course Management System - GUI Version

USAGE:
    python gui_course_management.py [options]

OPTIONS:
    --gui           Launch GUI interface (default)
    --cli           Use original CLI interface (if available)
    --import-csv    Import courses from CSV file
    --export-csv    Export courses to CSV file
    --backup        Create database backup

GUI FEATURES:
    • Tabbed interface for easy navigation
    • Advanced search and filtering
    • Course creation and editing dialogs
    • Real-time analytics and reporting
    • Instructor management
    • Prerequisites handling
    • Import/Export capabilities
    • System maintenance tools

BACKWARDS COMPATIBILITY:
    This GUI version is fully backwards compatible with the original
    CLI-based course management system. All original functions are
    supported and can be accessed through the GUI interface.

INTEGRATION:
    The GUI can be integrated with existing code by importing this
    module and calling the appropriate functions:
    
    from gui_course_management import show_gui
    show_gui()

For more information, see the Help menu in the GUI application.
""")

# Export key functions for external use
__all__ = [
    'CourseManagementGUI',
    'run_gui_application',
    'init_gui_mode',
    'show_gui',
    'create_course_gui',
    'view_courses_gui',
    'search_courses_gui',
    'analytics_gui',
    'BackwardsCompatibilityWrapper'
]
