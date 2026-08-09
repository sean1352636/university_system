"""Tests for university_system.core.logs."""
import sqlite3
import smtplib
from unittest.mock import patch

from education_system.systems.university.infrastructure import logs


class TestGetLogFile:
    def test_returns_string_path(self):
        path = logs.get_log_file("test.log")
        assert isinstance(path, str)
        assert path.endswith("test.log")


class TestLogEventLevels:
    def test_info_dispatches_to_logger(self):
        with patch.object(logs.logger, "info") as info:
            logs.log_event("info", "hello")
        info.assert_called_once_with("hello")

    def test_warning_dispatches(self):
        with patch.object(logs.logger, "warning") as warn:
            logs.log_event("warning", "watch")
        warn.assert_called_once_with("watch")

    def test_error_dispatches(self):
        with patch.object(logs.logger, "error") as err:
            logs.log_event("error", "bad")
        err.assert_called_once_with("bad")

    def test_critical_dispatches(self):
        with patch.object(logs.logger, "critical") as crit:
            logs.log_event("critical", "fatal")
        crit.assert_called_once_with("fatal")

    def test_debug_dispatches(self):
        with patch.object(logs.logger, "debug") as dbg:
            logs.log_event("debug", "trace")
        dbg.assert_called_once_with("trace")

    def test_unknown_level_falls_back_to_info(self):
        with patch.object(logs.logger, "info") as info:
            logs.log_event("mystery", "msg")
        info.assert_called_once_with("msg")


class TestHandleException:
    def test_returns_function_result(self):
        @logs.handle_exception
        def f(x):
            return x + 1
        assert f(5) == 6

    def test_catches_sqlite_error(self):
        @logs.handle_exception
        def f():
            raise sqlite3.Error("db err")
        assert f() is False

    def test_catches_smtp_error(self):
        @logs.handle_exception
        def f():
            raise smtplib.SMTPException("smtp err")
        assert f() is False

    def test_catches_generic_exception(self):
        @logs.handle_exception
        def f():
            raise RuntimeError("generic")
        assert f() is False


class TestModuleSurface:
    def test_logger_configured(self):
        assert logs.logger is not None
        assert logs.logger.name == "education_system.systems.university.infrastructure.logs"

    def test_callables_exposed(self):
        for name in ("configure_logging", "log_event", "handle_exception",
                     "get_log_file"):
            assert callable(getattr(logs, name))
