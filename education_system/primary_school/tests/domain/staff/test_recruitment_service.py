"""Tests for Recruitment service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, recruitment_service):
        """Creating a record should return a dict with an id."""
        result = recruitment_service.create(title="Year 3 Class Teacher", role_type="Teaching", closing_date="2026-03-01", status="Open")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, recruitment_service):
        """Created record should contain the provided fields."""
        result = recruitment_service.create(title="Year 3 Class Teacher", role_type="Teaching", closing_date="2026-03-01", status="Open")
        assert result["title"] == "Year 3 Class Teacher"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, recruitment_service):
        """Listing with no records should return an empty list."""
        result = recruitment_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, recruitment_service):
        """Listing after creating a record should include it."""
        recruitment_service.create(title="Year 3 Class Teacher", role_type="Teaching", closing_date="2026-03-01", status="Open")
        result = recruitment_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, recruitment_service):
        """Getting an existing record should return it."""
        created = recruitment_service.create(title="Year 3 Class Teacher", role_type="Teaching", closing_date="2026-03-01", status="Open")
        result = recruitment_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, recruitment_service):
        """Getting a nonexistent record should return None."""
        result = recruitment_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_title(self, recruitment_service):
        """Updating a field should persist the change."""
        created = recruitment_service.create(title="Year 3 Class Teacher", role_type="Teaching", closing_date="2026-03-01", status="Open")
        recruitment_service.update(created["id"], title="Updated Value")
        result = recruitment_service.get(created["id"])
        assert result["title"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, recruitment_service):
        """Deleting an existing record should remove it."""
        created = recruitment_service.create(title="Year 3 Class Teacher", role_type="Teaching", closing_date="2026-03-01", status="Open")
        recruitment_service.delete(created["id"])
        result = recruitment_service.get(created["id"])
        assert result is None
