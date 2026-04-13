"""Tests for First Aid service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, first_aid_service):
        """Creating a record should return a dict with an id."""
        result = first_aid_service.create(patient_name="Oliver Smith", patient_type="Pupil", incident_date="2026-01-10", location="Playground", description="Grazed knee", treatment_given="Cleaned and plaster applied")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, first_aid_service):
        """Created record should contain the provided fields."""
        result = first_aid_service.create(patient_name="Oliver Smith", patient_type="Pupil", incident_date="2026-01-10", location="Playground", description="Grazed knee", treatment_given="Cleaned and plaster applied")
        assert result["patient_name"] == "Oliver Smith"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, first_aid_service):
        """Listing with no records should return an empty list."""
        result = first_aid_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, first_aid_service):
        """Listing after creating a record should include it."""
        first_aid_service.create(patient_name="Oliver Smith", patient_type="Pupil", incident_date="2026-01-10", location="Playground", description="Grazed knee", treatment_given="Cleaned and plaster applied")
        result = first_aid_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, first_aid_service):
        """Getting an existing record should return it."""
        created = first_aid_service.create(patient_name="Oliver Smith", patient_type="Pupil", incident_date="2026-01-10", location="Playground", description="Grazed knee", treatment_given="Cleaned and plaster applied")
        result = first_aid_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, first_aid_service):
        """Getting a nonexistent record should return None."""
        result = first_aid_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_patient_name(self, first_aid_service):
        """Updating a field should persist the change."""
        created = first_aid_service.create(patient_name="Oliver Smith", patient_type="Pupil", incident_date="2026-01-10", location="Playground", description="Grazed knee", treatment_given="Cleaned and plaster applied")
        first_aid_service.update(created["id"], patient_name="Updated Value")
        result = first_aid_service.get(created["id"])
        assert result["patient_name"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, first_aid_service):
        """Deleting an existing record should remove it."""
        created = first_aid_service.create(patient_name="Oliver Smith", patient_type="Pupil", incident_date="2026-01-10", location="Playground", description="Grazed knee", treatment_given="Cleaned and plaster applied")
        first_aid_service.delete(created["id"])
        result = first_aid_service.get(created["id"])
        assert result is None
