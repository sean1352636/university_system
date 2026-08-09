"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def get_connection():
    """Get database connection with fallback"""
    try:
        # Prefer the central connection from education_system.systems.university.infrastructure.database.db if available
        from education_system.systems.university.infrastructure.database.db import get_connection as central_get_connection
        return central_get_connection()
    except Exception:
        try:
            # Compute the path to the central student_records.db relative to this file.
            from education_system.systems.university.infrastructure.database.db import sqlite3
            from education_system import paths
            return sqlite3.connect(str(paths.UNIVERSITY_DEFAULT_DB_PATH))
        except Exception as e:
            print_error(f"Database connection error: {e}")
            return None
