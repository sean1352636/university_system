"""Tests for the canonical University Finance CLI hub."""

from unittest.mock import Mock

from education_system.systems.university.domains.finance.interfaces.cli import menu


def test_menu_lists_all_finance_areas(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt="": "0")

    menu.display_finance_menu(Mock())

    output = capsys.readouterr().out
    assert "Core Finance Operations (29 options)" in output
    assert "General Ledger" in output
    assert "Bank Reconciliation" in output
    assert "Student Statements" in output
    assert "Budget Management" in output
    assert "Bursary Management" in output
    assert "Scholarship Finder" in output
    assert "Blockchain Credentials" in output


def test_menu_dispatches_selected_area_with_auth(monkeypatch):
    auth = Mock()
    action = Mock()
    choices = iter(["3", "0"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(choices))
    monkeypatch.setattr(
        menu,
        "FINANCE_AREAS",
        (("3", "Bank Reconciliation", action),),
    )

    menu.display_finance_menu(auth)

    action.assert_called_once_with(auth)


def test_failed_area_returns_to_hub(monkeypatch, capsys):
    action = Mock(side_effect=RuntimeError("optional dependency unavailable"))
    choices = iter(["1", "0"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(choices))
    monkeypatch.setattr(
        menu,
        "FINANCE_AREAS",
        (("1", "Core Finance", action),),
    )

    menu.display_finance_menu(Mock())

    assert "Unable to open this finance area" in capsys.readouterr().out
