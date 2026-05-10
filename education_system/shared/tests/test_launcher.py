"""Contract tests for the launcher package — dispatch, roles, menus, auth.

Verifies the state-machine transitions in dispatch_gui/dispatch_cli,
role picker logic, menu helpers, and the dispatch table completeness.
"""

import pytest
from unittest.mock import patch, MagicMock


# ── Dispatch table completeness ──────────────────────────────────────────────

class TestDispatchTable:
    def test_all_system_mode_combos_present(self):
        from education_system.launcher.systems import LAUNCHERS
        systems = ("university",)
        modes = ("cli", "gui", "api", "test")
        for system in systems:
            for mode in modes:
                assert (system, mode) in LAUNCHERS, f"Missing ({system}, {mode})"

    def test_all_launchers_are_callable(self):
        from education_system.launcher.systems import LAUNCHERS
        for key, fn in LAUNCHERS.items():
            assert callable(fn), f"LAUNCHERS[{key}] is not callable"

    def test_auth_systems_cover_all(self):
        from education_system.launcher.systems import AUTH_GUI_SYSTEMS, AUTH_CLI_SYSTEMS
        expected = {"university"}
        assert AUTH_GUI_SYSTEMS == expected
        assert AUTH_CLI_SYSTEMS == expected


# ── Role picker ──────────────────────────────────────────────────────────────

class TestRoles:
    def test_is_superadmin_university_admin(self):
        from education_system.launcher.roles import is_superadmin
        user = {"systems": [{"system_key": "university", "role": "admin"}]}
        assert is_superadmin(user)

    def test_is_superadmin_non_admin_role(self):
        from education_system.launcher.roles import is_superadmin
        user = {"systems": [{"system_key": "university", "role": "student"}]}
        assert not is_superadmin(user)

    def test_is_superadmin_none(self):
        from education_system.launcher.roles import is_superadmin
        assert not is_superadmin(None)
        assert not is_superadmin({})
        assert not is_superadmin({"systems": []})

    def test_system_names_complete(self):
        from education_system.launcher.roles import SYSTEM_NAMES
        assert "university" in SYSTEM_NAMES

    @patch("builtins.input", return_value="1")
    def test_pick_role_cli_returns_admin(self, _mock_input):
        from education_system.launcher.roles import pick_role_cli
        assert pick_role_cli("university") == "admin"

    @patch("builtins.input", return_value="4")
    def test_pick_role_cli_returns_student(self, _mock_input):
        from education_system.launcher.roles import pick_role_cli
        assert pick_role_cli("university") == "student"


# ── Menu helpers ─────────────────────────────────────────────────────────────

class TestMenus:
    @patch("builtins.input", return_value="1")
    def test_select_mode_cli(self, _):
        from education_system.launcher.menus import cli_select_mode
        assert cli_select_mode() == "cli"

    @patch("builtins.input", return_value="2")
    def test_select_mode_gui(self, _):
        from education_system.launcher.menus import cli_select_mode
        assert cli_select_mode() == "gui"

    @patch("builtins.input", return_value="0")
    def test_select_mode_exit(self, _):
        from education_system.launcher.menus import cli_select_mode
        assert cli_select_mode() is None

    @patch("builtins.input", return_value="1")
    def test_select_system_university(self, _):
        from education_system.launcher.menus import cli_select_system
        assert cli_select_system() == "university"

    @patch("builtins.input", return_value="0")
    def test_select_system_back(self, _):
        from education_system.launcher.menus import cli_select_system
        assert cli_select_system() is None


# ── Dispatch state transitions ───────────────────────────────────────────────
# These tests mock the launchers and switch module to verify the dispatch
# loop handles every branch correctly.

class TestDispatchGUI:
    """Table-driven tests for dispatch_gui state transitions."""

    def _make_user(self, superadmin=False):
        if superadmin:
            return {"systems": [
                {"system_key": s, "role": "admin"}
                for s in ("university", "college", "school", "primary")
            ]}
        return {"systems": [{"system_key": "university", "role": "student"}]}

    @patch("education_system.launcher.dispatch.LAUNCHERS")
    @patch("education_system.switch.consume", return_value=None)
    def test_normal_exit_no_switch(self, mock_consume, mock_launchers):
        from education_system.launcher.dispatch import dispatch_gui
        mock_launcher = MagicMock()
        mock_launchers.get.return_value = mock_launcher

        user = self._make_user()
        dispatch_gui(user, "university", "student", MagicMock())

        mock_launcher.assert_called_once()

    @patch("education_system.launcher.dispatch.LAUNCHERS")
    @patch("education_system.switch.consume", side_effect=[("college", "gui"), None])
    def test_switch_to_another_system(self, mock_consume, mock_launchers):
        from education_system.launcher.dispatch import dispatch_gui
        mock_launcher = MagicMock()
        mock_launchers.get.return_value = mock_launcher

        user = self._make_user()
        user["systems"].append({"system_key": "college", "role": "student"})
        dispatch_gui(user, "university", "student", MagicMock())

        assert mock_launcher.call_count == 2

    @patch("education_system.launcher.dispatch.gui_universal_login", return_value=None)
    @patch("education_system.launcher.dispatch.LAUNCHERS")
    @patch("education_system.switch.consume", return_value=("__login__", "gui"))
    def test_login_redirect_cancelled(self, mock_consume, mock_launchers, mock_login):
        from education_system.launcher.dispatch import dispatch_gui
        mock_launchers.get.return_value = MagicMock()

        user = self._make_user()
        dispatch_gui(user, "university", "student", MagicMock())

        mock_login.assert_called_once()


class TestDispatchCLI:
    """Table-driven tests for dispatch_cli state transitions."""

    def _make_user(self, superadmin=False):
        if superadmin:
            return {"systems": [
                {"system_key": s, "role": "admin"}
                for s in ("university", "college", "school", "primary")
            ]}
        return {"systems": [{"system_key": "school", "role": "teacher"}]}

    @patch("education_system.launcher.dispatch.LAUNCHERS")
    @patch("education_system.switch.consume", return_value=None)
    def test_normal_exit(self, mock_consume, mock_launchers):
        from education_system.launcher.dispatch import dispatch_cli
        mock_launcher = MagicMock()
        mock_launchers.get.return_value = mock_launcher

        user = self._make_user()
        dispatch_cli(user, "school", "teacher", MagicMock())

        mock_launcher.assert_called_once()

    @patch("education_system.launcher.dispatch.cli_universal_login", return_value=None)
    @patch("education_system.launcher.dispatch.LAUNCHERS")
    @patch("education_system.switch.consume", return_value=("__login__", "cli"))
    def test_login_redirect_cancelled(self, mock_consume, mock_launchers, mock_login):
        from education_system.launcher.dispatch import dispatch_cli
        mock_launchers.get.return_value = MagicMock()

        user = self._make_user()
        dispatch_cli(user, "school", "teacher", MagicMock())

        mock_login.assert_called_once()


# ── Auth module ──────────────────────────────────────────────────────────────

class TestAuthModule:
    def test_init_shared_auth_creates_db(self, tmp_path):
        """init_shared_auth should create the auth DB without errors."""
        import os
        os.environ["EDU_AUTH_DB"] = str(tmp_path / "auth.db")
        try:
            # Just verify it doesn't crash — actual DB creation
            # is tested more thoroughly in test_shared_services
            from education_system.launcher.auth import init_shared_auth
            init_shared_auth()
        finally:
            os.environ.pop("EDU_AUTH_DB", None)
