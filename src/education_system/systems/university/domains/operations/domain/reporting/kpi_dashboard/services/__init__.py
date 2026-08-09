"""KPI dashboard services package."""
from education_system.systems.university.domains.operations.domain.reporting.kpi_dashboard.services.kpi_dashboard_service import (
    KpiDashboardService,
    KpiDashboardError,
)

__all__ = ["KpiDashboardService", "KpiDashboardError"]
