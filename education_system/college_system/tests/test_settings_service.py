"""Tests for SettingsService."""

import pytest


class TestSettingsService:
    @pytest.fixture
    def settings_service(self, db_path):
        from education_system.college_system.modules.domain.settings.services.settings_service import SettingsService
        return SettingsService(db_path)

    def test_set_and_get_user_setting(self, settings_service):
        settings_service.set_user_setting(user_id=1, key="theme", value="dark")
        result = settings_service.get_user_setting(user_id=1, key="theme")
        assert result == "dark"

    def test_get_user_setting_default(self, settings_service):
        result = settings_service.get_user_setting(
            user_id=1, key="nonexistent", default="fallback",
        )
        assert result == "fallback"

    def test_get_all_user_settings(self, settings_service):
        settings_service.set_user_setting(user_id=1, key="theme", value="dark")
        settings_service.set_user_setting(user_id=1, key="language", value="en")
        all_settings = settings_service.get_all_user_settings(user_id=1)
        assert isinstance(all_settings, dict)
        assert all_settings.get("theme") == "dark"
        assert all_settings.get("language") == "en"

    def test_set_and_get_system_setting(self, settings_service):
        settings_service.set_system_setting(key="school_name", value="Test College")
        result = settings_service.get_system_setting(key="school_name")
        assert result == "Test College"

    def test_get_system_setting_default(self, settings_service):
        result = settings_service.get_system_setting(
            key="missing_key", default="default_val",
        )
        assert result == "default_val"

    def test_get_all_system_settings(self, settings_service):
        settings_service.set_system_setting(key="term_start", value="2026-09-01")
        all_settings = settings_service.get_all_system_settings()
        assert isinstance(all_settings, dict)

    def test_overwrite_setting(self, settings_service):
        settings_service.set_user_setting(user_id=1, key="theme", value="light")
        settings_service.set_user_setting(user_id=1, key="theme", value="dark")
        result = settings_service.get_user_setting(user_id=1, key="theme")
        assert result == "dark"

    def test_settings_scoped_to_user(self, settings_service):
        settings_service.set_user_setting(user_id=1, key="theme", value="dark")
        settings_service.set_user_setting(user_id=2, key="theme", value="light")
        assert settings_service.get_user_setting(user_id=1, key="theme") == "dark"
        assert settings_service.get_user_setting(user_id=2, key="theme") == "light"
