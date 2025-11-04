"""
Enhanced tests for database operations
"""
import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.database.db import DatabaseManager, get_db_connection


@pytest.fixture
def temp_db():
    """Create temporary database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestDatabaseManager:
    """Tests for DatabaseManager"""

    def test_connection(self, temp_db):
        """Test database connection"""
        db = DatabaseManager(temp_db)
        assert db is not None

    def test_create_table(self, temp_db):
        """Test table creation"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        conn.commit()

        # Verify table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        result = cursor.fetchone()
        assert result is not None
        conn.close()

    def test_insert_data(self, temp_db):
        """Test data insertion"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("INSERT INTO test_table (name) VALUES (?)", ("Test",))
        conn.commit()

        cursor.execute("SELECT * FROM test_table WHERE name = ?", ("Test",))
        result = cursor.fetchone()
        assert result is not None
        assert result[1] == "Test"
        conn.close()

    def test_transaction_rollback(self, temp_db):
        """Test transaction rollback on error"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")

        try:
            cursor.execute("INSERT INTO test_table (name) VALUES (?)", ("Test",))
            cursor.execute("INSERT INTO test_table (name) VALUES (?)", ("Test",))  # Duplicate
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()

        cursor.execute("SELECT COUNT(*) FROM test_table")
        count = cursor.fetchone()[0]
        assert count == 0  # Rollback should have undone the first insert
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
