"""Comprehensive tests for user_routes: admin-gated user CRUD."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from flask import Flask

from education_system.platform.delivery.api.university.auth import _blacklisted_tokens
from education_system.platform.delivery.api.university.errors import register_error_handlers
from education_system.platform.delivery.api.university.routes.user_routes import user_bp, _row_to_dict, _SENSITIVE_FIELDS

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

_SECRET = "user-test-secret"
_API_CONFIG = {
    "jwt": {
        "secret_key": _SECRET,
        "access_token_expires_minutes": 30,
        "refresh_token_expires_days": 7,
        "algorithm": "HS256",
    },
    "rate_limiting": {"enabled": False},
}


def _token(sub="admin", user_id=1, role="admin"):
    payload = {
        "sub": sub,
        "user_id": user_id,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, _SECRET, algorithm="HS256")


def _headers(role="admin", user_id=1):
    return {"Authorization": f"Bearer {_token(role=role, user_id=user_id)}"}


def _admin_headers():
    return _headers(role="admin")


def _student_headers(user_id=99):
    return _headers(role="student", user_id=user_id)


# ---------------------------------------------------------------------------
# Fake DB row helper
# ---------------------------------------------------------------------------

class _FakeRow:
    """Mimics a sqlite3.Row with dict-like key access."""

    def __init__(self, data: dict):
        self._data = data

    def keys(self):
        return self._data.keys()

    def __getitem__(self, key):
        return self._data[key]


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["API_CONFIG"] = _API_CONFIG
    register_error_handlers(app)
    app.register_blueprint(user_bp)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clear():
    _blacklisted_tokens.clear()
    yield
    _blacklisted_tokens.clear()


# ---------------------------------------------------------------------------
# _row_to_dict helper
# ---------------------------------------------------------------------------

class TestRowToDict:

    def test_converts_row(self):
        row = _FakeRow({"id": 1, "username": "alice", "email": "a@b.com"})
        d = _row_to_dict(row)
        assert d["id"] == 1
        assert d["username"] == "alice"

    def test_strips_sensitive_fields(self):
        row = _FakeRow({"id": 1, "username": "alice", "password_hash": "xxx", "salt": "yyy"})
        d = _row_to_dict(row)
        assert "password_hash" not in d
        assert "salt" not in d

    def test_none_returns_empty_dict(self):
        assert _row_to_dict(None) == {}


# ---------------------------------------------------------------------------
# Authentication / authorization
# ---------------------------------------------------------------------------

class TestUserAuth:

    def test_list_requires_token(self, client):
        resp = client.get("/api/users")
        assert resp.status_code == 401

    def test_list_requires_admin(self, client):
        resp = client.get("/api/users", headers=_student_headers())
        assert resp.status_code == 403

    def test_create_requires_admin(self, client):
        resp = client.post("/api/users", json={}, headers=_student_headers())
        assert resp.status_code == 403

    def test_update_requires_admin(self, client):
        resp = client.put("/api/users/1", json={}, headers=_student_headers())
        assert resp.status_code == 403

    def test_delete_requires_admin(self, client):
        resp = client.delete("/api/users/1", headers=_student_headers())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# List users
# ---------------------------------------------------------------------------

class TestListUsers:

    @patch("education_system.platform.delivery.api.university.routes.user_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_list_all_paginated(self, mock_conn, mock_log, client):
        row1 = _FakeRow({"id": 1, "username": "alice", "role": "admin"})
        conn = MagicMock()
        # First call: SELECT * FROM users LIMIT ? OFFSET ?
        conn.execute.return_value.fetchall.return_value = [row1]
        # Second call: SELECT COUNT(*)
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, i: 1
        conn.execute.return_value.fetchone.return_value = count_row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/users", headers=_admin_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data
        assert "pagination" in data

    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_list_search(self, mock_conn, client):
        row = _FakeRow({"id": 2, "username": "bob", "email": "bob@uni.edu"})
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [row]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/users?search=bob", headers=_admin_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1

    @patch("education_system.platform.delivery.api.university.routes.user_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_list_filter_by_role(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, i: 0
        conn.execute.return_value.fetchone.return_value = count_row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/users?role=instructor", headers=_admin_headers())
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Get user
# ---------------------------------------------------------------------------

class TestGetUser:

    @patch("education_system.platform.delivery.api.university.routes.user_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_admin_can_get_any_user(self, mock_conn, mock_log, client):
        row = _FakeRow({"id": 99, "username": "student1", "role": "student"})
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/users/99", headers=_admin_headers())
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "student1"

    @patch("education_system.platform.delivery.api.university.routes.user_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_user_can_get_own_profile(self, mock_conn, mock_log, client):
        row = _FakeRow({"id": 99, "username": "student1", "role": "student"})
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        # user_id=99 matches the requested /api/users/99
        resp = client.get("/api/users/99", headers=_student_headers(user_id=99))
        assert resp.status_code == 200

    def test_student_cannot_get_other_user(self, client):
        # student user_id=99 trying to access /api/users/1
        resp = client.get("/api/users/1", headers=_student_headers(user_id=99))
        assert resp.status_code == 403

    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_get_nonexistent_user(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/users/999", headers=_admin_headers())
        assert resp.status_code == 400  # ValidationError -> 400


# ---------------------------------------------------------------------------
# Create user
# ---------------------------------------------------------------------------

class TestCreateUser:

    @patch("education_system.platform.delivery.api.university.routes.user_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_auth")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_create_success(self, mock_conn, mock_auth_fn, mock_log, client):
        conn = MagicMock()
        # First call: check existing -> None
        # Second call: fetch newly created user
        new_row = _FakeRow({"id": 5, "username": "newuser", "role": "student", "email": "new@uni.edu"})
        conn.execute.return_value.fetchone.side_effect = [None, new_row]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        auth = MagicMock()
        mock_auth_fn.return_value = auth

        resp = client.post(
            "/api/users",
            json={"username": "newuser", "password": "secret123", "role": "student"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 201
        assert resp.get_json()["username"] == "newuser"

    def test_create_missing_fields(self, client):
        resp = client.post(
            "/api/users",
            json={"username": "x"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 400

    def test_create_invalid_role(self, client):
        resp = client.post(
            "/api/users",
            json={"username": "x", "password": "p", "role": "superadmin"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 400

    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_create_duplicate_username(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = _FakeRow({"1": 1})
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/users",
            json={"username": "exists", "password": "p", "role": "student"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 400
        assert "already exists" in resp.get_json()["error"]

    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_auth")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_create_auth_failure(self, mock_conn, mock_auth_fn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        auth = MagicMock()
        auth.create_user.side_effect = Exception("db error")
        mock_auth_fn.return_value = auth

        resp = client.post(
            "/api/users",
            json={"username": "newuser", "password": "p", "role": "student"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 400
        assert "Failed to create user" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# Update user
# ---------------------------------------------------------------------------

class TestUpdateUser:

    @patch("education_system.platform.delivery.api.university.routes.user_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.transaction")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_update_success(self, mock_conn, mock_tx, mock_log, client):
        row = _FakeRow({"id": 1, "username": "alice", "role": "admin", "email": "a@b.com"})
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/users/1",
            json={"email": "new@b.com"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200

    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_update_nonexistent(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/users/999",
            json={"email": "x@b.com"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 400

    def test_update_empty_body(self, client):
        resp = client.put("/api/users/1", json={}, headers=_admin_headers())
        assert resp.status_code == 400

    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_update_no_valid_fields(self, mock_conn, client):
        row = _FakeRow({"id": 1, "username": "alice", "role": "admin"})
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/users/1",
            json={"bogus_field": "value"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 400

    def test_update_invalid_role(self, client):
        resp = client.put(
            "/api/users/1",
            json={"role": "superadmin"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Deactivate (DELETE) user
# ---------------------------------------------------------------------------

class TestDeactivateUser:

    @patch("education_system.platform.delivery.api.university.routes.user_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.transaction")
    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_deactivate_success(self, mock_conn, mock_tx, mock_log, client):
        row = _FakeRow({"id": 5, "username": "victim", "role": "student"})
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.delete("/api/users/5", headers=_admin_headers())
        assert resp.status_code == 200
        assert "deactivated" in resp.get_json()["message"].lower()

    @patch("education_system.platform.delivery.api.university.routes.user_routes.get_connection")
    def test_deactivate_nonexistent(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.delete("/api/users/999", headers=_admin_headers())
        assert resp.status_code == 400
