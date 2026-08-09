"""WebSocket authentication must fail closed and reject refresh tokens (task 1)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.security

MOD = "education_system.platform.delivery.api.websocket_server"


def _mod():
    from education_system.platform.delivery.api import websocket_server
    return websocket_server


def test_refresh_token_rejected():
    mod = _mod()
    decode = "education_system.platform.delivery.api.auth.decode_token"
    with patch(decode, return_value={"sub": "1", "role": "admin", "type": "refresh"}):
        assert mod._validate_token("x") is None, "a refresh token must not authenticate a socket"


def test_access_token_accepted():
    mod = _mod()
    decode = "education_system.platform.delivery.api.auth.decode_token"
    with patch(decode, return_value={"sub": "1", "role": "admin", "type": "access"}):
        payload = mod._validate_token("x")
        assert payload and payload.get("type") == "access"


def test_invalid_token_returns_none():
    mod = _mod()
    decode = "education_system.platform.delivery.api.auth.decode_token"
    with patch(decode, side_effect=Exception("bad sig")):
        assert mod._validate_token("x") is None


def test_authenticate_requires_active_user():
    mod = _mod()
    decode = "education_system.platform.delivery.api.auth.decode_token"
    with patch(decode, return_value={"sub": "7", "role": "student", "type": "access"}):
        # is_active row returns falsy -> reject
        class _Conn:
            def execute(self, *a, **k):
                class _R:
                    def fetchone(self_inner):
                        return (0,)
                return _R()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with patch("education_system.platform.identity.auth.db.connect", return_value=_Conn()):
            assert mod._authenticate_ws("tok") is None


def test_authenticate_rejects_unknown_role():
    mod = _mod()
    decode = "education_system.platform.delivery.api.auth.decode_token"
    with patch(decode, return_value={"sub": "7", "role": "wizard", "type": "access"}):
        class _Conn:
            def execute(self, *a, **k):
                class _R:
                    def fetchone(self_inner):
                        return (1,)
                return _R()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with patch("education_system.platform.identity.auth.db.connect", return_value=_Conn()):
            assert mod._authenticate_ws("tok") is None
