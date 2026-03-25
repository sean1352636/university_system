"""Tests for shared UserAuth (secondary school context)."""

import pytest
from education_system.shared.auth.exceptions import AuthError


class TestAuth:
    def test_login_admin(self, auth):
        user = auth.login("admin2", "admin1234")
        assert user["username"] == "admin2"
        assert any(s["role"] == "admin" for s in user["systems"])
        assert auth.is_logged_in

    def test_login_teacher(self, auth):
        user = auth.login("staff2", "staff1234")
        assert any(s["role"] == "teacher" for s in user["systems"])

    def test_login_student(self, auth):
        user = auth.login("student2", "student1234")
        assert any(s["role"] == "student" for s in user["systems"])

    def test_login_invalid_username(self, auth):
        with pytest.raises(AuthError, match="Invalid"):
            auth.login("nonexistent", "password")

    def test_login_wrong_password(self, auth):
        with pytest.raises(AuthError, match="Invalid"):
            auth.login("admin2", "WrongPassword@1")

    def test_login_inactive_user(self, auth, auth_db_path):
        from education_system.shared.auth.db import connect
        conn = connect(auth_db_path)
        conn.execute("UPDATE users SET is_active = 0 WHERE username = 'student2'")
        conn.commit()
        conn.close()
        with pytest.raises(AuthError, match="Invalid"):
            auth.login("student2", "student1234")

    def test_logout(self, auth):
        auth.login("admin2", "admin1234")
        assert auth.is_logged_in
        auth.logout()
        assert not auth.is_logged_in

    def test_create_user(self, auth):
        user_id = auth.create_user(
            "newuser", "NewUser@12345",
            systems=[("school", "teacher")],
        )
        assert user_id > 0

    def test_create_duplicate_user(self, auth):
        with pytest.raises(AuthError, match="already exists"):
            auth.create_user("admin2", "Admin@School123")

    def test_change_password(self, auth):
        auth.login("admin2", "admin1234")
        user_id = auth.current_user["user_id"]
        auth.change_password(user_id, "admin1234", "NewAdmin@123")
        auth.logout()
        user = auth.login("admin2", "NewAdmin@123")
        assert user["username"] == "admin2"

    def test_change_password_wrong_old(self, auth):
        auth.login("admin2", "admin1234")
        with pytest.raises(AuthError, match="incorrect"):
            auth.change_password(auth.current_user["user_id"], "WrongOld@1", "NewAdmin@123")

    def test_account_lockout(self, auth):
        for _ in range(5):
            try:
                auth.login("admin2", "WrongPassword@1")
            except AuthError:
                pass
        with pytest.raises(AuthError, match="locked"):
            auth.login("admin2", "admin1234")

    def test_current_user_property(self, auth):
        assert auth.current_user is None
        auth.login("admin2", "admin1234")
        assert auth.current_user is not None
        assert auth.current_user["username"] == "admin2"

    def test_get_role_for_system(self, auth):
        auth.login("admin2", "admin1234")
        assert auth.get_role_for_system("school") == "admin"
        assert auth.get_role_for_system("university") is None
