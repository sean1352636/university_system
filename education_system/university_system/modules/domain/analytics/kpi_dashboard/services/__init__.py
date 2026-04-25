"""KPI dashboard services package."""
from education_system.university_system.modules.domain.analytics.kpi_dashboard.services.kpi_dashboard_service import (
    KpiDashboardService,
    KpiDashboardError,
)

__all__ = ["KpiDashboardService", "KpiDashboardError"]
