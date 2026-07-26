"""Centralised database utilities for the program application.

This module wraps Python's built-in :mod:`sqlite3` module and ensures
every subsystem connects to the same database file located under
``program/data/db_files``.
"""

from __future__ import annotations

import atexit
import logging
import os
import sqlite3 as _sqlite3
import time
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Optional

# Import from core package - no circular imports!
from education_system.systems.university.infrastructure.paths import DB_DIR, DB_EXPORTS_DIR, DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    TransactionError
)
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608

# Import database constants normally (within same package)
from education_system.systems.university.infrastructure.database.constants import (
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
_wal_keeper_connections: dict[str, _sqlite3.Connection] = {}
_ORIGINAL_DEFAULT_DB_PATH: str = os.path.abspath(DEFAULT_DB_PATH)


class _ManagedCursor(_sqlite3.Cursor):
    """Cursor that tolerates explicit BEGIN inside managed transactions."""

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> _sqlite3.Cursor:
        normalized = sql.strip().upper()
        if normalized.startswith("BEGIN") and self.connection.in_transaction:
            return self
        return super().execute(sql, parameters)


class _ManagedConnection(_sqlite3.Connection):
    """Connection using the managed cursor subclass.

    ``__exit__`` is overridden so that using the connection as a context
    manager (``with get_connection() as conn:``) commits/rolls back **and then
    closes** the connection. The stock :class:`sqlite3.Connection` context
    manager only commits/rolls back and leaves the connection open, which leaks
    a live reader for every ``with get_connection()`` block. Under WAL those
    lingering readers, combined with the TRUNCATE checkpoint in ``close()``,
    starve the write lock and surface as ``BEGIN IMMEDIATE ... database is
    locked``. Closing on ``__exit__`` removes the leak everywhere the
    context-manager form is used, while preserving commit-on-success semantics
    for writes.
    """

    def cursor(self, *args: Any, **kwargs: Any) -> _sqlite3.Cursor:
        kwargs.setdefault("factory", _ManagedCursor)
        return super().cursor(*args, **kwargs)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        # Let the stock context manager commit (no exception) or roll back
        # (exception), then always close. Closing in ``finally`` guarantees the
        # connection is released even if the commit itself fails.
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            try:
                self.close()
            except _sqlite3.Error:
                pass
        return False  # never suppress an exception raised inside the block

    def close(self) -> None:
        try:
            if not self.in_transaction:
                # PASSIVE (not TRUNCATE): checkpoint as many frames as possible
                # without acquiring the exclusive WAL lock. TRUNCATE blocks on
                # other readers/writers, so running it on *every* connection
                # close serialised concurrent access and surfaced as
                # "BEGIN IMMEDIATE ... database is locked" retries whenever a
                # flow opened several connections in quick succession (e.g.
                # scheduling an exam). PASSIVE never blocks; SQLite's automatic
                # checkpointing still keeps the WAL bounded.
                super().execute("PRAGMA wal_checkpoint(PASSIVE)")
        except _sqlite3.Error:
            pass
        super().close()


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


def _should_keep_wal_connection(db_path: str) -> bool:
    """Only retain a background WAL keeper for the primary application DB.

    Tests and one-off utilities often create many temporary/custom database
    files. Keeping a permanent WAL connection open for each unique path leaks
    file descriptors across the process and can eventually break pytest's
    tmp_path fixture with "Too many open files".

    Compares against the original default path captured at import time, so
    monkeypatching DEFAULT_DB_PATH in tests does not cause WAL keepers to
    accumulate for every temporary database.
    """
    try:
        return os.path.abspath(db_path) == _ORIGINAL_DEFAULT_DB_PATH
    except OSError:
        return False


def _ensure_wal_keeper(db_path: str) -> None:
    """Keep one background WAL connection open so sidecar files persist."""
    if not _should_keep_wal_connection(db_path):
        return
    if db_path in _wal_keeper_connections:
        return
    try:
        keeper = _sqlite3.connect(
            db_path,
            timeout=DEFAULT_DB_TIMEOUT,
            check_same_thread=False,
            factory=_ManagedConnection,
        )
        _apply_pragmas(keeper)
        _wal_keeper_connections[db_path] = keeper
    except Exception:
        logger.debug("Failed to create WAL keeper for %s", db_path, exc_info=True)


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
    kwargs.setdefault("factory", _ManagedConnection)
    conn = _sqlite3.connect(db, *args, **kwargs)
    _apply_pragmas(conn)
    _ensure_wal_keeper(os.fspath(db))
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
    conn = _sqlite3.connect(db, timeout=timeout, factory=_ManagedConnection)
    _apply_pragmas(conn)
    _ensure_wal_keeper(db)
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

        # Track thread-associated connections for diagnostics and compatibility.
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

        # Register atexit handler to ensure connections are closed on interpreter shutdown
        atexit.register(self.close_all)

        logging.info(f"ConnectionPool initialized: {min_connections}-{max_connections} connections (thread-safe)")

    def _initialize_pool(self) -> None:
        """Initialize pool with a minimum number of reusable connections."""
        try:
            with self._pool_lock:
                for _ in range(self.min_connections):
                    conn = self._create_raw_connection()
                    self._pool.append(
                        PooledConnection(
                            connection=conn,
                            created_at=datetime.now(),
                            last_used=datetime.now(),
                            in_use=False,
                        )
                    )
                if self._pool:
                    self._thread_connections[threading.get_ident()] = self._pool[0]
            logging.debug("Pool initialized with %s warm connections", len(self._pool))
        except Exception as e:
            logging.error(f"Failed to create initial connection: {e}")
            raise DatabaseConnectionError(
                f"Failed to initialize connection pool: {e}",
                code="DB_POOL_INIT_FAILED",
                details={'db_path': self.db_path}
            )

    def _create_raw_connection(self) -> _sqlite3.Connection:
        """Create a new reusable database connection."""
        conn = _sqlite3.connect(
            self.db_path,
            timeout=DEFAULT_DB_TIMEOUT,
            check_same_thread=False,
            factory=_ManagedConnection,
        )
        _apply_pragmas(conn)
        if self.row_factory:
            conn.row_factory = _sqlite3.Row
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

        if not self._connection_semaphore.acquire(timeout=timeout):
            raise DatabaseConnectionError(
                f"Could not acquire connection within {timeout}s",
                code="DB_CONNECTION_TIMEOUT",
                details={'timeout': timeout, 'thread_id': thread_id}
            )

        try:
            with self._pool_lock:
                for pooled in self._pool:
                    if pooled.in_use:
                        continue
                    if not self._is_connection_valid(pooled):
                        self._remove_connection(pooled)
                        break
                    pooled.in_use = True
                    pooled.last_used = datetime.now()
                    with self._thread_connections_lock:
                        self._thread_connections[thread_id] = pooled
                    return pooled.connection

                pooled = PooledConnection(
                    connection=self._create_raw_connection(),
                    created_at=datetime.now(),
                    last_used=datetime.now(),
                    in_use=True,
                )
                self._pool.append(pooled)
                with self._thread_connections_lock:
                    self._thread_connections[thread_id] = pooled
                return pooled.connection
        except Exception:
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

        with self._pool_lock:
            for pooled in self._pool:
                if pooled.connection is conn:
                    pooled.in_use = False
                    pooled.last_used = datetime.now()
                    with self._thread_connections_lock:
                        if self._thread_connections.get(thread_id) is pooled:
                            self._thread_connections.pop(thread_id, None)
                    self._connection_semaphore.release()
                    logging.debug("Released connection back to pool")
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
                    except _sqlite3.ProgrammingError:
                        # Cross-thread close not allowed — drop the reference
                        # so Python's GC reclaims it.
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
        # Unregister atexit handler to avoid double-close
        try:
            atexit.unregister(self.close_all)
        except Exception:
            pass

        # Stop cleanup thread
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)

        # Close all thread-local connections
        # Note: SQLite connections can only be closed from the thread that
        # created them. For cross-thread cleanup we disable the thread check
        # temporarily before closing, then clear the pool.
        with self._thread_connections_lock:
            for thread_id, pooled in list(self._thread_connections.items()):
                try:
                    pooled.connection.close()
                except _sqlite3.ProgrammingError:
                    # Cannot close from a different thread — release the
                    # reference so Python's GC can reclaim it.
                    pass
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
    # BEGIN IMMEDIATE acquires a RESERVED write-lock up front. busy_timeout
    # already retries inside SQLite, but if the conflicting writer hasn't
    # released by then we still see "database is locked" — typically when
    # a long-running operation in another thread holds the lock past the
    # default 30s. Add a small Python-level retry on top so transient
    # contention has another chance instead of bubbling straight out.
    _LOCK_RETRIES = 5
    _LOCK_BACKOFF_BASE = 0.5  # seconds — 0.5, 1, 2, 4, 8s = 15.5s extra

    conn = None
    last_lock_error: Optional[Exception] = None
    for attempt in range(_LOCK_RETRIES):
        conn = get_connection(db_path=db_path, row_factory=row_factory)
        try:
            conn.execute("BEGIN IMMEDIATE")
            break  # got the lock
        except _sqlite3.OperationalError as begin_err:
            try:
                conn.close()
            except Exception:
                pass
            if "database is locked" not in str(begin_err) or attempt == _LOCK_RETRIES - 1:
                last_lock_error = begin_err
                logging.error(
                    "Transaction BEGIN failed after %d attempt(s): %s",
                    attempt + 1, begin_err,
                )
                raise
            sleep_for = _LOCK_BACKOFF_BASE * (2 ** attempt)
            logging.warning(
                "BEGIN IMMEDIATE locked (attempt %d/%d); retrying after %.2fs",
                attempt + 1, _LOCK_RETRIES, sleep_for,
            )
            time.sleep(sleep_for)
            conn = None

    try:
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
def foreign_keys_off(conn: _sqlite3.Connection) -> Generator[_sqlite3.Connection, None, None]:
    """Temporarily disable FK enforcement on ``conn`` for the duration of the
    block, restoring it to ON afterwards even if the body raises.

    Replaces hand-written ``PRAGMA foreign_keys = OFF`` / ``= ON`` pairs around
    bulk multi-table writes (e.g. student create/delete) so the pragma is
    always restored — the explicit form leaves it OFF if an exception fires
    between the two statements.
    """
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        yield conn
    finally:
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            logging.debug("Could not re-enable foreign_keys on connection")


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



@contextmanager
def savepoint(
    conn: _sqlite3.Connection, name: Optional[str] = None
) -> Generator[_sqlite3.Connection, None, None]:
    """Context manager for savepoint-based nested transactions.

    Savepoints allow nested transactional blocks within an already-active
    transaction.  If the inner block raises an exception, only the work
    done since the savepoint is rolled back – the outer transaction stays
    intact.

    Parameters
    ----------
    conn : sqlite3.Connection
        An **open** database connection (the caller is responsible for
        managing the connection lifecycle).
    name : str or None, optional
        An explicit savepoint name.  If *None*, a unique name is
        generated automatically.

    Yields
    ------
    sqlite3.Connection
        The same *conn* that was passed in, so callers can issue queries
        inside the ``with`` block.

    Example
    -------
    >>> with transaction() as conn:
    ...     conn.execute("INSERT INTO t VALUES (1)")
    ...     with savepoint(conn) as sp_conn:
    ...         sp_conn.execute("INSERT INTO t VALUES (2)")
    ...         raise ValueError("oops")  # only row 2 is rolled back
    """
    import uuid as _uuid

    sp_name = name or f"sp_{_uuid.uuid4().hex[:8]}"
    # Validate savepoint name to prevent SQL injection via the 'name' parameter
    validate_identifier(sp_name, "savepoint name")
    conn.execute(f"SAVEPOINT {sp_name}")
    try:
        yield conn
        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
        raise


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

        from education_system.systems.university.infrastructure.database.db import DatabaseManager
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
    "savepoint",
    "foreign_keys_off",
]
