"""Tests for Surveys service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, surveys_service):
        """Creating a record should return a dict with an id."""
        result = surveys_service.create(title="Parent Satisfaction Survey", target_audience="Parents", status="Active")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, surveys_service):
        """Created record should contain the provided fields."""
        result = surveys_service.create(title="Parent Satisfaction Survey", target_audience="Parents", status="Active")
        assert result["title"] == "Parent Satisfaction Survey"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, surveys_service):
        """Listing with no records should return an empty list."""
        result = surveys_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, surveys_service):
        """Listing after creating a record should include it."""
        surveys_service.create(title="Parent Satisfaction Survey", target_audience="Parents", status="Active")
        result = surveys_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, surveys_service):
        """Getting an existing record should return it."""
        created = surveys_service.create(title="Parent Satisfaction Survey", target_audience="Parents", status="Active")
        result = surveys_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, surveys_service):
        """Getting a nonexistent record should return None."""
        result = surveys_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_title(self, surveys_service):
        """Updating a field should persist the change."""
        created = surveys_service.create(title="Parent Satisfaction Survey", target_audience="Parents", status="Active")
        surveys_service.update(created["id"], title="Updated Value")
        result = surveys_service.get(created["id"])
        assert result["title"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, surveys_service):
        """Deleting an existing record should remove it."""
        created = surveys_service.create(title="Parent Satisfaction Survey", target_audience="Parents", status="Active")
        surveys_service.delete(created["id"])
        result = surveys_service.get(created["id"])
        assert result is None
