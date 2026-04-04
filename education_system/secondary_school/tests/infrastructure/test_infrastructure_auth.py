"""Tests for infrastructure auth wrapper modules (re-exports from shared)."""

import pytest


class TestAuthCoreReexport:
    """Tests for infrastructure.auth.core re-exports."""

    def test_user_auth_importable(self):
        from education_system.secondary_school.infrastructure.auth.core import UserAuth
        assert UserAuth is not None

    def test_auth_error_importable(self):
        from education_system.secondary_school.infrastructure.auth.core import AuthError
        assert issubclass(AuthError, Exception)

    def test_user_auth_matches_shared(self):
        from education_system.secondary_school.infrastructure.auth.core import UserAuth
        from education_system.shared.auth.core import UserAuth as SharedUserAuth
        assert UserAuth is SharedUserAuth


class TestMFAServiceReexport:
    """Tests for infrastructure.auth.mfa_service re-export."""

    def test_mfa_service_importable(self):
        from education_system.secondary_school.infrastructure.auth.mfa_service import MFAService
        assert MFAService is not None

    def test_mfa_service_matches_shared(self):
        from education_system.secondary_school.infrastructure.auth.mfa_service import MFAService
        from education_system.shared.auth.mfa_service import MFAService as SharedMFAService
        assert MFAService is SharedMFAService


class TestPasswordManagerReexport:
    """Tests for infrastructure.auth.password_manager re-exports."""

    def test_hash_password_importable(self):
        from education_system.secondary_school.infrastructure.auth.password_manager import hash_password
        assert callable(hash_password)

    def test_verify_password_importable(self):
        from education_system.secondary_school.infrastructure.auth.password_manager import verify_password
        assert callable(verify_password)

    def test_validate_password_strength_importable(self):
        from education_system.secondary_school.infrastructure.auth.password_manager import validate_password_strength
        assert callable(validate_password_strength)

    def test_hash_and_verify_roundtrip(self):
        from education_system.secondary_school.infrastructure.auth.password_manager import (
            hash_password, verify_password,
        )
        hashed = hash_password("TestPassword@123")
        assert verify_password("TestPassword@123", hashed)
        assert not verify_password("WrongPassword@123", hashed)


class TestRoleManagerReexport:
    """Tests for infrastructure.auth.role_manager re-exports."""

    def test_role_manager_importable(self):
        from education_system.secondary_school.infrastructure.auth.role_manager import RoleManager
        assert RoleManager is not None

    def test_role_hierarchy_importable(self):
        from education_system.secondary_school.infrastructure.auth.role_manager import ROLE_HIERARCHY
        assert isinstance(ROLE_HIERARCHY, dict)

    def test_role_hierarchy_has_expected_roles(self):
        from education_system.secondary_school.infrastructure.auth.role_manager import ROLE_HIERARCHY
        assert "admin" in ROLE_HIERARCHY or "superadmin" in ROLE_HIERARCHY


class TestSessionManagerReexport:
    """Tests for infrastructure.auth.session_manager re-export."""

    def test_session_manager_importable(self):
        from education_system.secondary_school.infrastructure.auth.session_manager import SessionManager
        assert SessionManager is not None

    def test_session_manager_matches_shared(self):
        from education_system.secondary_school.infrastructure.auth.session_manager import SessionManager
        from education_system.shared.auth.session_manager import SessionManager as SharedSessionManager
        assert SessionManager is SharedSessionManager
