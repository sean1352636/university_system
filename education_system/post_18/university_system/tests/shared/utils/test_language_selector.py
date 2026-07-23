"""Tests for language_selector (CLI) shim."""
from unittest.mock import patch

from education_system.post_18.university_system.modules.shared.utils import language_selector


def test_display_language_selector_delegates():
    with patch.object(language_selector, "show_language_selector_cli", return_value="es") as m:
        assert language_selector.display_language_selector() == "es"
        m.assert_called_once()


def test_display_language_selector_force_show_ignored():
    with patch.object(language_selector, "show_language_selector_cli", return_value="fr") as m:
        assert language_selector.display_language_selector(force_show=True) == "fr"
        m.assert_called_once_with()


def test_display_language_menu_option_prints_current(capsys):
    with patch.object(language_selector, "get_current_language", return_value="en"):
        language_selector.display_language_menu_option()
    out = capsys.readouterr().out
    assert "en" in out
    assert "Current language" in out


def test_get_startup_language_choice_returns_current():
    with patch.object(language_selector, "get_current_language", return_value="de"):
        assert language_selector.get_startup_language_choice() == "de"


def test_module_all_includes_public_api():
    assert "display_language_selector" in language_selector.__all__
    assert "display_language_menu_option" in language_selector.__all__
    assert "get_startup_language_choice" in language_selector.__all__
