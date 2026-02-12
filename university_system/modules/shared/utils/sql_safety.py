"""
SQL Safety Utilities - Centralized validation for dynamic SQL identifiers.

DEPRECATED: This module has been moved to university_system.core.sql_safety
to prevent circular imports. This file now re-exports everything from core
for backward compatibility.

New code should import from:
    from university_system.core.sql_safety import validate_table_name, ...

This backward compatibility shim will be removed in a future version.
"""

# Re-export everything from core.sql_safety for backward compatibility
from university_system.core.sql_safety import (
    SQLIdentifierError,
    KNOWN_TABLES,
    KNOWN_COLUMNS,
    VALID_SQLITE_TYPES,
    ColumnDefinition,
    is_valid_identifier_format,
    validate_table_name,
    validate_column_name,
    validate_identifier,
    get_valid_tables,
    get_valid_columns,
    safe_table_query,
    validate_field_for_query,
    validate_column_definition,
    safe_alter_table_add_column,
    get_table_schema,
    build_where_clause,
    build_update_set,
)

__all__ = [
    "SQLIdentifierError",
    "KNOWN_TABLES",
    "KNOWN_COLUMNS",
    "VALID_SQLITE_TYPES",
    "ColumnDefinition",
    "is_valid_identifier_format",
    "validate_table_name",
    "validate_column_name",
    "validate_identifier",
    "get_valid_tables",
    "get_valid_columns",
    "safe_table_query",
    "validate_field_for_query",
    "validate_column_definition",
    "safe_alter_table_add_column",
    "get_table_schema",
    "build_where_clause",
    "build_update_set",
]
