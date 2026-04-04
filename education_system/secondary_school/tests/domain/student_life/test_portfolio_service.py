"""Tests for PortfolioService."""
import pytest
from education_system.secondary_school.modules.domain.student_life.portfolio.services.portfolio_service import PortfolioService


@pytest.fixture
def portfolio_service(db_path):
    return PortfolioService(db_path)


class TestPortfolioCRUD:
    def test_create(self, portfolio_service):
        r = portfolio_service.create(student_id="SEC0001", title="Art Project",
                                      category="art", description="Oil painting")
        assert r["student_id"] == "SEC0001"
        assert r["title"] == "Art Project"
        assert r["category"] == "art"
        assert r["description"] == "Oil painting"

    def test_list_all(self, portfolio_service):
        portfolio_service.create(student_id="SEC0001", title="Art Project")
        portfolio_service.create(student_id="SEC0001", title="Science Report")
        result = portfolio_service.list_all()
        assert len(result) >= 2

    def test_get(self, portfolio_service):
        r = portfolio_service.create(student_id="SEC0001", title="Art Project",
                                      category="art", description="Oil painting")
        found = portfolio_service.get(r["id"])
        assert found is not None
        assert found["student_id"] == "SEC0001"
        assert found["title"] == "Art Project"

    def test_update(self, portfolio_service):
        r = portfolio_service.create(student_id="SEC0001", title="Art Project",
                                      description="Oil painting")
        updated = portfolio_service.update(r["id"], title="Updated Art Project",
                                            description="Watercolour")
        assert updated["title"] == "Updated Art Project"
        assert updated["description"] == "Watercolour"

    def test_delete(self, portfolio_service):
        r = portfolio_service.create(student_id="SEC0001", title="Art Project")
        portfolio_service.delete(r["id"])
        assert portfolio_service.get(r["id"]) is None
