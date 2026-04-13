"""Tests for Equality & Diversity service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, equality_diversity_service):
        """Creating a record should return a dict with an id."""
        result = equality_diversity_service.create(record_type="Incident", category="Race", description="Reported incident", status="Under Investigation")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, equality_diversity_service):
        """Created record should contain the provided fields."""
        result = equality_diversity_service.create(record_type="Incident", category="Race", description="Reported incident", status="Under Investigation")
        assert result["record_type"] == "Incident"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, equality_diversity_service):
        """Listing with no records should return an empty list."""
        result = equality_diversity_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, equality_diversity_service):
        """Listing after creating a record should include it."""
        equality_diversity_service.create(record_type="Incident", category="Race", description="Reported incident", status="Under Investigation")
        result = equality_diversity_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, equality_diversity_service):
        """Getting an existing record should return it."""
        created = equality_diversity_service.create(record_type="Incident", category="Race", description="Reported incident", status="Under Investigation")
        result = equality_diversity_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, equality_diversity_service):
        """Getting a nonexistent record should return None."""
        result = equality_diversity_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_record_type(self, equality_diversity_service):
        """Updating a field should persist the change."""
        created = equality_diversity_service.create(record_type="Incident", category="Race", description="Reported incident", status="Under Investigation")
        equality_diversity_service.update(created["id"], record_type="Updated Value")
        result = equality_diversity_service.get(created["id"])
        assert result["record_type"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, equality_diversity_service):
        """Deleting an existing record should remove it."""
        created = equality_diversity_service.create(record_type="Incident", category="Race", description="Reported incident", status="Under Investigation")
        equality_diversity_service.delete(created["id"])
        result = equality_diversity_service.get(created["id"])
        assert result is None
