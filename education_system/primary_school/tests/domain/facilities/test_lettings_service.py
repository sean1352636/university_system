"""Tests for Lettings service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, lettings_service):
        """Creating a record should return a dict with an id."""
        result = lettings_service.create(facility="Main Hall", hirer_name="Local Cubs", event_type="Meeting", booking_date="2026-03-01", status="Confirmed")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, lettings_service):
        """Created record should contain the provided fields."""
        result = lettings_service.create(facility="Main Hall", hirer_name="Local Cubs", event_type="Meeting", booking_date="2026-03-01", status="Confirmed")
        assert result["facility"] == "Main Hall"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, lettings_service):
        """Listing with no records should return an empty list."""
        result = lettings_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, lettings_service):
        """Listing after creating a record should include it."""
        lettings_service.create(facility="Main Hall", hirer_name="Local Cubs", event_type="Meeting", booking_date="2026-03-01", status="Confirmed")
        result = lettings_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, lettings_service):
        """Getting an existing record should return it."""
        created = lettings_service.create(facility="Main Hall", hirer_name="Local Cubs", event_type="Meeting", booking_date="2026-03-01", status="Confirmed")
        result = lettings_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, lettings_service):
        """Getting a nonexistent record should return None."""
        result = lettings_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_facility(self, lettings_service):
        """Updating a field should persist the change."""
        created = lettings_service.create(facility="Main Hall", hirer_name="Local Cubs", event_type="Meeting", booking_date="2026-03-01", status="Confirmed")
        lettings_service.update(created["id"], facility="Updated Value")
        result = lettings_service.get(created["id"])
        assert result["facility"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, lettings_service):
        """Deleting an existing record should remove it."""
        created = lettings_service.create(facility="Main Hall", hirer_name="Local Cubs", event_type="Meeting", booking_date="2026-03-01", status="Confirmed")
        lettings_service.delete(created["id"])
        result = lettings_service.get(created["id"])
        assert result is None
