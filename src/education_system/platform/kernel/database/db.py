"""Shared database utilities for all education subsystems."""

import sqlite3
import threading
import logging
import contextlib
from queue import Queue, Empty

logger = logging.getLogger(__name__)

_db_path = None
_lock = threading.Lock()

DEFAULT_PRAGMAS = {
    "journal_mode": "WAL",
    "foreign_keys": "ON",
    "busy_timeout": "5000",
    "synchronous": "NORMAL",
}


def set_db_path(path):
    """Set the default database path."""
    global _db_path
    _db_path = path


def get_db_path():
    """Get the current default database path."""
    return _db_path


def connect(db_path=None):
    """Create a database connection with standard PRAGMAs."""
    path = db_path or _db_path
    if not path:
        raise ValueError("No database path specified. Call set_db_path() first.")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    for pragma, value in DEFAULT_PRAGMAS.items():
        conn.execute(f"PRAGMA {pragma} = {value}")
    return conn


@contextlib.contextmanager
def transaction(db_path=None):
    """Context manager for database transactions with auto commit/rollback."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class ConnectionPool:
    """Simple thread-safe SQLite connection pool."""

    def __init__(self, db_path, max_connections=5):
        self._db_path = db_path
        self._max = max_connections
        self._pool = Queue(maxsize=max_connections)
        self._size = 0
        self._lock = threading.Lock()

    def get_connection(self):
        try:
            return self._pool.get_nowait()
        except Empty:
            with self._lock:
                if self._size < self._max:
                    self._size += 1
                    return connect(self._db_path)
            return self._pool.get(timeout=10)

    def return_connection(self, conn):
        try:
            self._pool.put_nowait(conn)
        except Exception:
            conn.close()

    @contextlib.contextmanager
    def connection(self):
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)

    def close_all(self):
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break


class DatabaseManager:
    """Higher-level database operations."""

    def __init__(self, db_path=None, pool_size=5):
        self._db_path = db_path or _db_path
        self._pool = ConnectionPool(self._db_path, pool_size) if self._db_path else None

    def execute(self, sql, params=None):
        conn = connect(self._db_path)
        try:
            cursor = conn.execute(sql, params or ())
            conn.commit()
            return cursor
        finally:
            conn.close()

    def fetch_all(self, sql, params=None):
        conn = connect(self._db_path)
        try:
            cursor = conn.execute(sql, params or ())
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def fetch_one(self, sql, params=None):
        conn = connect(self._db_path)
        try:
            cursor = conn.execute(sql, params or ())
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def close(self):
        if self._pool:
            self._pool.close_all()
