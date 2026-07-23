"""Tests for the forced-password-change-on-first-login flag.

Seeded demo accounts ship with well-known weak passwords, so they are flagged
``must_change_password=1``. The login flow surfaces the flag, the GUI/CLI gates
force a change, and ``change_password`` clears it.
"""

import os
import shutil
import sys

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.shared.auth.core import UserAuth
from education_system.shared.auth.db import connect


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def _template_auth_db(tmp_path_factory):
    from education_system.shared.auth.schema import initialise_auth_db, seed_default_users
    path = str(tmp_path_factory.mktemp("mcp_tpl") / "template_auth.db")
    initialise_auth_db(path)
    seed_default_users(path)
    return path


@pytest.fixture
def auth_db(tmp_path, _template_auth_db):
    db_path = str(tmp_path / "test_auth.db")
    shutil.copy2(_template_auth_db, db_path)
    return db_path


@pytest.fixture
def auth(auth_db):
    return UserAuth(db_path=auth_db)


# ── Schema ────────────────────────────────────────────────────────────────

class TestSchema:
    def test_column_exists(self, auth_db):
        conn = connect(auth_db)
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        finally:
            conn.close()
        assert "must_change_password" in cols

    def test_reinit_is_idempotent(self, auth_db):
        # Re-running the initialiser must not error or drop data.
        from education_system.shared.auth.schema import initialise_auth_db
        initialise_auth_db(auth_db)
        initialise_auth_db(auth_db)
        conn = connect(auth_db)
        try:
            cnt = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        finally:
            conn.close()
        assert cnt > 0


# ── Seeded demo accounts are flagged ──────────────────────────────────────

class TestSeededAccountsFlagged:
    @pytest.mark.parametrize("username", ["admin", "staff", "S12345", "admin1", "superadmin"])
    def test_demo_account_flag_set_in_db(self, auth_db, username):
        conn = connect(auth_db)
        try:
            row = conn.execute(
                "SELECT must_change_password FROM users WHERE username = ?", (username,)
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row["must_change_password"] == 1

    def test_login_surfaces_flag(self, auth):
        result = auth.login("admin", "admin123")
        assert result.get("must_change_password") is True

    def test_flag_present_for_all_result_paths(self, auth):
        # Non-MFA demo login always carries the key (True/False), never missing.
        result = auth.login("admin1", "admin1234")
        assert "must_change_password" in result


# ── Newly created (non-demo) users are NOT flagged ────────────────────────

class TestNewUsersNotFlagged:
    def test_created_user_has_no_flag(self, auth):
        uid = auth.create_user(
            "freshuser", "Str0ng!Passw0rd", display_name="Fresh",
            email="fresh@example.com", systems=[("university", "student")],
        )
        assert uid
        result = auth.login("freshuser", "Str0ng!Passw0rd")
        assert not result.get("must_change_password")


# ── change_password clears the flag ───────────────────────────────────────

class TestChangePasswordClearsFlag:
    def test_flag_cleared_after_change(self, auth, auth_db):
        result = auth.login("admin", "admin123")
        assert result.get("must_change_password") is True

        auth.change_password(result["user_id"], "admin123", "Rotated!Pass123")

        # DB flag cleared
        conn = connect(auth_db)
        try:
            row = conn.execute(
                "SELECT must_change_password FROM users WHERE username = 'admin'"
            ).fetchone()
        finally:
            conn.close()
        assert row["must_change_password"] == 0

        # And a subsequent login no longer forces a change
        result2 = auth.login("admin", "Rotated!Pass123")
        assert not result2.get("must_change_password")
