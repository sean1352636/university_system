"""Tests for AbsenceRequestService."""

import pytest
from education_system.college_system.core.exceptions import AbsenceRequestError, ValidationError


class TestAbsenceRequestService:
    """Test suite for AbsenceRequestService."""

    def test_create_request(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        assert item["id"] is not None
        assert item["status"] == "pending"

    def test_create_request_with_reason(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="medical_appointment",
            start_date="2026-04-10", end_date="2026-04-10",
            reason="Dentist appointment",
        )
        assert item["reason"] == "Dentist appointment"

    def test_create_request_missing_staff_id(self, absence_requests_service):
        with pytest.raises(ValidationError, match="staff_id is required"):
            absence_requests_service.create_request(
                absence_type="sick", start_date="2026-04-01", end_date="2026-04-03",
            )

    def test_create_request_invalid_type(self, absence_requests_service):
        with pytest.raises(ValidationError, match="Invalid absence type"):
            absence_requests_service.create_request(
                staff_id=1, absence_type="invalid_type",
                start_date="2026-04-01", end_date="2026-04-03",
            )

    def test_create_request_invalid_date_format(self, absence_requests_service):
        with pytest.raises(ValidationError, match="valid date"):
            absence_requests_service.create_request(
                staff_id=1, absence_type="sick",
                start_date="01-04-2026", end_date="2026-04-03",
            )

    def test_create_request_end_before_start(self, absence_requests_service):
        with pytest.raises(ValidationError, match="end_date cannot be before"):
            absence_requests_service.create_request(
                staff_id=1, absence_type="sick",
                start_date="2026-04-05", end_date="2026-04-01",
            )

    def test_get_request(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        found = absence_requests_service.get_request(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_get_nonexistent_request(self, absence_requests_service):
        assert absence_requests_service.get_request(99999) is None

    def test_list_requests(self, absence_requests_service):
        absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        items = absence_requests_service.list_requests()
        assert len(items) >= 1

    def test_list_requests_filter_by_status(self, absence_requests_service):
        absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        pending = absence_requests_service.list_requests(status="pending")
        assert len(pending) >= 1
        assert all(r["status"] == "pending" for r in pending)

    def test_update_request(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        updated = absence_requests_service.update_request(item["id"], absence_type="annual_leave")
        assert updated["absence_type"] == "annual_leave"

    def test_update_request_invalid_type(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        with pytest.raises(ValidationError, match="Invalid absence type"):
            absence_requests_service.update_request(item["id"], absence_type="invalid")

    def test_approve_request(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        result = absence_requests_service.approve_request(item["id"], approved_by=99)
        assert result["status"] == "approved"
        assert result["approved_by"] == 99

    def test_approve_non_pending_raises(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        absence_requests_service.approve_request(item["id"], approved_by=99)
        with pytest.raises(AbsenceRequestError, match="Only pending"):
            absence_requests_service.approve_request(item["id"], approved_by=99)

    def test_reject_request(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        result = absence_requests_service.reject_request(item["id"], approved_by=99)
        assert result["status"] == "rejected"

    def test_cancel_request(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        result = absence_requests_service.cancel_request(item["id"], staff_id=1)
        assert result["status"] == "cancelled"

    def test_cancel_others_request_raises(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        with pytest.raises(AbsenceRequestError, match="only cancel your own"):
            absence_requests_service.cancel_request(item["id"], staff_id=999)

    def test_delete_request(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        result = absence_requests_service.delete_request(item["id"])
        assert result is True
        assert absence_requests_service.get_request(item["id"]) is None

    def test_count_requests(self, absence_requests_service):
        absence_requests_service.create_request(
            staff_id=1, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        count = absence_requests_service.count_requests()
        assert count >= 1

    def test_delete_nonexistent_raises(self, absence_requests_service):
        with pytest.raises(AbsenceRequestError):
            absence_requests_service.delete_request(99999)

    def test_get_my_requests(self, absence_requests_service):
        absence_requests_service.create_request(
            staff_id=42, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        absence_requests_service.create_request(
            staff_id=99, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        mine = absence_requests_service.get_my_requests(42)
        assert all(r["staff_id"] == 42 for r in mine)

    def test_get_my_requests_filtered_by_status(self, absence_requests_service):
        item = absence_requests_service.create_request(
            staff_id=42, absence_type="sick",
            start_date="2026-04-01", end_date="2026-04-03",
        )
        absence_requests_service.approve_request(item["id"], approved_by=1)
        pending = absence_requests_service.get_my_requests(42, status="pending")
        assert all(r["status"] == "pending" for r in pending)

    def test_approve_nonexistent_raises(self, absence_requests_service):
        with pytest.raises(AbsenceRequestError, match="not found"):
            absence_requests_service.approve_request(99999, approved_by=1)
