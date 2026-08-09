"""Behavioral tests for finance operations tabs introduced in features 6–10."""

from unittest.mock import Mock, patch

import pytest

from education_system.systems.university.domains.finance.interfaces.gui.finance.layout._operations import (
    FinanceOperationsMixin,
)
from education_system.systems.university.domains.finance.interfaces.gui.finance.layout._navigation import (
    NavigationMixin,
)

pytestmark = pytest.mark.gui

MODULE = "education_system.systems.university.domains.finance.interfaces.gui.finance.layout._operations"
NAV_MODULE = "education_system.systems.university.domains.finance.interfaces.gui.finance.layout._navigation"
OPERATIONS_TABS = {
    "fixed_assets",
    "approval_inbox",
    "fraud_investigations",
    "close_checklist",
}


class OperationsHarness(FinanceOperationsMixin):
    def __init__(self):
        self.root = Mock()
        self.gui = Mock(user_info={"username": "finance.manager"}, role="staff")
        self.service = Mock()
        self.frame = Mock()
        self.tree = Mock()
        self.refresh = Mock()
        self.add_action = None

    def _ops(self):
        return self.service

    def _ops_tab(self, key, title, table, columns, add_action):
        self.created_tab = (key, title, table, columns)
        self.add_action = add_action
        return self.frame, self.tree, self.refresh


@pytest.fixture
def harness():
    return OperationsHarness()


def test_fixed_asset_dialog_cancel_does_not_create_asset(harness):
    with patch(f"{MODULE}.simpledialog.askstring", return_value=None):
        harness.create_fixed_assets_tab()
        harness.add_action(harness.refresh)

    harness.service.add_asset.assert_not_called()
    harness.refresh.assert_not_called()


def test_fixed_asset_valid_dialog_refreshes_register(harness):
    with (
        patch(f"{MODULE}.simpledialog.askstring", side_effect=["LAB-1", "Microscope"]),
        patch(f"{MODULE}.simpledialog.askfloat", return_value=1200.0),
        patch(f"{MODULE}.simpledialog.askinteger", return_value=5),
    ):
        harness.create_fixed_assets_tab()
        harness.add_action(harness.refresh)

    harness.service.add_asset.assert_called_once_with("LAB-1", "Microscope", 1200.0, 5)
    harness.refresh.assert_called_once_with()


def test_approval_request_uses_authenticated_identity(harness):
    with (
        patch(f"{MODULE}.ttk.Button", return_value=Mock()),
        patch(f"{MODULE}.simpledialog.askstring", return_value="invoice"),
        patch(f"{MODULE}.simpledialog.askinteger", return_value=42),
        patch(f"{MODULE}.simpledialog.askfloat", return_value=2500.0),
    ):
        harness.create_approval_inbox_tab()
        harness.add_action(harness.refresh)

    harness.service.request_approval.assert_called_once_with(
        "invoice", 42, 2500.0, "finance.manager"
    )


def test_empty_selection_does_not_submit_approval_decision(harness):
    harness.tree.selection.return_value = ()
    harness._approval_decide(harness.tree, harness.refresh, "approved")
    harness.service.decide_approval.assert_not_called()


def test_selected_fraud_case_records_user_and_refreshes(harness):
    harness.tree.selection.return_value = ("row",)
    harness.tree.item.return_value = (17,)

    harness._fraud_decide(harness.tree, harness.refresh, "confirmed")

    harness.service.decide_fraud_case.assert_called_once_with(17, "confirmed", "finance.manager")
    harness.refresh.assert_called_once_with()


def test_invalid_fraud_score_shows_friendly_error(harness):
    harness.service.create_fraud_case.side_effect = ValueError("Risk score must be between 0 and 1")
    with (
        patch(f"{MODULE}.ttk.Button", return_value=Mock()),
        patch(f"{MODULE}.simpledialog.askinteger", return_value=91),
        patch(f"{MODULE}.simpledialog.askfloat", return_value=1.2),
        patch(f"{MODULE}.simpledialog.askstring", return_value="Unusual pattern"),
        patch(f"{MODULE}.messagebox.showerror") as showerror,
    ):
        harness.create_fraud_investigations_tab()
        harness._run_ops_action(harness.add_action, harness.refresh)

    showerror.assert_called_once()
    harness.refresh.assert_not_called()


def test_close_task_error_does_not_refresh(harness):
    harness.tree.selection.return_value = ("row",)
    harness.tree.item.return_value = (8,)
    harness.service.complete_close_task.side_effect = ValueError("Evidence is required")
    with (
        patch(f"{MODULE}.simpledialog.askstring", return_value="reference"),
        patch(f"{MODULE}.messagebox.showerror") as showerror,
    ):
        harness._close_complete(harness.tree, harness.refresh)

    showerror.assert_called_once()
    harness.refresh.assert_not_called()


@pytest.mark.parametrize(
    ("method", "key"),
    [
        ("create_fixed_assets_tab", "fixed_assets"),
        ("create_approval_inbox_tab", "approval_inbox"),
        ("create_fraud_investigations_tab", "fraud_investigations"),
        ("create_close_checklist_tab", "close_checklist"),
    ],
)
def test_each_finance_workspace_registers_its_tab(harness, method, key):
    with patch(f"{MODULE}.ttk.Button", return_value=Mock()):
        getattr(harness, method)()
    assert harness.created_tab[0] == key


class NavigationButton:
    created = []

    def __init__(self, _parent, command=None, **_options):
        self.command = command
        self.created.append(self)

    def pack(self, **_options):
        pass


def visible_navigation_tabs(*, admin=False, staff=False, student=False):
    navigation = object.__new__(NavigationMixin)
    navigation.gui = Mock()
    navigation.gui.is_admin.return_value = admin
    navigation.gui.is_staff.return_value = staff
    navigation.gui.is_student.return_value = student
    navigation.nav_frame = Mock()
    navigation.nav_canvas = Mock()
    navigation.colors = {"secondary": "#336699", "dark": "#111111"}
    navigation.show_tab = Mock()
    NavigationButton.created = []

    with (
        patch(f"{NAV_MODULE}.tk.Button", NavigationButton),
        patch(f"{NAV_MODULE}.tk.Frame", return_value=Mock()),
    ):
        navigation.setup_navigation()

    for button in NavigationButton.created:
        button.command()
    return {call.args[0] for call in navigation.show_tab.call_args_list}


def test_operations_workspaces_are_hidden_from_students():
    assert OPERATIONS_TABS.isdisjoint(visible_navigation_tabs(student=True))


@pytest.mark.parametrize("role", ["admin", "staff"])
def test_operations_workspaces_are_available_to_finance_roles(role):
    assert OPERATIONS_TABS <= visible_navigation_tabs(**{role: True})
