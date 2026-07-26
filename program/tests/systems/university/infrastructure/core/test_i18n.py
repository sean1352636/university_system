"""Comprehensive tests for university_system.core.i18n module.

Tests internationalization features: translations loading, deep merge,
get_text with dot notation and fallback, language management, config
persistence, and reload.
"""

import json
import os
from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock, mock_open, call

import education_system.systems.university.infrastructure.i18n as i18n_mod
# The university i18n module now delegates to the shared engine;
# internal state (_current_language, _translations, _loaded) lives
# in the shared core module.
import education_system.platform.features.i18n.core as _core


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_i18n_state():
    """Reset global state before and after every test."""
    original_lang = _core._current_language
    original_trans = _core._translations.copy()
    original_loaded = _core._loaded

    # Reset to clean state — mark as loaded to prevent _ensure_loaded()
    # from calling init_i18n() which reads the real config file
    _core._current_language = "en"
    _core._translations = {}
    _core._loaded = True

    yield

    # Restore original state
    _core._current_language = original_lang
    _core._translations = original_trans
    _core._loaded = original_loaded


# ---------------------------------------------------------------------------
# SUPPORTED_LANGUAGES
# ---------------------------------------------------------------------------

class TestSupportedLanguages:
    """Tests for the SUPPORTED_LANGUAGES constant."""

    def test_supported_languages_has_13_entries(self):
        assert len(i18n_mod.SUPPORTED_LANGUAGES) == 13

    def test_english_is_supported(self):
        assert "en" in i18n_mod.SUPPORTED_LANGUAGES
        assert i18n_mod.SUPPORTED_LANGUAGES["en"] == "English"

    def test_all_codes_are_strings(self):
        for code, name in i18n_mod.SUPPORTED_LANGUAGES.items():
            assert isinstance(code, str)
            assert isinstance(name, str)
            assert len(code) == 2

    def test_expected_languages_present(self):
        expected = ["en", "es", "fr", "de", "zh", "ar", "pt", "ru", "ja", "ko", "cy", "pl", "ur"]
        for code in expected:
            assert code in i18n_mod.SUPPORTED_LANGUAGES


# ---------------------------------------------------------------------------
# _deep_merge_dicts
# ---------------------------------------------------------------------------

class TestDeepMergeDicts:
    """Tests for _deep_merge_dicts."""

    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        update = {"c": 3}
        result = _core._deep_merge(base, update)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_overwrite_value(self):
        base = {"a": 1}
        update = {"a": 2}
        result = _core._deep_merge(base, update)
        assert result == {"a": 2}

    def test_nested_merge(self):
        base = {"level1": {"a": 1, "b": 2}}
        update = {"level1": {"b": 3, "c": 4}}
        result = _core._deep_merge(base, update)
        assert result == {"level1": {"a": 1, "b": 3, "c": 4}}

    def test_deeply_nested_merge(self):
        base = {"l1": {"l2": {"l3": {"a": 1}}}}
        update = {"l1": {"l2": {"l3": {"b": 2}}}}
        result = _core._deep_merge(base, update)
        assert result == {"l1": {"l2": {"l3": {"a": 1, "b": 2}}}}

    def test_base_not_mutated(self):
        base = {"a": {"x": 1}}
        update = {"a": {"y": 2}}
        result = _core._deep_merge(base, update)
        assert result == {"a": {"x": 1, "y": 2}}
        assert base == {"a": {"x": 1}}  # original untouched

    def test_empty_base(self):
        result = _core._deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_empty_update(self):
        result = _core._deep_merge({"a": 1}, {})
        assert result == {"a": 1}

    def test_both_empty(self):
        result = _core._deep_merge({}, {})
        assert result == {}

    def test_dict_overrides_non_dict(self):
        base = {"a": "string"}
        update = {"a": {"nested": True}}
        result = _core._deep_merge(base, update)
        assert result == {"a": {"nested": True}}

    def test_non_dict_overrides_dict(self):
        base = {"a": {"nested": True}}
        update = {"a": "string"}
        result = _core._deep_merge(base, update)
        assert result == {"a": "string"}


# ---------------------------------------------------------------------------
# _load_split_translations
# ---------------------------------------------------------------------------

class TestLoadSplitTranslations:
    """Tests for _load_split_translations."""

    def test_loads_json_files_from_directory(self, tmp_path):
        lang_dir = tmp_path / "en"
        lang_dir.mkdir()

        (lang_dir / "menu.json").write_text(
            json.dumps({"menu": {"home": "Home", "about": "About"}}),
            encoding="utf-8"
        )
        (lang_dir / "errors.json").write_text(
            json.dumps({"errors": {"not_found": "Not Found"}}),
            encoding="utf-8"
        )

        result = _core._load_json_files_from_dir(lang_dir)
        assert result["menu"]["home"] == "Home"
        assert result["errors"]["not_found"] == "Not Found"

    def test_deep_merges_overlapping_keys(self, tmp_path):
        lang_dir = tmp_path / "en"
        lang_dir.mkdir()

        (lang_dir / "a.json").write_text(
            json.dumps({"shared": {"key1": "val1"}}),
            encoding="utf-8"
        )
        (lang_dir / "b.json").write_text(
            json.dumps({"shared": {"key2": "val2"}}),
            encoding="utf-8"
        )

        result = _core._load_json_files_from_dir(lang_dir)
        assert result["shared"]["key1"] == "val1"
        assert result["shared"]["key2"] == "val2"

    def test_handles_invalid_json(self, tmp_path):
        lang_dir = tmp_path / "en"
        lang_dir.mkdir()

        (lang_dir / "bad.json").write_text("not valid json", encoding="utf-8")
        (lang_dir / "good.json").write_text(
            json.dumps({"ok": "yes"}),
            encoding="utf-8"
        )

        result = _core._load_json_files_from_dir(lang_dir)
        assert result.get("ok") == "yes"

    def test_handles_empty_directory(self, tmp_path):
        lang_dir = tmp_path / "en"
        lang_dir.mkdir()

        result = _core._load_json_files_from_dir(lang_dir)
        assert result == {}

    def test_recursively_loads_subdirectories(self, tmp_path):
        lang_dir = tmp_path / "en"
        sub_dir = lang_dir / "system"
        sub_dir.mkdir(parents=True)

        (sub_dir / "system.json").write_text(
            json.dumps({"system": {"name": "Test"}}),
            encoding="utf-8"
        )

        result = _core._load_json_files_from_dir(lang_dir)
        assert result["system"]["name"] == "Test"


# ---------------------------------------------------------------------------
# _load_translation_file
# ---------------------------------------------------------------------------

class TestLoadTranslationFile:
    """Tests for _load_translation_file."""

    def test_loads_from_directory(self, tmp_path):
        lang_dir = tmp_path / "locales" / "en"
        lang_dir.mkdir(parents=True)
        (lang_dir / "main.json").write_text(
            json.dumps({"hello": "Hello"}),
            encoding="utf-8"
        )

        with patch.object(_core, '_locale_dirs', [tmp_path / "locales"]):
            result = _core._load_language("en")
            assert result.get("hello") == "Hello"

    def test_returns_empty_when_dir_missing(self, tmp_path):
        with patch.object(_core, '_locale_dirs', [tmp_path / "locales"]):
            result = _core._load_language("xx")
            assert result == {}

    def test_returns_empty_when_dir_empty(self, tmp_path):
        lang_dir = tmp_path / "locales" / "en"
        lang_dir.mkdir(parents=True)

        with patch.object(_core, '_locale_dirs', [tmp_path / "locales"]):
            result = _core._load_language("en")
            assert result == {}


# ---------------------------------------------------------------------------
# get_text
# ---------------------------------------------------------------------------

class TestGetText:
    """Tests for get_text function."""

    def test_simple_key_lookup(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {"en": {"greeting": "Hello"}}

        assert i18n_mod.get_text("greeting") == "Hello"

    def test_dot_notation_nested_lookup(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {
            "en": {"menu": {"file": {"open": "Open File"}}}
        }

        assert i18n_mod.get_text("menu.file.open") == "Open File"

    def test_returns_key_when_not_found(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {"en": {}}

        assert i18n_mod.get_text("nonexistent.key") == "nonexistent.key"

    def test_returns_default_when_not_found(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {"en": {}}

        assert i18n_mod.get_text("missing", default="Default Text") == "Default Text"

    def test_english_fallback_for_missing_translation(self):
        _core._loaded = True
        _core._current_language = "fr"
        _core._translations = {
            "fr": {},
            "en": {"greeting": "Hello (English)"}
        }

        assert i18n_mod.get_text("greeting") == "Hello (English)"

    def test_no_english_fallback_when_already_english(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {"en": {}}

        # Should return key, not try fallback
        assert i18n_mod.get_text("missing_key") == "missing_key"

    def test_format_kwargs(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {
            "en": {"welcome": "Hello, {name}! You have {count} messages."}
        }

        result = i18n_mod.get_text("welcome", name="Alice", count=5)
        assert result == "Hello, Alice! You have 5 messages."

    def test_format_kwargs_missing_key_returns_unformatted(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {
            "en": {"msg": "Hello {name}, your id is {id}"}
        }

        # Only providing 'name', missing 'id'
        result = i18n_mod.get_text("msg", name="Bob")
        assert result == "Hello {name}, your id is {id}"

    def test_returns_key_when_value_is_non_string(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {
            "en": {"number_value": 42}
        }

        result = i18n_mod.get_text("number_value")
        assert result == "number_value"

    def test_triggers_load_when_not_loaded(self):
        _core._loaded = False

        with patch.object(_core, '_load_all_translations') as mock_load:
            def do_load():
                _core._loaded = True
                _core._translations = {"en": {"test": "value"}}
            mock_load.side_effect = do_load

            result = i18n_mod.get_text("test")
            mock_load.assert_called_once()
            assert result == "value"

    def test_dot_notation_stops_at_non_dict(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {
            "en": {"a": "leaf_string"}
        }

        # Trying a.b should fail since "a" is a string, not a dict
        result = i18n_mod.get_text("a.b")
        assert result == "a.b"

    def test_english_fallback_with_dot_notation(self):
        _core._loaded = True
        _core._current_language = "es"
        _core._translations = {
            "es": {"menu": {}},
            "en": {"menu": {"help": "Help"}}
        }

        result = i18n_mod.get_text("menu.help")
        assert result == "Help"


# ---------------------------------------------------------------------------
# set_language
# ---------------------------------------------------------------------------

class TestSetLanguage:
    """Tests for set_language function."""

    def test_set_supported_language(self):
        with patch.object(_core, 'save_language_preference') as mock_save:
            result = i18n_mod.set_language("es")

        assert result is True
        assert _core._current_language == "es"
        mock_save.assert_called_once_with("es")

    def test_set_unsupported_language_returns_false(self):
        _core._current_language = "en"
        result = i18n_mod.set_language("xx")

        assert result is False
        assert _core._current_language == "en"  # unchanged

    def test_set_language_without_save(self):
        with patch.object(_core, 'save_language_preference') as mock_save:
            result = i18n_mod.set_language("fr", save=False)

        assert result is True
        assert _core._current_language == "fr"
        mock_save.assert_not_called()

    def test_set_language_with_save(self):
        with patch.object(_core, 'save_language_preference') as mock_save:
            i18n_mod.set_language("de", save=True)

        mock_save.assert_called_once_with("de")


# ---------------------------------------------------------------------------
# get_current_language / get_current_language_name
# ---------------------------------------------------------------------------

class TestGetCurrentLanguage:
    """Tests for get_current_language and get_current_language_name."""

    def test_get_current_language(self):
        _core._current_language = "ja"
        assert i18n_mod.get_current_language() == "ja"

    def test_get_current_language_name(self):
        _core._current_language = "en"
        assert i18n_mod.get_current_language_name() == "English"

    def test_get_current_language_name_unknown(self):
        _core._current_language = "zz"
        # Shared i18n returns the code itself for unsupported languages
        assert i18n_mod.get_current_language_name() == "zz"


# ---------------------------------------------------------------------------
# get_available_languages / get_available_language_list
# ---------------------------------------------------------------------------

class TestGetAvailableLanguages:
    """Tests for get_available_languages and get_available_language_list."""

    def test_get_available_languages_returns_copy(self):
        result = i18n_mod.get_available_languages()
        assert result == i18n_mod.SUPPORTED_LANGUAGES
        assert result is not i18n_mod.SUPPORTED_LANGUAGES  # must be a copy

    def test_get_available_language_list(self):
        result = i18n_mod.get_available_language_list()
        assert isinstance(result, list)
        assert len(result) == len(i18n_mod.SUPPORTED_LANGUAGES)
        # Each element should be (code, name)
        for code, name in result:
            assert isinstance(code, str)
            assert isinstance(name, str)
            assert code in i18n_mod.SUPPORTED_LANGUAGES


# ---------------------------------------------------------------------------
# load_saved_language
# ---------------------------------------------------------------------------

class TestLoadSavedLanguage:
    """Tests for load_saved_language."""

    def test_returns_en_when_no_config(self):
        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with patch.object(_core, '_LANGUAGE_CONFIG_PATH',mock_path):
            result = i18n_mod.load_saved_language()
            assert result == "en"

    def test_returns_saved_language(self, tmp_path):
        config_file = tmp_path / "language_config.json"
        config_file.write_text(json.dumps({"language": "es"}), encoding="utf-8")

        with patch.object(_core, '_LANGUAGE_CONFIG_PATH',config_file):
            result = i18n_mod.load_saved_language()
            assert result == "es"

    def test_returns_en_on_invalid_json(self, tmp_path):
        config_file = tmp_path / "language_config.json"
        config_file.write_text("not json", encoding="utf-8")

        with patch.object(_core, '_LANGUAGE_CONFIG_PATH',config_file):
            result = i18n_mod.load_saved_language()
            assert result == "en"

    def test_returns_en_when_key_missing(self, tmp_path):
        config_file = tmp_path / "language_config.json"
        config_file.write_text(json.dumps({"other": "data"}), encoding="utf-8")

        with patch.object(_core, '_LANGUAGE_CONFIG_PATH',config_file):
            result = i18n_mod.load_saved_language()
            assert result == "en"


# ---------------------------------------------------------------------------
# save_language_preference
# ---------------------------------------------------------------------------

class TestSaveLanguagePreference:
    """Tests for save_language_preference."""

    def test_saves_successfully(self, tmp_path):
        config_file = tmp_path / "config" / "language_config.json"

        with patch.object(_core, '_LANGUAGE_CONFIG_PATH', config_file), \
             patch.object(_core, '_CONFIG_DIR', tmp_path / "config"):
            result = i18n_mod.save_language_preference("fr")

        assert result is True
        assert config_file.exists()
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert data["language"] == "fr"

    def test_returns_false_on_io_error(self, tmp_path):
        config_file = tmp_path / "config" / "language_config.json"

        with patch.object(_core, '_LANGUAGE_CONFIG_PATH',config_file):
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                result = i18n_mod.save_language_preference("de")

        assert result is False

    def test_creates_parent_directory(self, tmp_path):
        config_file = tmp_path / "deep" / "nested" / "lang.json"

        with patch.object(_core, '_LANGUAGE_CONFIG_PATH', config_file), \
             patch.object(_core, '_CONFIG_DIR', tmp_path / "deep" / "nested"):
            result = i18n_mod.save_language_preference("ko")

        assert result is True
        assert config_file.parent.exists()


# ---------------------------------------------------------------------------
# init_i18n
# ---------------------------------------------------------------------------

class TestInitI18n:
    """Tests for init_i18n."""

    def test_init_with_language_code(self):
        i18n_mod._initialised = False
        _core._loaded = False
        _core._locale_dirs = []
        result = i18n_mod.init_i18n("fr")

        assert result == "fr"
        assert _core._current_language == "fr"
        assert _core._loaded is True

    def test_init_without_language_loads_saved(self):
        i18n_mod._initialised = False
        _core._loaded = False
        _core._locale_dirs = []
        with patch.object(_core, 'load_saved_language', return_value="de"):
            result = i18n_mod.init_i18n()

        assert result == "de"
        assert _core._current_language == "de"

    def test_init_unsupported_language_falls_back_to_english(self):
        i18n_mod._initialised = False
        _core._loaded = False
        _core._locale_dirs = []
        result = i18n_mod.init_i18n("zz")

        assert result == "en"
        assert _core._current_language == "en"

    def test_init_does_not_reload_if_already_loaded(self):
        # First call loads (manually set _loaded to True to simulate)
        _core._loaded = True
        _core._translations = {"en": {}, "fr": {}}

        # Since _loaded is True, _load_all_translations should NOT be called
        with patch.object(_core, '_load_all_translations') as mock_load:
            i18n_mod.init_i18n("fr")
            mock_load.assert_not_called()

    def test_init_returns_current_language(self):
        with patch.object(_core, '_load_all_translations'):
            result = i18n_mod.init_i18n("ja")
        assert result == "ja"


# ---------------------------------------------------------------------------
# reload_translations
# ---------------------------------------------------------------------------

class TestReloadTranslations:
    """Tests for reload_translations."""

    def test_reload_resets_loaded_flag_and_reloads(self):
        _core._loaded = True

        with patch.object(_core, '_load_all_translations') as mock_load:
            i18n_mod.reload_translations()

        assert mock_load.call_count == 1
        # _loaded should be False before _load_all_translations is called
        # but _load_all_translations sets it to True again

    def test_reload_forces_fresh_load(self):
        _core._loaded = True
        _core._translations = {"en": {"old": "data"}}

        with patch.object(_core, '_load_all_translations') as mock_load:
            def do_load():
                _core._translations = {"en": {"new": "data"}}
                _core._loaded = True
            mock_load.side_effect = do_load

            i18n_mod.reload_translations()

        assert _core._translations == {"en": {"new": "data"}}


# ---------------------------------------------------------------------------
# _ shorthand alias
# ---------------------------------------------------------------------------

class TestUnderscoreAlias:
    """Tests that _ is aliased to get_text."""

    def test_underscore_is_get_text(self):
        assert i18n_mod._ is i18n_mod.get_text

    def test_underscore_works_as_function(self):
        _core._loaded = True
        _core._current_language = "en"
        _core._translations = {"en": {"test": "Test Value"}}

        result = i18n_mod._("test")
        assert result == "Test Value"


# ---------------------------------------------------------------------------
# _load_all_translations
# ---------------------------------------------------------------------------

class TestLoadAllTranslations:
    """Tests for _load_all_translations."""

    def test_loads_all_supported_languages(self, tmp_path):
        locales_dir = tmp_path / "locales"
        # Create directories for a few languages
        for lang in ["en", "es"]:
            lang_dir = locales_dir / lang
            lang_dir.mkdir(parents=True)
            (lang_dir / "main.json").write_text(
                json.dumps({f"{lang}_key": f"{lang}_value"}),
                encoding="utf-8"
            )

        with patch.object(_core, '_locale_dirs', [locales_dir]):
            _core._load_all_translations()

        assert _core._loaded is True
        assert "en" in _core._translations
        assert "es" in _core._translations
        assert _core._translations["en"].get("en_key") == "en_value"
        assert _core._translations["es"].get("es_key") == "es_value"

    def test_sets_empty_dict_for_missing_language_dir(self, tmp_path):
        locales_dir = tmp_path / "locales"
        locales_dir.mkdir(parents=True)
        # No language directories at all

        with patch.object(_core, '_locale_dirs', [locales_dir]):
            _core._load_all_translations()

        assert _core._loaded is True
        # All languages should have empty dicts
        for lang_code in i18n_mod.SUPPORTED_LANGUAGES:
            assert _core._translations.get(lang_code) == {}


# ---------------------------------------------------------------------------
# __all__ exports
# ---------------------------------------------------------------------------

class TestI18nAllExports:
    """Tests for __all__ exports."""

    def test_all_exports_are_importable(self):
        for name in i18n_mod.__all__:
            assert hasattr(i18n_mod, name), f"{name} listed in __all__ but not found"

    def test_key_items_in_all(self):
        expected = [
            "init_i18n", "get_text", "set_language",
            "get_current_language", "get_current_language_name",
            "get_available_languages", "get_available_language_list",
            "load_saved_language", "save_language_preference",
            "reload_translations", "SUPPORTED_LANGUAGES", "_",
        ]
        for name in expected:
            assert name in i18n_mod.__all__
