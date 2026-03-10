"""Tests for MealOrderingService."""

import pytest
from education_system.college_system.core.exceptions import MealOrderingError, ValidationError


class TestMealOrderingService:
    """Test suite for MealOrderingService."""

    def test_create_item(self, meal_ordering_service):
        item = meal_ordering_service.create_item(name="test_name", category="test_category")
        assert item["id"] is not None

    def test_get_item(self, meal_ordering_service):
        item = meal_ordering_service.create_item(name="test_name", category="test_category")
        found = meal_ordering_service.get_item(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_items(self, meal_ordering_service):
        meal_ordering_service.create_item(name="test_name", category="test_category")
        items = meal_ordering_service.list_items()
        assert len(items) >= 1

    def test_update_item(self, meal_ordering_service):
        item = meal_ordering_service.create_item(name="test_name", category="test_category")
        updated = meal_ordering_service.update_item(item["id"], name="updated_value")
        assert updated["name"] == "updated_value"

    def test_delete_item(self, meal_ordering_service):
        item = meal_ordering_service.create_item(name="test_name", category="test_category")
        result = meal_ordering_service.delete_item(item["id"])
        assert result is True
        assert meal_ordering_service.get_item(item["id"]) is None

    def test_count_items(self, meal_ordering_service):
        meal_ordering_service.create_item(name="test_name", category="test_category")
        count = meal_ordering_service.count_items()
        assert count >= 1

    def test_delete_nonexistent_raises(self, meal_ordering_service):
        with pytest.raises(MealOrderingError):
            meal_ordering_service.delete_item(99999)
