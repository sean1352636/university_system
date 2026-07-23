"""Service layer for institutional analytics."""

from education_system.post_18.university_system.modules.domain.analytics.institutional_analytics.services.institutional_analytics_service import (  # noqa: E501
    InstitutionalAnalyticsError,
    InstitutionalAnalyticsService,
)

__all__ = ["InstitutionalAnalyticsService", "InstitutionalAnalyticsError"]
