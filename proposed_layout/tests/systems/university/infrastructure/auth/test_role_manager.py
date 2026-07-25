#!/usr/bin/env python3
"""
Unit tests for RoleManager.

Tests cover:
- ROLES constant structure
- create_role: permission gate, input validation, duplicate detection, success path
- Permission linking during role creation
- Mocked DB cursor interactions
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from contextlib import contextmanager

from education_system.systems.university.infrastructure.auth.managers.role_manager import RoleManager, ROLES


# ============================================================================
# ROLES Constant Tests
# ============================================================================

class TestRolesConstant:
    """Tests for the module-level ROLES dictionary."""

    def test_roles_contains_admin(self):
        """ROLES includes 'admin'."""
        assert "admin" in ROLES

    def test_roles_contains_staff(self):
        """ROLES includes 'staff'."""
        assert "staff" in ROLES

    def test_roles_contains_student(self):
        """ROLES includes 'student'."""
        assert "student" in ROLES

    def test_roles_contains_instructor(self):
        """ROLES includes 'instructor'."""
        assert "instructor" in ROLES

    def test_roles_contains_parent(self):
        """ROLES includes 'parent'."""
        assert "parent" in ROLES

    def test_roles_has_five_entries(self):
        """ROLES has exactly five default roles."""
        assert len(ROLES) == 5

    def test_role_values_are_strings(self):
        """Every ROLES value (description) is a non-empty string."""
        for key, value in ROLES.items():
            assert isinstance(value, str) and len(value) > 0


# ============================================================================
# Fixtures / helpers
# ============================================================================

def _make_admin_user():
    """Return a dict representing an admin user with manage_roles permission."""
    return {
        "id": 1,
        "username": "admin",
        "permissions": ["manage_roles", "manage_users"],
    }


def _make_unprivileged_user():
    """Return a dict representing a user without manage_roles permission."""
    return {
        "id": 2,
        "username": "student1",
        "permissions": ["view_grades"],
    }


def _build_role_manager(current_user=None, cursor_side_effects=None):
    """
    Build a RoleManager with a mocked db_manager.

    Parameters
    ----------
    current_user : dict or None
        The dict returned by current_user_getter.
    cursor_side_effects : list or None
        Sequence of return values for cursor.fetchone(). Each call
        to fetchone() pops the next value from this list.

    Returns
    -------
    tuple of (RoleManager, MagicMock-cursor, MagicMock-conn)
    """
    cursor = MagicMock()
    if cursor_side_effects is not None:
        cursor.fetchone.side_effect = list(cursor_side_effects)
    else:
        cursor.fetchone.return_value = None

    cursor.lastrowid = 100  # newly inserted role id

    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)

    db_manager = Mock()
    db_manager.get_connection.return_value = conn

    activity_logger = Mock()
    current_user_getter = Mock(return_value=current_user)

    rm = RoleManager(db_manager, activity_logger, current_user_getter)
    return rm, cursor, conn


# ============================================================================
# create_role Tests
# ============================================================================

class TestCreateRole:
    """Tests for RoleManager.create_role()."""

    def test_no_user_returns_false(self):
        """Returns False when current_user_getter returns None."""
        rm, cursor, conn = _build_role_manager(current_user=None)
        assert rm.create_role("new_role", "A new role") is False

    def test_no_permission_returns_false(self):
        """Returns False when user lacks manage_roles permission."""
        rm, cursor, conn = _build_role_manager(current_user=_make_unprivileged_user())
        assert rm.create_role("new_role", "A new role") is False

    def test_empty_role_name_returns_false(self):
        """Returns False when role_name is empty string."""
        rm, cursor, conn = _build_role_manager(current_user=_make_admin_user())
        assert rm.create_role("", "A description") is False

    def test_empty_description_returns_false(self):
        """Returns False when description is empty string."""
        rm, cursor, conn = _build_role_manager(current_user=_make_admin_user())
        assert rm.create_role("new_role", "") is False

    def test_none_role_name_returns_false(self):
        """Returns False when role_name is None."""
        rm, cursor, conn = _build_role_manager(current_user=_make_admin_user())
        assert rm.create_role(None, "desc") is False

    def test_none_description_returns_false(self):
        """Returns False when description is None."""
        rm, cursor, conn = _build_role_manager(current_user=_make_admin_user())
        assert rm.create_role("new_role", None) is False

    def test_permissions_not_list_returns_false(self):
        """Returns False when permissions is a non-list truthy value."""
        rm, cursor, conn = _build_role_manager(current_user=_make_admin_user())
        assert rm.create_role("new_role", "desc", permissions="not_a_list") is False

    def test_duplicate_role_returns_false(self):
        """Returns False when role_name already exists in DB."""
        # First fetchone returns a row (existing role)
        rm, cursor, conn = _build_role_manager(
            current_user=_make_admin_user(),
            cursor_side_effects=[(42,)],  # role already exists with id=42
        )
        assert rm.create_role("existing_role", "Exists already") is False
        conn.commit.assert_not_called()

    def test_successful_creation_returns_true(self):
        """Returns True and commits when role is created successfully."""
        # fetchone returns None (role does not exist yet)
        rm, cursor, conn = _build_role_manager(
            current_user=_make_admin_user(),
            cursor_side_effects=[None],
        )
        result = rm.create_role("new_role", "Brand new role")
        assert result is True
        conn.commit.assert_called_once()

    def test_successful_creation_inserts_into_roles(self):
        """An INSERT INTO roles statement is executed on success."""
        rm, cursor, conn = _build_role_manager(
            current_user=_make_admin_user(),
            cursor_side_effects=[None],
        )
        rm.create_role("new_role", "Brand new role")

        # Verify that cursor.execute was called with INSERT INTO roles
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT INTO roles" in str(c)
        ]
        assert len(insert_calls) == 1

    def test_permissions_linked_on_creation(self):
        """Permissions are linked via role_permissions when they exist in DB."""
        rm, cursor, conn = _build_role_manager(
            current_user=_make_admin_user(),
            cursor_side_effects=[
                None,    # role does not exist yet
                (5,),    # permission 'view_grades' exists with id=5
                (6,),    # permission 'edit_grades' exists with id=6
            ],
        )
        result = rm.create_role("grader", "Can grade", permissions=["view_grades", "edit_grades"])
        assert result is True

        # Two INSERT INTO role_permissions calls expected
        rp_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT INTO role_permissions" in str(c)
        ]
        assert len(rp_calls) == 2

    def test_nonexistent_permission_skipped(self):
        """A permission that does not exist in DB is skipped (no error)."""
        rm, cursor, conn = _build_role_manager(
            current_user=_make_admin_user(),
            cursor_side_effects=[
                None,    # role does not exist yet
                None,    # permission 'bogus' not found
            ],
        )
        result = rm.create_role("new_role", "desc", permissions=["bogus"])
        assert result is True

        # No INSERT INTO role_permissions since the permission was not found
        rp_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT INTO role_permissions" in str(c)
        ]
        assert len(rp_calls) == 0

    def test_activity_logger_called_on_success(self):
        """activity_logger is called with role creation details."""
        rm, cursor, conn = _build_role_manager(
            current_user=_make_admin_user(),
            cursor_side_effects=[None],
        )
        rm.create_role("new_role", "desc")
        rm.activity_logger.assert_called_once()
        args = rm.activity_logger.call_args[0]
        assert args[0] == "admin"
        assert "new_role" in args[1]

    def test_no_permissions_kwarg_defaults_to_none(self):
        """Calling create_role without permissions does not crash."""
        rm, cursor, conn = _build_role_manager(
            current_user=_make_admin_user(),
            cursor_side_effects=[None],
        )
        result = rm.create_role("plain_role", "No perms")
        assert result is True


# ============================================================================
# delete_role / update_role Permission Gate Tests
# ============================================================================

class TestRoleManagerPermissionGates:
    """Ensure other RoleManager methods also check permissions."""

    def test_delete_role_no_permission_returns_false(self):
        """delete_role returns False without manage_roles."""
        rm, cursor, conn = _build_role_manager(current_user=_make_unprivileged_user())
        assert rm.delete_role(1) is False

    def test_update_role_no_permission_returns_false(self):
        """update_role returns False without manage_roles."""
        rm, cursor, conn = _build_role_manager(current_user=_make_unprivileged_user())
        assert rm.update_role(1, description="new desc") is False

    def test_list_roles_no_permission_returns_none(self):
        """list_roles returns None without manage_roles."""
        rm, cursor, conn = _build_role_manager(current_user=_make_unprivileged_user())
        assert rm.list_roles() is None

    def test_get_role_no_permission_returns_none(self):
        """get_role returns None without manage_roles."""
        rm, cursor, conn = _build_role_manager(current_user=_make_unprivileged_user())
        assert rm.get_role(role_id=1) is None
