"""KPI dashboard services package."""
from education_system.systems.university.domain.operations.reporting.kpi_dashboard.services.kpi_dashboard_service import (
    KpiDashboardService,
    KpiDashboardError,
)

__all__ = ["KpiDashboardService", "KpiDashboardError"]
