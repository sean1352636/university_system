"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def get_db_connection():
    """Get database connection - wrapper for backwards compatibility"""
    if ORIGINAL_LIBRARY_AVAILABLE:
        # This should call the original library's get_db_connection
        try:
            from library import get_db_connection as original_get_db_connection
            return original_get_db_connection()
        except ImportError:
            pass

    # Fallback implementation
    try:
        from education_system.systems.university.infrastructure.database.db import sqlite3
        return sqlite3.connect(str(DEFAULT_DB_PATH))
    except (sqlite3.Error, DatabaseError, ValueError, TypeError) as e:
        print(f"Database connection error: {e}")
        return None
