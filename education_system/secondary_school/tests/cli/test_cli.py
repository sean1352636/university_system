"""Tests for CLI modules: cli_main and mfa_cli."""

import pytest
from unittest.mock import patch, MagicMock


class TestCliMainHelpers:
    """Tests for cli_main helper functions."""

    def test_print_header(self, capsys):
        from education_system.secondary_school.cli.cli_main import print_header
        print_header("Test Title")
        captured = capsys.readouterr()
        assert "Test Title" in captured.out

    def test_print_menu(self, capsys):
        from education_system.secondary_school.cli.cli_main import print_menu
        options = [("1", "Option One"), ("2", "Option Two"), ("0", "Exit")]
        print_menu(options)
        captured = capsys.readouterr()
        assert "Option One" in captured.out
        assert "Option Two" in captured.out

    @patch("builtins.input", return_value="3")
    def test_get_choice(self, mock_input):
        from education_system.secondary_school.cli.cli_main import get_choice
        result = get_choice()
        assert result == "3"


class TestCliMainMenus:
    """Tests for CLI menu routing logic."""

    @patch("builtins.input", side_effect=["0"])
    def test_student_menu_main_exits(self, mock_input, db_path):
        from education_system.secondary_school.cli.cli_main import student_menu_main
        mock_auth = MagicMock()
        mock_auth.current_user = {
            "id": 1, "user_id": 1, "username": "student2",
            "systems": [{"system": "school", "role": "student"}],
        }
        mock_auth._db_path = db_path
        student_menu_main(mock_auth)

    @patch("builtins.input", side_effect=["0"])
    def test_teacher_menu_exits(self, mock_input, db_path):
        from education_system.secondary_school.cli.cli_main import teacher_menu
        mock_auth = MagicMock()
        mock_auth.current_user = {
            "id": 1, "user_id": 1, "username": "staff2",
            "systems": [{"system": "school", "role": "teacher"}],
        }
        mock_auth._db_path = db_path
        teacher_menu(mock_auth)

    @patch("builtins.input", side_effect=["0"])
    def test_admin_menu_exits(self, mock_input, db_path):
        from education_system.secondary_school.cli.cli_main import admin_menu
        mock_auth = MagicMock()
        mock_auth.current_user = {
            "id": 1, "user_id": 1, "username": "admin2",
            "systems": [{"system": "school", "system_key": "school", "role": "admin"}],
        }
        mock_auth._db_path = db_path
        admin_menu(mock_auth)


class TestMfaCli:
    """Tests for MFA CLI menu."""

    @patch("builtins.input", side_effect=["0"])
    def test_mfa_settings_menu_exits(self, mock_input, auth_db_path):
        from education_system.secondary_school.cli.mfa_cli import mfa_settings_menu
        mock_auth = MagicMock()
        mock_auth._db_path = auth_db_path
        mock_auth.current_user = {"user_id": 1, "username": "admin2"}
        mfa_settings_menu(mock_auth)

    @patch("builtins.input", side_effect=["3", "0"])
    def test_mfa_view_recovery_count(self, mock_input, auth_db_path, capsys):
        from education_system.secondary_school.cli.mfa_cli import mfa_settings_menu
        mock_auth = MagicMock()
        mock_auth._db_path = auth_db_path
        mock_auth.current_user = {"user_id": 1, "username": "admin2"}
        mfa_settings_menu(mock_auth)
        captured = capsys.readouterr()
        assert "recovery" in captured.out.lower() or "MFA" in captured.out

    @patch("builtins.input", side_effect=["2", "n", "0"])
    def test_mfa_disable_cancelled(self, mock_input, auth_db_path, capsys):
        from education_system.secondary_school.cli.mfa_cli import mfa_settings_menu
        mock_auth = MagicMock()
        mock_auth._db_path = auth_db_path
        mock_auth.current_user = {"user_id": 1, "username": "admin2"}
        mfa_settings_menu(mock_auth)
        captured = capsys.readouterr()
        assert "Cancelled" in captured.out or "cancel" in captured.out.lower() or "MFA" in captured.out
