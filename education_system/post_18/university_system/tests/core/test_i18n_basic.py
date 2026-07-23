"""Tests for university_system.core.i18n."""
from pathlib import Path

from education_system.post_18.university_system.core import i18n


class TestModuleSurface:
    def test_required_exports(self):
        for name in (
            "init_i18n", "get_text", "t", "set_language", "get_current_language",
            "get_current_language_name", "get_available_languages",
            "get_available_language_list", "load_saved_language",
            "save_language_preference", "reload_translations",
            "SUPPORTED_LANGUAGES", "_",
        ):
            assert hasattr(i18n, name)

    def test_underscore_alias_is_get_text(self):
        assert i18n._ is i18n.get_text


class TestInitI18n:
    def test_returns_language_code(self):
        code = i18n.init_i18n()
        assert isinstance(code, str)
        assert code  # non-empty

    def test_set_language_via_init(self):
        i18n.init_i18n()
        i18n.init_i18n("en")
        assert i18n.get_current_language() == "en"


class TestLocaleDir:
    def test_university_locales_path_under_data(self):
        # Internal constant: verify it points under the university data dir
        assert i18n._UNIVERSITY_LOCALES.name == "locales"
        assert isinstance(i18n._UNIVERSITY_LOCALES, Path)


class TestConfigPath:
    def test_get_config_path_returns_path(self):
        p = i18n._get_config_path()
        assert isinstance(p, Path)
        assert p.name == "language_config.json"


class TestGetTextWorks:
    def test_returns_string_for_any_key(self):
        result = i18n.get_text("nonexistent.key.xyz")
        assert isinstance(result, str)
