"""Database utilities for shared/utils package.

This module now re-exports from the centralized database utilities module.
"""

from __future__ import annotations

# Re-export from centralized database utilities
from education_system.post_18.university_system.infrastructure.database.utilities import (
    sqlite3,
    DatabaseManager,
    get_connection,
    get_db_connection,
    DEFAULT_DB_PATH,
    DB_DIR,
    EXPORTS_DIR,
    get_unified_connection,
    SimpleDBManager,
    get_db_manager,
    execute_db_operation,
    safe_db_operation,
    initialize_email_db,
    migrate_email_log_table,
    schedule_database_maintenance,
    optimize_database,
    ensure_db_directory,
    ensure_parent_dir,
)

# Backward compatibility aliases
from education_system.post_18.university_system.infrastructure.email.email_db_utilities import (
    _DB_READY,
    MAIN_DIR,
    PROJECT_ROOT,
    DB_PATH,
    _db_manager,
    _db_manager_lock,
    _ensure_db_ready,
)

# Check if we can import auth database connection
try:
    from education_system.post_18.university_system.infrastructure.auth import (
        get_connection as auth_get_connection,
    )
    USE_AUTH_DB = True
except ImportError:
    USE_AUTH_DB = False
    auth_get_connection = None

__all__ = [
    # Core database
    'sqlite3',
    'DatabaseManager',
    'get_connection',
    'get_db_connection',
    'DEFAULT_DB_PATH',
    'DB_DIR',
    'EXPORTS_DIR',

    # Email database utilities
    'get_unified_connection',
    'SimpleDBManager',
    'get_db_manager',
    'execute_db_operation',
    'safe_db_operation',
    'initialize_email_db',
    'migrate_email_log_table',
    'schedule_database_maintenance',
    'optimize_database',
    'ensure_db_directory',
    'ensure_parent_dir',

    # Backward compatibility
    '_DB_READY',
    'USE_AUTH_DB',
    'MAIN_DIR',
    'PROJECT_ROOT',
    'DB_PATH',
    '_db_manager',
    '_db_manager_lock',
    '_ensure_db_ready',
]