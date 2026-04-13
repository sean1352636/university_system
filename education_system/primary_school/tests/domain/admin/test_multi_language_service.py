"""Tests for Multi-Language service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, multi_language_service):
        """Creating a record should return a dict with an id."""
        result = multi_language_service.create(language_code="cy", translation_key="welcome_message", translation_value="Croeso")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, multi_language_service):
        """Created record should contain the provided fields."""
        result = multi_language_service.create(language_code="cy", translation_key="welcome_message", translation_value="Croeso")
        assert result["language_code"] == "cy"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, multi_language_service):
        """Listing with no records should return an empty list."""
        result = multi_language_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, multi_language_service):
        """Listing after creating a record should include it."""
        multi_language_service.create(language_code="cy", translation_key="welcome_message", translation_value="Croeso")
        result = multi_language_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, multi_language_service):
        """Getting an existing record should return it."""
        created = multi_language_service.create(language_code="cy", translation_key="welcome_message", translation_value="Croeso")
        result = multi_language_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, multi_language_service):
        """Getting a nonexistent record should return None."""
        result = multi_language_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_language_code(self, multi_language_service):
        """Updating a field should persist the change."""
        created = multi_language_service.create(language_code="cy", translation_key="welcome_message", translation_value="Croeso")
        multi_language_service.update(created["id"], language_code="Updated Value")
        result = multi_language_service.get(created["id"])
        assert result["language_code"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, multi_language_service):
        """Deleting an existing record should remove it."""
        created = multi_language_service.create(language_code="cy", translation_key="welcome_message", translation_value="Croeso")
        multi_language_service.delete(created["id"])
        result = multi_language_service.get(created["id"])
        assert result is None
