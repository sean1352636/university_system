"""
Database Connection Manager for Authentication Module

Provides thread-safe database connection management with comprehensive
error handling, retry logic, and connection pooling to prevent locking
issues and ensure robust database operations.

Features:
- Thread-safe connection management with RLock
- Automatic retry logic with exponential backoff
- Comprehensive error handling for all SQLite error types
- Write-Ahead Logging (WAL) mode for better concurrency
- Connection statistics and monitoring
- Proper cleanup and resource management

Part of the authentication module refactoring to isolate database
connection concerns from business logic.
"""

import contextlib
import logging
from education_system.systems.university.infrastructure.database.db import sqlite3
import threading
import time
from typing import Dict, Any

from education_system.systems.university.infrastructure.exceptions import DatabaseError

__all__ = ['DatabaseConnectionManager']

logger = logging.getLogger(__name__)

class DatabaseConnectionManager:
    """Thread-safe database connection manager to prevent locking issues"""

    def __init__(self, db_path):
        """
        Initialize the database connection manager.

        Parameters
        ----------
        db_path : str
            Path to the SQLite database file
        """
        self.db_path = db_path
        self._lock = threading.RLock()
        self.connection_count = 0
        self.max_retries = 3
        self.retry_delay = 0.1

    @contextlib.contextmanager
    def get_connection(self):
        """
        Context manager for database connections with comprehensive error handling.

        Provides a database connection within a context manager that handles:
        - Lock acquisition with timeout protection
        - Connection retry logic with exponential backoff
        - Automatic configuration of SQLite pragmas
        - Comprehensive error handling and logging
        - Proper cleanup of resources

        Yields
        ------
        sqlite3.Connection
            A configured database connection

        Raises
        ------
        DatabaseError
            If lock acquisition times out
        sqlite3.OperationalError
            For operational database errors (locked, I/O, etc.)
        sqlite3.DatabaseError
            For general database errors
        sqlite3.Error
            For other SQLite errors

        Examples
        --------
        >>> manager = DatabaseConnectionManager('path/to/db.db')
        >>> with manager.get_connection() as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM users")
        ...     results = cursor.fetchall()
        """
        conn = None
        connection_acquired = False
        lock_acquired = False

        try:
            # Acquire lock with timeout protection
            lock_acquired = self._lock.acquire(timeout=30.0)
            if not lock_acquired:
                raise DatabaseError(
                    "Failed to acquire database lock within timeout period",
                    code="DB_LOCK_TIMEOUT"
                )

            # Track connection attempts for monitoring
            self.connection_count += 1
            connection_id = self.connection_count

            # Attempt to establish database connection with retry logic
            conn = self._establish_connection_with_retry(connection_id)
            connection_acquired = True

            # Configure connection for optimal performance and concurrency
            self._configure_connection(conn, connection_id)

            # Yield the connection to the calling code
            logging.debug(f"Database connection #{connection_id} established successfully")
            yield conn

        except sqlite3.OperationalError as e:
            self._handle_operational_error(e, connection_id if 'connection_id' in locals() else 'unknown')
            if conn:
                self._safe_rollback(conn, connection_id if 'connection_id' in locals() else 'unknown')
            raise e

        except sqlite3.DatabaseError as e:
            self._handle_database_error(e, connection_id if 'connection_id' in locals() else 'unknown')
            if conn:
                self._safe_rollback(conn, connection_id if 'connection_id' in locals() else 'unknown')
            raise e

        except sqlite3.Error as e:
            self._handle_sqlite_error(e, connection_id if 'connection_id' in locals() else 'unknown')
            if conn:
                self._safe_rollback(conn, connection_id if 'connection_id' in locals() else 'unknown')
            raise e

        except Exception as e:
            self._handle_unexpected_error(e, connection_id if 'connection_id' in locals() else 'unknown')
            if conn:
                self._safe_rollback(conn, connection_id if 'connection_id' in locals() else 'unknown')
            raise e

        finally:
            # Comprehensive cleanup with detailed error handling
            self._cleanup_connection(conn, connection_acquired, lock_acquired,
                                   connection_id if 'connection_id' in locals() else 'unknown')

    def _establish_connection_with_retry(self, connection_id):
        """
        Establish database connection with retry logic.

        Attempts to connect to the database with exponential backoff
        retry strategy for transient errors like database locks.

        Parameters
        ----------
        connection_id : int
            Unique identifier for this connection attempt

        Returns
        -------
        sqlite3.Connection
            Established database connection

        Raises
        ------
        sqlite3.OperationalError
            If connection fails after all retries
        DatabaseError
            If all retry attempts are exhausted
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                logging.debug(f"Connection #{connection_id} established on attempt {attempt + 1}")
                return conn

            except sqlite3.OperationalError as e:
                last_error = e
                if "database is locked" in str(e).lower() and attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(f"Database locked on attempt {attempt + 1}, retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e

            except sqlite3.Error as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logging.warning(f"Database error on attempt {attempt + 1}, retrying in {wait_time:.2f}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e

        # If we get here, all retries failed
        raise last_error or DatabaseError(
            "Failed to establish database connection after all retries",
            code="DB_CONNECTION_FAILED"
        )

    def _configure_connection(self, conn, connection_id):
        """
        Configure database connection for optimal performance.

        Sets SQLite pragmas for improved concurrency, performance,
        and safety including WAL mode, timeouts, and caching.

        Parameters
        ----------
        conn : sqlite3.Connection
            Database connection to configure
        connection_id : int
            Connection identifier for logging
        """
        try:
            # Set timeout and concurrency settings
            conn.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout
            conn.execute("PRAGMA journal_mode = WAL")    # Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA synchronous = NORMAL")  # Balance safety and performance
            conn.execute("PRAGMA foreign_keys = ON")     # Enable foreign key constraints
            conn.execute("PRAGMA temp_store = MEMORY")   # Store temp tables in memory
            conn.execute("PRAGMA cache_size = 10000")    # Increase cache size

            logging.debug(f"Connection #{connection_id} configured successfully")

        except sqlite3.Error as e:
            logging.warning(f"Failed to configure connection #{connection_id}: {e}")
            # Don't raise here as the connection might still be usable

    def _create_configured_connection(self):
        """
        Create a new database connection with proper PRAGMA settings.

        Use this instead of direct sqlite3.connect() to ensure consistent
        timeout and concurrency settings across all database operations.

        Returns
        -------
        sqlite3.Connection
            Configured database connection
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as e:
            logging.warning(f"Failed to configure connection: {e}")
        return conn

    def _safe_rollback(self, conn, connection_id):
        """
        Safely rollback transaction with proper error handling.

        Parameters
        ----------
        conn : sqlite3.Connection or None
            Connection to rollback (may be None)
        connection_id : str or int
            Connection identifier for logging
        """
        if not conn:
            return

        try:
            conn.rollback()
            logging.debug(f"Transaction rolled back successfully for connection #{connection_id}")

        except sqlite3.OperationalError as e:
            if "no transaction is active" in str(e).lower():
                logging.debug(f"No active transaction to rollback for connection #{connection_id}")
            else:
                logging.warning(f"Operational error during rollback for connection #{connection_id}: {e}")

        except sqlite3.Error as e:
            logging.error(f"Database error during rollback for connection #{connection_id}: {e}")

        except Exception as e:
            logging.error(f"Unexpected error during rollback for connection #{connection_id}: {type(e).__name__}: {e}")

    def _cleanup_connection(self, conn, connection_acquired, lock_acquired, connection_id):
        """
        Comprehensive connection cleanup with detailed error handling.

        Parameters
        ----------
        conn : sqlite3.Connection or None
            Connection to close
        connection_acquired : bool
            Whether connection was successfully acquired
        lock_acquired : bool
            Whether thread lock was acquired
        connection_id : str or int
            Connection identifier for logging
        """
        cleanup_errors = []

        # Close database connection if it was established
        if conn and connection_acquired:
            try:
                # Check if connection is still valid before closing
                conn.execute("SELECT 1")  # Simple query to test connection
                conn.close()
                logging.debug(f"Connection #{connection_id} closed successfully")

            except sqlite3.ProgrammingError as e:
                if "cannot operate on a closed database" in str(e).lower():
                    logging.debug(f"Connection #{connection_id} was already closed")
                else:
                    cleanup_errors.append(f"Programming error during close: {e}")
                    logging.warning(f"Programming error closing connection #{connection_id}: {e}")

            except sqlite3.OperationalError as e:
                cleanup_errors.append(f"Operational error during close: {e}")
                logging.warning(f"Operational error closing connection #{connection_id}: {e}")

            except sqlite3.Error as e:
                cleanup_errors.append(f"Database error during close: {e}")
                logging.error(f"Database error closing connection #{connection_id}: {e}")

            except Exception as e:
                cleanup_errors.append(f"Unexpected error during close: {type(e).__name__}: {e}")
                logging.error(f"Unexpected error closing connection #{connection_id}: {type(e).__name__}: {e}")

        # Release the thread lock
        if lock_acquired:
            try:
                self._lock.release()
                logging.debug(f"Lock released successfully for connection #{connection_id}")

            except RuntimeError as e:
                cleanup_errors.append(f"Lock release error: {e}")
                logging.error(f"Error releasing lock for connection #{connection_id}: {e}")

            except Exception as e:
                cleanup_errors.append(f"Unexpected lock error: {type(e).__name__}: {e}")
                logging.error(f"Unexpected error releasing lock for connection #{connection_id}: {type(e).__name__}: {e}")

        # Log cleanup summary if there were any issues
        if cleanup_errors:
            logging.warning(f"Connection #{connection_id} cleanup completed with {len(cleanup_errors)} issues: {'; '.join(cleanup_errors)}")
        else:
            logging.debug(f"Connection #{connection_id} cleanup completed successfully")

    def _handle_operational_error(self, error, connection_id):
        """
        Handle SQLite operational errors with specific categorization.

        Parameters
        ----------
        error : sqlite3.OperationalError
            The operational error to handle
        connection_id : str or int
            Connection identifier for logging
        """
        error_msg = str(error).lower()

        if "database is locked" in error_msg:
            logging.warning(f"Database lock detected for connection #{connection_id}: {error}")
        elif "disk i/o error" in error_msg:
            logging.error(f"Disk I/O error for connection #{connection_id}: {error}")
        elif "database disk image is malformed" in error_msg:
            logging.critical(f"Database corruption detected for connection #{connection_id}: {error}")
        elif "no such table" in error_msg:
            logging.error(f"Table not found for connection #{connection_id}: {error}")
        elif "permission denied" in error_msg:
            logging.error(f"Permission denied for connection #{connection_id}: {error}")
        else:
            logging.error(f"Operational error for connection #{connection_id}: {error}")

    def _handle_database_error(self, error, connection_id):
        """
        Handle SQLite database errors.

        Parameters
        ----------
        error : sqlite3.DatabaseError
            The database error to handle
        connection_id : str or int
            Connection identifier for logging
        """
        logging.error(f"Database error for connection #{connection_id}: {error}")

    def _handle_sqlite_error(self, error, connection_id):
        """
        Handle general SQLite errors.

        Parameters
        ----------
        error : sqlite3.Error
            The SQLite error to handle
        connection_id : str or int
            Connection identifier for logging
        """
        logging.error(f"SQLite error for connection #{connection_id}: {error}")

    def _handle_unexpected_error(self, error, connection_id):
        """
        Handle unexpected non-SQLite errors.

        Parameters
        ----------
        error : Exception
            The unexpected error to handle
        connection_id : str or int
            Connection identifier for logging
        """
        logging.error(f"Unexpected error for connection #{connection_id}: {type(error).__name__}: {error}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about database connections for monitoring.

        Returns
        -------
        dict
            Connection statistics including total connections,
            database path, retry configuration, and lock status
        """
        return {
            'total_connections': self.connection_count,
            'db_path': self.db_path,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'lock_acquired': self._lock._count > 0 if hasattr(self._lock, '_count') else 'unknown'
        }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test database connectivity and return status.

        Returns
        -------
        dict
            Test result containing status, message, and optional
            error information
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return {
                    'status': 'success',
                    'message': 'Database connection test successful',
                    'result': result[0] if result else None
                }

        except sqlite3.Error as e:
            return {
                'status': 'error',
                'message': f'Database connection test failed: {e}',
                'error_type': type(e).__name__
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Unexpected error during connection test: {e}',
                'error_type': type(e).__name__
            }
