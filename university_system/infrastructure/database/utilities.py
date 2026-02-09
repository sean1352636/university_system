"""
Centralized database utilities module.

This module provides a single import point for common database operations,
combining functionality from various database.py files across the system.
"""

from __future__ import annotations

# Core database functionality
from university_system.infrastructure.database.db import (
    sqlite3,
    DatabaseManager,
    get_connection,
    get_db_connection,
    DEFAULT_DB_PATH,
    DB_DIR,
    EXPORTS_DIR,
)

# Email database utilities
from university_system.infrastructure.email.email_db_utilities import (
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
from university_system.modules.domain.health.services.health_db_backup import (
    create_sqlite_backup,
    ensure_templates_schema,
)

# Schema initialization functions
try:
    from university_system.infrastructure.database.schemas.core_schemas import init_grade_system_db
    from university_system.infrastructure.database.schemas.finance_schemas import init_finance_system_db
    from university_system.infrastructure.database.schemas.student_union_schemas import init_student_union_db
    from university_system.infrastructure.database.schemas.communication_schemas import init_email_system_db
    from university_system.infrastructure.database.schemas.misc_schemas import initialize_all_schemas
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
