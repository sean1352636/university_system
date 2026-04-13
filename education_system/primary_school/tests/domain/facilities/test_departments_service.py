"""Tests for Departments service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, departments_service):
        """Creating a record should return a dict with an id."""
        result = departments_service.create(name="Mathematics", head_of_department="Mrs Brown", status="Active")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, departments_service):
        """Created record should contain the provided fields."""
        result = departments_service.create(name="Mathematics", head_of_department="Mrs Brown", status="Active")
        assert result["name"] == "Mathematics"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, departments_service):
        """Listing with no records should return an empty list."""
        result = departments_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, departments_service):
        """Listing after creating a record should include it."""
        departments_service.create(name="Mathematics", head_of_department="Mrs Brown", status="Active")
        result = departments_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, departments_service):
        """Getting an existing record should return it."""
        created = departments_service.create(name="Mathematics", head_of_department="Mrs Brown", status="Active")
        result = departments_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, departments_service):
        """Getting a nonexistent record should return None."""
        result = departments_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_name(self, departments_service):
        """Updating a field should persist the change."""
        created = departments_service.create(name="Mathematics", head_of_department="Mrs Brown", status="Active")
        departments_service.update(created["id"], name="Updated Value")
        result = departments_service.get(created["id"])
        assert result["name"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, departments_service):
        """Deleting an existing record should remove it."""
        created = departments_service.create(name="Mathematics", head_of_department="Mrs Brown", status="Active")
        departments_service.delete(created["id"])
        result = departments_service.get(created["id"])
        assert result is None
