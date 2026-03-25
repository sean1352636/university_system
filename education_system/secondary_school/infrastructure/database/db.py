"""Database connection management and utilities for the Secondary School system."""

import sqlite3
import logging
from contextlib import contextmanager

from education_system.secondary_school.core.paths import DB_FILE, ensure_directories
from education_system.secondary_school.core.exceptions import DatabaseError
from education_system.secondary_school.infrastructure.database.constants import (
    PRAGMAS, CONNECTION_TIMEOUT,
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
        return conn
    except sqlite3.Error as e:
        logger.error("Database connection failed: %s", e)
        raise DatabaseError(f"Failed to connect to database: {e}") from e


def get_connection() -> sqlite3.Connection:
    """Get a database connection (simple wrapper around connect)."""
    return connect()


@contextmanager
def transaction(conn: sqlite3.Connection | None = None):
    """Context manager for database transactions."""
    own_conn = conn is None
    if own_conn:
        conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if own_conn:
            conn.close()
