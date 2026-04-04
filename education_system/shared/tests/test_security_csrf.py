"""Tests for shared.security.csrf — CSRF token generation and validation."""

import pytest

from education_system.shared.security.csrf import (
    generate_csrf_token,
    validate_csrf_token,
)


class TestGenerateCsrfToken:
    """Test token generation."""

    def test_returns_string(self):
        token = generate_csrf_token("session-abc")
        assert isinstance(token, str)

    def test_contains_timestamp_and_signature(self):
        token = generate_csrf_token("session-123")
        parts = token.split(":", 1)
        assert len(parts) == 2
        assert parts[0].isdigit()

    def test_different_sessions_different_tokens(self):
        t1 = generate_csrf_token("session-a")
        t2 = generate_csrf_token("session-b")
        assert t1 != t2


class TestValidateCsrfToken:
    """Test token validation."""

    def test_valid_token_passes(self):
        session_id = "my-session"
        token = generate_csrf_token(session_id)
        assert validate_csrf_token(token, session_id) is True

    def test_wrong_session_fails(self):
        token = generate_csrf_token("session-real")
        assert validate_csrf_token(token, "session-wrong") is False

    def test_tampered_signature_fails(self):
        token = generate_csrf_token("sess")
        ts, sig = token.split(":", 1)
        tampered = f"{ts}:{'0' * len(sig)}"
        assert validate_csrf_token(tampered, "sess") is False

    def test_garbage_token_fails(self):
        assert validate_csrf_token("not-a-token", "sess") is False

    def test_empty_token_fails(self):
        assert validate_csrf_token("", "sess") is False

    def test_multiple_tokens_for_same_session(self):
        sid = "session-multi"
        t1 = generate_csrf_token(sid)
        t2 = generate_csrf_token(sid)
        # Both should validate (timestamps may differ slightly)
        assert validate_csrf_token(t1, sid) is True
        assert validate_csrf_token(t2, sid) is True
