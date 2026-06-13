import os
import csv
import json
import uuid
import shutil
import platform
import subprocess
import logging
import calendar as cal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.core import paths
from education_system.university_system.infrastructure.database.db import get_connection

from education_system.university_system.modules.domain.academics.services.academic_calendar.exceptions import (
    CalendarError, ValidationError, DatabaseError,
    PermissionError, ExportError
)
from education_system.university_system.modules.domain.academics.services.academic_calendar.config import CalendarConfig, ValidationUtils
from education_system.university_system.modules.domain.academics.services.academic_calendar.database import DatabaseManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.auth import AuthenticationManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.audit import AuditManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.recurring_events import RecurringEventManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.categories import EventCategoryManager, CourseManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.resources import ResourceManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.notifications import NotificationManager, SMSNotificationManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.search import AdvancedSearchManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.holidays import HolidayManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.visualization import DataVisualizationManager, EnhancedCalendarVisualizationManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.dependencies import EventDependencyManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.reporting import AdvancedReportingManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.deadlines import AcademicDeadlineManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.batch import BatchOperationsManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.timezone import EnhancedTimeZoneManager

logger = configure_logging(name=__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

try:
    from ics import Calendar as ICSCalendar, Event as ICSEvent
    ICS_AVAILABLE = True
except Exception:
    ICS_AVAILABLE = False

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from flask import Flask
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# Main Academic Calendar Manager
class AcademicCalendarManager:
    """Enhanced Academic Calendar Manager with all features"""

    def __init__(self, config: CalendarConfig = None, auth_manager: AuthenticationManager = None):
        self.config = config or CalendarConfig()
        self.db_manager = DatabaseManager(self.config.db_file)

        # Use the provided auth_manager (which should be the main UserAuth system)
        if auth_manager:
            self.auth_manager = auth_manager
        else:
            # Create a wrapper that uses the main auth system
            self.auth_manager = AuthenticationManager(self.db_manager)
            try:
                self.auth_manager._load_permissions()
            except Exception as e:
                logger.warning(f"Failed to load permissions in fallback auth manager: {e}")
                self.auth_manager.current_user = None
                self.auth_manager.permissions_cache = {}

        self.audit_manager = AuditManager(self.db_manager)

        # Initialize feature managers with error handling
        try:
            self.recurring_events = RecurringEventManager(self.db_manager, self.auth_manager)
            self.categories = EventCategoryManager(self.db_manager, self.auth_manager)
            self.courses = CourseManager(self.db_manager, self.auth_manager)
            self.resources = ResourceManager(self.db_manager, self.auth_manager)
            self.notifications = NotificationManager(self.db_manager, self.auth_manager)
            self.search = AdvancedSearchManager(self.db_manager, self.auth_manager)
            self.holidays = HolidayManager(self.db_manager, self.auth_manager)
            self.visualizations = DataVisualizationManager(self.db_manager, self.auth_manager)
            self.event_dependencies = EventDependencyManager(self.db_manager, self.auth_manager)
            self.advanced_reporting = AdvancedReportingManager(self.db_manager, self.auth_manager)
            self.sms_notifications = SMSNotificationManager(self.db_manager, self.auth_manager)
            self.mobile_api = None
            if FLASK_AVAILABLE:
                try:
                    from education_system.university_system.modules.domain.academics.services.academic_calendar.mobile_api import MobileAPIManager
                    self.mobile_api = MobileAPIManager(self)
                except Exception:
                    self.mobile_api = None
            self.enhanced_visualizations = EnhancedCalendarVisualizationManager(self.db_manager, self.auth_manager)
            self.academic_deadlines = AcademicDeadlineManager(self.db_manager, self.auth_manager)
            self.batch_operations = BatchOperationsManager(self.db_manager, self.auth_manager)
            self.timezone_manager = EnhancedTimeZoneManager(self.db_manager, self.auth_manager)
        except Exception as e:
            logger.warning(f"Some feature managers failed to initialize: {e}")

        # Initialize database with proper error handling
        try:
            self._initialize_database()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            # Try to continue with existing schema by creating minimal required tables
            try:
                self._create_minimal_tables()
                logger.info("Created minimal tables as fallback")
            except Exception as verify_error:
                logger.error(f"Minimal table creation failed: {verify_error}")
                # Don't raise here - allow the system to continue with limited functionality
                logger.warning("Calendar system running with limited functionality")

        try:
            self._create_backup_directory()
        except Exception as e:
            logger.warning(f"Could not create backup directory: {e}")

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
                    created_by TEXT
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

                '''CREATE TABLE IF NOT EXISTS trip_calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT DEFAULT 'trip_event',
                    created_at TEXT NOT NULL,
                    UNIQUE (trip_id, event_id)
                )'''
            ]

            for table_sql in minimal_tables:
                try:
                    self.db_manager.execute_update(table_sql)
                    logger.debug(f"Created table successfully")
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
                        created_by TEXT
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

            from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608
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
                    CONSTRAINT valid_event_dates CHECK (
                        (date IS NOT NULL AND date_start IS NULL AND date_end IS NULL) OR
                        (date IS NULL AND date_start IS NOT NULL AND date_end IS NOT NULL AND date_start <= date_end)
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

                '''CREATE TABLE IF NOT EXISTS holiday_calendars (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    country_code TEXT NOT NULL,
                    region TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    date_added TEXT NOT NULL
                )''',

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

                '''CREATE TABLE IF NOT EXISTS trip_calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT DEFAULT 'trip_event',
                    created_at TEXT NOT NULL,
                    UNIQUE (trip_id, event_id)
                )''',

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
                    logger.debug(f"Created enhanced table successfully")
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

    def get_trips_for_calendar_integration(self):
        """Get trips that can be integrated with calendar"""
        try:
            # sqlite3 is imported globally from education_system.university_system.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()

            # Get trips that don't have calendar events yet
            cursor.execute('''
                SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
                FROM trips t
                LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
                WHERE tce.trip_id IS NULL AND t.status IN ('planning', 'open', 'confirmed')
                ORDER BY t.start_date
            ''')

            trips = cursor.fetchall()
            conn.close()

            return [
                {
                    'id': trip[0],
                    'name': trip[1],
                    'destination': trip[2],
                    'start_date': trip[3],
                    'end_date': trip[4],
                    'status': trip[5]
                }
                for trip in trips
            ]

        except Exception as e:
            logger.error(f"Error getting trips for calendar integration: {e}")
            return []

    def get_calendar_events_for_trip(self, trip_id):
        """Get calendar events linked to a specific trip"""
        try:
            # sqlite3 is imported globally from education_system.university_system.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT e.id, e.name, e.date, e.date_start, e.date_end, e.description, e.event_type
                FROM trip_calendar_events tce
                JOIN academic_calendar_events e ON tce.event_id = e.id
                WHERE tce.trip_id = ?
                ORDER BY COALESCE(e.date, e.date_start)
            ''', (trip_id,))

            events = cursor.fetchall()
            conn.close()

            return [
                {
                    'id': event[0],
                    'name': event[1],
                    'date': event[2],
                    'date_start': event[3],
                    'date_end': event[4],
                    'description': event[5],
                    'event_type': event[6]
                }
                for event in events
            ]

        except Exception as e:
            logger.error(f"Error getting calendar events for trip: {e}")
            return []

    def remove_trip_calendar_link(self, trip_id, event_id):
        """Remove the link between a trip and calendar event"""
        try:
            # sqlite3 is imported globally from education_system.university_system.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM trip_calendar_events
                WHERE trip_id = ? AND event_id = ?
            ''', (trip_id, event_id))

            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                logger.info(f"Removed link between trip {trip_id} and event {event_id}")
                return {'success': True, 'message': 'Link removed successfully'}
            else:
                return {'success': False, 'message': 'Link not found'}

        except Exception as e:
            logger.error(f"Error removing trip-calendar link: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    def get_current_user_permissions(self):
        """Get current user's permissions for menu display"""
        try:
            if not self.auth_manager or not self.auth_manager.current_user:
                return set()

            # Get permissions from the main auth system
            from education_system.university_system.infrastructure.auth import get_global_auth
            global_auth = get_global_auth()
            if global_auth and getattr(global_auth, "current_user", None):
                user_permissions = global_auth.current_user.get('permissions', [])
                return set(user_permissions)

            return set()

        except Exception as e:
            logger.warning(f"Could not get user permissions: {e}")
            return set()

    def verify_calendar_database_integrity(self):
        """Verify and repair calendar database integrity"""
        try:
            logger.info("Verifying calendar database integrity...")

            # Check for required tables
            required_tables = [
                'academic_years', 'semesters', 'academic_calendar_events', 'event_categories'
            ]

            from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608
            missing_tables = []
            for table in required_tables:
                try:
                    safe_table = validate_identifier(table, "table")
                    self.db_manager.execute_query("SELECT COUNT(*) FROM [" + safe_table + "] LIMIT 1")
                except Exception:
                    missing_tables.append(table)

            if missing_tables:
                logger.warning(f"Missing tables detected: {missing_tables}")
                self._create_minimal_tables()
                logger.info("Created missing tables")

            # Check for data consistency
            self._check_data_consistency()

            logger.info("Database integrity verification completed")
            return True

        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False

    def _check_data_consistency(self):
        """Check for data consistency issues"""
        try:
            # Check for orphaned events (events without valid academic year context)
            orphaned_events = self.db_manager.execute_query('''
                SELECT COUNT(*) as count FROM academic_calendar_events e
                WHERE e.date_start IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM semesters s
                    WHERE e.date_start BETWEEN s.start_date AND s.end_date
                )
            ''')

            if orphaned_events and orphaned_events[0]['count'] > 0:
                logger.warning(f"Found {orphaned_events[0]['count']} orphaned events")

            # Check for invalid date ranges
            invalid_ranges = self.db_manager.execute_query('''
                SELECT COUNT(*) as count FROM academic_calendar_events
                WHERE date_start IS NOT NULL AND date_end IS NOT NULL
                AND date_start > date_end
            ''')

            if invalid_ranges and invalid_ranges[0]['count'] > 0:
                logger.warning(f"Found {invalid_ranges[0]['count']} events with invalid date ranges")

        except Exception as e:
            logger.warning(f"Data consistency check had issues: {e}")

    def get_system_stats(self):
        """Get system statistics for dashboard"""
        try:
            stats = {}

            # Count events by type
            event_counts = self.db_manager.execute_query('''
                SELECT event_type, COUNT(*) as count
                FROM academic_calendar_events
                GROUP BY event_type
            ''')
            stats['events_by_type'] = {row['event_type']: row['count'] for row in event_counts}

            # Count total academic years
            year_count = self.db_manager.execute_query('SELECT COUNT(*) as count FROM academic_years')
            stats['total_academic_years'] = year_count[0]['count'] if year_count else 0

            # Count total semesters
            semester_count = self.db_manager.execute_query('SELECT COUNT(*) as count FROM semesters')
            stats['total_semesters'] = semester_count[0]['count'] if semester_count else 0

            # Get current academic period
            current_year = self.get_current_academic_year()
            current_semester = self.get_current_semester()

            stats['current_academic_year'] = current_year['id'] if current_year else 'None'
            stats['current_semester'] = current_semester['name'] if current_semester else 'None'

            # Count upcoming events (next 30 days)
            future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            current_date = datetime.now().strftime("%Y-%m-%d")

            upcoming_events = self.db_manager.execute_query('''
                SELECT COUNT(*) as count FROM academic_calendar_events
                WHERE COALESCE(date, date_start) BETWEEN ? AND ?
            ''', (current_date, future_date))

            stats['upcoming_events'] = upcoming_events[0]['count'] if upcoming_events else 0

            return stats

        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}

    def cleanup_old_data(self, days_old=365):
        """Clean up old data to maintain database performance"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions for data cleanup")

        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime("%Y-%m-%d")

            # Clean up old events
            old_events = self.db_manager.execute_update('''
                DELETE FROM academic_calendar_events
                WHERE COALESCE(date, date_end) < ?
                AND event_type NOT IN ('Holiday', 'Academic')
            ''', (cutoff_date,))

            # Clean up old notifications
            old_notifications = self.db_manager.execute_update('''
                DELETE FROM notification_queue
                WHERE scheduled_time < ? AND status IN ('sent', 'failed')
            ''', (cutoff_date,))

            # Clean up old audit logs (keep important ones)
            old_audit = self.db_manager.execute_update('''
                DELETE FROM audit_log
                WHERE timestamp < ? AND action NOT IN ('DELETE', 'CREATE')
            ''', (cutoff_date,))

            logger.info(f"Cleanup completed: {old_events} events, {old_notifications} notifications, {old_audit} audit logs")

            return {
                'success': True,
                'cleaned_events': old_events,
                'cleaned_notifications': old_notifications,
                'cleaned_audit_logs': old_audit
            }

        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
            return {'success': False, 'error': str(e)}

    def export_system_configuration(self):
        """Export system configuration for backup/migration"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to export configuration")

        try:
            config_data = {
                'academic_years': [],
                'semesters': [],
                'event_categories': [],
                'export_timestamp': datetime.now().isoformat(),
                'system_version': '1.0'
            }

            # Export academic years
            years = self.db_manager.execute_query('SELECT * FROM academic_years ORDER BY start_date')
            config_data['academic_years'] = [dict(row) for row in years]

            # Export semesters
            semesters = self.db_manager.execute_query('SELECT * FROM semesters ORDER BY academic_year_id, start_date')
            config_data['semesters'] = [dict(row) for row in semesters]

            # Export event categories
            categories = self.db_manager.execute_query('SELECT * FROM event_categories ORDER BY name')
            config_data['event_categories'] = [dict(row) for row in categories]

            return config_data

        except Exception as e:
            logger.error(f"Configuration export failed: {e}")
            raise CalendarError(f"Configuration export failed: {e}")

    def import_system_configuration(self, config_data):
        """Import system configuration from backup"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to import configuration")

        try:
            imported_counts = {'academic_years': 0, 'semesters': 0, 'event_categories': 0}

            with self.db_manager.transaction():
                # Import academic years
                for year_data in config_data.get('academic_years', []):
                    try:
                        self.db_manager.execute_update('''
                            INSERT OR IGNORE INTO academic_years (id, start_date, end_date, date_added)
                            VALUES (?, ?, ?, ?)
                        ''', (year_data['id'], year_data['start_date'], year_data['end_date'], year_data['date_added']))
                        imported_counts['academic_years'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to import academic year {year_data.get('id')}: {e}")

                # Import semesters
                for semester_data in config_data.get('semesters', []):
                    try:
                        self.db_manager.execute_update('''
                            INSERT OR IGNORE INTO semesters (academic_year_id, name, start_date, end_date, date_added)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (semester_data['academic_year_id'], semester_data['name'],
                             semester_data['start_date'], semester_data['end_date'], semester_data['date_added']))
                        imported_counts['semesters'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to import semester {semester_data.get('name')}: {e}")

                # Import event categories
                for category_data in config_data.get('event_categories', []):
                    try:
                        self.db_manager.execute_update('''
                            INSERT OR IGNORE INTO event_categories (name, color_code, description, date_added)
                            VALUES (?, ?, ?, ?)
                        ''', (category_data['name'], category_data.get('color_code'),
                             category_data.get('description'), category_data['date_added']))
                        imported_counts['event_categories'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to import category {category_data.get('name')}: {e}")

            logger.info(f"Configuration import completed: {imported_counts}")
            return {'success': True, 'imported': imported_counts}

        except Exception as e:
            logger.error(f"Configuration import failed: {e}")
            return {'success': False, 'error': str(e)}

    # Trip integration method
    def create_trip_event(self, trip_id, event_details=None):
        """Create a calendar event for a trip"""
        if not self.auth_manager or not self.auth_manager.current_user:
            return {'success': False, 'message': 'Authentication required'}

        if not self.auth_manager.check_permission('manage_schedules'):
            return {'success': False, 'message': 'Insufficient permissions'}

        try:
            # Get trip details from trip_management
            # sqlite3 is imported globally from education_system.university_system.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trips WHERE id = ?', (trip_id,))
            trip = cursor.fetchone()

            if not trip:
                conn.close()
                return {'success': False, 'message': 'Trip not found'}

            # Create event details
            trip_id_val, trip_name, description, destination, start_date, end_date = trip[:6]

            event_name = event_details.get('name', f"Trip: {trip_name}") if event_details else f"Trip: {trip_name}"
            event_description = event_details.get('description', f"Trip to {destination} - {description or 'No description'}") if event_details else f"Trip to {destination}"

            # Create the calendar event
            result = self.add_event(
                name=event_name,
                date_start=start_date,
                date_end=end_date,
                description=event_description,
                event_type='Trip'
            )

            if result['success']:
                # Link trip to event
                cursor.execute('''
                    INSERT OR IGNORE INTO trip_calendar_events (trip_id, event_id, created_at)
                    VALUES (?, ?, ?)
                ''', (trip_id, result['event_id'], datetime.now().isoformat()))
                conn.commit()

            conn.close()
            return result

        except Exception as e:
            logger.error(f"Error creating trip event: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    # Core event management methods
    def add_event(self, name: str, date: Optional[str] = None,
                  date_start: Optional[str] = None, date_end: Optional[str] = None,
                  description: Optional[str] = None, event_type: str = 'Academic') -> Dict[str, Any]:
        """Add a new event to the calendar"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to add events")

        # Validate inputs
        if not name or not name.strip():
            raise ValidationError("Event name is required")

        if not date and not (date_start and date_end):
            raise ValidationError("Either date or date_start and date_end are required")

        if date and not ValidationUtils.validate_date(date):
            raise ValidationError("Invalid date format. Use YYYY-MM-DD")

        if date_start and not ValidationUtils.validate_date(date_start):
            raise ValidationError("Invalid start date format. Use YYYY-MM-DD")

        if date_end and not ValidationUtils.validate_date(date_end):
            raise ValidationError("Invalid end date format. Use YYYY-MM-DD")

        if date_start and date_end and date_start >= date_end:
            raise ValidationError("End date must be after start date")

        event_id = str(uuid.uuid4())
        current_time = datetime.now().isoformat()
        user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None

        # Sanitize inputs
        name = ValidationUtils.sanitize_string(name, 255)
        description = ValidationUtils.sanitize_string(description or "", 1000)
        event_type = ValidationUtils.sanitize_string(event_type, 50)

        try:
            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO academic_calendar_events (id, name, date, date_start, date_end, description,
                       event_type, date_added, last_modified, created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, name, date, date_start, date_end,
                     description, event_type, current_time, current_time, user_id)
                )

                # Log the action
                self.audit_manager.log_change(
                    table_name='events',
                    record_id=event_id,
                    action='CREATE',
                    new_values={'name': name, 'event_type': event_type},
                    user_id=user_id
                )

            logger.info(f"Event '{name}' created with ID {event_id}")

            # Calendar is the canonical writer for academic periods —
            # publish so every scheduler refreshes its term-aware filters.
            # Holidays and exam windows in particular drive validation
            # gates in Module Scheduling, Exam, and Grade.
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    publish, EVENT_CALENDAR_CHANGED,
                )
                publish(
                    EVENT_CALENDAR_CHANGED,
                    event_id=event_id, name=name, event_type=event_type,
                    date=date, date_start=date_start, date_end=date_end,
                    action="created",
                )
            except Exception:
                pass

            return {
                'success': True,
                'message': f"Event '{name}' added successfully",
                'event_id': event_id
            }

        except Exception as e:
            logger.error(f"Failed to add event: {e}")
            raise DatabaseError(f"Failed to add event: {e}")

    def update_event(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to update events")

        if not event_id or not str(event_id).strip():
            raise ValidationError("Invalid event ID format")

        # Get existing event
        rows = self.db_manager.execute_query("SELECT * FROM academic_calendar_events WHERE id = ?", (event_id,))
        if not rows:
            raise ValidationError(f"Event with ID {event_id} not found")

        existing_event = dict(rows[0])

        # Validate and sanitize updates
        allowed_fields = {'name', 'date', 'date_start', 'date_end', 'description', 'event_type'}
        invalid_fields = set(updates.keys()) - allowed_fields
        if invalid_fields:
            raise ValidationError(f"Invalid fields: {', '.join(invalid_fields)}")

        sanitized_updates = {}
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                if field in ['date', 'date_start', 'date_end']:
                    if not ValidationUtils.validate_date(str(value)):
                        raise ValidationError(f"Invalid {field} format. Use YYYY-MM-DD")
                    sanitized_updates[field] = str(value)
                elif field in ['name', 'event_type']:
                    sanitized_updates[field] = ValidationUtils.sanitize_string(str(value), 255)
                elif field == 'description':
                    sanitized_updates[field] = ValidationUtils.sanitize_string(str(value), 1000)

        if not sanitized_updates:
            return {'success': True, 'message': 'No changes to apply'}

        try:
            with self.db_manager.transaction():
                # Build update query
                set_clauses = []
                params = []

                from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608
                for field, value in sanitized_updates.items():
                    safe_field = validate_identifier(field, "column")
                    set_clauses.append("[" + safe_field + "] = ?")
                    params.append(value)

                set_clauses.append("[last_modified] = ?")
                params.append(datetime.now().isoformat())
                params.append(event_id)

                query = "UPDATE [academic_calendar_events] SET " + ", ".join(set_clauses) + " WHERE id = ?"
                self.db_manager.execute_update(query, tuple(params))

                # Log the action
                user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None
                self.audit_manager.log_change(
                    table_name='events',
                    record_id=event_id,
                    action='UPDATE',
                    old_values={k: existing_event.get(k) for k in sanitized_updates.keys()},
                    new_values=sanitized_updates,
                    user_id=user_id
                )

            logger.info(f"Event {event_id} updated successfully")

            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    publish, EVENT_CALENDAR_CHANGED,
                )
                publish(EVENT_CALENDAR_CHANGED,
                        event_id=event_id, action="updated")
            except Exception:
                pass

            return {'success': True, 'message': 'Event updated successfully'}

        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            raise DatabaseError(f"Failed to update event: {e}")

    def delete_event(self, event_id: str) -> Dict[str, Any]:
        """Delete an event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to delete events")

        if not event_id or not str(event_id).strip():
            raise ValidationError("Invalid event ID format")

        # Get existing event for audit log
        rows = self.db_manager.execute_query("SELECT * FROM academic_calendar_events WHERE id = ?", (event_id,))
        if not rows:
            raise ValidationError(f"Event with ID {event_id} not found")

        event_data = dict(rows[0])

        try:
            with self.db_manager.transaction():
                # Delete the event (cascade will handle related records)
                rows_affected = self.db_manager.execute_update("DELETE FROM academic_calendar_events WHERE id = ?", (event_id,))

                if rows_affected > 0:
                    # Log the action
                    user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None
                    self.audit_manager.log_change(
                        table_name='events',
                        record_id=event_id,
                        action='DELETE',
                        old_values={'name': event_data.get('name'), 'event_type': event_data.get('event_type')},
                        user_id=user_id
                    )

            logger.info(f"Event {event_id} deleted successfully")

            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    publish, EVENT_CALENDAR_CHANGED,
                )
                publish(EVENT_CALENDAR_CHANGED,
                        event_id=event_id, action="deleted")
            except Exception:
                pass

            return {'success': True, 'message': 'Event deleted successfully'}

        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            raise DatabaseError(f"Failed to delete event: {e}")

    def get_events_by_date_range(self, start_date: str, end_date: str,
                                event_type: Optional[str] = None) -> List[Dict]:
        """Get all events within a date range"""
        if not ValidationUtils.validate_date(start_date):
            raise ValidationError("Invalid start date format")

        if not ValidationUtils.validate_date(end_date):
            raise ValidationError("Invalid end date format")

        if start_date > end_date:
            raise ValidationError("End date must be after start date")

        try:
            query = """
                SELECT * FROM academic_calendar_events
                WHERE ((date BETWEEN ? AND ?)
                OR (date_start <= ? AND date_end >= ?)
                OR (date_start BETWEEN ? AND ?)
                OR (date_end BETWEEN ? AND ?))
            """
            params = [start_date, end_date, end_date, start_date,
                     start_date, end_date, start_date, end_date]

            if event_type:
                event_type = ValidationUtils.sanitize_string(event_type, 50)
                query += " AND event_type = ?"
                params.append(event_type)

            query += " ORDER BY COALESCE(date, date_start) LIMIT ?"
            params.append(self.config.max_search_results)

            rows = self.db_manager.execute_query(query, tuple(params))
            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get events by date range: {e}")
            raise DatabaseError(f"Failed to retrieve events: {e}")

    def view_calendar(self, academic_year: Optional[str] = None, semester: Optional[str] = None) -> Tuple[bool, List[Dict]]:
        """Retrieve the calendar information for an academic year and/or semester"""
        try:
            query = """
                SELECT s.name AS semester_name, s.start_date AS semester_start, s.end_date AS semester_end,
                       e.name AS event_name, e.date, e.date_start, e.date_end, e.description, e.event_type
                FROM semesters s
                LEFT JOIN academic_calendar_events e ON (
                    (e.date BETWEEN s.start_date AND s.end_date) OR
                    (e.date_start BETWEEN s.start_date AND s.end_date) OR
                    (e.date_end BETWEEN s.start_date AND s.end_date)
                )
            """
            conditions = []
            params = []

            if academic_year:
                academic_year = ValidationUtils.sanitize_string(academic_year, 20)
                conditions.append("s.academic_year_id = ?")
                params.append(academic_year)

            if semester:
                semester = ValidationUtils.sanitize_string(semester, 50)
                conditions.append("s.name = ?")
                params.append(semester)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY s.start_date, COALESCE(e.date, e.date_start)"

            rows = self.db_manager.execute_query(query, tuple(params))

            if not rows:
                return False, "No calendar data found for the given selection."

            result = [dict(row) for row in rows]
            return True, result

        except Exception as e:
            logger.error(f"Failed to view calendar: {e}")
            return False, f"Database error: {str(e)}"

    # Calendar sync with security improvements
    def calendar_sync(self, ical_url: str, local_calendar: Optional[str] = None) -> Dict[str, Any]:
        """Sync external iCal feed with security improvements"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to sync calendars")

        if not REQUESTS_AVAILABLE:
            raise CalendarError("Requests library not available. Install with: pip install requests")

        if not ICS_AVAILABLE:
            raise CalendarError("ICS library not available. Install with: pip install ics")

        try:
            # Validate URL
            if not ValidationUtils.validate_url(ical_url):
                raise ValidationError("Invalid URL format")

            # Fetch external calendar with timeout
            response = requests.get(ical_url, timeout=30, headers={'User-Agent': 'Academic Calendar Manager'})
            response.raise_for_status()

            # Check response size
            if len(response.content) > self.config.max_file_size:
                raise ValidationError("Calendar file too large")

            # Parse calendar
            try:
                ext_cal = ICSCalendar(response.text)
            except Exception as e:
                raise ValidationError(f"Invalid iCal format: {e}")

            # Get existing events for conflict detection
            existing_events = self._get_existing_events_index()

            synced = 0
            conflicts = []
            skipped = 0
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                for event in ext_cal.events:
                    try:
                        # Skip holidays/breaks
                        event_name = str(event.name) if hasattr(event, 'name') and event.name else ""
                        if any(keyword in event_name.lower() for keyword in ['holiday', 'break']):
                            skipped += 1
                            continue

                        # Extract event details safely
                        if not hasattr(event, 'begin') or not event.begin:
                            skipped += 1
                            continue

                        start_dt = event.begin.datetime if hasattr(event.begin, 'datetime') else None
                        end_dt = event.end.datetime if hasattr(event, 'end') and hasattr(event.end, 'datetime') else None

                        if not start_dt:
                            skipped += 1
                            continue

                        # Convert to local timezone if needed
                        if hasattr(start_dt, 'tzinfo') and start_dt.tzinfo:
                            start_dt = start_dt.replace(tzinfo=None)
                        if end_dt and hasattr(end_dt, 'tzinfo') and end_dt.tzinfo:
                            end_dt = end_dt.replace(tzinfo=None)

                        # Check for conflicts
                        conflict_events = self._check_event_conflicts(start_dt, end_dt, existing_events)
                        if conflict_events:
                            conflicts.extend([{
                                'external': event_name,
                                'conflicts_with': conflict['name'],
                                'when': start_dt.strftime("%Y-%m-%d")
                            } for conflict in conflict_events])

                        # Generate safe event ID
                        event_uid = getattr(event, 'uid', None)
                        if event_uid:
                            event_id = ValidationUtils.sanitize_string(str(event_uid), 36)
                        else:
                            event_id = str(uuid.uuid4())

                        # Check if event already exists
                        if not self._event_exists(event_id):
                            description = ValidationUtils.sanitize_string(
                                str(event.description) if hasattr(event, 'description') and event.description else "",
                                1000
                            )

                            self.db_manager.execute_update(
                                """INSERT INTO academic_calendar_events (id, name, date_start, date_end, description,
                                   event_type, date_added, last_modified, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (event_id,
                                 ValidationUtils.sanitize_string(event_name, 255),
                                 start_dt.strftime("%Y-%m-%d"),
                                 end_dt.strftime("%Y-%m-%d") if end_dt else start_dt.strftime("%Y-%m-%d"),
                                 description,
                                 'Academic',
                                 current_time, current_time, user_id)
                            )
                            synced += 1

                    except Exception as e:
                        logger.warning(f"Failed to process event: {e}")
                        skipped += 1
                        continue

            # Get upcoming deadlines
            upcoming_deadlines = self._get_upcoming_deadlines()

            result = {
                'success': True,
                'synced': synced,
                'skipped_holidays': skipped,
                'conflicts': conflicts,
                'upcoming_deadlines': upcoming_deadlines
            }

            logger.info(f"Calendar sync completed: {synced} synced, {skipped} skipped")
            return result

        except Exception as e:
            if REQUESTS_AVAILABLE and isinstance(e, requests.RequestException):
                logger.error(f"Failed to fetch remote calendar: {e}")
                raise CalendarError(f"Failed to fetch remote calendar: {e}")
            logger.error(f"Calendar sync failed: {e}")
            raise CalendarError(f"Calendar sync failed: {e}")

    def _get_existing_events_index(self) -> List[Dict]:
        """Get index of existing events for conflict detection"""
        query = "SELECT id, name, date, date_start, date_end, event_type FROM academic_calendar_events"
        rows = self.db_manager.execute_query(query)

        events = []
        for row in rows:
            try:
                start_str = row['date'] or row['date_start']
                end_str = row['date'] or row['date_end']

                if start_str:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_str, "%Y-%m-%d") if end_str else start_dt

                    events.append({
                        'id': row['id'],
                        'name': row['name'],
                        'start': start_dt,
                        'end': end_dt,
                        'type': row['event_type']
                    })
            except (ValueError, TypeError):
                continue

        return events

    def _check_event_conflicts(self, start_dt: datetime, end_dt: datetime,
                              existing_events: List[Dict]) -> List[Dict]:
        """Check for scheduling conflicts"""
        conflicts = []

        if not end_dt:
            end_dt = start_dt

        for event in existing_events:
            if event['type'].lower() in ('assignment', 'exam'):
                # Check for overlap
                if not (end_dt <= event['start'] or start_dt >= event['end']):
                    conflicts.append(event)

        return conflicts

    def _event_exists(self, event_id: str) -> bool:
        """Check if event already exists"""
        rows = self.db_manager.execute_query("SELECT 1 FROM academic_calendar_events WHERE id = ?", (event_id,))
        return len(rows) > 0

    def _get_upcoming_deadlines(self, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming assignment deadlines"""
        end_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        current_date = datetime.now().strftime("%Y-%m-%d")

        query = """
            SELECT name, COALESCE(date, date_start) as due_date
            FROM academic_calendar_events
            WHERE event_type = 'Assignment'
            AND COALESCE(date, date_start) BETWEEN ? AND ?
            ORDER BY COALESCE(date, date_start)
        """

        rows = self.db_manager.execute_query(query, (current_date, end_date))
        return [{'name': row['name'], 'due': row['due_date']} for row in rows]

    # Academic year and semester management
    # ------------------------------------------------------------------
    #  Calendar-event mirroring for academic years & semesters
    # ------------------------------------------------------------------

    def _upsert_event(self, event_id: str, name: str,
                      date_start: str, date_end: str,
                      description: str = "", event_type: str = "Academic"):
        """Insert or update one academic_calendar_events row keyed on
        the deterministic *event_id*. Used to mirror academic years and
        semester sub-periods onto the calendar so they show up alongside
        exams, holidays, and ad-hoc events."""
        now = datetime.now().isoformat()
        existing = self.db_manager.execute_query(
            "SELECT id FROM academic_calendar_events WHERE id = ?",
            (event_id,),
        )
        if existing:
            self.db_manager.execute_update(
                """UPDATE academic_calendar_events
                   SET name = ?, date_start = ?, date_end = ?,
                       description = ?, event_type = ?, last_modified = ?
                   WHERE id = ?""",
                (name, date_start, date_end, description, event_type, now,
                 event_id),
            )
        else:
            self.db_manager.execute_update(
                """INSERT INTO academic_calendar_events
                   (id, name, date_start, date_end, description,
                    event_type, date_added, last_modified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, name, date_start, date_end, description,
                 event_type, now, now),
            )

    def _sync_academic_year_to_calendar(self, year_id: str,
                                         start_date: str,
                                         end_date: str) -> None:
        """Push an academic year onto the calendar as one spanning event."""
        try:
            self._upsert_event(
                event_id=f"AY-{year_id}",
                name=f"Academic Year {year_id}",
                date_start=start_date,
                date_end=end_date,
                description=f"Academic year {year_id}",
                event_type="Academic Year",
            )
        except Exception as exc:
            logger.warning("Failed to sync academic year to calendar: %s", exc)

    def _sync_semester_to_calendar(self, semester_id: int, name: str,
                                    start_date: str, end_date: str,
                                    registration_start: Optional[str] = None,
                                    registration_end: Optional[str] = None,
                                    exams_start: Optional[str] = None,
                                    exams_end: Optional[str] = None) -> None:
        """Push a semester onto the calendar as up to three events:
        the semester period, the registration window, and the final
        exams window. Each gets a deterministic id so re-syncing
        replaces rather than duplicates."""
        try:
            self._upsert_event(
                event_id=f"SEM-{semester_id}-PERIOD",
                name=f"{name} Semester",
                date_start=start_date,
                date_end=end_date,
                description=f"{name} semester period",
                event_type="Semester",
            )
            if registration_start and registration_end:
                self._upsert_event(
                    event_id=f"SEM-{semester_id}-REG",
                    name=f"{name} Registration / Add-Drop",
                    date_start=registration_start,
                    date_end=registration_end,
                    description=(
                        f"Registration and add/drop window for {name} "
                        "semester."
                    ),
                    event_type="Registration",
                )
            if exams_start and exams_end:
                self._upsert_event(
                    event_id=f"SEM-{semester_id}-EXAMS",
                    name=f"{name} Final Exams",
                    date_start=exams_start,
                    date_end=exams_end,
                    description=f"Final exam period for {name} semester.",
                    event_type="Exam Period",
                )
        except Exception as exc:
            logger.warning("Failed to sync semester to calendar: %s", exc)

    def add_academic_year(self, year: str, start_date: str, end_date: str) -> Tuple[bool, str]:
        """Add a new academic year to the calendar"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to add academic years")

        try:
            year = ValidationUtils.sanitize_string(year, 20)
            if not isinstance(year, str) or len(year.split('-')) != 2:
                raise ValidationError("Year should be in format 'YYYY-YYYY' (e.g., '2023-2024')")

            if not ValidationUtils.validate_date(start_date) or not ValidationUtils.validate_date(end_date):
                raise ValidationError("Invalid date format. Use YYYY-MM-DD.")

            if start_date >= end_date:
                raise ValidationError("End date must be after start date")

            # Check if academic year already exists
            existing = self.db_manager.execute_query("SELECT id FROM academic_years WHERE id = ?", (year,))
            if existing:
                return False, f"Academic year {year} already exists"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO academic_years (id, start_date, end_date, date_added)
                       VALUES (?, ?, ?, ?)""",
                    (year, start_date, end_date, datetime.now().isoformat())
                )

                # Log the action
                user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None
                self.audit_manager.log_change(
                    table_name='academic_years',
                    record_id=year,
                    action='CREATE',
                    new_values={'year': year, 'start_date': start_date, 'end_date': end_date},
                    user_id=user_id
                )

                # Mirror onto the calendar so the academic year shows up
                # alongside exams, holidays and ad-hoc events.
                self._sync_academic_year_to_calendar(
                    year, start_date, end_date)

            logger.info(f"Academic year {year} added successfully")
            return True, f"Academic year {year} added successfully"

        except Exception as e:
            logger.error(f"Failed to add academic year: {e}")
            raise DatabaseError(f"Database error: {str(e)}")

    def add_semester(self, academic_year: str, semester_name: str, start_date: str, end_date: str) -> Tuple[bool, str]:
        """Add a semester to an academic year"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to add semesters")

        try:
            academic_year = ValidationUtils.sanitize_string(academic_year, 20)
            semester_name = ValidationUtils.sanitize_string(semester_name, 50)

            if not ValidationUtils.validate_date(start_date) or not ValidationUtils.validate_date(end_date):
                raise ValidationError("Invalid date format. Use YYYY-MM-DD.")

            if start_date >= end_date:
                raise ValidationError("End date must be after start date")

            # Check if academic year exists
            year_data = self.db_manager.execute_query(
                "SELECT id, start_date, end_date FROM academic_years WHERE id = ?", (academic_year,)
            )
            if not year_data:
                return False, f"Academic year {academic_year} not found"

            year_info = dict(year_data[0])
            if start_date < year_info['start_date'] or end_date > year_info['end_date']:
                return False, "Semester dates must fall within the academic year"

            # Check if semester already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM semesters WHERE academic_year_id = ? AND name = ?",
                (academic_year, semester_name)
            )
            if existing:
                return False, f"Semester {semester_name} already exists for academic year {academic_year}"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO semesters (academic_year_id, name, start_date, end_date, date_added)
                       VALUES (?, ?, ?, ?, ?)""",
                    (academic_year, semester_name, start_date, end_date, datetime.now().isoformat())
                )

                # Look up the new semester's id and mirror it onto the
                # calendar (period plus registration/exam sub-windows
                # if those dates have been set).
                new_row = self.db_manager.execute_query(
                    "SELECT id, registration_start, registration_end, "
                    "       final_exams_start, final_exams_end "
                    "FROM semesters WHERE academic_year_id = ? AND name = ?",
                    (academic_year, semester_name),
                )
                if new_row:
                    sem = dict(new_row[0])
                    self._sync_semester_to_calendar(
                        semester_id=sem["id"],
                        name=semester_name,
                        start_date=start_date,
                        end_date=end_date,
                        registration_start=sem.get("registration_start"),
                        registration_end=sem.get("registration_end"),
                        exams_start=sem.get("final_exams_start"),
                        exams_end=sem.get("final_exams_end"),
                    )

            logger.info(f"Semester {semester_name} added to academic year {academic_year}")
            return True, f"Semester {semester_name} added successfully to academic year {academic_year}"

        except Exception as e:
            logger.error(f"Failed to add semester: {e}")
            raise DatabaseError(f"Database error: {str(e)}")

    def get_current_academic_year(self) -> Optional[Dict]:
        """Get the current academic year"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        try:
            # First try to find current academic year
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE start_date <= ? AND end_date >= ?",
                (current_date, current_date)
            )
            if rows:
                return dict(rows[0])

            # If not found, look for upcoming academic year
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE start_date > ? ORDER BY start_date ASC LIMIT 1",
                (current_date,)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'upcoming'
                return result

            # If still not found, look for most recent past academic year
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE end_date < ? ORDER BY end_date DESC LIMIT 1",
                (current_date,)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'past'
                return result

            return None

        except Exception as e:
            logger.error(f"Failed to get current academic year: {e}")
            return None

    def get_current_semester(self) -> Optional[Dict]:
        """Get the current semester"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        try:
            current_year = self.get_current_academic_year()
            if not current_year:
                return None

            current_year_id = current_year['id']
            year_status = current_year.get('status')

            if year_status == 'upcoming':
                rows = self.db_manager.execute_query(
                    "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY start_date ASC LIMIT 1",
                    (current_year_id,)
                )
                if rows:
                    result = dict(rows[0])
                    result['status'] = 'upcoming'
                    return result
            elif year_status == 'past':
                rows = self.db_manager.execute_query(
                    "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY end_date DESC LIMIT 1",
                    (current_year_id,)
                )
                if rows:
                    result = dict(rows[0])
                    result['status'] = 'past'
                    return result

            # Look for current semester
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? AND start_date <= ? AND end_date >= ?",
                (current_year_id, current_date, current_date)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'current'
                return result

            # Look for upcoming semester
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? AND start_date > ? ORDER BY start_date ASC LIMIT 1",
                (current_year_id, current_date)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'upcoming'
                return result

            # Look for most recent past semester
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? AND end_date < ? ORDER BY end_date DESC LIMIT 1",
                (current_year_id, current_date)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'past'
                return result

            return None

        except Exception as e:
            logger.error(f"Failed to get current semester: {e}")
            return None

    def get_semesters_for_academic_year(self, academic_year_id: str) -> List[Dict]:
        """Get all semesters for a specific academic year"""
        try:
            academic_year_id = ValidationUtils.sanitize_string(academic_year_id, 20)
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY start_date",
                (academic_year_id,)
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get semesters: {e}")
            return []

    # Export functionality with security improvements
    def export_calendar(self, file_path: str, format_type: str,
                       academic_year: Optional[str] = None) -> Dict[str, Any]:
        """Export calendar with security validation"""
        if not self.auth_manager.check_permission('export_data'):
            raise PermissionError("Insufficient permissions to export data")

        # Validate file path
        safe_path = ValidationUtils.sanitize_filename(os.path.basename(file_path))
        if not safe_path:
            raise ValidationError("Invalid file name")

        # Validate format
        supported_formats = {'json', 'csv', 'xlsx', 'pdf', 'ics', 'txt'}
        format_type = format_type.lower()
        if format_type not in supported_formats:
            raise ValidationError(f"Unsupported format. Use: {', '.join(supported_formats)}")

        # Get export data
        try:
            export_data = self._get_export_data(academic_year)

            if not export_data:
                return {'success': False, 'message': 'No data to export'}

            # Limit export size
            if len(export_data) > self.config.max_export_records:
                raise ValidationError(f"Export too large. Maximum {self.config.max_export_records} records allowed")

            # Export based on format
            export_methods = {
                'json': self._export_json,
                'csv': self._export_csv,
                'xlsx': self._export_excel,
                'pdf': self._export_pdf,
                'ics': self._export_ical,
                'txt': self._export_txt
            }

            export_method = export_methods[format_type]
            success = export_method(export_data, safe_path)

            if success:
                logger.info(f"Calendar exported to {safe_path}")
                return {'success': True, 'message': f'Calendar exported to {safe_path}', 'file_path': safe_path}
            else:
                return {'success': False, 'message': 'Export failed'}

        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise ExportError(f"Export failed: {e}")

    def _get_export_data(self, academic_year: Optional[str] = None) -> List[Dict]:
        """Get formatted data for export"""
        try:
            query = """
                SELECT s.name AS semester_name, s.start_date AS semester_start,
                       s.end_date AS semester_end, e.name AS event_name,
                       COALESCE(e.date, e.date_start) as event_date,
                       e.date_end, e.event_type, e.description
                FROM semesters s
                LEFT JOIN academic_calendar_events e ON (
                    (e.date BETWEEN s.start_date AND s.end_date) OR
                    (e.date_start BETWEEN s.start_date AND s.end_date) OR
                    (e.date_end BETWEEN s.start_date AND s.end_date)
                )
            """
            params = []

            if academic_year:
                academic_year = ValidationUtils.sanitize_string(academic_year, 20)
                query += " WHERE s.academic_year_id = ?"
                params.append(academic_year)

            query += " ORDER BY s.start_date, event_date"

            rows = self.db_manager.execute_query(query, tuple(params))

            export_data = []
            for row in rows:
                if row['event_name']:  # Only include rows with events
                    event_date = row['event_date']
                    if row['date_end'] and row['date_end'] != row['event_date']:
                        event_date += f" to {row['date_end']}"

                    export_data.append({
                        'Academic Year': academic_year or 'All',
                        'Semester': row['semester_name'],
                        'Semester Start': row['semester_start'],
                        'Semester End': row['semester_end'],
                        'Event Name': row['event_name'],
                        'Event Date': event_date,
                        'Event Type': row['event_type'],
                        'Description': row['description'] or ''
                    })

            return export_data

        except Exception as e:
            logger.error(f"Failed to get export data: {e}")
            raise DatabaseError(f"Failed to get export data: {e}")

    def _export_json(self, data: List[Dict], file_path: str) -> bool:
        """Export to JSON format"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False

    def _export_csv(self, data: List[Dict], file_path: str) -> bool:
        """Export to CSV format"""
        try:
            if not data:
                return False

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            return True
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False

    def _export_excel(self, data: List[Dict], file_path: str) -> bool:
        """Export to Excel format"""
        if not PANDAS_AVAILABLE:
            logger.error("pandas not available for Excel export")
            return False

        try:
            df = pd.DataFrame(data)
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Academic Calendar', index=False)

                # Auto-adjust column widths
                worksheet = writer.sheets['Academic Calendar']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except (AttributeError, TypeError):
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

            return True
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            return False

    def _export_pdf(self, data: List[Dict], file_path: str) -> bool:
        """Export to PDF format"""
        if not REPORTLAB_AVAILABLE:
            logger.error("reportlab not available for PDF export")
            return False

        try:
            doc = SimpleDocTemplate(file_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()

            # Add title
            title = Paragraph("Academic Calendar", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))

            # Add generation info
            generation_info = Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles['Normal']
            )
            story.append(generation_info)
            story.append(Spacer(1, 12))

            # Group by semester
            semesters = {}
            for item in data:
                semester = item['Semester']
                if semester not in semesters:
                    semesters[semester] = {
                        'info': {'start': item['Semester Start'], 'end': item['Semester End']},
                        'events': []
                    }
                semesters[semester]['events'].append(item)

            # Create tables for each semester
            for semester_name, semester_data in semesters.items():
                # Semester header
                semester_title = Paragraph(f"{semester_name} Semester", styles['Heading2'])
                story.append(semester_title)

                period_info = Paragraph(
                    f"Period: {semester_data['info']['start']} to {semester_data['info']['end']}",
                    styles['Normal']
                )
                story.append(period_info)
                story.append(Spacer(1, 6))

                # Events table
                table_data = [['Date', 'Event', 'Type', 'Description']]
                for event in semester_data['events']:
                    description = event['Description'][:50] + ('...' if len(event['Description']) > 50 else '')
                    table_data.append([
                        event['Event Date'],
                        event['Event Name'],
                        event['Event Type'],
                        description
                    ])

                table = Table(table_data, colWidths=[100, 200, 80, 150])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))

                story.append(table)
                story.append(Spacer(1, 20))

            doc.build(story)
            return True
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return False

    def _export_txt(self, data: List[Dict], file_path: str) -> bool:
        """Export to plain text format"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("ACADEMIC CALENDAR\n")
                f.write("=" * 80 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n")

                current_semester = None
                for item in data:
                    if current_semester != item['Semester']:
                        current_semester = item['Semester']
                        f.write(f"\n{current_semester} SEMESTER\n")
                        f.write(f"Period: {item['Semester Start']} to {item['Semester End']}\n")
                        f.write("-" * 60 + "\n")

                    f.write(f"{item['Event Date']:<20} {item['Event Name']:<30} ({item['Event Type']})\n")
                    if item['Description']:
                        f.write(f"{'':20} {item['Description']}\n")

                f.write("\n" + "=" * 80 + "\n")

            return True
        except Exception as e:
            logger.error(f"TXT export failed: {e}")
            return False

    def _export_ical(self, data: List[Dict], file_path: str) -> bool:
        """Export to iCal format"""
        try:
            ical_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Academic Calendar Manager//EN",
                "CALSCALE:GREGORIAN"
            ]

            for item in data:
                if item['Event Name']:
                    event_id = str(uuid.uuid4())
                    event_lines = [
                        "BEGIN:VEVENT",
                        f"UID:{event_id}@academic-calendar",
                        f"SUMMARY:{item['Event Name']}",
                        f"DESCRIPTION:{item['Description']}",
                        f"CATEGORIES:{item['Event Type']}"
                    ]

                    # Handle date formatting
                    try:
                        if ' to ' in item['Event Date']:
                            start_date, end_date = item['Event Date'].split(' to ')
                            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        else:
                            start_dt = datetime.strptime(item['Event Date'], "%Y-%m-%d")
                            end_dt = start_dt + timedelta(days=1)

                        event_lines.extend([
                            f"DTSTART;VALUE=DATE:{start_dt.strftime('%Y%m%d')}",
                            f"DTEND;VALUE=DATE:{end_dt.strftime('%Y%m%d')}",
                            f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}"
                        ])
                    except ValueError:
                        continue

                    event_lines.append("END:VEVENT")
                    ical_lines.extend(event_lines)

            ical_lines.append("END:VCALENDAR")

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(ical_lines))

            return True
        except Exception as e:
            logger.error(f"iCal export failed: {e}")
            return False

    # Safe file operations
    def safe_open_file(self, file_path: str):
        """Safely open a file with security checks"""
        try:
            # Sanitize file path
            safe_path = ValidationUtils.sanitize_filename(os.path.basename(file_path))

            # Check file extension
            _, ext = os.path.splitext(safe_path)
            if ext.lower() not in self.config.allowed_file_types:
                raise ValidationError(f"File type {ext} not allowed")

            # Check if file exists
            if not os.path.exists(safe_path):
                raise ValidationError(f"File {safe_path} not found")

            # Open file with appropriate application
            if platform.system() == "Windows":
                os.startfile(safe_path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", safe_path])
            else:
                subprocess.call(["xdg-open", safe_path])

            logger.info(f"Opened file: {safe_path}")

        except Exception as e:
            logger.error(f"Failed to open file: {e}")
            raise CalendarError(f"Failed to open file: {e}")

    # Backup and recovery
    def create_backup(self, backup_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a backup of the database"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to create backups")

        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(self.config.backup_directory, f"calendar_backup_{timestamp}.db")

            # Ensure backup directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)

            # Create backup using SQLite's backup method
            self.db_manager.backup_database(backup_path)

            # Verify backup
            if os.path.exists(backup_path):
                file_size = os.path.getsize(backup_path)

                # Record backup in history
                with self.db_manager.transaction():
                    backup_id = str(uuid.uuid4())
                    self.db_manager.execute_update(
                        """INSERT INTO backup_history (id, backup_type, file_path, file_size,
                           backup_time, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (backup_id, "manual", backup_path, file_size,
                         datetime.now().isoformat(), "completed", "Manual backup")
                    )

                logger.info(f"Backup created: {backup_path} ({file_size} bytes)")
                return {
                    'success': True,
                    'message': f'Backup created successfully: {backup_path}',
                    'file_path': backup_path,
                    'file_size': file_size
                }
            else:
                return {'success': False, 'message': 'Backup creation failed'}

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise CalendarError(f"Backup creation failed: {e}")

    def restore_backup(self, backup_path: str) -> Dict[str, Any]:
        """Restore database from backup"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to restore backups")

        if not os.path.exists(backup_path):
            raise ValidationError(f"Backup file not found: {backup_path}")

        try:
            # Create backup of current database
            current_backup = f"{self.config.db_file}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(self.config.db_file, current_backup)

            # Close current connection
            self.db_manager.close()

            # Restore from backup
            shutil.copy2(backup_path, self.config.db_file)

            # Reconnect to restored database
            self.db_manager = DatabaseManager(self.config.db_file)

            logger.info(f"Database restored from {backup_path}")
            return {
                'success': True,
                'message': f'Database restored from {backup_path}. Previous version saved as {current_backup}'
            }

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise CalendarError(f"Restore failed: {e}")

    # Cleanup and maintenance
    def close(self):
        """Clean up resources"""
        if self.db_manager:
            self.db_manager.close()
        if self.auth_manager:
            self.auth_manager.logout()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
