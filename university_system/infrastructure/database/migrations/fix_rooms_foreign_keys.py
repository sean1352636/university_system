"""
Migration: Fix room foreign key references

Issue: The rooms table uses 'id' as primary key, but foreign keys reference 'room_id'
This migration updates all foreign key constraints to reference rooms(id) correctly.
"""

from university_system.infrastructure.database.db import get_connection, transaction

def migrate():
    """Fix foreign key constraints for rooms table"""

    with transaction() as conn:
        print("Starting rooms foreign key migration...")

        # 1. Drop and recreate room_bookings with correct foreign key
        print("  - Backing up and recreating room_bookings...")

        # Backup data (if any)
        conn.execute('''
            CREATE TEMPORARY TABLE room_bookings_backup AS
            SELECT * FROM room_bookings
        ''')

        # Drop old table
        conn.execute('DROP TABLE IF EXISTS room_bookings')

        # Recreate with correct foreign key
        conn.execute('''
            CREATE TABLE room_bookings (
                booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                booked_by TEXT NOT NULL,
                booking_type TEXT NOT NULL,
                purpose TEXT,
                start_datetime TEXT NOT NULL,
                end_datetime TEXT NOT NULL,
                setup_required TEXT,
                equipment_needed TEXT,
                expected_attendees INTEGER,
                recurrence_pattern TEXT,
                booking_status TEXT DEFAULT 'confirmed',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (room_id) REFERENCES rooms (id)
            )
        ''')

        # Restore data
        conn.execute('''
            INSERT INTO room_bookings
            SELECT * FROM room_bookings_backup
        ''')

        conn.execute('DROP TABLE room_bookings_backup')
        print("  ✓ room_bookings fixed")

        # 2. Fix maintenance_requests
        print("  - Fixing maintenance_requests...")
        conn.execute('''
            CREATE TEMPORARY TABLE maintenance_requests_backup AS
            SELECT * FROM maintenance_requests
        ''')

        conn.execute('DROP TABLE IF EXISTS maintenance_requests')

        conn.execute('''
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
                FOREIGN KEY (building_id) REFERENCES buildings (building_id),
                FOREIGN KEY (room_id) REFERENCES rooms (id)
            )
        ''')

        conn.execute('''
            INSERT INTO maintenance_requests
            SELECT * FROM maintenance_requests_backup
        ''')

        conn.execute('DROP TABLE maintenance_requests_backup')
        print("  ✓ maintenance_requests fixed")

        # 3. Fix facility_assets
        print("  - Fixing facility_assets...")
        conn.execute('''
            CREATE TEMPORARY TABLE facility_assets_backup AS
            SELECT * FROM facility_assets
        ''')

        conn.execute('DROP TABLE IF EXISTS facility_assets')

        conn.execute('''
            CREATE TABLE facility_assets (
                asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                asset_tag TEXT UNIQUE,
                building_id INTEGER,
                room_id INTEGER,
                purchase_date TEXT,
                purchase_cost REAL,
                warranty_expiry TEXT,
                maintenance_schedule TEXT,
                last_maintenance_date TEXT,
                condition TEXT DEFAULT 'good',
                status TEXT DEFAULT 'active',
                FOREIGN KEY (building_id) REFERENCES buildings (building_id),
                FOREIGN KEY (room_id) REFERENCES rooms (id)
            )
        ''')

        conn.execute('''
            INSERT INTO facility_assets
            SELECT * FROM facility_assets_backup
        ''')

        conn.execute('DROP TABLE facility_assets_backup')
        print("  ✓ facility_assets fixed")

        # 4. Fix space_utilization
        print("  - Fixing space_utilization...")
        conn.execute('''
            CREATE TEMPORARY TABLE space_utilization_backup AS
            SELECT * FROM space_utilization
        ''')

        conn.execute('DROP TABLE IF EXISTS space_utilization')

        conn.execute('''
            CREATE TABLE space_utilization (
                utilization_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                measurement_date TEXT NOT NULL,
                occupancy_rate REAL,
                booking_rate REAL,
                peak_usage_time TEXT,
                average_attendees REAL,
                total_booking_hours REAL,
                FOREIGN KEY (room_id) REFERENCES rooms (id)
            )
        ''')

        conn.execute('''
            INSERT INTO space_utilization
            SELECT * FROM space_utilization_backup
        ''')

        conn.execute('DROP TABLE space_utilization_backup')
        print("  ✓ space_utilization fixed")

        print("Migration completed successfully! ✅")


if __name__ == '__main__':
    print("=" * 60)
    print("Rooms Foreign Key Migration")
    print("=" * 60)
    migrate()
