"""Tests for document_manager.manager (DocumentManager core)"""
from unittest.mock import patch, MagicMock

import pytest

from education_system.systems.university.infrastructure.utils.document_manager import (
    manager as manager_mod,
)


class TestInit:
    def test_initializes_with_admin_defaults(self, doc_manager):
        assert doc_manager.current_user == "admin"
        assert doc_manager.user_role == "admin"

    def test_uses_get_current_user_when_available(self, patched_connection, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch.object(manager_mod, "get_current_user",
                          return_value={"username": "bob", "role": "registrar"}):
            from education_system.systems.university.infrastructure.utils.document_manager import (
                DocumentManager,
            )
            dm = DocumentManager()
            assert dm.current_user == "bob"
            assert dm.user_role == "registrar"

    def test_falls_back_when_get_current_user_raises(self, patched_connection, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch.object(manager_mod, "get_current_user", side_effect=RuntimeError):
            from education_system.systems.university.infrastructure.utils.document_manager import (
                DocumentManager,
            )
            dm = DocumentManager()
            assert dm.current_user == "admin"


class TestCheckAuthentication:
    def test_returns_true_with_session(self, doc_manager):
        with patch.object(manager_mod, "get_current_user",
                          return_value={"username": "carol", "role": "staff"}):
            assert doc_manager.check_authentication() is True
            assert doc_manager.current_user == "carol"

    def test_returns_true_when_already_set(self, doc_manager):
        with patch.object(manager_mod, "get_current_user", return_value=None):
            doc_manager.current_user = "x"
            assert doc_manager.check_authentication() is True

    def test_returns_false_when_no_user(self, doc_manager):
        with patch.object(manager_mod, "get_current_user", side_effect=RuntimeError):
            doc_manager.current_user = None
            assert doc_manager.check_authentication() is False


class TestMenus:
    def test_admin_menu_dispatch_each_choice(self, doc_manager, feed_input):
        # Stub every dispatched method, run through every choice
        method_names = [
            "upload_student_document", "view_student_documents", "update_document_status",
            "check_document_expiry", "advanced_search", "display_dashboard",
            "bulk_operations_menu", "generate_reports_menu", "manage_document_templates",
            "document_versioning_menu", "workflow_management", "notification_center",
            "bulk_import_documents", "export_data_menu", "ocr_integration_menu",
            "api_server_menu", "web_interface_menu", "document_type_management",
            "system_settings", "backup_system",
        ]
        for m in method_names:
            setattr(doc_manager, m, MagicMock())
        for i, m in enumerate(method_names, start=1):
            doc_manager.handle_admin_choice(str(i))
            getattr(doc_manager, m).assert_called_once()

    def test_admin_menu_invalid_choice(self, doc_manager, capsys):
        doc_manager.handle_admin_choice("99")
        out = capsys.readouterr().out
        assert "Invalid" in out or "invalid" in out

    def test_admin_menu_exit_choice(self, doc_manager, capsys):
        # Choice 21 = Exit; should print goodbye and return
        doc_manager.handle_admin_choice("21")
        assert "Goodbye" in capsys.readouterr().out

    def test_student_menu_dispatch(self, doc_manager):
        for m in ["view_my_documents", "student_upload_document",
                  "student_dashboard", "check_my_requirements",
                  "my_document_status", "my_notifications"]:
            setattr(doc_manager, m, MagicMock())
        for i, m in enumerate(
            ["view_my_documents", "student_upload_document", "student_dashboard",
             "check_my_requirements", "my_document_status", "my_notifications"],
            start=1,
        ):
            doc_manager.handle_student_choice(str(i))
            getattr(doc_manager, m).assert_called_once()

    def test_student_menu_invalid(self, doc_manager, capsys):
        doc_manager.handle_student_choice("99")
        assert "Invalid" in capsys.readouterr().out or "invalid" in capsys.readouterr().out

    def test_student_menu_exit(self, doc_manager, capsys):
        doc_manager.handle_student_choice("7")
        assert "Goodbye" in capsys.readouterr().out

    def test_display_admin_menu_calls_handler(self, doc_manager, feed_input):
        feed_input("21")  # exit
        with patch.object(doc_manager, "handle_admin_choice") as h:
            doc_manager.display_admin_menu()
            h.assert_called_once_with("21")

    def test_display_student_menu_calls_handler(self, doc_manager, feed_input):
        feed_input("7")  # exit
        with patch.object(doc_manager, "handle_student_choice") as h:
            doc_manager.display_student_menu()
            h.assert_called_once_with("7")

    def test_display_main_menu_requires_auth(self, doc_manager, capsys):
        with patch.object(doc_manager, "check_authentication", return_value=False):
            doc_manager.display_main_menu()
        assert "Authentication" in capsys.readouterr().out

    def test_display_main_menu_routes_admin(self, doc_manager):
        doc_manager.user_role = "admin"
        called = {"n": 0}
        def fake_admin():
            called["n"] += 1
            if called["n"] >= 2:
                raise StopIteration
        with patch.object(doc_manager, "display_admin_menu", side_effect=fake_admin):
            with pytest.raises(StopIteration):
                doc_manager.display_main_menu()

    def test_display_main_menu_routes_student(self, doc_manager):
        # check_authentication() re-syncs the role from the session, so the
        # session user must be the student we want to route.
        with patch.object(manager_mod, "get_current_user",
                          return_value={"username": "sam", "role": "student"}):
            with patch.object(doc_manager, "display_student_menu", side_effect=StopIteration):
                with pytest.raises(StopIteration):
                    doc_manager.display_main_menu()


class TestStandaloneFunctions:
    def test_display_document_management_menu_handles_keyboard_interrupt(self, capsys, patched_connection, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch.object(manager_mod, "DocumentManager") as DMClass:
            inst = MagicMock()
            inst.display_main_menu.side_effect = KeyboardInterrupt
            DMClass.return_value = inst
            manager_mod.display_document_management_menu()
        assert "shutdown" in capsys.readouterr().out.lower()

    def test_display_document_management_menu_handles_generic_exception(self, capsys, patched_connection, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch.object(manager_mod, "DocumentManager") as DMClass:
            inst = MagicMock()
            inst.display_main_menu.side_effect = RuntimeError("boom")
            DMClass.return_value = inst
            manager_mod.display_document_management_menu()
        assert "error" in capsys.readouterr().out.lower()

    def test_main_calls_display_main_menu(self, patched_connection, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch.object(manager_mod, "DocumentManager") as DMClass, \
             patch("education_system.systems.university.infrastructure.auth.UserAuth") as UA, \
             patch("education_system.systems.university.infrastructure.auth.set_auth_instance"), \
             patch("education_system.systems.university.infrastructure.auth.get_current_user",
                   return_value={"username": "u", "role": "admin"}):
            dm_inst = MagicMock()
            DMClass.return_value = dm_inst
            manager_mod.main()
            dm_inst.display_main_menu.assert_called_once()
