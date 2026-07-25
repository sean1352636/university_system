"""Tests for shared.auth.mfa_service — TOTP setup, verification, recovery codes."""

import os
import re
import shutil
import sys
import time

import pyotp
import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.platform.identity.auth.mfa_service import (
    MFAService,
    _RECOVERY_MAX_ATTEMPTS,
)
from education_system.platform.identity.auth.exceptions import MFAError


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def _template_auth_db(tmp_path_factory):
    from education_system.platform.identity.auth.schema import initialise_auth_db, seed_default_users
    path = str(tmp_path_factory.mktemp("mfa_tpl") / "template_auth.db")
    initialise_auth_db(path)
    seed_default_users(path)
    return path


@pytest.fixture
def auth_db(tmp_path, _template_auth_db):
    db_path = str(tmp_path / "test_auth.db")
    shutil.copy2(_template_auth_db, db_path)
    return db_path


@pytest.fixture
def mfa(auth_db):
    return MFAService(db_path=auth_db)


@pytest.fixture
def user_id(auth_db):
    """Return the ID of the first user."""
    from education_system.platform.identity.auth.db import connect
    conn = connect(auth_db)
    uid = conn.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
    conn.close()
    return uid


# Recovery-code rate limiting is now backed by a PersistentRateLimiter scoped to
# the MFAService db_path. Each test gets a fresh auth_db (see the `auth_db`
# fixture), so rate-limit state is reset per test with no extra teardown needed.


# ── Setup ─────────────────────────────────────────────────────────────────


class TestSetupTOTP:
    def test_returns_secret_and_uri(self, mfa, user_id):
        result = mfa.setup_totp(user_id, "testuser")
        assert "secret" in result
        assert "provisioning_uri" in result
        assert "otpauth://" in result["provisioning_uri"]

    def test_generates_recovery_codes(self, mfa, user_id):
        result = mfa.setup_totp(user_id, "testuser")
        codes = result["recovery_codes"]
        assert len(codes) == MFAService.RECOVERY_CODE_COUNT
        for code in codes:
            assert re.match(r"^[A-Z0-9]{4}-[A-Z0-9]{4}$", code)

    def test_enables_mfa(self, mfa, user_id):
        mfa.setup_totp(user_id, "testuser")
        assert mfa.is_mfa_enabled(user_id) is True

    def test_re_setup_replaces_old_secret(self, mfa, user_id):
        r1 = mfa.setup_totp(user_id, "testuser")
        r2 = mfa.setup_totp(user_id, "testuser")
        assert r1["secret"] != r2["secret"]
        # Old recovery codes should be gone
        assert mfa.get_remaining_recovery_codes(user_id) == MFAService.RECOVERY_CODE_COUNT


# ── TOTP verification ─────────────────────────────────────────────────────


class TestVerifyTOTP:
    def test_valid_code(self, mfa, user_id):
        result = mfa.setup_totp(user_id, "testuser")
        totp = pyotp.TOTP(result["secret"])
        assert mfa.verify_totp(user_id, totp.now()) is True

    def test_invalid_code(self, mfa, user_id):
        mfa.setup_totp(user_id, "testuser")
        assert mfa.verify_totp(user_id, "000000") is False

    def test_mfa_not_setup_raises(self, mfa):
        with pytest.raises(MFAError, match="not set up"):
            mfa.verify_totp(999999, "123456")

    def test_disabled_mfa_raises(self, mfa, user_id, auth_db):
        mfa.setup_totp(user_id, "testuser")
        # Manually disable in DB without removing row
        from education_system.platform.identity.auth.db import connect
        conn = connect(auth_db)
        conn.execute("UPDATE mfa_secrets SET is_enabled = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

        with pytest.raises(MFAError, match="disabled"):
            mfa.verify_totp(user_id, "123456")


# ── Enable / Disable ─────────────────────────────────────────────────────


class TestMFAEnableDisable:
    def test_mfa_initially_disabled(self, mfa, user_id):
        assert mfa.is_mfa_enabled(user_id) is False

    def test_disable_mfa(self, mfa, user_id):
        mfa.setup_totp(user_id, "testuser")
        assert mfa.is_mfa_enabled(user_id) is True

        mfa.disable_mfa(user_id)
        assert mfa.is_mfa_enabled(user_id) is False

    def test_disable_when_not_setup_raises(self, mfa, user_id):
        with pytest.raises(MFAError, match="not set up"):
            mfa.disable_mfa(user_id)

    def test_disable_removes_recovery_codes(self, mfa, user_id):
        mfa.setup_totp(user_id, "testuser")
        assert mfa.get_remaining_recovery_codes(user_id) == 10
        mfa.disable_mfa(user_id)
        assert mfa.get_remaining_recovery_codes(user_id) == 0


# ── Recovery codes ────────────────────────────────────────────────────────


class TestRecoveryCodes:
    def test_valid_recovery_code(self, mfa, user_id):
        result = mfa.setup_totp(user_id, "testuser")
        code = result["recovery_codes"][0]
        assert mfa.verify_recovery_code(user_id, code) is True

    def test_recovery_code_single_use(self, mfa, user_id):
        result = mfa.setup_totp(user_id, "testuser")
        code = result["recovery_codes"][0]
        assert mfa.verify_recovery_code(user_id, code) is True
        assert mfa.verify_recovery_code(user_id, code) is False

    def test_remaining_decrements(self, mfa, user_id):
        result = mfa.setup_totp(user_id, "testuser")
        assert mfa.get_remaining_recovery_codes(user_id) == 10
        mfa.verify_recovery_code(user_id, result["recovery_codes"][0])
        assert mfa.get_remaining_recovery_codes(user_id) == 9

    def test_invalid_recovery_code(self, mfa, user_id):
        mfa.setup_totp(user_id, "testuser")
        assert mfa.verify_recovery_code(user_id, "ZZZZ-ZZZZ") is False

    def test_case_insensitive(self, mfa, user_id):
        result = mfa.setup_totp(user_id, "testuser")
        code = result["recovery_codes"][0]
        assert mfa.verify_recovery_code(user_id, code.lower()) is True

    def test_rate_limit_lockout(self, mfa, user_id):
        mfa.setup_totp(user_id, "testuser")
        for _ in range(_RECOVERY_MAX_ATTEMPTS):
            mfa.verify_recovery_code(user_id, "XXXX-XXXX")

        with pytest.raises(MFAError, match="Too many failed"):
            mfa.verify_recovery_code(user_id, "XXXX-XXXX")

    def test_successful_verify_clears_attempts(self, mfa, user_id):
        result = mfa.setup_totp(user_id, "testuser")
        # Fail a few times
        for _ in range(_RECOVERY_MAX_ATTEMPTS - 1):
            mfa.verify_recovery_code(user_id, "XXXX-XXXX")
        # Succeed
        mfa.verify_recovery_code(user_id, result["recovery_codes"][0])
        # Should NOT be locked out — counter was cleared
        assert mfa.verify_recovery_code(user_id, result["recovery_codes"][1]) is True
