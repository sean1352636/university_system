"""Tests for Parent Portal service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, parent_portal_service):
        """Creating a record should return a dict with an id."""
        result = parent_portal_service.create(parent_name="Sarah Smith", email="sarah@example.com", access_level="Standard")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, parent_portal_service):
        """Created record should contain the provided fields."""
        result = parent_portal_service.create(parent_name="Sarah Smith", email="sarah@example.com", access_level="Standard")
        assert result["parent_name"] == "Sarah Smith"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, parent_portal_service):
        """Listing with no records should return an empty list."""
        result = parent_portal_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, parent_portal_service):
        """Listing after creating a record should include it."""
        parent_portal_service.create(parent_name="Sarah Smith", email="sarah@example.com", access_level="Standard")
        result = parent_portal_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, parent_portal_service):
        """Getting an existing record should return it."""
        created = parent_portal_service.create(parent_name="Sarah Smith", email="sarah@example.com", access_level="Standard")
        result = parent_portal_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, parent_portal_service):
        """Getting a nonexistent record should return None."""
        result = parent_portal_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_parent_name(self, parent_portal_service):
        """Updating a field should persist the change."""
        created = parent_portal_service.create(parent_name="Sarah Smith", email="sarah@example.com", access_level="Standard")
        parent_portal_service.update(created["id"], parent_name="Updated Value")
        result = parent_portal_service.get(created["id"])
        assert result["parent_name"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, parent_portal_service):
        """Deleting an existing record should remove it."""
        created = parent_portal_service.create(parent_name="Sarah Smith", email="sarah@example.com", access_level="Standard")
        parent_portal_service.delete(created["id"])
        result = parent_portal_service.get(created["id"])
        assert result is None
