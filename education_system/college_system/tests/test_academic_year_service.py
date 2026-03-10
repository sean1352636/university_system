"""Tests for AcademicYearService."""

import pytest
from education_system.college_system.core.exceptions import AcademicYearError, ValidationError


class TestAcademicYearService:
    """Test suite for AcademicYearService."""

    def test_create_year(self, academic_year_service):
        item = academic_year_service.create_year(name="test_name", start_date="test_start_date", end_date="test_end_date")
        assert item["id"] is not None

    def test_get_year(self, academic_year_service):
        item = academic_year_service.create_year(name="test_name", start_date="test_start_date", end_date="test_end_date")
        found = academic_year_service.get_year(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_years(self, academic_year_service):
        academic_year_service.create_year(name="test_name", start_date="test_start_date", end_date="test_end_date")
        items = academic_year_service.list_years()
        assert len(items) >= 1

    def test_update_year(self, academic_year_service):
        item = academic_year_service.create_year(name="test_name", start_date="test_start_date", end_date="test_end_date")
        updated = academic_year_service.update_year(item["id"], name="updated_value")
        assert updated["name"] == "updated_value"

    def test_delete_year(self, academic_year_service):
        item = academic_year_service.create_year(name="test_name", start_date="test_start_date", end_date="test_end_date")
        result = academic_year_service.delete_year(item["id"])
        assert result is True
        assert academic_year_service.get_year(item["id"]) is None

    def test_count_years(self, academic_year_service):
        academic_year_service.create_year(name="test_name", start_date="test_start_date", end_date="test_end_date")
        count = academic_year_service.count_years()
        assert count >= 1

    def test_delete_nonexistent_raises(self, academic_year_service):
        with pytest.raises(AcademicYearError):
            academic_year_service.delete_year(99999)
