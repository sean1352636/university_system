"""
Database migration to fix campus events tables

This migration:
1. Recreates event_registrations table with correct schema for campus events
2. Ensures foreign key constraints are correct
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
        print("Starting campus events table migration...")

        # 1. Drop the incorrectly-structured event_registrations table
        print("  - Dropping old event_registrations table...")
        cursor.execute("DROP TABLE IF EXISTS event_registrations")

        # 2. Create the correct event_registrations table for campus events
        print("  - Creating new event_registrations table with correct schema...")
        cursor.execute('''
        CREATE TABLE event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            user_type TEXT NOT NULL,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP,
            attendance_status TEXT DEFAULT 'registered',
            checked_in_at TEXT,
            feedback_rating INTEGER,
            feedback_comment TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id) ON DELETE CASCADE
        )
        ''')

        # 3. Add indexes for better performance
        print("  - Creating indexes...")
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_event_registrations_event_id
        ON event_registrations(event_id)
        ''')

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_event_registrations_user
        ON event_registrations(user_id, user_type)
        ''')

        # 4. Verify campus_events table exists
        cursor.execute('''
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='table' AND name='campus_events'
        ''')
        if cursor.fetchone()[0] == 0:
            print("  ⚠️  Warning: campus_events table doesn't exist. Creating it...")
            cursor.execute('''
            CREATE TABLE campus_events (
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

        # 5. Verify event_sponsors table has correct foreign key
        # (Already correct, but let's verify)
        cursor.execute('''
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name='event_sponsors'
        ''')
        result = cursor.fetchone()
        if result and 'FOREIGN KEY (event_id) REFERENCES campus_events (event_id)' in result[0]:
            print("  ✓ event_sponsors foreign key is correct")
        else:
            print("  ⚠️  event_sponsors table might need foreign key fix")

        # 6. Create event_announcements table if missing
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_announcements (
            announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            announcement_text TEXT NOT NULL,
            sent_to TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_by TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id) ON DELETE CASCADE
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

        conn.commit()
        print("✅ Migration completed successfully!")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
