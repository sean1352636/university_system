"""Comprehensive tests for university_system.core.institution_settings module.

Tests institution contact configuration with env var overrides, file-based
settings, caching, save/reset, and convenience functions.
"""

import json
import os
from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock

import education_system.systems.university.infrastructure.institution_settings as settings_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Reset module-level cache before and after each test."""
    original_settings = settings_mod._settings.copy()
    original_loaded = settings_mod._settings_loaded

    settings_mod._settings = {}
    settings_mod._settings_loaded = False

    yield

    settings_mod._settings = original_settings
    settings_mod._settings_loaded = original_loaded


# ---------------------------------------------------------------------------
# DEFAULT_INSTITUTION_SETTINGS
# ---------------------------------------------------------------------------

class TestDefaultInstitutionSettings:
    """Tests for the DEFAULT_INSTITUTION_SETTINGS constant."""

    def test_has_expected_keys(self):
        expected_keys = [
            "institution_name", "main_phone", "main_email", "website",
            "student_union_phone", "student_union_email",
            "elections_email", "elections_phone",
            "events_support_phone", "events_support_email",
            "address_line1", "address_line2", "postcode", "country",
            "mfa_recovery_code_format", "mfa_recovery_code_hint",
        ]
        for key in expected_keys:
            assert key in settings_mod.DEFAULT_INSTITUTION_SETTINGS, \
                f"Missing key: {key}"

    def test_all_values_are_strings(self):
        for key, value in settings_mod.DEFAULT_INSTITUTION_SETTINGS.items():
            assert isinstance(value, str), \
                f"Value for {key} is {type(value)}, expected str"

    def test_institution_name_default(self):
        assert settings_mod.DEFAULT_INSTITUTION_SETTINGS["institution_name"] == "Teesside University"

    def test_country_default(self):
        assert settings_mod.DEFAULT_INSTITUTION_SETTINGS["country"] == "United Kingdom"


# ---------------------------------------------------------------------------
# _get_config_path
# ---------------------------------------------------------------------------

class TestGetConfigPath:
    """Tests for _get_config_path."""

    def test_returns_path_object(self):
        result = settings_mod._get_config_path()
        assert isinstance(result, Path)

    def test_path_ends_with_expected_filename(self):
        result = settings_mod._get_config_path()
        assert result.name == "institution_settings.json"


# ---------------------------------------------------------------------------
# load_settings
# ---------------------------------------------------------------------------

class TestLoadSettings:
    """Tests for load_settings."""

    def test_returns_defaults_when_no_file_and_no_env(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"
        # config_file does not exist

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            with patch.dict(os.environ, {}, clear=False):
                # Remove any UNIVERSITY_ env vars that might interfere
                env_clean = {k: v for k, v in os.environ.items()
                             if not k.startswith("UNIVERSITY_")}
                with patch.dict(os.environ, env_clean, clear=True):
                    result = settings_mod.load_settings()

        assert result["institution_name"] == "Teesside University"
        assert result["country"] == "United Kingdom"

    def test_file_settings_override_defaults(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"
        config_file.write_text(
            json.dumps({"institution_name": "MIT", "country": "USA"}),
            encoding="utf-8"
        )

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.load_settings()

        assert result["institution_name"] == "MIT"
        assert result["country"] == "USA"
        # Other defaults still present
        assert result["main_phone"] == settings_mod.DEFAULT_INSTITUTION_SETTINGS["main_phone"]

    def test_env_vars_override_file_and_defaults(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"
        config_file.write_text(
            json.dumps({"institution_name": "MIT"}),
            encoding="utf-8"
        )

        env_overrides = {
            "UNIVERSITY_INSTITUTION_NAME": "Harvard",
            "UNIVERSITY_COUNTRY": "Canada"
        }
        # Start with clean env plus our overrides
        env_clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("UNIVERSITY_")}
        env_clean.update(env_overrides)

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.load_settings()

        assert result["institution_name"] == "Harvard"
        assert result["country"] == "Canada"

    def test_returns_cached_on_second_call(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result1 = settings_mod.load_settings()
                result2 = settings_mod.load_settings()

        assert result1 == result2

    def test_cached_result_is_a_copy(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result1 = settings_mod.load_settings()
                result2 = settings_mod.load_settings()

        assert result1 is not result2  # should be copies

    def test_handles_invalid_json_file(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"
        config_file.write_text("not valid json", encoding="utf-8")

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.load_settings()

        # Should fall back to defaults
        assert result["institution_name"] == "Teesside University"

    def test_env_var_prefix_is_UNIVERSITY(self, tmp_path):
        """Verify that the env var prefix is UNIVERSITY_ for all default keys."""
        config_file = tmp_path / "institution_settings.json"

        env_overrides = {"UNIVERSITY_MAIN_PHONE": "+1 555 0000"}
        env_clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("UNIVERSITY_")}
        env_clean.update(env_overrides)

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.load_settings()

        assert result["main_phone"] == "+1 555 0000"

    def test_only_default_keys_read_from_env(self, tmp_path):
        """Env vars outside DEFAULT_INSTITUTION_SETTINGS keys are ignored."""
        config_file = tmp_path / "institution_settings.json"

        env_overrides = {"UNIVERSITY_CUSTOM_THING": "custom_value"}
        env_clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("UNIVERSITY_")}
        env_clean.update(env_overrides)

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.load_settings()

        assert "custom_thing" not in result


# ---------------------------------------------------------------------------
# get_setting
# ---------------------------------------------------------------------------

class TestGetSetting:
    """Tests for get_setting."""

    def test_returns_existing_setting(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_setting("institution_name")

        assert result == "Teesside University"

    def test_returns_default_for_missing_key(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_setting("nonexistent_key", default="fallback")

        assert result == "fallback"

    def test_returns_none_for_missing_key_no_default(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_setting("nonexistent_key")

        assert result is None

    def test_get_setting_respects_env_override(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        env_overrides = {"UNIVERSITY_WEBSITE": "https://example.com"}
        env_clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("UNIVERSITY_")}
        env_clean.update(env_overrides)

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_setting("website")

        assert result == "https://example.com"


# ---------------------------------------------------------------------------
# save_settings
# ---------------------------------------------------------------------------

class TestSaveSettings:
    """Tests for save_settings."""

    def test_saves_to_file(self, tmp_path):
        config_file = tmp_path / "config" / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.save_settings({"institution_name": "Oxford"})

        assert result is True
        assert config_file.exists()

        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert data["institution_name"] == "Oxford"

    def test_merges_with_existing_settings(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                settings_mod.save_settings({"country": "Germany"})

        data = json.loads(config_file.read_text(encoding="utf-8"))
        # Original defaults should be present plus the override
        assert data["country"] == "Germany"
        assert data["institution_name"] == "Teesside University"

    def test_updates_cache(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                settings_mod.save_settings({"main_email": "new@uni.com"})

                # Subsequent reads should reflect the saved value
                result = settings_mod.get_setting("main_email")

        assert result == "new@uni.com"

    def test_returns_false_on_io_error(self, tmp_path):
        config_file = tmp_path / "config" / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                with patch("builtins.open", side_effect=IOError("disk full")):
                    result = settings_mod.save_settings({"key": "val"})

        assert result is False

    def test_creates_parent_directory(self, tmp_path):
        config_file = tmp_path / "deep" / "nested" / "settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.save_settings({"institution_name": "Test"})

        assert result is True
        assert config_file.parent.exists()


# ---------------------------------------------------------------------------
# reset_settings
# ---------------------------------------------------------------------------

class TestResetSettings:
    """Tests for reset_settings."""

    def test_clears_cache(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                # Load once to populate cache
                settings_mod.load_settings()
                assert settings_mod._settings_loaded is True

                # Reset
                settings_mod.reset_settings()
                assert settings_mod._settings_loaded is False
                assert settings_mod._settings == {}

    def test_forces_reload_on_next_access(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                # First load
                r1 = settings_mod.load_settings()
                assert settings_mod._settings_loaded is True

                # Write a file to change the settings
                config_file.write_text(
                    json.dumps({"institution_name": "New Name"}),
                    encoding="utf-8"
                )

                # Without reset, should still return cached
                r2 = settings_mod.load_settings()
                assert r2["institution_name"] == "Teesside University"  # cached

                # After reset, should reload from file
                settings_mod.reset_settings()
                r3 = settings_mod.load_settings()
                assert r3["institution_name"] == "New Name"


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for get_elections_phone, get_events_support_phone, get_mfa_recovery_format_hint."""

    def test_get_elections_phone_default(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_elections_phone()

        assert result == settings_mod.DEFAULT_INSTITUTION_SETTINGS["elections_phone"]

    def test_get_elections_phone_from_env(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        env_overrides = {"UNIVERSITY_ELECTIONS_PHONE": "+1 555 1234"}
        env_clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("UNIVERSITY_")}
        env_clean.update(env_overrides)

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_elections_phone()

        assert result == "+1 555 1234"

    def test_get_events_support_phone_default(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_events_support_phone()

        assert result == settings_mod.DEFAULT_INSTITUTION_SETTINGS["events_support_phone"]

    def test_get_events_support_phone_from_env(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        env_overrides = {"UNIVERSITY_EVENTS_SUPPORT_PHONE": "+1 555 9999"}
        env_clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("UNIVERSITY_")}
        env_clean.update(env_overrides)

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_events_support_phone()

        assert result == "+1 555 9999"

    def test_get_mfa_recovery_format_hint_default(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_mfa_recovery_format_hint()

        assert result == settings_mod.DEFAULT_INSTITUTION_SETTINGS["mfa_recovery_code_hint"]

    def test_get_mfa_recovery_format_hint_from_file(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"
        config_file.write_text(
            json.dumps({"mfa_recovery_code_hint": "Custom hint"}),
            encoding="utf-8"
        )

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            env_clean = {k: v for k, v in os.environ.items()
                         if not k.startswith("UNIVERSITY_")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.get_mfa_recovery_format_hint()

        assert result == "Custom hint"


# ---------------------------------------------------------------------------
# Priority order tests
# ---------------------------------------------------------------------------

class TestSettingsPriority:
    """Tests to verify the env > file > defaults priority order."""

    def test_env_overrides_file_which_overrides_default(self, tmp_path):
        config_file = tmp_path / "institution_settings.json"
        config_file.write_text(
            json.dumps({
                "institution_name": "From File",
                "main_phone": "From File Phone",
            }),
            encoding="utf-8"
        )

        env_overrides = {"UNIVERSITY_INSTITUTION_NAME": "From Env"}
        env_clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("UNIVERSITY_")}
        env_clean.update(env_overrides)

        with patch.object(settings_mod, '_get_config_path', return_value=config_file):
            with patch.dict(os.environ, env_clean, clear=True):
                result = settings_mod.load_settings()

        # Env overrides file
        assert result["institution_name"] == "From Env"
        # File overrides default
        assert result["main_phone"] == "From File Phone"
        # Default survives when not overridden by file or env
        assert result["country"] == settings_mod.DEFAULT_INSTITUTION_SETTINGS["country"]


# ---------------------------------------------------------------------------
# __all__ exports
# ---------------------------------------------------------------------------

class TestSettingsAllExports:
    """Tests for __all__ exports."""

    def test_all_exports_are_importable(self):
        for name in settings_mod.__all__:
            assert hasattr(settings_mod, name), f"{name} listed in __all__ but not found"

    def test_key_items_in_all(self):
        expected = [
            "DEFAULT_INSTITUTION_SETTINGS",
            "load_settings", "get_setting", "save_settings", "reset_settings",
            "get_elections_phone", "get_events_support_phone",
            "get_mfa_recovery_format_hint",
        ]
        for name in expected:
            assert name in settings_mod.__all__
