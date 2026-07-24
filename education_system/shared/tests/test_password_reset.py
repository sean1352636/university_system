"""Tests for password-reset tokens: expiry, single use, and rotation.

Covers PasswordResetService.request_reset / validate_token / reset_password.
"""

import os
import shutil
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.shared.auth.db import connect
from education_system.shared.auth.exceptions import AuthError
from education_system.shared.auth.password_reset import PasswordResetService


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def _template_auth_db(tmp_path_factory):
    from education_system.shared.auth.schema import initialise_auth_db, seed_default_users
    path = str(tmp_path_factory.mktemp("pwreset_tpl") / "template_auth.db")
    initialise_auth_db(path)
    seed_default_users(path)
    return path


@pytest.fixture
def auth_db(tmp_path, _template_auth_db):
    db_path = str(tmp_path / "test_auth.db")
    shutil.copy2(_template_auth_db, db_path)
    return db_path


@pytest.fixture
def svc(auth_db):
    return PasswordResetService(db_path=auth_db)


# admin is a seeded demo account (university admin).
_EMAIL = "admin@university.edu"
_STRONG = "Rotated!Passw0rd#1"


# ── request / validate ─────────────────────────────────────────────────────

class TestRequestAndValidate:
    def test_request_returns_token(self, svc):
        result = svc.request_reset(_EMAIL)
        assert result["sent"] is True
        assert result.get("token")

    def test_valid_token_validates(self, svc):
        token = svc.request_reset(_EMAIL)["token"]
        info = svc.validate_token(token)
        assert info["email"].lower() == _EMAIL

    def test_unknown_email_yields_no_token(self, svc):
        result = svc.request_reset("nobody@nowhere.invalid")
        assert result["sent"] is True
        assert "token" not in result

    def test_garbage_token_rejected(self, svc):
        with pytest.raises(AuthError):
            svc.validate_token("not-a-real-token")


# ── single use ─────────────────────────────────────────────────────────────

class TestSingleUse:
    def test_token_cannot_be_reused_after_reset(self, svc):
        token = svc.request_reset(_EMAIL)["token"]
        assert svc.reset_password(token, _STRONG) is True
        # The token is consumed — neither validation nor a second reset works.
        with pytest.raises(AuthError):
            svc.validate_token(token)
        with pytest.raises(AuthError):
            svc.reset_password(token, "Another!Passw0rd#2")


# ── expiry ─────────────────────────────────────────────────────────────────

class TestExpiry:
    def _expire(self, auth_db, user_id):
        past = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
        conn = connect(auth_db)
        try:
            conn.execute(
                "UPDATE password_reset_tokens SET expires_at = ? WHERE user_id = ?",
                (past, user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def test_expired_token_rejected_on_validate(self, svc, auth_db):
        result = svc.request_reset(_EMAIL)
        self._expire(auth_db, result["user_id"])
        with pytest.raises(AuthError):
            svc.validate_token(result["token"])

    def test_expired_token_rejected_on_reset(self, svc, auth_db):
        result = svc.request_reset(_EMAIL)
        self._expire(auth_db, result["user_id"])
        with pytest.raises(AuthError):
            svc.reset_password(result["token"], _STRONG)


# ── rotation ───────────────────────────────────────────────────────────────

class TestRotation:
    def test_new_request_invalidates_previous_token(self, svc):
        first = svc.request_reset(_EMAIL)["token"]
        second = svc.request_reset(_EMAIL)["token"]
        assert first != second
        # Requesting a fresh token deletes the earlier one.
        with pytest.raises(AuthError):
            svc.validate_token(first)
        assert svc.validate_token(second)["email"].lower() == _EMAIL
