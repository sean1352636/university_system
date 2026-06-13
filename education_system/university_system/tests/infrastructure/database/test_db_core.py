"""
Comprehensive tests for the core database module (db.py).

Tests all public functions, classes, and context managers including:
- _apply_pragmas, ensure_parent_dir, connect, get_connection
- ConnectionPool, PooledConnection
- DatabaseManager context manager
- transaction, atomic_operation, savepoint
- _SQLiteProxy, get_db_connection, get_connection_pool
"""

import os
import sqlite3 as _sqlite3
import tempfile
import threading
import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db_path():
    """Create a temporary database file path and clean up after."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass
    # Also try removing WAL/SHM files
    for suffix in ('-wal', '-shm'):
        try:
            os.unlink(path + suffix)
        except OSError:
            pass


@pytest.fixture
def temp_db_with_table(temp_db_path):
    """Create a temporary database with a test table."""
    conn = _sqlite3.connect(temp_db_path)
    conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, name TEXT, value REAL)")
    conn.execute("INSERT INTO test_data VALUES (1, 'alpha', 10.5)")
    conn.execute("INSERT INTO test_data VALUES (2, 'beta', 20.0)")
    conn.commit()
    conn.close()
    return temp_db_path


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    d = tempfile.mkdtemp()
    yield d
    try:
        os.rmdir(d)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Test _apply_pragmas
# ---------------------------------------------------------------------------

class TestApplyPragmas:
    """Test _apply_pragmas helper function."""

    def test_apply_pragmas_sets_all_settings(self, temp_db_path):
        """Test that _apply_pragmas executes all PRAGMA statements."""
        from education_system.university_system.infrastructure.database.db import _apply_pragmas
        conn = _sqlite3.connect(temp_db_path)
        _apply_pragmas(conn)

        # Verify PRAGMAs were applied
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1  # ON

        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal.lower() == 'wal'

        sync = conn.execute("PRAGMA synchronous").fetchone()[0]
        assert sync == 1  # NORMAL

        conn.close()

    def test_apply_pragmas_handles_operational_error(self):
        """Test that _apply_pragmas logs warning but does not raise on error."""
        from education_system.university_system.infrastructure.database.db import _apply_pragmas
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = _sqlite3.OperationalError("test error")

        # Should not raise
        _apply_pragmas(mock_conn)


# ---------------------------------------------------------------------------
# Test ensure_parent_dir
# ---------------------------------------------------------------------------

class TestEnsureParentDir:
    """Test ensure_parent_dir function."""

    def test_creates_parent_directory(self, temp_dir):
        """Test that parent directory is created when it does not exist."""
        from education_system.university_system.infrastructure.database.db import ensure_parent_dir
        nested_path = os.path.join(temp_dir, "subdir", "db.sqlite")
        ensure_parent_dir(nested_path)
        assert os.path.isdir(os.path.join(temp_dir, "subdir"))
        # Cleanup
        os.rmdir(os.path.join(temp_dir, "subdir"))

    def test_does_not_fail_if_parent_exists(self, temp_dir):
        """Test that function is a no-op if parent already exists."""
        from education_system.university_system.infrastructure.database.db import ensure_parent_dir
        path = os.path.join(temp_dir, "existing.db")
        ensure_parent_dir(path)
        # No exception, directory still exists
        assert os.path.isdir(temp_dir)


# ---------------------------------------------------------------------------
# Test connect function
# ---------------------------------------------------------------------------

class TestConnectFunction:
    """Test the connect() wrapper function."""

    def test_connect_returns_connection(self, temp_db_path):
        """Test connect returns a valid sqlite3 connection."""
        from education_system.university_system.infrastructure.database.db import connect
        conn = connect(temp_db_path)
        assert conn is not None
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1
        conn.close()

    def test_connect_applies_pragmas(self, temp_db_path):
        """Test connect applies PRAGMA settings."""
        from education_system.university_system.infrastructure.database.db import connect
        conn = connect(temp_db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_connect_default_timeout(self, temp_db_path):
        """Test connect uses DEFAULT_DB_TIMEOUT when no timeout given."""
        from education_system.university_system.infrastructure.database.db import connect
        with patch('education_system.university_system.infrastructure.database.db._sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            connect(temp_db_path)
            args, kwargs = mock_connect.call_args
            assert 'timeout' in kwargs
            assert kwargs['timeout'] > 0

    def test_connect_custom_timeout(self, temp_db_path):
        """Test connect passes custom timeout through."""
        from education_system.university_system.infrastructure.database.db import connect
        with patch('education_system.university_system.infrastructure.database.db._sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            connect(temp_db_path, timeout=99.0)
            args, kwargs = mock_connect.call_args
            assert kwargs['timeout'] == 99.0

    def test_connect_none_uses_default_path(self):
        """Test connect(None) uses DEFAULT_DB_PATH."""
        from education_system.university_system.infrastructure.database.db import connect, DEFAULT_DB_PATH
        with patch('education_system.university_system.infrastructure.database.db._sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            connect(None)
            args, kwargs = mock_connect.call_args
            assert args[0] == DEFAULT_DB_PATH


# ---------------------------------------------------------------------------
# Test get_connection function
# ---------------------------------------------------------------------------

class TestGetConnection:
    """Test the get_connection() function."""

    def test_get_connection_returns_connection(self, temp_db_path):
        """Test get_connection returns a sqlite3 connection."""
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection(temp_db_path)
        assert conn is not None
        conn.close()

    def test_get_connection_with_row_factory(self, temp_db_with_table):
        """Test get_connection with row_factory=True enables Row access."""
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection(temp_db_with_table, row_factory=True)
        row = conn.execute("SELECT * FROM test_data WHERE id = 1").fetchone()
        assert row['name'] == 'alpha'
        assert row['value'] == 10.5
        conn.close()

    def test_get_connection_without_row_factory(self, temp_db_with_table):
        """Test get_connection with row_factory=False returns tuples."""
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection(temp_db_with_table, row_factory=False)
        row = conn.execute("SELECT * FROM test_data WHERE id = 1").fetchone()
        assert row == (1, 'alpha', 10.5)
        conn.close()

    def test_get_connection_custom_timeout(self, temp_db_path):
        """Test get_connection passes custom timeout."""
        from education_system.university_system.infrastructure.database.db import get_connection
        with patch('education_system.university_system.infrastructure.database.db._sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            get_connection(temp_db_path, timeout=15.0)
            args, kwargs = mock_connect.call_args
            assert kwargs['timeout'] == 15.0

    def test_get_connection_none_uses_default_path(self):
        """Test get_connection(None) uses DEFAULT_DB_PATH."""
        from education_system.university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH
        with patch('education_system.university_system.infrastructure.database.db._sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            get_connection(None)
            args, kwargs = mock_connect.call_args
            assert args[0] == DEFAULT_DB_PATH


# ---------------------------------------------------------------------------
# Test get_db_connection alias
# ---------------------------------------------------------------------------

class TestGetDbConnection:
    """Test get_db_connection alias for backward compatibility."""

    def test_get_db_connection_returns_connection(self, temp_db_path):
        """Test get_db_connection returns a valid connection."""
        from education_system.university_system.infrastructure.database.db import get_db_connection
        conn = get_db_connection(temp_db_path)
        assert conn is not None
        conn.close()

    def test_get_db_connection_delegates_to_get_connection(self, temp_db_path):
        """Test get_db_connection calls get_connection internally."""
        from education_system.university_system.infrastructure.database.db import get_db_connection
        with patch('education_system.university_system.infrastructure.database.db.get_connection') as mock_gc:
            mock_gc.return_value = MagicMock()
            get_db_connection(temp_db_path, row_factory=False, timeout=5.0)
            mock_gc.assert_called_once_with(temp_db_path, False, 5.0)


# ---------------------------------------------------------------------------
# Test DatabaseManager
# ---------------------------------------------------------------------------

class TestDatabaseManager:
    """Test DatabaseManager context manager."""

    def test_context_manager_enter_exit(self, temp_db_path):
        """Test entering and exiting the context manager."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        with DatabaseManager(db_path=temp_db_path) as db:
            assert db is not None
            assert db.conn is not None
            assert db.cursor is not None

    def test_execute_select(self, temp_db_with_table):
        """Test execute with a SELECT query."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        with DatabaseManager(db_path=temp_db_with_table) as db:
            db.execute("SELECT * FROM test_data WHERE id = ?", (1,))
            row = db.fetchone()
            assert row['name'] == 'alpha'

    def test_execute_insert_commits(self, temp_db_with_table):
        """Test that inserts are committed on successful exit."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        with DatabaseManager(db_path=temp_db_with_table) as db:
            db.execute("INSERT INTO test_data VALUES (3, 'gamma', 30.0)")

        # Verify committed
        conn = _sqlite3.connect(temp_db_with_table)
        row = conn.execute("SELECT name FROM test_data WHERE id = 3").fetchone()
        assert row[0] == 'gamma'
        conn.close()

    def test_executemany(self, temp_db_with_table):
        """Test executemany inserts multiple rows."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        with DatabaseManager(db_path=temp_db_with_table) as db:
            db.executemany(
                "INSERT INTO test_data VALUES (?, ?, ?)",
                [(10, 'ten', 10.0), (11, 'eleven', 11.0)]
            )

        conn = _sqlite3.connect(temp_db_with_table)
        count = conn.execute("SELECT COUNT(*) FROM test_data").fetchone()[0]
        assert count >= 4
        conn.close()

    def test_fetchall(self, temp_db_with_table):
        """Test fetchall returns all rows."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        with DatabaseManager(db_path=temp_db_with_table) as db:
            db.execute("SELECT * FROM test_data")
            rows = db.fetchall()
            assert len(rows) == 2

    def test_rollback_on_exception(self, temp_db_with_table):
        """Test that transaction is rolled back on exception."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        try:
            with DatabaseManager(db_path=temp_db_with_table) as db:
                db.execute("INSERT INTO test_data VALUES (99, 'rollback', 0.0)")
                raise ValueError("force rollback")
        except ValueError:
            pass

        conn = _sqlite3.connect(temp_db_with_table)
        row = conn.execute("SELECT * FROM test_data WHERE id = 99").fetchone()
        assert row is None
        conn.close()

    def test_execute_without_cursor_raises(self):
        """Test execute raises QueryError when cursor is None."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        from education_system.university_system.core.exceptions import QueryError
        dm = DatabaseManager(db_path=":memory:")
        # cursor is None before __enter__
        with pytest.raises(QueryError):
            dm.execute("SELECT 1")

    def test_executemany_without_cursor_raises(self):
        """Test executemany raises QueryError when cursor is None."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        from education_system.university_system.core.exceptions import QueryError
        dm = DatabaseManager(db_path=":memory:")
        with pytest.raises(QueryError):
            dm.executemany("INSERT INTO t VALUES (?)", [(1,)])

    def test_fetchone_without_cursor_raises(self):
        """Test fetchone raises QueryError when cursor is None."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        from education_system.university_system.core.exceptions import QueryError
        dm = DatabaseManager(db_path=":memory:")
        with pytest.raises(QueryError):
            dm.fetchone()

    def test_fetchall_without_cursor_raises(self):
        """Test fetchall raises QueryError when cursor is None."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        from education_system.university_system.core.exceptions import QueryError
        dm = DatabaseManager(db_path=":memory:")
        with pytest.raises(QueryError):
            dm.fetchall()

    def test_default_db_path(self):
        """Test DatabaseManager uses DEFAULT_DB_PATH when no path given."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager, DEFAULT_DB_PATH
        dm = DatabaseManager()
        assert dm.db_path == DEFAULT_DB_PATH

    def test_custom_retry_settings(self):
        """Test DatabaseManager accepts custom retry settings."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        dm = DatabaseManager(db_path=":memory:", max_retries=10, retry_delay=0.5)
        assert dm.max_retries == 10
        assert dm.retry_delay == 0.5

    def test_retry_on_database_locked(self):
        """Test that DatabaseManager retries when database is locked."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        with patch('education_system.university_system.infrastructure.database.db.connect') as mock_connect:
            # Fail first time, succeed second time
            locked_err = _sqlite3.OperationalError("database is locked")
            mock_conn = MagicMock()
            mock_connect.side_effect = [locked_err, mock_conn]

            dm = DatabaseManager(db_path="/tmp/fake.db", max_retries=3, retry_delay=0.01)
            result = dm.__enter__()
            assert result is dm
            assert dm.conn is mock_conn

    def test_non_lock_error_not_retried(self):
        """Test that non-lock OperationalError is not retried."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        with patch('education_system.university_system.infrastructure.database.db.connect') as mock_connect:
            mock_connect.side_effect = _sqlite3.OperationalError("disk I/O error")
            dm = DatabaseManager(db_path="/tmp/fake.db", max_retries=3, retry_delay=0.01)
            with pytest.raises(_sqlite3.OperationalError, match="disk I/O error"):
                dm.__enter__()

    def test_exit_does_not_suppress_exceptions(self, temp_db_path):
        """Test __exit__ returns False (does not suppress exceptions)."""
        from education_system.university_system.infrastructure.database.db import DatabaseManager
        with pytest.raises(RuntimeError):
            with DatabaseManager(db_path=temp_db_path):
                raise RuntimeError("test")


# ---------------------------------------------------------------------------
# Test transaction context manager
# ---------------------------------------------------------------------------

class TestTransaction:
    """Test the transaction() context manager."""

    def test_transaction_commits_on_success(self, temp_db_with_table):
        """Test that transaction commits on successful completion."""
        from education_system.university_system.infrastructure.database.db import transaction
        with transaction(db_path=temp_db_with_table) as conn:
            conn.execute("INSERT INTO test_data VALUES (5, 'five', 5.0)")

        verify_conn = _sqlite3.connect(temp_db_with_table)
        row = verify_conn.execute("SELECT name FROM test_data WHERE id = 5").fetchone()
        assert row[0] == 'five'
        verify_conn.close()

    def test_transaction_rolls_back_on_error(self, temp_db_with_table):
        """Test that transaction rolls back on exception."""
        from education_system.university_system.infrastructure.database.db import transaction
        try:
            with transaction(db_path=temp_db_with_table) as conn:
                conn.execute("INSERT INTO test_data VALUES (6, 'six', 6.0)")
                raise ValueError("rollback")
        except ValueError:
            pass

        verify_conn = _sqlite3.connect(temp_db_with_table)
        row = verify_conn.execute("SELECT * FROM test_data WHERE id = 6").fetchone()
        assert row is None
        verify_conn.close()

    def test_transaction_exception_re_raised(self, temp_db_path):
        """Test that the original exception is re-raised after rollback."""
        from education_system.university_system.infrastructure.database.db import transaction
        with pytest.raises(ValueError, match="test error"):
            with transaction(db_path=temp_db_path):
                raise ValueError("test error")

    def test_transaction_with_row_factory(self, temp_db_with_table):
        """Test transaction with row_factory parameter."""
        from education_system.university_system.infrastructure.database.db import transaction
        with transaction(db_path=temp_db_with_table, row_factory=True) as conn:
            row = conn.execute("SELECT * FROM test_data WHERE id = 1").fetchone()
            assert row['name'] == 'alpha'

    def test_transaction_without_row_factory(self, temp_db_with_table):
        """Test transaction with row_factory=False."""
        from education_system.university_system.infrastructure.database.db import transaction
        with transaction(db_path=temp_db_with_table, row_factory=False) as conn:
            row = conn.execute("SELECT * FROM test_data WHERE id = 1").fetchone()
            assert row == (1, 'alpha', 10.5)

    def test_transaction_closes_connection(self, temp_db_path):
        """Test that transaction closes the connection in finally block."""
        from education_system.university_system.infrastructure.database.db import transaction
        captured_conn = None
        with transaction(db_path=temp_db_path) as conn:
            conn.execute("CREATE TABLE t (id INTEGER)")
            captured_conn = conn

        # Connection should be closed; executing should raise
        with pytest.raises(Exception):
            captured_conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# Test atomic_operation context manager
# ---------------------------------------------------------------------------

class TestAtomicOperation:
    """Test the atomic_operation() context manager."""

    def test_atomic_with_existing_connection(self, temp_db_with_table):
        """Test atomic_operation with an existing connection (not owned)."""
        from education_system.university_system.infrastructure.database.db import atomic_operation, get_connection
        conn = get_connection(temp_db_with_table, row_factory=False)
        with atomic_operation(conn=conn) as c:
            c.execute("INSERT INTO test_data VALUES (7, 'seven', 7.0)")

        # Connection should NOT be closed (not owned)
        row = conn.execute("SELECT name FROM test_data WHERE id = 7").fetchone()
        assert row[0] == 'seven'
        conn.close()

    def test_atomic_creates_new_connection_if_none(self, temp_db_with_table):
        """Test atomic_operation creates connection when none provided."""
        from education_system.university_system.infrastructure.database.db import atomic_operation
        with atomic_operation(db_path=temp_db_with_table) as conn:
            conn.execute("INSERT INTO test_data VALUES (8, 'eight', 8.0)")

        verify = _sqlite3.connect(temp_db_with_table)
        row = verify.execute("SELECT name FROM test_data WHERE id = 8").fetchone()
        assert row[0] == 'eight'
        verify.close()

    def test_atomic_rolls_back_on_error(self, temp_db_with_table):
        """Test atomic_operation rolls back on error."""
        from education_system.university_system.infrastructure.database.db import atomic_operation, get_connection
        conn = get_connection(temp_db_with_table, row_factory=False)
        try:
            with atomic_operation(conn=conn) as c:
                c.execute("INSERT INTO test_data VALUES (9, 'nine', 9.0)")
                raise RuntimeError("fail")
        except RuntimeError:
            pass

        row = conn.execute("SELECT * FROM test_data WHERE id = 9").fetchone()
        assert row is None
        conn.close()


# ---------------------------------------------------------------------------
# Test savepoint context manager
# ---------------------------------------------------------------------------

class TestSavepoint:
    """Test the savepoint() context manager for nested transactions."""

    def test_savepoint_success(self, temp_db_with_table):
        """Test savepoint commits nested work on success."""
        from education_system.university_system.infrastructure.database.db import savepoint
        conn = _sqlite3.connect(temp_db_with_table)
        conn.execute("BEGIN")
        with savepoint(conn, name="sp_test") as sp_conn:
            sp_conn.execute("INSERT INTO test_data VALUES (20, 'sp_ok', 20.0)")

        conn.commit()
        row = conn.execute("SELECT name FROM test_data WHERE id = 20").fetchone()
        assert row[0] == 'sp_ok'
        conn.close()

    def test_savepoint_rollback_on_error(self, temp_db_with_table):
        """Test savepoint rolls back nested work on error."""
        from education_system.university_system.infrastructure.database.db import savepoint
        conn = _sqlite3.connect(temp_db_with_table)
        conn.execute("BEGIN")
        conn.execute("INSERT INTO test_data VALUES (21, 'outer', 21.0)")

        try:
            with savepoint(conn, name="sp_fail") as sp_conn:
                sp_conn.execute("INSERT INTO test_data VALUES (22, 'inner', 22.0)")
                raise ValueError("inner fail")
        except ValueError:
            pass

        conn.commit()
        # Outer insert should be present
        row21 = conn.execute("SELECT name FROM test_data WHERE id = 21").fetchone()
        assert row21[0] == 'outer'
        # Inner insert should be rolled back
        row22 = conn.execute("SELECT * FROM test_data WHERE id = 22").fetchone()
        assert row22 is None
        conn.close()

    def test_savepoint_auto_name(self, temp_db_with_table):
        """Test savepoint generates a name when none provided."""
        from education_system.university_system.infrastructure.database.db import savepoint
        conn = _sqlite3.connect(temp_db_with_table)
        conn.execute("BEGIN")
        with savepoint(conn) as sp_conn:
            sp_conn.execute("INSERT INTO test_data VALUES (23, 'auto', 23.0)")
        conn.commit()
        row = conn.execute("SELECT name FROM test_data WHERE id = 23").fetchone()
        assert row[0] == 'auto'
        conn.close()


# ---------------------------------------------------------------------------
# Test _SQLiteProxy
# ---------------------------------------------------------------------------

class TestSQLiteProxy:
    """Test the _SQLiteProxy class."""

    def test_proxy_connect_returns_connection(self, temp_db_path):
        """Test proxy.connect returns a working connection."""
        from education_system.university_system.infrastructure.database.db import sqlite3 as proxy
        conn = proxy.connect(temp_db_path)
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1
        conn.close()

    def test_proxy_delegates_attributes(self):
        """Test proxy delegates non-connect attributes to real sqlite3."""
        from education_system.university_system.infrastructure.database.db import sqlite3 as proxy
        assert proxy.Row is _sqlite3.Row
        assert proxy.OperationalError is _sqlite3.OperationalError
        assert proxy.IntegrityError is _sqlite3.IntegrityError

    def test_proxy_sqlite_version(self):
        """Test proxy exposes sqlite3.sqlite_version."""
        from education_system.university_system.infrastructure.database.db import sqlite3 as proxy
        assert proxy.sqlite_version == _sqlite3.sqlite_version


# ---------------------------------------------------------------------------
# Test ConnectionPool
# ---------------------------------------------------------------------------

class TestConnectionPool:
    """Test the ConnectionPool class."""

    def test_pool_initialization(self, temp_db_path):
        """Test ConnectionPool can be initialized."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool
        pool = ConnectionPool(db_path=temp_db_path, max_connections=5, min_connections=1)
        assert pool.db_path == temp_db_path
        assert pool.max_connections == 5
        assert pool.min_connections == 1
        pool.close_all()

    def test_pool_get_connection(self, temp_db_path):
        """Test getting a connection from the pool."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool
        pool = ConnectionPool(db_path=temp_db_path, max_connections=5, min_connections=1)
        conn = pool.get_connection()
        assert conn is not None
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1
        pool.release_connection(conn)
        pool.close_all()

    def test_pool_release_connection(self, temp_db_path):
        """Test releasing a connection back to the pool."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool
        pool = ConnectionPool(db_path=temp_db_path, max_connections=5, min_connections=1)
        conn = pool.get_connection()
        pool.release_connection(conn)
        # Get connection again - should work (reuse)
        conn2 = pool.get_connection()
        assert conn2 is not None
        pool.release_connection(conn2)
        pool.close_all()

    def test_pool_context_manager(self, temp_db_path):
        """Test ConnectionPool as context manager closes all on exit."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool
        with ConnectionPool(db_path=temp_db_path, max_connections=3, min_connections=1) as pool:
            conn = pool.get_connection()
            result = conn.execute("SELECT 42").fetchone()
            assert result[0] == 42
            pool.release_connection(conn)

    def test_pool_get_connection_context(self, temp_db_path):
        """Test get_connection_context yields and releases properly."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool
        pool = ConnectionPool(db_path=temp_db_path, max_connections=5, min_connections=1)
        with pool.get_connection_context() as conn:
            result = conn.execute("SELECT 100").fetchone()
            assert result[0] == 100
        pool.close_all()

    def test_pool_get_stats(self, temp_db_path):
        """Test get_stats returns expected keys."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool
        pool = ConnectionPool(db_path=temp_db_path, max_connections=5, min_connections=1)
        stats = pool.get_stats()
        assert 'thread_local_connections' in stats
        assert 'total_connections' in stats
        assert 'max_connections' in stats
        assert stats['max_connections'] == 5
        assert 'db_path' in stats
        pool.close_all()

    def test_pool_row_factory(self, temp_db_with_table):
        """Test pool connections have row_factory when enabled."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool
        pool = ConnectionPool(db_path=temp_db_with_table, row_factory=True,
                              max_connections=3, min_connections=1)
        conn = pool.get_connection()
        row = conn.execute("SELECT * FROM test_data WHERE id = 1").fetchone()
        assert row['name'] == 'alpha'
        pool.release_connection(conn)
        pool.close_all()

    def test_pool_close_all(self, temp_db_path):
        """Test close_all cleanly shuts down the pool."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool
        pool = ConnectionPool(db_path=temp_db_path, max_connections=3, min_connections=1)
        conn = pool.get_connection()
        pool.release_connection(conn)
        pool.close_all()
        # cleanup thread should be stopped
        assert pool._stop_cleanup.is_set()

    def test_pool_connection_validation(self, temp_db_path):
        """Test _is_connection_valid detects stale connections."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool, PooledConnection
        pool = ConnectionPool(db_path=temp_db_path, max_connections=3,
                              min_connections=1, max_connection_age=1)

        # Create a pooled connection that appears very old
        conn = _sqlite3.connect(temp_db_path)
        old_pooled = PooledConnection(
            connection=conn,
            created_at=datetime.now() - timedelta(seconds=9999),
            last_used=datetime.now(),
            in_use=False,
        )
        assert pool._is_connection_valid(old_pooled) is False
        conn.close()
        pool.close_all()

    def test_pool_release_unknown_connection(self, temp_db_path):
        """Test releasing a connection not from the pool logs warning."""
        from education_system.university_system.infrastructure.database.db import ConnectionPool
        pool = ConnectionPool(db_path=temp_db_path, max_connections=3, min_connections=1)
        unknown_conn = _sqlite3.connect(":memory:")
        # Should not raise, just log a warning
        pool.release_connection(unknown_conn)
        unknown_conn.close()
        pool.close_all()


# ---------------------------------------------------------------------------
# Test PooledConnection dataclass
# ---------------------------------------------------------------------------

class TestPooledConnection:
    """Test PooledConnection dataclass."""

    def test_pooled_connection_creation(self):
        """Test creating a PooledConnection."""
        from education_system.university_system.infrastructure.database.db import PooledConnection
        conn = MagicMock()
        now = datetime.now()
        pc = PooledConnection(connection=conn, created_at=now, last_used=now)
        assert pc.connection is conn
        assert pc.created_at == now
        assert pc.in_use is False

    def test_pooled_connection_in_use_flag(self):
        """Test setting in_use flag."""
        from education_system.university_system.infrastructure.database.db import PooledConnection
        conn = MagicMock()
        now = datetime.now()
        pc = PooledConnection(connection=conn, created_at=now, last_used=now, in_use=True)
        assert pc.in_use is True


# ---------------------------------------------------------------------------
# Test get_connection_pool global singleton
# ---------------------------------------------------------------------------

class TestGetConnectionPool:
    """Test get_connection_pool global factory."""

    def test_get_connection_pool_returns_pool(self, temp_db_path):
        """Test get_connection_pool returns a ConnectionPool."""
        import education_system.university_system.infrastructure.database.db as db_mod
        # Reset global pool
        old_pool = db_mod._connection_pool
        db_mod._connection_pool = None
        try:
            pool = db_mod.get_connection_pool(db_path=temp_db_path, max_connections=3)
            assert isinstance(pool, db_mod.ConnectionPool)
            pool.close_all()
        finally:
            db_mod._connection_pool = old_pool

    def test_get_connection_pool_singleton(self, temp_db_path):
        """Test get_connection_pool returns the same instance."""
        import education_system.university_system.infrastructure.database.db as db_mod
        old_pool = db_mod._connection_pool
        db_mod._connection_pool = None
        try:
            pool1 = db_mod.get_connection_pool(db_path=temp_db_path, max_connections=3)
            pool2 = db_mod.get_connection_pool()
            assert pool1 is pool2
            pool1.close_all()
        finally:
            db_mod._connection_pool = old_pool


# ---------------------------------------------------------------------------
# Test module __all__
# ---------------------------------------------------------------------------

class TestModuleExports:
    """Test module exports."""

    def test_all_is_defined(self):
        """Test __all__ is defined in db.py."""
        import education_system.university_system.infrastructure.database.db as db_mod
        assert hasattr(db_mod, '__all__')

    def test_all_contains_key_names(self):
        """Test __all__ contains all key public names."""
        from education_system.university_system.infrastructure.database.db import __all__
        expected = [
            'sqlite3', 'DatabaseManager', 'get_connection', 'get_db_connection',
            'DEFAULT_DB_PATH', 'DB_DIR', 'EXPORTS_DIR',
            'ConnectionPool', 'PooledConnection', 'get_connection_pool',
            'transaction', 'atomic_operation', 'savepoint',
        ]
        for name in expected:
            assert name in __all__, f"{name} missing from __all__"

    def test_all_names_accessible(self):
        """Test all names in __all__ can be accessed."""
        import education_system.university_system.infrastructure.database.db as db_mod
        for name in db_mod.__all__:
            assert hasattr(db_mod, name), f"{name} in __all__ but not accessible"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
