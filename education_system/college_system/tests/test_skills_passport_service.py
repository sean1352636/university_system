"""Tests for SkillsPassportService."""

import pytest
from education_system.college_system.core.exceptions import SkillsPassportError, ValidationError


class TestSkillsPassportService:
    """Test suite for SkillsPassportService."""

    def test_create_category(self, skills_passport_service):
        item = skills_passport_service.create_category(name="test_name")
        assert item["id"] is not None

    def test_get_category(self, skills_passport_service):
        item = skills_passport_service.create_category(name="test_name")
        found = skills_passport_service.get_category(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_categories(self, skills_passport_service):
        skills_passport_service.create_category(name="test_name")
        items = skills_passport_service.list_categories()
        assert len(items) >= 1

    def test_update_category(self, skills_passport_service):
        item = skills_passport_service.create_category(name="test_name")
        updated = skills_passport_service.update_category(item["id"], name="updated_value")
        assert updated["name"] == "updated_value"

    def test_delete_category(self, skills_passport_service):
        item = skills_passport_service.create_category(name="test_name")
        result = skills_passport_service.delete_category(item["id"])
        assert result is True
        assert skills_passport_service.get_category(item["id"]) is None

    def test_count_categories(self, skills_passport_service):
        skills_passport_service.create_category(name="test_name")
        count = skills_passport_service.count_categories()
        assert count >= 1

    def test_delete_nonexistent_raises(self, skills_passport_service):
        with pytest.raises(SkillsPassportError):
            skills_passport_service.delete_category(99999)
