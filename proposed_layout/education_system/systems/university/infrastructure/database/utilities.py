"""
Centralized database utilities module.

This module provides a single import point for common database operations,
combining functionality from various database.py files across the system.
"""

from __future__ import annotations

# Common database path constants (re-exported for convenience)
from education_system.systems.university.infrastructure.paths import (
    DEFAULT_DB_PATH,
    DB_DIR,
    EXPORTS_DIR,
)

# Core database functionality
from education_system.systems.university.infrastructure.database import db as _db_module
from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    DatabaseManager,
    get_connection,
    get_db_connection,
)

# Email database utilities
from education_system.systems.university.infrastructure.email.email_db_utilities import (
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

# Health database backup utilities
try:
    from education_system.systems.university.domain.pastoral.health.services.health_db_backup import (
        create_sqlite_backup,
        ensure_templates_schema,
    )
except ImportError:
    create_sqlite_backup = None
    ensure_templates_schema = None

# Schema initialization functions
try:
    from education_system.systems.university.infrastructure.database.schemas.core_schemas import init_grade_system_db
    from education_system.systems.university.infrastructure.database.schemas.finance_schemas import init_finance_system_db
    from education_system.systems.university.infrastructure.database.schemas.student_union_schemas import init_student_union_db
    from education_system.systems.university.infrastructure.database.schemas.communication_schemas import init_email_system_db
    from education_system.systems.university.infrastructure.database.schemas.misc_schemas import initialize_all_schemas
except ImportError:
    # Fallback if schemas module doesn't exist yet
    init_grade_system_db = None
    init_finance_system_db = None
    init_student_union_db = None
    init_email_system_db = None
    initialize_all_schemas = None


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

    # Health database utilities
    'create_sqlite_backup',
    'ensure_templates_schema',

    # Schema initialization
    'init_grade_system_db',
    'init_finance_system_db',
    'init_student_union_db',
    'init_email_system_db',
    'initialize_all_schemas',
]


def __getattr__(name):
    if name in {'DEFAULT_DB_PATH', 'DB_DIR', 'EXPORTS_DIR'}:
        return getattr(_db_module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
