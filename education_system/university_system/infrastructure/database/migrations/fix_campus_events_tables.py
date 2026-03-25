"""
Database migration to fix campus events tables

This migration:
1. Recreates event_registrations as unified_event_registrations with correct schema
2. Ensures unified_events table exists with the new schema
3. Adds any missing indexes for performance
"""

from education_system.university_system.core import paths
from education_system.university_system.infrastructure.database.db import sqlite3
def migrate():
    """Run the migration"""
    db_path = paths.DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Starting unified events table migration...")

        # 1. Drop the old event_registrations and campus_event_registrations tables
        print("  - Dropping old event_registrations table...")
        cursor.execute("DROP TABLE IF EXISTS event_registrations")
        cursor.execute("DROP TABLE IF EXISTS campus_event_registrations")
        cursor.execute("DROP TABLE IF EXISTS career_event_registrations")
        cursor.execute("DROP TABLE IF EXISTS alumni_event_registrations")
        cursor.execute("DROP TABLE IF EXISTS event_attendance")

        # 2. Create the unified_event_registrations table
        print("  - Creating unified_event_registrations table with correct schema...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS unified_event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id TEXT,
            user_type TEXT,
            registration_date TEXT DEFAULT (datetime('now')),
            attendance_status TEXT DEFAULT 'registered',
            checked_in_at TEXT,
            check_out_time TEXT,
            payment_status TEXT,
            payment_amount REAL,
            payment_method TEXT,
            is_waitlisted INTEGER DEFAULT 0,
            num_guests INTEGER DEFAULT 0,
            feedback_rating INTEGER,
            feedback_comment TEXT,
            qr_code TEXT,
            cpd_credits REAL,
            FOREIGN KEY (event_id) REFERENCES unified_events(event_id)
        )
        ''')

        # 3. Add indexes for better performance
        print("  - Creating indexes...")
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_unified_event_registrations_event_id
        ON unified_event_registrations(event_id)
        ''')

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_unified_event_registrations_user
        ON unified_event_registrations(user_id, user_type)
        ''')

        # 4. Ensure unified_events table exists
        cursor.execute('''
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='table' AND name='unified_events'
        ''')
        if cursor.fetchone()[0] == 0:
            print("  Warning: unified_events table doesn't exist. Creating it...")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_event_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                event_type TEXT,
                event_category TEXT,
                start_datetime TEXT,
                end_datetime TEXT,
                location TEXT,
                building TEXT,
                room TEXT,
                room_id INTEGER,
                organizer_id TEXT,
                organizer_name TEXT,
                organizer_type TEXT,
                max_capacity INTEGER,
                registration_required INTEGER DEFAULT 0,
                registration_deadline TEXT,
                is_public INTEGER DEFAULT 1,
                is_featured INTEGER DEFAULT 0,
                status TEXT DEFAULT 'scheduled',
                tags TEXT,
                image_url TEXT,
                virtual_link TEXT,
                event_fee REAL DEFAULT 0,
                payment_required INTEGER DEFAULT 0,
                waitlist_enabled INTEGER DEFAULT 0,
                qr_code_path TEXT,
                club_id INTEGER,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT,
                notes TEXT
            )
            ''')

        # 5. Verify event_sponsors table has correct foreign key
        cursor.execute('''
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name='event_sponsors'
        ''')
        result = cursor.fetchone()
        if result and 'FOREIGN KEY (event_id) REFERENCES unified_events (event_id)' in result[0]:
            print("  - event_sponsors foreign key is correct")
        else:
            print("  - event_sponsors table might need foreign key fix")

        # 6. Create event_announcements table if missing
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_announcements (
            announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            announcement_text TEXT NOT NULL,
            sent_to TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_by TEXT,
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id) ON DELETE CASCADE
        )
        ''')

        # 7. Create event_series table if missing
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

        # 8. Drop old event tables that are now replaced by unified_events
        print("  - Dropping old event tables replaced by unified_events...")
        cursor.execute("DROP TABLE IF EXISTS campus_events")
        cursor.execute("DROP TABLE IF EXISTS career_events")
        cursor.execute("DROP TABLE IF EXISTS alumni_events")

        conn.commit()
        print("Migration completed successfully!")
        return True

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
