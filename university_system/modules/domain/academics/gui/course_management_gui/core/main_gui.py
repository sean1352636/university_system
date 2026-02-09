# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
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
    print(_("course_management.warnings.original_module_not_found"))

# Import academic system launchers
try:
    from university_system.modules.domain.academics.services.lms.lms_core import launch_lms_gui
    from university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# Import dialog classes from submodules
from university_system.modules.domain.academics.gui.course_management_gui.courses.course_crud import (
    CourseCreateDialog, CourseEditDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.courses.course_status import (
    ManageCourseStatusDialog, CourseHistoryDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.schedules.schedules import (
    CreateScheduleDialog, ViewSchedulesDialog, UpdateScheduleDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.prerequisites.prerequisites import (
    PrerequisitesWindow, RemovePrerequisiteDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.search.search import (
    AdvancedCourseSearchDialog, AdvancedSearchDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.waitlists.waitlists import (
    AddToWaitlistDialog, ViewWaitlistsDialog, ProcessWaitlistDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.recommendations.recommendations import (
    RecommendCoursesDialog, AlternativeCourseDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.analytics.analytics import (
    CourseAnalyticsDialog, EnrollmentReportDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.bulk.bulk_operations import (
    BulkUpdateDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.maintenance.maintenance import (
    MaintenanceDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.import_export.import_export import (
    ImportExportDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.core.validation import (
    CourseValidationDialog
)
from university_system.modules.domain.academics.gui.course_management_gui.instructors.instructors import (
    InstructorCreateDialog, AssignInstructorDialog
)

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


class CourseManagementGUI:
    def __init__(self, parent, auth_system=None):
        self.root = parent
        self.root.title(_("course_management.title"))
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # Initialize authentication - accept passed auth or use centralized auth
        if auth_system:
            self.auth = auth_system
        else:
            # Use centralized auth system
            self.auth = get_auth()
            if self.auth is None:
                self.auth = UserAuth()

        # Create status bar FIRST so update_status() is safe during init
        self.status_var = tk.StringVar(value=_("course_management.status.initializing"))
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
            print(_("course_management.errors.user_role", error=str(e)))
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
                    self.update_status(_("course_management.status.database_initialized"))
                    return
                except (NameError, AttributeError):
                    # Function doesn't exist, fall back to our implementation
                    pass
            
            # Use our fallback implementation
            self.init_fallback_database()
            
        except Exception as e:
            # Don't crash the app, just show an error and continue
            print(_("course_management.errors.db_init", error=str(e)))
            try:
                self.init_fallback_database()
            except Exception as e2:
                print(_("course_management.errors.db_fallback_failed", error=str(e2)))
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

                self.update_status(_("course_management.status.database_initialized_with_count").format(count=course_count))

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
            self.update_status(_("course_management.status.minimal_database_created"), error=True)
            
        except Exception as e:
            self.update_status(_("course_management.status.database_creation_failed").format(error=e), error=True)
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
        import uuid

        for course_data in sample_courses:
            course_id = str(uuid.uuid4())
            course_code = course_data[0]
            course_name = course_data[1]
            credit_hours = course_data[6]

            cursor.execute('''
            INSERT INTO courses (
                id, code, name, credits, date_added,
                course_code, course_name, description, duration, level, department,
                credit_hours, contact_hours_per_week, learning_outcomes, assessment_methods,
                required_textbooks, course_fee, lab_required, online_available,
                max_enrollment, current_enrollment, status, course_type, tags,
                availability_periods, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (course_id, course_code, course_name, int(credit_hours), timestamp) + course_data + (timestamp, timestamp))

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
                    print(_("course_management.success.migration_executed", migration=migration))
                except sqlite3.Error as e:
                    print(_("course_management.errors.migration_failed", migration=migration, error=str(e)))

            conn.commit()

        except Exception as e:
            print(_("course_management.errors.migration_error", error=str(e)))

    def refresh_course_list(self):
        """FIXED: Enhanced error handling for course list refresh"""
        try:
            # Switch to courses tab first
            self.notebook.select(0)  # Courses tab is index 0

            # Clear existing items
            for item in self.course_tree.get_children():
                self.course_tree.delete(item)

            # Get courses from database
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Check if courses table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
                if not cursor.fetchone():
                    self.update_status(_("course_management.status.courses_table_not_found"), error=True)
                    return

                # Get table schema to handle missing columns gracefully
                cursor.execute("PRAGMA table_info(courses)")
                columns = {row[1]: row[2] for row in cursor.fetchall()}

                # Build query based on available columns - use actual database ID
                base_fields = "id, course_code, course_name"
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

                query = f"SELECT {base_fields}, {', '.join(extra_fields)} FROM courses WHERE course_code IS NOT NULL ORDER BY course_code"

                cursor.execute(query)
                courses = cursor.fetchall()

                # Populate treeview
                for course in courses:
                    self.course_tree.insert("", tk.END, values=course)

                self.update_status(_("course_management.status.courses_loaded", count=len(courses)))
            
        except sqlite3.Error as e:
            self.update_status(_("course_management.status.database_error", error=str(e)), error=True)
            print(_("course_management.errors.db_refresh", error=str(e)))
        except Exception as e:
            self.update_status(_("course_management.status.error_loading_courses", error=str(e)), error=True)
            print(_("course_management.errors.refresh_courses", error=str(e)))
    
    # Add decorator for safe database operations
    def safe_db_operation(func):
        """Decorator to safely handle database operations"""
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except sqlite3.Error as e:
                error_msg = _("course_management.errors.database_error_function", function=func.__name__, error=str(e))
                self.update_status(error_msg, error=True)
                messagebox.showerror(_("common.database_error"), error_msg)
                return None
            except Exception as e:
                error_msg = _("course_management.errors.error_in_function", function=func.__name__, error=str(e))
                self.update_status(error_msg, error=True)
                messagebox.showerror(_("common.error"), error_msg)
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
        menubar.add_cascade(label=_("course_management.menu.file"), menu=file_menu)

        # Admin and Staff can import/export
        if is_admin or is_staff:
            file_menu.add_command(label=_("course_management.menu.import_csv"), command=self.show_import_csv)
            file_menu.add_command(label=_("course_management.menu.export_csv"), command=self.show_export_csv)
            file_menu.add_separator()

        # Admin only - Database backup
        if is_admin:
            file_menu.add_command(label=_("course_management.menu.database_backup"), command=self.backup_database)
            file_menu.add_separator()

        file_menu.add_command(label=_("common.exit"), command=self.root.quit)

        # Course menu
        course_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("course_management.menu.courses"), menu=course_menu)

        # Admin and Staff can create courses
        if is_admin or is_staff:
            course_menu.add_command(label=_("course_management.menu.create_course"), command=self.show_create_course)

        # Everyone can view and search
        course_menu.add_command(label=_("course_management.menu.view_all_courses"), command=self.refresh_course_list)
        course_menu.add_command(label=_("course_management.menu.search_courses"), command=self.show_search_dialog)

        # Admin and Staff can manage prerequisites
        if is_admin or is_staff:
            course_menu.add_separator()
            course_menu.add_command(label=_("course_management.menu.manage_prerequisites"), command=self.show_prerequisites_window)
            course_menu.add_command(label=_("course_management.menu.remove_prerequisite"), command=self.show_remove_prerequisite)

        # Everyone can find alternatives
        course_menu.add_command(label=_("course_management.menu.find_alternatives"), command=self.find_alternative_courses)

        # Admin and Staff can manage status
        if is_admin or is_staff:
            course_menu.add_command(label=_("course_management.menu.manage_status"), command=self.show_manage_status)

        # Scheduling menu - Admin and Staff only
        if is_admin or is_staff:
            schedule_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.scheduling"), menu=schedule_menu)
            schedule_menu.add_command(label=_("course_management.menu.create_schedule"), command=self.show_create_schedule)
            schedule_menu.add_command(label=_("course_management.menu.update_schedule"), command=self.show_update_schedule)
            schedule_menu.add_command(label=_("course_management.menu.view_schedules"), command=self.show_view_schedules)
        elif is_student:
            # Students can only view schedules
            schedule_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.scheduling"), menu=schedule_menu)
            schedule_menu.add_command(label=_("course_management.menu.view_schedules"), command=self.show_view_schedules)

        # Enrollment menu - Admin and Staff only
        if is_admin or is_staff:
            enrollment_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.enrollment"), menu=enrollment_menu)
            enrollment_menu.add_command(label=_("course_management.menu.manage_waitlists"), command=self.show_add_waitlist)
            enrollment_menu.add_command(label=_("course_management.menu.process_waitlists"), command=self.show_process_waitlist)
            enrollment_menu.add_command(label=_("course_management.menu.view_waitlists"), command=self.show_view_waitlists)
        elif is_student:
            # Students can only view waitlists
            enrollment_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.enrollment"), menu=enrollment_menu)
            enrollment_menu.add_command(label=_("course_management.menu.view_waitlists"), command=self.show_view_waitlists)

        # Analytics menu
        analytics_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("course_management.menu.analytics"), menu=analytics_menu)

        # Admin and Staff get full analytics
        if is_admin or is_staff:
            analytics_menu.add_command(label=_("course_management.menu.course_analytics"), command=self.show_analytics)
            analytics_menu.add_command(label=_("course_management.menu.enrollment_report"), command=self.show_enrollment_report)
            analytics_menu.add_command(label=_("course_management.menu.department_statistics"), command=self.show_department_stats)
            analytics_menu.add_command(label=_("course_management.menu.course_history"), command=self.show_course_history)
            analytics_menu.add_command(label=_("course_management.menu.detailed_analytics"), command=self.show_course_analytics_detailed)
        elif is_student:
            # Students get limited analytics
            analytics_menu.add_command(label=_("course_management.menu.course_analytics"), command=self.show_analytics)
            analytics_menu.add_command(label=_("course_management.menu.course_history"), command=self.show_course_history)

        # Tools menu - Admin and Staff only
        if is_admin or is_staff:
            tools_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.tools"), menu=tools_menu)

            # Admin only - bulk operations
            if is_admin:
                tools_menu.add_command(label=_("course_management.menu.bulk_update"), command=self.show_bulk_update)
                tools_menu.add_command(label=_("course_management.menu.system_maintenance"), command=self.show_system_maintenance)

            tools_menu.add_command(label=_("course_management.menu.course_recommendations"), command=self.show_recommend_courses)
            tools_menu.add_separator()
            tools_menu.add_command(label=_("course_management.menu.advanced_search"), command=self.show_advanced_search)

            # Admin only - data validation
            if is_admin:
                tools_menu.add_command(label=_("course_management.menu.data_validation"), command=self.show_data_validation)

        # Help menu - available to everyone
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("course_management.menu.help"), menu=help_menu)
        help_menu.add_command(label=_("course_management.menu.about"), command=self.show_about)
        help_menu.add_command(label=_("course_management.menu.user_guide"), command=self.show_help)
        
    def create_main_interface(self):
        """Create the main interface with tabs"""
        # Create toolbar frame at the top
        toolbar_frame = ttk.Frame(self.root)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        # Return to Main Menu button
        home_button = ttk.Button(toolbar_frame, text=_("course_management.buttons.return_to_main_menu"),
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
        self.notebook.add(course_frame, text=_("course_management.tabs.course_list"))

        # Search and filter frame
        search_frame = ttk.LabelFrame(course_frame, text=_("course_management.labels.search_filter"), padding=10)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        # Search controls
        ttk.Label(search_frame, text=_("course_management.labels.search")).grid(row=0, column=0, sticky=tk.W)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.grid(row=0, column=1, padx=5)
        self.search_entry.bind('<KeyRelease>', self.on_search_change)

        ttk.Label(search_frame, text=_("course_management.labels.department")).grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        self.dept_filter = ttk.Combobox(search_frame, width=15)
        self.dept_filter.grid(row=0, column=3, padx=5)
        self.dept_filter.bind('<<ComboboxSelected>>', self.on_filter_change)

        ttk.Label(search_frame, text=_("course_management.labels.status")).grid(row=0, column=4, sticky=tk.W, padx=(20,0))
        self.status_filter = ttk.Combobox(search_frame, values=[_("common.all"), _("common.active"), _("common.inactive"), _("common.archived"), _("common.cancelled")], width=10)
        self.status_filter.set(_("common.all"))
        self.status_filter.grid(row=0, column=5, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        # Course list with treeview
        list_frame = ttk.Frame(course_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview with scrollbar
        columns = (
            _("course_management.columns.id"),
            _("course_management.columns.code"),
            _("course_management.columns.name"),
            _("course_management.columns.department"),
            _("course_management.columns.level"),
            _("course_management.columns.credits"),
            _("course_management.columns.enrollment"),
            _("course_management.columns.status")
        )
        column_labels = {
            "ID": _("course_management.columns.id"),
            "Code": _("course_management.columns.code"),
            "Name": _("course_management.columns.name"),
            "Department": _("course_management.columns.department"),
            "Level": _("course_management.columns.level"),
            "Credits": _("course_management.columns.credits"),
            "Enrollment": _("course_management.columns.enrollment"),
            "Status": _("course_management.columns.status")
        }
        self.course_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)

        # Configure column headings and widths
        for col in columns:
            self.course_tree.heading(col, text=column_labels.get(col, col), command=lambda c=col: self.sort_treeview(c))
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
            ttk.Button(buttons_frame, text=_("course_management.buttons.create_course"), command=self.show_create_course).pack(side=tk.LEFT, padx=5)

        # Admin and Staff can edit courses
        if is_admin or is_staff:
            ttk.Button(buttons_frame, text=_("course_management.buttons.edit_course"), command=self.edit_selected_course).pack(side=tk.LEFT, padx=5)

        # Only Admin can delete courses
        if is_admin:
            ttk.Button(buttons_frame, text=_("course_management.buttons.delete_course"), command=self.delete_selected_course).pack(side=tk.LEFT, padx=5)

        # Everyone can refresh
        ttk.Button(buttons_frame, text=_("common.refresh"), command=self.refresh_course_list).pack(side=tk.LEFT, padx=5)
        
        # Load initial data
        self.refresh_course_list()
        self.load_filter_options()
    
    def create_course_details_tab(self):
        """Create the course details tab"""
        details_frame = ttk.Frame(self.notebook)
        self.notebook.add(details_frame, text=_("course_management.tabs.course_details"))

        # Course selection frame
        selection_frame = ttk.LabelFrame(details_frame, text=_("course_management.labels.select_course"), padding=10)
        selection_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(selection_frame, text=_("course_management.labels.course")).pack(side=tk.LEFT)
        self.course_selector = ttk.Combobox(selection_frame, width=50)
        self.course_selector.pack(side=tk.LEFT, padx=5)
        self.course_selector.bind('<<ComboboxSelected>>', self.on_course_select)

        # Details display frame
        self.details_frame = ttk.LabelFrame(details_frame, text=_("course_management.labels.course_information"), padding=10)
        self.details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create scrolled text for details
        self.details_text = ScrolledText(self.details_frame, wrap=tk.WORD, height=20)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        
        # Load course options
        self.load_course_selector_options()
    
    def create_analytics_tab(self):
        """Create the analytics tab with role-based access"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text=_("course_management.tabs.analytics"))

        is_admin = self.is_admin()
        is_staff = self.is_staff()

        # Analytics controls - Admin and Staff only
        if is_admin or is_staff:
            controls_frame = ttk.LabelFrame(analytics_frame, text=_("course_management.labels.analytics_controls"), padding=10)
            controls_frame.pack(fill=tk.X, padx=5, pady=5)

            ttk.Button(controls_frame, text=_("course_management.buttons.generate_course_analytics"), command=self.generate_analytics).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text=_("course_management.messages.open_in_new_window"), command=self.open_analytics_window).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text=_("course_management.buttons.enrollment_report"), command=self.show_enrollment_report).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text=_("course_management.buttons.department_stats"), command=self.show_department_stats).pack(side=tk.LEFT, padx=5)

        # Analytics display
        self.analytics_text = ScrolledText(analytics_frame, wrap=tk.WORD, height=25)
        self.analytics_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def create_instructors_tab(self):
        """Create the instructors tab with role-based access"""
        instructors_frame = ttk.Frame(self.notebook)
        self.notebook.add(instructors_frame, text=_("course_management.tabs.instructors"))

        is_admin = self.is_admin()
        is_staff = self.is_staff()

        # Instructor controls - Admin and Staff only
        if is_admin or is_staff:
            controls_frame = ttk.LabelFrame(instructors_frame, text=_("course_management.labels.instructor_management"), padding=10)
            controls_frame.pack(fill=tk.X, padx=5, pady=5)

            # Admin only - Add instructor
            if is_admin:
                ttk.Button(controls_frame, text=_("course_management.buttons.add_instructor"), command=self.show_add_instructor).pack(side=tk.LEFT, padx=5)

            # Admin and Staff can view instructors
            ttk.Button(controls_frame, text=_("course_management.buttons.view_instructors"), command=self.refresh_instructor_list).pack(side=tk.LEFT, padx=5)

            # Admin only - Assign to course
            if is_admin:
                ttk.Button(controls_frame, text=_("course_management.buttons.assign_to_course"), command=self.show_assign_instructor).pack(side=tk.LEFT, padx=5)

        # Instructor list
        self.instructor_text = ScrolledText(instructors_frame, wrap=tk.WORD, height=25)
        self.instructor_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_academic_systems_tab(self):
        """Create the academic systems tab with LMS, Degree Audit, and Course Evaluation"""
        systems_frame = ttk.Frame(self.notebook)
        self.notebook.add(systems_frame, text=_("course_management.tabs.academic_systems"))

        # Title
        title_label = ttk.Label(systems_frame, text=_("course_management.labels.academic_management_systems"),
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=20)

        # Description
        desc_label = ttk.Label(systems_frame,
                              text=_("course_management.labels.academic_systems_description"),
                              wraplength=600, justify=tk.CENTER)
        desc_label.pack(pady=10)

        # Create scrollable canvas for systems
        canvas_frame = ttk.Frame(systems_frame)
        canvas_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        canvas = tk.Canvas(canvas_frame, bg='#f0f0f0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Systems container inside canvas
        container = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=container, anchor='nw')

        # Configure canvas scrolling
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
            # Make the container width match the canvas width
            canvas.itemconfig(canvas_window, width=event.width - 20)

        canvas.bind('<Configure>', configure_scroll)
        container.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        canvas.bind_all('<MouseWheel>', on_mousewheel)
        canvas.bind_all('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
        canvas.bind_all('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))

        # LMS System
        lms_frame = ttk.LabelFrame(container, text=_("course_management.labels.lms"), padding=20)
        lms_frame.pack(fill=tk.X, pady=10)

        lms_desc = ttk.Label(lms_frame,
                            text=_("course_management.labels.lms_description"),
                            wraplength=500)
        lms_desc.pack(pady=5)

        ttk.Button(lms_frame, text=_("course_management.buttons.launch_lms"),
                  command=self.show_lms_gui,
                  width=30).pack(pady=10)

        # Degree Audit System
        audit_frame = ttk.LabelFrame(container, text=_("course_management.labels.degree_audit"), padding=20)
        audit_frame.pack(fill=tk.X, pady=10)

        audit_desc = ttk.Label(audit_frame,
                              text=_("course_management.labels.degree_audit_description"),
                              wraplength=500)
        audit_desc.pack(pady=5)

        ttk.Button(audit_frame, text=_("course_management.buttons.launch_degree_audit"),
                  command=self.show_degree_audit_gui,
                  width=30).pack(pady=10)

        # Course Evaluation System
        eval_frame = ttk.LabelFrame(container, text=_("course_management.labels.course_evaluation"), padding=20)
        eval_frame.pack(fill=tk.X, pady=10)

        eval_desc = ttk.Label(eval_frame,
                             text=_("course_management.labels.course_evaluation_description"),
                             wraplength=500)
        eval_desc.pack(pady=5)

        ttk.Button(eval_frame, text=_("course_management.buttons.launch_course_evaluation"),
                  command=self.show_course_evaluation_gui,
                  width=30).pack(pady=10)

        # Status message if systems not available
        if not ACADEMIC_SYSTEMS_AVAILABLE:
            warning_label = ttk.Label(container,
                                    text=_("course_management.messages.systems_not_available"),
                                    foreground="orange")
            warning_label.pack(pady=10)

    def show_lms_gui(self):
        """Launch the LMS GUI"""
        try:
            if ACADEMIC_SYSTEMS_AVAILABLE:
                launch_lms_gui(self.root, self.auth)
            else:
                messagebox.showerror(_("common.error"), _("course_management.messages.lms_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_management.messages.lms_launch_failed").format(error=e))

    def show_degree_audit_gui(self):
        """Launch the Degree Audit GUI"""
        try:
            if ACADEMIC_SYSTEMS_AVAILABLE:
                launch_degree_audit_gui(self.root, self.auth)
            else:
                messagebox.showerror(_("common.error"), _("course_management.messages.degree_audit_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_management.messages.degree_audit_launch_failed").format(error=e))

    def show_course_evaluation_gui(self):
        """Launch the Course Evaluation GUI"""
        try:
            if ACADEMIC_SYSTEMS_AVAILABLE:
                launch_course_evaluation_gui(self.root, self.auth)
            else:
                messagebox.showerror(_("common.error"), _("course_management.messages.course_evaluation_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_management.messages.course_evaluation_launch_failed").format(error=e))

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
            self.update_status(_("course_management.status.prerequisite_removed"))

    def show_manage_status(self):
        """Show manage course status dialog"""
        dialog = ManageCourseStatusDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_course_list()
            self.update_status(_("course_management.status.course_status_updated"))

    def show_import_csv(self):
        """Show import CSV dialog"""
        dialog = ImportExportDialog(self.root, self.auth, "import")
        if dialog.result:
            self.refresh_course_list()
            self.update_status(_("course_management.status.courses_imported"))

    def show_export_csv(self):
        """Show export CSV dialog"""
        dialog = ImportExportDialog(self.root, self.auth, "export")
        if dialog.result:
            self.update_status(_("course_management.status.courses_exported"))

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
            self.update_status(_("course_management.status.maintenance_completed"))

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
            self.update_status(_("course_management.status.course_created").format(course=dialog.result))

    def edit_selected_course(self):
        """Edit the selected course"""
        selection = self.course_tree.selection()
        if not selection:
            messagebox.showwarning(_("course_management.messages.no_selection"), _("course_management.messages.select_course_to_edit"))
            return
        
        item = self.course_tree.item(selection[0])
        course_id = item['values'][0]
        
        dialog = CourseEditDialog(self.root, self.auth, course_id)
        if dialog.result:
            self.refresh_course_list()
            self.update_status(_("course_management.status.course_updated"))

    def delete_selected_course(self):
        """Delete the selected course"""
        selection = self.course_tree.selection()
        if not selection:
            messagebox.showwarning(_("course_management.messages.no_selection"), _("course_management.messages.select_course_to_delete"))
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
                self.update_status(_("course_management.status.course_deleted").format(course=course_code))

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), _("course_management.messages.delete_course_failed").format(error=e))

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

            print(_("course_management.success.students_reassigned", count=reassignment_count, code=course_code))

        except Exception as e:
            print(_("course_management.errors.student_reassignment", error=str(e)))

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
            print(_("course_management.success.modules_deleted", count=len(modules), code=course_code))

        except Exception as e:
            print(_("course_management.errors.module_delete", code=course_code, error=str(e)))

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
            print(_("course_management.errors.assignment_delete", code=module_code, error=str(e)))

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

                print(_("course_management.success.student_assigned_modules", id=student_id, count=len(selected_modules), code=course_code))

        except Exception as e:
            print(_("course_management.errors.student_assign_modules", id=student_id, error=str(e)))

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
                message += _("course_management.messages.deletion_warning") + "\n"
                message += _("course_management.messages.consider_inactive") + "\n\n"

            message += _("course_management.messages.action_cannot_be_undone")

            return messagebox.askyesno(_("course_management.dialogs.confirm_deletion"), message)

        except sqlite3.Error:
            return messagebox.askyesno(_("course_management.dialogs.confirm_deletion"), _("course_management.messages.delete_course_confirm").format(code=course_code, name=course_name))
        
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
            SELECT id, course_code, course_name,
                   COALESCE(department, 'N/A') as department,
                   COALESCE(level, 'N/A') as level,
                   COALESCE(credit_hours, 3.0) as credit_hours,
                   COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment,
                   COALESCE(status, 'Active') as status
            FROM courses WHERE course_code IS NOT NULL
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

            self.update_status(_("course_management.status.search_found", count=len(courses)))
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.search_failed").format(error=e))
    
    def load_filter_options(self):
        """Load options for filter dropdowns"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Load departments
                cursor.execute("SELECT DISTINCT department FROM courses WHERE course_code IS NOT NULL AND department IS NOT NULL ORDER BY department")
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
                    messagebox.showerror(_("common.error"), _("course_management.messages.course_not_found"))
                    return

                # Switch to details tab and populate
                self.notebook.select(1)  # Details tab

                # Format course details
                details = self.format_course_details(course)

                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, details)
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_load_course_details", error=str(e)))
    
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

                # Overall statistics (using case-insensitive status check)
                cursor.execute("""
                SELECT
                    COUNT(*) as total_courses,
                    SUM(COALESCE(current_enrollment, 0)) as total_students,
                    SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                    AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                """)

                stats = cursor.fetchone()
                if stats:
                    analytics_text += "OVERALL STATISTICS:\n"
                    analytics_text += f"Total Active Courses: {stats[0] or 0}\n"
                    analytics_text += f"Total Students Enrolled: {stats[1] or 0}\n"
                    analytics_text += f"Total System Capacity: {stats[2] or 0}\n"
                    avg_enrollment = stats[3] if stats[3] is not None else 0.0
                    analytics_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                    if stats[2] and stats[2] > 0:
                        fill_rate = (stats[1] / stats[2]) * 100
                        analytics_text += f"System Fill Rate: {fill_rate:.1f}%\n"
                    available = (stats[2] or 0) - (stats[1] or 0)
                    analytics_text += f"Available Spots: {available}\n\n"

                # Department breakdown
                cursor.execute("""
                SELECT
                    COALESCE(department, 'Unknown') as dept,
                    COUNT(*) as course_count,
                    SUM(COALESCE(current_enrollment, 0)) as total_students
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
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
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
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
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
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

            self.update_status(_("course_management.status.analytics_generated"))

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))

    def open_analytics_window(self):
        """Open analytics/statistics in a new window with export and email options"""
        # Generate analytics data
        analytics_text = self._generate_analytics_text()

        if not analytics_text:
            return

        # Create new window
        window = tk.Toplevel(self.root)
        window.title(_("course_management.dialogs.course_analytics_report"))
        window.geometry("800x600")
        window.transient(self.root)

        # Main frame
        main_frame = ttk.Frame(window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_("course_management.dialogs.course_analytics_report"),
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))

        # Analytics display
        text_widget = ScrolledText(main_frame, wrap=tk.WORD, height=30)
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_widget.insert(1.0, analytics_text)
        text_widget.config(state='disabled')

        # Store analytics text for later use
        window.analytics_content = analytics_text

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))

        # Export as TXT button
        def export_txt():
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"course_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(analytics_text)
                        f.write(f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_saved", filename=filename))
                except Exception as e:
                    messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_save_report", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.export_as_txt"),
                  command=export_txt).pack(side=tk.LEFT, padx=5)

        # Email to Admin button
        def email_to_admin():
            try:
                # Get admin email from database
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Try to get admin email from users table
                cursor.execute("""
                    SELECT email FROM users
                    WHERE role IN ('admin', 'administrator', 'Admin', 'Administrator')
                    AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                result = cursor.fetchone()
                admin_email = result[0] if result else None
                conn.close()

                # If not found, prompt for it
                if not admin_email:
                    admin_email = tk.simpledialog.askstring(_("course_management.messages.admin_email"),
                        _("course_management.labels.admin_email_address"),
                        parent=window)

                if not admin_email:
                    return

                # Render email from template
                from university_system.infrastructure.email.template_utils import render_template

                subject, body = render_template('academics/course_analytics_report', {
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'analytics_content': analytics_text,
                    'generated_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = f"Course Analytics Report - {datetime.now().strftime('%Y-%m-%d')}"
                    body = analytics_text + f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

                send_email(admin_email, subject, body)
                messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_sent", admin_email=admin_email))

            except Exception as e:
                messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_send_email", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.email_to_admin"),
                  command=email_to_admin).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(button_frame, text=_("common.close"),
                  command=window.destroy).pack(side=tk.RIGHT, padx=5)

    def _generate_analytics_text(self):
        """Generate analytics text content (extracted for reuse)"""
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
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                """)

                stats = cursor.fetchone()
                if stats:
                    analytics_text += "OVERALL STATISTICS:\n"
                    analytics_text += f"Total Active Courses: {stats[0] or 0}\n"
                    analytics_text += f"Total Students Enrolled: {stats[1] or 0}\n"
                    analytics_text += f"Total System Capacity: {stats[2] or 0}\n"
                    avg_enrollment = stats[3] if stats[3] is not None else 0.0
                    analytics_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                    if stats[2] and stats[2] > 0:
                        fill_rate = (stats[1] / stats[2]) * 100
                        analytics_text += f"System Fill Rate: {fill_rate:.1f}%\n"
                    available = (stats[2] or 0) - (stats[1] or 0)
                    analytics_text += f"Available Spots: {available}\n\n"

                # Department breakdown
                cursor.execute("""
                SELECT
                    COALESCE(department, 'Unknown') as dept,
                    COUNT(*) as course_count,
                    SUM(COALESCE(current_enrollment, 0)) as total_students
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
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
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
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
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
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

                return analytics_text

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to generate analytics: {e}")
            return None

    def show_enrollment_report(self):
        """Show enrollment report dialog"""
        dialog = EnrollmentReportDialog(self.root)
        if dialog.result:
            # Generate selected report type and open in new window
            report_type = dialog.result
            self.open_enrollment_report_window(report_type)
    
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

                ttk.Button(self.report_action_frame, text=_("course_management.buttons.visualize_report"),
                          command=self.visualize_report).pack(side=tk.LEFT, padx=5)
                ttk.Button(self.report_action_frame, text=_("course_management.buttons.email_report_to_admin"),
                          command=self.email_report).pack(side=tk.LEFT, padx=5)

            self.update_status(_("course_management.status.report_generated"))

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))

    def open_enrollment_report_window(self, report_type):
        """Open enrollment report in a new window with export and email options"""
        # Generate report text
        report_text = self._generate_enrollment_report_text(report_type)

        if not report_text:
            return

        # Create new window
        window = tk.Toplevel(self.root)
        window.title(_("course_management.dialogs.enrollment_report_type", type=report_type))
        window.geometry("900x600")
        window.transient(self.root)

        # Main frame
        main_frame = ttk.Frame(window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_("course_management.dialogs.enrollment_report_type", type=report_type),
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))

        # Report display
        text_widget = ScrolledText(main_frame, wrap=tk.WORD, height=30)
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_widget.insert(1.0, report_text)
        text_widget.config(state='disabled')

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))

        # Export as TXT button
        def export_txt():
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"enrollment_report_{report_type.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(report_text)
                    messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_saved", filename=filename))
                except Exception as e:
                    messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_save_report", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.export_as_txt"),
                  command=export_txt).pack(side=tk.LEFT, padx=5)

        # Email to Admin button
        def email_to_admin():
            try:
                # Get admin email from database
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Try to get admin email from users table
                cursor.execute("""
                    SELECT email FROM users
                    WHERE role IN ('admin', 'administrator', 'Admin', 'Administrator')
                    AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                result = cursor.fetchone()
                admin_email = result[0] if result else None
                conn.close()

                # If not found, prompt for it
                if not admin_email:
                    admin_email = tk.simpledialog.askstring(_("course_management.messages.admin_email"),
                        _("course_management.labels.admin_email_address"),
                        parent=window)

                if not admin_email:
                    return

                # Render email from template
                from university_system.infrastructure.email.template_utils import render_template

                subject, body = render_template('academics/enrollment_report', {
                    'report_type': report_type,
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'report_content': report_text
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = f"Enrollment Report - {report_type} - {datetime.now().strftime('%Y-%m-%d')}"
                    body = report_text

                send_email(admin_email, subject, body)
                messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_sent", admin_email=admin_email))

            except Exception as e:
                messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_send_email", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.email_to_admin"),
                  command=email_to_admin).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(button_frame, text=_("common.close"),
                  command=window.destroy).pack(side=tk.RIGHT, padx=5)

    def _generate_enrollment_report_text(self, report_type):
        """Generate enrollment report text (extracted for reuse)"""
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
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                    """)

                    summary = cursor.fetchone()
                    report_text += f"Total Active Courses: {summary[0] or 0}\n"
                    report_text += f"Total Students Enrolled: {summary[1] or 0}\n"
                    report_text += f"Total System Capacity: {summary[2] or 0}\n"
                    avg_enrollment = summary[3] if summary[3] is not None else 0.0
                    report_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                    if summary[2] and summary[2] > 0:
                        report_text += f"System Fill Rate: {(summary[1]/summary[2]*100):.1f}%\n"
                    available = (summary[2] or 0) - (summary[1] or 0)
                    report_text += f"Available Spots: {available}\n"

                elif report_type == "Department":
                    cursor.execute("""
                    SELECT
                        COALESCE(department, 'Unknown') as dept,
                        COUNT(*) as course_count,
                        SUM(COALESCE(current_enrollment, 0)) as total_students,
                        SUM(COALESCE(max_enrollment, 0)) as total_capacity
                    FROM courses
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
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
                           COALESCE(current_enrollment, 0), COALESCE(max_enrollment, 0)
                    FROM courses
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                    ORDER BY current_enrollment DESC
                    """)

                    course_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<25} {'Dept':<12} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 77 + "\n"

                    for code, name, dept, level, enrolled, capacity in course_data:
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
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                    ORDER BY available DESC
                    """)

                    capacity_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<30} {'Department':<15} {'Enrolled':<10} {'Capacity':<10} {'Available':<10}\n"
                    report_text += "-" * 83 + "\n"

                    for code, name, dept, enrolled, capacity, available in capacity_data:
                        name_short = name[:27] + "..." if len(name) > 30 else name
                        dept_short = dept[:12] + "..." if dept and len(dept) > 15 else dept or "N/A"
                        report_text += f"{code:<8} {name_short:<30} {dept_short:<15} {enrolled:<10} {capacity:<10} {available:<10}\n"

                return report_text

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))
            return None

    def visualize_report(self):
        """Generate and display visual charts for the current report"""
        if not hasattr(self, 'last_report_data'):
            messagebox.showwarning(_("course_management.messages.no_report"), _("course_management.messages.generate_report_first"))
            return

        if not CHARTS_AVAILABLE:
            messagebox.showerror(_("course_management.messages.charts_unavailable"),
                               _("course_management.messages.charts_unavailable"))
            return

        report_type = self.last_report_data['type']

        try:
            # Create chart window
            chart_window = tk.Toplevel(self.root)
            chart_window.title(_("course_management.dialogs.report_visualization", type=report_type))
            chart_window.geometry("1200x800")
            chart_window.transient(self.root)

            # Create main frame
            main_frame = ttk.Frame(chart_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_("course_management.dialogs.report_visualization", type=report_type),
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
            ttk.Button(main_frame, text=_("common.close"), command=chart_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("course_management.messages.visualization_error"), _("course_management.messages.failed_create_charts", error=str(e)))
            print(_("course_management.errors.chart_generation", error=str(e)))

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
        notebook.add(frame1, text=_("course_management.analytics_tabs.enrollment_overview"))

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
        notebook.add(frame2, text=_("course_management.analytics_tabs.capacity_fill_rate"))

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
        notebook.add(frame1, text=_("course_management.analytics_tabs.students_by_department"))

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
        notebook.add(frame2, text=_("course_management.analytics_tabs.courses_by_department"))

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
        notebook.add(frame3, text=_("course_management.analytics_tabs.fill_rate_by_department"))

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
        notebook.add(frame1, text=_("course_management.analytics_tabs.top_courses"))

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
        notebook.add(frame2, text=_("course_management.analytics_tabs.enrollment_vs_capacity"))

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
        notebook.add(frame1, text=_("course_management.analytics_tabs.available_spots"))

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
        notebook.add(frame2, text=_("course_management.analytics_tabs.utilization_breakdown"))

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
            messagebox.showwarning(_("course_management.messages.no_report"), _("course_management.messages.generate_report_first"))
            return

        if not EMAIL_AVAILABLE:
            messagebox.showerror(_("course_management.messages.email_service_unavailable"),
                               _("course_management.messages.email_service_unavailable"))
            return

        # Create email dialog
        email_dialog = tk.Toplevel(self.root)
        email_dialog.title(_("course_management.dialogs.email_course_report"))
        email_dialog.geometry("1000x750")
        email_dialog.transient(self.root)
        email_dialog.grab_set()

        frame = ttk.Frame(email_dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_("course_management.labels.email_course_management_report"),
                 font=("Arial", 14, "bold")).pack(pady=(0, 20))

        # Get admin email from database
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1")
                admin_row = cursor.fetchone()
                default_email = admin_row[0] if admin_row else "admin@university.edu"
        except Exception as e:
            print(_("course_management.warnings.admin_email_fetch_failed", error=str(e)))
            default_email = "admin@university.edu"

        ttk.Label(frame, text=_("course_management.labels.admin_email_address")).pack(anchor='w', pady=(0, 5))
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
                        admin_select_dialog.title(_("course_management.dialogs.select_admin"))
                        admin_select_dialog.geometry("900x700")
                        admin_select_dialog.transient(email_dialog)
                        admin_select_dialog.grab_set()

                        ttk.Label(admin_select_dialog, text=_("course_management.labels.select_admin_user"),
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

                        ttk.Button(admin_select_dialog, text=_("course_management.buttons.select"),
                                  command=select_admin).pack(pady=10)
                    else:
                        email_var.set(admins[0][1])
                        messagebox.showinfo(_("course_management.messages.admin_email"), _("course_management.messages.using_admin_email", email=admins[0][1]))
                else:
                    messagebox.showwarning(_("course_management.messages.no_admins_found"), _("course_management.messages.no_admins_found"))
            except Exception as e:
                messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_load_course_details", error=str(e)))

        ttk.Button(email_frame, text="🔄", command=refresh_admin_email, width=3).pack(side='left', padx=(5, 0))

        ttk.Label(frame, text=_("course_management.labels.subject")).pack(anchor='w', pady=(10, 5))
        subject_var = tk.StringVar(value=f"Course Management Report - {self.last_report_data['type']}")
        ttk.Entry(frame, textvariable=subject_var, width=60).pack(fill='x', pady=(0, 10))

        ttk.Label(frame, text=_("course_management.labels.message_optional")).pack(anchor='w', pady=(10, 5))
        message_text = ScrolledText(frame, height=8, wrap=tk.WORD)
        message_text.pack(fill='both', expand=True, pady=(0, 10))
        message_text.insert('1.0', "Please find the course management report below.\n\n"
                                   "This report was automatically generated from the Course Management GUI.")

        ttk.Label(frame, text=_("course_management.labels.report_preview")).pack(anchor='w', pady=(10, 5))
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
                    messagebox.showwarning(_("course_management.messages.invalid_email"), _("course_management.messages.invalid_email"))
                    return

                # Render email from template
                from university_system.infrastructure.email.template_utils import render_template

                template_subject, template_body = render_template('academics/course_management_report', {
                    'custom_message': message,
                    'separator': '=' * 80,
                    'report_content': self.last_report_data['text'],
                    'report_type': self.last_report_data['type'],
                    'generated_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

                # Use template if available, otherwise fallback
                if template_subject and template_body:
                    # Subject from dialog takes precedence
                    body = template_body
                else:
                    # Fallback to hardcoded format
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

                messagebox.showinfo(_("course_management.messages.email_sent_success"),
                                  _("course_management.messages.email_sent_success", email=admin_email, subject=subject))
                email_dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("course_management.messages.email_error_details"),
                                   _("course_management.messages.email_error_details", error=str(e)))
                print(_("course_management.errors.email", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(button_frame, text=_("course_management.buttons.send_email"),
                  command=send_email_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_("common.cancel"),
                  command=email_dialog.destroy).pack(side='right')

    def show_department_stats(self):
        """Show department statistics dialog with enhanced GUI display"""
        try:
            # Create department stats window
            stats_window = tk.Toplevel(self.root)
            stats_window.title(_("course_management.dialogs.department_stats"))
            stats_window.geometry("800x600")
            stats_window.transient(self.root)

            main_frame = ttk.Frame(stats_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Department selection
            selection_frame = ttk.Frame(main_frame)
            selection_frame.pack(fill=tk.X, pady=5)

            ttk.Label(selection_frame, text=_("course_management.labels.department_colon")).pack(side=tk.LEFT)
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

            ttk.Button(selection_frame, text=_("course_management.buttons.update"), command=update_stats).pack(side=tk.LEFT, padx=5)

            # Export and email buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=10)

            def export_stats_txt():
                selected_dept = dept_var.get()
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                    initialfile=f"dept_stats_{selected_dept.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )
                if filename:
                    try:
                        stats_content = stats_text.get(1.0, tk.END)
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(stats_content)
                            f.write(f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.statistics_saved_to", filename=filename))
                    except Exception as e:
                        messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_save_statistics", error=str(e)))

            def email_stats_to_admin():
                try:
                    # Get admin email from database
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT email FROM users
                        WHERE role IN ('admin', 'administrator', 'Admin', 'Administrator')
                        AND email IS NOT NULL AND email != ''
                        LIMIT 1
                    """)
                    result = cursor.fetchone()
                    admin_email = result[0] if result else None
                    conn.close()

                    # If not found, prompt for it
                    if not admin_email:
                        admin_email = tk.simpledialog.askstring("Admin Email",
                            "Enter admin email address:",
                            parent=stats_window)

                    if not admin_email:
                        return

                    # Render email from template
                    from university_system.infrastructure.email.template_utils import render_template

                    selected_dept = dept_var.get()
                    stats_content = stats_text.get(1.0, tk.END)

                    subject, body = render_template('academics/department_statistics', {
                        'department_name': selected_dept,
                        'report_date': datetime.now().strftime('%Y-%m-%d'),
                        'statistics_content': stats_content,
                        'generated_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })

                    # Fallback if template not found
                    if not subject or not body:
                        subject = f"Department Statistics - {selected_dept} - {datetime.now().strftime('%Y-%m-%d')}"
                        body = stats_content + f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

                    send_email(admin_email, subject, body)
                    messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.statistics_sent_to", admin_email=admin_email))

                except Exception as e:
                    messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_send_email", error=str(e)))

            ttk.Button(button_frame, text=_("course_management.buttons.export_as_txt"),
                      command=export_stats_txt).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_("course_management.buttons.email_to_admin"),
                      command=email_stats_to_admin).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_("common.close"),
                      command=stats_window.destroy).pack(side=tk.RIGHT, padx=5)

            # Initial load
            update_stats()
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))
    
    # =====================================================================
    # INSTRUCTOR MANAGEMENT
    # =====================================================================
    
    def show_add_instructor(self):
        """Show add instructor dialog"""
        dialog = InstructorCreateDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_instructor_list()
            self.update_status(_("course_management.messages.instructor_added_success", name=dialog.result))
    
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
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))
    
    def show_assign_instructor(self):
        """Show assign instructor to course dialog"""
        dialog = AssignInstructorDialog(self.root, self.auth)
        if dialog.result:
            self.update_status(_("course_management.messages.instructor_assigned_success"))
    
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
            FROM courses WHERE course_code IS NOT NULL
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

            self.update_status(_("course_management.messages.search_completed_count", count=len(courses)))
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.search_failed").format(error=e))
    
    def show_prerequisites_window(self):
        """Show prerequisites management window"""
        PrerequisitesWindow(self.root, self.auth)
    
    def show_bulk_update(self):
        """Show bulk update dialog"""
        dialog = BulkUpdateDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_course_list()
            self.update_status(_("course_management.status.bulk_update_completed"))
    
    def show_maintenance(self):
        """Show system maintenance dialog"""
        dialog = MaintenanceDialog(self.root, self.auth)
        if dialog.result:
            self.update_status(_("course_management.status.maintenance_completed"))
    
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
                    messagebox.showerror(_("common.import_error"), _("course_management.messages.csv_missing_required_columns", columns=', '.join(required_fields)))
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
                        cursor.execute("SELECT id FROM courses WHERE code = ?", (course_code,))
                        if cursor.fetchone():
                            error_count += 1
                            continue

                        # Prepare optional fields
                        description = row.get('description', '').strip()
                        level = row.get('level', '').strip()
                        credit_hours = float(row.get('credit_hours', 3.0))
                        max_enrollment = int(row.get('max_enrollment', 30))
                        course_type = row.get('course_type', 'Core').strip()

                        import uuid
                        course_id = str(uuid.uuid4())

                        # Insert course
                        cursor.execute('''
                        INSERT INTO courses (
                            id, code, name, credits, date_added,
                            course_code, course_name, description, level, department,
                            credit_hours, max_enrollment, course_type, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (course_id, course_code, course_name, int(credit_hours), timestamp,
                              course_code, course_name, description, level, department,
                              credit_hours, max_enrollment, course_type, timestamp, timestamp))

                        imported_count += 1
                        
                    except (ValueError, sqlite3.Error):
                        error_count += 1
                        continue
                
                conn.commit()
                conn.close()
            
            self.refresh_course_list()

            message = _("course_management.messages.import_results", success=imported_count, errors=error_count)
            messagebox.showinfo(_("course_management.messages.import_results"), message)
            self.update_status(_("course_management.status.import_completed"))

        except Exception as e:
            messagebox.showerror(_("common.import_error"), _("course_management.messages.failed_import_csv", error=str(e)))
    
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

            messagebox.showinfo(_("common.export_complete"), _("course_management.messages.export_complete_count", count=len(courses), file=file_path))
            self.update_status(_("course_management.status.export_completed", count=len(courses)))

        except Exception as e:
            messagebox.showerror(_("common.export_error"), _("course_management.messages.failed_export_csv", error=str(e)))
    
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

            messagebox.showinfo(_("course_management.messages.backup_complete"), _("course_management.messages.backup_complete", file=file_path))
            self.update_status(_("course_management.status.database_backup_created"))

        except Exception as e:
            messagebox.showerror(_("course_management.messages.backup_error"), _("course_management.messages.failed_backup", error=str(e)))

    def view_course_details(self, cursor, course_id):
        """Enhanced course details viewer"""
        cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        course = cursor.fetchone()
        
        if not course:
            messagebox.showerror(_("common.error"), _("course_management.messages.course_not_found"))
            return

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(_("course_management.dialogs.course_details", name=course[1]))
        details_window.geometry("600x700")
        details_window.transient(self.root)
        
        # Create notebook for different views
        notebook = ttk.Notebook(details_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Basic Info Tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text=_("course_management.analytics_tabs.basic_info"))
        
        basic_text = ScrolledText(basic_frame, wrap=tk.WORD)
        basic_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        basic_text.insert(tk.END, self.format_course_details(course))
        basic_text.config(state=tk.DISABLED)
        
        # Prerequisites Tab
        prereq_frame = ttk.Frame(notebook)
        notebook.add(prereq_frame, text=_("course_management.analytics_tabs.prerequisites"))
        
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
        notebook.add(schedule_frame, text=_("course_management.analytics_tabs.schedule"))
        
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
        ttk.Button(details_window, text=_("common.close"), command=details_window.destroy).pack(pady=10)

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
        except Exception:
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
        
        messagebox.showinfo(_("course_management.dialogs.about_system"), about_text)
    
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
        help_window.title(_("course_management.dialogs.user_guide"))
        help_window.geometry("600x400")
        
        help_text_widget = ScrolledText(help_window, wrap=tk.WORD)
        help_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        help_text_widget.insert(1.0, help_text)
        help_text_widget.config(state=tk.DISABLED)

    def return_to_main_menu(self):
        """Return to the main menu/GUI"""
        if messagebox.askyesno(_("course_management.messages.return_to_main_menu_confirm"), _("course_management.messages.return_to_main_menu_confirm")):
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
                messagebox.showerror(_("common.error"), _("course_management.messages.failed_return_to_main", error=str(e)))
