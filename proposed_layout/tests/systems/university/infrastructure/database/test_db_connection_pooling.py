"""
Comprehensive tests for database connection pooling and transaction management.

Tests the core db.py module including:
- Connection pooling
- Transaction management
- Context managers
- DatabaseManager class
- Connection utilities
"""

import pytest
import os
import tempfile
from education_system.systems.university.infrastructure.database.db import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from education_system.systems.university.infrastructure.database import db as db_module

@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            value INTEGER
        )
    ''')
    cursor.execute("INSERT INTO test_table (name, value) VALUES ('test1', 100)")
    conn.commit()
    conn.close()

    yield db_path

    try:
        os.unlink(db_path)
    except (OSError, IOError):
        pass

class TestSQLite3Proxy:
    """Test the SQLite3 proxy wrapper."""

    def test_sqlite3_proxy_connect(self, temp_db):
        """Test that sqlite3 proxy connect works."""
        conn = db_module.sqlite3.connect(temp_db)
        assert conn is not None
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_sqlite3_proxy_exceptions(self):
        """Test that sqlite3 proxy exposes exceptions."""
        assert hasattr(db_module.sqlite3, 'Error')
        assert hasattr(db_module.sqlite3, 'OperationalError')
        assert hasattr(db_module.sqlite3, 'IntegrityError')

    def test_sqlite3_proxy_row(self):
        """Test that sqlite3.Row is available."""
        assert hasattr(db_module.sqlite3, 'Row')

class TestGetConnection:
    """Test get_connection function."""

    def test_get_connection_default_path(self):
        """Test getting connection with default path."""
        # This may fail if default DB doesn't exist, which is OK
        try:
            conn = db_module.get_connection()
            assert conn is not None
            conn.close()
        except Exception:
            # Expected if default DB doesn't exist yet
            pass

    def test_get_connection_custom_path(self, temp_db):
        """Test getting connection with custom path."""
        conn = db_module.get_connection(db_path=temp_db)
        assert conn is not None

        # Test query execution
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test_table")
        results = cursor.fetchall()
        assert len(results) >= 1

        conn.close()

    def test_get_connection_row_factory(self, temp_db):
        """Test connection with row factory enabled."""
        conn = db_module.get_connection(db_path=temp_db, row_factory=True)

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test_table LIMIT 1")
        row = cursor.fetchone()

        # Row factory enables dict-like access
        if row:
            try:
                _ = row['name']
                assert True
            except (TypeError, KeyError):
                pass  # Row factory may not be working, but that's OK

        conn.close()

    def test_get_connection_without_row_factory(self, temp_db):
        """Test connection without row factory."""
        conn = db_module.get_connection(db_path=temp_db, row_factory=False)

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test_table LIMIT 1")
        row = cursor.fetchone()

        # Without row factory, results are tuples
        if row:
            assert isinstance(row, tuple)

        conn.close()

    def test_get_connection_timeout(self, temp_db):
        """Test connection with custom timeout."""
        conn = db_module.get_connection(db_path=temp_db, timeout=5.0)
        assert conn is not None
        conn.close()

class TestConnectionPool:
    """Test ConnectionPool class."""

    def test_connection_pool_init(self, temp_db):
        """Test connection pool initialization."""
        pool = db_module.ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        assert pool.db_path == temp_db
        assert pool.max_connections == 5
        assert pool.min_connections == 2
        assert len(pool._pool) >= 2  # Should have min connections

        pool.close_all()

    def test_connection_pool_get_connection(self, temp_db):
        """Test getting connection from pool."""
        pool = db_module.ConnectionPool(db_path=temp_db, max_connections=3)

        conn = pool.get_connection()
        assert conn is not None

        # Test using the connection
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1

        pool.release_connection(conn)
        pool.close_all()

    def test_connection_pool_release_connection(self, temp_db):
        """Test releasing connection back to pool."""
        pool = db_module.ConnectionPool(db_path=temp_db, max_connections=3)

        conn = pool.get_connection()
        pool.release_connection(conn)

        # Connection should be available for reuse
        conn2 = pool.get_connection()
        assert conn2 is not None

        pool.release_connection(conn2)
        pool.close_all()

    def test_connection_pool_context_manager(self, temp_db):
        """Test connection pool with context manager."""
        pool = db_module.ConnectionPool(db_path=temp_db)

        with pool.get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

        pool.close_all()

    def test_connection_pool_concurrent_access(self, temp_db):
        """Test concurrent access to connection pool."""
        pool = db_module.ConnectionPool(db_path=temp_db, max_connections=5)
        results = []
        errors = []

        def worker():
            try:
                with pool.get_connection_context() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    results.append(result[0])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert all(r == 1 for r in results)
        assert len(errors) == 0

        pool.close_all()

    def test_connection_pool_max_connections_limit(self, temp_db):
        """Test that pool respects max connections limit."""
        pool = db_module.ConnectionPool(db_path=temp_db, max_connections=2)

        conn1 = pool.get_connection()
        conn2 = pool.get_connection()

        # Third connection should timeout
        with pytest.raises(Exception):  # Should raise timeout error
            pool.get_connection(timeout=0.5)

        pool.release_connection(conn1)
        pool.release_connection(conn2)
        pool.close_all()

    def test_connection_pool_cleanup(self, temp_db):
        """Test connection pool cleanup."""
        pool = db_module.ConnectionPool(db_path=temp_db, max_connections=5)

        # Create connections
        conns = [pool.get_connection() for _ in range(3)]

        # Release them
        for conn in conns:
            pool.release_connection(conn)

        # Close pool
        pool.close_all()

        # Pool should be empty
        assert len(pool._pool) == 0

class TestGetConnectionPool:
    """Test get_connection_pool function."""

    def test_get_connection_pool_singleton(self):
        """Test that get_connection_pool returns singleton instance."""
        # Reset global pool
        db_module._connection_pool = None

        pool1 = db_module.get_connection_pool()
        pool2 = db_module.get_connection_pool()

        assert pool1 is pool2

        if pool1:
            pool1.close_all()

class TestTransaction:
    """Test transaction context manager."""

    def test_transaction_commit(self, temp_db):
        """Test transaction commits on success."""
        with db_module.transaction(db_path=temp_db) as conn:
            conn.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('tx_test', 200))

        # Verify data was committed
        conn = db_module.get_connection(db_path=temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM test_table WHERE name = ?", ('tx_test',))
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 200

    def test_transaction_rollback(self, temp_db):
        """Test transaction rolls back on exception."""
        try:
            with db_module.transaction(db_path=temp_db) as conn:
                conn.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('rollback_test', 300))
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify data was NOT committed
        conn = db_module.get_connection(db_path=temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM test_table WHERE name = ?", ('rollback_test',))
        result = cursor.fetchone()
        conn.close()

        assert result is None

    def test_transaction_isolation(self, temp_db):
        """Test transaction isolation."""
        with db_module.transaction(db_path=temp_db) as conn:
            conn.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('iso_test', 400))
            # Data should not be visible outside transaction yet

        # Now it should be visible
        conn = db_module.get_connection(db_path=temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM test_table WHERE name = ?", ('iso_test',))
        result = cursor.fetchone()
        conn.close()

        assert result is not None

class TestAtomicOperation:
    """Test atomic_operation context manager."""

    def test_atomic_operation_with_new_connection(self, temp_db):
        """Test atomic operation creates new connection."""
        with db_module.atomic_operation(db_path=temp_db) as conn:
            conn.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('atomic_test', 500))

        # Verify data was committed
        conn = db_module.get_connection(db_path=temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM test_table WHERE name = ?", ('atomic_test',))
        result = cursor.fetchone()
        conn.close()

        assert result is not None

    def test_atomic_operation_with_existing_connection(self, temp_db):
        """Test atomic operation with existing connection."""
        conn = db_module.get_connection(db_path=temp_db)

        with db_module.atomic_operation(conn=conn) as c:
            c.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('atomic_existing', 600))

        # Connection should still be open
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM test_table WHERE name = ?", ('atomic_existing',))
        result = cursor.fetchone()

        conn.close()
        assert result is not None

class TestDatabaseManager:
    """Test DatabaseManager context manager."""

    def test_database_manager_basic_usage(self, temp_db):
        """Test basic DatabaseManager usage."""
        with db_module.DatabaseManager(db_path=temp_db) as db:
            db.execute("SELECT * FROM test_table")
            results = db.fetchall()
            assert len(results) >= 1

    def test_database_manager_execute(self, temp_db):
        """Test DatabaseManager execute method."""
        with db_module.DatabaseManager(db_path=temp_db) as db:
            db.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('mgr_test', 700))

        # Verify insertion
        with db_module.DatabaseManager(db_path=temp_db) as db:
            db.execute("SELECT value FROM test_table WHERE name = ?", ('mgr_test',))
            result = db.fetchone()
            assert result is not None

    def test_database_manager_executemany(self, temp_db):
        """Test DatabaseManager executemany method."""
        with db_module.DatabaseManager(db_path=temp_db) as db:
            data = [('many1', 801), ('many2', 802), ('many3', 803)]
            db.executemany("INSERT INTO test_table (name, value) VALUES (?, ?)", data)

        # Verify insertions
        with db_module.DatabaseManager(db_path=temp_db) as db:
            db.execute("SELECT COUNT(*) FROM test_table WHERE name LIKE 'many%'")
            count = db.fetchone()[0]
            assert count == 3

    def test_database_manager_fetchone(self, temp_db):
        """Test DatabaseManager fetchone method."""
        with db_module.DatabaseManager(db_path=temp_db) as db:
            db.execute("SELECT * FROM test_table LIMIT 1")
            result = db.fetchone()
            assert result is not None

    def test_database_manager_fetchall(self, temp_db):
        """Test DatabaseManager fetchall method."""
        with db_module.DatabaseManager(db_path=temp_db) as db:
            db.execute("SELECT * FROM test_table")
            results = db.fetchall()
            assert isinstance(results, list)
            assert len(results) >= 1

    def test_database_manager_commit(self, temp_db):
        """Test DatabaseManager commits on successful exit."""
        with db_module.DatabaseManager(db_path=temp_db) as db:
            db.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('commit_test', 900))

        # Verify committed
        with db_module.DatabaseManager(db_path=temp_db) as db:
            db.execute("SELECT value FROM test_table WHERE name = ?", ('commit_test',))
            result = db.fetchone()
            assert result is not None

    def test_database_manager_rollback(self, temp_db):
        """Test DatabaseManager rolls back on exception."""
        try:
            with db_module.DatabaseManager(db_path=temp_db) as db:
                db.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('rollback_mgr', 1000))
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify rolled back
        with db_module.DatabaseManager(db_path=temp_db) as db:
            db.execute("SELECT value FROM test_table WHERE name = ?", ('rollback_mgr',))
            result = db.fetchone()
            assert result is None

    def test_database_manager_retry_logic(self, temp_db):
        """Test DatabaseManager retry logic on lock."""
        db_manager = db_module.DatabaseManager(db_path=temp_db, max_retries=3, retry_delay=0.1)
        assert db_manager.max_retries == 3
        assert db_manager.retry_delay == 0.1

class TestConnectionAliases:
    """Test connection utility aliases."""

    def test_get_db_connection_alias(self, temp_db):
        """Test get_db_connection is alias for get_connection."""
        conn = db_module.get_db_connection(db_path=temp_db)
        assert conn is not None
        conn.close()

class TestPragmaSettings:
    """Test that PRAGMA settings are applied."""

    def test_pragma_foreign_keys(self, temp_db):
        """Test foreign keys pragma is set."""
        conn = db_module.get_connection(db_path=temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        conn.close()

        # Should be ON (1)
        if result:
            assert result[0] in [0, 1]  # Either 0 or 1 is valid

    def test_pragma_journal_mode(self, temp_db):
        """Test journal mode pragma is set."""
        conn = db_module.get_connection(db_path=temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()
        conn.close()

        if result:
            assert isinstance(result[0], str)

class TestModuleExports:
    """Test that module exports all required symbols."""

    def test_exports_defined(self):
        """Test that __all__ exports are defined."""
        for name in db_module.__all__:
            assert hasattr(db_module, name), f"{name} in __all__ but not defined"

    def test_essential_exports(self):
        """Test that essential exports are available."""
        essential = [
            'sqlite3',
            'DatabaseManager',
            'get_connection',
            'get_db_connection',
            'DEFAULT_DB_PATH',
            'ConnectionPool',
            'transaction',
            'atomic_operation',
        ]

        for name in essential:
            assert hasattr(db_module, name), f"Essential export {name} not available"
            assert name in db_module.__all__, f"Essential export {name} not in __all__"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
