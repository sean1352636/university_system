"""Tests for the SettingsService in the Primary School system."""

import pytest


class TestSetSetting:
    """Tests for setting values."""

    def test_set_setting_returns_dict(self, settings_service):
        """Setting a value returns a dict with key, value, category."""
        result = settings_service.set_setting("school_name", "Oakwood Primary")
        assert isinstance(result, dict)
        assert result["key"] == "school_name"
        assert result["value"] == "Oakwood Primary"

    def test_set_setting_persists(self, settings_service):
        """A stored setting can be retrieved."""
        settings_service.set_setting("term_start", "2026-01-06")
        assert settings_service.get_setting("term_start") == "2026-01-06"

    def test_set_setting_upsert(self, settings_service):
        """Setting the same key twice overwrites the value."""
        settings_service.set_setting("color", "blue")
        settings_service.set_setting("color", "red")
        assert settings_service.get_setting("color") == "red"

    def test_set_setting_with_category(self, settings_service):
        """A setting can be stored with a custom category."""
        settings_service.set_setting("logo_url", "/img/logo.png", category="Branding")
        all_settings = settings_service.get_all_settings(category="Branding")
        assert len(all_settings) == 1
        assert all_settings[0]["category"] == "Branding"


class TestGetSetting:
    """Tests for retrieving individual settings."""

    def test_get_nonexistent_returns_none(self, settings_service):
        """Getting a key that does not exist returns None."""
        assert settings_service.get_setting("nonexistent_key") is None


class TestGetAllSettings:
    """Tests for listing settings."""

    def test_get_all_settings_empty(self, settings_service):
        """An empty database returns an empty list."""
        assert settings_service.get_all_settings() == []

    def test_get_all_settings_returns_all(self, settings_service):
        """All stored settings are returned."""
        settings_service.set_setting("a", "1")
        settings_service.set_setting("b", "2")
        settings_service.set_setting("c", "3")
        all_s = settings_service.get_all_settings()
        assert len(all_s) == 3

    def test_filter_by_category(self, settings_service):
        """Filtering by category returns only matching settings."""
        settings_service.set_setting("x", "1", category="Alpha")
        settings_service.set_setting("y", "2", category="Beta")
        results = settings_service.get_all_settings(category="Alpha")
        assert len(results) == 1
        assert results[0]["key"] == "x"


class TestDeleteSetting:
    """Tests for deleting settings."""

    def test_delete_existing_setting(self, settings_service):
        """Deleting an existing setting returns True and removes it."""
        settings_service.set_setting("temp", "value")
        assert settings_service.delete_setting("temp") is True
        assert settings_service.get_setting("temp") is None

    def test_delete_nonexistent_setting(self, settings_service):
        """Deleting a non-existent key returns False."""
        assert settings_service.delete_setting("nope") is False

    def test_delete_does_not_affect_others(self, settings_service):
        """Deleting one setting leaves other settings intact."""
        settings_service.set_setting("keep", "yes")
        settings_service.set_setting("remove", "no")
        settings_service.delete_setting("remove")
        assert settings_service.get_setting("keep") == "yes"
        assert settings_service.get_setting("remove") is None
