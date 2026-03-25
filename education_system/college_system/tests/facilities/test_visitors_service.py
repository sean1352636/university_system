"""Tests for VisitorService."""

import pytest
from education_system.college_system.core.exceptions import VisitorError, ValidationError


class TestVisitorService:
    """Test suite for VisitorService."""

    def test_create_visitor(self, visitors_service):
        item = visitors_service.create_visitor(first_name="test_first_name", last_name="test_last_name", purpose="test_purpose")
        assert item["id"] is not None

    def test_get_visitor(self, visitors_service):
        item = visitors_service.create_visitor(first_name="test_first_name", last_name="test_last_name", purpose="test_purpose")
        found = visitors_service.get_visitor(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_visitors(self, visitors_service):
        visitors_service.create_visitor(first_name="test_first_name", last_name="test_last_name", purpose="test_purpose")
        items = visitors_service.list_visitors()
        assert len(items) >= 1

    def test_update_visitor(self, visitors_service):
        item = visitors_service.create_visitor(first_name="test_first_name", last_name="test_last_name", purpose="test_purpose")
        updated = visitors_service.update_visitor(item["id"], first_name="updated_value")
        assert updated["first_name"] == "updated_value"

    def test_delete_visitor(self, visitors_service):
        item = visitors_service.create_visitor(first_name="test_first_name", last_name="test_last_name", purpose="test_purpose")
        result = visitors_service.delete_visitor(item["id"])
        assert result is True
        assert visitors_service.get_visitor(item["id"]) is None

    def test_count_visitors(self, visitors_service):
        visitors_service.create_visitor(first_name="test_first_name", last_name="test_last_name", purpose="test_purpose")
        count = visitors_service.count_visitors()
        assert count >= 1

    def test_delete_nonexistent_raises(self, visitors_service):
        with pytest.raises(VisitorError):
            visitors_service.delete_visitor(99999)
