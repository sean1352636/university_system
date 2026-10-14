from education_system.systems.university.domains.finance.interfaces.gui.finance.dashboard import DashboardManager


class _Widget:
    def __init__(self):
        self.calls = []

    def grid_configure(self, **kwargs):
        self.calls.append(kwargs)

    def grid_columnconfigure(self, column, weight):
        self.calls.append({"column": column, "weight": weight})


def test_dashboard_reflow_switches_to_single_column_on_narrow_width():
    dashboard = object.__new__(DashboardManager)
    cards = [(_Widget(), _Widget()) for _ in range(3)]
    buttons = [_Widget(), _Widget()]
    dashboard.dashboard_stat_cards = cards
    dashboard.dashboard_action_buttons = buttons
    dashboard._reflow_dashboard(500)
    assert [card.calls[0]["column"] for card, _ in cards] == [0, 0, 0]
    assert [card.calls[0]["row"] for card, _ in cards] == [0, 1, 2]
    assert all(button.calls[0]["sticky"] == "ew" for button in buttons)
