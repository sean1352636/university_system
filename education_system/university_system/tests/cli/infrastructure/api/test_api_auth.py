#!/usr/bin/env python3
"""
Comprehensive tests for the API JWT authentication module.

Tests cover:
- Access and refresh token creation with correct payload fields
- Token decoding (valid, expired, invalid signature)
- Token blacklist add and check
- Bearer token extraction from Authorization header
- @token_required decorator (valid, missing, expired, invalid, blacklisted, refresh-type)
- @admin_required decorator (admin passes, non-admin rejected)
- In-memory rate limiter (disabled, within limit, exceeds limit, window expiry)
- Isolation: _blacklisted_tokens and _rate_limit_store cleared between tests
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

import jwt as pyjwt
import pytest
from flask import Flask, g, jsonify

from education_system.university_system.api.auth import (
    _blacklisted_tokens,
    _rate_limit_store,
    admin_required,
    blacklist_token,
    check_rate_limit,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_token_blacklisted,
    token_required,
    _extract_bearer_token,
)


# ============================================================================
# Helpers and Fixtures
# ============================================================================

def _make_config(
    secret_key="test-secret-key-for-jwt",
    algorithm="HS256",
    access_minutes=30,
    refresh_days=7,
    rate_enabled=True,
    rpm=100,
):
    """Build a config dict matching the expected format."""
    return {
        "jwt": {
            "secret_key": secret_key,
            "algorithm": algorithm,
            "access_token_expires_minutes": access_minutes,
            "refresh_token_expires_days": refresh_days,
        },
        "rate_limiting": {
            "enabled": rate_enabled,
            "requests_per_minute": rpm,
        },
    }


def _make_user(username="jdoe", user_id=42, role="student"):
    """Build a minimal user dict."""
    return {"username": username, "id": user_id, "role": role}


@pytest.fixture(autouse=True)
def _clean_global_state():
    """Clear module-level mutable state before *and* after every test."""
    _blacklisted_tokens.clear()
    _rate_limit_store.clear()
    yield
    _blacklisted_tokens.clear()
    _rate_limit_store.clear()


@pytest.fixture
def app():
    """Create a minimal Flask test application."""
    application = Flask(__name__)
    application.config["TESTING"] = True
    application.config["API_CONFIG"] = _make_config()
    return application


@pytest.fixture
def config():
    """Return a default config dict."""
    return _make_config()


@pytest.fixture
def user():
    """Return a default user dict."""
    return _make_user()


@pytest.fixture
def admin_user():
    """Return an admin user dict."""
    return _make_user(username="admin", user_id=1, role="admin")


# ============================================================================
# Token Creation Tests
# ============================================================================

class TestCreateAccessToken:
    """Tests for create_access_token()."""

    def test_returns_string(self, user, config):
        """Access token should be a non-empty string."""
        token = create_access_token(user, config)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_payload_contains_required_fields(self, user, config):
        """Decoded payload must include sub, user_id, role, type, iat, exp."""
        token = create_access_token(user, config)
        payload = pyjwt.decode(
            token, config["jwt"]["secret_key"], algorithms=["HS256"]
        )
        assert payload["sub"] == user["username"]
        assert payload["user_id"] == user["id"]
        assert payload["role"] == user["role"]
        assert payload["type"] == "access"
        assert "iat" in payload
        assert "exp" in payload

    def test_token_type_is_access(self, user, config):
        """Token type field must be 'access'."""
        token = create_access_token(user, config)
        payload = pyjwt.decode(
            token, config["jwt"]["secret_key"], algorithms=["HS256"]
        )
        assert payload["type"] == "access"

    def test_expiry_matches_config(self, user):
        """Expiration should be approximately access_token_expires_minutes from now."""
        cfg = _make_config(access_minutes=15)
        before = datetime.now(timezone.utc)
        token = create_access_token(user, cfg)
        after = datetime.now(timezone.utc)

        payload = pyjwt.decode(
            token, cfg["jwt"]["secret_key"], algorithms=["HS256"]
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp >= before + timedelta(minutes=15) - timedelta(seconds=2)
        assert exp <= after + timedelta(minutes=15) + timedelta(seconds=2)

    def test_different_users_produce_different_tokens(self, config):
        """Two different users must not generate the same token."""
        t1 = create_access_token(_make_user(username="alice", user_id=1), config)
        t2 = create_access_token(_make_user(username="bob", user_id=2), config)
        assert t1 != t2

    def test_custom_algorithm(self, user):
        """Token should respect a custom algorithm from config."""
        cfg = _make_config(algorithm="HS384")
        token = create_access_token(user, cfg)
        payload = pyjwt.decode(
            token, cfg["jwt"]["secret_key"], algorithms=["HS384"]
        )
        assert payload["sub"] == user["username"]

    def test_default_algorithm_fallback(self, user):
        """When algorithm is missing from config, HS256 should be used."""
        cfg = _make_config()
        del cfg["jwt"]["algorithm"]
        token = create_access_token(user, cfg)
        payload = pyjwt.decode(
            token, cfg["jwt"]["secret_key"], algorithms=["HS256"]
        )
        assert payload["type"] == "access"

    def test_default_expiry_fallback(self, user):
        """When access_token_expires_minutes is missing, 30 minutes should be used."""
        cfg = _make_config()
        del cfg["jwt"]["access_token_expires_minutes"]
        before = datetime.now(timezone.utc)
        token = create_access_token(user, cfg)

        payload = pyjwt.decode(
            token, cfg["jwt"]["secret_key"], algorithms=["HS256"]
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp >= before + timedelta(minutes=29)
        assert exp <= before + timedelta(minutes=31)


class TestCreateRefreshToken:
    """Tests for create_refresh_token()."""

    def test_returns_string(self, user, config):
        """Refresh token should be a non-empty string."""
        token = create_refresh_token(user, config)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_payload_contains_required_fields(self, user, config):
        """Decoded payload must include sub, user_id, type, iat, exp."""
        token = create_refresh_token(user, config)
        payload = pyjwt.decode(
            token, config["jwt"]["secret_key"], algorithms=["HS256"]
        )
        assert payload["sub"] == user["username"]
        assert payload["user_id"] == user["id"]
        assert payload["type"] == "refresh"
        assert "iat" in payload
        assert "exp" in payload

    def test_token_type_is_refresh(self, user, config):
        """Token type field must be 'refresh'."""
        token = create_refresh_token(user, config)
        payload = pyjwt.decode(
            token, config["jwt"]["secret_key"], algorithms=["HS256"]
        )
        assert payload["type"] == "refresh"

    def test_refresh_does_not_contain_role(self, user, config):
        """Refresh tokens must NOT include the role claim."""
        token = create_refresh_token(user, config)
        payload = pyjwt.decode(
            token, config["jwt"]["secret_key"], algorithms=["HS256"]
        )
        assert "role" not in payload

    def test_expiry_matches_config(self, user):
        """Expiration should be approximately refresh_token_expires_days from now."""
        cfg = _make_config(refresh_days=14)
        before = datetime.now(timezone.utc)
        token = create_refresh_token(user, cfg)

        payload = pyjwt.decode(
            token, cfg["jwt"]["secret_key"], algorithms=["HS256"]
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp >= before + timedelta(days=14) - timedelta(seconds=2)
        assert exp <= before + timedelta(days=14) + timedelta(seconds=2)

    def test_default_expiry_fallback(self, user):
        """When refresh_token_expires_days is missing, 7 days should be used."""
        cfg = _make_config()
        del cfg["jwt"]["refresh_token_expires_days"]
        before = datetime.now(timezone.utc)
        token = create_refresh_token(user, cfg)

        payload = pyjwt.decode(
            token, cfg["jwt"]["secret_key"], algorithms=["HS256"]
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp >= before + timedelta(days=6, hours=23)
        assert exp <= before + timedelta(days=7, seconds=5)


# ============================================================================
# Token Decoding Tests
# ============================================================================

class TestDecodeToken:
    """Tests for decode_token()."""

    def test_valid_token_decodes_successfully(self, user, config):
        """A freshly created token should decode without error."""
        token = create_access_token(user, config)
        payload = decode_token(token, config)
        assert payload["sub"] == user["username"]
        assert payload["user_id"] == user["id"]

    def test_expired_token_raises(self, user):
        """An expired token must raise jwt.ExpiredSignatureError."""
        cfg = _make_config()
        expired_payload = {
            "sub": user["username"],
            "user_id": user["id"],
            "role": user["role"],
            "type": "access",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = pyjwt.encode(
            expired_payload, cfg["jwt"]["secret_key"], algorithm="HS256"
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token, cfg)

    def test_invalid_signature_raises(self, user, config):
        """A token signed with a different secret must raise InvalidTokenError."""
        token = create_access_token(user, config)
        wrong_config = _make_config(secret_key="wrong-secret-key")
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_token(token, wrong_config)

    def test_malformed_token_raises(self, config):
        """A completely malformed string must raise InvalidTokenError."""
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_token("not.a.valid.jwt.at.all", config)

    def test_empty_token_raises(self, config):
        """An empty string must raise an error."""
        with pytest.raises(pyjwt.exceptions.DecodeError):
            decode_token("", config)

    def test_tampered_payload_raises(self, user, config):
        """A token whose payload has been tampered with must be rejected."""
        token = create_access_token(user, config)
        parts = token.split(".")
        # Tamper with the payload portion
        parts[1] = parts[1][::-1]
        tampered = ".".join(parts)
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_token(tampered, config)


# ============================================================================
# Token Blacklist Tests
# ============================================================================

class TestBlacklistToken:
    """Tests for blacklist_token() and is_token_blacklisted()."""

    def test_new_token_is_not_blacklisted(self, user, config):
        """A freshly created token should not be blacklisted."""
        token = create_access_token(user, config)
        assert is_token_blacklisted(token) is False

    def test_blacklisted_token_is_detected(self, user, config):
        """After blacklisting, the token should be detected."""
        token = create_access_token(user, config)
        blacklist_token(token)
        assert is_token_blacklisted(token) is True

    def test_blacklist_is_idempotent(self, user, config):
        """Blacklisting the same token twice should not cause errors."""
        token = create_access_token(user, config)
        blacklist_token(token)
        blacklist_token(token)
        assert is_token_blacklisted(token) is True

    def test_different_tokens_are_independent(self, user, config):
        """Blacklisting one token must not affect another."""
        t1 = create_access_token(user, config)
        t2 = create_access_token(_make_user(username="other", user_id=99), config)
        blacklist_token(t1)
        assert is_token_blacklisted(t1) is True
        assert is_token_blacklisted(t2) is False

    def test_arbitrary_string_can_be_blacklisted(self):
        """The blacklist should work with arbitrary token strings."""
        blacklist_token("some-opaque-string")
        assert is_token_blacklisted("some-opaque-string") is True
        assert is_token_blacklisted("something-else") is False

    def test_clean_state_fixture_clears_blacklist(self, user, config):
        """Verify the autouse fixture provides a clean blacklist."""
        assert len(_blacklisted_tokens) == 0


# ============================================================================
# Bearer Token Extraction Tests
# ============================================================================

class TestExtractBearerToken:
    """Tests for _extract_bearer_token()."""

    def test_valid_bearer_header(self, app):
        """A proper 'Bearer <token>' header returns the token."""
        with app.test_request_context(
            headers={"Authorization": "Bearer abc123xyz"}
        ):
            assert _extract_bearer_token() == "abc123xyz"

    def test_missing_authorization_header(self, app):
        """No Authorization header returns None."""
        with app.test_request_context():
            assert _extract_bearer_token() is None

    def test_empty_authorization_header(self, app):
        """An empty Authorization header returns None."""
        with app.test_request_context(headers={"Authorization": ""}):
            assert _extract_bearer_token() is None

    def test_non_bearer_scheme(self, app):
        """A 'Basic' scheme (not Bearer) returns None."""
        with app.test_request_context(
            headers={"Authorization": "Basic dXNlcjpwYXNz"}
        ):
            assert _extract_bearer_token() is None

    def test_bearer_lowercase_rejected(self, app):
        """'bearer' (lowercase) must not be accepted."""
        with app.test_request_context(
            headers={"Authorization": "bearer some-token"}
        ):
            assert _extract_bearer_token() is None

    def test_bearer_without_space(self, app):
        """'BearerTOKEN' (no space) must not match."""
        with app.test_request_context(
            headers={"Authorization": "BearerTOKEN"}
        ):
            assert _extract_bearer_token() is None

    def test_bearer_with_extra_spaces(self, app):
        """'Bearer  tok' with double space returns ' tok' (leading space)."""
        with app.test_request_context(
            headers={"Authorization": "Bearer  tok"}
        ):
            # The implementation slices at index 7, so an extra space is included
            result = _extract_bearer_token()
            assert result == " tok"

    def test_bearer_empty_token(self, app):
        """'Bearer ' with trailing space returns empty string."""
        with app.test_request_context(
            headers={"Authorization": "Bearer "}
        ):
            result = _extract_bearer_token()
            assert result == ""


# ============================================================================
# @token_required Decorator Tests
# ============================================================================

class TestTokenRequired:
    """Tests for the @token_required decorator."""

    @pytest.fixture
    def protected_app(self, app):
        """Flask app with a protected endpoint registered."""

        @app.route("/protected")
        @token_required
        def protected_view():
            return jsonify({"user": g.current_user["sub"]}), 200

        return app

    def test_valid_access_token_passes(self, protected_app, user, config):
        """Request with a valid access token should succeed (200)."""
        token = create_access_token(user, config)
        client = protected_app.test_client()
        resp = client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"] == user["username"]

    def test_missing_token_returns_401(self, protected_app):
        """Request without Authorization header returns 401."""
        client = protected_app.test_client()
        resp = client.get("/protected")
        assert resp.status_code == 401
        data = resp.get_json()
        assert "Missing authorization token" in data["error"]

    def test_expired_token_returns_401(self, protected_app, user):
        """An expired access token returns 401 with 'expired' message."""
        cfg = _make_config()
        expired_payload = {
            "sub": user["username"],
            "user_id": user["id"],
            "role": user["role"],
            "type": "access",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = pyjwt.encode(
            expired_payload, cfg["jwt"]["secret_key"], algorithm="HS256"
        )
        client = protected_app.test_client()
        resp = client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert "expired" in data["error"].lower()

    def test_invalid_token_returns_401(self, protected_app):
        """A garbage token returns 401 with 'Invalid token'."""
        client = protected_app.test_client()
        resp = client.get(
            "/protected",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert "Invalid token" in data["error"]

    def test_wrong_secret_returns_401(self, protected_app, user):
        """Token signed with a different secret is rejected."""
        wrong_cfg = _make_config(secret_key="totally-different-key")
        token = create_access_token(user, wrong_cfg)
        client = protected_app.test_client()
        resp = client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401

    def test_blacklisted_token_returns_401(self, protected_app, user, config):
        """A blacklisted token should be rejected with 'revoked' message."""
        token = create_access_token(user, config)
        blacklist_token(token)
        client = protected_app.test_client()
        resp = client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert "revoked" in data["error"].lower()

    def test_refresh_token_rejected_as_access(self, protected_app, user, config):
        """A refresh token must not be accepted by @token_required."""
        token = create_refresh_token(user, config)
        client = protected_app.test_client()
        resp = client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert "Invalid token type" in data["error"]

    def test_g_current_user_is_set(self, app, user, config):
        """After successful validation g.current_user must contain the payload."""
        token = create_access_token(user, config)
        captured = {}

        @app.route("/check-g")
        @token_required
        def check_g_view():
            captured["current_user"] = dict(g.current_user)
            captured["raw_token"] = g.raw_token
            return jsonify({"ok": True}), 200

        client = app.test_client()
        resp = client.get(
            "/check-g", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert captured["current_user"]["sub"] == user["username"]
        assert captured["current_user"]["user_id"] == user["id"]
        assert captured["current_user"]["role"] == user["role"]
        assert captured["raw_token"] == token

    def test_decorator_preserves_function_name(self):
        """@token_required should preserve the wrapped function's __name__."""

        @token_required
        def my_endpoint():
            pass  # pragma: no cover

        assert my_endpoint.__name__ == "my_endpoint"


# ============================================================================
# @admin_required Decorator Tests
# ============================================================================

class TestAdminRequired:
    """Tests for the @admin_required decorator."""

    @pytest.fixture
    def admin_app(self, app):
        """Flask app with an admin-only endpoint."""

        @app.route("/admin-only")
        @token_required
        @admin_required
        def admin_view():
            return jsonify({"admin": True}), 200

        return app

    def test_admin_user_passes(self, admin_app, admin_user, config):
        """A user with role='admin' should get 200."""
        token = create_access_token(admin_user, config)
        client = admin_app.test_client()
        resp = client.get(
            "/admin-only", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["admin"] is True

    def test_non_admin_user_rejected(self, admin_app, user, config):
        """A user with role='student' should get 403."""
        token = create_access_token(user, config)
        client = admin_app.test_client()
        resp = client.get(
            "/admin-only", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert "Admin access required" in data["error"]

    def test_missing_role_rejected(self, app, config):
        """A payload with no role at all should get 403."""

        @app.route("/admin-only-2")
        @token_required
        @admin_required
        def admin_view_2():
            return jsonify({"admin": True}), 200  # pragma: no cover

        # Craft a token whose role is missing by directly building the JWT
        payload = {
            "sub": "sneaky",
            "user_id": 999,
            "type": "access",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = pyjwt.encode(
            payload, config["jwt"]["secret_key"], algorithm="HS256"
        )
        client = app.test_client()
        resp = client.get(
            "/admin-only-2", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403

    def test_non_admin_role_variations(self, admin_app, config):
        """Various non-admin roles should all be rejected."""
        for role in ("student", "instructor", "staff", "viewer", ""):
            u = _make_user(username=f"user_{role}", user_id=100, role=role)
            token = create_access_token(u, config)
            client = admin_app.test_client()
            resp = client.get(
                "/admin-only", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 403, f"Role '{role}' should be rejected"

    def test_decorator_preserves_function_name(self):
        """@admin_required should preserve the wrapped function's __name__."""

        @admin_required
        def my_admin_view():
            pass  # pragma: no cover

        assert my_admin_view.__name__ == "my_admin_view"


# ============================================================================
# Rate Limiter Tests
# ============================================================================

class TestCheckRateLimit:
    """Tests for check_rate_limit()."""

    def test_rate_limiting_disabled_returns_none(self, app):
        """When rate_limiting.enabled is False, no limiting occurs."""
        cfg = _make_config(rate_enabled=False)
        with app.test_request_context(environ_base={"REMOTE_ADDR": "1.2.3.4"}):
            result = check_rate_limit(cfg)
            assert result is None

    def test_rate_limiting_missing_config_returns_none(self, app):
        """When rate_limiting section is absent, no limiting occurs."""
        cfg = {"jwt": _make_config()["jwt"]}
        with app.test_request_context(environ_base={"REMOTE_ADDR": "1.2.3.4"}):
            result = check_rate_limit(cfg)
            assert result is None

    def test_within_limit_returns_none(self, app):
        """Requests within the limit should return None (allowed)."""
        cfg = _make_config(rate_enabled=True, rpm=10)
        with app.test_request_context(environ_base={"REMOTE_ADDR": "10.0.0.1"}):
            for _ in range(10):
                result = check_rate_limit(cfg)
                assert result is None

    def test_exceeds_limit_returns_429(self, app):
        """The (rpm+1)-th request should return a 429 response."""
        cfg = _make_config(rate_enabled=True, rpm=5)
        with app.test_request_context(environ_base={"REMOTE_ADDR": "10.0.0.2"}):
            for _ in range(5):
                assert check_rate_limit(cfg) is None
            result = check_rate_limit(cfg)
            assert result is not None
            response, status_code = result
            assert status_code == 429
            data = response.get_json()
            assert "Rate limit exceeded" in data["error"]

    def test_different_ips_are_independent(self, app):
        """Rate limits should be tracked per IP address."""
        cfg = _make_config(rate_enabled=True, rpm=3)
        with app.test_request_context(environ_base={"REMOTE_ADDR": "192.168.1.1"}):
            for _ in range(3):
                check_rate_limit(cfg)
            # IP 1 is now at the limit
            result = check_rate_limit(cfg)
            assert result is not None

        with app.test_request_context(environ_base={"REMOTE_ADDR": "192.168.1.2"}):
            result = check_rate_limit(cfg)
            assert result is None

    def test_window_expiry_resets_count(self, app):
        """Timestamps older than 60 seconds should be pruned from the window."""
        cfg = _make_config(rate_enabled=True, rpm=2)
        ip = "10.0.0.3"
        # Pre-fill the store with old timestamps (> 60 s ago)
        _rate_limit_store[ip] = [time.time() - 120, time.time() - 90]

        with app.test_request_context(environ_base={"REMOTE_ADDR": ip}):
            result = check_rate_limit(cfg)
            assert result is None

        # The old entries should have been pruned; only the new one remains
        assert len(_rate_limit_store[ip]) == 1

    def test_store_tracks_timestamps(self, app):
        """Each call should record a timestamp in _rate_limit_store."""
        cfg = _make_config(rate_enabled=True, rpm=100)
        ip = "10.0.0.4"
        with app.test_request_context(environ_base={"REMOTE_ADDR": ip}):
            check_rate_limit(cfg)
            check_rate_limit(cfg)
            check_rate_limit(cfg)
        assert len(_rate_limit_store[ip]) == 3

    def test_unknown_ip_uses_fallback(self, app):
        """When remote_addr is None the key 'unknown' should be used."""
        cfg = _make_config(rate_enabled=True, rpm=100)
        with app.test_request_context():
            # Flask test_request_context may set REMOTE_ADDR; override it
            from flask import request as flask_request
            with patch.object(flask_request, "remote_addr", new=None):
                check_rate_limit(cfg)
        assert "unknown" in _rate_limit_store

    def test_exactly_at_limit_is_allowed(self, app):
        """Exactly rpm requests should all succeed; the (rpm+1)-th fails."""
        cfg = _make_config(rate_enabled=True, rpm=1)
        with app.test_request_context(environ_base={"REMOTE_ADDR": "10.0.0.5"}):
            first = check_rate_limit(cfg)
            assert first is None  # 1st request is allowed (count == 1 == rpm)
            second = check_rate_limit(cfg)
            assert second is not None  # 2nd request exceeds (count == 2 > rpm)

    def test_clean_state_fixture_clears_store(self):
        """Verify the autouse fixture provides a clean rate-limit store."""
        assert len(_rate_limit_store) == 0


# ============================================================================
# Integration / End-to-End Scenarios
# ============================================================================

class TestAuthIntegration:
    """Cross-cutting integration scenarios."""

    def test_full_lifecycle_access_token(self, app, user, config):
        """Create -> use -> blacklist -> reject lifecycle."""

        @app.route("/lifecycle")
        @token_required
        def lifecycle_view():
            return jsonify({"ok": True}), 200

        token = create_access_token(user, config)
        client = app.test_client()

        # 1. Token works initially
        resp = client.get(
            "/lifecycle", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200

        # 2. Blacklist it
        blacklist_token(token)

        # 3. Subsequent request is rejected
        resp = client.get(
            "/lifecycle", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401

    def test_refresh_token_cannot_access_protected_route(self, app, user, config):
        """Refresh tokens must not pass @token_required."""

        @app.route("/access-only")
        @token_required
        def access_only():
            return jsonify({"ok": True}), 200

        refresh = create_refresh_token(user, config)
        client = app.test_client()
        resp = client.get(
            "/access-only", headers={"Authorization": f"Bearer {refresh}"}
        )
        assert resp.status_code == 401

    def test_rate_limit_and_auth_combined(self, app, user):
        """Demonstrate rate limiting alongside authentication."""
        cfg = _make_config(rate_enabled=True, rpm=3)
        app.config["API_CONFIG"] = cfg

        @app.route("/rate-and-auth")
        @token_required
        def rate_and_auth_view():
            limit_resp = check_rate_limit(cfg)
            if limit_resp is not None:
                return limit_resp
            return jsonify({"ok": True}), 200

        token = create_access_token(user, cfg)
        client = app.test_client()

        for _ in range(3):
            resp = client.get(
                "/rate-and-auth",
                headers={"Authorization": f"Bearer {token}"},
                environ_base={"REMOTE_ADDR": "10.0.0.99"},
            )
            assert resp.status_code == 200

        # The 4th request should hit the rate limit
        resp = client.get(
            "/rate-and-auth",
            headers={"Authorization": f"Bearer {token}"},
            environ_base={"REMOTE_ADDR": "10.0.0.99"},
        )
        assert resp.status_code == 429


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
