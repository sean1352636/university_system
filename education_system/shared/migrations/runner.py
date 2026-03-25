"""Lightweight migration runner for SQLite databases.

Improvement #3: Formal Database Migrations

Tracks applied migrations in a _migrations table, discovers migration files
from a directory, and applies them in order. Supports both SQL and Python-based
migrations.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Registry for Python-based migrations
_MIGRATIONS: dict[str, callable] = {}


def migration(name: str):
    """Decorator to register a Python-based migration function.

    Usage:
        @migration("003_add_email_column")
        def add_email(conn):
            conn.execute("ALTER TABLE students ADD COLUMN email TEXT")
    """
    def decorator(func):
        _MIGRATIONS[name] = func
        return func
    return decorator


class MigrationRunner:
    """Run and track database schema migrations.

    Usage:
        runner = MigrationRunner("/path/to/database.db")

        # Apply SQL migration
        runner.apply_sql("001_create_users", "CREATE TABLE users (...)")

        # Apply all .sql files in a directory
        runner.run_directory("migrations/")

        # Apply registered Python migrations
        runner.run_registered()

        # Check status
        print(runner.status())
    """

    TRACKING_TABLE = "_migrations"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_tracking_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.TRACKING_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    def applied(self) -> list[str]:
        """Return list of already-applied migration names."""
        conn = self._connect()
        try:
            self._ensure_tracking_table(conn)
            rows = conn.execute(
                f"SELECT name FROM {self.TRACKING_TABLE} ORDER BY id"
            ).fetchall()
            return [r["name"] for r in rows]
        finally:
            conn.close()

    def apply_sql(self, name: str, sql: str) -> bool:
        """Apply a single SQL migration if not already applied.

        Returns True if applied, False if already existed.
        """
        conn = self._connect()
        try:
            self._ensure_tracking_table(conn)
            existing = conn.execute(
                f"SELECT 1 FROM {self.TRACKING_TABLE} WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                return False

            conn.executescript(sql)
            conn.execute(
                f"INSERT INTO {self.TRACKING_TABLE} (name, applied_at) VALUES (?, ?)",
                (name, datetime.utcnow().isoformat()),
            )
            conn.commit()
            logger.info("Migration applied: %s", name)
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def apply_python(self, name: str, func) -> bool:
        """Apply a Python-based migration function if not already applied."""
        conn = self._connect()
        try:
            self._ensure_tracking_table(conn)
            existing = conn.execute(
                f"SELECT 1 FROM {self.TRACKING_TABLE} WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                return False

            func(conn)
            conn.execute(
                f"INSERT INTO {self.TRACKING_TABLE} (name, applied_at) VALUES (?, ?)",
                (name, datetime.utcnow().isoformat()),
            )
            conn.commit()
            logger.info("Migration applied: %s", name)
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def run_directory(self, migrations_dir: str | Path) -> int:
        """Discover and apply all .sql files in a directory, in sorted order.

        Returns the number of migrations applied.
        """
        migrations_dir = Path(migrations_dir)
        if not migrations_dir.is_dir():
            return 0

        applied_set = set(self.applied())
        count = 0

        for sql_file in sorted(migrations_dir.glob("*.sql")):
            name = sql_file.stem
            if name in applied_set:
                continue
            sql = sql_file.read_text()
            self.apply_sql(name, sql)
            count += 1

        return count

    def run_registered(self) -> int:
        """Apply all registered Python migrations (via @migration decorator)."""
        applied_set = set(self.applied())
        count = 0
        for name in sorted(_MIGRATIONS):
            if name in applied_set:
                continue
            self.apply_python(name, _MIGRATIONS[name])
            count += 1
        return count

    def status(self) -> list[dict]:
        """Return migration status as list of dicts."""
        conn = self._connect()
        try:
            self._ensure_tracking_table(conn)
            rows = conn.execute(
                f"SELECT name, applied_at FROM {self.TRACKING_TABLE} ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
