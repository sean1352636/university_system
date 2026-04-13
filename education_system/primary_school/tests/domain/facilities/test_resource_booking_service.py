"""Tests for Resource Booking service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, resource_booking_service):
        """Creating a record should return a dict with an id."""
        result = resource_booking_service.create(name="iPad Set A", resource_type="Technology", location="IT Suite")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, resource_booking_service):
        """Created record should contain the provided fields."""
        result = resource_booking_service.create(name="iPad Set A", resource_type="Technology", location="IT Suite")
        assert result["name"] == "iPad Set A"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, resource_booking_service):
        """Listing with no records should return an empty list."""
        result = resource_booking_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, resource_booking_service):
        """Listing after creating a record should include it."""
        resource_booking_service.create(name="iPad Set A", resource_type="Technology", location="IT Suite")
        result = resource_booking_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, resource_booking_service):
        """Getting an existing record should return it."""
        created = resource_booking_service.create(name="iPad Set A", resource_type="Technology", location="IT Suite")
        result = resource_booking_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, resource_booking_service):
        """Getting a nonexistent record should return None."""
        result = resource_booking_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_name(self, resource_booking_service):
        """Updating a field should persist the change."""
        created = resource_booking_service.create(name="iPad Set A", resource_type="Technology", location="IT Suite")
        resource_booking_service.update(created["id"], name="Updated Value")
        result = resource_booking_service.get(created["id"])
        assert result["name"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, resource_booking_service):
        """Deleting an existing record should remove it."""
        created = resource_booking_service.create(name="iPad Set A", resource_type="Technology", location="IT Suite")
        resource_booking_service.delete(created["id"])
        result = resource_booking_service.get(created["id"])
        assert result is None
