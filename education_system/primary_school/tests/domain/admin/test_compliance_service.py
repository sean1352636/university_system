"""Tests for Compliance service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, compliance_service):
        """Creating a record should return a dict with an id."""
        result = compliance_service.create(area="Health & Safety", requirement="Fire extinguisher check", responsible_person="Site Manager", status="Compliant")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, compliance_service):
        """Created record should contain the provided fields."""
        result = compliance_service.create(area="Health & Safety", requirement="Fire extinguisher check", responsible_person="Site Manager", status="Compliant")
        assert result["area"] == "Health & Safety"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, compliance_service):
        """Listing with no records should return an empty list."""
        result = compliance_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, compliance_service):
        """Listing after creating a record should include it."""
        compliance_service.create(area="Health & Safety", requirement="Fire extinguisher check", responsible_person="Site Manager", status="Compliant")
        result = compliance_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, compliance_service):
        """Getting an existing record should return it."""
        created = compliance_service.create(area="Health & Safety", requirement="Fire extinguisher check", responsible_person="Site Manager", status="Compliant")
        result = compliance_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, compliance_service):
        """Getting a nonexistent record should return None."""
        result = compliance_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_area(self, compliance_service):
        """Updating a field should persist the change."""
        created = compliance_service.create(area="Health & Safety", requirement="Fire extinguisher check", responsible_person="Site Manager", status="Compliant")
        compliance_service.update(created["id"], area="Updated Value")
        result = compliance_service.get(created["id"])
        assert result["area"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, compliance_service):
        """Deleting an existing record should remove it."""
        created = compliance_service.create(area="Health & Safety", requirement="Fire extinguisher check", responsible_person="Site Manager", status="Compliant")
        compliance_service.delete(created["id"])
        result = compliance_service.get(created["id"])
        assert result is None
