"""Tests for authentication system."""

import pytest
from education_system.shared.auth.exceptions import AuthError
from education_system.college_system.infrastructure.auth.password_manager import (
    hash_password, verify_password, validate_password_strength,
)


class TestPasswordManager:
    def test_hash_and_verify(self):
        pw = "TestPass@12345"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)
        assert not verify_password("wrong", hashed)

    def test_password_strength_valid(self):
        is_valid, _ = validate_password_strength("StrongP@ss1234")
        assert is_valid

    def test_password_too_short(self):
        is_valid, msg = validate_password_strength("Sh@1")
        assert not is_valid
        assert "12 characters" in msg

    def test_password_no_uppercase(self):
        is_valid, _ = validate_password_strength("lowercase@12345")
        assert not is_valid

    def test_password_no_special(self):
        is_valid, _ = validate_password_strength("NoSpecial12345")
        assert not is_valid


class TestUserAuth:
    def test_login_admin(self, auth):
        user = auth.login("admin1", "admin1234")
        assert user["username"] == "admin1"
        assert any(s["role"] == "admin" for s in user["systems"])
        assert auth.is_logged_in

    def test_login_wrong_password(self, auth):
        with pytest.raises(AuthError, match="Invalid"):
            auth.login("admin1", "wrong")

    def test_login_nonexistent_user(self, auth):
        with pytest.raises(AuthError, match="Invalid"):
            auth.login("nobody", "test")

    def test_logout(self, auth):
        auth.login("admin1", "admin1234")
        auth.logout()
        assert not auth.is_logged_in
        assert auth.current_user is None

    def test_create_user(self, auth):
        user_id = auth.create_user(
            "newuser", "NewUser@12345",
            systems=[("college", "student")],
        )
        assert user_id > 0

    def test_create_duplicate_user(self, auth):
        auth.create_user("testuser", "TestUser@12345",
                         systems=[("college", "student")])
        with pytest.raises(AuthError, match="already exists"):
            auth.create_user("testuser", "TestUser@12345",
                             systems=[("college", "student")])

    def test_create_user_weak_password(self, auth):
        with pytest.raises(AuthError):
            auth.create_user("weak", "123")

    def test_change_password(self, auth):
        auth.create_user("changepw", "OldPass@12345",
                         systems=[("college", "student")])
        auth.login("changepw", "OldPass@12345")
        auth.change_password(auth.current_user["user_id"], "OldPass@12345", "NewPass@45678")
        auth.logout()
        # Login with new password
        user = auth.login("changepw", "NewPass@45678")
        assert user["username"] == "changepw"

    def test_check_permission_admin(self, auth):
        user = auth.login("admin1", "admin1234")
        assert any(s["role"] == "admin" for s in user["systems"])

    def test_account_lockout(self, auth):
        for _ in range(5):
            try:
                auth.login("admin1", "wrongpassword")
            except AuthError:
                pass

        with pytest.raises(AuthError, match="locked"):
            auth.login("admin1", "admin1234")


class TestRoleManager:
    def test_role_hierarchy(self, auth):
        rm = auth.role_manager
        assert rm.has_minimum_role("admin", "student")
        assert rm.has_minimum_role("admin", "instructor")
        assert not rm.has_minimum_role("student", "admin")

    def test_get_role_level(self, auth):
        rm = auth.role_manager
        assert rm.get_role_level("admin") == 100
        assert rm.get_role_level("student") == 25
