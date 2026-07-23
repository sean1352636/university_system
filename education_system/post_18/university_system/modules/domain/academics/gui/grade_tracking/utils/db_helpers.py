"""
Database helper utilities for grade tracking GUI.

Provides secure SQL operations with SQL injection prevention.
"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import logging
from education_system.post_18.university_system.core.sql_safety import (
    validate_table_name,
    safe_alter_table_add_column,
    SQLIdentifierError
)

logger = logging.getLogger(__name__)

def ensure_column_exists_safe(cursor, table_name, column_name, column_def):
    """
    Safely add column to table if it doesn't exist.

    This is a secure replacement for the vulnerable ensure_column_exists() function
    that was used throughout the grade tracking modules. It uses SQL injection
    prevention via the sql_safety module.

    Args:
        cursor: Database cursor
        table_name: Name of the table to modify
        column_name: Name of the column to add
        column_def: Column type definition (e.g., "TEXT", "INTEGER DEFAULT 0")

    Returns:
        bool: True if successful, False if error occurred

    Security:
        - Validates table name against database schema
        - Validates column name format
        - Validates column type definition
        - Prevents SQL injection via parameterized queries where possible
        - Uses validated identifiers with bracket notation for safety
    """
    try:
        conn = cursor.connection

        # Use the high-level helper from sql_safety (handles all validation)
        was_added = safe_alter_table_add_column(
            table_name=table_name,
            column_name=column_name,
            column_type=column_def,
            conn=conn,
            if_not_exists=True
        )

        if was_added:
            logger.info(f"Added column {column_name} to table {table_name}")
        else:
            logger.debug(f"Column {column_name} already exists in table {table_name}")

        return True

    except SQLIdentifierError as e:
        # SQL injection attempt or invalid identifier detected
        logger.error(f"SQL safety error in ensure_column_exists: {e}")
        print(f"Warning: could not ensure column {column_name} on {table_name}: {e}")
        return False
    except sqlite3.Error as exc:
        # Database error
        logger.error(f"Database error in ensure_column_exists: {exc}")
        print(f"Warning: could not ensure column {column_name} on {table_name}: {exc}")
        return False
    except Exception as exc:
        # Unexpected error
        logger.error(f"Unexpected error in ensure_column_exists: {exc}")
        print(f"Warning: could not ensure column {column_name} on {table_name}: {exc}")
        return False

# Alias for backward compatibility - allows drop-in replacement
ensure_column_exists = ensure_column_exists_safe
