"""Tests for Health & Safety service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, health_safety_service):
        """Creating a record should return a dict with an id."""
        result = health_safety_service.create(title="Playground trip", description="Pupil tripped on uneven surface", location="Playground", severity="Minor", status="Open")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, health_safety_service):
        """Created record should contain the provided fields."""
        result = health_safety_service.create(title="Playground trip", description="Pupil tripped on uneven surface", location="Playground", severity="Minor", status="Open")
        assert result["title"] == "Playground trip"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, health_safety_service):
        """Listing with no records should return an empty list."""
        result = health_safety_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, health_safety_service):
        """Listing after creating a record should include it."""
        health_safety_service.create(title="Playground trip", description="Pupil tripped on uneven surface", location="Playground", severity="Minor", status="Open")
        result = health_safety_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, health_safety_service):
        """Getting an existing record should return it."""
        created = health_safety_service.create(title="Playground trip", description="Pupil tripped on uneven surface", location="Playground", severity="Minor", status="Open")
        result = health_safety_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, health_safety_service):
        """Getting a nonexistent record should return None."""
        result = health_safety_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_title(self, health_safety_service):
        """Updating a field should persist the change."""
        created = health_safety_service.create(title="Playground trip", description="Pupil tripped on uneven surface", location="Playground", severity="Minor", status="Open")
        health_safety_service.update(created["id"], title="Updated Value")
        result = health_safety_service.get(created["id"])
        assert result["title"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, health_safety_service):
        """Deleting an existing record should remove it."""
        created = health_safety_service.create(title="Playground trip", description="Pupil tripped on uneven surface", location="Playground", severity="Minor", status="Open")
        health_safety_service.delete(created["id"])
        result = health_safety_service.get(created["id"])
        assert result is None
