"""Simple migration framework for schema evolution."""

import sqlite3
from datetime import datetime

from education_system.college_system.infrastructure.database.db import connect


def _ensure_migration_table(conn: sqlite3.Connection):
    """Create the migrations tracking table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT UNIQUE NOT NULL,
            description TEXT,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def get_applied_migrations(conn: sqlite3.Connection) -> set[str]:
    """Get the set of already-applied migration versions."""
    _ensure_migration_table(conn)
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def apply_migration(conn: sqlite3.Connection, version: str, description: str,
                    sql_statements: list[str]):
    """Apply a single migration if not already applied."""
    applied = get_applied_migrations(conn)
    if version in applied:
        return False

    for sql in sql_statements:
        conn.execute(sql)

    conn.execute(
        "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
        (version, description),
    )
    conn.commit()
    return True


# Registry of all migrations
MIGRATIONS = [
    # Example: ("001", "Initial schema", ["CREATE TABLE ..."]),
    # Add new migrations here as the system evolves
]


def run_all_migrations(db_path: str | None = None):
    """Run all pending migrations."""
    conn = connect(db_path)
    try:
        applied_count = 0
        for version, description, statements in MIGRATIONS:
            if apply_migration(conn, version, description, statements):
                applied_count += 1
        return applied_count
    finally:
        conn.close()
