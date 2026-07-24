"""Tests for the sixth-form CLI entry points.

These exercise the shim ``sixthform_system/cli_main.py`` which re-exports
from ``modules.shared.cli.cli_main`` — so we cover ``run``,
``run_authenticated``, the ``CATEGORIES`` catalogue, the ``_prompt`` /
``_submenu`` / ``_main_menu`` helpers.
"""

from __future__ import annotations

import io
import sys
import types
from unittest.mock import patch, MagicMock

import pytest


# ── Module shape ─────────────────────────────────────────────────────

def test_shim_reexports_run_and_run_authenticated():
    from education_system.post_16.sixthform_system import cli_main as shim
    from education_system.post_16.sixthform_system.modules.shared.cli import (
        cli_main as inner,
    )
    assert shim.run is inner.run
    assert shim.run_authenticated is inner.run_authenticated


def test_categories_catalogue_shape():
    from education_system.post_16.sixthform_system.modules.shared.cli.cli_main import (
        CATEGORIES,
    )
    assert isinstance(CATEGORIES, list)
    assert len(CATEGORIES) == 10
    labels = {cat for cat, _items in CATEGORIES}
    assert {
        "Student Management", "Academic Management", "Assessment & Grades",
        "UCAS & Careers", "Pastoral & Wellbeing", "Staff & Communication",
        "Finance & Bursaries", "Reports & Analytics", "Cross-System", "System",
    } == labels
    for _cat, items in CATEGORIES:
        assert items and all(isinstance(i, str) for i in items)
    # No duplicate labels inside a single category.
    for _cat, items in CATEGORIES:
        assert len(items) == len(set(items))


# ── run / run_authenticated ──────────────────────────────────────────

def test_run_raises_without_shared_auth():
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    with pytest.raises(RuntimeError):
        cli_main.run(shared_auth=None)


def test_run_raises_when_shared_auth_has_no_current_user():
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    auth = MagicMock()
    auth.current_user = None
    with pytest.raises(RuntimeError):
        cli_main.run(shared_auth=auth)


def test_run_delegates_to_main_menu(monkeypatch):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    auth = MagicMock()
    auth.current_user = {"username": "tester", "role": "staff"}
    called = {}

    def fake_main_menu(a):
        called["auth"] = a

    monkeypatch.setattr(cli_main, "_main_menu", fake_main_menu)
    rc = cli_main.run(role="staff", shared_auth=auth)
    assert rc == 0
    assert called["auth"] is auth


def test_run_authenticated_returns_zero(monkeypatch):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    monkeypatch.setattr(cli_main, "_main_menu", lambda _a: None)
    assert cli_main.run_authenticated(MagicMock()) == 0


# ── _prompt ──────────────────────────────────────────────────────────

def test_prompt_returns_zero_on_eof(monkeypatch):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    from education_system.post_16.sixthform_system.modules.shared.cli import idle_timeout

    def boom(_prompt):
        raise EOFError()

    monkeypatch.setattr(idle_timeout, "timed_input", boom)
    assert cli_main._prompt("> ") == "0"


def test_prompt_returns_zero_on_keyboard_interrupt(monkeypatch):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    from education_system.post_16.sixthform_system.modules.shared.cli import idle_timeout

    def boom(_prompt):
        raise KeyboardInterrupt()

    monkeypatch.setattr(idle_timeout, "timed_input", boom)
    assert cli_main._prompt("> ") == "0"


def test_prompt_strips_whitespace(monkeypatch):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    from education_system.post_16.sixthform_system.modules.shared.cli import idle_timeout

    monkeypatch.setattr(idle_timeout, "timed_input", lambda _p: "  abc  ")
    assert cli_main._prompt("> ") == "abc"


# ── _submenu ─────────────────────────────────────────────────────────

def test_submenu_zero_returns_immediately(monkeypatch, capsys):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    monkeypatch.setattr(cli_main, "_prompt", lambda _m: "0")
    cli_main._submenu("Cat", ["A", "B"])
    out = capsys.readouterr().out
    assert "── Cat ──" in out
    assert "1) A" in out and "2) B" in out


def test_submenu_invalid_then_back(monkeypatch, capsys):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    answers = iter(["bogus", "99", "0"])
    monkeypatch.setattr(cli_main, "_prompt", lambda _m: next(answers))
    cli_main._submenu("Cat", ["A", "B"])
    out = capsys.readouterr().out
    assert "Invalid selection." in out


def test_submenu_dispatches_to_handler_and_back(monkeypatch, capsys):
    """Selecting an unhandled label prints the stub and continues."""
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    # The list of bound dispatchers in ``_submenu`` is large; rather than
    # mock them all, pick a label that none of them claim — anything
    # nonsense will fall through to the stub branch.
    answers = iter(["1", "", "0"])
    monkeypatch.setattr(cli_main, "_prompt", lambda _m: next(answers))
    cli_main._submenu("Cat", ["DefinitelyNotARealFeatureLabel"])
    out = capsys.readouterr().out
    assert "[stub] DefinitelyNotARealFeatureLabel" in out


# ── _main_menu ───────────────────────────────────────────────────────

def test_main_menu_logout_calls_auth_logout(monkeypatch):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    from education_system import switch

    auth = MagicMock()
    auth.current_user = {"username": "u1", "role": "staff"}

    monkeypatch.setattr(cli_main, "_prompt", lambda _m: "l")
    monkeypatch.setattr(
        "education_system.launcher.roles.is_superadmin", lambda _u: False)
    sentinel = {"logout": None}
    monkeypatch.setattr(
        switch, "request_logout",
        lambda iface: sentinel.__setitem__("logout", iface))

    cli_main._main_menu(auth)
    assert sentinel["logout"] == "cli"
    auth.logout.assert_called_once()


def test_main_menu_switch_to_gui(monkeypatch):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    from education_system import switch

    auth = MagicMock()
    auth.current_user = {"username": "u1", "role": "staff"}

    monkeypatch.setattr(cli_main, "_prompt", lambda _m: "g")
    monkeypatch.setattr(
        "education_system.launcher.roles.is_superadmin", lambda _u: False)
    captured = {}
    monkeypatch.setattr(
        switch, "request_switch",
        lambda sys, iface: captured.update(system=sys, iface=iface))

    cli_main._main_menu(auth)
    assert captured == {"system": "sixth_form", "iface": "gui"}


def test_main_menu_idle_timeout_logs_out(monkeypatch):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    from education_system.post_16.sixthform_system.modules.shared.cli import idle_timeout
    from education_system import switch

    auth = MagicMock()
    auth.current_user = {"username": "u1"}

    def boom(_msg):
        raise idle_timeout.SessionTimeoutError()
    monkeypatch.setattr(cli_main, "_prompt", boom)
    monkeypatch.setattr(idle_timeout, "timeout_minutes", lambda: 30)
    monkeypatch.setattr(
        "education_system.launcher.roles.is_superadmin", lambda _u: False)
    monkeypatch.setattr(switch, "request_logout", lambda _i: None)

    cli_main._main_menu(auth)
    auth.logout.assert_called_once()


def test_main_menu_invalid_then_logout(monkeypatch, capsys):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    from education_system import switch

    auth = MagicMock()
    auth.current_user = {"username": "u1"}

    answers = iter(["zz", "99", "l"])
    monkeypatch.setattr(cli_main, "_prompt", lambda _m: next(answers))
    monkeypatch.setattr(
        "education_system.launcher.roles.is_superadmin", lambda _u: False)
    monkeypatch.setattr(switch, "request_logout", lambda _i: None)

    cli_main._main_menu(auth)
    out = capsys.readouterr().out
    assert "Invalid selection." in out


def test_main_menu_superadmin_shows_switch_system(monkeypatch, capsys):
    from education_system.post_16.sixthform_system.modules.shared.cli import cli_main
    from education_system import switch

    auth = MagicMock()
    auth.current_user = {"username": "root", "role": "admin"}

    monkeypatch.setattr(cli_main, "_prompt", lambda _m: "l")
    monkeypatch.setattr(
        "education_system.launcher.roles.is_superadmin", lambda _u: True)
    monkeypatch.setattr(switch, "request_logout", lambda _i: None)

    cli_main._main_menu(auth)
    out = capsys.readouterr().out
    assert "Switch System" in out


def test_main_menu_main_module_guard(monkeypatch):
    """Importing the module directly under ``__main__`` exits with 2."""
    import runpy
    with pytest.raises(SystemExit) as exc:
        runpy.run_module(
            "education_system.post_16.sixthform_system.modules.shared.cli.cli_main",
            run_name="__main__",
        )
    assert exc.value.code == 2
