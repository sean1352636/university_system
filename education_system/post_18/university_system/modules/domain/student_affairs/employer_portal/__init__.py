"""Employer-facing portal layered on top of internship_management."""
from education_system.post_18.university_system.modules.domain.student_affairs.employer_portal.services.employer_portal_service import (
    EmployerPortalService,
    EmployerPortalError,
)

__all__ = ["EmployerPortalService", "EmployerPortalError"]
