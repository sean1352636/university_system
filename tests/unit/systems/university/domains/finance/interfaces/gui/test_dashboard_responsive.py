"""Behavioral tests for finance dashboard responsive layout."""

from unittest.mock import Mock

import pytest

from education_system.systems.university.domains.finance.interfaces.gui.finance.dashboard import (
    DashboardManager,
)
from education_system.systems.university.domains.finance.interfaces.gui.finance_management_gui import (
    responsive_window_size,
)

pytestmark = pytest.mark.gui


class GridWidget:
    def __init__(self):
        self.grid = {}

    def grid_configure(self, **options):
        self.grid.update(options)


class GridParent:
    def __init__(self):
        self.weights = {}

    def grid_columnconfigure(self, column, weight):
        self.weights[column] = weight


@pytest.mark.parametrize(
    ("width", "columns"),
    [(480, 1), (700, 2), (900, 2), (1100, 4), (1600, 4)],
)
def test_dashboard_reflows_at_narrow_tablet_and_desktop_widths(width, columns):
    manager = object.__new__(DashboardManager)
    parent = GridParent()
    cards = [GridWidget() for _ in range(4)]
    actions = [GridWidget() for _ in range(4)]
    manager.dashboard_stat_cards = [(card, parent) for card in cards]
    manager.dashboard_action_buttons = actions

    manager._reflow_dashboard(width)

    assert [(card.grid["row"], card.grid["column"]) for card in cards] == [
        (index // columns, index % columns) for index in range(4)
    ]
    assert all(action.grid["sticky"] == "ew" for action in actions)
    assert sum(parent.weights.values()) == columns


def test_reflow_is_safe_while_dashboard_widgets_are_not_created():
    manager = object.__new__(DashboardManager)
    manager._reflow_dashboard(640)


@pytest.mark.parametrize(
    ("screen", "expected"),
    [
        ((1920, 1080), (1400, 900, 700, 560)),
        ((1024, 768), (944, 668, 700, 560)),
        ((600, 480), (520, 380, 520, 380)),
        ((320, 320), (320, 320, 320, 320)),
    ],
)
def test_finance_window_size_stays_inside_available_screen(screen, expected):
    assert responsive_window_size(*screen) == expected


def test_long_translated_labels_do_not_change_breakpoint_calculation():
    manager = object.__new__(DashboardManager)
    parent = GridParent()
    cards = [GridWidget() for _label in ["A" * 200, "売上高" * 80]]
    manager.dashboard_stat_cards = [(card, parent) for card in cards]
    manager.dashboard_action_buttons = []

    manager._reflow_dashboard(720)

    assert [card.grid["column"] for card in cards] == [0, 1]
