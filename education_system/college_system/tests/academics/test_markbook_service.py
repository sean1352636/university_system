"""Tests for MarkbookService."""

import pytest
from education_system.college_system.core.exceptions import MarkbookError, ValidationError


class TestMarkbookService:
    """Test suite for MarkbookService."""

    def test_create_column(self, markbook_service):
        item = markbook_service.create_column(course_id=1, column_name="test_column_name")
        assert item["id"] is not None

    def test_get_column(self, markbook_service):
        item = markbook_service.create_column(course_id=1, column_name="test_column_name")
        found = markbook_service.get_column(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_columns(self, markbook_service):
        markbook_service.create_column(course_id=1, column_name="test_column_name")
        items = markbook_service.list_columns()
        assert len(items) >= 1

    def test_update_column(self, markbook_service):
        item = markbook_service.create_column(course_id=1, column_name="test_column_name")
        updated = markbook_service.update_column(item["id"], column_name="updated_value")
        assert updated["column_name"] == "updated_value"

    def test_delete_column(self, markbook_service):
        item = markbook_service.create_column(course_id=1, column_name="test_column_name")
        result = markbook_service.delete_column(item["id"])
        assert result is True
        assert markbook_service.get_column(item["id"]) is None

    def test_count_columns(self, markbook_service):
        markbook_service.create_column(course_id=1, column_name="test_column_name")
        count = markbook_service.count_columns()
        assert count >= 1

    def test_delete_nonexistent_raises(self, markbook_service):
        with pytest.raises(MarkbookError):
            markbook_service.delete_column(99999)
