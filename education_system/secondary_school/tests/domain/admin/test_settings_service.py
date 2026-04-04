"""Tests for SettingsService."""
import pytest


class TestSettings:
    def test_set_and_get(self, settings_service):
        settings_service.seed_defaults()
        settings_service.set("school_name", "Test Academy")
        value = settings_service.get("school_name")
        assert value == "Test Academy"

    def test_get_returns_default_when_missing(self, settings_service):
        value = settings_service.get("nonexistent_key", default="fallback")
        assert value == "fallback"

    def test_list_settings(self, settings_service):
        settings_service.seed_defaults()
        settings = settings_service.list_settings()
        assert len(settings) >= 1
        assert any(s["key"] == "school_name" for s in settings)
