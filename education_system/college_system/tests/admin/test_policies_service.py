"""Tests for PolicyService."""

import pytest
from education_system.college_system.core.exceptions import PolicyError, ValidationError


class TestPolicyService:
    """Test suite for PolicyService."""

    def test_create_policy(self, policies_service):
        item = policies_service.create_policy(title="test_title", category="test_category")
        assert item["id"] is not None

    def test_get_policy(self, policies_service):
        item = policies_service.create_policy(title="test_title", category="test_category")
        found = policies_service.get_policy(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_policies(self, policies_service):
        policies_service.create_policy(title="test_title", category="test_category")
        items = policies_service.list_policies()
        assert len(items) >= 1

    def test_update_policy(self, policies_service):
        item = policies_service.create_policy(title="test_title", category="test_category")
        updated = policies_service.update_policy(item["id"], title="updated_value")
        assert updated["title"] == "updated_value"

    def test_delete_policy(self, policies_service):
        item = policies_service.create_policy(title="test_title", category="test_category")
        result = policies_service.delete_policy(item["id"])
        assert result is True
        assert policies_service.get_policy(item["id"]) is None

    def test_count_policies(self, policies_service):
        policies_service.create_policy(title="test_title", category="test_category")
        count = policies_service.count_policies()
        assert count >= 1

    def test_delete_nonexistent_raises(self, policies_service):
        with pytest.raises(PolicyError):
            policies_service.delete_policy(99999)
