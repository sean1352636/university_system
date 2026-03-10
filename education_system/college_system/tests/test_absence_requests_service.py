"""Tests for AbsenceRequestService."""

import pytest
from education_system.college_system.core.exceptions import AbsenceRequestError, ValidationError


class TestAbsenceRequestService:
    """Test suite for AbsenceRequestService."""

    def test_create_request(self, absence_requests_service):
        item = absence_requests_service.create_request(staff_id=1, absence_type="test_absence_type", start_date="test_start_date", end_date="test_end_date")
        assert item["id"] is not None

    def test_get_request(self, absence_requests_service):
        item = absence_requests_service.create_request(staff_id=1, absence_type="test_absence_type", start_date="test_start_date", end_date="test_end_date")
        found = absence_requests_service.get_request(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_requests(self, absence_requests_service):
        absence_requests_service.create_request(staff_id=1, absence_type="test_absence_type", start_date="test_start_date", end_date="test_end_date")
        items = absence_requests_service.list_requests()
        assert len(items) >= 1

    def test_update_request(self, absence_requests_service):
        item = absence_requests_service.create_request(staff_id=1, absence_type="test_absence_type", start_date="test_start_date", end_date="test_end_date")
        updated = absence_requests_service.update_request(item["id"], absence_type="updated_value")
        assert updated["absence_type"] == "updated_value"

    def test_delete_request(self, absence_requests_service):
        item = absence_requests_service.create_request(staff_id=1, absence_type="test_absence_type", start_date="test_start_date", end_date="test_end_date")
        result = absence_requests_service.delete_request(item["id"])
        assert result is True
        assert absence_requests_service.get_request(item["id"]) is None

    def test_count_requests(self, absence_requests_service):
        absence_requests_service.create_request(staff_id=1, absence_type="test_absence_type", start_date="test_start_date", end_date="test_end_date")
        count = absence_requests_service.count_requests()
        assert count >= 1

    def test_delete_nonexistent_raises(self, absence_requests_service):
        with pytest.raises(AbsenceRequestError):
            absence_requests_service.delete_request(99999)
