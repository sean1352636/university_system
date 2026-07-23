"""Database utilities re-exported from email infrastructure for backward compatibility."""

from __future__ import annotations

import threading
from pathlib import Path

# Import from the actual location
from education_system.post_18.university_system.infrastructure.email.email_db_utilities import (
    ensure_db_directory,
    ensure_parent_dir,
)

# Also make these available
from education_system.post_18.university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH
from education_system.post_18.university_system.core import paths

# Database management variables - Thread-safe using locks
_DB_READY = False
_DB_READY_LOCK = threading.Lock()  # Protect _DB_READY flag
USE_AUTH_DB = True
MAIN_DIR = str(paths.DATA_DIR)  # Use DATA_DIR instead of MAIN_DIR
PROJECT_ROOT = str(Path(__file__).parent.parent.parent.parent)  # Calculate from file location
DB_PATH = DEFAULT_DB_PATH
_db_manager = None
_db_manager_lock = threading.Lock()

def _ensure_db_ready():
    """
    Ensure database is ready (thread-safe).

    Uses double-checked locking pattern to minimize lock contention
    while ensuring thread-safe initialization.
    """
    global _DB_READY

    # First check without lock (fast path)
    if _DB_READY:
        return True

    # Acquire lock for initialization
    with _DB_READY_LOCK:
        # Double-check inside lock (slow path)
        if not _DB_READY:
            ensure_db_directory()
            _DB_READY = True
        return _DB_READY

def get_unified_connection():
    """
    Get a unified database connection with automatic initialization.

    Returns a database connection from the centralized database layer,
    ensuring the database directory and schema are initialized before
    returning the connection.

    Returns
    -------
    sqlite3.Connection
        A configured database connection with Row factory enabled.

    Examples
    --------
    >>> conn = get_unified_connection()
    >>> cursor = conn.cursor()
    >>> cursor.execute("SELECT COUNT(*) FROM users")
    >>> print(cursor.fetchone()[0])
    42
    >>> conn.close()

    Notes
    -----
    This function is thread-safe due to internal locking during
    initialization. Prefer using context managers or the transaction()
    function from the database module for write operations.

    See Also
    --------
    get_connection : Lower-level connection function.
    transaction : Context manager for transactional operations.
    """
    _ensure_db_ready()
    return get_connection()

class SimpleDBManager:
    """Simple database manager for backward compatibility"""
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH
        _ensure_db_ready()

    def get_connection(self):
        return get_connection()

def get_db_manager():
    """Get database manager instance"""
    global _db_manager
    with _db_manager_lock:
        if _db_manager is None:
            _db_manager = SimpleDBManager()
        return _db_manager

def execute_db_operation(operation, *args, **kwargs):
    """
    Execute a database operation with automatic connection and error handling.

    Provides a safe wrapper for database operations that handles connection
    lifecycle and error handling. Opens a connection, executes the operation,
    and closes the connection regardless of success or failure.

    Parameters
    ----------
    operation : Callable
        A function that takes a sqlite3.Connection as its first argument
        and performs database operations.
    *args : Any
        Additional positional arguments to pass to the operation function.
    **kwargs : Any
        Additional keyword arguments to pass to the operation function.

    Returns
    -------
    Any or None
        The return value of the operation function, or None if an error occurred.

    Examples
    --------
    >>> def count_users(conn):
    ...     cursor = conn.cursor()
    ...     cursor.execute("SELECT COUNT(*) FROM users")
    ...     return cursor.fetchone()[0]
    ...
    >>> user_count = execute_db_operation(count_users)
    >>> print(f"Total users: {user_count}")
    Total users: 42

    >>> def insert_record(conn, table, data):
    ...     from education_system.post_18.university_system.core.sql_safety import validate_table_name
    ...     safe_table = validate_table_name(table)
    ...     cursor = conn.cursor()
    ...     cursor.execute("INSERT INTO [" + safe_table + "] VALUES (?)", (data,))
    ...     conn.commit()
    ...     return cursor.lastrowid
    ...
    >>> record_id = execute_db_operation(insert_record, "logs", "test")

    Notes
    -----
    This function does NOT use transactions. For operations requiring
    ACID guarantees, use the transaction() context manager instead.
    Errors are logged to stdout and None is returned on failure.

    See Also
    --------
    safe_db_operation : Decorator version for wrapping functions.
    transaction : Context manager for transactional operations.
    """
    try:
        conn = get_connection()
        result = operation(conn, *args, **kwargs)
        conn.close()
        return result
    except Exception as e:
        print(f"Database operation error: {e}")
        return None

def safe_db_operation(func):
    """
    Decorator that wraps a function with database error handling.

    Catches any exceptions raised by the decorated function and returns
    None instead of propagating the error. Useful for database operations
    where failure should not crash the application.

    Parameters
    ----------
    func : Callable
        The function to wrap with error handling.

    Returns
    -------
    Callable
        Wrapped function that returns None on error.

    Examples
    --------
    >>> @safe_db_operation
    ... def get_user_by_id(user_id):
    ...     conn = get_connection()
    ...     cursor = conn.cursor()
    ...     cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    ...     return cursor.fetchone()
    ...
    >>> user = get_user_by_id(123)  # Returns None if error occurs
    >>> if user:
    ...     print(f"Found user: {user['name']}")

    Notes
    -----
    This decorator silently catches ALL exceptions, which may hide bugs.
    For production code, consider more specific error handling or using
    the transaction() context manager which provides better control.

    Errors are logged to stdout with the function name for debugging.

    See Also
    --------
    execute_db_operation : Functional approach with connection handling.
    transaction : Recommended approach for write operations.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Database error in {func.__name__}: {e}")
            return None
    return wrapper

def initialize_email_db():
    """Initialize email database tables"""
    _ensure_db_ready()
    return True

def migrate_email_log_table():
    """Migrate email log table"""
    return True

def schedule_database_maintenance(interval_hours: int = 24, run_immediately: bool = False):
    """
    Schedule database maintenance

    Schedules periodic database maintenance operations including:
    - VACUUM to reclaim space and defragment
    - ANALYZE to update query planner statistics
    - Integrity check to detect corruption
    - WAL checkpoint to manage write-ahead log

    Args:
        interval_hours: Hours between maintenance runs (default: 24)
        run_immediately: If True, run maintenance immediately before scheduling

    Returns:
        threading.Timer: Timer object for scheduled maintenance (can be cancelled)

    Note:
        This uses threading.Timer for scheduling. For production systems,
        consider using a proper task scheduler (cron, systemd timer, etc.)
    """
    import threading
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3
    def run_maintenance():
        """Execute database maintenance operations"""
        try:
            _ensure_db_ready()
            conn = get_connection()
            cursor = conn.cursor()

            print(f"[{threading.current_thread().name}] Starting database maintenance...")

            # 1. ANALYZE - Update statistics for query optimizer
            try:
                cursor.execute("ANALYZE")
                print("  ✓ Statistics updated (ANALYZE)")
            except sqlite3.Error as e:
                print(f"  ✗ ANALYZE failed: {e}")

            # 2. Integrity check
            try:
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                if result and result[0] == 'ok':
                    print("  ✓ Integrity check passed")
                else:
                    print(f"  ⚠ Integrity check: {result}")
            except sqlite3.Error as e:
                print(f"  ✗ Integrity check failed: {e}")

            # 3. WAL checkpoint (if in WAL mode)
            try:
                cursor.execute("PRAGMA journal_mode")
                mode = cursor.fetchone()
                if mode and mode[0].lower() == 'wal':
                    cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    print("  ✓ WAL checkpoint completed")
            except sqlite3.Error as e:
                print(f"  ✗ WAL checkpoint failed: {e}")

            # 4. VACUUM - Reclaim space (only if not in WAL mode during checkpoint)
            # Note: VACUUM cannot run inside a transaction
            try:
                conn.commit()  # Commit any pending transaction
                conn.isolation_level = None  # Autocommit mode for VACUUM
                cursor.execute("VACUUM")
                print("  ✓ Database vacuumed")
                conn.isolation_level = ''  # Restore default mode
            except sqlite3.Error as e:
                print(f"  ✗ VACUUM failed: {e}")
                conn.isolation_level = ''  # Restore even on error

            conn.close()
            print("  Database maintenance completed successfully")

        except Exception as e:
            print(f"  Database maintenance error: {e}")

        # Schedule next maintenance
        timer = threading.Timer(interval_hours * 3600, run_maintenance)
        timer.daemon = True
        timer.name = "DatabaseMaintenanceTimer"
        timer.start()
        print(f"  Next maintenance scheduled in {interval_hours} hours")

    # Run immediately if requested
    if run_immediately:
        run_maintenance()
        return None  # Already scheduled next run inside run_maintenance

    # Otherwise schedule first run
    timer = threading.Timer(interval_hours * 3600, run_maintenance)
    timer.daemon = True
    timer.name = "DatabaseMaintenanceTimer"
    timer.start()
    print(f"Database maintenance scheduled every {interval_hours} hours")
    return timer

def optimize_database():
    """Optimize database"""
    _ensure_db_ready()

__all__ = [
    '_DB_READY',
    'USE_AUTH_DB',
    'MAIN_DIR',
    'PROJECT_ROOT',
    'DB_PATH',
    '_db_manager',
    '_db_manager_lock',
    '_ensure_db_ready',
    'ensure_db_directory',
    'ensure_parent_dir',
    'get_unified_connection',
    'SimpleDBManager',
    'get_db_manager',
    'execute_db_operation',
    'safe_db_operation',
    'initialize_email_db',
    'migrate_email_log_table',
    'schedule_database_maintenance',
    'optimize_database',
]
