"""Tests for KPI Dashboard service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, kpi_dashboard_service):
        """Creating a record should return a dict with an id."""
        result = kpi_dashboard_service.create(metric_name="Attendance Rate", category="Attendance", current_value="96.5", target_value="97.0", unit="%")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, kpi_dashboard_service):
        """Created record should contain the provided fields."""
        result = kpi_dashboard_service.create(metric_name="Attendance Rate", category="Attendance", current_value="96.5", target_value="97.0", unit="%")
        assert result["metric_name"] == "Attendance Rate"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, kpi_dashboard_service):
        """Listing with no records should return an empty list."""
        result = kpi_dashboard_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, kpi_dashboard_service):
        """Listing after creating a record should include it."""
        kpi_dashboard_service.create(metric_name="Attendance Rate", category="Attendance", current_value="96.5", target_value="97.0", unit="%")
        result = kpi_dashboard_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, kpi_dashboard_service):
        """Getting an existing record should return it."""
        created = kpi_dashboard_service.create(metric_name="Attendance Rate", category="Attendance", current_value="96.5", target_value="97.0", unit="%")
        result = kpi_dashboard_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, kpi_dashboard_service):
        """Getting a nonexistent record should return None."""
        result = kpi_dashboard_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_metric_name(self, kpi_dashboard_service):
        """Updating a field should persist the change."""
        created = kpi_dashboard_service.create(metric_name="Attendance Rate", category="Attendance", current_value="96.5", target_value="97.0", unit="%")
        kpi_dashboard_service.update(created["id"], metric_name="Updated Value")
        result = kpi_dashboard_service.get(created["id"])
        assert result["metric_name"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, kpi_dashboard_service):
        """Deleting an existing record should remove it."""
        created = kpi_dashboard_service.create(metric_name="Attendance Rate", category="Attendance", current_value="96.5", target_value="97.0", unit="%")
        kpi_dashboard_service.delete(created["id"])
        result = kpi_dashboard_service.get(created["id"])
        assert result is None
