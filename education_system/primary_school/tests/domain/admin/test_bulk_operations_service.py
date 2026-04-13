"""Tests for Bulk Operations service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, bulk_operations_service):
        """Creating a record should return a dict with an id."""
        result = bulk_operations_service.create(operation_type="Year Group Rollover", description="Move all pupils up one year", initiated_by="admin", status="Pending")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, bulk_operations_service):
        """Created record should contain the provided fields."""
        result = bulk_operations_service.create(operation_type="Year Group Rollover", description="Move all pupils up one year", initiated_by="admin", status="Pending")
        assert result["operation_type"] == "Year Group Rollover"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, bulk_operations_service):
        """Listing with no records should return an empty list."""
        result = bulk_operations_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, bulk_operations_service):
        """Listing after creating a record should include it."""
        bulk_operations_service.create(operation_type="Year Group Rollover", description="Move all pupils up one year", initiated_by="admin", status="Pending")
        result = bulk_operations_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, bulk_operations_service):
        """Getting an existing record should return it."""
        created = bulk_operations_service.create(operation_type="Year Group Rollover", description="Move all pupils up one year", initiated_by="admin", status="Pending")
        result = bulk_operations_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, bulk_operations_service):
        """Getting a nonexistent record should return None."""
        result = bulk_operations_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_operation_type(self, bulk_operations_service):
        """Updating a field should persist the change."""
        created = bulk_operations_service.create(operation_type="Year Group Rollover", description="Move all pupils up one year", initiated_by="admin", status="Pending")
        bulk_operations_service.update(created["id"], operation_type="Updated Value")
        result = bulk_operations_service.get(created["id"])
        assert result["operation_type"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, bulk_operations_service):
        """Deleting an existing record should remove it."""
        created = bulk_operations_service.create(operation_type="Year Group Rollover", description="Move all pupils up one year", initiated_by="admin", status="Pending")
        bulk_operations_service.delete(created["id"])
        result = bulk_operations_service.get(created["id"])
        assert result is None
