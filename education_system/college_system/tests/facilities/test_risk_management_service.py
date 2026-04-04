"""Tests for RiskManagementService."""

import pytest


class TestRiskManagementService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.risk_management.services.risk_management_service import RiskManagementService
        return RiskManagementService(db_path)

    def test_create_risk(self, service):
        risk = service.create_risk(
            risk_title="Data breach risk",
            category="information_security",
            description="Potential for student data leak",
            likelihood=3, impact=5,
            mitigation_strategy="Encrypt all databases",
            risk_owner="IT Director",
        )
        assert risk is not None

    def test_list_risks(self, service):
        service.create_risk("Risk A", category="operational")
        service.create_risk("Risk B", category="financial")
        risks = service.list_risks()
        assert len(risks) >= 2

    def test_list_risks_filter(self, service):
        service.create_risk("Op Risk", category="operational")
        risks = service.list_risks(category="operational")
        assert all(r["category"] == "operational" for r in risks)

    def test_get_risk(self, service):
        risk = service.create_risk("Test Risk")
        rid = risk if isinstance(risk, int) else risk.get("id", risk)
        found = service.get_risk(rid)
        assert found is not None

    def test_update_risk(self, service):
        risk = service.create_risk("Update me")
        rid = risk if isinstance(risk, int) else risk.get("id", risk)
        updated = service.update_risk(rid, status="mitigated")
        assert updated is not None

    def test_delete_risk(self, service):
        risk = service.create_risk("Delete me")
        rid = risk if isinstance(risk, int) else risk.get("id", risk)
        result = service.delete_risk(rid)
        assert result is True or result is None

    def test_create_review(self, service):
        risk = service.create_risk("Review target")
        rid = risk if isinstance(risk, int) else risk.get("id", risk)
        review = service.create_review(
            risk_id=rid, review_date="2026-04-01",
            reviewer="Risk Committee",
            commentary="Risk level unchanged",
        )
        assert review is not None

    def test_list_reviews(self, service):
        risk = service.create_risk("Reviewed risk")
        rid = risk if isinstance(risk, int) else risk.get("id", risk)
        service.create_review(rid, "2026-04-01")
        reviews = service.list_reviews(rid)
        assert len(reviews) >= 1

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
