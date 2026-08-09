"""Typed failures exposed by critical university operation boundaries."""

from __future__ import annotations

from typing import Any

from education_system.systems.university.infrastructure.exceptions import (
    UniversitySystemError,
)


class BoundaryError(UniversitySystemError, ValueError):
    """Base class for expected, machine-identifiable boundary failures."""

    default_code = "BOUNDARY_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code or self.default_code, details=details)


class AdmissionsBoundaryError(BoundaryError):
    default_code = "ADMISSIONS_OPERATION_FAILED"


class EnrolmentBoundaryError(BoundaryError):
    default_code = "ENROLMENT_OPERATION_FAILED"


class FinanceBoundaryError(BoundaryError):
    default_code = "FINANCE_OPERATION_FAILED"


class SafeguardingBoundaryError(BoundaryError):
    default_code = "SAFEGUARDING_OPERATION_FAILED"


class ExportBoundaryError(BoundaryError):
    default_code = "EXPORT_OPERATION_FAILED"


__all__ = [
    "AdmissionsBoundaryError",
    "BoundaryError",
    "EnrolmentBoundaryError",
    "ExportBoundaryError",
    "FinanceBoundaryError",
    "SafeguardingBoundaryError",
]
