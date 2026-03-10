"""Database maintenance CLI functions."""

import os

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as _DB_PATH
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.utils.sql_safety import (
    validate_table_name,
    SQLIdentifierError,
)


def database_maintenance_menu(log_manager, auth):
    """Database maintenance menu"""
    print("\n\U0001f527 DATABASE MAINTENANCE")
    print("="*26)

    print("1. Check database size")
    print("2. Optimize database")
    print("3. Rebuild indexes")
    print("4. Vacuum database")
    print("5. Database statistics")
    print("6. Return")

    choice = input("Choose maintenance option: ")

    if choice == '1':
        check_database_size(log_manager)
    elif choice == '2':
        optimize_database(log_manager, auth)
    elif choice == '3':
        rebuild_indexes(log_manager)
    elif choice == '4':
        vacuum_database(log_manager)
    elif choice == '5':
        show_database_stats(log_manager)


def check_database_size(log_manager):
    """Check database size and usage"""
    print("\n\U0001f4be DATABASE SIZE CHECK")
    print("="*24)

    db_path = log_manager.db.db_path

    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        size_mb = size_bytes / (1024 * 1024)
        size_gb = size_mb / 1024

        print(f"Database file: {db_path}")
        print(f"Size: {size_bytes:,} bytes")
        print(f"Size: {size_mb:.2f} MB")
        print(f"Size: {size_gb:.3f} GB")

        # Get record counts
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM logs")
        log_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alerts")
        alert_count = cursor.fetchone()[0]

        conn.close()

        print(f"\nRecord counts:")
        print(f"Logs: {log_count:,}")
        print(f"Alerts: {alert_count:,}")

        # Estimate average sizes
        if log_count > 0:
            avg_log_size = size_bytes / log_count
            print(f"Average log size: {avg_log_size:.0f} bytes")
    else:
        print("Database file not found.")

    input("\nPress Enter to continue...")


def optimize_database(log_manager, auth):
    """Optimize database performance"""
    print("\n\u26a1 DATABASE OPTIMIZATION")
    print("="*26)

    print("This will optimize the database for better performance.")
    confirm = input("Continue? (y/n): ")

    if confirm.lower() != 'y':
        return

    try:
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()

        print("Running optimization...")

        # Analyze tables
        cursor.execute("ANALYZE")
        print("\u2713 Table analysis completed")

        # Update statistics
        cursor.execute("PRAGMA optimize")
        print("\u2713 Statistics updated")

        conn.commit()
        conn.close()

        print("Database optimization completed!")

    except Exception as e:
        print(f"Error during optimization: {e}")

    input("\nPress Enter to continue...")


def rebuild_indexes(log_manager):
    """Rebuild database indexes"""
    print("\n\U0001f3d7\ufe0f REBUILD INDEXES")
    print("="*18)

    confirm = input("Rebuild all database indexes? (y/n): ")

    if confirm.lower() != 'y':
        return

    try:
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()

        print("Rebuilding indexes...")

        # Drop and recreate indexes
        indexes = [
            "DROP INDEX IF EXISTS idx_logs_timestamp",
            "DROP INDEX IF EXISTS idx_logs_user_id",
            "DROP INDEX IF EXISTS idx_logs_action",
            "DROP INDEX IF EXISTS idx_logs_module",
            "CREATE INDEX idx_logs_timestamp ON logs(timestamp)",
            "CREATE INDEX idx_logs_user_id ON logs(user_id)",
            "CREATE INDEX idx_logs_action ON logs(action)",
            "CREATE INDEX idx_logs_module ON logs(module)"
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)
            print(".", end="", flush=True)

        conn.commit()
        conn.close()

        print("\nIndexes rebuilt successfully!")

    except Exception as e:
        print(f"Error rebuilding indexes: {e}")

    input("\nPress Enter to continue...")


def vacuum_database(log_manager):
    """Vacuum database to reclaim space"""
    print("\n\U0001f9f9 VACUUM DATABASE")
    print("="*19)

    print("This will reclaim unused space in the database.")
    print("\u26a0\ufe0f This operation may take some time for large databases.")

    confirm = input("Continue? (y/n): ")

    if confirm.lower() != 'y':
        return

    try:
        # Get size before
        size_before = os.path.getsize(log_manager.db.db_path)

        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()

        print("Running VACUUM...")
        cursor.execute("VACUUM")

        conn.close()

        # Get size after
        size_after = os.path.getsize(log_manager.db.db_path)
        space_saved = size_before - size_after

        print(f"VACUUM completed!")
        print(f"Space reclaimed: {space_saved:,} bytes ({space_saved/(1024*1024):.2f} MB)")

    except Exception as e:
        print(f"Error during VACUUM: {e}")

    input("\nPress Enter to continue...")


def show_database_stats(log_manager):
    """Show detailed database statistics"""
    print("\n\U0001f4ca DATABASE STATISTICS")
    print("="*24)

    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Table information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        print("Database Tables:")
        for table in tables:
            # Validate table name using SQL safety utility
            try:
                validated_table = validate_table_name(table, conn=conn)
                # Use bracket quoting for additional safety
                cursor.execute(f"SELECT COUNT(*) FROM [{validated_table}]")
                count = cursor.fetchone()[0]
                print(f"  {validated_table}: {count:,} records")
            except SQLIdentifierError:
                print(f"  {table}: Invalid table (skipped)")

        # Index information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]

        print(f"\nIndexes: {len(indexes)}")
        for index in indexes:
            if not index.startswith('sqlite_'):  # Skip system indexes
                print(f"  {index}")

        # Recent activity stats
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN date(timestamp) = date('now') THEN 1 END) as today,
                COUNT(CASE WHEN date(timestamp) >= date('now', '-7 days') THEN 1 END) as last_week
            FROM logs
        """)

        stats = cursor.fetchone()

        print(f"\nActivity Statistics:")
        print(f"  Total logs: {stats['total']:,}")
        print(f"  Today: {stats['today']:,}")
        print(f"  Last 7 days: {stats['last_week']:,}")

        # Performance info
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]

        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]

        print(f"\nPerformance Info:")
        print(f"  Page count: {page_count:,}")
        print(f"  Page size: {page_size:,} bytes")
        print(f"  Estimated size: {(page_count * page_size)/(1024*1024):.2f} MB")

        conn.close()

    except Exception as e:
        print(f"Error retrieving statistics: {e}")

    input("\nPress Enter to continue...")
