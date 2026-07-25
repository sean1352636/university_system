"""Institutional analytics — cross-module aggregate metrics.

Unlike ``kpi_dashboard`` (which reads pre-recorded KPIs from the
``analytics_bi`` tables), this sub-module *computes* institutional
analytics on demand from the operational data already held in
``student_records.db``: enrolment, retention, module performance,
course capacity and finance.

All reads are non-destructive aggregate queries — no DDL, no writes.
"""

from education_system.systems.university.domain.operations.reporting.institutional_analytics.services.institutional_analytics_service import (  # noqa: E501
    InstitutionalAnalyticsError,
    InstitutionalAnalyticsService,
)

__all__ = ["InstitutionalAnalyticsService", "InstitutionalAnalyticsError"]
