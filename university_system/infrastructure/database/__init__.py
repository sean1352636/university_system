"""
Database package initialisation.

This package centralises all database‑related utilities for the
application.  Modules should import ``sqlite3``, ``DatabaseManager``
and other helpers from :mod:`refactored.database.db` instead of
directly using the built‑in :mod:`sqlite3` module.  Doing so ensures
that all database connections are created consistently and that the
database file resides in a single, well‑defined location on disk.
"""

# Re‑export commonly used classes and functions from the db module
from university_system.infrastructure.database.db import (
    sqlite3,
    DatabaseManager,
    get_connection,
    DEFAULT_DB_PATH,
    DB_DIR,
    EXPORTS_DIR,
)

__all__ = [
    "sqlite3",
    "DatabaseManager",
    "get_connection",
    "DEFAULT_DB_PATH",
    "DB_DIR",
    "EXPORTS_DIR",
]