"""Employer-facing portal layered on top of internship_management."""
from education_system.systems.university.domains.progression.domain.employer_portal.services.employer_portal_service import (
    EmployerPortalService,
    EmployerPortalError,
)

__all__ = ["EmployerPortalService", "EmployerPortalError"]
