"""Display-free tests for the Primary School GUI's view-model logic.

The dashboard KPI helpers (`_safe_count`, `_count_pupils`, `_count_staff`,
`_count_classes`) are module-level pure functions — no Tk widget is touched, so
they run without a display (importing the module never constructs a window).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def g():
    from education_system.primarysch_system import gui_main
    return gui_main


# ── _safe_count: the display formatter ──────────────────────────────────

def test_safe_count_formats_value(g):
    assert g._safe_count(lambda: 42) == "42"


def test_safe_count_zero(g):
    assert g._safe_count(lambda: 0) == "0"


def test_safe_count_swallows_errors_to_dash(g):
    def boom():
        raise RuntimeError("db down")
    assert g._safe_count(boom) == "—"


# ── _count_* wrap the domain list functions ─────────────────────────────

def test_count_pupils_counts_rows(g):
    with patch(
        "education_system.primarysch_system.modules.domain.pupils.pupils.list_pupils",
        return_value=[1, 2, 3],
    ):
        assert g._count_pupils() == 3


def test_count_staff_counts_rows(g):
    with patch(
        "education_system.primarysch_system.modules.domain.staff.staff.list_staff",
        return_value=[1, 2],
    ):
        assert g._count_staff() == 2


def test_safe_count_over_count_pupils(g):
    """The dashboard composes _safe_count(_count_pupils); a domain failure
    degrades to the em-dash rather than crashing the KPI row."""
    with patch(
        "education_system.primarysch_system.modules.domain.pupils.pupils.list_pupils",
        side_effect=RuntimeError("boom"),
    ):
        assert g._safe_count(g._count_pupils) == "—"
