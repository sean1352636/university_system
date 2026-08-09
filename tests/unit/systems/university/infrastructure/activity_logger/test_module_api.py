"""Tests for simple_activity_logger.module_api"""
import json
import os
from unittest.mock import patch, MagicMock

import pytest

from education_system.systems.university.infrastructure.utils.activity_logger import module_api


@pytest.fixture
def patched_logger():
    fake = MagicMock()
    fake.log_activity = MagicMock(return_value=True)
    with patch.object(module_api, "logger", fake):
        yield fake


class TestLogActivityWrappers:
    def test_log_activity_passes_through(self, patched_logger):
        module_api.log_activity("u", "n", "r", "a", "m")
        patched_logger.log_activity.assert_called_once()

    def test_enhanced_log_activity_alias(self, patched_logger):
        module_api.enhanced_log_activity("u", "n", "r", "a", "m")
        patched_logger.log_activity.assert_called_once()

    def test_log_login(self, patched_logger):
        module_api.log_login("u", "n", "r", status="failure", details="bad pw")
        args, _ = patched_logger.log_activity.call_args
        assert args[3] == "login"
        assert args[4] == "authentication"
        assert args[6] == "failure"

    def test_log_logout(self, patched_logger):
        module_api.log_logout("u", "n", "r")
        args, _ = patched_logger.log_activity.call_args
        assert args[3] == "logout"

    def test_log_dynamic_activity_uses_system_user(self, patched_logger):
        module_api.log_dynamic_activity("ping", "module")
        args, _ = patched_logger.log_activity.call_args
        assert args[0] == "system"
        assert args[1] == "system"
        assert args[3] == "ping"


class TestModuleApiAliases:
    @pytest.mark.parametrize("name", [
        "log_create", "log_read", "log_update", "log_delete",
        "log_search", "log_export", "log_admin_action", "log_menu_navigation",
    ])
    def test_alias_invokes_logger(self, patched_logger, name):
        getattr(module_api, name)("u", "n", "r", "a", "m")
        patched_logger.log_activity.assert_called_once()


class TestGetLoggerInstance:
    def test_returns_module_logger(self):
        assert module_api.get_logger_instance() is module_api.logger


class TestPluginRegistration:
    def test_register_and_unregister(self):
        from education_system.systems.university.infrastructure.utils.activity_logger.plugins.base import LoggerPlugin

        class P(LoggerPlugin):
            pass

        plugin = P({})
        before = len(module_api.plugin_manager.plugins)
        module_api.register_plugin(plugin)
        try:
            assert len(module_api.plugin_manager.plugins) == before + 1
            statuses = module_api.get_plugin_status()
            assert any(s["name"] == "P" for s in statuses)
        finally:
            module_api.unregister_plugin("P")
        assert len(module_api.plugin_manager.plugins) == before


class TestCreateDefaultConfig:
    def test_writes_json_file(self, tmp_path):
        out = tmp_path / "cfg.json"
        path = module_api.create_default_config(str(out))
        assert path == str(out)
        with open(out) as f:
            data = json.load(f)
        assert "log_dir" in data
        assert data["min_log_level"] == "INFO"
        assert "security" in data


class TestLoadLoggerConfig:
    def test_reloads_logger(self, tmp_path):
        cfg = {
            "log_dir": str(tmp_path / "logs"),
            "output_formats": ["json"],
            "min_log_level": "DEBUG",
        }
        path = tmp_path / "c.json"
        path.write_text(json.dumps(cfg))
        original = module_api.logger
        try:
            module_api.load_logger_config(str(path))
            assert module_api.logger is not original
        finally:
            module_api.logger.shutdown(timeout=2)
            # Restore original logger so other tests aren't affected
            module_api.logger = original
