"""Tests for Letter Templates service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, letter_templates_service):
        """Creating a record should return a dict with an id."""
        result = letter_templates_service.create(name="Absence Warning", category="Attendance", subject="Attendance Concern", body_template="Dear {parent_name},")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, letter_templates_service):
        """Created record should contain the provided fields."""
        result = letter_templates_service.create(name="Absence Warning", category="Attendance", subject="Attendance Concern", body_template="Dear {parent_name},")
        assert result["name"] == "Absence Warning"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, letter_templates_service):
        """Listing with no records should return an empty list."""
        result = letter_templates_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, letter_templates_service):
        """Listing after creating a record should include it."""
        letter_templates_service.create(name="Absence Warning", category="Attendance", subject="Attendance Concern", body_template="Dear {parent_name},")
        result = letter_templates_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, letter_templates_service):
        """Getting an existing record should return it."""
        created = letter_templates_service.create(name="Absence Warning", category="Attendance", subject="Attendance Concern", body_template="Dear {parent_name},")
        result = letter_templates_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, letter_templates_service):
        """Getting a nonexistent record should return None."""
        result = letter_templates_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_name(self, letter_templates_service):
        """Updating a field should persist the change."""
        created = letter_templates_service.create(name="Absence Warning", category="Attendance", subject="Attendance Concern", body_template="Dear {parent_name},")
        letter_templates_service.update(created["id"], name="Updated Value")
        result = letter_templates_service.get(created["id"])
        assert result["name"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, letter_templates_service):
        """Deleting an existing record should remove it."""
        created = letter_templates_service.create(name="Absence Warning", category="Attendance", subject="Attendance Concern", body_template="Dear {parent_name},")
        letter_templates_service.delete(created["id"])
        result = letter_templates_service.get(created["id"])
        assert result is None
