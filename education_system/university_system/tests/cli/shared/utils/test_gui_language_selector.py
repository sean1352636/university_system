"""Tests for gui_language_selector shim."""
from unittest.mock import patch, MagicMock

from education_system.university_system.modules.shared.utils import gui_language_selector


def test_show_gui_language_selector_delegates():
    with patch.object(gui_language_selector, "show_language_selector",
                      return_value="ja") as m:
        assert gui_language_selector.show_gui_language_selector() == "ja"
        m.assert_called_once()


def test_show_gui_language_selector_with_parent():
    parent = MagicMock()
    with patch.object(gui_language_selector, "show_language_selector",
                      return_value="es") as m:
        assert gui_language_selector.show_gui_language_selector(parent) == "es"
        m.assert_called_once_with(parent)


def test_create_language_menu_button_returns_button():
    parent = MagicMock()
    fake_btn = MagicMock()
    with patch.object(gui_language_selector, "ttk") as ttk_mod, \
         patch.object(gui_language_selector, "get_current_language_name",
                      return_value="English"):
        ttk_mod.Button.return_value = fake_btn
        out = gui_language_selector.create_language_menu_button(parent)
        assert out is fake_btn
        ttk_mod.Button.assert_called_once()
        kwargs = ttk_mod.Button.call_args.kwargs
        assert "English" in kwargs["text"]


def test_create_language_menu_button_callback_reloads_on_change():
    parent = MagicMock()
    fake_btn = MagicMock()
    captured = {}
    def fake_button(*a, **kwargs):
        captured["command"] = kwargs.get("command")
        return fake_btn
    with patch.object(gui_language_selector, "ttk") as ttk_mod, \
         patch.object(gui_language_selector, "get_current_language_name",
                      return_value="English"), \
         patch.object(gui_language_selector, "get_current_language",
                      side_effect=["en", "fr"]), \
         patch.object(gui_language_selector, "show_language_selector"), \
         patch.object(gui_language_selector, "reload_translations") as reload_mock:
        ttk_mod.Button.side_effect = fake_button
        gui_language_selector.create_language_menu_button(parent)
        # Invoke the captured callback
        captured["command"]()
        reload_mock.assert_called_once()


def test_create_language_menu_button_callback_no_reload_when_same():
    parent = MagicMock()
    fake_btn = MagicMock()
    captured = {}
    def fake_button(*a, **kwargs):
        captured["command"] = kwargs.get("command")
        return fake_btn
    with patch.object(gui_language_selector, "ttk") as ttk_mod, \
         patch.object(gui_language_selector, "get_current_language_name",
                      return_value="English"), \
         patch.object(gui_language_selector, "get_current_language",
                      side_effect=["en", "en"]), \
         patch.object(gui_language_selector, "show_language_selector"), \
         patch.object(gui_language_selector, "reload_translations") as reload_mock:
        ttk_mod.Button.side_effect = fake_button
        gui_language_selector.create_language_menu_button(parent)
        captured["command"]()
        reload_mock.assert_not_called()


def test_module_all_includes_public_api():
    assert "show_gui_language_selector" in gui_language_selector.__all__
    assert "create_language_menu_button" in gui_language_selector.__all__
    assert "LanguageSelectorDialog" in gui_language_selector.__all__
