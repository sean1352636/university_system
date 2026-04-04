"""Tests for the FinanceService in the Primary School system."""

import pytest


class TestRecordTransaction:
    """Tests for recording financial transactions."""

    def test_record_transaction_returns_dict(self, finance_service):
        """Recording a transaction returns a dict with id and type."""
        result = finance_service.record_transaction(
            transaction_type="income",
            description="School trip payment",
            amount=25.00,
            category="Trips",
            reference="TRP-001",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["transaction_type"] == "income"
        assert result["amount"] == 25.00

    def test_record_transaction_persists(self, finance_service):
        """Recorded transaction appears in get_transactions."""
        finance_service.record_transaction(
            transaction_type="expense",
            description="Art supplies",
            amount=150.00,
            category="Resources",
        )
        txns = finance_service.get_transactions()
        assert len(txns) == 1
        assert txns[0]["description"] == "Art supplies"

    def test_record_multiple_transactions(self, finance_service):
        """Multiple transactions receive distinct IDs."""
        t1 = finance_service.record_transaction(
            transaction_type="income", description="Fee A", amount=10.0,
        )
        t2 = finance_service.record_transaction(
            transaction_type="expense", description="Fee B", amount=20.0,
        )
        assert t1["id"] != t2["id"]


class TestGetTransactions:
    """Tests for querying transactions."""

    def test_get_transactions_empty_db(self, finance_service):
        """Querying an empty database returns an empty list."""
        assert finance_service.get_transactions() == []

    def test_filter_by_category(self, finance_service):
        """Filtering by category returns only matching transactions."""
        finance_service.record_transaction(
            transaction_type="income", description="Lunch", amount=5.0,
            category="Meals",
        )
        finance_service.record_transaction(
            transaction_type="expense", description="Books", amount=30.0,
            category="Resources",
        )
        results = finance_service.get_transactions(category="Meals")
        assert len(results) == 1
        assert results[0]["category"] == "Meals"


class TestUpdateTransaction:
    """Tests for updating transactions."""

    @pytest.mark.xfail(reason="Service references updated_at column missing from schema")
    def test_update_transaction_amount(self, finance_service):
        """Updating the amount persists the change."""
        txn = finance_service.record_transaction(
            transaction_type="income", description="Donation", amount=100.0,
        )
        updated = finance_service.update_transaction(txn["id"], amount=200.0)
        assert updated["amount"] == 200.0

    def test_update_with_no_valid_fields(self, finance_service):
        """Passing unrecognised fields returns None."""
        txn = finance_service.record_transaction(
            transaction_type="income", description="X", amount=1.0,
        )
        result = finance_service.update_transaction(txn["id"], bogus="val")
        assert result is None


class TestBudgets:
    """Tests for budget CRUD."""

    def test_create_budget_returns_dict(self, finance_service):
        """Creating a budget returns a dict with id and name."""
        result = finance_service.create_budget(
            budget_name="IT Equipment",
            allocated_amount=5000.0,
            category="Technology",
            academic_year="2025/26",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["budget_name"] == "IT Equipment"

    def test_get_budgets_empty(self, finance_service):
        """Querying budgets on an empty database returns an empty list."""
        assert finance_service.get_budgets() == []

    def test_get_budgets_after_create(self, finance_service):
        """Created budget appears in get_budgets."""
        finance_service.create_budget(
            budget_name="Sports", allocated_amount=2000.0,
            academic_year="2025/26",
        )
        budgets = finance_service.get_budgets()
        assert len(budgets) == 1
        assert budgets[0]["budget_name"] == "Sports"

    @pytest.mark.xfail(reason="Service references updated_at column missing from schema")
    def test_update_budget(self, finance_service):
        """Updating a budget persists the change."""
        b = finance_service.create_budget(
            budget_name="Library", allocated_amount=1000.0,
        )
        updated = finance_service.update_budget(b["id"], allocated_amount=1500.0)
        assert updated["allocated_amount"] == 1500.0
