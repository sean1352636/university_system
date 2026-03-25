"""Tests for PortfolioService."""

import pytest
from education_system.college_system.core.exceptions import PortfolioError, ValidationError


class TestPortfolioService:
    """Test suite for PortfolioService."""

    def test_create_item(self, portfolio_service):
        item = portfolio_service.create_item(student_id=1, title="test_title")
        assert item["id"] is not None

    def test_get_item(self, portfolio_service):
        item = portfolio_service.create_item(student_id=1, title="test_title")
        found = portfolio_service.get_item(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_items(self, portfolio_service):
        portfolio_service.create_item(student_id=1, title="test_title")
        items = portfolio_service.list_items()
        assert len(items) >= 1

    def test_update_item(self, portfolio_service):
        item = portfolio_service.create_item(student_id=1, title="test_title")
        updated = portfolio_service.update_item(item["id"], title="updated_value")
        assert updated["title"] == "updated_value"

    def test_delete_item(self, portfolio_service):
        item = portfolio_service.create_item(student_id=1, title="test_title")
        result = portfolio_service.delete_item(item["id"])
        assert result is True
        assert portfolio_service.get_item(item["id"]) is None

    def test_count_items(self, portfolio_service):
        portfolio_service.create_item(student_id=1, title="test_title")
        count = portfolio_service.count_items()
        assert count >= 1

    def test_delete_nonexistent_raises(self, portfolio_service):
        with pytest.raises(PortfolioError):
            portfolio_service.delete_item(99999)
