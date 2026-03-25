"""Database connection management and utilities for the College system."""

import sqlite3
import logging
from contextlib import contextmanager

from education_system.college_system.core.paths import DB_FILE, ensure_directories
from education_system.college_system.core.exceptions import DatabaseError
from education_system.college_system.infrastructure.database.constants import (
    PRAGMAS, POOL_MIN_SIZE, POOL_MAX_SIZE, CONNECTION_TIMEOUT,
)
from education_system.shared.database.db import (
    ConnectionPool as _SharedConnectionPool,
    DatabaseManager as _SharedDatabaseManager,
)

logger = logging.getLogger(__name__)

_db_path_override: str | None = None


def set_db_path(path: str):
    """Override the default database path (used for testing)."""
    global _db_path_override
    _db_path_override = path


def get_db_path() -> str:
    """Get the current database file path."""
    if _db_path_override:
        return _db_path_override
    ensure_directories()
    return str(DB_FILE)


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Create a new database connection with standard PRAGMAs applied."""
    path = db_path or get_db_path()
    try:
        conn = sqlite3.connect(path, timeout=CONNECTION_TIMEOUT)
        conn.row_factory = sqlite3.Row
        for pragma, value in PRAGMAS.items():
            conn.execute(f"PRAGMA {pragma} = {value}")
        logger.debug("Database connection opened: %s", path)
        return conn
    except sqlite3.Error as e:
        logger.error("Database connection failed: %s", e)
        raise DatabaseError(f"Failed to connect to database: {e}") from e


def get_connection() -> sqlite3.Connection:
    """Get a database connection (simple wrapper around connect)."""
    return connect()


@contextmanager
def transaction(conn: sqlite3.Connection | None = None):
    """Context manager for database transactions.

    Auto-commits on success, rolls back on exception.
    If no connection is provided, creates a new one.
    """
    own_conn = conn is None
    if own_conn:
        conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        logger.warning("Transaction rolled back due to exception", exc_info=True)
        conn.rollback()
        raise
    finally:
        if own_conn:
            conn.close()


class ConnectionPool(_SharedConnectionPool):
    """College-specific connection pool using shared base."""

    def __init__(self, db_path: str | None = None, min_size: int = POOL_MIN_SIZE,
                 max_size: int = POOL_MAX_SIZE):
        # Use college's connect() which applies system-specific settings
        self._db_path = db_path
        self._max = max_size
        self._size = 0

        from queue import Queue
        import threading
        self._pool: Queue = Queue(maxsize=max_size)
        self._lock = threading.Lock()

        # Pre-create minimum connections
        for _ in range(min_size):
            self._pool.put(connect(db_path))
            self._size += 1

        logger.debug("Connection pool created (min=%d, max=%d)", min_size, max_size)

    def get_connection(self):
        from queue import Empty
        try:
            return self._pool.get_nowait()
        except Empty:
            with self._lock:
                if self._size < self._max:
                    self._size += 1
                    return connect(self._db_path)
            return self._pool.get(timeout=CONNECTION_TIMEOUT)

    def return_connection(self, conn):
        try:
            self._pool.put_nowait(conn)
        except Exception:
            logger.warning("Connection pool full, closing excess connection", exc_info=True)
            conn.close()
            with self._lock:
                self._size -= 1

    # Keep backward-compatible aliases
    get = get_connection
    put = return_connection


class DatabaseManager:
    """High-level database manager combining pool and transaction support."""

    def __init__(self, db_path: str | None = None):
        self._pool = ConnectionPool(db_path)

    def execute(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        """Execute a query and return all results."""
        with self._pool.connection() as conn:
            try:
                cursor = conn.execute(sql, params)
                conn.commit()
                return cursor.fetchall()
            except sqlite3.Error as e:
                conn.rollback()
                logger.error("Query failed: %s", e)
                raise DatabaseError(f"Query failed: {e}") from e

    def execute_one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        """Execute a query and return the first result."""
        rows = self.execute(sql, params)
        return rows[0] if rows else None

    def execute_write(self, sql: str, params: tuple | list = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE and return lastrowid or rowcount."""
        with self._pool.connection() as conn:
            try:
                cursor = conn.execute(sql, params)
                conn.commit()
                return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
            except sqlite3.Error as e:
                conn.rollback()
                logger.error("Write query failed: %s", e)
                raise DatabaseError(f"Write failed: {e}") from e

    @contextmanager
    def transaction(self):
        """Get a connection in a transaction context."""
        with self._pool.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                logger.warning("DatabaseManager transaction rolled back due to exception", exc_info=True)
                conn.rollback()
                raise

    def close(self):
        """Close all pool connections."""
        self._pool.close_all()
