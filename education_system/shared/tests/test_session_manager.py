"""Tests for shared.auth.session_manager — token lifecycle, expiry, invalidation."""

import os
import shutil
import sys

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.shared.auth.session_manager import SessionManager
from education_system.shared.auth.db import connect


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def _template_auth_db(tmp_path_factory):
    from education_system.shared.auth.schema import initialise_auth_db, seed_default_users
    path = str(tmp_path_factory.mktemp("sess_tpl") / "template_auth.db")
    initialise_auth_db(path)
    seed_default_users(path)
    return path


@pytest.fixture
def auth_db(tmp_path, _template_auth_db):
    db_path = str(tmp_path / "test_auth.db")
    shutil.copy2(_template_auth_db, db_path)
    return db_path


@pytest.fixture
def sm(auth_db):
    return SessionManager(db_path=auth_db)


@pytest.fixture
def user_id(auth_db):
    conn = connect(auth_db)
    uid = conn.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
    conn.close()
    return uid


# ── Creation ──────────────────────────────────────────────────────────────


class TestCreateSession:
    def test_returns_token_string(self, sm, user_id):
        token = sm.create_session(user_id)
        assert isinstance(token, str)
        assert len(token) >= 32

    def test_unique_tokens(self, sm, user_id):
        tokens = {sm.create_session(user_id) for _ in range(10)}
        assert len(tokens) == 10

    def test_valid_immediately(self, sm, user_id):
        token = sm.create_session(user_id)
        info = sm.validate_session(token)
        assert info is not None
        assert info["user_id"] == user_id


# ── Validation ────────────────────────────────────────────────────────────


class TestValidateSession:
    def test_valid_token(self, sm, user_id):
        token = sm.create_session(user_id)
        info = sm.validate_session(token)
        assert info["user_id"] == user_id
        assert "username" in info

    def test_invalid_token(self, sm):
        assert sm.validate_session("not-a-real-token") is None

    def test_empty_token(self, sm):
        assert sm.validate_session("") is None

    def test_expired_token(self, sm, user_id, auth_db):
        token = sm.create_session(user_id)
        conn = connect(auth_db)
        conn.execute(
            "UPDATE sessions SET expires_at = '2000-01-01T00:00:00' WHERE token = ?",
            (token,),
        )
        conn.commit()
        conn.close()
        assert sm.validate_session(token) is None


# ── Invalidation ──────────────────────────────────────────────────────────


class TestInvalidateSession:
    def test_invalidate_single(self, sm, user_id):
        token = sm.create_session(user_id)
        sm.invalidate_session(token)
        assert sm.validate_session(token) is None

    def test_invalidate_does_not_affect_other_sessions(self, sm, user_id):
        t1 = sm.create_session(user_id)
        t2 = sm.create_session(user_id)
        sm.invalidate_session(t1)
        assert sm.validate_session(t1) is None
        assert sm.validate_session(t2) is not None


class TestInvalidateUserSessions:
    def test_invalidates_all(self, sm, user_id):
        tokens = [sm.create_session(user_id) for _ in range(5)]
        sm.invalidate_user_sessions(user_id)
        for t in tokens:
            assert sm.validate_session(t) is None

    def test_does_not_affect_other_users(self, sm, auth_db):
        conn = connect(auth_db)
        rows = conn.execute("SELECT id FROM users LIMIT 2").fetchall()
        conn.close()
        uid1, uid2 = rows[0]["id"], rows[1]["id"]

        t1 = sm.create_session(uid1)
        t2 = sm.create_session(uid2)

        sm.invalidate_user_sessions(uid1)
        assert sm.validate_session(t1) is None
        assert sm.validate_session(t2) is not None


# ── Cleanup ───────────────────────────────────────────────────────────────


class TestCleanupExpired:
    def test_removes_expired(self, sm, user_id, auth_db):
        token = sm.create_session(user_id)
        conn = connect(auth_db)
        conn.execute(
            "UPDATE sessions SET expires_at = '2000-01-01T00:00:00' WHERE token = ?",
            (token,),
        )
        conn.commit()
        conn.close()

        sm.cleanup_expired()

        conn = connect(auth_db)
        row = conn.execute("SELECT id FROM sessions WHERE token = ?", (token,)).fetchone()
        conn.close()
        assert row is None

    def test_keeps_active(self, sm, user_id, auth_db):
        token = sm.create_session(user_id)
        sm.cleanup_expired()
        assert sm.validate_session(token) is not None


# ── Concurrent sessions ──────────────────────────────────────────────────


class TestConcurrentSessions:
    def test_multiple_valid_simultaneously(self, sm, user_id):
        tokens = [sm.create_session(user_id) for _ in range(3)]
        for t in tokens:
            assert sm.validate_session(t) is not None
