"""KPI dashboard adapter — push grade-side KPIs.

Same best-effort lookup pattern as the assignment-side
``push_assignment_kpi``: silently no-ops when no KPI with the given
name is registered.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def push_grade_kpi(metric_name: str, value: float) -> bool:
    try:
        from education_system.post_18.university_system.modules.domain.analytics.kpi_dashboard.services.kpi_dashboard_service import (
            KpiDashboardService,
        )
    except ImportError as exc:
        logger.debug("kpi_dashboard service not available: %s", exc)
        return False
    try:
        svc = KpiDashboardService()
        kpis = svc.list_kpis() or []
        target = metric_name.strip().lower()
        match = next(
            (k for k in kpis if (k.get("name") or "").strip().lower() == target),
            None,
        )
        if not match:
            logger.debug("no KPI registered for %r", metric_name)
            return False
        kpi_id = match.get("kpi_id") or match.get("id")
        if not kpi_id:
            return False
        svc.update_kpi_actual(int(kpi_id), float(value))
        return True
    except Exception as exc:
        logger.warning("push_grade_kpi(%s) failed: %s", metric_name, exc)
        return False
