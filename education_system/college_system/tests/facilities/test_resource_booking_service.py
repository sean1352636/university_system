"""Tests for ResourceBookingService."""

import pytest
from education_system.college_system.core.exceptions import ResourceBookingError, ValidationError


class TestResourceBookingService:
    """Test suite for ResourceBookingService."""

    def test_create_resource(self, resource_booking_service):
        item = resource_booking_service.create_resource(name="test_name", resource_type="test_resource_type")
        assert item["id"] is not None

    def test_get_resource(self, resource_booking_service):
        item = resource_booking_service.create_resource(name="test_name", resource_type="test_resource_type")
        found = resource_booking_service.get_resource(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_resources(self, resource_booking_service):
        resource_booking_service.create_resource(name="test_name", resource_type="test_resource_type")
        items = resource_booking_service.list_resources()
        assert len(items) >= 1

    def test_update_resource(self, resource_booking_service):
        item = resource_booking_service.create_resource(name="test_name", resource_type="test_resource_type")
        updated = resource_booking_service.update_resource(item["id"], name="updated_value")
        assert updated["name"] == "updated_value"

    def test_delete_resource(self, resource_booking_service):
        item = resource_booking_service.create_resource(name="test_name", resource_type="test_resource_type")
        result = resource_booking_service.delete_resource(item["id"])
        assert result is True
        assert resource_booking_service.get_resource(item["id"]) is None

    def test_count_resources(self, resource_booking_service):
        resource_booking_service.create_resource(name="test_name", resource_type="test_resource_type")
        count = resource_booking_service.count_resources()
        assert count >= 1

    def test_delete_nonexistent_raises(self, resource_booking_service):
        with pytest.raises(ResourceBookingError):
            resource_booking_service.delete_resource(99999)
