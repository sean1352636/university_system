"""Tests for StaffWellbeingService."""

import pytest
from education_system.college_system.core.exceptions import StaffWellbeingError, ValidationError


class TestStaffWellbeingService:
    """Test suite for StaffWellbeingService."""

    def test_create_checkin(self, staff_wellbeing_service):
        item = staff_wellbeing_service.create_checkin(staff_id=1)
        assert item["id"] is not None

    def test_get_checkin(self, staff_wellbeing_service):
        item = staff_wellbeing_service.create_checkin(staff_id=1)
        found = staff_wellbeing_service.get_checkin(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_checkins(self, staff_wellbeing_service):
        staff_wellbeing_service.create_checkin(staff_id=1)
        items = staff_wellbeing_service.list_checkins()
        assert len(items) >= 1

    def test_update_checkin(self, staff_wellbeing_service):
        item = staff_wellbeing_service.create_checkin(staff_id=1)
        updated = staff_wellbeing_service.update_checkin(item["id"], checkin_date="updated_value")
        assert updated["checkin_date"] == "updated_value"

    def test_delete_checkin(self, staff_wellbeing_service):
        item = staff_wellbeing_service.create_checkin(staff_id=1)
        result = staff_wellbeing_service.delete_checkin(item["id"])
        assert result is True
        assert staff_wellbeing_service.get_checkin(item["id"]) is None

    def test_count_checkins(self, staff_wellbeing_service):
        staff_wellbeing_service.create_checkin(staff_id=1)
        count = staff_wellbeing_service.count_checkins()
        assert count >= 1

    def test_delete_nonexistent_raises(self, staff_wellbeing_service):
        with pytest.raises(StaffWellbeingError):
            staff_wellbeing_service.delete_checkin(99999)
