"""Tests for plugins.base (LoggerPlugin, PluginManager)"""
from unittest.mock import MagicMock

from education_system.university_system.modules.shared.utils.simple_activity_logger.plugins.base import (
    LoggerPlugin, PluginManager,
)


class TestLoggerPlugin:
    def test_default_enabled(self):
        p = LoggerPlugin({})
        assert p.enabled is True

    def test_disabled(self):
        p = LoggerPlugin({"enabled": False})
        assert p.enabled is False

    def test_before_log_passthrough(self, make_log_entry):
        p = LoggerPlugin({})
        e = make_log_entry()
        assert p.before_log(e) is e

    def test_before_log_disabled(self, make_log_entry):
        p = LoggerPlugin({"enabled": False})
        e = make_log_entry()
        assert p.before_log(e) is e

    def test_after_log_returns_none(self, make_log_entry):
        p = LoggerPlugin({})
        assert p.after_log(make_log_entry(), True) is None

    def test_on_shutdown_no_error(self):
        LoggerPlugin({}).on_shutdown()
        LoggerPlugin({"enabled": False}).on_shutdown()

    def test_get_status(self):
        p = LoggerPlugin({"enabled": True, "x": 1})
        s = p.get_status()
        assert s["name"] == "LoggerPlugin"
        assert s["enabled"] is True


class TestPluginManager:
    def test_register_and_unregister(self):
        m = PluginManager()
        p1 = LoggerPlugin({})
        m.register_plugin(p1)
        assert len(m.plugins) == 1
        m.unregister_plugin("LoggerPlugin")
        assert m.plugins == []

    def test_before_log_runs_each_plugin(self, make_log_entry):
        m = PluginManager()
        p1 = LoggerPlugin({})
        p1.before_log = MagicMock(side_effect=lambda e: e)
        m.register_plugin(p1)
        e = make_log_entry()
        out = m.before_log(e)
        assert out is e
        p1.before_log.assert_called_once()

    def test_before_log_handles_exception(self, make_log_entry):
        m = PluginManager()
        p = LoggerPlugin({})
        p.before_log = MagicMock(side_effect=RuntimeError("x"))
        m.register_plugin(p)
        # Should not raise; returns input entry
        e = make_log_entry()
        result = m.before_log(e)
        assert result is e

    def test_after_log_runs_and_swallows_errors(self, make_log_entry):
        m = PluginManager()
        p = LoggerPlugin({})
        p.after_log = MagicMock(side_effect=RuntimeError("x"))
        m.register_plugin(p)
        m.after_log(make_log_entry(), True)  # no raise
        p.after_log.assert_called_once()

    def test_shutdown_plugins_swallows_errors(self):
        m = PluginManager()
        p = LoggerPlugin({})
        p.on_shutdown = MagicMock(side_effect=RuntimeError("x"))
        m.register_plugin(p)
        m.shutdown_plugins()
        p.on_shutdown.assert_called_once()

    def test_get_plugin_status(self):
        m = PluginManager()
        m.register_plugin(LoggerPlugin({"enabled": True}))
        m.register_plugin(LoggerPlugin({"enabled": False}))
        statuses = m.get_plugin_status()
        assert len(statuses) == 2
