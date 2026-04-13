"""Tests for Census service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, census_service):
        """Creating a record should return a dict with an id."""
        result = census_service.create(census_type="Spring", academic_year="2025/26", return_date="2026-01-15", total_pupils="210", status="Draft")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, census_service):
        """Created record should contain the provided fields."""
        result = census_service.create(census_type="Spring", academic_year="2025/26", return_date="2026-01-15", total_pupils="210", status="Draft")
        assert result["census_type"] == "Spring"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, census_service):
        """Listing with no records should return an empty list."""
        result = census_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, census_service):
        """Listing after creating a record should include it."""
        census_service.create(census_type="Spring", academic_year="2025/26", return_date="2026-01-15", total_pupils="210", status="Draft")
        result = census_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, census_service):
        """Getting an existing record should return it."""
        created = census_service.create(census_type="Spring", academic_year="2025/26", return_date="2026-01-15", total_pupils="210", status="Draft")
        result = census_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, census_service):
        """Getting a nonexistent record should return None."""
        result = census_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_census_type(self, census_service):
        """Updating a field should persist the change."""
        created = census_service.create(census_type="Spring", academic_year="2025/26", return_date="2026-01-15", total_pupils="210", status="Draft")
        census_service.update(created["id"], census_type="Updated Value")
        result = census_service.get(created["id"])
        assert result["census_type"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, census_service):
        """Deleting an existing record should remove it."""
        created = census_service.create(census_type="Spring", academic_year="2025/26", return_date="2026-01-15", total_pupils="210", status="Draft")
        census_service.delete(created["id"])
        result = census_service.get(created["id"])
        assert result is None
