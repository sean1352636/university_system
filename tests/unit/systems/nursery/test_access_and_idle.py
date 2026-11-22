"""Role rule for the Nursery menus, and idle logout in its CLI."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from education_system import switch
from education_system.platform.delivery.cli import cli_helpers
from education_system.systems.nursery import cli_main, gui_main
from education_system.systems.nursery.domain import access
from education_system.systems.nursery.menu import NAV_CATEGORIES

ALL_LABELS = {label for _c, items in NAV_CATEGORIES for label in items}
ACCOUNT = {"Change Password", "Multi-Factor Authentication", "Multi-Language"}


def principal(role):
    systems = [{"system_key": "nursery", "role": role}] if role else []
    return access.from_auth(
        SimpleNamespace(current_user={"username": "u", "systems": systems}))


@pytest.fixture(autouse=True)
def _clean_state():
    access.set_current(access.POLICY.anonymous)
    yield
    access.set_current(access.POLICY.anonymous)
    switch.consume()


@pytest.mark.parametrize("role", ["admin", "teacher", "staff"])
def test_admin_and_staff_keep_every_screen(role):
    assert principal(role).filter_menu(NAV_CATEGORIES) == NAV_CATEGORIES


@pytest.mark.parametrize("role", ["student", "parent"])
def test_learners_get_only_their_account(role):
    p = principal(role)
    assert ACCOUNT <= ALL_LABELS
    assert {label for label in ALL_LABELS if p.can_open(label)} == ACCOUNT
    assert p.notice()


@pytest.mark.parametrize("role", ["", "alumni"])
def test_unknown_or_missing_role_opens_nothing(role):
    p = principal(role)
    assert p.filter_menu(NAV_CATEGORIES) == []
    assert p.notice()


def test_gui_opening_path_is_checked():
    gui = object.__new__(gui_main.NurseryMainGUI)
    gui.principal = principal("parent")
    gui._clear_content = MagicMock()
    gui.status_var = MagicMock()
    gui.content_frame = MagicMock()
    gui._dispatch_feature = MagicMock()
    with patch.object(gui_main.ttk, "Label") as label:
        gui._show_stub("Child Directory")
    gui._dispatch_feature.assert_not_called()
    assert "does not have access" in label.call_args.kwargs["text"]


def test_cli_refuses_before_dispatching(capsys):
    access.set_current(principal("student"))
    auth = MagicMock()
    auth.current_user = {"username": "u"}
    with patch.object(cli_main, "_prompt", side_effect=["1", "0"]), \
            patch("education_system.platform.cross_system.journey_cli.dispatch") as dispatch:
        cli_main._submenu("Children", ["Child Directory"], auth=auth)
    dispatch.assert_not_called()
    assert "does not have access" in capsys.readouterr().out


def test_cli_idle_timeout_runs_the_logout_path(monkeypatch):
    monkeypatch.setenv("EDU_IDLE_TIMEOUT_MINUTES", "5")
    auth = MagicMock()
    auth.current_user = {"username": "u", "systems": []}

    def timed_out(_prompt=""):
        raise cli_helpers._IdleTimeoutSignal()

    with patch("builtins.input", timed_out), patch("signal.alarm"):
        assert cli_main.run_authenticated(auth) == 0
    auth.logout.assert_called_once_with()
    assert switch.consume() == ("__login__", "cli")
