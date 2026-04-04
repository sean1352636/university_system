"""Tests for shared.auth.role_manager — RoleManager and ROLE_HIERARCHY."""

import pytest

from education_system.shared.auth.role_manager import RoleManager, ROLE_HIERARCHY


class TestRoleHierarchy:
    """Test the exported ROLE_HIERARCHY constant."""

    def test_hierarchy_has_expected_roles(self):
        for role in ("admin", "staff", "instructor", "teacher", "student", "parent"):
            assert role in ROLE_HIERARCHY

    def test_admin_highest(self):
        assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["staff"]
        assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["teacher"]
        assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["student"]

    def test_teacher_instructor_equal(self):
        assert ROLE_HIERARCHY["teacher"] == ROLE_HIERARCHY["instructor"]

    def test_student_below_teacher(self):
        assert ROLE_HIERARCHY["student"] < ROLE_HIERARCHY["teacher"]

    def test_staff_above_teacher(self):
        assert ROLE_HIERARCHY["staff"] > ROLE_HIERARCHY["teacher"]


class TestRoleLevelAndMinimumRole:
    """Test get_role_level and has_minimum_role (no DB needed)."""

    def setup_method(self):
        self.rm = RoleManager(db_path=None)

    def test_get_role_level_known(self):
        assert self.rm.get_role_level("admin") == 100
        assert self.rm.get_role_level("student") == 25

    def test_get_role_level_unknown_returns_zero(self):
        assert self.rm.get_role_level("nonexistent") == 0

    def test_has_minimum_role_true(self):
        assert self.rm.has_minimum_role("admin", "teacher") is True
        assert self.rm.has_minimum_role("teacher", "teacher") is True

    def test_has_minimum_role_false(self):
        assert self.rm.has_minimum_role("student", "admin") is False


class TestRoleManagerDB:
    """Tests that hit the shared auth database."""

    def test_get_user_role_for_system(self, shared_auth_db):
        rm = RoleManager(shared_auth_db)
        # superadmin (user_id=1) should have access to university
        role = rm.get_user_role_for_system(1, "university")
        assert role is not None

    def test_get_user_role_missing_returns_none(self, shared_auth_db):
        rm = RoleManager(shared_auth_db)
        assert rm.get_user_role_for_system(99999, "nonexistent") is None

    def test_get_user_systems(self, shared_auth_db):
        rm = RoleManager(shared_auth_db)
        systems = rm.get_user_systems(1)  # superadmin
        assert isinstance(systems, list)
        assert len(systems) >= 1
        assert all("system_key" in s and "role" in s for s in systems)

    def test_grant_and_revoke_system_access(self, shared_auth_db):
        rm = RoleManager(shared_auth_db)
        # Grant a new mapping
        rm.grant_system_access(1, "test_system", "staff")
        role = rm.get_user_role_for_system(1, "test_system")
        assert role == "staff"

        # Revoke it
        rm.revoke_system_access(1, "test_system")
        assert rm.get_user_role_for_system(1, "test_system") is None

    def test_grant_invalid_role_raises(self, shared_auth_db):
        rm = RoleManager(shared_auth_db)
        with pytest.raises(ValueError, match="Invalid role"):
            rm.grant_system_access(1, "university", "wizard")

    def test_grant_overwrites_existing_role(self, shared_auth_db):
        rm = RoleManager(shared_auth_db)
        rm.grant_system_access(1, "overwrite_test", "student")
        rm.grant_system_access(1, "overwrite_test", "admin")
        assert rm.get_user_role_for_system(1, "overwrite_test") == "admin"
