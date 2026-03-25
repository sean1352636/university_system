"""Database connection utilities for the Primary School Management System."""

import sqlite3
from contextlib import contextmanager

from education_system.primary_school.core.paths import DB_FILE
from education_system.primary_school.infrastructure.database.constants import (
    PRAGMAS, CONNECTION_TIMEOUT,
)

_db_path_override = None


def set_db_path(path):
    """Override the default database path (useful for testing)."""
    global _db_path_override
    _db_path_override = path


def get_db_path():
    """Return the active database path."""
    return _db_path_override or str(DB_FILE)


def connect(db_path=None):
    """Create and return a database connection with standard pragmas."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=CONNECTION_TIMEOUT)
    conn.row_factory = sqlite3.Row
    for pragma, value in PRAGMAS.items():
        conn.execute(f"PRAGMA {pragma} = {value}")
    return conn


@contextmanager
def transaction(conn=None):
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
