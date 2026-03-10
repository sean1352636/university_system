#!/usr/bin/env python3
"""
Unit tests for PermissionManager.

Tests cover:
- check_permission: no user, direct permission, missing permission, delegated permission
- has_permission: session check integration, direct and delegated paths
- get_user_permissions (mocked DB)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from education_system.university_system.infrastructure.auth.managers.permission_manager import PermissionManager


# ============================================================================
# Helpers
# ============================================================================

def _make_permission_manager(current_user=None, session_valid=True):
    """
    Build a PermissionManager with mocked dependencies.

    Parameters
    ----------
    current_user : dict or None
        Value returned by current_user_getter.
    session_valid : bool
        Value returned by session_checker.

    Returns
    -------
    PermissionManager
    """
    db_manager = Mock()
    activity_logger = Mock()
    current_user_getter = Mock(return_value=current_user)
    session_checker = Mock(return_value=session_valid)

    pm = PermissionManager(db_manager, activity_logger, current_user_getter, session_checker)
    return pm


# ============================================================================
# check_permission Tests
# ============================================================================

class TestCheckPermission:
    """Tests for PermissionManager.check_permission()."""

    def test_no_user_from_getter_returns_false(self):
        """Returns False when current_user_getter returns None and no user passed."""
        pm = _make_permission_manager(current_user=None)
        assert pm.check_permission("view_grades") is False

    def test_no_user_passed_explicitly_returns_false(self):
        """Returns False when current_user=None is passed explicitly and getter also None."""
        pm = _make_permission_manager(current_user=None)
        assert pm.check_permission("view_grades", current_user=None) is False

    def test_user_has_direct_permission_returns_true(self):
        """Returns True when permission is in user's permissions list."""
        user = {"id": 1, "permissions": ["view_grades", "edit_grades"]}
        pm = _make_permission_manager(current_user=user)
        assert pm.check_permission("view_grades") is True

    def test_user_lacks_permission_returns_false(self):
        """Returns False when permission is not in user's permissions."""
        user = {"id": 1, "permissions": ["view_grades"]}
        pm = _make_permission_manager(current_user=user)
        assert pm.check_permission("manage_roles") is False

    def test_explicit_current_user_takes_precedence(self):
        """When current_user is passed directly, it is used instead of getter."""
        # Getter returns user without the permission
        getter_user = {"id": 1, "permissions": []}
        pm = _make_permission_manager(current_user=getter_user)

        # Explicit user has the permission
        explicit_user = {"id": 2, "permissions": ["manage_roles"]}
        assert pm.check_permission("manage_roles", current_user=explicit_user) is True

    def test_empty_permissions_list_returns_false(self):
        """Returns False when user has empty permissions list."""
        user = {"id": 1, "permissions": []}
        pm = _make_permission_manager(current_user=user)
        assert pm.check_permission("anything") is False

    def test_missing_permissions_key_returns_false(self):
        """Returns False when user dict has no 'permissions' key."""
        user = {"id": 1}
        pm = _make_permission_manager(current_user=user)
        assert pm.check_permission("view_grades") is False

    @patch(
        "university_system.infrastructure.auth.managers.permission_manager"
        ".PermissionManager._check_delegated_permission",
        return_value=True,
    )
    def test_delegated_permission_checked_when_acting_as_delegate(self, mock_delegated):
        """Delegated permissions are checked when acting_as_delegate_for is set."""
        user = {
            "id": 1,
            "permissions": [],
            "acting_as_delegate_for": 42,
        }
        pm = _make_permission_manager(current_user=user)
        result = pm.check_permission("view_grades")
        assert result is True
        mock_delegated.assert_called_once_with(1, 42, "view_grades")

    @patch(
        "university_system.infrastructure.auth.managers.permission_manager"
        ".PermissionManager._check_delegated_permission",
        return_value=False,
    )
    def test_delegated_permission_returns_false_when_not_granted(self, mock_delegated):
        """Returns False when delegate does not have the requested permission."""
        user = {
            "id": 1,
            "permissions": [],
            "acting_as_delegate_for": 42,
        }
        pm = _make_permission_manager(current_user=user)
        assert pm.check_permission("manage_users") is False

    def test_no_delegation_when_not_acting_as_delegate(self):
        """_check_delegated_permission is not called when acting_as_delegate_for is not set."""
        user = {"id": 1, "permissions": []}
        pm = _make_permission_manager(current_user=user)
        with patch.object(pm, "_check_delegated_permission") as mock_delegated:
            pm.check_permission("view_grades")
            mock_delegated.assert_not_called()


# ============================================================================
# has_permission Tests
# ============================================================================

class TestHasPermission:
    """Tests for PermissionManager.has_permission()."""

    def test_no_user_returns_false(self):
        """Returns False when no user is available."""
        pm = _make_permission_manager(current_user=None, session_valid=True)
        assert pm.has_permission("view_grades") is False

    def test_expired_session_returns_false(self):
        """Returns False when session checker returns False."""
        user = {"id": 1, "permissions": ["view_grades"]}
        pm = _make_permission_manager(current_user=user, session_valid=False)
        assert pm.has_permission("view_grades") is False

    def test_valid_session_with_permission_returns_true(self):
        """Returns True when session is valid and user has the permission."""
        user = {"id": 1, "permissions": ["view_grades"]}
        pm = _make_permission_manager(current_user=user, session_valid=True)
        assert pm.has_permission("view_grades") is True

    def test_valid_session_without_permission_returns_false(self):
        """Returns False when session is valid but user lacks the permission."""
        user = {"id": 1, "permissions": ["view_grades"]}
        pm = _make_permission_manager(current_user=user, session_valid=True)
        assert pm.has_permission("manage_users") is False

    def test_explicit_user_parameter(self):
        """current_user parameter overrides the getter."""
        pm = _make_permission_manager(current_user=None, session_valid=True)
        explicit_user = {"id": 5, "permissions": ["admin_panel"]}
        assert pm.has_permission("admin_panel", current_user=explicit_user) is True

    @patch(
        "university_system.infrastructure.auth.managers.permission_manager"
        ".PermissionManager._check_delegated_permission",
        return_value=True,
    )
    def test_has_permission_with_delegation(self, mock_delegated):
        """has_permission also checks delegated permissions."""
        user = {
            "id": 1,
            "permissions": [],
            "acting_as_delegate_for": 99,
        }
        pm = _make_permission_manager(current_user=user, session_valid=True)
        assert pm.has_permission("view_grades") is True

    def test_exception_in_has_permission_returns_false(self):
        """has_permission returns False on unexpected exceptions."""
        pm = _make_permission_manager(current_user=None, session_valid=True)
        # Force an exception by making get_current_user raise
        pm.get_current_user = Mock(side_effect=RuntimeError("boom"))
        assert pm.has_permission("anything") is False


# ============================================================================
# get_user_permissions Tests (mocked DB)
# ============================================================================

class TestGetUserPermissions:
    """Tests for PermissionManager.get_user_permissions()."""

    def _make_pm_with_db(self, fetchone_side_effects, fetchall_return=None):
        """Build a PermissionManager with controlled cursor responses."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = list(fetchone_side_effects)
        if fetchall_return is not None:
            cursor.fetchall.return_value = fetchall_return

        conn = MagicMock()
        conn.cursor.return_value = cursor
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)

        db_manager = Mock()
        db_manager.get_connection.return_value = conn

        pm = PermissionManager(db_manager, Mock(), Mock(), Mock())
        return pm

    def test_user_not_found_returns_empty_list(self):
        """Returns [] when user_id does not exist."""
        pm = self._make_pm_with_db(fetchone_side_effects=[None])
        assert pm.get_user_permissions(999) == []

    def test_role_not_found_returns_empty_list(self):
        """Returns [] when user's role is not in the roles table."""
        pm = self._make_pm_with_db(
            fetchone_side_effects=[("nonexistent_role",), None]
        )
        assert pm.get_user_permissions(1) == []

    def test_returns_permission_names(self):
        """Returns a list of permission name strings."""
        pm = self._make_pm_with_db(
            fetchone_side_effects=[("admin",), (1,)],  # role='admin', role_id=1
            fetchall_return=[("view_grades",), ("manage_users",)],
        )
        perms = pm.get_user_permissions(1)
        assert perms == ["view_grades", "manage_users"]
