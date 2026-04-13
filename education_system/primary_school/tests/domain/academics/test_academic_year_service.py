"""Tests for Academic Year service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, academic_year_service):
        """Creating a record should return a dict with an id."""
        result = academic_year_service.create_year(name="2025/26", start_date="2025-09-01", end_date="2026-07-20")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, academic_year_service):
        """Created record should contain the provided fields."""
        result = academic_year_service.create_year(name="2025/26", start_date="2025-09-01", end_date="2026-07-20")
        assert result["name"] == "2025/26"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, academic_year_service):
        """Listing with no records should return an empty list."""
        result = academic_year_service.list_years()
        assert isinstance(result, list)

    def test_list_after_create(self, academic_year_service):
        """Listing after creating a record should include it."""
        academic_year_service.create_year(name="2025/26", start_date="2025-09-01", end_date="2026-07-20")
        result = academic_year_service.list_years()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, academic_year_service):
        """Getting an existing record should return it."""
        created = academic_year_service.create_year(name="2025/26", start_date="2025-09-01", end_date="2026-07-20")
        result = academic_year_service.get_year(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, academic_year_service):
        """Getting a nonexistent record should return None."""
        result = academic_year_service.get_year(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_name(self, academic_year_service):
        """Updating a field should persist the change."""
        created = academic_year_service.create_year(name="2025/26", start_date="2025-09-01", end_date="2026-07-20")
        academic_year_service.update_year(created["id"], name="Updated Value")
        result = academic_year_service.get_year(created["id"])
        assert result["name"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, academic_year_service):
        """Deleting an existing record should remove it."""
        created = academic_year_service.create_year(name="2025/26", start_date="2025-09-01", end_date="2026-07-20")
        academic_year_service.delete_year(created["id"])
        result = academic_year_service.get_year(created["id"])
        assert result is None
