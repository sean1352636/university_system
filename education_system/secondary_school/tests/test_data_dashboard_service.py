"""Tests for DataDashboardService."""
import pytest
from education_system.secondary_school.modules.domain.admin.data_dashboard.services.data_dashboard_service import DataDashboardService


@pytest.fixture
def data_dashboard_service(db_path):
    return DataDashboardService(db_path)


class TestDataDashboardCRUD:
    def test_create(self, data_dashboard_service):
        r = data_dashboard_service.create(kpi_name="Attendance Rate", kpi_value="94.5",
                                           period="Spring 2026", category="attendance")
        assert r["kpi_name"] == "Attendance Rate"
        assert r["kpi_value"] == "94.5"
        assert r["period"] == "Spring 2026"

    def test_list_all(self, data_dashboard_service):
        data_dashboard_service.create(kpi_name="Attendance Rate", kpi_value="94.5")
        data_dashboard_service.create(kpi_name="Pass Rate", kpi_value="87.0")
        result = data_dashboard_service.list_all()
        assert len(result) >= 2

    def test_get(self, data_dashboard_service):
        r = data_dashboard_service.create(kpi_name="Attendance Rate", kpi_value="94.5",
                                           period="Spring 2026")
        found = data_dashboard_service.get(r["id"])
        assert found is not None
        assert found["kpi_name"] == "Attendance Rate"
        assert found["kpi_value"] == "94.5"

    def test_update(self, data_dashboard_service):
        r = data_dashboard_service.create(kpi_name="Attendance Rate", kpi_value="94.5")
        updated = data_dashboard_service.update(r["id"], kpi_value="95.2")
        assert updated["kpi_value"] == "95.2"

    def test_delete(self, data_dashboard_service):
        r = data_dashboard_service.create(kpi_name="Attendance Rate", kpi_value="94.5")
        data_dashboard_service.delete(r["id"])
        assert data_dashboard_service.get(r["id"]) is None
