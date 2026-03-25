"""Tests for AccessibilityService."""

import pytest
from education_system.college_system.core.exceptions import AccessibilityError, ValidationError


class TestAccessibilityService:
    """Test suite for AccessibilityService."""

    def test_create_preference(self, accessibility_service):
        item = accessibility_service.create_preference(user_id=1)
        assert item["id"] is not None

    def test_get_preference(self, accessibility_service):
        item = accessibility_service.create_preference(user_id=1)
        found = accessibility_service.get_preference(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_preferences(self, accessibility_service):
        accessibility_service.create_preference(user_id=1)
        items = accessibility_service.list_preferences()
        assert len(items) >= 1

    def test_update_preference(self, accessibility_service):
        item = accessibility_service.create_preference(user_id=1)
        updated = accessibility_service.update_preference(item["id"], theme="updated_value")
        assert updated["theme"] == "updated_value"

    def test_delete_preference(self, accessibility_service):
        item = accessibility_service.create_preference(user_id=1)
        result = accessibility_service.delete_preference(item["id"])
        assert result is True
        assert accessibility_service.get_preference(item["id"]) is None

    def test_count_preferences(self, accessibility_service):
        accessibility_service.create_preference(user_id=1)
        count = accessibility_service.count_preferences()
        assert count >= 1

    def test_delete_nonexistent_raises(self, accessibility_service):
        with pytest.raises(AccessibilityError):
            accessibility_service.delete_preference(99999)
