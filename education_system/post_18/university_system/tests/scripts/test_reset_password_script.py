"""Tests for university_system.scripts.reset_password."""
import sqlite3
from unittest.mock import patch

import pytest

from education_system.post_18.university_system.scripts import reset_password


def _make_user_db(path, username="admin"):
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE user_accounts (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            salt TEXT,
            updated_at TEXT,
            password_reset_required INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )"""
    )
    conn.execute(
        "INSERT INTO user_accounts (username, password_hash, salt, is_active) VALUES (?, 'old', 'oldsalt', 0)",
        (username,),
    )
    conn.commit()
    conn.close()


class TestHashPassword:
    def test_generates_salt_when_missing(self):
        salt, h = reset_password.hash_password("secret")
        assert salt and isinstance(salt, str)
        assert h and isinstance(h, str)
        assert len(h) == 128  # dklen=64 -> 128 hex chars

    def test_deterministic_with_same_salt(self):
        salt = "deadbeef"
        _, h1 = reset_password.hash_password("p", salt=salt)
        _, h2 = reset_password.hash_password("p", salt=salt)
        assert h1 == h2

    def test_different_passwords_different_hash(self):
        salt = "deadbeef"
        _, h1 = reset_password.hash_password("p1", salt=salt)
        _, h2 = reset_password.hash_password("p2", salt=salt)
        assert h1 != h2

    def test_different_salt_different_hash(self):
        _, h1 = reset_password.hash_password("p", salt="aa")
        _, h2 = reset_password.hash_password("p", salt="bb")
        assert h1 != h2


class TestResetUserPassword:
    def test_updates_existing_user(self, tmp_path):
        db = tmp_path / "auth.db"
        _make_user_db(db, "admin")
        assert reset_password.reset_user_password("admin", "newpass", db_path=str(db))
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT password_hash, salt, password_reset_required, is_active FROM user_accounts WHERE username='admin'"
        ).fetchone()
        conn.close()
        assert row[0] != "old"
        assert row[1] != "oldsalt"
        assert row[2] == 0
        assert row[3] == 1

    def test_returns_false_for_unknown_user(self, tmp_path):
        db = tmp_path / "auth.db"
        _make_user_db(db, "admin")
        assert not reset_password.reset_user_password("ghost", "x", db_path=str(db))

    def test_returns_false_on_sqlite_error(self, tmp_path):
        # Point at a non-existent path / unwritable DB
        assert not reset_password.reset_user_password(
            "admin", "x", db_path=str(tmp_path / "missing_dir" / "no.db")
        )


class TestModuleSurface:
    def test_callables_exist(self):
        for name in (
            "hash_password",
            "reset_user_password",
            "reset_default_passwords",
            "interactive_mode",
            "main",
        ):
            assert callable(getattr(reset_password, name))
