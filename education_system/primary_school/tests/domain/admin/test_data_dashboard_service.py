"""Tests for the DataDashboardService in the Primary School system."""

import pytest


class TestCreate:
    """Tests for creating dashboard KPI records."""

    def test_create_returns_id(self, data_dashboard_service):
        """Creating a KPI record returns a positive integer ID."""
        record_id = data_dashboard_service.create(
            kpi_name="Attendance Rate",
            kpi_value="96.5%",
            period="Spring 2026",
            category="Attendance",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_persists(self, data_dashboard_service):
        """Created record can be retrieved by ID."""
        record_id = data_dashboard_service.create(
            kpi_name="Progress Score",
            kpi_value="3.2",
            period="Autumn 2025",
            category="Academics",
        )
        fetched = data_dashboard_service.get(record_id)
        assert fetched is not None
        assert fetched["kpi_name"] == "Progress Score"
        assert fetched["kpi_value"] == "3.2"

    def test_create_multiple(self, data_dashboard_service):
        """Multiple records receive distinct IDs."""
        id1 = data_dashboard_service.create(kpi_name="KPI A", kpi_value="1")
        id2 = data_dashboard_service.create(kpi_name="KPI B", kpi_value="2")
        assert id1 != id2


class TestListAll:
    """Tests for listing dashboard KPI records."""

    def test_list_all_empty_db(self, data_dashboard_service):
        """Listing on an empty database returns an empty list."""
        assert data_dashboard_service.list_all() == []

    def test_list_all_returns_records(self, data_dashboard_service):
        """All created records appear in the list."""
        data_dashboard_service.create(kpi_name="D1", kpi_value="10")
        data_dashboard_service.create(kpi_name="D2", kpi_value="20")
        results = data_dashboard_service.list_all()
        assert len(results) == 2

    def test_list_all_with_filter(self, data_dashboard_service):
        """Filtering by category returns only matching records."""
        data_dashboard_service.create(
            kpi_name="X", kpi_value="1", category="Attendance",
        )
        data_dashboard_service.create(
            kpi_name="Y", kpi_value="2", category="Finance",
        )
        results = data_dashboard_service.list_all(category="Finance")
        assert len(results) == 1
        assert results[0]["kpi_name"] == "Y"


class TestGet:
    """Tests for retrieving a single KPI record."""

    def test_get_nonexistent_returns_none(self, data_dashboard_service):
        """Fetching a non-existent ID returns None."""
        assert data_dashboard_service.get(99999) is None


class TestUpdate:
    """Tests for updating dashboard KPI records."""

    def test_update_returns_true(self, data_dashboard_service):
        """Updating a record returns True."""
        record_id = data_dashboard_service.create(kpi_name="Old", kpi_value="0")
        result = data_dashboard_service.update(record_id, kpi_value="99")
        assert result is True

    def test_update_persists(self, data_dashboard_service):
        """Updated fields are reflected on retrieval."""
        record_id = data_dashboard_service.create(
            kpi_name="Original", kpi_value="5", category="Test",
        )
        data_dashboard_service.update(record_id, kpi_value="10")
        fetched = data_dashboard_service.get(record_id)
        assert fetched["kpi_value"] == "10"

    def test_update_empty_kwargs_returns_false(self, data_dashboard_service):
        """Passing no fields returns False."""
        record_id = data_dashboard_service.create(kpi_name="NoOp", kpi_value="0")
        result = data_dashboard_service.update(record_id)
        assert result is False


class TestDelete:
    """Tests for deleting dashboard KPI records."""

    def test_delete_existing(self, data_dashboard_service):
        """Deleting an existing record returns True and removes it."""
        record_id = data_dashboard_service.create(kpi_name="Gone", kpi_value="0")
        assert data_dashboard_service.delete(record_id) is True
        assert data_dashboard_service.get(record_id) is None

    def test_delete_does_not_affect_others(self, data_dashboard_service):
        """Deleting one record leaves other records intact."""
        id1 = data_dashboard_service.create(kpi_name="Keep", kpi_value="1")
        id2 = data_dashboard_service.create(kpi_name="Remove", kpi_value="2")
        data_dashboard_service.delete(id2)
        remaining = data_dashboard_service.list_all()
        assert len(remaining) == 1
        assert remaining[0]["id"] == id1
