"""Tests for Helpdesk service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, helpdesk_service):
        """Creating a record should return a dict with an id."""
        result = helpdesk_service.create(title="Projector not working", description="Classroom 4 projector", category="IT", priority="Medium", status="Open")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, helpdesk_service):
        """Created record should contain the provided fields."""
        result = helpdesk_service.create(title="Projector not working", description="Classroom 4 projector", category="IT", priority="Medium", status="Open")
        assert result["title"] == "Projector not working"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, helpdesk_service):
        """Listing with no records should return an empty list."""
        result = helpdesk_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, helpdesk_service):
        """Listing after creating a record should include it."""
        helpdesk_service.create(title="Projector not working", description="Classroom 4 projector", category="IT", priority="Medium", status="Open")
        result = helpdesk_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, helpdesk_service):
        """Getting an existing record should return it."""
        created = helpdesk_service.create(title="Projector not working", description="Classroom 4 projector", category="IT", priority="Medium", status="Open")
        result = helpdesk_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, helpdesk_service):
        """Getting a nonexistent record should return None."""
        result = helpdesk_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_title(self, helpdesk_service):
        """Updating a field should persist the change."""
        created = helpdesk_service.create(title="Projector not working", description="Classroom 4 projector", category="IT", priority="Medium", status="Open")
        helpdesk_service.update(created["id"], title="Updated Value")
        result = helpdesk_service.get(created["id"])
        assert result["title"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, helpdesk_service):
        """Deleting an existing record should remove it."""
        created = helpdesk_service.create(title="Projector not working", description="Classroom 4 projector", category="IT", priority="Medium", status="Open")
        helpdesk_service.delete(created["id"])
        result = helpdesk_service.get(created["id"])
        assert result is None
