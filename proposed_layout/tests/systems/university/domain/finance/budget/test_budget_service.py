"""Tests for budget_service.py — student budget/expense/income/savings tracking.

All managers use ``get_connection()`` / ``transaction()`` with the default DB
path, which the autouse ``_isolate_db`` fixture points at a throw-away copy of
the template DB. The ``_tables`` fixture (re)creates the budget tables in that
isolated DB before each test.
"""

import pytest

from education_system.systems.university.domain.finance.budget.services.budget_service import (
    BudgetManager,
    ExpenseManager,
    IncomeManager,
    SavingsGoalManager,
)


@pytest.fixture(autouse=True)
def _tables():
    """Ensure budget tables exist in the isolated DB for every test."""
    BudgetManager.create_tables()
    yield


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

class TestBudgetManager:
    def test_create_budget_returns_id(self):
        bid = BudgetManager.create_budget(
            "STU001", "Spring Budget", "semester",
            "2025-01-01", "2025-05-31", 5000.0,
        )
        assert isinstance(bid, int) and bid > 0

    def test_create_budget_with_categories(self):
        cats = [
            {"name": "Food", "type": "essential", "amount": 1000},
            {"name": "Fun", "type": "discretionary", "amount": 500},
        ]
        bid = BudgetManager.create_budget(
            "STU002", "Monthly", "monthly",
            "2025-01-01", "2025-01-31", 2000.0, categories=cats,
        )
        summary = BudgetManager.get_budget_summary(bid)
        assert summary["allocated_amount"] == 1500
        assert len(summary["categories"]) == 2

    def test_get_student_budgets(self):
        BudgetManager.create_budget("STU003", "A", "monthly", "2025-01-01", "2025-01-31", 1000.0)
        BudgetManager.create_budget("STU003", "B", "monthly", "2025-02-01", "2025-02-28", 1200.0)
        budgets = BudgetManager.get_student_budgets("STU003")
        assert len(budgets) == 2
        assert all(b["student_id"] == "STU003" for b in budgets)

    def test_get_student_budgets_empty(self):
        assert BudgetManager.get_student_budgets("NOBODY") == []

    def test_budget_summary_statistics(self):
        bid = BudgetManager.create_budget(
            "STU004", "S", "semester", "2025-01-01", "2025-12-31", 1000.0,
        )
        summary = BudgetManager.get_budget_summary(bid)
        assert summary["remaining_budget"] == 1000.0
        assert summary["budget_utilization_pct"] == 0
        assert "recommended_daily_spending" in summary


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

class TestExpenseManager:
    def test_add_expense_returns_id(self):
        eid = ExpenseManager.add_expense(
            "STU010", 25.50, "2025-03-01", description="Lunch",
            merchant_name="Cafe", payment_method="debit",
        )
        assert isinstance(eid, int) and eid > 0

    def test_add_expense_updates_budget_spent(self):
        bid = BudgetManager.create_budget(
            "STU011", "B", "monthly", "2025-01-01", "2025-01-31", 500.0,
        )
        ExpenseManager.add_expense("STU011", 100.0, "2025-01-05", budget_id=bid)
        summary = BudgetManager.get_budget_summary(bid)
        assert summary["spent_amount"] == 100.0
        assert summary["remaining_budget"] == 400.0

    def test_get_student_expenses(self):
        ExpenseManager.add_expense("STU012", 10.0, "2025-03-01")
        ExpenseManager.add_expense("STU012", 20.0, "2025-03-02")
        expenses = ExpenseManager.get_student_expenses("STU012")
        assert len(expenses) == 2

    def test_get_student_expenses_date_filter(self):
        ExpenseManager.add_expense("STU013", 10.0, "2025-03-01")
        ExpenseManager.add_expense("STU013", 20.0, "2025-04-01")
        march = ExpenseManager.get_student_expenses(
            "STU013", start_date="2025-03-01", end_date="2025-03-31",
        )
        assert len(march) == 1
        assert march[0]["amount"] == 10.0

    def test_spending_by_category(self):
        ExpenseManager.add_expense("STU014", 30.0, "2025-03-01", merchant_name="Store A")
        ExpenseManager.add_expense("STU014", 20.0, "2025-03-02", merchant_name="Store A")
        breakdown = ExpenseManager.get_spending_by_category("STU014", "2025-03-01", "2025-03-31")
        assert len(breakdown) >= 1
        total = sum(row["total_amount"] for row in breakdown)
        assert total == 50.0

    def test_delete_expense(self):
        eid = ExpenseManager.add_expense("STU015", 40.0, "2025-03-01")
        assert ExpenseManager.delete_expense(eid) is True
        assert ExpenseManager.get_student_expenses("STU015") == []

    def test_delete_missing_expense(self):
        assert ExpenseManager.delete_expense(999999) is False

    def test_update_expense(self):
        eid = ExpenseManager.add_expense("STU016", 40.0, "2025-03-01", description="old")
        assert ExpenseManager.update_expense(eid, description="new", amount=55.0) is True
        rows = ExpenseManager.get_student_expenses("STU016")
        assert rows[0]["description"] == "new"
        assert rows[0]["amount"] == 55.0

    def test_update_expense_no_valid_fields(self):
        eid = ExpenseManager.add_expense("STU017", 40.0, "2025-03-01")
        assert ExpenseManager.update_expense(eid, not_a_field="x") is False


# ---------------------------------------------------------------------------
# Income
# ---------------------------------------------------------------------------

class TestIncomeManager:
    def test_add_income_returns_id(self):
        iid = IncomeManager.add_income(
            "STU020", 1500.0, "2025-03-01", "Work Study", "work-study",
        )
        assert isinstance(iid, int) and iid > 0

    def test_add_income_updates_budget_total(self):
        bid = BudgetManager.create_budget(
            "STU021", "B", "monthly", "2025-01-01", "2025-01-31", 500.0,
        )
        IncomeManager.add_income("STU021", 300.0, "2025-01-02", "Job", "job", budget_id=bid)
        summary = BudgetManager.get_budget_summary(bid)
        assert summary["total_income"] == 300.0

    def test_get_student_income(self):
        IncomeManager.add_income("STU022", 100.0, "2025-03-01", "A", "grant")
        IncomeManager.add_income("STU022", 200.0, "2025-03-02", "B", "scholarship")
        income = IncomeManager.get_student_income("STU022")
        assert len(income) == 2


# ---------------------------------------------------------------------------
# Savings goals
# ---------------------------------------------------------------------------

class TestSavingsGoalManager:
    def test_create_goal(self):
        gid = SavingsGoalManager.create_goal("STU030", "Laptop", 1200.0, priority="high")
        assert isinstance(gid, int) and gid > 0

    def test_update_goal_progress(self):
        gid = SavingsGoalManager.create_goal("STU031", "Trip", 500.0)
        assert SavingsGoalManager.update_goal_progress(gid, 200.0) is True
        goals = SavingsGoalManager.get_student_goals("STU031")
        assert goals[0]["current_amount"] == 200.0
        assert goals[0]["progress_pct"] == 40.0

    def test_goal_completes_when_target_reached(self):
        gid = SavingsGoalManager.create_goal("STU032", "Fund", 100.0)
        SavingsGoalManager.update_goal_progress(gid, 100.0)
        # completed goals drop out of active-only listing
        assert SavingsGoalManager.get_student_goals("STU032", active_only=True) == []
        allgoals = SavingsGoalManager.get_student_goals("STU032", active_only=False)
        assert allgoals[0]["status"] == "completed"

    def test_update_progress_missing_goal(self):
        assert SavingsGoalManager.update_goal_progress(999999, 50.0) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
