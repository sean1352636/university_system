from __future__ import annotations
from datetime import datetime
from university_system.infrastructure.database.db import get_connection, sqlite3
from university_system.core.i18n import get_text as _t, init_i18n
from university_system.core.sql_safety import safe_alter_table_add_column

# Initialize i18n
init_i18n()

def init_campus_events_system_db():
    """Initialize the Campus Events Hub database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Campus Events Hub"))

        # Events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS campus_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_category TEXT NOT NULL,
            description TEXT,
            organizer_id TEXT NOT NULL,
            organizer_type TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT,
            room_id INTEGER,
            capacity INTEGER,
            registration_required BOOLEAN DEFAULT 0,
            registration_deadline TEXT,
            is_public BOOLEAN DEFAULT 1,
            is_featured BOOLEAN DEFAULT 0,
            tags TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Campus Event registrations (separate from alumni_events)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS campus_event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            user_type TEXT NOT NULL,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP,
            attendance_status TEXT DEFAULT 'registered',
            checked_in_at TEXT,
            feedback_rating INTEGER,
            feedback_comment TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id)
        )
        ''')

        # Migration: Ensure campus_event_registrations has all required columns
        cursor.execute("PRAGMA table_info(campus_event_registrations)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        event_reg_migrations = [
            ('user_id', 'TEXT'),
            ('user_type', 'TEXT'),
            ('registration_date', 'TEXT'),
            ('attendance_status', 'TEXT'),
            ('checked_in_at', 'TEXT'),
            ('feedback_rating', 'INTEGER'),
            ('feedback_comment', 'TEXT'),
        ]

        for col_name, col_type in event_reg_migrations:
            if col_name not in existing_columns:
                try:
                    safe_alter_table_add_column("campus_event_registrations", col_name, col_type, conn)
                    print(_t("schemas.added_missing_column", column=col_name, table="campus_event_registrations"))
                except Exception as e:
                    print(_t("schemas.column_add_warning", column=col_name, table="campus_event_registrations", error=str(e)))

        # Event series/recurring events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_series (
            series_id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_name TEXT NOT NULL,
            series_description TEXT,
            organizer_id TEXT NOT NULL,
            recurrence_pattern TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Event announcements
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_announcements (
            announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            announcement_text TEXT NOT NULL,
            sent_to TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_by TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id)
        )
        ''')

        # Event sponsors
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_sponsors (
            sponsor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            sponsor_name TEXT NOT NULL,
            sponsor_type TEXT,
            contribution_amount REAL,
            logo_url TEXT,
            website_url TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id)
        )
        ''')

        # Event calendar subscriptions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_calendar_subscriptions (
            subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            calendar_feed_url TEXT NOT NULL,
            filter_categories TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Campus Events Hub"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Campus Events", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ALUMNI RELATIONS & ENGAGEMENT SCHEMAS
# ============================================================================


def init_smart_timetable_system_db():
    """Initialize the Smart Timetable Optimizer database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Smart Timetable Optimizer"))

        # Timetable configurations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_configurations (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            optimization_status TEXT DEFAULT 'pending',
            last_optimized_date TEXT,
            conflicts_detected INTEGER DEFAULT 0,
            conflicts_resolved INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Time slots
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_time_slots (
            slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_name TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            is_available BOOLEAN DEFAULT 1,
            priority_level INTEGER DEFAULT 3
        )
        ''')

        # Class schedules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_classes (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            class_type TEXT NOT NULL,
            instructor_id TEXT,
            room_id INTEGER,
            slot_id INTEGER NOT NULL,
            capacity INTEGER DEFAULT 30,
            enrolled_count INTEGER DEFAULT 0,
            recurrence_pattern TEXT DEFAULT 'weekly',
            status TEXT DEFAULT 'scheduled',
            FOREIGN KEY (config_id) REFERENCES timetable_configurations (config_id),
            FOREIGN KEY (slot_id) REFERENCES timetable_time_slots (slot_id)
        )
        ''')

        # Scheduling constraints
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_constraints (
            constraint_id INTEGER PRIMARY KEY AUTOINCREMENT,
            constraint_type TEXT NOT NULL,
            constraint_name TEXT NOT NULL,
            applies_to TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            constraint_rule TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            is_hard_constraint BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Scheduling conflicts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_conflicts (
            conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            conflict_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            affected_schedules TEXT,
            resolution_status TEXT DEFAULT 'unresolved',
            resolution_notes TEXT,
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (config_id) REFERENCES timetable_configurations (config_id)
        )
        ''')

        # Student preferences
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_student_preferences (
            preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            preference_type TEXT NOT NULL,
            preferred_days TEXT,
            preferred_times TEXT,
            avoid_days TEXT,
            avoid_times TEXT,
            max_daily_hours INTEGER,
            gap_preference TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Smart Timetable Optimizer"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Smart Timetable", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# CAMPUS EVENTS HUB SCHEMAS
# ============================================================================


