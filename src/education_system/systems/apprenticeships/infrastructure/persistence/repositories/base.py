"""Helpers shared by every repository.

Repositories are thin: they run SQL and map rows onto domain
dataclasses. Validation, authorisation and orchestration all live a
layer up in ``services/``. Keeping that boundary sharp is what lets the
services be unit-tested against a temporary database without stubbing
anything.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from education_system.systems.apprenticeships.infrastructure.persistence.schema import (
    connect,
    init_db,
)

__all__ = ["QueryBuilder", "col", "connect", "init_db", "to_bool", "to_float", "to_int"]


def col(row: sqlite3.Row, name: str, default: Any = None) -> Any:
    """Read a column that may not be in this particular SELECT.

    List queries often select a subset of columns or add joined labels.
    Rather than write a mapper per query shape, the mappers ask for
    everything and fall back to a default for anything absent.
    """
    try:
        return row[name]
    except (IndexError, KeyError):
        return default


def to_bool(value: Any, default: bool = False) -> bool:
    """SQLite has no boolean type; 0/1 INTEGERs stand in for one."""
    if value is None:
        return default
    return bool(value)


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class QueryBuilder:
    """Accumulates WHERE clauses and their bound parameters.

    Every list method takes optional filters, and hand-rolling the
    ``clauses``/``args`` pair in each one is where SQL injection creeps
    in. Values only ever reach SQL as bound parameters here — the
    fragments callers pass are literal strings written in this codebase,
    never anything from a user.
    """

    def __init__(self) -> None:
        self._clauses: list[str] = []
        self._args: list[Any] = []

    def add(self, clause: str, *args: Any) -> QueryBuilder:
        """Add a fragment such as ``"status = ?"`` with its values."""
        self._clauses.append(clause)
        self._args.extend(args)
        return self

    def add_if(self, condition: Any, clause: str, *args: Any) -> QueryBuilder:
        """Add *clause* only when *condition* is truthy."""
        if condition:
            self.add(clause, *args)
        return self

    def add_in(self, column: str, values: list[Any] | tuple[Any, ...] | None) -> QueryBuilder:
        """Add an ``IN`` filter with one placeholder per value.

        An empty collection is ignored rather than producing ``IN ()``,
        which SQLite rejects outright.
        """
        if not values:
            return self
        placeholders = ", ".join("?" for _ in values)
        return self.add(f"{column} IN ({placeholders})", *values)

    @property
    def where(self) -> str:
        """The WHERE clause, including the keyword, or an empty string."""
        if not self._clauses:
            return ""
        return "WHERE " + " AND ".join(self._clauses)

    @property
    def args(self) -> list[Any]:
        return list(self._args)
