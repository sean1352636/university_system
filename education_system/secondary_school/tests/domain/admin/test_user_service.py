"""Tests for UserService."""
import pytest


class TestUserService:
    def test_create_user(self, user_service):
        user_service.create_user("newuser", "Pass1234!", role="teacher", email="new@school.local")
        users = user_service.list_users()
        assert any(u["username"] == "newuser" for u in users)

    def test_list_users(self, user_service):
        # Default seeded users exist
        users = user_service.list_users()
        assert len(users) >= 1

    def test_list_users_filters_by_role(self, user_service):
        user_service.create_user("teach1", "Pass1234!", role="teacher")
        user_service.create_user("stu1", "Pass1234!", role="student")
        users = user_service.list_users(role="teacher")
        assert all(u["role"] == "teacher" for u in users)

    def test_reset_password(self, user_service):
        user_service.create_user("resetme", "OldPass1!")
        users = user_service.list_users()
        uid = [u for u in users if u["username"] == "resetme"][0]["id"]
        # Should not raise
        user_service.reset_password(uid, "NewPass1!")

    def test_toggle_active(self, user_service):
        user_service.create_user("toggleuser", "Pass1234!")
        users = user_service.list_users()
        uid = [u for u in users if u["username"] == "toggleuser"][0]["id"]
        user_service.toggle_active(uid)
        users = user_service.list_users()
        user = [u for u in users if u["id"] == uid][0]
        assert user["is_active"] == 0

    def test_update_role(self, user_service):
        user_service.create_user("roleuser", "Pass1234!", role="student")
        users = user_service.list_users()
        uid = [u for u in users if u["username"] == "roleuser"][0]["id"]
        user_service.update_role(uid, "teacher")
        users = user_service.list_users()
        user = [u for u in users if u["id"] == uid][0]
        assert user["role"] == "teacher"

    def test_delete_user(self, user_service):
        user_service.create_user("deluser", "Pass1234!")
        users = user_service.list_users()
        uid = [u for u in users if u["username"] == "deluser"][0]["id"]
        user_service.delete_user(uid)
        users = user_service.list_users()
        assert all(u["id"] != uid for u in users)
