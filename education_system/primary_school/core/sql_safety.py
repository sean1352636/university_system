"""SQL safety utilities for the Primary School system.

Re-exports from :mod:`education_system.shared.database.sql_safety` so that
domain services can import from the primary school namespace without coupling
directly to the shared package layout.
"""

from education_system.shared.database.sql_safety import (
    ALLOWED_OPERATORS,
    build_insert_clause,
    build_set_clause,
    build_where_clause,
    escape_like,
    validate_identifier,
)

__all__ = [
    "ALLOWED_OPERATORS",
    "build_insert_clause",
    "build_set_clause",
    "build_where_clause",
    "escape_like",
    "validate_identifier",
]
