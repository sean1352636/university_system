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


class TestIsMFAEnabledAgreesWithEnrolment:
    """``is_mfa_enabled`` is the login gate, so it must agree with what the
    MFA settings screen reports.

    It used to consult ``mfa_secrets`` alone — the TOTP secret. Enrolling an
    email or SMS factor writes ``mfa_methods`` / ``mfa_user_settings`` and
    never touches ``mfa_secrets``, so those users showed "ENABLED" in every
    UI and were silently never challenged at login.
    """

    # These two tables are created by the MFA enrolment flows rather than by
    # initialise_auth_db, so the helpers make them on demand — which is also
    # why is_mfa_enabled has to tolerate their absence.
    _METHODS_DDL = """
        CREATE TABLE IF NOT EXISTS mfa_methods (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            method_type       TEXT NOT NULL,
            method_identifier TEXT,
            is_primary        INTEGER NOT NULL DEFAULT 0,
            is_enabled        INTEGER NOT NULL DEFAULT 0
        )
    """
    _SETTINGS_DDL = """
        CREATE TABLE IF NOT EXISTS mfa_user_settings (
            user_id               INTEGER PRIMARY KEY,
            verification_disabled INTEGER NOT NULL DEFAULT 0,
            mfa_enabled           INTEGER DEFAULT 0
        )
    """

    @classmethod
    def _enable_method(cls, auth_db, user_id, method_type="email",
                       identifier="user@example.test", enabled=1):
        import sqlite3
        conn = sqlite3.connect(auth_db)
        conn.execute(cls._METHODS_DDL)
        conn.execute(
            "INSERT INTO mfa_methods (user_id, method_type, method_identifier, "
            " is_enabled) VALUES (?, ?, ?, ?)",
            (user_id, method_type, identifier, enabled),
        )
        conn.commit()
        conn.close()

    @classmethod
    def _set_verification_disabled(cls, auth_db, user_id, disabled):
        import sqlite3
        conn = sqlite3.connect(auth_db)
        conn.execute(cls._SETTINGS_DDL)
        conn.execute(
            "INSERT INTO mfa_user_settings (user_id, mfa_enabled, verification_disabled) "
            "VALUES (?, 1, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "  verification_disabled = excluded.verification_disabled",
            (user_id, disabled),
        )
        conn.commit()
        conn.close()

    def test_absent_mfa_tables_do_not_break_the_gate(self, mfa, user_id):
        """A fresh auth DB has neither table; the gate must not raise."""
        assert mfa.is_mfa_enabled(user_id) is False

    def test_email_enrolment_requires_mfa_without_any_totp_secret(self, mfa, user_id, auth_db):
        self._enable_method(auth_db, user_id, "email")
        assert mfa.is_mfa_enabled(user_id) is True

    def test_sms_enrolment_requires_mfa(self, mfa, user_id, auth_db):
        self._enable_method(auth_db, user_id, "sms", "+447700900000")
        assert mfa.is_mfa_enabled(user_id) is True

    def test_a_disabled_method_does_not_require_mfa(self, mfa, user_id, auth_db):
        self._enable_method(auth_db, user_id, "email", enabled=0)
        assert mfa.is_mfa_enabled(user_id) is False

    def test_totp_secret_still_requires_mfa(self, mfa, user_id):
        mfa.setup_totp(user_id, "testuser")
        assert mfa.is_mfa_enabled(user_id) is True

    def test_verification_disabled_overrides_an_enabled_method(self, mfa, user_id, auth_db):
        """Deliberately suspending MFA for an account must still win."""
        self._enable_method(auth_db, user_id, "email")
        self._set_verification_disabled(auth_db, user_id, 1)
        assert mfa.is_mfa_enabled(user_id) is False

    def test_verification_disabled_overrides_a_totp_secret(self, mfa, user_id, auth_db):
        mfa.setup_totp(user_id, "testuser")
        self._set_verification_disabled(auth_db, user_id, 1)
        assert mfa.is_mfa_enabled(user_id) is False

    def test_no_factors_at_all_does_not_require_mfa(self, mfa, user_id):
        assert mfa.is_mfa_enabled(user_id) is False


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
