"""Tests for the legacy→shared bcrypt self-migration hook.

When a university account authenticates via the legacy PBKDF2 path, it is
provisioned into the shared bcrypt auth DB so subsequent logins use the fast
shared path. These tests exercise ``UserAuth._migrate_legacy_to_shared`` in
isolation (without the heavy full UserAuth initialisation) using a stub ``self``
and a real shared auth database.
"""

import contextlib
import shutil
import sqlite3
import tempfile
import types
from pathlib import Path

import pytest

from education_system.post_18.university_system.infrastructure.auth.core import UserAuth as UniUserAuth
from education_system.shared.auth.core import UserAuth as SharedUserAuth
from education_system.shared.auth.schema import initialise_auth_db
from education_system.shared.auth.db import connect as shared_connect


@pytest.fixture
def shared_db(tmp_path):
    path = str(tmp_path / "shared_auth.db")
    initialise_auth_db(path)
    return path


@pytest.fixture
def uni_db(tmp_path):
    """Minimal university DB with a users table (role/email lookup source)."""
    path = str(tmp_path / "uni.db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, "
        "role TEXT, email TEXT)"
    )
    conn.execute(
        "INSERT INTO users (username, role, email) VALUES (?, ?, ?)",
        ("bob", "staff", "bob@uni.test"),
    )
    conn.commit()
    conn.close()
    return path


def _make_stub(shared_db, uni_db, current_user=None):
    """Build a lightweight object carrying just what the migration hook uses."""
    shared_auth = SharedUserAuth(db_path=shared_db)

    class _DBManager:
        def __init__(self, path):
            self._path = path

        @contextlib.contextmanager
        def get_connection(self):
            conn = sqlite3.connect(self._path)
            try:
                yield conn
            finally:
                conn.close()

    stub = types.SimpleNamespace(
        _shared_auth=shared_auth,
        db_manager=_DBManager(uni_db),
        session_manager=types.SimpleNamespace(current_user=current_user),
    )
    return stub, shared_auth


def _shared_user(shared_db, username):
    conn = shared_connect(shared_db)
    try:
        return conn.execute(
            "SELECT u.id, u.password_hash, u.legacy_salt, us.system_key, us.role "
            "FROM users u LEFT JOIN user_systems us ON us.user_id = u.id "
            "WHERE u.username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()


class TestLegacyMigration:
    def test_provisions_from_session_user(self, shared_db, uni_db):
        """result=True → role/display/email come from session_manager.current_user."""
        stub, _ = _make_stub(
            shared_db, uni_db,
            current_user={"role": "admin", "display_name": "Bob B", "email": "b@uni.test"},
        )
        UniUserAuth._migrate_legacy_to_shared(stub, "bob", "S3cret!pw", True)

        row = _shared_user(shared_db, "bob")
        assert row is not None
        assert row["password_hash"].startswith("$2")   # bcrypt
        assert row["legacy_salt"] is None
        assert (row["system_key"], row["role"]) == ("university", "admin")

    def test_provisions_from_uni_db_for_2fa_dict(self, shared_db, uni_db):
        """2FA dict result → current_user not set yet, role/email read from uni DB."""
        stub, _ = _make_stub(shared_db, uni_db, current_user=None)
        result = {"success": True, "requires_2fa": True, "user_id": 1, "username": "bob"}
        UniUserAuth._migrate_legacy_to_shared(stub, "bob", "S3cret!pw", result)

        row = _shared_user(shared_db, "bob")
        assert row is not None
        assert (row["system_key"], row["role"]) == ("university", "staff")  # from uni_db

    def test_then_login_via_fast_shared_path(self, shared_db, uni_db):
        stub, shared_auth = _make_stub(
            shared_db, uni_db, current_user={"role": "student"},
        )
        UniUserAuth._migrate_legacy_to_shared(stub, "carol", "Another1!", True)

        result = shared_auth.login("carol", "Another1!")
        assert result["username"] == "carol"
        assert {"system_key": "university", "role": "student"} in result["systems"]

    def test_no_shared_auth_is_noop(self, uni_db):
        stub = types.SimpleNamespace(_shared_auth=None)
        # Must not raise even though db_manager / session_manager are absent.
        UniUserAuth._migrate_legacy_to_shared(stub, "bob", "pw", True)

    def test_provision_failure_is_swallowed(self, shared_db, uni_db):
        stub, shared_auth = _make_stub(
            shared_db, uni_db, current_user={"role": "student"},
        )

        def _boom(*a, **k):
            raise RuntimeError("db exploded")

        shared_auth.provision_user = _boom
        # Migration failure must never propagate to the login flow.
        UniUserAuth._migrate_legacy_to_shared(stub, "dave", "pw", True)
        assert _shared_user(shared_db, "dave") is None
