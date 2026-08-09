"""Extracted AcademicCalendarManager schema methods."""

from ._shared import *  # noqa: F401,F403


class SchemaMixin:
    def _initialize_database(self):
        """Initialize database schema with better error handling"""
        try:
            logger.info("Initializing calendar database...")

            # Create core tables first
            self._create_core_tables()

            # Create enhanced tables
            self._create_enhanced_tables()

            # Create indexes
            self._create_indexes()

            # Create default data
            self._create_default_data()

            logger.info("Calendar database initialized successfully")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}")

    def _create_minimal_tables(self):
        """Create minimal required tables if full initialization fails"""
        try:
            logger.info("Creating minimal calendar tables...")

            # Create the most basic tables needed for calendar functionality
            minimal_tables = [
                '''CREATE TABLE IF NOT EXISTS academic_calendar_events (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    date TEXT,
                    date_start TEXT,
                    date_end TEXT,
                    description TEXT,
                    event_type TEXT DEFAULT 'Academic',
                    date_added TEXT NOT NULL,
                    last_modified TEXT,
                    created_by TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    audience TEXT,
                    assignment_id INTEGER,
                    trip_id INTEGER,
                    organizer TEXT,
                    participants TEXT,
                    status TEXT,
                    country_code TEXT,
                    region TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    CONSTRAINT valid_event_dates CHECK (
                        date_start IS NULL OR date_end IS NULL OR date_start <= date_end
                    )
                )''',

                '''CREATE TABLE IF NOT EXISTS academic_years (
                    id TEXT PRIMARY KEY,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    date_added TEXT NOT NULL
                )''',

                '''CREATE TABLE IF NOT EXISTS semesters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    academic_year_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    date_added TEXT NOT NULL
                )''',

                # trip_calendar_events folded into academic_calendar_events
                # (trip_id column links a calendar event to its trip).
            ]

            for table_sql in minimal_tables:
                try:
                    self.db_manager.execute_update(table_sql)
                    logger.debug("Created table successfully")
                except Exception as e:
                    logger.warning(f"Table creation warning: {e}")

            logger.info("Minimal calendar tables created successfully")

        except Exception as e:
            logger.error(f"Failed to create minimal tables: {e}")
            raise

    def _create_backup_directory(self):
        """Create backup directory if it doesn't exist"""
        try:
            import os
            backup_dir = getattr(self.config, 'backup_directory', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            logger.debug(f"Backup directory ensured: {backup_dir}")
        except Exception as e:
            logger.warning(f"Could not create backup directory: {e}")

    def _verify_required_tables(self):
        """Verify that required tables exist, create missing ones"""
        try:
            required_tables = {
                'academic_years': '''
                    CREATE TABLE IF NOT EXISTS academic_years (
                        id TEXT PRIMARY KEY,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        date_added TEXT NOT NULL
                    )
                ''',
                'semesters': '''
                    CREATE TABLE IF NOT EXISTS semesters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        academic_year_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        date_added TEXT NOT NULL
                    )
                ''',
                'events': '''
                    CREATE TABLE IF NOT EXISTS academic_calendar_events (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        date TEXT,
                        date_start TEXT,
                        date_end TEXT,
                        description TEXT,
                        event_type TEXT DEFAULT 'Academic',
                        date_added TEXT NOT NULL,
                        last_modified TEXT,
                        created_by TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        location TEXT,
                        audience TEXT,
                        assignment_id INTEGER,
                        trip_id INTEGER,
                        organizer TEXT,
                        participants TEXT,
                        status TEXT,
                        country_code TEXT,
                        region TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        CONSTRAINT valid_event_dates CHECK (
                            date_start IS NULL OR date_end IS NULL OR date_start <= date_end
                        )
                    )
                ''',
                'event_categories': '''
                    CREATE TABLE IF NOT EXISTS event_categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        color_code TEXT,
                        description TEXT,
                        date_added TEXT NOT NULL
                    )
                '''
            }

            from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
            for table_name, create_sql in required_tables.items():
                try:
                    # Test if table exists by querying it
                    safe_table = validate_identifier(table_name, "table")
                    self.db_manager.execute_query("SELECT COUNT(*) FROM [" + safe_table + "] LIMIT 1")
                    logger.debug(f"Table {table_name} exists")
                except Exception:
                    # Table doesn't exist, create it
                    logger.info(f"Creating missing table: {table_name}")
                    self.db_manager.execute_update(create_sql)
                    logger.info(f"Successfully created table: {table_name}")

            logger.info("Required tables verified/created successfully")
            return True

        except Exception as e:
            logger.error(f"Table verification failed: {e}")
            return False

    def _create_core_tables(self):
        """Create core database tables"""
        try:
            tables = [
                '''CREATE TABLE IF NOT EXISTS academic_years (
                    id TEXT PRIMARY KEY,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    date_added TEXT NOT NULL,
                    CONSTRAINT valid_dates CHECK (start_date < end_date)
                )''',

                '''CREATE TABLE IF NOT EXISTS semesters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    academic_year_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    registration_start TEXT,
                    registration_end TEXT,
                    final_exams_start TEXT,
                    final_exams_end TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (academic_year_id) REFERENCES academic_years (id) ON DELETE CASCADE,
                    UNIQUE(academic_year_id, name),
                    CONSTRAINT valid_semester_dates CHECK (start_date < end_date)
                )''',

                '''CREATE TABLE IF NOT EXISTS academic_calendar_events (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    date TEXT,
                    date_start TEXT,
                    date_end TEXT,
                    description TEXT,
                    event_type TEXT DEFAULT 'Academic',
                    date_added TEXT NOT NULL,
                    last_modified TEXT,
                    created_by TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    audience TEXT,
                    assignment_id INTEGER,
                    trip_id INTEGER,
                    organizer TEXT,
                    participants TEXT,
                    status TEXT,
                    country_code TEXT,
                    region TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    CONSTRAINT valid_event_dates CHECK (
                        date_start IS NULL OR date_end IS NULL OR date_start <= date_end
                    )
                )'''
            ]

            for table_sql in tables:
                self.db_manager.execute_update(table_sql)

        except Exception as e:
            logger.error(f"Failed to create core tables: {e}")
            raise

    def _create_enhanced_tables(self):
        """Create enhanced feature tables with better error handling"""
        try:
            enhanced_tables = [
                '''CREATE TABLE IF NOT EXISTS event_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color_code TEXT,
                    date_added TEXT NOT NULL
                )''',

                '''CREATE TABLE IF NOT EXISTS event_tag_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    tag_id INTEGER NOT NULL,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES event_tags (id) ON DELETE CASCADE,
                    UNIQUE(event_id, tag_id)
                )''',

                '''CREATE TABLE IF NOT EXISTS courses (
                    id TEXT PRIMARY KEY,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    credits INTEGER DEFAULT 3,
                    department TEXT,
                    instructor_id TEXT,
                    academic_year_id TEXT,
                    semester_id TEXT,
                    status TEXT DEFAULT 'active',
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (academic_year_id) REFERENCES academic_years (id),
                    FOREIGN KEY (semester_id) REFERENCES semesters (id)
                )''',

                '''CREATE TABLE IF NOT EXISTS course_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    event_sub_type TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
                    UNIQUE(event_id, course_id)
                )''',

                '''CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    capacity INTEGER,
                    location TEXT,
                    equipment TEXT,
                    status TEXT DEFAULT 'available',
                    date_added TEXT NOT NULL
                )''',

                '''CREATE TABLE IF NOT EXISTS resource_bookings (
                    id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    event_id TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    status TEXT DEFAULT 'confirmed',
                    notes TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE,
                    FOREIGN KEY (event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE
                )''',

                '''CREATE TABLE IF NOT EXISTS notification_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT TRUE,
                    advance_time INTEGER DEFAULT 60,
                    method TEXT DEFAULT 'email',
                    date_added TEXT NOT NULL,
                    UNIQUE(user_id, notification_type)
                )''',

                '''CREATE TABLE IF NOT EXISTS notification_queue (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_id TEXT,
                    notification_type TEXT NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    message TEXT,
                    date_added TEXT NOT NULL,
                    sent_at TEXT,
                    FOREIGN KEY (event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE
                )''',

                '''CREATE TABLE IF NOT EXISTS search_presets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    filters TEXT NOT NULL,
                    date_added TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                )''',

                # holiday_calendars folded into academic_calendar_events
                # (event_type='holiday_calendar').

                '''CREATE TABLE IF NOT EXISTS recurring_events (
                    id TEXT PRIMARY KEY,
                    base_event_id TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    interval_count INTEGER DEFAULT 1,
                    days_of_week TEXT,
                    day_of_month INTEGER,
                    month_of_year INTEGER,
                    end_date TEXT,
                    occurrence_count INTEGER,
                    timezone TEXT DEFAULT 'UTC',
                    exceptions TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (base_event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE
                )''',

                '''CREATE TABLE IF NOT EXISTS backup_history (
                    id TEXT PRIMARY KEY,
                    backup_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    backup_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT
                )''',

                '''CREATE TABLE IF NOT EXISTS unified_event_registrations (
                    registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_type TEXT DEFAULT 'student',
                    registration_date TEXT,
                    attendance_status TEXT DEFAULT 'present',
                    checked_in_at TEXT,
                    check_out_time TEXT,
                    payment_status TEXT,
                    payment_amount REAL DEFAULT 0.0,
                    payment_method TEXT,
                    is_waitlisted BOOLEAN DEFAULT 0,
                    num_guests INTEGER DEFAULT 0,
                    feedback_rating REAL,
                    feedback_comment TEXT,
                    qr_code TEXT,
                    cpd_credits REAL DEFAULT 0.0,
                    FOREIGN KEY (event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE
                )''',

                # trip_calendar_events folded into academic_calendar_events
                # (trip_id column links a calendar event to its trip).

                '''CREATE TABLE IF NOT EXISTS event_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color_code TEXT,
                    description TEXT,
                    date_added TEXT NOT NULL
                )''',

            ]

            for table_sql in enhanced_tables:
                try:
                    self.db_manager.execute_update(table_sql)
                    logger.debug("Created enhanced table successfully")
                except Exception as e:
                    logger.warning(f"Enhanced table creation warning: {e}")

        except Exception as e:
            logger.warning(f"Some enhanced tables failed to create: {e}")

    def _create_indexes(self):
        """Create database indexes for performance"""
        try:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_events_date ON academic_calendar_events(date)",
                "CREATE INDEX IF NOT EXISTS idx_events_date_start ON academic_calendar_events(date_start)",
                "CREATE INDEX IF NOT EXISTS idx_events_type ON academic_calendar_events(event_type)",
                "CREATE INDEX IF NOT EXISTS idx_events_created_by ON academic_calendar_events(created_by)",
                "CREATE INDEX IF NOT EXISTS idx_semesters_academic_year ON semesters(academic_year_id)"
            ]

            for index_sql in indexes:
                try:
                    self.db_manager.execute_update(index_sql)
                except Exception as e:
                    logger.debug(f"Index creation note: {e}")

        except Exception as e:
            logger.warning(f"Index creation had issues: {e}")

    def _create_default_data(self):
        """Create default data if database is empty"""
        try:
            # Check if data already exists
            rows = self.db_manager.execute_query("SELECT COUNT(*) as count FROM academic_years")
            if rows and rows[0][0] > 0:
                return

            current_year = datetime.now().year
            academic_year_id = f"{current_year}-{current_year+1}"
            current_time = datetime.now().isoformat()

            # Create default academic year
            self.db_manager.execute_update(
                "INSERT OR IGNORE INTO academic_years (id, start_date, end_date, date_added) VALUES (?, ?, ?, ?)",
                (academic_year_id, f"{current_year}-09-01", f"{current_year+1}-05-31", current_time)
            )

            # Create default semesters
            semester_data = [
                (academic_year_id, "Fall", f"{current_year}-09-01", f"{current_year}-12-20", current_time),
                (academic_year_id, "Spring", f"{current_year+1}-01-15", f"{current_year+1}-05-31", current_time)
            ]

            for semester in semester_data:
                try:
                    self.db_manager.execute_update(
                        "INSERT OR IGNORE INTO semesters (academic_year_id, name, start_date, end_date, date_added) VALUES (?, ?, ?, ?, ?)",
                        semester
                    )
                except Exception as e:
                    logger.debug(f"Semester creation note: {e}")

            # Create default categories
            default_categories = [
                ("Academic", "#1E3A8A", "Academic events like lectures, exams"),
                ("Trip", "#15803D", "Educational trips and excursions"),
                ("Holiday", "#7C3AED", "Holidays and breaks"),
                ("Deadline", "#EA580C", "Important deadlines")
            ]

            for name, color, description in default_categories:
                try:
                    self.db_manager.execute_update(
                        "INSERT OR IGNORE INTO event_categories (name, color_code, description, date_added) VALUES (?, ?, ?, ?)",
                        (name, color, description, current_time)
                    )
                except Exception as e:
                    logger.debug(f"Category creation note: {e}")

        except Exception as e:
            logger.warning(f"Default data creation had issues: {e}")
