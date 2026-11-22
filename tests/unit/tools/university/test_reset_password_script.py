"""Tests for tools/university/reset_password.py: it resets logins in auth.db."""
import sqlite3
from unittest.mock import patch

import bcrypt
import pytest

from education_system.platform.identity.auth.core import UserAuth
from education_system.platform.identity.auth.schema import (
    initialise_auth_db,
    seed_default_users,
)
from tools.university import reset_password

STRONG = "N3w-Passw0rd!long"


@pytest.fixture
def auth_db(tmp_path, monkeypatch):
    """A real auth schema with the seeded accounts, in a temp file. Nothing is e-mailed."""
    monkeypatch.setenv("EDU_DEV_SEED", "true")
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    seed_default_users(path)
    with patch.object(UserAuth, "_notify_temporary_password", return_value=False):
        yield path


def _user(path, username):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()


def _matches(path, username, password):
    stored = _user(path, username)["password_hash"].encode()
    return bcrypt.checkpw(password.encode(), stored)


class TestResetUserPassword:
    def test_sets_a_bcrypt_password_the_login_accepts(self, auth_db):
        assert reset_password.reset_user_password("admin", STRONG, db_path=auth_db)
        assert _matches(auth_db, "admin", STRONG)

    def test_unlocks_the_account_and_marks_the_password_temporary(self, auth_db):
        conn = sqlite3.connect(auth_db)
        conn.execute(
            "UPDATE users SET failed_login_attempts = 3, locked_until = '2999-01-01' "
            "WHERE username = 'admin'"
        )
        conn.commit()
        conn.close()
        assert reset_password.reset_user_password("admin", STRONG, db_path=auth_db)
        row = _user(auth_db, "admin")
        assert row["failed_login_attempts"] == 0
        assert row["locked_until"] is None
        assert row["must_change_password"] == 1

    def test_does_not_reactivate_a_deactivated_account(self, auth_db, capsys):
        conn = sqlite3.connect(auth_db)
        conn.execute("UPDATE users SET is_active = 0 WHERE username = 'admin'")
        conn.commit()
        conn.close()
        assert reset_password.reset_user_password("admin", STRONG, db_path=auth_db)
        assert _user(auth_db, "admin")["is_active"] == 0
        assert "deactivated" in capsys.readouterr().out

    def test_refuses_a_weak_password(self, auth_db):
        before = _user(auth_db, "admin")["password_hash"]
        assert not reset_password.reset_user_password("admin", "weak", db_path=auth_db)
        assert _user(auth_db, "admin")["password_hash"] == before

    def test_returns_false_for_unknown_user(self, auth_db):
        assert not reset_password.reset_user_password("ghost", STRONG, db_path=auth_db)

    def test_missing_database_is_an_error_and_is_not_created(self, tmp_path):
        missing = tmp_path / "no.db"
        assert not reset_password.reset_user_password("admin", STRONG, db_path=str(missing))
        assert not missing.exists()


class TestResetDefaults:
    def test_refused_without_dev_seed(self, auth_db, monkeypatch):
        before = _user(auth_db, "admin")["password_hash"]
        monkeypatch.delenv("EDU_DEV_SEED")
        assert reset_password.reset_default_passwords(auth_db) == 0
        assert _user(auth_db, "admin")["password_hash"] == before

    def test_restores_documented_passwords_for_university_accounts(self, auth_db):
        assert reset_password.reset_user_password("admin", STRONG, db_path=auth_db)
        assert reset_password.reset_default_passwords(auth_db) >= 1
        assert _matches(auth_db, "admin", "admin123")
        assert _user(auth_db, "admin")["must_change_password"] == 0

    def test_leaves_other_systems_accounts_alone(self, auth_db):
        before = _user(auth_db, "admin3")["password_hash"]
        reset_password.reset_default_passwords(auth_db)
        assert _user(auth_db, "admin3")["password_hash"] == before


class TestListUsers:
    def test_lists_logins_without_hashes(self, auth_db, capsys):
        reset_password.list_users(auth_db)
        out = capsys.readouterr().out
        assert "admin" in out
        assert "university:admin" in out
        assert _user(auth_db, "admin")["password_hash"] not in out


class TestModuleSurface:
    def test_callables_exist(self):
        for name in (
            "reset_user_password",
            "reset_default_passwords",
            "list_users",
            "interactive_mode",
            "main",
        ):
            assert callable(getattr(reset_password, name))
