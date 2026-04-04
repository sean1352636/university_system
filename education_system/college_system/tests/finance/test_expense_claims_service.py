"""Tests for ExpenseClaimService."""

import pytest


class TestExpenseClaimService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.expense_claims.services.expense_claims_service import ExpenseClaimService
        return ExpenseClaimService(db_path)

    def test_create_claim(self, service):
        claim = service.create_claim(
            claimant_id=1, description="Train to conference",
            amount=45.50, category="travel",
        )
        assert claim is not None

    def test_list_claims(self, service):
        service.create_claim(1, "Lunch meeting", 15.00)
        service.create_claim(2, "Stationery", 8.50)
        claims = service.list_claims()
        assert len(claims) >= 2

    def test_get_claim(self, service):
        claim = service.create_claim(1, "Test", 10.00)
        found = service.get_claim(claim["id"])
        assert found is not None

    def test_update_claim(self, service):
        claim = service.create_claim(1, "Update me", 20.00)
        updated = service.update_claim(claim["id"], amount=25.00)
        assert updated is not None

    def test_delete_claim(self, service):
        claim = service.create_claim(1, "Delete me", 5.00)
        result = service.delete_claim(claim["id"])
        assert result is True

    def test_approve_claim(self, service):
        claim = service.create_claim(1, "Approve me", 30.00)
        approved = service.approve_claim(claim["id"], approved_by=99)
        assert approved["status"] in ("approved", "accepted")

    def test_reject_claim(self, service):
        claim = service.create_claim(1, "Reject me", 500.00)
        rejected = service.reject_claim(claim["id"], notes="Over budget")
        assert rejected["status"] == "rejected"

    def test_mark_paid(self, service):
        claim = service.create_claim(1, "Pay me", 30.00)
        service.approve_claim(claim["id"], approved_by=99)
        paid = service.mark_paid(claim["id"])
        assert paid["status"] == "paid"

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
