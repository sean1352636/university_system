"""Tests for MultiLanguageService."""

import pytest
from education_system.college_system.core.exceptions import MultiLanguageError, ValidationError


class TestMultiLanguageService:
    """Test suite for MultiLanguageService."""

    def test_create_override(self, multi_language_service):
        item = multi_language_service.create_override(locale="test_locale", key="test_key", value="test_value")
        assert item["id"] is not None

    def test_get_override(self, multi_language_service):
        item = multi_language_service.create_override(locale="test_locale", key="test_key", value="test_value")
        found = multi_language_service.get_override(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_overrides(self, multi_language_service):
        multi_language_service.create_override(locale="test_locale", key="test_key", value="test_value")
        items = multi_language_service.list_overrides()
        assert len(items) >= 1

    def test_update_override(self, multi_language_service):
        item = multi_language_service.create_override(locale="test_locale", key="test_key", value="test_value")
        updated = multi_language_service.update_override(item["id"], locale="updated_value")
        assert updated["locale"] == "updated_value"

    def test_delete_override(self, multi_language_service):
        item = multi_language_service.create_override(locale="test_locale", key="test_key", value="test_value")
        result = multi_language_service.delete_override(item["id"])
        assert result is True
        assert multi_language_service.get_override(item["id"]) is None

    def test_count_overrides(self, multi_language_service):
        multi_language_service.create_override(locale="test_locale", key="test_key", value="test_value")
        count = multi_language_service.count_overrides()
        assert count >= 1

    def test_delete_nonexistent_raises(self, multi_language_service):
        with pytest.raises(MultiLanguageError):
            multi_language_service.delete_override(99999)
