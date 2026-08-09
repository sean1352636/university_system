"""University database revision contract.

Application processes validate schema state but never mutate it. Deployment
jobs own Alembic upgrades.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

REQUIRED_REVISION = "a83f5c7d9e12"


@dataclass(frozen=True, slots=True)
class SchemaState:
    current: str | None
    required: str

    @property
    def supported(self) -> bool:
        return self.current == self.required


class UnsupportedSchemaError(RuntimeError):
    """The application database has not been migrated to the required head."""


def _database_path(db_path: str | Path | None) -> Path:
    if db_path is not None:
        return Path(db_path)
    # Resolve dynamically so tests and tenant-aware deployments can override
    # the database target without re-importing this module.
    from education_system.systems.university.infrastructure.database import db

    return Path(db.DEFAULT_DB_PATH)


def get_schema_state(db_path: str | Path | None = None) -> SchemaState:
    path = _database_path(db_path)
    if not path.exists():
        return SchemaState(current=None, required=REQUIRED_REVISION)
    conn = sqlite3.connect(path)
    try:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='alembic_version'"
        ).fetchone()
        current = (
            conn.execute("SELECT version_num FROM alembic_version").fetchone()
            if table
            else None
        )
        return SchemaState(
            current=str(current[0]) if current else None,
            required=REQUIRED_REVISION,
        )
    finally:
        conn.close()


def require_supported_schema(db_path: str | Path | None = None) -> SchemaState:
    state = get_schema_state(db_path)
    if not state.supported:
        raise UnsupportedSchemaError(
            "Unsupported university database revision "
            f"{state.current or 'unversioned'}; required {state.required}. "
            "Run: python -m alembic -c "
            "src/education_system/alembic.ini upgrade head"
        )
    return state


def require_tables(
    *requirements: tuple[str, frozenset[str]],
    db_path: str | Path | None = None,
) -> None:
    """Validate service-specific tables/columns without running DDL."""
    path = _database_path(db_path)
    conn = sqlite3.connect(path)
    try:
        for table, required_columns in requirements:
            columns = {
                str(row[1])
                for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            missing = required_columns - columns
            if missing:
                raise UnsupportedSchemaError(
                    f"Database table {table!r} is missing columns "
                    f"{', '.join(sorted(missing))}; run Alembic upgrade"
                )
    finally:
        conn.close()


__all__ = [
    "REQUIRED_REVISION",
    "SchemaState",
    "UnsupportedSchemaError",
    "get_schema_state",
    "require_supported_schema",
    "require_tables",
]
