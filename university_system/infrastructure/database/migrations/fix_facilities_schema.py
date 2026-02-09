"""
Migration: Fix facilities management schema mismatches

This migration fixes the following issues:
1. rooms table missing building_id, floor_number, and status columns
2. rooms table using 'building' instead of 'building_id'
3. maintenance_requests foreign key referencing non-existent rooms.room_id
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH


def migrate():
    """Run the migration"""
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()

    try:
        print("Starting facilities schema migration...")

        # Check if migration is needed
        cursor.execute("PRAGMA table_info(rooms)")
        columns = {row[1] for row in cursor.fetchall()}

        if 'building_id' in columns:
            print("Migration already applied. Skipping.")
            return

        print("Step 1: Creating new rooms table with correct schema...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building_id INTEGER NOT NULL,
                room_number TEXT NOT NULL,
                room_type TEXT,
                capacity INTEGER DEFAULT 0,
                floor_number INTEGER DEFAULT 1,
                status TEXT DEFAULT 'available',
                equipment TEXT,
                notes TEXT,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (building_id) REFERENCES buildings(building_id),
                UNIQUE(building_id, room_number)
            )
        ''')

        print("Step 2: Migrating data from old rooms table...")
        # Get building mapping (building_code -> building_id)
        cursor.execute("SELECT building_id, building_code FROM buildings")
        building_map = {row[1]: row[0] for row in cursor.fetchall()}

        # Migrate room data
        cursor.execute("SELECT id, room_number, building, capacity, room_type, equipment, notes, is_active FROM rooms")
        old_rooms = cursor.fetchall()

        for room in old_rooms:
            room_id, room_number, building_code, capacity, room_type, equipment, notes, is_active = room

            # Try to find building_id
            building_id = building_map.get(building_code)
            if not building_id:
                # Try to parse if it's already an ID
                try:
                    building_id = int(building_code) if building_code else None
                except (ValueError, TypeError):
                    building_id = None

            if building_id:
                cursor.execute('''
                    INSERT INTO rooms_new (
                        id, building_id, room_number, room_type, capacity,
                        floor_number, status, equipment, notes, is_active
                    ) VALUES (?, ?, ?, ?, ?, 1, 'available', ?, ?, ?)
                ''', (room_id, building_id, room_number, room_type, capacity, equipment, notes, is_active))
                print(f"  Migrated room {room_number} (ID: {room_id})")

        print("Step 3: Replacing old rooms table...")
        cursor.execute("DROP TABLE rooms")
        cursor.execute("ALTER TABLE rooms_new RENAME TO rooms")

        print("Step 4: Recreating maintenance_requests foreign keys...")
        # Get existing maintenance requests
        cursor.execute("SELECT * FROM maintenance_requests")
        maint_requests = cursor.fetchall()

        # Drop and recreate table with correct foreign key
        cursor.execute("DROP TABLE IF EXISTS maintenance_requests_backup")
        cursor.execute('''
            CREATE TABLE maintenance_requests_backup AS
            SELECT * FROM maintenance_requests
        ''')

        cursor.execute("DROP TABLE maintenance_requests")
        cursor.execute('''
            CREATE TABLE maintenance_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_type TEXT NOT NULL,
                building_id INTEGER,
                room_id INTEGER,
                request_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                description TEXT NOT NULL,
                reported_by TEXT NOT NULL,
                reported_date TEXT DEFAULT CURRENT_TIMESTAMP,
                assigned_to TEXT,
                assigned_date TEXT,
                scheduled_date TEXT,
                completion_date TEXT,
                status TEXT DEFAULT 'open',
                cost REAL,
                notes TEXT,
                FOREIGN KEY (building_id) REFERENCES buildings(building_id),
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            )
        ''')

        cursor.execute('''
            INSERT INTO maintenance_requests
            SELECT * FROM maintenance_requests_backup
        ''')

        cursor.execute("DROP TABLE maintenance_requests_backup")

        print("Step 5: Committing changes...")
        conn.commit()

        print("✓ Migration completed successfully!")
        print(f"  - Updated {len(old_rooms)} rooms")
        print("  - Fixed maintenance_requests foreign keys")

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.close()


if __name__ == "__main__":
    migrate()
