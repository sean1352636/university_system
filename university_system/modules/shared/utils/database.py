"""Database utilities re-exported from email infrastructure for backward compatibility."""

from __future__ import annotations

import threading
from pathlib import Path

# Import from the actual location
from university_system.infrastructure.email.email_db_utilities import (
    ensure_db_directory,
    ensure_parent_dir,
)

# Also make these available
from university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH
from university_system.modules.shared.constants import paths

# Database management variables - Thread-safe using locks
_DB_READY = False
_DB_READY_LOCK = threading.Lock()  # Protect _DB_READY flag
USE_AUTH_DB = True
MAIN_DIR = str(paths.DATA_DIR)  # Use DATA_DIR instead of MAIN_DIR
PROJECT_ROOT = str(Path(__file__).parent.parent.parent.parent)  # Calculate from file location
DB_PATH = DEFAULT_DB_PATH
_db_manager = None
_db_manager_lock = threading.Lock()

def _ensure_db_ready():
    """
    Ensure database is ready (thread-safe).

    Uses double-checked locking pattern to minimize lock contention
    while ensuring thread-safe initialization.
    """
    global _DB_READY

    # First check without lock (fast path)
    if _DB_READY:
        return True

    # Acquire lock for initialization
    with _DB_READY_LOCK:
        # Double-check inside lock (slow path)
        if not _DB_READY:
            ensure_db_directory()
            _DB_READY = True
        return _DB_READY

def get_unified_connection():
    """Get unified database connection"""
    _ensure_db_ready()
    return get_connection()

class SimpleDBManager:
    """Simple database manager for backward compatibility"""
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH
        _ensure_db_ready()

    def get_connection(self):
        return get_connection()

def get_db_manager():
    """Get database manager instance"""
    global _db_manager
    with _db_manager_lock:
        if _db_manager is None:
            _db_manager = SimpleDBManager()
        return _db_manager

def execute_db_operation(operation, *args, **kwargs):
    """Execute database operation with error handling"""
    try:
        conn = get_connection()
        result = operation(conn, *args, **kwargs)
        conn.close()
        return result
    except Exception as e:
        print(f"Database operation error: {e}")
        return None

def safe_db_operation(func):
    """Decorator for safe database operations"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Database error in {func.__name__}: {e}")
            return None
    return wrapper

def initialize_email_db():
    """Initialize email database tables"""
    _ensure_db_ready()
    return True

def migrate_email_log_table():
    """Migrate email log table"""
    return True

def schedule_database_maintenance():
    """Schedule database maintenance"""
    pass

def optimize_database():
    """Optimize database"""
    _ensure_db_ready()

__all__ = [
    '_DB_READY',
    'USE_AUTH_DB',
    'MAIN_DIR',
    'PROJECT_ROOT',
    'DB_PATH',
    '_db_manager',
    '_db_manager_lock',
    '_ensure_db_ready',
    'ensure_db_directory',
    'ensure_parent_dir',
    'get_unified_connection',
    'SimpleDBManager',
    'get_db_manager',
    'execute_db_operation',
    'safe_db_operation',
    'initialize_email_db',
    'migrate_email_log_table',
    'schedule_database_maintenance',
    'optimize_database',
]
