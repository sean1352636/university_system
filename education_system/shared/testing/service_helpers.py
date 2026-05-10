"""Service layer testing utilities.

Improvement #11: Testing helpers for service-layer tests
that validate the data flow behind GUI actions.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path


class ServiceTestCase(unittest.TestCase):
    """Base test case for service layer tests.

    Provides:
    - Temporary database per test
    - Schema initialization
    - Helper methods for creating test data

    Usage:
        class TestStudentService(ServiceTestCase):
            SCHEMA_MODULE = "education_system.university_system.infrastructure.database.database_utils"
    """

    SCHEMA_MODULE: str = ""
    DB_MODULE: str = ""

    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self._tmp_dir) / "test.db")

        # Initialize schema if module specified
        if self.SCHEMA_MODULE:
            import importlib
            schema_mod = importlib.import_module(self.SCHEMA_MODULE)
            if hasattr(schema_mod, "init_db"):
                schema_mod.init_db(self.db_path)
            if hasattr(schema_mod, "seed_default_data"):
                schema_mod.seed_default_data(self.db_path)

        # Set db path if module specified
        if self.DB_MODULE:
            import importlib
            db_mod = importlib.import_module(self.DB_MODULE)
            if hasattr(db_mod, "set_db_path"):
                db_mod.set_db_path(self.db_path)

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        except Exception:
            pass

    def execute_sql(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute SQL against the test database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
            conn.commit()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def insert_test_data(self, table: str, data: dict) -> int:
        """Insert test data and return the rowid."""
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                tuple(data.values()),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def count_rows(self, table: str) -> int:
        """Count rows in a table."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            return row[0]
        finally:
            conn.close()
