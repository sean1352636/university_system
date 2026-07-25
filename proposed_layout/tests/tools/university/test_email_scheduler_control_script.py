"""Smoke tests for scripts.email_scheduler_control."""
from unittest.mock import patch

from education_system.systems.university.scripts import email_scheduler_control as script


class TestModuleSurface:
    def test_callables_exist(self):
        for name in ("print_status", "start_command", "stop_command", "run_command", "main"):
            assert callable(getattr(script, name))


class TestStartCommand:
    def test_returns_1_when_already_running(self):
        with patch.object(script, "is_scheduler_running", return_value=True):
            assert script.start_command() == 1

    def test_returns_0_when_started(self):
        with patch.object(script, "is_scheduler_running", return_value=False), \
             patch.object(script, "start_scheduler", return_value=True), \
             patch.object(script, "get_scheduled_jobs", return_value=[]), \
             patch("time.sleep"):
            assert script.start_command() == 0

    def test_returns_1_when_start_fails(self):
        with patch.object(script, "is_scheduler_running", return_value=False), \
             patch.object(script, "start_scheduler", return_value=False), \
             patch("time.sleep"):
            assert script.start_command() == 1


class TestStopCommand:
    def test_returns_1_when_not_running(self):
        with patch.object(script, "is_scheduler_running", return_value=False):
            assert script.stop_command() == 1

    def test_returns_0_when_stopped(self):
        with patch.object(script, "is_scheduler_running", return_value=True), \
             patch.object(script, "stop_scheduler", return_value=True):
            assert script.stop_command() == 0

    def test_returns_1_when_stop_fails(self):
        with patch.object(script, "is_scheduler_running", return_value=True), \
             patch.object(script, "stop_scheduler", return_value=False):
            assert script.stop_command() == 1


class TestMain:
    def test_unknown_command_returns_nonzero(self):
        with patch.object(script.sys, "argv", ["prog", "bogus"]):
            rc = script.main()
        assert rc != 0

    def test_status_dispatches(self):
        with patch.object(script.sys, "argv", ["prog", "status"]), \
             patch.object(script, "print_status") as ps:
            script.main()
        ps.assert_called_once()
