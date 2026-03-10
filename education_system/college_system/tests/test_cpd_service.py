"""Tests for CPDService."""

import pytest
from education_system.college_system.core.exceptions import CPDError, ValidationError


class TestCPDService:
    """Test suite for CPDService."""

    def test_create_record(self, cpd_service):
        item = cpd_service.create_record(staff_id=1, title="test_title", cpd_type="test_cpd_type")
        assert item["id"] is not None

    def test_get_record(self, cpd_service):
        item = cpd_service.create_record(staff_id=1, title="test_title", cpd_type="test_cpd_type")
        found = cpd_service.get_record(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_records(self, cpd_service):
        cpd_service.create_record(staff_id=1, title="test_title", cpd_type="test_cpd_type")
        items = cpd_service.list_records()
        assert len(items) >= 1

    def test_update_record(self, cpd_service):
        item = cpd_service.create_record(staff_id=1, title="test_title", cpd_type="test_cpd_type")
        updated = cpd_service.update_record(item["id"], title="updated_value")
        assert updated["title"] == "updated_value"

    def test_delete_record(self, cpd_service):
        item = cpd_service.create_record(staff_id=1, title="test_title", cpd_type="test_cpd_type")
        result = cpd_service.delete_record(item["id"])
        assert result is True
        assert cpd_service.get_record(item["id"]) is None

    def test_count_records(self, cpd_service):
        cpd_service.create_record(staff_id=1, title="test_title", cpd_type="test_cpd_type")
        count = cpd_service.count_records()
        assert count >= 1

    def test_delete_nonexistent_raises(self, cpd_service):
        with pytest.raises(CPDError):
            cpd_service.delete_record(99999)
