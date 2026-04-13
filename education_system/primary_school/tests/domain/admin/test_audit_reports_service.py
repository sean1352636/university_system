"""Tests for Audit Reports service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, audit_reports_service):
        """Creating a record should return a dict with an id."""
        result = audit_reports_service.create(title="Safeguarding Audit Q1", report_type="Safeguarding", scope="Whole School", auditor="Jane Smith", status="Draft")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, audit_reports_service):
        """Created record should contain the provided fields."""
        result = audit_reports_service.create(title="Safeguarding Audit Q1", report_type="Safeguarding", scope="Whole School", auditor="Jane Smith", status="Draft")
        assert result["title"] == "Safeguarding Audit Q1"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, audit_reports_service):
        """Listing with no records should return an empty list."""
        result = audit_reports_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, audit_reports_service):
        """Listing after creating a record should include it."""
        audit_reports_service.create(title="Safeguarding Audit Q1", report_type="Safeguarding", scope="Whole School", auditor="Jane Smith", status="Draft")
        result = audit_reports_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, audit_reports_service):
        """Getting an existing record should return it."""
        created = audit_reports_service.create(title="Safeguarding Audit Q1", report_type="Safeguarding", scope="Whole School", auditor="Jane Smith", status="Draft")
        result = audit_reports_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, audit_reports_service):
        """Getting a nonexistent record should return None."""
        result = audit_reports_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_title(self, audit_reports_service):
        """Updating a field should persist the change."""
        created = audit_reports_service.create(title="Safeguarding Audit Q1", report_type="Safeguarding", scope="Whole School", auditor="Jane Smith", status="Draft")
        audit_reports_service.update(created["id"], title="Updated Value")
        result = audit_reports_service.get(created["id"])
        assert result["title"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, audit_reports_service):
        """Deleting an existing record should remove it."""
        created = audit_reports_service.create(title="Safeguarding Audit Q1", report_type="Safeguarding", scope="Whole School", auditor="Jane Smith", status="Draft")
        audit_reports_service.delete(created["id"])
        result = audit_reports_service.get(created["id"])
        assert result is None
