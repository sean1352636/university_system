"""Tests for KPIDashboardService."""

import pytest
from education_system.college_system.core.exceptions import KPIDashboardError, ValidationError


class TestKPIDashboardService:
    """Test suite for KPIDashboardService."""

    def test_create_target(self, kpi_dashboard_service):
        item = kpi_dashboard_service.create_target(academic_year="test_academic_year", kpi_name="test_kpi_name")
        assert item["id"] is not None

    def test_get_target(self, kpi_dashboard_service):
        item = kpi_dashboard_service.create_target(academic_year="test_academic_year", kpi_name="test_kpi_name")
        found = kpi_dashboard_service.get_target(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_targets(self, kpi_dashboard_service):
        kpi_dashboard_service.create_target(academic_year="test_academic_year", kpi_name="test_kpi_name")
        items = kpi_dashboard_service.list_targets()
        assert len(items) >= 1

    def test_update_target(self, kpi_dashboard_service):
        item = kpi_dashboard_service.create_target(academic_year="test_academic_year", kpi_name="test_kpi_name")
        updated = kpi_dashboard_service.update_target(item["id"], academic_year="updated_value")
        assert updated["academic_year"] == "updated_value"

    def test_delete_target(self, kpi_dashboard_service):
        item = kpi_dashboard_service.create_target(academic_year="test_academic_year", kpi_name="test_kpi_name")
        result = kpi_dashboard_service.delete_target(item["id"])
        assert result is True
        assert kpi_dashboard_service.get_target(item["id"]) is None

    def test_count_targets(self, kpi_dashboard_service):
        kpi_dashboard_service.create_target(academic_year="test_academic_year", kpi_name="test_kpi_name")
        count = kpi_dashboard_service.count_targets()
        assert count >= 1

    def test_delete_nonexistent_raises(self, kpi_dashboard_service):
        with pytest.raises(KPIDashboardError):
            kpi_dashboard_service.delete_target(99999)
