"""FE College CLI idle logout."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from education_system import switch
from education_system.platform.delivery.cli import cli_helpers
from education_system.systems.fe_college import cli_main


def test_idle_timeout_runs_the_logout_path(monkeypatch):
    monkeypatch.setenv("EDU_IDLE_TIMEOUT_MINUTES", "5")
    auth = MagicMock()

    def timed_out(_prompt=""):
        raise cli_helpers._IdleTimeoutSignal()

    def menu(_ctl, _auth):
        input("Select: ")

    with patch("builtins.input", timed_out), patch("signal.alarm"), \
            patch.object(cli_main, "CollegeSession"), \
            patch.object(cli_main, "_main_menu", menu):
        assert cli_main.run_authenticated(auth, {"username": "u"}, "student") == 0
    auth.logout.assert_called_once_with()
    assert switch.consume() == ("__login__", "cli")
