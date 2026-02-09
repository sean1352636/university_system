"""
SQL Safety Utilities - Centralized validation for dynamic SQL identifiers.

This module provides validation functions to prevent SQL injection attacks
when table names, column names, or field names must be dynamically included
in SQL queries.

Usage:
    from university_system.modules.shared.utils.sql_safety import (
        validate_table_name,
        validate_column_name,
        validate_column_definition,
        validate_identifier,
        validate_field_for_query,
        get_valid_tables,
        get_valid_columns,
        get_table_schema,
        safe_table_query,
        safe_alter_table_add_column,
        SQLIdentifierError,
        ColumnDefinition,
        VALID_SQLITE_TYPES,
    )

    # Validate table name before using in query
    safe_table = validate_table_name(user_input)
    cursor.execute(f"SELECT * FROM [{safe_table}]")

    # Validate with database connection (checks table exists)
    safe_table = validate_table_name(table_name, conn=connection)
    cursor.execute(f"SELECT COUNT(*) FROM [{safe_table}]")

    # Validate column definition for ALTER TABLE
    col = validate_column_definition('email', 'TEXT NOT NULL', 'users', conn)
    cursor.execute(f'ALTER TABLE users ADD COLUMN [{col.name}] {col.type_def}')

    # High-level helper for adding columns safely
    safe_alter_table_add_column('users', 'email', 'TEXT NOT NULL', conn)

    # Get table schema for validation
    schema = get_table_schema('users', conn)
    if 'email' not in schema['column_names']:
        # Add the column
        pass
"""

import re
import sqlite3
import logging
from typing import Set, Optional, FrozenSet
from functools import lru_cache

logger = logging.getLogger(__name__)


class SQLIdentifierError(ValueError):
    """Raised when an invalid SQL identifier is detected."""
    pass


# Known system tables in the university_system database
# NOTE: The database contains 1000+ tables. This is a core subset used for validation
# when no database connection is available. ALWAYS prefer passing conn parameter
# to validate_table_name() for database verification against actual schema.
KNOWN_TABLES: FrozenSet[str] = frozenset({
    # Core tables
    'students',
    'users',
    'user_accounts',
    'modules',
    'student_modules',
    'courses',
    'enrollments',
    'grades',

    # Authentication tables
    'sessions',
    'login_attempts',
    'mfa_tokens',
    'password_reset_tokens',
    'user_permissions',
    'roles',
    'role_permissions',

    # Academic tables
    'assignments',
    'submissions',
    'attendance',
    'schedules',
    'academic_calendar',
    'course_sections',
    'instructors',
    'departments',

    # Finance tables
    'transactions',
    'invoices',
    'payments',
    'scholarships',
    'financial_aid',
    'budgets',
    'fees',

    # Communication tables
    'messages',
    'chat_rooms',
    'chat_room_members',
    'chat_messages',
    'notifications',
    'notification_preferences',
    'email_queue',
    'email_metrics',
    'scheduled_emails',

    # Student affairs tables
    'clubs',
    'club_members',
    'events',
    'event_registrations',
    'mentorship',
    'alumni',
    'helpdesk_tickets',

    # Health tables
    'health_records',
    'appointments',
    'prescriptions',
    'immunizations',

    # Housing tables
    'accommodations',
    'room_assignments',
    'maintenance_requests',

    # Commerce tables
    'orders',
    'products',
    'inventory',
    'dining_plans',

    # Logging tables
    'logs',
    'activity_logs',
    'audit_trail',
    'error_logs',

    # Backup/System tables
    'backup_metadata',
    'schema_migrations',
    'system_config',

    # AI/Analytics tables
    'ai_detector_submissions',
    'search_history',
    'analytics_data',

    # Encryption tables
    'encryption_keys',
    'encrypted_fields_metadata',
})

# Known columns for common tables (subset - add more as needed)
KNOWN_COLUMNS: FrozenSet[str] = frozenset({
    # Common columns
    'id', 'created_at', 'updated_at', 'status',

    # Student columns
    'student_id', 'first_name', 'last_name', 'email', 'gender',
    'date_of_birth', 'dob', 'age', 'course', 'registration_datetime',
    'enrollment_date', 'phone', 'address',

    # User columns
    'user_id', 'username', 'password_hash', 'salt', 'role',
    'is_active', 'last_login', 'mfa_enabled',

    # Message columns
    'sender_id', 'recipient_id', 'subject', 'body', 'message',
    'content', 'sent_at', 'read_at', 'is_read', 'is_archived',
    'is_deleted_by_sender', 'is_deleted_by_recipient', 'attachment_path',
    'assignment_id',

    # Chat columns
    'room_id', 'max_members', 'description', 'joined_at', 'is_admin',

    # Generic columns
    'name', 'title', 'description', 'type', 'value', 'timestamp',
})

# Valid SQL identifier pattern (alphanumeric and underscores only)
_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def is_valid_identifier_format(identifier: str) -> bool:
    """
    Check if a string matches valid SQL identifier format.

    Valid identifiers:
    - Start with a letter or underscore
    - Contain only letters, numbers, and underscores
    - Are not empty
    - Are reasonably sized (max 128 chars)

    Args:
        identifier: The string to validate

    Returns:
        True if format is valid, False otherwise
    """
    if not identifier or not isinstance(identifier, str):
        return False
    if len(identifier) > 128:
        return False
    return bool(_IDENTIFIER_PATTERN.match(identifier))


def validate_table_name(
    table_name: str,
    allowed_tables: Optional[Set[str]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """
    Validate a table name for safe use in SQL queries.

    This function performs multiple validation checks:
    1. Format validation (valid SQL identifier characters)
    2. Whitelist validation (against known tables or provided set)
    3. Optional database verification (table actually exists)

    Args:
        table_name: The table name to validate
        allowed_tables: Optional set of allowed table names. If None,
                       uses KNOWN_TABLES constant.
        conn: Optional database connection to verify table exists

    Returns:
        The validated table name (unchanged if valid)

    Raises:
        SQLIdentifierError: If validation fails

    Example:
        >>> safe_table = validate_table_name('students')
        >>> cursor.execute(f"SELECT * FROM {safe_table}")
    """
    if not is_valid_identifier_format(table_name):
        logger.warning(f"Invalid table name format rejected: {table_name!r}")
        raise SQLIdentifierError(
            f"Invalid table name format: {table_name!r}. "
            "Table names must start with a letter or underscore and "
            "contain only alphanumeric characters and underscores."
        )

    # Normalize to lowercase for comparison
    table_lower = table_name.lower()

    # Check against whitelist
    whitelist = allowed_tables if allowed_tables is not None else KNOWN_TABLES
    whitelist_lower = {t.lower() for t in whitelist}

    if table_lower not in whitelist_lower:
        # If connection provided, verify against actual database
        if conn is not None:
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if cursor.fetchone() is None:
                    logger.warning(f"Table name not in database: {table_name!r}")
                    raise SQLIdentifierError(
                        f"Table '{table_name}' does not exist in the database."
                    )
                # Table exists in database, allow it
                return table_name
            except sqlite3.Error as e:
                logger.error(f"Database error validating table name: {e}")
                raise SQLIdentifierError(f"Could not validate table name: {e}")

        logger.warning(f"Table name not in whitelist: {table_name!r}")
        raise SQLIdentifierError(
            f"Table '{table_name}' is not in the allowed tables list. "
            "If this is a valid table, add it to KNOWN_TABLES in sql_safety.py"
        )

    return table_name


def validate_column_name(
    column_name: str,
    allowed_columns: Optional[Set[str]] = None,
    table_name: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """
    Validate a column name for safe use in SQL queries.

    Args:
        column_name: The column name to validate
        allowed_columns: Optional set of allowed column names
        table_name: Optional table name to validate column against
        conn: Optional database connection for schema verification

    Returns:
        The validated column name

    Raises:
        SQLIdentifierError: If validation fails
    """
    if not is_valid_identifier_format(column_name):
        logger.warning(f"Invalid column name format rejected: {column_name!r}")
        raise SQLIdentifierError(
            f"Invalid column name format: {column_name!r}. "
            "Column names must start with a letter or underscore and "
            "contain only alphanumeric characters and underscores."
        )

    # Normalize to lowercase for comparison
    column_lower = column_name.lower()

    # If table and connection provided, validate against actual schema
    if table_name is not None and conn is not None:
        try:
            # First validate the table name
            validate_table_name(table_name, conn=conn)

            # Get actual columns from table
            cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
            actual_columns = {row[1].lower() for row in cursor.fetchall()}

            if column_lower not in actual_columns:
                raise SQLIdentifierError(
                    f"Column '{column_name}' does not exist in table '{table_name}'."
                )
            return column_name
        except sqlite3.Error as e:
            logger.error(f"Database error validating column name: {e}")
            raise SQLIdentifierError(f"Could not validate column name: {e}")

    # Check against whitelist
    if allowed_columns is not None:
        allowed_lower = {c.lower() for c in allowed_columns}
        if column_lower not in allowed_lower:
            raise SQLIdentifierError(
                f"Column '{column_name}' is not in the allowed columns list."
            )
    elif column_lower not in {c.lower() for c in KNOWN_COLUMNS}:
        # Log warning but allow - column might be valid but not in our list
        logger.debug(f"Column '{column_name}' not in KNOWN_COLUMNS, allowing anyway")

    return column_name


def validate_identifier(identifier: str, identifier_type: str = "identifier") -> str:
    """
    Generic validation for any SQL identifier (table, column, index, etc.).

    This performs only format validation, not whitelist checking.
    Use validate_table_name or validate_column_name for stricter validation.

    Args:
        identifier: The identifier to validate
        identifier_type: Type description for error messages

    Returns:
        The validated identifier

    Raises:
        SQLIdentifierError: If format validation fails
    """
    if not is_valid_identifier_format(identifier):
        raise SQLIdentifierError(
            f"Invalid {identifier_type} format: {identifier!r}. "
            f"{identifier_type.capitalize()}s must start with a letter or underscore "
            "and contain only alphanumeric characters and underscores."
        )
    return identifier


def get_valid_tables(conn: Optional[sqlite3.Connection] = None) -> Set[str]:
    """
    Get the set of valid table names.

    If a connection is provided, returns actual tables from the database.
    Otherwise, returns the KNOWN_TABLES constant.

    Args:
        conn: Optional database connection

    Returns:
        Set of valid table names
    """
    if conn is not None:
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            return {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"Error getting tables from database: {e}")
            return set(KNOWN_TABLES)
    return set(KNOWN_TABLES)


def get_valid_columns(
    table_name: str,
    conn: sqlite3.Connection
) -> Set[str]:
    """
    Get valid column names for a specific table from the database.

    Args:
        table_name: The table to get columns for
        conn: Database connection

    Returns:
        Set of column names for the table

    Raises:
        SQLIdentifierError: If table name is invalid
    """
    # Validate table name first
    validate_table_name(table_name, conn=conn)

    try:
        cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
        return {row[1] for row in cursor.fetchall()}
    except sqlite3.Error as e:
        logger.error(f"Error getting columns for table {table_name}: {e}")
        raise SQLIdentifierError(f"Could not get columns for table: {e}")


def safe_table_query(table_name: str, conn: Optional[sqlite3.Connection] = None) -> str:
    """
    Create a safe table reference for use in SQL queries.

    Validates the table name and returns it wrapped in square brackets
    for additional safety.

    Args:
        table_name: The table name to validate and format
        conn: Optional database connection for verification

    Returns:
        Safe table reference string (e.g., "[students]")

    Raises:
        SQLIdentifierError: If validation fails
    """
    validated = validate_table_name(table_name, conn=conn)
    return f"[{validated}]"


def validate_field_for_query(
    field_name: str,
    allowed_fields: Set[str],
    field_type: str = "field"
) -> str:
    """
    Validate a field name against a specific whitelist for query use.

    This is useful when you have a specific set of fields that are valid
    for a particular query context.

    Args:
        field_name: The field name to validate
        allowed_fields: Set of allowed field names for this context
        field_type: Type description for error messages

    Returns:
        The validated field name

    Raises:
        SQLIdentifierError: If validation fails
    """
    if not is_valid_identifier_format(field_name):
        raise SQLIdentifierError(
            f"Invalid {field_type} format: {field_name!r}"
        )

    # Case-insensitive comparison
    allowed_lower = {f.lower() for f in allowed_fields}
    if field_name.lower() not in allowed_lower:
        raise SQLIdentifierError(
            f"Invalid {field_type}: '{field_name}'. "
            f"Allowed values: {', '.join(sorted(allowed_fields))}"
        )

    return field_name


# Valid SQLite column types for ALTER TABLE validation
VALID_SQLITE_TYPES: FrozenSet[str] = frozenset({
    'TEXT', 'INTEGER', 'REAL', 'BLOB', 'NUMERIC',
    'INT', 'TINYINT', 'SMALLINT', 'MEDIUMINT', 'BIGINT',
    'UNSIGNED', 'BIG', 'INT2', 'INT8',
    'CHARACTER', 'VARCHAR', 'VARYING', 'NCHAR', 'NATIVE',
    'NVARCHAR', 'CLOB',
    'DOUBLE', 'PRECISION', 'FLOAT',
    'BOOLEAN', 'DATE', 'DATETIME',
})


class ColumnDefinition:
    """Represents a validated column definition for ALTER TABLE operations."""

    def __init__(self, name: str, type_def: str):
        self.name = name
        self.type_def = type_def

    def __repr__(self) -> str:
        return f"ColumnDefinition(name={self.name!r}, type_def={self.type_def!r})"


def validate_column_definition(
    column_name: str,
    column_type: str,
    table_name: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> ColumnDefinition:
    """
    Validate a column name and type definition for use in ALTER TABLE statements.

    This function provides comprehensive validation for dynamic ALTER TABLE operations:
    1. Validates column name format (alphanumeric + underscores)
    2. Validates column type starts with a valid SQLite type
    3. Optionally checks if column already exists in table (to prevent duplicates)

    Args:
        column_name: The column name to add
        column_type: The column type definition (e.g., "TEXT", "INTEGER DEFAULT 0")
        table_name: Optional table name to check for existing columns
        conn: Optional database connection for schema verification

    Returns:
        ColumnDefinition object with validated name and type

    Raises:
        SQLIdentifierError: If validation fails

    Example:
        >>> col = validate_column_definition('email', 'TEXT NOT NULL')
        >>> cursor.execute(f'ALTER TABLE users ADD COLUMN [{col.name}] {col.type_def}')
    """
    # Validate column name format
    if not is_valid_identifier_format(column_name):
        raise SQLIdentifierError(
            f"Invalid column name format: {column_name!r}. "
            "Column names must start with a letter or underscore and "
            "contain only alphanumeric characters and underscores."
        )

    # Validate column type starts with a valid SQLite type
    if not column_type or not isinstance(column_type, str):
        raise SQLIdentifierError(
            f"Invalid column type: {column_type!r}. Type definition is required."
        )

    # Extract base type (first word, uppercase)
    type_parts = column_type.strip().split()
    if not type_parts:
        raise SQLIdentifierError(
            f"Invalid column type: {column_type!r}. Type definition is empty."
        )

    base_type = type_parts[0].upper()

    if base_type not in VALID_SQLITE_TYPES:
        raise SQLIdentifierError(
            f"Invalid column type: '{base_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_SQLITE_TYPES))}"
        )

    # If table and connection provided, check if column already exists
    if table_name is not None and conn is not None:
        try:
            # Validate table name first
            validate_table_name(table_name, conn=conn)

            # Check existing columns
            cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
            existing_columns = {row[1].lower() for row in cursor.fetchall()}

            if column_name.lower() in existing_columns:
                raise SQLIdentifierError(
                    f"Column '{column_name}' already exists in table '{table_name}'."
                )
        except sqlite3.Error as e:
            logger.error(f"Database error validating column definition: {e}")
            raise SQLIdentifierError(f"Could not validate column definition: {e}")

    return ColumnDefinition(name=column_name, type_def=column_type)


def safe_alter_table_add_column(
    table_name: str,
    column_name: str,
    column_type: str,
    conn: sqlite3.Connection,
    if_not_exists: bool = True
) -> bool:
    """
    Safely add a column to a table with full validation.

    This is a high-level helper that validates all inputs and executes
    the ALTER TABLE statement safely.

    Args:
        table_name: The table to add the column to
        column_name: The name of the new column
        column_type: The type definition for the new column
        conn: Database connection
        if_not_exists: If True, silently skip if column exists (default True)

    Returns:
        True if column was added, False if it already existed (when if_not_exists=True)

    Raises:
        SQLIdentifierError: If validation fails
        sqlite3.Error: If database operation fails
    """
    # Validate table name
    validated_table = validate_table_name(table_name, conn=conn)

    # Check if column already exists
    cursor = conn.execute(f"PRAGMA table_info([{validated_table}])")
    existing_columns = {row[1].lower() for row in cursor.fetchall()}

    if column_name.lower() in existing_columns:
        if if_not_exists:
            logger.debug(f"Column '{column_name}' already exists in '{table_name}', skipping")
            return False
        raise SQLIdentifierError(
            f"Column '{column_name}' already exists in table '{table_name}'."
        )

    # Validate column definition
    col_def = validate_column_definition(column_name, column_type)

    # Execute the ALTER TABLE statement
    sql = f"ALTER TABLE [{validated_table}] ADD COLUMN [{col_def.name}] {col_def.type_def}"
    logger.info(f"Adding column: {sql}")
    conn.execute(sql)

    return True


def get_table_schema(
    table_name: str,
    conn: sqlite3.Connection
) -> dict:
    """
    Get the complete schema for a table.

    Args:
        table_name: The table to get schema for
        conn: Database connection

    Returns:
        Dictionary with table schema information:
        {
            'name': str,
            'columns': [{'name': str, 'type': str, 'notnull': bool, 'pk': bool, 'default': any}],
            'column_names': set[str]
        }

    Raises:
        SQLIdentifierError: If table name is invalid
    """
    # Validate table name
    validated_table = validate_table_name(table_name, conn=conn)

    try:
        cursor = conn.execute(f"PRAGMA table_info([{validated_table}])")
        columns = []
        column_names = set()

        for row in cursor.fetchall():
            col_info = {
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': bool(row[3]),
                'default': row[4],
                'pk': bool(row[5])
            }
            columns.append(col_info)
            column_names.add(row[1].lower())

        return {
            'name': validated_table,
            'columns': columns,
            'column_names': column_names
        }
    except sqlite3.Error as e:
        logger.error(f"Error getting schema for table {table_name}: {e}")
        raise SQLIdentifierError(f"Could not get table schema: {e}")
