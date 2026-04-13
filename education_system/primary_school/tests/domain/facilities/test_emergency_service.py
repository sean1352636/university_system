"""Tests for Emergency service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, emergency_service):
        """Creating a record should return a dict with an id."""
        result = emergency_service.create(procedure_type="Fire Evacuation", title="Main Building Fire Drill", description="Full evacuation procedure", status="Active")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, emergency_service):
        """Created record should contain the provided fields."""
        result = emergency_service.create(procedure_type="Fire Evacuation", title="Main Building Fire Drill", description="Full evacuation procedure", status="Active")
        assert result["procedure_type"] == "Fire Evacuation"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, emergency_service):
        """Listing with no records should return an empty list."""
        result = emergency_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, emergency_service):
        """Listing after creating a record should include it."""
        emergency_service.create(procedure_type="Fire Evacuation", title="Main Building Fire Drill", description="Full evacuation procedure", status="Active")
        result = emergency_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, emergency_service):
        """Getting an existing record should return it."""
        created = emergency_service.create(procedure_type="Fire Evacuation", title="Main Building Fire Drill", description="Full evacuation procedure", status="Active")
        result = emergency_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, emergency_service):
        """Getting a nonexistent record should return None."""
        result = emergency_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_procedure_type(self, emergency_service):
        """Updating a field should persist the change."""
        created = emergency_service.create(procedure_type="Fire Evacuation", title="Main Building Fire Drill", description="Full evacuation procedure", status="Active")
        emergency_service.update(created["id"], procedure_type="Updated Value")
        result = emergency_service.get(created["id"])
        assert result["procedure_type"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, emergency_service):
        """Deleting an existing record should remove it."""
        created = emergency_service.create(procedure_type="Fire Evacuation", title="Main Building Fire Drill", description="Full evacuation procedure", status="Active")
        emergency_service.delete(created["id"])
        result = emergency_service.get(created["id"])
        assert result is None
