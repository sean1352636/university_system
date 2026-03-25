"""Tests for EmergencyService."""

import pytest
from education_system.college_system.core.exceptions import EmergencyError, ValidationError


class TestEmergencyService:
    """Test suite for EmergencyService."""

    def test_create_drill(self, emergency_service):
        item = emergency_service.create_drill(drill_type="test_drill_type", scheduled_date="test_scheduled_date")
        assert item["id"] is not None

    def test_get_drill(self, emergency_service):
        item = emergency_service.create_drill(drill_type="test_drill_type", scheduled_date="test_scheduled_date")
        found = emergency_service.get_drill(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_drills(self, emergency_service):
        emergency_service.create_drill(drill_type="test_drill_type", scheduled_date="test_scheduled_date")
        items = emergency_service.list_drills()
        assert len(items) >= 1

    def test_update_drill(self, emergency_service):
        item = emergency_service.create_drill(drill_type="test_drill_type", scheduled_date="test_scheduled_date")
        updated = emergency_service.update_drill(item["id"], drill_type="updated_value")
        assert updated["drill_type"] == "updated_value"

    def test_delete_drill(self, emergency_service):
        item = emergency_service.create_drill(drill_type="test_drill_type", scheduled_date="test_scheduled_date")
        result = emergency_service.delete_drill(item["id"])
        assert result is True
        assert emergency_service.get_drill(item["id"]) is None

    def test_count_drills(self, emergency_service):
        emergency_service.create_drill(drill_type="test_drill_type", scheduled_date="test_scheduled_date")
        count = emergency_service.count_drills()
        assert count >= 1

    def test_delete_nonexistent_raises(self, emergency_service):
        with pytest.raises(EmergencyError):
            emergency_service.delete_drill(99999)
