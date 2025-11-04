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
from typing import Any, Iterable, Optional

from university_system.modules.shared.constants import paths
from university_system.infrastructure.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    TransactionError,
)
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
    POOL_CLEANUP_INTERVAL,
)

DB_DIR = os.fspath(paths.DB_DIR)
EXPORTS_DIR = os.fspath(paths.DB_EXPORTS_DIR)
DEFAULT_DB_PATH = os.fspath(paths.DEFAULT_DB_PATH)

os.makedirs(EXPORTS_DIR, exist_ok=True)

DEFAULT_DB_NAME = os.path.basename(DEFAULT_DB_PATH)

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
    db = database
    if db is None or os.fspath(db) == DEFAULT_DB_NAME:
        db = DEFAULT_DB_PATH
    kwargs.setdefault("timeout", DEFAULT_DB_TIMEOUT)
    conn = _sqlite3.connect(db, *args, **kwargs)
    try:
        conn.execute(f"PRAGMA foreign_keys={PRAGMA_FOREIGN_KEYS};")
        conn.execute(f"PRAGMA journal_mode={PRAGMA_JOURNAL_MODE};")
        conn.execute(f"PRAGMA synchronous={PRAGMA_SYNCHRONOUS};")
        conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT};")
    except _sqlite3.OperationalError as e:
        logging.warning(f"Failed to set database PRAGMA settings: {e}")
        # Continue with connection even if PRAGMA fails
    return conn

def get_connection(
    db_path: Optional[str | os.PathLike[str]] = None,
    row_factory: bool = True,
    timeout: float = DEFAULT_DB_TIMEOUT,
) -> _sqlite3.Connection:
    target = DEFAULT_DB_PATH if (db_path is None or os.fspath(db_path) == DEFAULT_DB_NAME) else db_path
    db = os.fspath(target)
    conn = _sqlite3.connect(db, timeout=timeout)
    try:
        conn.execute(f"PRAGMA foreign_keys={PRAGMA_FOREIGN_KEYS};")
        conn.execute(f"PRAGMA journal_mode={PRAGMA_JOURNAL_MODE};")
        conn.execute(f"PRAGMA synchronous={PRAGMA_SYNCHRONOUS};")
        conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT};")
    except _sqlite3.OperationalError as e:
        logging.warning(f"Failed to set database PRAGMA settings: {e}")
        # Continue with connection even if PRAGMA fails
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

        # Thread-safe pool management
        self._pool: list[PooledConnection] = []
        self._pool_lock = threading.RLock()  # Reentrant lock for nested operations
        self._connection_semaphore = threading.Semaphore(max_connections)

        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

        # Initialize minimum connections
        self._initialize_pool()

        # Start cleanup thread
        self._start_cleanup_thread()

        logging.info(f"ConnectionPool initialized: {min_connections}-{max_connections} connections")

    def _initialize_pool(self) -> None:
        """Initialize pool with minimum number of connections."""
        with self._pool_lock:
            for _ in range(self.min_connections):
                try:
                    conn = self._create_connection()
                    pooled = PooledConnection(
                        connection=conn,
                        created_at=datetime.now(),
                        last_used=datetime.now(),
                        in_use=False,
                    )
                    self._pool.append(pooled)
                except Exception as e:
                    logging.error(f"Failed to create initial connection: {e}")

    def _create_connection(self) -> _sqlite3.Connection:
        """Create and configure a new database connection."""
        conn = _sqlite3.connect(self.db_path, timeout=DEFAULT_DB_TIMEOUT, check_same_thread=False)
        try:
            conn.execute(f"PRAGMA foreign_keys={PRAGMA_FOREIGN_KEYS};")
            conn.execute(f"PRAGMA journal_mode={PRAGMA_JOURNAL_MODE};")
            conn.execute(f"PRAGMA synchronous={PRAGMA_SYNCHRONOUS};")
            conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT};")
        except _sqlite3.OperationalError as e:
            logging.warning(f"Failed to set database PRAGMA settings: {e}")

        if self.row_factory:
            conn.row_factory = _sqlite3.Row

        return conn

    def get_connection(self, timeout: Optional[float] = None) -> _sqlite3.Connection:
        """
        Get a connection from the pool.

        Args:
            timeout: Override default timeout for getting connection

        Returns:
            Database connection from pool

        Raises:
            TimeoutError: If connection cannot be acquired within timeout
        """
        timeout = timeout or self.timeout
        start_time = time.time()

        # Wait for available slot in semaphore
        if not self._connection_semaphore.acquire(timeout=timeout):
            raise DatabaseConnectionError(
                f"Could not acquire connection within {timeout}s",
                code="DB_CONNECTION_TIMEOUT",
                details={'timeout': timeout, 'pool_size': len(self._pool)}
            )

        try:
            with self._pool_lock:
                # Try to find an available connection
                for pooled in self._pool:
                    if not pooled.in_use:
                        # Check if connection is still valid and not too old
                        if self._is_connection_valid(pooled):
                            pooled.in_use = True
                            pooled.last_used = datetime.now()
                            logging.debug(f"Reusing pooled connection (pool size: {len(self._pool)})")
                            return pooled.connection
                        else:
                            # Connection is stale, remove and create new one
                            self._remove_connection(pooled)

                # No available connection, create new one if under max limit
                if len(self._pool) < self.max_connections:
                    conn = self._create_connection()
                    pooled = PooledConnection(
                        connection=conn,
                        created_at=datetime.now(),
                        last_used=datetime.now(),
                        in_use=True,
                    )
                    self._pool.append(pooled)
                    logging.debug(f"Created new pooled connection (pool size: {len(self._pool)})")
                    return conn

                # Should not reach here due to semaphore, but handle gracefully
                raise DatabaseConnectionError(
                    "Connection pool exhausted unexpectedly",
                    code="DB_POOL_EXHAUSTED",
                    details={'pool_size': len(self._pool), 'max_connections': self.max_connections}
                )

        except Exception:
            # Release semaphore if we failed to get connection
            self._connection_semaphore.release()
            raise

    def release_connection(self, conn: _sqlite3.Connection) -> None:
        """
        Release a connection back to the pool.

        Args:
            conn: Connection to release
        """
        with self._pool_lock:
            for pooled in self._pool:
                if pooled.connection is conn:
                    pooled.in_use = False
                    pooled.last_used = datetime.now()
                    self._connection_semaphore.release()
                    logging.debug(f"Released connection back to pool")
                    return

            # Connection not found in pool - should not happen
            logging.warning("Attempted to release connection not in pool")
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
        """Remove old or idle connections from pool (keeps minimum alive)."""
        with self._pool_lock:
            current_time = datetime.now()
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

            if connections_to_remove:
                logging.info(f"Cleaned up {len(connections_to_remove)} old connections")

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
        """Close all connections in pool and stop cleanup thread."""
        # Stop cleanup thread
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)

        # Close all connections
        with self._pool_lock:
            for pooled in self._pool[:]:  # Copy list to avoid modification during iteration
                self._remove_connection(pooled)

        logging.info("Connection pool closed")

    @contextmanager
    def get_connection_context(self, timeout: Optional[float] = None):
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

    def __enter__(self):
        """Support using pool itself as context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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
def transaction(db_path: Optional[str | os.PathLike[str]] = None, row_factory: bool = True):
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
        # Begin transaction explicitly
        conn.execute("BEGIN TRANSACTION")
        yield conn
        # If we reach here, commit the transaction
        conn.commit()
        logging.debug("Transaction committed successfully")
    except Exception as e:
        # Rollback on any exception
        conn.rollback()
        logging.error(f"Transaction failed, rolling back: {e}")
        raise
    finally:
        # Always close the connection
        conn.close()


@contextmanager
def atomic_operation(conn: Optional[_sqlite3.Connection] = None, db_path: Optional[str | os.PathLike[str]] = None):
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
    """Alias for get_connection for compatibility with GUI code."""
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
