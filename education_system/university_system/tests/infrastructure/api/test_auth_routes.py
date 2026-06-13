"""Comprehensive tests for auth_routes: login, logout, refresh, me."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from flask import Flask

from education_system.shared.api.university.auth import _blacklisted_tokens
from education_system.shared.api.university.errors import register_error_handlers
from education_system.shared.api.university.routes.auth_routes import auth_bp
from education_system.university_system.core.exceptions import InvalidCredentialsError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECRET = "test-secret-key-for-unit-tests"

_JWT_CONFIG = {
    "jwt": {
        "secret_key": _SECRET,
        "access_token_expires_minutes": 30,
        "refresh_token_expires_days": 7,
        "algorithm": "HS256",
    },
    "rate_limiting": {"enabled": False},
}

_FAKE_USER = {
    "username": "testuser",
    "id": 42,
    "role": "student",
}


def _make_access_token(sub="testuser", user_id=42, role="student", expired=False):
    """Create a real JWT access token for testing."""
    if expired:
        exp = datetime.now(timezone.utc) - timedelta(hours=1)
    else:
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": sub,
        "user_id": user_id,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": exp,
    }
    return pyjwt.encode(payload, _SECRET, algorithm="HS256")


def _auth_header(token=None):
    if token is None:
        token = _make_access_token()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["API_CONFIG"] = _JWT_CONFIG
    register_error_handlers(app)
    app.register_blueprint(auth_bp)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clear_blacklist():
    _blacklisted_tokens.clear()
    yield
    _blacklisted_tokens.clear()


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------

class TestLogin:

    @patch("education_system.shared.api.university.routes.auth_routes.log_login")
    @patch("education_system.shared.api.university.routes.auth_routes.get_auth")
    def test_successful_login(self, mock_get_auth, mock_log_login, client):
        auth = MagicMock()
        auth.login.return_value = True
        auth.get_current_user.return_value = _FAKE_USER
        auth.logout.return_value = None
        mock_get_auth.return_value = auth

        resp = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "pass123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["role"] == "student"
        assert data["user"]["user_id"] == 42
        mock_log_login.assert_called_once_with("testuser", success=True)

    def test_login_missing_username(self, client):
        resp = client.post("/api/auth/login", json={"password": "pass123"})
        assert resp.status_code == 400

    def test_login_missing_password(self, client):
        resp = client.post("/api/auth/login", json={"username": "testuser"})
        assert resp.status_code == 400

    def test_login_empty_body(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400

    def test_login_no_json(self, client):
        resp = client.post("/api/auth/login", data="not json")
        assert resp.status_code == 400

    @patch("education_system.shared.api.university.routes.auth_routes.get_auth")
    def test_login_invalid_credentials(self, mock_get_auth, client):
        auth = MagicMock()
        auth.login.side_effect = InvalidCredentialsError("Bad creds")
        mock_get_auth.return_value = auth

        resp = client.post(
            "/api/auth/login",
            json={"username": "bad", "password": "wrong"},
        )
        assert resp.status_code == 401

    @patch("education_system.shared.api.university.routes.auth_routes.get_auth")
    def test_login_password_reset_required(self, mock_get_auth, client):
        auth = MagicMock()
        auth.login.return_value = "password_reset_required"
        mock_get_auth.return_value = auth

        resp = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "expired"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["password_reset_required"] is True

    @patch("education_system.shared.api.university.routes.auth_routes.MFAService")
    @patch("education_system.shared.api.university.routes.auth_routes.create_mfa_token", return_value="mfa-test-token")
    @patch("education_system.shared.api.university.routes.auth_routes.get_auth")
    def test_login_requires_2fa(self, mock_get_auth, mock_mfa_token, mock_mfa_svc, client):
        auth = MagicMock()
        auth.login.return_value = {"requires_2fa": True, "username": "testuser", "user_id": 42}
        mock_get_auth.return_value = auth

        mfa_svc = MagicMock()
        mfa_svc.get_user_mfa_methods.return_value = {"success": True, "methods": []}
        mock_mfa_svc.return_value = mfa_svc

        resp = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "pass"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mfa_required"] is True
        assert "Two-factor" in data["message"]

    @patch("education_system.shared.api.university.routes.auth_routes.log_login")
    @patch("education_system.shared.api.university.routes.auth_routes.get_auth")
    def test_login_logout_failure_is_swallowed(self, mock_get_auth, mock_log, client):
        """auth.logout() failing should not break the login response."""
        auth = MagicMock()
        auth.login.return_value = True
        auth.get_current_user.return_value = _FAKE_USER
        auth.logout.side_effect = RuntimeError("session error")
        mock_get_auth.return_value = auth

        resp = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "pass123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()

    def test_login_get_not_allowed(self, client):
        resp = client.get("/api/auth/login")
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# Logout tests
# ---------------------------------------------------------------------------

class TestLogout:

    @patch("education_system.shared.api.university.routes.auth_routes.log_activity")
    def test_successful_logout(self, mock_log, client):
        token = _make_access_token()
        resp = client.post("/api/auth/logout", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "logged out" in data["message"].lower()
        mock_log.assert_called_once()
        # Token should be blacklisted after logout
        assert token in _blacklisted_tokens

    def test_logout_requires_auth_token(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401

    def test_logout_with_expired_token(self, client):
        token = _make_access_token(expired=True)
        resp = client.post("/api/auth/logout", headers=_auth_header(token))
        assert resp.status_code == 401

    def test_logout_with_invalid_token(self, client):
        resp = client.post("/api/auth/logout", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401

    @patch("education_system.shared.api.university.routes.auth_routes.log_activity")
    def test_logout_with_blacklisted_token(self, mock_log, client):
        token = _make_access_token()
        _blacklisted_tokens.add(token)
        resp = client.post("/api/auth/logout", headers=_auth_header(token))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Refresh tests
# ---------------------------------------------------------------------------

class TestRefresh:

    @patch("education_system.shared.api.university.routes.auth_routes.create_access_token")
    @patch("education_system.shared.api.university.routes.auth_routes.decode_token")
    @patch("education_system.shared.api.university.routes.auth_routes.is_token_blacklisted", return_value=False)
    def test_successful_refresh(self, _bl, mock_decode, mock_create, client):
        mock_decode.return_value = {
            "sub": "testuser",
            "user_id": 42,
            "role": "student",
            "type": "refresh",
        }
        mock_create.return_value = "new-access-token"

        resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "valid-refresh"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["access_token"] == "new-access-token"

    def test_refresh_missing_token(self, client):
        resp = client.post("/api/auth/refresh", json={})
        assert resp.status_code == 400
        assert "refresh_token" in resp.get_json()["error"].lower()

    @patch("education_system.shared.api.university.routes.auth_routes.is_token_blacklisted", return_value=True)
    def test_refresh_blacklisted_token(self, _bl, client):
        resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "revoked-token"},
        )
        assert resp.status_code == 401
        assert "revoked" in resp.get_json()["error"].lower()

    @patch("education_system.shared.api.university.routes.auth_routes.decode_token")
    @patch("education_system.shared.api.university.routes.auth_routes.is_token_blacklisted", return_value=False)
    def test_refresh_invalid_token(self, _bl, mock_decode, client):
        mock_decode.side_effect = Exception("bad token")

        resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "garbage"},
        )
        assert resp.status_code == 401
        assert "invalid" in resp.get_json()["error"].lower()

    @patch("education_system.shared.api.university.routes.auth_routes.decode_token")
    @patch("education_system.shared.api.university.routes.auth_routes.is_token_blacklisted", return_value=False)
    def test_refresh_wrong_token_type(self, _bl, mock_decode, client):
        mock_decode.return_value = {
            "sub": "testuser",
            "user_id": 42,
            "type": "access",  # wrong type
        }
        resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "access-token-value"},
        )
        assert resp.status_code == 401
        assert "invalid token type" in resp.get_json()["error"].lower()

    @patch("education_system.shared.api.university.routes.auth_routes.create_access_token")
    @patch("education_system.shared.api.university.routes.auth_routes.decode_token")
    @patch("education_system.shared.api.university.routes.auth_routes.is_token_blacklisted", return_value=False)
    def test_refresh_default_role(self, _bl, mock_decode, mock_create, client):
        """When role is missing from payload, it should default to 'student'."""
        mock_decode.return_value = {
            "sub": "testuser",
            "user_id": 42,
            "type": "refresh",
        }
        mock_create.return_value = "tok"

        resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "valid"},
        )
        assert resp.status_code == 200
        call_args = mock_create.call_args[0][0]
        assert call_args["role"] == "student"

    def test_refresh_no_json_body(self, client):
        resp = client.post("/api/auth/refresh", data="not json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Me endpoint
# ---------------------------------------------------------------------------

class TestMe:

    def test_me_without_token_returns_401(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_returns_user_info(self, client):
        token = _make_access_token(sub="testuser", user_id=42, role="student")
        resp = client.get("/api/auth/me", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "testuser"
        assert data["user_id"] == 42
        assert data["role"] == "student"

    def test_me_with_admin_role(self, client):
        token = _make_access_token(sub="admin", user_id=1, role="admin")
        resp = client.get("/api/auth/me", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["role"] == "admin"

    def test_me_with_expired_token(self, client):
        token = _make_access_token(expired=True)
        resp = client.get("/api/auth/me", headers=_auth_header(token))
        assert resp.status_code == 401
