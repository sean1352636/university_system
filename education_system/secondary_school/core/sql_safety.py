"""SQL safety utilities — re-exports from the shared canonical module."""

from education_system.shared.database.sql_safety import (  # noqa: F401
    ALLOWED_OPERATORS,
    build_set_clause,
    build_where_clause,
    escape_like,
    validate_identifier,
)
