"""Tests for Self-Assessment service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, self_assessment_service):
        """Creating a record should return a dict with an id."""
        result = self_assessment_service.create(academic_year="2025/26", area="Quality of Education", ofsted_grade="Good", status="Draft")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, self_assessment_service):
        """Created record should contain the provided fields."""
        result = self_assessment_service.create(academic_year="2025/26", area="Quality of Education", ofsted_grade="Good", status="Draft")
        assert result["academic_year"] == "2025/26"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, self_assessment_service):
        """Listing with no records should return an empty list."""
        result = self_assessment_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, self_assessment_service):
        """Listing after creating a record should include it."""
        self_assessment_service.create(academic_year="2025/26", area="Quality of Education", ofsted_grade="Good", status="Draft")
        result = self_assessment_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, self_assessment_service):
        """Getting an existing record should return it."""
        created = self_assessment_service.create(academic_year="2025/26", area="Quality of Education", ofsted_grade="Good", status="Draft")
        result = self_assessment_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, self_assessment_service):
        """Getting a nonexistent record should return None."""
        result = self_assessment_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_academic_year(self, self_assessment_service):
        """Updating a field should persist the change."""
        created = self_assessment_service.create(academic_year="2025/26", area="Quality of Education", ofsted_grade="Good", status="Draft")
        self_assessment_service.update(created["id"], academic_year="Updated Value")
        result = self_assessment_service.get(created["id"])
        assert result["academic_year"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, self_assessment_service):
        """Deleting an existing record should remove it."""
        created = self_assessment_service.create(academic_year="2025/26", area="Quality of Education", ofsted_grade="Good", status="Draft")
        self_assessment_service.delete(created["id"])
        result = self_assessment_service.get(created["id"])
        assert result is None
