"""Tests for simple_activity_logger.plugins.base."""
from unittest.mock import MagicMock

from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger.plugins.base import (
    LoggerPlugin,
    PluginManager,
)


def _stub_entry():
    return MagicMock()


class TestLoggerPlugin:
    def test_defaults_enabled_true(self):
        p = LoggerPlugin({})
        assert p.enabled is True

    def test_enabled_false_when_configured(self):
        p = LoggerPlugin({"enabled": False})
        assert p.enabled is False

    def test_before_log_returns_entry_unchanged(self):
        p = LoggerPlugin({})
        e = _stub_entry()
        assert p.before_log(e) is e

    def test_get_status_shape(self):
        p = LoggerPlugin({"key": "val", "enabled": True})
        s = p.get_status()
        assert s["name"] == "LoggerPlugin"
        assert s["enabled"] is True
        assert s["config"] == {"key": "val", "enabled": True}


class TestPluginManager:
    def test_register_and_status(self, capsys):
        m = PluginManager()
        p = LoggerPlugin({})
        m.register_plugin(p)
        assert p in m.plugins
        status = m.get_plugin_status()
        assert len(status) == 1

    def test_unregister_by_class_name(self):
        m = PluginManager()
        m.register_plugin(LoggerPlugin({}))
        m.unregister_plugin("LoggerPlugin")
        assert m.plugins == []

    def test_before_log_applies_all_plugins(self):
        m = PluginManager()
        p1, p2 = MagicMock(), MagicMock()
        p1.before_log.side_effect = lambda e: e
        p2.before_log.side_effect = lambda e: e
        m.plugins = [p1, p2]
        e = _stub_entry()
        m.before_log(e)
        p1.before_log.assert_called_once_with(e)
        p2.before_log.assert_called_once_with(e)

    def test_before_log_swallows_plugin_errors(self):
        m = PluginManager()
        bad = MagicMock()
        bad.before_log.side_effect = RuntimeError("boom")
        good = MagicMock()
        good.before_log.side_effect = lambda e: e
        m.plugins = [bad, good]
        # Should not raise, and good plugin still runs
        result = m.before_log(_stub_entry())
        assert result is not None
        good.before_log.assert_called_once()

    def test_after_log_swallows_errors(self):
        m = PluginManager()
        bad = MagicMock()
        bad.after_log.side_effect = RuntimeError("boom")
        m.plugins = [bad]
        m.after_log(_stub_entry(), True)  # must not raise

    def test_shutdown_plugins_calls_on_shutdown(self):
        m = PluginManager()
        p = MagicMock()
        m.plugins = [p]
        m.shutdown_plugins()
        p.on_shutdown.assert_called_once()

    def test_shutdown_swallows_errors(self):
        m = PluginManager()
        bad = MagicMock()
        bad.on_shutdown.side_effect = RuntimeError("boom")
        m.plugins = [bad]
        m.shutdown_plugins()
