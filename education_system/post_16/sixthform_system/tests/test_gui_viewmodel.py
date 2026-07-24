"""Display-free tests for the sixth-form GUI's view-model logic.

The dashboard's KPI/attendance computations (``_gather_kpis``, ``_safe_count``,
``_today_attendance_pct``) are pure — they read domain data and format display
strings without touching any Tk widget. We exercise them on a *bare* instance
created via ``__new__`` (which skips ``__init__``, so no window is constructed
and no display is required). This runs in the default suite, unlike the
``@pytest.mark.gui`` tests that build a real Tk window.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


_ATT = (
    "education_system.post_16.sixthform_system.modules.domain."
    "academics.attendance.attendance.list_records"
)


@pytest.fixture
def vm():
    """A bare SixthFormMainGUI — no __init__, no Tk window, no display."""
    from education_system.post_16.sixthform_system.modules.shared.gui.gui_main import (
        SixthFormMainGUI,
    )
    return SixthFormMainGUI.__new__(SixthFormMainGUI)


# ── _today_attendance_pct ────────────────────────────────────────────────

class TestAttendancePct:
    def test_no_rows(self, vm):
        with patch(_ATT, return_value=[]):
            pct, hint = vm._today_attendance_pct("2026-05-18")
        assert pct == "—"
        assert "No marks" in hint

    def test_with_rows(self, vm):
        rows = [
            SimpleNamespace(status="Present"),
            SimpleNamespace(status="Late"),
            SimpleNamespace(status="Absent"),
            SimpleNamespace(status="Absent"),
        ]
        with patch(_ATT, return_value=rows):
            pct, hint = vm._today_attendance_pct("2026-05-18")
        assert pct == "50%"          # 2 present-like of 4
        assert "2/4" in hint

    def test_all_present(self, vm):
        rows = [SimpleNamespace(status="Present")] * 3
        with patch(_ATT, return_value=rows):
            pct, _hint = vm._today_attendance_pct("2026-05-18")
        assert pct == "100%"

    def test_error_is_swallowed(self, vm):
        with patch(_ATT, side_effect=RuntimeError("boom")):
            pct, hint = vm._today_attendance_pct("2026-05-18")
        assert pct == "—"
        assert "not available" in hint.lower()


# ── _safe_count ──────────────────────────────────────────────────────────

class TestSafeCount:
    def test_returns_row_count(self, vm):
        with patch("importlib.import_module") as imp:
            imp.return_value = MagicMock(list_things=MagicMock(return_value=[1, 2, 3]))
            assert vm._safe_count("any.module", "list_things") == 3

    def test_none_rows_is_zero(self, vm):
        with patch("importlib.import_module") as imp:
            imp.return_value = MagicMock(list_things=MagicMock(return_value=None))
            assert vm._safe_count("any.module", "list_things") == 0

    def test_missing_function_is_none(self, vm):
        # A real module that lacks the requested attribute.
        assert vm._safe_count("logging", "definitely_not_a_function") is None

    def test_missing_module_is_none(self, vm):
        assert vm._safe_count("no.such.module.anywhere", "list_x") is None


# ── _gather_kpis (assembles the 4 dashboard tiles) ───────────────────────

class TestGatherKpis:
    def test_four_tiles_with_values(self, vm):
        with patch.object(vm, "_safe_count", return_value=7), \
             patch.object(vm, "_today_attendance_pct", return_value=("80%", "x/y")):
            tiles = vm._gather_kpis()
        assert len(tiles) == 4
        titles = [t[0] for t in tiles]
        assert titles == ["Students", "Staff", "Courses", "Today's Attendance"]
        # counts render as the stringified number; attendance passes through
        assert tiles[0][1] == "7"
        assert tiles[3][1] == "80%"

    def test_missing_counts_render_as_dash(self, vm):
        with patch.object(vm, "_safe_count", return_value=None), \
             patch.object(vm, "_today_attendance_pct", return_value=("—", "n/a")):
            tiles = vm._gather_kpis()
        assert tiles[0][1] == "—"
        assert tiles[1][1] == "—"
        assert tiles[2][1] == "—"
