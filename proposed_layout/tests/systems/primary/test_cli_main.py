"""Tests for the primary-school CLI entry points.

Covers the ``CATEGORIES`` catalogue, the ``run`` / ``run_authenticated``
guards, and the ``_prompt`` / ``_submenu`` helpers in
``primarysch_system/cli_main.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Module shape ─────────────────────────────────────────────────────

def test_categories_catalogue_shape():
    from education_system.systems.primary.cli_main import CATEGORIES
    assert isinstance(CATEGORIES, list)
    assert CATEGORIES, "expected at least one category"
    labels = [cat for cat, _items in CATEGORIES]
    # No duplicate top-level category labels.
    assert len(labels) == len(set(labels))
    assert "System" in labels
    for _cat, items in CATEGORIES:
        assert items and all(isinstance(i, str) for i in items)
        # No duplicate items inside a single category.
        assert len(items) == len(set(items))


# ── run / run_authenticated ──────────────────────────────────────────

def test_run_raises_without_shared_auth():
    from education_system.systems.primary import cli_main
    with pytest.raises(RuntimeError):
        cli_main.run(shared_auth=None)


def test_run_raises_when_shared_auth_has_no_current_user():
    from education_system.systems.primary import cli_main
    auth = MagicMock()
    auth.current_user = None
    with pytest.raises(RuntimeError):
        cli_main.run(shared_auth=auth)


def test_run_dispatches_to_run_authenticated():
    from education_system.systems.primary import cli_main
    auth = MagicMock()
    auth.current_user = {"username": "tester"}
    with patch.object(cli_main, "run_authenticated", return_value=0) as ra:
        assert cli_main.run(shared_auth=auth) == 0
        ra.assert_called_once_with(auth)


# ── helpers ──────────────────────────────────────────────────────────

def test_prompt_returns_zero_on_eof():
    from education_system.systems.primary import cli_main
    with patch("builtins.input", side_effect=EOFError):
        assert cli_main._prompt("? ") == "0"


def test_prompt_strips_whitespace():
    from education_system.systems.primary import cli_main
    with patch("builtins.input", return_value="  5  "):
        assert cli_main._prompt("? ") == "5"


def test_submenu_back_returns_immediately(capsys):
    from education_system.systems.primary import cli_main
    with patch.object(cli_main, "_prompt", return_value="0"):
        cli_main._submenu("Demo", ["A", "B"])
    out = capsys.readouterr().out
    assert "Demo" in out


def test_submenu_rejects_invalid_then_exits(capsys):
    from education_system.systems.primary import cli_main
    with patch.object(cli_main, "_prompt", side_effect=["99", "0"]):
        cli_main._submenu("Demo", ["A", "B"])
    out = capsys.readouterr().out
    assert "Invalid selection." in out
