"""Display-free tests for the Secondary School GUI's view-model logic.

`_safe_count` is the dashboard's KPI display formatter — a module-level pure
function that never touches a Tk widget, so it runs without a display.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def g():
    from education_system.systems.secondary import gui_main
    return gui_main


def test_safe_count_formats_value(g):
    assert g._safe_count(lambda: 17) == "17"


def test_safe_count_zero(g):
    assert g._safe_count(lambda: 0) == "0"


def test_safe_count_swallows_errors_to_dash(g):
    def boom():
        raise RuntimeError("db down")
    assert g._safe_count(boom) == "—"


def test_count_helpers_are_wrapped_gracefully(g):
    # The three KPI sources are composed through _safe_count on the dashboard;
    # even if the underlying domain call fails, the tile shows the em-dash.
    for fn in (g._count_pupils, g._count_staff, g._count_form_groups):
        out = g._safe_count(fn)
        assert isinstance(out, str)  # a number string, or "—" — never raises
