"""Employer-facing portal layered on top of internship_management."""
from education_system.systems.university.domain.progression.employer_portal.services.employer_portal_service import (
    EmployerPortalService,
    EmployerPortalError,
)

__all__ = ["EmployerPortalService", "EmployerPortalError"]
