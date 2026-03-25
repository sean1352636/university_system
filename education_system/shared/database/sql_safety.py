"""Shared SQL safety utilities to prevent injection attacks.

This is the canonical implementation used by all subsystems (college,
secondary, primary).  Each subsystem's ``core/sql_safety.py`` re-exports
from here so that consumer imports remain unchanged.
"""

import re

# Only allow alphanumeric characters and underscores in identifiers
_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Allowed SQL operators for WHERE clauses
ALLOWED_OPERATORS = {"=", "!=", "<", ">", "<=", ">=", "LIKE", "IN", "IS", "IS NOT"}


def validate_identifier(name: str) -> str:
    """Validate and return a safe SQL identifier.

    Raises ValueError if the identifier contains unsafe characters.
    """
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


def escape_like(search: str) -> str:
    """Escape special LIKE wildcard characters in a search term."""
    return search.replace("%", "\\%").replace("_", "\\_")


def build_where_clause(conditions: dict, operator: str = "AND") -> tuple[str, list]:
    """Build a parameterized WHERE clause from a dict of {column: value}.

    Returns (clause_string, params_list). Clause includes leading WHERE.
    None values are treated as IS NULL.
    """
    if not conditions:
        return "", []

    parts = []
    params = []
    for col, val in conditions.items():
        validate_identifier(col)
        if val is None:
            parts.append(f"{col} IS NULL")  # nosec B608 - col validated by validate_identifier
        else:
            parts.append(f"{col} = ?")  # nosec B608 - col validated by validate_identifier
            params.append(val)

    op = f" {operator} "
    return f"WHERE {op.join(parts)}", params


def build_set_clause(updates: dict) -> tuple[str, list]:
    """Build a parameterized SET clause from a dict of {column: value}.

    Returns (clause_string, params_list). Clause includes leading SET.
    """
    if not updates:
        raise ValueError("No columns to update")

    parts = []
    params = []
    for col, val in updates.items():
        validate_identifier(col)
        parts.append(f"{col} = ?")  # nosec B608 - col validated by validate_identifier
        params.append(val)

    return f"SET {', '.join(parts)}", params
