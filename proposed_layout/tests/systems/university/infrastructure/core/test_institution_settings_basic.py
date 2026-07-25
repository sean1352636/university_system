"""Tests for university_system.core.institution_settings."""
import json

import pytest

from education_system.systems.university.infrastructure import institution_settings as inst


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect config path to a tmp file and clear cache before each test."""
    def _tmp_path():
        return tmp_path / "institution_settings.json"
    monkeypatch.setattr(inst, "_get_config_path", _tmp_path)
    inst.reset_settings()
    yield
    inst.reset_settings()


class TestLoadSettings:
    def test_returns_defaults_when_no_file(self):
        s = inst.load_settings()
        assert s["institution_name"] == "Teesside University"
        assert s["main_email"] == "info@tees.ac.uk"

    def test_caches_results(self):
        first = inst.load_settings()
        first["main_email"] = "mutated"
        # Cache returns a fresh copy each call, so mutation doesn't leak
        assert inst.load_settings()["main_email"] == "info@tees.ac.uk"

    def test_file_overrides_defaults(self, tmp_path):
        cfg = tmp_path / "institution_settings.json"
        cfg.write_text(json.dumps({"main_email": "custom@x"}))
        assert inst.load_settings()["main_email"] == "custom@x"

    def test_invalid_json_falls_back_to_defaults(self, tmp_path):
        cfg = tmp_path / "institution_settings.json"
        cfg.write_text("not json{")
        s = inst.load_settings()
        assert s["main_email"] == "info@tees.ac.uk"

    def test_env_var_overrides(self, monkeypatch):
        monkeypatch.setenv("UNIVERSITY_INSTITUTION_NAME", "Env Univ")
        assert inst.load_settings()["institution_name"] == "Env Univ"


class TestGetSetting:
    def test_returns_value(self):
        assert inst.get_setting("institution_name") == "Teesside University"

    def test_returns_default_when_missing(self):
        assert inst.get_setting("never_set", "fallback") == "fallback"


class TestSaveSettings:
    def test_persists_and_caches(self, tmp_path):
        assert inst.save_settings({"main_email": "new@x"}) is True
        cfg = tmp_path / "institution_settings.json"
        assert cfg.exists()
        # Cache reflects new value
        assert inst.get_setting("main_email") == "new@x"

    def test_merges_with_existing(self):
        inst.save_settings({"main_email": "a@x"})
        inst.save_settings({"main_phone": "555"})
        s = inst.load_settings()
        assert s["main_email"] == "a@x"
        assert s["main_phone"] == "555"


class TestResetSettings:
    def test_forces_reload(self, tmp_path):
        inst.load_settings()
        # Write a new config and confirm reset triggers reload
        (tmp_path / "institution_settings.json").write_text(
            json.dumps({"main_email": "after_reset@x"})
        )
        inst.reset_settings()
        assert inst.get_setting("main_email") == "after_reset@x"


class TestConvenienceHelpers:
    def test_get_elections_phone(self):
        assert inst.get_elections_phone() == \
            inst.DEFAULT_INSTITUTION_SETTINGS["elections_phone"]

    def test_get_events_support_phone(self):
        assert inst.get_events_support_phone() == \
            inst.DEFAULT_INSTITUTION_SETTINGS["events_support_phone"]

    def test_get_mfa_recovery_format_hint(self):
        assert inst.get_mfa_recovery_format_hint() == \
            inst.DEFAULT_INSTITUTION_SETTINGS["mfa_recovery_code_hint"]
