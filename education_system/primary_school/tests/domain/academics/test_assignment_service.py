"""Tests for Assignment service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, assignment_service):
        """Creating a record should return a dict with an id."""
        result = assignment_service.create_assignment(title="Maths HW 1", description="Fractions worksheet", due_date="2026-01-15")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, assignment_service):
        """Created record should contain the provided fields."""
        result = assignment_service.create_assignment(title="Maths HW 1", description="Fractions worksheet", due_date="2026-01-15")
        assert result["title"] == "Maths HW 1"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, assignment_service):
        """Listing with no records should return an empty list."""
        result = assignment_service.list_assignments()
        assert isinstance(result, list)

    def test_list_after_create(self, assignment_service):
        """Listing after creating a record should include it."""
        assignment_service.create_assignment(title="Maths HW 1", description="Fractions worksheet", due_date="2026-01-15")
        result = assignment_service.list_assignments()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, assignment_service):
        """Getting an existing record should return it."""
        created = assignment_service.create_assignment(title="Maths HW 1", description="Fractions worksheet", due_date="2026-01-15")
        result = assignment_service.get_assignment(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, assignment_service):
        """Getting a nonexistent record should return None."""
        result = assignment_service.get_assignment(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_title(self, assignment_service):
        """Updating a field should persist the change."""
        created = assignment_service.create_assignment(title="Maths HW 1", description="Fractions worksheet", due_date="2026-01-15")
        assignment_service.update_assignment(created["id"], title="Updated Value")
        result = assignment_service.get_assignment(created["id"])
        assert result["title"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, assignment_service):
        """Deleting an existing record should remove it."""
        created = assignment_service.create_assignment(title="Maths HW 1", description="Fractions worksheet", due_date="2026-01-15")
        assignment_service.delete_assignment(created["id"])
        result = assignment_service.get_assignment(created["id"])
        assert result is None
