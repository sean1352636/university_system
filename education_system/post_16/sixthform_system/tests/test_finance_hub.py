"""Tests for the unified Finance hub.

The hub is a thin shell that embeds every finance submodule's notebook
behind a sidebar and renders an aggregated dashboard. These tests pin
the section wiring and exercise a real Tk build of every section + the
dashboard against a throwaway database.
"""

from __future__ import annotations

import os

import pytest


_NO_DISPLAY = not os.environ.get("DISPLAY")

# Every finance data module (plus students, which the others FK to)
# whose DB_PATH must be redirected at a temp file for an isolated build.
_DATA_MODULES = (
    "education_system.post_16.sixthform_system.modules.domain.students.students.students",
    "education_system.post_16.sixthform_system.modules.domain.finance.fees.fees",
    "education_system.post_16.sixthform_system.modules.domain.finance.bursaries.bursaries",
    "education_system.post_16.sixthform_system.modules.domain.finance.trips.trips",
    "education_system.post_16.sixthform_system.modules.domain.finance.receipts.receipts",
    "education_system.post_16.sixthform_system.modules.domain.finance.expense_claims.expense_claims",
    "education_system.post_16.sixthform_system.modules.domain.finance.funding.funding",
    "education_system.post_16.sixthform_system.modules.domain.finance.census_ilr.census_ilr",
)


@pytest.fixture
def finance_db(tmp_path, monkeypatch):
    """Point every finance + students data module at one temp SQLite file."""
    import importlib

    db = str(tmp_path / "sixthform.db")
    students = None
    for dotted in _DATA_MODULES:
        mod = importlib.import_module(dotted)
        monkeypatch.setattr(mod, "DB_PATH", db, raising=False)
        if hasattr(mod, "_DB_READY"):
            monkeypatch.setattr(mod, "_DB_READY", False, raising=False)
        if dotted.endswith("students.students"):
            students = mod
    students.init_db()
    return db


# ── wiring (no display needed) ───────────────────────────────────────

def test_sections_have_builders_for_every_module():
    from education_system.post_16.sixthform_system.modules.domain.finance.finance_hub import (
        finance_hub_views as v,
    )
    ids = [sid for sid, _label, _b in v.FinanceHubGUI.SECTIONS]
    assert ids[0] == "dashboard"
    assert set(ids) == {
        "dashboard", "fees", "bursaries", "trips",
        "receipts", "expenses", "funding", "census",
    }
    # Dashboard has no builder; every other section must have a callable one.
    for sid, _label, builder in v.FinanceHubGUI.SECTIONS:
        if sid == "dashboard":
            assert builder is None
        else:
            assert callable(builder)


def test_money_formatting():
    from education_system.post_16.sixthform_system.modules.domain.finance.finance_hub import (
        finance_hub_views as v,
    )
    assert v._money(1234.5) == "£1,234.50"
    assert v._money(-10) == "-£10.00"
    assert v._money(None) == "£0.00"
    assert v._money("oops") == "—"


# ── full Tk build ────────────────────────────────────────────────────

@pytest.mark.skipif(_NO_DISPLAY, reason="no DISPLAY for Tk")
def test_hub_builds_every_section_and_dashboard(finance_db):
    import tkinter as tk

    from education_system.post_16.sixthform_system.modules.domain.finance.finance_hub import (
        finance_hub_views as v,
    )

    root = tk.Tk()
    root.withdraw()
    try:
        hub = v.FinanceHubGUI(tk.Toplevel(root))
        for sid, _label, _b in hub.SECTIONS:
            hub.show_section(sid)
            assert sid in hub._frames
        # Dashboard rebuild path.
        hub.refresh_dashboard()
        assert hub._current == "dashboard"
        root.update_idletasks()
    finally:
        root.destroy()


@pytest.mark.skipif(_NO_DISPLAY, reason="no DISPLAY for Tk")
def test_dashboard_cards_cover_all_modules(finance_db):
    import tkinter as tk

    from education_system.post_16.sixthform_system.modules.domain.finance.finance_hub import (
        finance_hub_views as v,
    )

    root = tk.Tk()
    root.withdraw()
    try:
        hub = v.FinanceHubGUI(tk.Toplevel(root))
        cards = hub._dashboard_cards()
        sections = {c["section"] for c in cards}
        assert sections == {
            "fees", "bursaries", "trips", "receipts",
            "expenses", "funding", "census",
        }
        # On an empty DB nothing should have errored to "unavailable".
        assert all(c["subtitle"] != "unavailable" for c in cards)
    finally:
        root.destroy()
