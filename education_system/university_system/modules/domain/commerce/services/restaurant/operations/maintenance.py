from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta

from education_system.university_system.modules.domain.commerce.services.restaurant.operations import restaurant_context as ctx
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.restaurant_context import (
    DATABASE_FILE,
    get_db_connection,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.audit import log_audit_action
from education_system.university_system.infrastructure.logging.log_config import get_log_file
from education_system.university_system.core.sql_safety import validate_identifier, validate_table_name  # nosec B608

# Configure logging
logger = logging.getLogger(__name__)

def system_maintenance():
    """System maintenance operations"""

    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in for system maintenance.")
        return

    if not ctx.auth.check_permission('admin'):
        print("You don't have permission for system maintenance.")
        return

    try:
        print("\n" + "="*50)
        print("SYSTEM MAINTENANCE")
        print("="*50)

        print("\nOptions:")
        print("1. Database cleanup")
        print("2. Clear old logs")
        print("3. Reset system counters")
        print("4. Rebuild indexes")
        print("5. System health check")
        print("6. Clear cache")
        print("7. Return to system settings")

        choice = input("Choose an option (1-7): ")

        if choice == '1':
            database_cleanup()
        elif choice == '2':
            clear_old_logs()
        elif choice == '3':
            reset_system_counters()
        elif choice == '4':
            rebuild_indexes()
        elif choice == '5':
            system_health_check()
        elif choice == '6':
            clear_cache()
        elif choice == '7':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in system_maintenance: {e}")
        print(f"An error occurred: {e}")

def database_cleanup():
    """Perform database cleanup operations"""
    try:
        print("\nPerforming database cleanup...")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Remove old completed orders (older than 2 years)
        two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
        cursor.execute('DELETE FROM orders WHERE order_status = ? AND order_date < ?',
                      ('Completed', two_years_ago))
        deleted_orders = cursor.rowcount

        # Remove old audit logs (older than 1 year)
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        cursor.execute('DELETE FROM restaurant_audit_logs WHERE timestamp < ?', (one_year_ago,))
        deleted_logs = cursor.rowcount

        # Remove old notifications (older than 90 days)
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        cursor.execute('DELETE FROM restaurant_notifications WHERE created_date < ?', (ninety_days_ago,))
        deleted_notifications = cursor.rowcount

        # Vacuum database to reclaim space
        cursor.execute('VACUUM')

        conn.commit()
        conn.close()

        print(f"✅ Database cleanup completed!")
        print(f"Deleted {deleted_orders} old orders")
        print(f"Deleted {deleted_logs} old audit logs")
        print(f"Deleted {deleted_notifications} old notifications")
        print("Database vacuumed to reclaim space")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'DATABASE_CLEANUP',
            None,
            None,
            None,
            {'deleted_orders': deleted_orders, 'deleted_logs': deleted_logs, 'deleted_notifications': deleted_notifications}
        )

    except Exception as e:
        logging.error(f"Error in database_cleanup: {e}")
        print(f"An error occurred: {e}")

def clear_old_logs():
    """Clear old log files"""
    try:
        print("\nClearing old log files...")

        # Get log directory
        log_dir = os.path.dirname(get_log_file("restaurant_system.log"))

        if not os.path.exists(log_dir):
            print("Log directory not found.")
            return

        deleted_count = 0
        total_size = 0

        # Remove log files older than 30 days
        cutoff_date = datetime.now() - timedelta(days=30)

        for filename in os.listdir(log_dir):
            if filename.endswith('.log'):
                file_path = os.path.join(log_dir, filename)
                file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_modified < cutoff_date:
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    deleted_count += 1
                    total_size += file_size

        print(f"✅ Cleared {deleted_count} old log files")
        print(f"Freed {total_size / 1024 / 1024:.2f} MB of disk space")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'CLEAR_OLD_LOGS',
            None,
            None,
            None,
            {'deleted_files': deleted_count, 'freed_space_mb': total_size / 1024 / 1024}
        )

    except Exception as e:
        logging.error(f"Error in clear_old_logs: {e}")
        print(f"An error occurred: {e}")

def reset_system_counters():
    """Reset system counters and statistics"""
    try:
        print("\nResetting system counters...")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Reset QR code usage counts
        cursor.execute('UPDATE restaurant_qr_codes SET usage_count = 0')

        # Reset menu item popularity scores (optional)
        reset_popularity = input("Reset menu item popularity scores? (y/n): ")
        if reset_popularity.lower() == 'y':
            cursor.execute('UPDATE menu_items SET popularity_score = 0')
            print("Menu item popularity scores reset")

        conn.commit()
        conn.close()

        print("✅ System counters reset successfully!")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'RESET_SYSTEM_COUNTERS',
            None,
            None,
            None,
            {'reset_popularity': reset_popularity.lower() == 'y'}
        )

    except Exception as e:
        logging.error(f"Error in reset_system_counters: {e}")
        print(f"An error occurred: {e}")

def rebuild_indexes():
    """Rebuild database indexes for better performance"""
    try:
        print("\nRebuilding database indexes...")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Drop and recreate indexes
        indexes = [
            ('idx_restaurant_orders_date', 'orders', 'order_date'),
            ('idx_restaurant_orders_customer', 'orders', 'customer_id'),
            ('idx_restaurant_orders_status', 'orders', 'order_status'),
            ('idx_restaurant_customer_email', 'restaurant_customers', 'email'),
            ('idx_restaurant_inventory_reorder', 'restaurant_inventory', 'reorder_level'),
            ('idx_restaurant_staff_schedules_date', 'restaurant_staff_schedules', 'date'),
            ('idx_restaurant_audit_logs_timestamp', 'restaurant_audit_logs', 'timestamp')
        ]

        for index_name, table_name, column_name in indexes:
            try:
                safe_index = validate_identifier(index_name, "index")
                safe_table = validate_identifier(table_name, "table")
                safe_column = validate_identifier(column_name, "column")
                cursor.execute('DROP INDEX IF EXISTS [' + safe_index + ']')
                cursor.execute('CREATE INDEX [' + safe_index + '] ON [' + safe_table + ']([' + safe_column + '])')
                print(f"Rebuilt index: {index_name}")
            except Exception as e:
                print(f"Warning: Could not rebuild index {index_name}: {e}")

        # Analyze tables for query optimization
        cursor.execute('ANALYZE')

        conn.commit()
        conn.close()

        print("✅ Database indexes rebuilt successfully!")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'REBUILD_INDEXES',
            None,
            None,
            None,
            {'indexes_rebuilt': len(indexes)}
        )

    except Exception as e:
        logging.error(f"Error in rebuild_indexes: {e}")
        print(f"An error occurred: {e}")

def system_health_check():
    """Perform system health check"""
    try:
        print("\n" + "="*60)
        print("SYSTEM HEALTH CHECK")
        print("="*60)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check database integrity
        print("Checking database integrity...")
        cursor.execute('PRAGMA integrity_check')
        integrity_result = cursor.fetchone()[0]
        print(f"Database integrity: {integrity_result}")

        # Check table counts
        tables = [
            'menu_items', 'orders', 'restaurant_customers', 'restaurant_tables',
            'restaurant_staff', 'restaurant_inventory', 'restaurant_suppliers'
        ]

        print("\nTable record counts:")
        for table in tables:
            try:
                safe_table = validate_identifier(table, "table")
                cursor.execute('SELECT COUNT(*) FROM [' + safe_table + ']')
                count = cursor.fetchone()[0]
                print(f"  {table}: {count} records")
            except Exception as e:
                print(f"  {table}: Error - {e}")

        # Check for orphaned records
        print("\nChecking for data consistency issues...")

        # Orders without customers
        cursor.execute('''
            SELECT COUNT(*) FROM orders o
            LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
            WHERE o.customer_id IS NOT NULL AND c.customer_id IS NULL
        ''')
        orphaned_orders = cursor.fetchone()[0]
        if orphaned_orders > 0:
            print(f"  Warning: {orphaned_orders} orders reference non-existent customers")

        # Order items without menu items
        cursor.execute('''
            SELECT COUNT(*) FROM order_items oi
            LEFT JOIN menu_items mi ON oi.item_id = mi.item_id
            WHERE mi.item_id IS NULL
        ''')
        orphaned_items = cursor.fetchone()[0]
        if orphaned_items > 0:
            print(f"  Warning: {orphaned_items} order items reference non-existent menu items")

        # Check disk space (if possible)
        try:
            db_size = os.path.getsize(DATABASE_FILE)
            print(f"\nDatabase file size: {db_size / 1024 / 1024:.2f} MB")
        except (OSError, IOError):
            print("\nCould not determine database file size")

        # Check system settings
        cursor.execute('SELECT COUNT(*) FROM restaurant_system_settings')
        settings_count = cursor.fetchone()[0]
        print(f"System settings: {settings_count} configured")

        if integrity_result == 'ok' and orphaned_orders == 0 and orphaned_items == 0:
            print("\n✅ System health check passed - no issues found")
        else:
            print("\n⚠️  System health check completed with warnings")

        conn.close()

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'SYSTEM_HEALTH_CHECK',
            None,
            None,
            None,
            {'integrity': integrity_result, 'orphaned_orders': orphaned_orders, 'orphaned_items': orphaned_items}
        )

    except Exception as e:
        logging.error(f"Error in system_health_check: {e}")
        print(f"An error occurred: {e}")

def clear_cache():
    """Clear system cache"""
    try:
        print("\nClearing system cache...")

        # Clear any temporary files
        temp_files_cleared = 0
        for filename in os.listdir('.'):
            if filename.endswith('.tmp') or filename.startswith('temp_'):
                try:
                    os.remove(filename)
                    temp_files_cleared += 1
                except Exception as e:
                    logger.debug(f"Could not remove temp file {filename}: {e}")

        print(f"✅ Cache cleared successfully!")
        print(f"Removed {temp_files_cleared} temporary files")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'CLEAR_CACHE',
            None,
            None,
            None,
            {'temp_files_cleared': temp_files_cleared}
        )

    except Exception as e:
        logging.error(f"Error in clear_cache: {e}")
        print(f"An error occurred: {e}")

def database_optimization():
    """Database optimization operations"""
    try:
        print("\n" + "="*50)
        print("DATABASE OPTIMIZATION")
        print("="*50)

        print("\nOptimization options:")
        print("1. Analyze query performance")
        print("2. Optimize table structure")
        print("3. Update statistics")
        print("4. Defragment database")
        print("5. Return to system settings")

        choice = input("Choose option (1-5): ")

        if choice == '1':
            analyze_query_performance()
        elif choice == '2':
            optimize_table_structure()
        elif choice == '3':
            update_statistics()
        elif choice == '4':
            defragment_database()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in database_optimization: {e}")
        print(f"An error occurred: {e}")

def update_statistics():
    """Update database statistics"""
    try:
        print("\nUpdating database statistics...")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Update SQLite statistics
        cursor.execute('ANALYZE')

        conn.commit()
        conn.close()

        print("✅ Database statistics updated successfully!")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'UPDATE_DB_STATISTICS',
            None,
            None,
            None,
            {'completed': True}
        )

    except Exception as e:
        logging.error(f"Error in update_statistics: {e}")
        print(f"An error occurred: {e}")

def defragment_database():
    """Defragment (vacuum) the database."""
    conn = None
    cursor = None
    try:
        print("\nDefragmenting database...")

        conn = get_db_connection()

        # If this is sqlite3, VACUUM must run in autocommit mode (no active transaction).
        # sqlite3 connections expose `isolation_level`. Use that to flip to autocommit safely.
        if hasattr(conn, "isolation_level"):  # likely sqlite3
            # Ensure no pending txn
            try:
                conn.commit()
            except Exception as e:
                logger.debug(f"Error committing transaction: {e}")

            old_iso = conn.isolation_level
            try:
                conn.isolation_level = None  # autocommit
                conn.execute("VACUUM")
            finally:
                # restore isolation level
                conn.isolation_level = old_iso
        else:
            # Generic DB (e.g., Postgres). VACUUM is fine in a txn for many drivers,
            # but we'll keep it simple.
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            conn.commit()

        print("✅ Database defragmentation completed!")

        # Audit log (assumes these exist in your codebase)
        log_audit_action(
            ctx.auth.current_user['id'],
            'DEFRAGMENT_DATABASE',
            None,
            None,
            None,
            {'completed': True}
        )

    except Exception as e:
        logging.error(f"Error in defragment_database: {e}", exc_info=True)
        print(f"An error occurred: {e}")
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception as e:
            logger.debug(f"Error closing cursor: {e}")
        try:
            if conn:
                conn.close()
        except Exception as e:
            logger.debug(f"Error closing connection: {e}")


def analyze_query_performance():
    """Analyze query performance"""
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to analyze query performance.")
        return

    if not ctx.auth.check_permission('admin'):
        print("You don't have permission to analyze query performance.")
        return

    try:
        print("\n" + "="*60)
        print("QUERY PERFORMANCE ANALYSIS")
        print("="*60)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Test common queries and measure execution time
        test_queries = [
            ("Daily Sales Query", '''
                SELECT COUNT(*), SUM(total_amount)
                FROM orders
                WHERE DATE(order_date) = date('now') AND order_status = 'Completed'
            '''),
            ("Menu Items Lookup", '''
                SELECT * FROM menu_items WHERE available = 1 ORDER BY category, name
            '''),
            ("Customer Orders", '''
                SELECT o.*, c.name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                ORDER BY o.order_date DESC LIMIT 50
            '''),
            ("Inventory Low Stock", '''
                SELECT * FROM restaurant_inventory
                WHERE quantity <= reorder_level
            '''),
            ("Staff Schedules", '''
                SELECT ss.*, s.name
                FROM restaurant_staff_schedules ss
                JOIN restaurant_staff s ON ss.staff_id = s.staff_id
                WHERE ss.date = date('now')
            ''')
        ]

        print("Testing query performance...")
        print("-"*60)
        print(f"{'Query':<25} {'Execution Time':<15} {'Rows':<8} {'Status':<10}")
        print("-"*60)

        for query_name, query_sql in test_queries:
            try:
                start_time = time.time()
                cursor.execute(query_sql)
                results = cursor.fetchall()
                end_time = time.time()

                execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
                row_count = len(results)

                if execution_time < 100:
                    status = "Fast"
                elif execution_time < 500:
                    status = "OK"
                else:
                    status = "Slow"

                print(f"{query_name[:24]:<25} {execution_time:<14.2f}ms {row_count:<8} {status:<10}")

            except Exception as e:
                print(f"{query_name[:24]:<25} {'ERROR':<15} {0:<8} {'Failed':<10}")
                logging.error(f"Query failed: {query_name} - {e}")

        conn.close()
        print("\nQuery performance analysis completed.")

    except Exception as e:
        logging.error(f"Error in analyze_query_performance: {e}")
        print(f"An error occurred: {e}")


def optimize_table_structure():
    """Optimize table structure"""
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to optimize table structure.")
        return

    if not ctx.auth.check_permission('admin'):
        print("You don't have permission to optimize table structure.")
        return

    try:
        print("\n" + "="*60)
        print("TABLE STRUCTURE OPTIMIZATION")
        print("="*60)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Analyze table structures
        tables_to_analyze = [
            'orders', 'restaurant_customers', 'menu_items',
            'restaurant_inventory', 'restaurant_staff', 'restaurant_audit_logs'
        ]

        print("Analyzing table structures...")
        print("-"*60)

        for table in tables_to_analyze:
            try:
                safe_table = validate_identifier(table, "table")
                # Get table info
                cursor.execute("PRAGMA table_info([" + safe_table + "])")
                columns = cursor.fetchall()

                # Get table size
                cursor.execute('SELECT COUNT(*) FROM [' + safe_table + ']')
                row_count = cursor.fetchone()[0]

                print(f"\nTable: {table}")
                print(f"Rows: {row_count:,}")
                print(f"Columns: {len(columns)}")

                # Check for missing indexes
                index_suggestions = []

                if table == 'orders':
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='orders' AND name LIKE '%order_date%'")
                    if not cursor.fetchone():
                        index_suggestions.append("order_date (for date queries)")

                if index_suggestions:
                    print(f"Suggested indexes:")
                    for suggestion in index_suggestions:
                        print(f"  • {suggestion}")
                else:
                    print("Table structure appears optimized")

            except Exception as e:
                logging.error(f"Error analyzing table {table}: {e}")
                print(f"Error analyzing table {table}: {e}")

        conn.close()
        print("\nTable structure optimization analysis completed.")

    except Exception as e:
        logging.error(f"Error in optimize_table_structure: {e}")
        print(f"An error occurred: {e}")
