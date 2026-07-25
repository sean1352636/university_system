"""Service layer for institutional analytics."""

from education_system.systems.university.domain.operations.reporting.institutional_analytics.services.institutional_analytics_service import (  # noqa: E501
    InstitutionalAnalyticsError,
    InstitutionalAnalyticsService,
)

__all__ = ["InstitutionalAnalyticsService", "InstitutionalAnalyticsError"]
