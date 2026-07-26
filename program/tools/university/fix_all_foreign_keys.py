#!/usr/bin/env python3
"""
Fix all foreign key constraints in the database.

This script fixes tables that incorrectly reference users(user_id)
when they should reference users(id).
"""

from education_system.systems.university.infrastructure.database.db import transaction, get_connection
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
import sys

def fix_foreign_keys():
    """Fix all tables with incorrect foreign key references."""

    # Tables that need fixing with their schemas
    tables_to_fix = {
        'app_installations': """
            CREATE TABLE app_installations (
                installation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_id INTEGER,
                app_version TEXT,
                installation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
            )
        """,
        'blockchain_wallets': """
            CREATE TABLE blockchain_wallets (
                wallet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                wallet_address TEXT NOT NULL UNIQUE,
                public_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """,
        'mobile_analytics': """
            CREATE TABLE mobile_analytics (
                analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """,
        'mobile_devices': """
            CREATE TABLE mobile_devices (
                device_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_name TEXT,
                device_type TEXT,
                os_version TEXT,
                app_version TEXT,
                push_token TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """,
        'mobile_preferences': """
            CREATE TABLE mobile_preferences (
                pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                notifications_enabled BOOLEAN DEFAULT 1,
                dark_mode BOOLEAN DEFAULT 0,
                language TEXT DEFAULT 'en',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """,
        'mobile_sessions': """
            CREATE TABLE mobile_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_id INTEGER,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                logout_time TIMESTAMP,
                session_token TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
            )
        """,
        'rideshare_posts': """
            CREATE TABLE rideshare_posts (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                post_type TEXT NOT NULL,
                departure_location TEXT NOT NULL,
                destination TEXT NOT NULL,
                departure_time TIMESTAMP NOT NULL,
                seats_available INTEGER,
                price_per_seat REAL,
                notes TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """,
        'visitor_parking': """
            CREATE TABLE visitor_parking (
                visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_user_id INTEGER,
                visitor_name TEXT NOT NULL,
                visitor_vehicle TEXT,
                visitor_plate TEXT,
                visit_date TEXT NOT NULL,
                duration_hours INTEGER,
                parking_location TEXT,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (host_user_id) REFERENCES users(id)
            )
        """
    }

    print("=" * 70)
    print("FIXING ALL FOREIGN KEY CONSTRAINTS")
    print("=" * 70)

    try:
        with transaction() as conn:
            cursor = conn.cursor()

            for table_name, new_schema in tables_to_fix.items():
                print(f"\nProcessing {table_name}...")

                # Validate table name for defense-in-depth
                validate_identifier(table_name, "table name")

                # Check if table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name=?
                """, (table_name,))

                if not cursor.fetchone():
                    print("  ⚠️  Table does not exist, skipping")
                    continue

                # Backup data
                cursor.execute(f"SELECT * FROM [{table_name}]")
                backup_data = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                print(f"  📦 Backed up {len(backup_data)} row(s)")

                # Drop table
                cursor.execute(f"DROP TABLE [{table_name}]")
                print("  🗑️  Dropped table")

                # Recreate with correct schema
                cursor.execute(new_schema.strip())
                print("  ✨ Recreated table")

                # Restore data
                if backup_data:
                    # Validate column names for defense-in-depth
                    for col in columns:
                        validate_identifier(col, "column name")
                    placeholders = ','.join(['?' for _ in columns])
                    insert_sql = f"INSERT INTO [{table_name}] ({','.join(columns)}) VALUES ({placeholders})"
                    cursor.executemany(insert_sql, backup_data)
                    print(f"  💾 Restored {len(backup_data)} row(s)")
                else:
                    print("  ℹ️  No data to restore")

                print(f"  ✅ {table_name} fixed successfully")

        print("\n" + "=" * 70)
        print("✅ ALL FOREIGN KEY CONSTRAINTS FIXED SUCCESSFULLY!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n❌ Error during fix: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_foreign_keys()
    sys.exit(0 if success else 1)
