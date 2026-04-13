"""Tests for Quality Assurance service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, quality_assurance_service):
        """Creating a record should return a dict with an id."""
        result = quality_assurance_service.create(review_type="Learning Walk", subject_area="Mathematics", reviewer="Head Teacher", rating="Good")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, quality_assurance_service):
        """Created record should contain the provided fields."""
        result = quality_assurance_service.create(review_type="Learning Walk", subject_area="Mathematics", reviewer="Head Teacher", rating="Good")
        assert result["review_type"] == "Learning Walk"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, quality_assurance_service):
        """Listing with no records should return an empty list."""
        result = quality_assurance_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, quality_assurance_service):
        """Listing after creating a record should include it."""
        quality_assurance_service.create(review_type="Learning Walk", subject_area="Mathematics", reviewer="Head Teacher", rating="Good")
        result = quality_assurance_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, quality_assurance_service):
        """Getting an existing record should return it."""
        created = quality_assurance_service.create(review_type="Learning Walk", subject_area="Mathematics", reviewer="Head Teacher", rating="Good")
        result = quality_assurance_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, quality_assurance_service):
        """Getting a nonexistent record should return None."""
        result = quality_assurance_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_review_type(self, quality_assurance_service):
        """Updating a field should persist the change."""
        created = quality_assurance_service.create(review_type="Learning Walk", subject_area="Mathematics", reviewer="Head Teacher", rating="Good")
        quality_assurance_service.update(created["id"], review_type="Updated Value")
        result = quality_assurance_service.get(created["id"])
        assert result["review_type"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, quality_assurance_service):
        """Deleting an existing record should remove it."""
        created = quality_assurance_service.create(review_type="Learning Walk", subject_area="Mathematics", reviewer="Head Teacher", rating="Good")
        quality_assurance_service.delete(created["id"])
        result = quality_assurance_service.get(created["id"])
        assert result is None
