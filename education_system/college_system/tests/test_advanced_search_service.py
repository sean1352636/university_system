"""Tests for AdvancedSearchService."""

import pytest
from education_system.college_system.core.exceptions import AdvancedSearchError, ValidationError


class TestAdvancedSearchService:
    """Test suite for AdvancedSearchService."""

    def test_create_search(self, advanced_search_service):
        item = advanced_search_service.create_search(user_id=1, query="test_query")
        assert item["id"] is not None

    def test_get_search(self, advanced_search_service):
        item = advanced_search_service.create_search(user_id=1, query="test_query")
        found = advanced_search_service.get_search(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_searches(self, advanced_search_service):
        advanced_search_service.create_search(user_id=1, query="test_query")
        items = advanced_search_service.list_searches()
        assert len(items) >= 1

    def test_update_search(self, advanced_search_service):
        item = advanced_search_service.create_search(user_id=1, query="test_query")
        updated = advanced_search_service.update_search(item["id"], query="updated_value")
        assert updated["query"] == "updated_value"

    def test_delete_search(self, advanced_search_service):
        item = advanced_search_service.create_search(user_id=1, query="test_query")
        result = advanced_search_service.delete_search(item["id"])
        assert result is True
        assert advanced_search_service.get_search(item["id"]) is None

    def test_count_searches(self, advanced_search_service):
        advanced_search_service.create_search(user_id=1, query="test_query")
        count = advanced_search_service.count_searches()
        assert count >= 1

    def test_delete_nonexistent_raises(self, advanced_search_service):
        with pytest.raises(AdvancedSearchError):
            advanced_search_service.delete_search(99999)
