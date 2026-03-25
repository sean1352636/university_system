"""Tests for MFAService."""

import pytest
import pyotp

from education_system.college_system.infrastructure.auth.mfa_service import MFAService
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.shared.auth.exceptions import AuthError


class TestMFAService:

    def test_setup_totp(self, mfa_service):
        result = mfa_service.setup_totp(1, "admin1")
        assert "secret" in result
        assert "provisioning_uri" in result
        assert len(result["recovery_codes"]) == 10
        # Codes should be in XXXX-XXXX format
        for code in result["recovery_codes"]:
            assert len(code) == 9
            assert code[4] == "-"

    def test_verify_valid_totp(self, mfa_service):
        result = mfa_service.setup_totp(1, "admin1")
        totp = pyotp.TOTP(result["secret"])
        code = totp.now()
        assert mfa_service.verify_totp(1, code) is True

    def test_verify_invalid_totp(self, mfa_service):
        mfa_service.setup_totp(1, "admin1")
        assert mfa_service.verify_totp(1, "000000") is False

    def test_is_mfa_enabled(self, mfa_service):
        assert mfa_service.is_mfa_enabled(1) is False
        mfa_service.setup_totp(1, "admin1")
        assert mfa_service.is_mfa_enabled(1) is True

    def test_disable_mfa(self, mfa_service):
        mfa_service.setup_totp(1, "admin1")
        assert mfa_service.is_mfa_enabled(1) is True
        mfa_service.disable_mfa(1)
        assert mfa_service.is_mfa_enabled(1) is False

    def test_recovery_code(self, mfa_service):
        result = mfa_service.setup_totp(1, "admin1")
        code = result["recovery_codes"][0]
        assert mfa_service.verify_recovery_code(1, code) is True
        # Same code should not work again
        assert mfa_service.verify_recovery_code(1, code) is False
        assert mfa_service.get_remaining_recovery_codes(1) == 9

    def test_auth_login_with_mfa(self, auth_db_path):
        auth = UserAuth(auth_db_path)
        mfa_svc = MFAService(auth_db_path)

        # Login without MFA - should get full user dict
        user = auth.login("admin1", "admin1234")
        assert any(s["role"] == "admin" for s in user["systems"])
        auth.logout()

        # Enable MFA
        result = mfa_svc.setup_totp(user["user_id"], user["username"])

        # Login with MFA enabled - should get mfa_required
        auth2 = UserAuth(auth_db_path)
        mfa_result = auth2.login("admin1", "admin1234")
        assert mfa_result.get("mfa_required") is True

        # Complete MFA with TOTP
        totp = pyotp.TOTP(result["secret"])
        code = totp.now()
        final = auth2.verify_mfa(mfa_result["user_id"], code)
        assert any(s["role"] == "admin" for s in final["systems"])
