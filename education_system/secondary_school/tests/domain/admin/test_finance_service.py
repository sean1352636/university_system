"""Tests for FinanceService."""
import pytest


class TestFinance:
    def test_add_income_transaction(self, finance_service):
        txn = finance_service.add_transaction(
            transaction_type="income", category="tuition_fees",
            amount=500.00, description="Term 1 fees",
        )
        assert txn["transaction_type"] == "income"
        assert txn["amount"] == 500.00

    def test_add_expense_transaction(self, finance_service):
        txn = finance_service.add_transaction(
            transaction_type="expense", category="supplies",
            amount=120.50, description="Stationery order",
        )
        assert txn["transaction_type"] == "expense"
        assert txn["amount"] == 120.50

    def test_list_transactions(self, finance_service):
        finance_service.add_transaction("income", "donations", 100.0)
        finance_service.add_transaction("expense", "supplies", 50.0)
        txns = finance_service.list_transactions()
        assert len(txns) >= 2

    def test_list_transactions_filters_by_type(self, finance_service):
        finance_service.add_transaction("income", "donations", 100.0)
        finance_service.add_transaction("expense", "supplies", 50.0)
        txns = finance_service.list_transactions(transaction_type="income")
        assert all(t["transaction_type"] == "income" for t in txns)

    def test_delete_transaction(self, finance_service):
        txn = finance_service.add_transaction("income", "donations", 200.0)
        finance_service.delete_transaction(txn["id"])
        txns = finance_service.list_transactions()
        assert all(t["id"] != txn["id"] for t in txns)

    def test_get_summary(self, finance_service):
        finance_service.add_transaction("income", "donations", 1000.0)
        finance_service.add_transaction("expense", "supplies", 300.0)
        summary = finance_service.get_summary()
        assert summary["total_income"] >= 1000.0
        assert summary["total_expense"] >= 300.0
        assert "balance" in summary

    def test_set_budget(self, finance_service):
        budget = finance_service.set_budget(
            department="Maths", allocated=10000.0, notes="Annual budget",
        )
        assert budget["department"] == "Maths"
        assert budget["allocated"] == 10000.0

    def test_list_budgets(self, finance_service):
        finance_service.set_budget("Maths", 10000.0)
        finance_service.set_budget("Science", 12000.0)
        budgets = finance_service.list_budgets()
        assert len(budgets) >= 2

    def test_update_budget_spent(self, finance_service):
        budget = finance_service.set_budget("English", 8000.0)
        finance_service.update_budget_spent(budget["id"], 2500.0)
        budgets = finance_service.list_budgets()
        eng = [b for b in budgets if b["department"] == "English"][0]
        assert eng["spent"] == 2500.0

    def test_delete_budget(self, finance_service):
        budget = finance_service.set_budget("Art", 5000.0)
        finance_service.delete_budget(budget["id"])
        budgets = finance_service.list_budgets()
        assert all(b["id"] != budget["id"] for b in budgets)
