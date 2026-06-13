"""Tests for simple_activity_logger.module_api."""
import json
from unittest.mock import MagicMock, patch

from education_system.university_system.modules.shared.utils.simple_activity_logger import module_api


class TestCreateDefaultConfig:
    def test_writes_valid_json(self, tmp_path):
        out = tmp_path / "cfg.json"
        module_api.create_default_config(str(out))
        cfg = json.loads(out.read_text())
        assert cfg["log_dir"] == "enhanced_logs"
        assert "security" in cfg
        assert cfg["security"]["max_failed_attempts"] == 5


class TestModuleSurface:
    def test_log_activity_helpers_callable(self):
        for name in (
            "log_activity", "enhanced_log_activity", "log_create", "log_read",
            "log_update", "log_delete", "log_search", "log_export",
            "log_admin_action", "log_menu_navigation", "log_login", "log_logout",
            "log_dynamic_activity",
        ):
            assert callable(getattr(module_api, name))

    def test_get_logger_instance_returns_logger(self):
        assert module_api.get_logger_instance() is module_api.logger


class TestLogHelperDispatch:
    def test_log_activity_forwards_to_logger(self):
        with patch.object(module_api, "logger") as stub:
            module_api.log_activity("u", "alice", "user", "act", "mod", "details")
        stub.log_activity.assert_called_once()

    def test_log_login_passes_login_action(self):
        with patch.object(module_api, "logger") as stub:
            module_api.log_login("u", "alice", "user")
        args = stub.log_activity.call_args.args
        assert args[3] == "login"
        assert args[4] == "authentication"

    def test_log_logout_passes_logout_action(self):
        with patch.object(module_api, "logger") as stub:
            module_api.log_logout("u", "alice", "user")
        args = stub.log_activity.call_args.args
        assert args[3] == "logout"

    def test_log_dynamic_activity_uses_system_identity(self):
        with patch.object(module_api, "logger") as stub:
            module_api.log_dynamic_activity("act", "mod", "details")
        args = stub.log_activity.call_args.args
        assert args[0] == "system"
        assert args[1] == "system"


class TestPluginRegistry:
    def test_register_and_status_round_trip(self):
        # Use a fresh manager via patching to avoid leaking state
        with patch.object(module_api, "plugin_manager") as pm:
            plugin = MagicMock()
            module_api.register_plugin(plugin)
            module_api.unregister_plugin("Foo")
            module_api.get_plugin_status()
        pm.register_plugin.assert_called_once_with(plugin)
        pm.unregister_plugin.assert_called_once_with("Foo")
        pm.get_plugin_status.assert_called_once()
