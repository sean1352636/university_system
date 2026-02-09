"""Centralised database utilities for the program application.

This module wraps Python's built-in :mod:`sqlite3` module and ensures
every subsystem connects to the same database file located under
``program/data/db_files``.
"""

from __future__ import annotations

import logging
import os
import sqlite3 as _sqlite3
import time
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Optional

# Import from core package - no circular imports!
from university_system.core.paths import DB_DIR, DB_EXPORTS_DIR, DEFAULT_DB_PATH
from university_system.core.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    TransactionError
)

# Import database constants normally (within same package)
from university_system.infrastructure.database.constants import (
    DEFAULT_DB_TIMEOUT,
    SQLITE_BUSY_TIMEOUT,
    PRAGMA_FOREIGN_KEYS,
    PRAGMA_JOURNAL_MODE,
    PRAGMA_SYNCHRONOUS,
    MAX_POOL_CONNECTIONS,
    MIN_POOL_CONNECTIONS,
    POOL_TIMEOUT,
    MAX_CONNECTION_AGE,
    POOL_CLEANUP_INTERVAL
)

# Convert Path objects to strings for os operations
DB_DIR = os.fspath(DB_DIR)
EXPORTS_DIR = os.fspath(DB_EXPORTS_DIR)
DEFAULT_DB_PATH = os.fspath(DEFAULT_DB_PATH)

os.makedirs(EXPORTS_DIR, exist_ok=True)

DEFAULT_DB_NAME = os.path.basename(DEFAULT_DB_PATH)

logger = logging.getLogger(__name__)


def _apply_pragmas(conn: _sqlite3.Connection) -> None:
    """Apply standard PRAGMA settings to a database connection.

    This centralizes all PRAGMA configuration to ensure consistency
    across all connection methods (connect, get_connection, ConnectionPool).

    Args:
        conn: SQLite connection to configure
    """
    pragmas = [
        f"PRAGMA foreign_keys={PRAGMA_FOREIGN_KEYS}",
        f"PRAGMA journal_mode={PRAGMA_JOURNAL_MODE}",
        f"PRAGMA synchronous={PRAGMA_SYNCHRONOUS}",
        f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT}",
    ]
    try:
        for pragma in pragmas:
            conn.execute(pragma)
        logger.debug("Applied %d PRAGMA settings", len(pragmas))
    except _sqlite3.OperationalError as e:
        logger.warning(f"Failed to set database PRAGMA settings: {e}")
        # Continue with connection even if PRAGMA fails


def ensure_parent_dir(path: str) -> None:
    """
    Ensure the parent directory of given path exists.
    Used when a user supplies a custom database path outside the default.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


# ---------------------------------------------------------------------------
# sqlite3 wrapper

def connect(database: Optional[str | os.PathLike[str]] = None, *args: Any, **kwargs: Any) -> _sqlite3.Connection:
    """
    Create and configure a new SQLite database connection with PRAGMA settings.

    This is a low-level wrapper around sqlite3.connect() that automatically
    applies performance and safety PRAGMA settings (WAL mode, foreign keys, etc.).
    For most use cases, prefer get_connection() or transaction() instead.

    Parameters
    ----------
    database : str or os.PathLike or None, optional
        Path to the database file. If None or equals DEFAULT_DB_NAME,
        uses DEFAULT_DB_PATH (data/db_files/student_records.db).
    *args : Any
        Additional positional arguments passed to sqlite3.connect().
    **kwargs : Any
        Additional keyword arguments passed to sqlite3.connect().
        If 'timeout' is not specified, defaults to DEFAULT_DB_TIMEOUT.

    Returns
    -------
    sqlite3.Connection
        A configured database connection with PRAGMA settings applied.

    Examples
    --------
    >>> conn = connect()
    >>> conn.execute("SELECT 1").fetchone()
    (1,)
    >>> conn.close()

    >>> conn = connect("/custom/path/db.sqlite", isolation_level=None)
    >>> # ... use connection
    >>> conn.close()

    See Also
    --------
    get_connection : Higher-level connection function with Row factory support.
    transaction : Context manager for transactional operations.
    """
    db = database
    if db is None or os.fspath(db) == DEFAULT_DB_NAME:
        db = DEFAULT_DB_PATH
    kwargs.setdefault("timeout", DEFAULT_DB_TIMEOUT)
    conn = _sqlite3.connect(db, *args, **kwargs)
    _apply_pragmas(conn)
    return conn

def get_connection(
    db_path: Optional[str | os.PathLike[str]] = None,
    row_factory: bool = True,
    timeout: float = DEFAULT_DB_TIMEOUT,
) -> _sqlite3.Connection:
    """
    Get a database connection with optional Row factory and configurable timeout.

    This is the primary function for obtaining database connections in the
    application. It automatically applies PRAGMA settings for performance
    and optionally enables sqlite3.Row factory for dict-like row access.

    Parameters
    ----------
    db_path : str or os.PathLike or None, optional
        Path to the database file. If None or equals DEFAULT_DB_NAME,
        uses DEFAULT_DB_PATH (data/db_files/student_records.db).
    row_factory : bool, default=True
        If True, sets connection.row_factory to sqlite3.Row, allowing
        column access by name (e.g., row['column_name']).
    timeout : float, default=DEFAULT_DB_TIMEOUT
        Database lock timeout in seconds. Operations will wait this long
        before raising sqlite3.OperationalError if the database is locked.

    Returns
    -------
    sqlite3.Connection
        A configured database connection ready for use.

    Raises
    ------
    sqlite3.OperationalError
        If unable to connect to database or timeout is exceeded.

    Examples
    --------
    >>> with get_connection() as conn:
    ...     result = conn.execute("SELECT * FROM students LIMIT 1").fetchone()
    ...     print(result['name'])  # Row factory enables dict-like access
    'John Doe'

    >>> # Without row factory (tuple results)
    >>> conn = get_connection(row_factory=False)
    >>> result = conn.execute("SELECT id, name FROM students").fetchone()
    >>> print(result[0], result[1])  # Access by index only
    1 John Doe
    >>> conn.close()

    Notes
    -----
    Always close connections when done, preferably using context managers
    or the transaction() function for write operations.

    See Also
    --------
    transaction : Context manager for transactional write operations.
    get_connection_pool : For high-concurrency scenarios with connection reuse.
    """
    target = DEFAULT_DB_PATH if (db_path is None or os.fspath(db_path) == DEFAULT_DB_NAME) else db_path
    db = os.fspath(target)
    conn = _sqlite3.connect(db, timeout=timeout)
    _apply_pragmas(conn)
    if row_factory:
        conn.row_factory = _sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Connection Pooling
# ---------------------------------------------------------------------------

import threading
import queue
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class PooledConnection:
    """Wrapper for a pooled database connection with metadata."""
    connection: _sqlite3.Connection
    created_at: datetime
    last_used: datetime
    in_use: bool = False


class ConnectionPool:
    """
    Thread-safe connection pool for SQLite database connections.

    Uses thread-local storage to ensure each thread gets its own connection,
    maintaining SQLite's thread safety guarantees (check_same_thread=True).
    This prevents potential data corruption from cross-thread connection sharing.

    Provides connection reuse to improve performance and reduce overhead
    of creating new connections. Automatically manages connection lifecycle,
    including cleanup of old or idle connections.

    Example:
        >>> pool = ConnectionPool(db_path="/path/to/db.sqlite")
        >>> conn = pool.get_connection()
        >>> try:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM users")
        ...     results = cursor.fetchall()
        ... finally:
        ...     pool.release_connection(conn)

        >>> # Or use context manager (recommended)
        >>> with pool.get_connection_context() as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM users")
        ...     results = cursor.fetchall()

    Thread Safety:
        Each thread receives its own dedicated connection via thread-local storage.
        Connections are never shared between threads, ensuring SQLite's thread
        safety model is respected.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        max_connections: int = MAX_POOL_CONNECTIONS,
        min_connections: int = MIN_POOL_CONNECTIONS,
        max_connection_age: int = MAX_CONNECTION_AGE,
        timeout: float = POOL_TIMEOUT,
        row_factory: bool = True,
    ):
        """
        Initialize connection pool.

        Args:
            db_path: Path to database file (uses default if None)
            max_connections: Maximum number of connections in pool
            min_connections: Minimum number of connections to keep alive
            max_connection_age: Maximum age of connection in seconds before refresh
            timeout: Timeout for getting connection from pool
            row_factory: Whether to use Row factory for results
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.max_connection_age = max_connection_age
        self.timeout = timeout
        self.row_factory = row_factory

        # Thread-local storage for per-thread connections
        # This ensures each thread has its own connection (thread safety)
        self._local = threading.local()

        # Track all thread connections for cleanup
        self._thread_connections: dict[int, PooledConnection] = {}
        self._thread_connections_lock = threading.Lock()

        # Thread-safe pool management (for non-thread-local fallback pool)
        self._pool: list[PooledConnection] = []
        self._pool_lock = threading.RLock()  # Reentrant lock for nested operations
        self._connection_semaphore = threading.Semaphore(max_connections)

        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

        # Initialize minimum connections (pre-warm for main thread)
        self._initialize_pool()

        # Start cleanup thread
        self._start_cleanup_thread()

        logging.info(f"ConnectionPool initialized: {min_connections}-{max_connections} connections (thread-safe)")

    def _initialize_pool(self) -> None:
        """Initialize pool - creates connection for current thread only.

        With thread-local storage, we don't pre-create connections for other threads.
        Each thread will get its own connection on first request.
        This initialization creates a connection for the main/startup thread.
        """
        try:
            # Create a connection for the current (main) thread
            # This validates the database path and warms up the pool
            conn = self._create_connection()
            logging.debug(f"Pool initialized with connection for main thread {threading.get_ident()}")
        except Exception as e:
            logging.error(f"Failed to create initial connection: {e}")
            raise DatabaseConnectionError(
                f"Failed to initialize connection pool: {e}",
                code="DB_POOL_INIT_FAILED",
                details={'db_path': self.db_path}
            )

    def _create_connection(self) -> _sqlite3.Connection:
        """Create a new database connection with proper thread safety.

        Uses thread-local storage to ensure each thread has its own connection.
        This maintains SQLite's thread safety guarantees by keeping
        check_same_thread=True (the default).

        Returns:
            sqlite3.Connection: A thread-safe database connection for the current thread.
        """
        thread_id = threading.get_ident()

        # Check if this thread already has a connection in thread-local storage
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            # Verify the existing connection is still valid
            try:
                self._local.connection.execute("SELECT 1")
                return self._local.connection
            except Exception:
                # Connection is stale, close it and create a new one
                try:
                    self._local.connection.close()
                except Exception:
                    pass
                self._local.connection = None

        # Create connection FOR THIS THREAD ONLY with check_same_thread=True (default)
        # This ensures SQLite's thread safety is maintained
        conn = _sqlite3.connect(
            self.db_path,
            timeout=DEFAULT_DB_TIMEOUT,
            check_same_thread=True  # SECURITY: Keep thread safety enabled
        )

        # Configure connection with standard PRAGMA settings
        _apply_pragmas(conn)

        if self.row_factory:
            conn.row_factory = _sqlite3.Row

        # Store in thread-local storage
        self._local.connection = conn

        # Track for cleanup across all threads
        with self._thread_connections_lock:
            # Clean up any previous connection for this thread
            if thread_id in self._thread_connections:
                old_pooled = self._thread_connections[thread_id]
                try:
                    old_pooled.connection.close()
                except Exception:
                    pass

            self._thread_connections[thread_id] = PooledConnection(
                connection=conn,
                created_at=datetime.now(),
                last_used=datetime.now(),
                in_use=True,
            )

        logging.debug(f"Created thread-local connection for thread {thread_id}")
        return conn

    def get_connection(self, timeout: Optional[float] = None) -> _sqlite3.Connection:
        """
        Get a thread-safe connection from the pool.

        Each thread receives its own dedicated connection via thread-local storage,
        ensuring SQLite's thread safety model is respected.

        Args:
            timeout: Override default timeout for getting connection

        Returns:
            Database connection for the current thread

        Raises:
            DatabaseConnectionError: If connection cannot be acquired within timeout
        """
        timeout = timeout or self.timeout
        thread_id = threading.get_ident()

        # Check for existing thread-local connection first
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            # Update last_used timestamp
            with self._thread_connections_lock:
                if thread_id in self._thread_connections:
                    pooled = self._thread_connections[thread_id]
                    # Check if connection is still valid
                    if self._is_connection_valid(pooled):
                        pooled.last_used = datetime.now()
                        pooled.in_use = True
                        logging.debug(f"Reusing thread-local connection for thread {thread_id}")
                        return pooled.connection

            # Connection is stale, clear it
            try:
                self._local.connection.close()
            except Exception:
                pass
            self._local.connection = None

        # Wait for available slot in semaphore (limits total connections)
        if not self._connection_semaphore.acquire(timeout=timeout):
            raise DatabaseConnectionError(
                f"Could not acquire connection within {timeout}s",
                code="DB_CONNECTION_TIMEOUT",
                details={'timeout': timeout, 'thread_id': thread_id}
            )

        try:
            # Create new thread-local connection
            conn = self._create_connection()
            logging.debug(f"Created new thread-local connection for thread {thread_id}")
            return conn

        except Exception:
            # Release semaphore if we failed to get connection
            self._connection_semaphore.release()
            raise

    def release_connection(self, conn: _sqlite3.Connection) -> None:
        """
        Release a connection back to the pool.

        For thread-local connections, marks the connection as not in use
        but keeps it available for the same thread to reuse.

        Args:
            conn: Connection to release
        """
        thread_id = threading.get_ident()

        # Check thread-local connections first
        with self._thread_connections_lock:
            if thread_id in self._thread_connections:
                pooled = self._thread_connections[thread_id]
                if pooled.connection is conn:
                    pooled.in_use = False
                    pooled.last_used = datetime.now()
                    self._connection_semaphore.release()
                    logging.debug(f"Released thread-local connection for thread {thread_id}")
                    return

        # Fallback: Check legacy pool (for backwards compatibility)
        with self._pool_lock:
            for pooled in self._pool:
                if pooled.connection is conn:
                    pooled.in_use = False
                    pooled.last_used = datetime.now()
                    self._connection_semaphore.release()
                    logging.debug(f"Released connection back to pool")
                    return

            # Connection not found - release semaphore anyway to prevent deadlock
            logging.warning(f"Attempted to release unknown connection from thread {thread_id}")
            self._connection_semaphore.release()

    def _is_connection_valid(self, pooled: PooledConnection) -> bool:
        """
        Check if a pooled connection is still valid.

        Args:
            pooled: Pooled connection to check

        Returns:
            True if connection is valid, False otherwise
        """
        # Check age
        age = (datetime.now() - pooled.created_at).total_seconds()
        if age > self.max_connection_age:
            logging.debug(f"Connection too old ({age}s), will refresh")
            return False

        # Try to execute simple query to verify connection
        try:
            pooled.connection.execute("SELECT 1")
            return True
        except Exception as e:
            logging.warning(f"Connection validation failed: {e}")
            return False

    def _remove_connection(self, pooled: PooledConnection) -> None:
        """
        Remove a connection from the pool and close it.

        Args:
            pooled: Pooled connection to remove
        """
        try:
            pooled.connection.close()
        except Exception as e:
            logging.error(f"Error closing connection: {e}")

        if pooled in self._pool:
            self._pool.remove(pooled)
            logging.debug(f"Removed connection from pool (pool size: {len(self._pool)})")

    def _cleanup_old_connections(self) -> None:
        """Remove old or idle connections from pool and thread-local storage."""
        current_time = datetime.now()
        cleaned_count = 0

        # Clean up thread-local connections
        with self._thread_connections_lock:
            thread_ids_to_remove = []

            for thread_id, pooled in self._thread_connections.items():
                # Skip connections currently in use
                if pooled.in_use:
                    continue

                # Check if connection is too old
                age = (current_time - pooled.created_at).total_seconds()
                if age > self.max_connection_age:
                    thread_ids_to_remove.append(thread_id)

            # Remove old thread connections
            for thread_id in thread_ids_to_remove:
                pooled = self._thread_connections.pop(thread_id, None)
                if pooled:
                    try:
                        pooled.connection.close()
                        cleaned_count += 1
                    except Exception as e:
                        logging.error(f"Error closing thread connection: {e}")

        # Clean up legacy pool connections
        with self._pool_lock:
            connections_to_remove = []

            for pooled in self._pool:
                # Don't remove if we're at minimum and it's not in use
                if len(self._pool) - len(connections_to_remove) <= self.min_connections:
                    break

                # Skip connections currently in use
                if pooled.in_use:
                    continue

                # Check if connection is too old
                age = (current_time - pooled.created_at).total_seconds()
                if age > self.max_connection_age:
                    connections_to_remove.append(pooled)

            # Remove old connections
            for pooled in connections_to_remove:
                self._remove_connection(pooled)
                cleaned_count += 1

        if cleaned_count > 0:
            logging.info(f"Cleaned up {cleaned_count} old connections")

    def _cleanup_loop(self) -> None:
        """Background thread that periodically cleans up old connections."""
        while not self._stop_cleanup.wait(timeout=POOL_CLEANUP_INTERVAL):
            try:
                self._cleanup_old_connections()
            except Exception as e:
                logging.error(f"Error in connection pool cleanup: {e}")

    def _start_cleanup_thread(self) -> None:
        """Start background cleanup thread."""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="ConnectionPoolCleanup"
        )
        self._cleanup_thread.start()

    def close_all(self) -> None:
        """Close all connections in pool (both thread-local and legacy) and stop cleanup thread."""
        # Stop cleanup thread
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)

        # Close all thread-local connections
        with self._thread_connections_lock:
            for thread_id, pooled in list(self._thread_connections.items()):
                try:
                    pooled.connection.close()
                except Exception as e:
                    logging.error(f"Error closing thread {thread_id} connection: {e}")
            self._thread_connections.clear()

        # Close all legacy pool connections
        with self._pool_lock:
            for pooled in self._pool[:]:  # Copy list to avoid modification during iteration
                self._remove_connection(pooled)

        logging.info("Connection pool closed (all thread-local and pooled connections)")

    @contextmanager
    def get_connection_context(
        self, timeout: Optional[float] = None
    ) -> Generator[_sqlite3.Connection, None, None]:
        """
        Context manager for getting and releasing connections.

        Args:
            timeout: Override default timeout for getting connection

        Yields:
            Database connection from pool

        Example:
            >>> with pool.get_connection_context() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("SELECT * FROM users")
        """
        conn = self.get_connection(timeout=timeout)
        try:
            yield conn
        finally:
            self.release_connection(conn)

    def get_stats(self) -> dict:
        """
        Get connection pool statistics for monitoring.

        Returns:
            dict: Statistics including active connections, thread count, etc.
        """
        with self._thread_connections_lock:
            thread_conn_count = len(self._thread_connections)
            active_thread_conns = sum(1 for p in self._thread_connections.values() if p.in_use)

        with self._pool_lock:
            legacy_pool_count = len(self._pool)
            active_legacy_conns = sum(1 for p in self._pool if p.in_use)

        return {
            'thread_local_connections': thread_conn_count,
            'thread_local_active': active_thread_conns,
            'legacy_pool_connections': legacy_pool_count,
            'legacy_pool_active': active_legacy_conns,
            'total_connections': thread_conn_count + legacy_pool_count,
            'total_active': active_thread_conns + active_legacy_conns,
            'max_connections': self.max_connections,
            'db_path': self.db_path,
        }

    def __enter__(self) -> "ConnectionPool":
        """Support using pool itself as context manager."""
        return self

    def __exit__(
        self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Any
    ) -> bool:
        """Close pool when exiting context."""
        self.close_all()
        return False


# Global connection pool instance (lazy initialization)
_connection_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool(
    db_path: Optional[str] = None,
    max_connections: int = MAX_POOL_CONNECTIONS,
) -> ConnectionPool:
    """
    Get or create the global connection pool.

    Args:
        db_path: Path to database file (uses default if None)
        max_connections: Maximum number of connections in pool

    Returns:
        Global connection pool instance
    """
    global _connection_pool

    # Double-checked locking pattern
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = ConnectionPool(
                    db_path=db_path,
                    max_connections=max_connections,
                )

    return _connection_pool


# ---------------------------------------------------------------------------
# Transaction Management
# ---------------------------------------------------------------------------


@contextmanager
def transaction(
    db_path: Optional[str | os.PathLike[str]] = None, row_factory: bool = True
) -> Generator[_sqlite3.Connection, None, None]:
    """
    Context manager for database transactions with automatic commit/rollback.

    This provides proper transaction management with automatic commit on success
    and rollback on failure. It ensures ACID properties for database operations.

    Args:
        db_path: Path to database file (uses default if None)
        row_factory: Whether to use Row factory for results

    Yields:
        sqlite3.Connection: Database connection with transaction active

    Example:
        >>> with transaction() as conn:
        ...     conn.execute("INSERT INTO students VALUES (?, ?)", (1, "John"))
        ...     conn.execute("INSERT INTO enrollments VALUES (?, ?)", (1, 101))
        ...     # Both inserts committed atomically

        >>> try:
        ...     with transaction() as conn:
        ...         conn.execute("INSERT INTO students VALUES (?, ?)", (1, "John"))
        ...         raise ValueError("Something went wrong")
        ... except ValueError:
        ...     pass  # Transaction automatically rolled back

    Note:
        - Automatically begins transaction on enter
        - Commits on successful completion
        - Rolls back on any exception
        - Closes connection on exit
    """
    conn = get_connection(db_path=db_path, row_factory=row_factory)
    try:
        # Begin transaction explicitly with IMMEDIATE to acquire write lock upfront
        # This prevents database locked errors with concurrent access
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        # If we reach here, commit the transaction
        conn.commit()
        logging.debug("Transaction committed successfully")
    except Exception as e:
        # Rollback on any exception
        try:
            conn.rollback()
            logging.error(f"Transaction failed, rolling back: {e}")
        except Exception as rollback_error:
            logging.error(f"Rollback also failed: {rollback_error}")
        raise
    finally:
        # Always close the connection
        try:
            conn.close()
        except Exception as close_error:
            logging.error(f"Failed to close connection: {close_error}")


@contextmanager
def atomic_operation(
    conn: Optional[_sqlite3.Connection] = None,
    db_path: Optional[str | os.PathLike[str]] = None,
) -> Generator[_sqlite3.Connection, None, None]:
    """
    Context manager for atomic database operations.

    Similar to transaction() but can work with an existing connection or create a new one.
    Useful when you want to ensure atomicity for a block of operations within a larger function.

    Args:
        conn: Existing connection to use (creates new if None)
        db_path: Path to database file (ignored if conn provided)

    Yields:
        sqlite3.Connection: Database connection with transaction active

    Example:
        >>> conn = get_connection()
        >>> with atomic_operation(conn) as c:
        ...     c.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (100, 1))
        ...     c.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (100, 2))
        ...     # Both updates are atomic
        >>> conn.close()

    Note:
        - If conn is provided, does NOT close it on exit
        - If conn is None, creates and closes connection automatically
    """
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection(db_path=db_path)

    try:
        conn.execute("BEGIN TRANSACTION")
        yield conn
        conn.commit()
        logging.debug("Atomic operation committed successfully")
    except Exception as e:
        conn.rollback()
        logging.error(f"Atomic operation failed, rolling back: {e}")
        raise
    finally:
        if owns_connection:
            conn.close()



class _SQLiteProxy:
    """Proxy object that delegates attribute access to :mod:`sqlite3`.

    The proxy overrides the :func:`connect` attribute to call our
    custom :func:`connect` function defined above.  All other
    attributes and exceptions are forwarded to the underlying
    :mod:`sqlite3` module.  This allows existing code written against
    ``sqlite3`` to function unchanged when imported from this module.
    """

    def __getattr__(self, name: str) -> Any:
        if name == "connect":
            return connect
        return getattr(_sqlite3, name)


# Export a single proxy instance named ``sqlite3``.  Modules should
# import ``sqlite3`` from this module instead of the standard library.
sqlite3 = _SQLiteProxy()


# ---------------------------------------------------------------------------
# Database context manager

class DatabaseManager:
    """
    Context manager for SQLite database connections with retry and
    automatic transaction handling.

    Example usage::

        from university_system.infrastructure.database.db import DatabaseManager
        with DatabaseManager() as db:
            db.execute("SELECT * FROM students")
            rows = db.fetchall()

    The connection uses the project‑wide default database path unless
    another ``db_path`` is supplied.  If the database is locked, the
    manager will retry the connection a configurable number of times
    before raising the underlying exception.
    """

    def __init__(self, db_path: Optional[str] = None, max_retries: int = 5, retry_delay: float = 0.1) -> None:
        # Use the default database path if none is provided
        self.db_path = db_path or DEFAULT_DB_PATH
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.conn: Optional[_sqlite3.Connection] = None
        self.cursor: Optional[_sqlite3.Cursor] = None

    def __enter__(self) -> "DatabaseManager":
        for attempt in range(self.max_retries):
            try:
                self.conn = connect(self.db_path, timeout=10.0)
                # Set row_factory to sqlite3.Row so rows are dict‑like
                self.conn.row_factory = _sqlite3.Row
                self.cursor = self.conn.cursor()
                return self
            except _sqlite3.OperationalError as e:
                # Retry if the database is locked
                if "database is locked" in str(e) and attempt < self.max_retries - 1:
                    logging.warning(
                        f"Database locked, retrying in {self.retry_delay}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(self.retry_delay)
                    # Exponential backoff
                    self.retry_delay *= 2
                else:
                    # Re‑raise other operational errors
                    raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self.conn:
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
            finally:
                self.conn.close()
        # Do not suppress exceptions
        return False

    # Delegate common cursor methods for convenience
    def execute(self, query: str, params: Optional[Iterable[Any]] = None) -> _sqlite3.Cursor:
        if self.cursor is None:
            raise QueryError(
                "DatabaseManager has no active cursor",
                code="DB_NO_CURSOR",
                details={'query': query[:100]}  # First 100 chars of query
            )
        return self.cursor.execute(query, params or [])

    def executemany(self, query: str, params: Iterable[Iterable[Any]]) -> _sqlite3.Cursor:
        if self.cursor is None:
            raise QueryError(
                "DatabaseManager has no active cursor",
                code="DB_NO_CURSOR",
                details={'query': query[:100]}
            )
        return self.cursor.executemany(query, params)

    def fetchone(self) -> Optional[_sqlite3.Row]:
        if self.cursor is None:
            raise QueryError(
                "DatabaseManager has no active cursor",
                code="DB_NO_CURSOR"
            )
        return self.cursor.fetchone()

    def fetchall(self) -> list[_sqlite3.Row]:
        if self.cursor is None:
            raise QueryError(
                "DatabaseManager has no active cursor",
                code="DB_NO_CURSOR"
            )
        return self.cursor.fetchall()

# Alias for compatibility with GUI code
def get_db_connection(
    db_path: Optional[str | os.PathLike[str]] = None,
    row_factory: bool = True,
    timeout: float = 30.0,
) -> _sqlite3.Connection:
    """
    Get a database connection (alias for get_connection).

    This function exists for backward compatibility with legacy GUI code
    that uses the get_db_connection naming convention. New code should
    use get_connection() directly.

    Parameters
    ----------
    db_path : str or os.PathLike or None, optional
        Path to the database file. If None or equals DEFAULT_DB_NAME,
        uses DEFAULT_DB_PATH (data/db_files/student_records.db).
    row_factory : bool, default=True
        If True, sets connection.row_factory to sqlite3.Row, allowing
        column access by name (e.g., row['column_name']).
    timeout : float, default=30.0
        Database lock timeout in seconds.

    Returns
    -------
    sqlite3.Connection
        A configured database connection ready for use.

    See Also
    --------
    get_connection : The primary connection function (preferred).
    transaction : Context manager for transactional write operations.

    Notes
    -----
    .. deprecated::
        Use get_connection() instead for new code.
    """
    return get_connection(db_path, row_factory, timeout)

__all__ = [
    "sqlite3",
    "DatabaseManager",
    "get_connection",
    "get_db_connection",
    "DEFAULT_DB_PATH",
    "DB_DIR",
    "EXPORTS_DIR",
    # Connection Pooling
    "ConnectionPool",
    "PooledConnection",
    "get_connection_pool",
    # Transaction Management
    "transaction",
    "atomic_operation",
]
