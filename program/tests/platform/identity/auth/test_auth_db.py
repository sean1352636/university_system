"""Tests for shared.auth.db — connect, get_connection, _secure_db_permissions."""

import os
import sqlite3
import stat

import pytest

from education_system.platform.identity.auth.db import connect, get_connection, _secure_db_permissions


class TestConnect:
    """Test the connect() helper."""

    def test_returns_connection(self, shared_auth_db):
        conn = connect(shared_auth_db)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_row_factory_is_row(self, shared_auth_db):
        conn = connect(shared_auth_db)
        assert conn.row_factory is sqlite3.Row
        conn.close()

    def test_wal_mode_enabled(self, shared_auth_db):
        conn = connect(shared_auth_db)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_foreign_keys_enabled(self, shared_auth_db):
        conn = connect(shared_auth_db)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_creates_parent_directories(self, tmp_path):
        deep = str(tmp_path / "a" / "b" / "test.db")
        conn = connect(deep)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()


class TestGetConnection:
    """Test the get_connection context manager."""

    def test_context_manager_yields_connection(self, shared_auth_db):
        with get_connection(shared_auth_db) as conn:
            assert isinstance(conn, sqlite3.Connection)

    def test_commit_mode(self, tmp_path):
        db = str(tmp_path / "cm.db")
        conn = connect(db)
        conn.execute("CREATE TABLE t (x TEXT)")
        conn.commit()
        conn.close()

        with get_connection(db, commit=True) as conn:
            conn.execute("INSERT INTO t VALUES ('hello')")

        # Verify committed
        conn2 = connect(db)
        row = conn2.execute("SELECT x FROM t").fetchone()
        assert row[0] == "hello"
        conn2.close()

    def test_rollback_on_error(self, tmp_path):
        db = str(tmp_path / "rb.db")
        conn = connect(db)
        conn.execute("CREATE TABLE t (x TEXT)")
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError):
            with get_connection(db, commit=True) as conn:
                conn.execute("INSERT INTO t VALUES ('should_rollback')")
                raise RuntimeError("boom")

        conn2 = connect(db)
        row = conn2.execute("SELECT COUNT(*) FROM t").fetchone()
        assert row[0] == 0
        conn2.close()


class TestSecureDbPermissions:
    """Test _secure_db_permissions sets chmod 600."""

    def test_sets_600(self, tmp_path):
        db_file = tmp_path / "perm.db"
        db_file.write_text("")
        os.chmod(db_file, 0o644)

        _secure_db_permissions(str(db_file))

        mode = stat.S_IMODE(os.stat(db_file).st_mode)
        assert mode == 0o600

    def test_nonexistent_file_no_error(self, tmp_path):
        _secure_db_permissions(str(tmp_path / "missing.db"))
