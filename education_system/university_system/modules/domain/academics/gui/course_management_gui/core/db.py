from ._imports import (
    _, datetime, messagebox, tk, sqlite3, DEFAULT_DB_PATH,
    ORIGINAL_MODULE_AVAILABLE, initialize_enhanced_database,
)


class DatabaseMixin:
    """Database initialization, migration, and refresh operations."""

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
