"""Shared idle logout: the setting, the GUI watchdog and the CLI session.

The GUI tests drive the watchdog with a fake root, so no window opens.
"""

from __future__ import annotations

import builtins
import getpass
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from education_system.platform.delivery import idle_settings
from education_system.platform.delivery.cli import cli_helpers
from education_system.platform.delivery.gui import idle_timeout


@pytest.mark.parametrize(("raw", "expected"), [
    (None, 30), ("", 30), ("15", 15), ("0", 0), ("-5", 30), ("soon", 30),
])
def test_setting(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv(idle_settings.ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(idle_settings.ENV_VAR, raw)
    assert idle_settings.idle_timeout_minutes() == expected


class FakeRoot:
    """The parts of ``tk.Tk`` the watchdog uses."""

    def __init__(self):
        self.pending = {}
        self.destroy_handlers = []
        self.alive = True
        self._next = 0

    def bind_all(self, *_a, **_k):
        pass

    def bind(self, sequence, handler, add=None):
        assert sequence == "<Destroy>" and add == "+"
        self.destroy_handlers.append(handler)

    def after(self, _ms, func):
        self._next += 1
        after_id = f"after#{self._next}"
        self.pending[after_id] = func
        return after_id

    def after_cancel(self, after_id):
        self.pending.pop(after_id, None)

    def winfo_exists(self):
        if not self.alive:
            raise tk.TclError("application has been destroyed")
        return 1

    def run_pending(self):
        for after_id, func in list(self.pending.items()):
            del self.pending[after_id]
            func()

    def destroy(self):
        for handler in self.destroy_handlers:
            handler(SimpleNamespace(widget=self))
        self.alive = False


@pytest.fixture
def clock(monkeypatch):
    now = SimpleNamespace(value=1000.0)
    monkeypatch.setattr(idle_timeout, "time", SimpleNamespace(monotonic=lambda: now.value))
    return now


def test_zero_installs_nothing(monkeypatch):
    monkeypatch.setenv(idle_settings.ENV_VAR, "0")
    root = FakeRoot()
    idle_timeout.install_idle_logout(root, lambda: None)()
    assert not root.pending and not root.destroy_handlers


def test_not_idle_yet_keeps_polling(monkeypatch, clock):
    monkeypatch.setenv(idle_settings.ENV_VAR, "30")
    calls = []
    root = FakeRoot()
    idle_timeout.install_idle_logout(root, lambda: calls.append("logout"))
    clock.value += 29 * 60
    root.run_pending()
    assert not calls and len(root.pending) == 1


def test_logout_runs_before_the_modal_notice(monkeypatch, clock):
    """A dialog first would leave an unattended session signed in behind it."""
    monkeypatch.setenv(idle_settings.ENV_VAR, "30")
    calls = []
    root = FakeRoot()
    idle_timeout.install_idle_logout(root, lambda: calls.append("logout"))
    clock.value += 30 * 60
    with patch.object(idle_timeout, "notify_signed_out",
                      side_effect=lambda *a: calls.append("notice")):
        root.run_pending()
    assert calls == ["logout", "notice"]
    assert not root.pending


def test_destroy_cancels_pending_check(monkeypatch):
    monkeypatch.setenv(idle_settings.ENV_VAR, "30")
    root = FakeRoot()
    idle_timeout.install_idle_logout(root, lambda: None)
    assert root.pending
    root.destroy()
    assert not root.pending


def test_destroying_a_child_does_not_cancel(monkeypatch):
    monkeypatch.setenv(idle_settings.ENV_VAR, "30")
    root = FakeRoot()
    idle_timeout.install_idle_logout(root, lambda: None)
    root.destroy_handlers[0](SimpleNamespace(widget=object()))
    assert root.pending


def _timed_out(*_args):
    raise cli_helpers._IdleTimeoutSignal()


def test_cli_session_times_plain_input_then_returns():
    calls = []
    with patch("builtins.input", _timed_out), patch("signal.alarm"):
        with cli_helpers.idle_session(lambda: calls.append("logout"), minutes=5):
            input("Select: ")
            pytest.fail("the prompt should have timed out")
    assert calls == ["logout"]
    assert cli_helpers._idle_state["minutes"] == 0


def test_cli_session_covers_getpass():
    calls = []
    with patch("getpass.getpass", _timed_out), patch("signal.alarm"):
        with cli_helpers.idle_session(lambda: calls.append("logout"), minutes=5):
            getpass.getpass("Password: ")
            pytest.fail("the prompt should have timed out")
    assert calls == ["logout"]


def test_cli_session_restores_prompts_on_a_normal_exit():
    before = builtins.input, getpass.getpass
    with cli_helpers.idle_session(lambda: None, minutes=5):
        assert builtins.input is not before[0]
    assert (builtins.input, getpass.getpass) == before


def test_cli_session_disabled_leaves_prompts_alone():
    before = builtins.input
    with cli_helpers.idle_session(lambda: None, minutes=0):
        assert builtins.input is before


def test_idle_logout_escapes_except_exception():
    assert issubclass(cli_helpers.IdleLogout, SystemExit)
    assert not issubclass(cli_helpers.IdleLogout, Exception)
    assert cli_helpers.IdleLogout().code == 0
