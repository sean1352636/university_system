"""Typed outcomes for university application-service boundaries.

Expected operational failures should be returned explicitly instead of being
hidden by a broad ``except Exception``. Unexpected programming errors should
still raise and be captured by the platform error boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Generic, Mapping, TypeVar

from education_system.systems.university.infrastructure.exceptions import (
    UniversitySystemError,
)

T = TypeVar("T")


class OperationStatus(StrEnum):
    """Externally observable state of an application operation."""

    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    RETRYING = "retrying"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class OperationalIssue:
    """Machine-readable failure or degradation detail."""

    code: str
    message: str
    retryable: bool = False
    component: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_exception(
        cls,
        error: Exception,
        *,
        component: str | None = None,
        retryable: bool = False,
    ) -> "OperationalIssue":
        if isinstance(error, UniversitySystemError):
            return cls(
                code=error.code or error.__class__.__name__,
                message=error.message,
                retryable=retryable,
                component=component,
                details=error.details,
            )
        return cls(
            code=error.__class__.__name__,
            message=str(error),
            retryable=retryable,
            component=component,
        )


@dataclass(frozen=True, slots=True)
class OperationResult(Generic[T]):
    """Result returned across API, worker and integration boundaries."""

    status: OperationStatus
    value: T | None = None
    issues: tuple[OperationalIssue, ...] = ()
    correlation_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def ok(self) -> bool:
        return self.status is OperationStatus.SUCCEEDED

    @property
    def retryable(self) -> bool:
        return any(issue.retryable for issue in self.issues)

    @classmethod
    def success(
        cls, value: T, *, correlation_id: str | None = None
    ) -> "OperationResult[T]":
        return cls(
            status=OperationStatus.SUCCEEDED,
            value=value,
            correlation_id=correlation_id,
        )

    @classmethod
    def degraded(
        cls,
        value: T,
        *issues: OperationalIssue,
        correlation_id: str | None = None,
    ) -> "OperationResult[T]":
        if not issues:
            raise ValueError("A degraded result requires at least one issue")
        return cls(
            status=OperationStatus.DEGRADED,
            value=value,
            issues=tuple(issues),
            correlation_id=correlation_id,
        )

    @classmethod
    def failure(
        cls,
        *issues: OperationalIssue,
        correlation_id: str | None = None,
    ) -> "OperationResult[T]":
        if not issues:
            raise ValueError("A failed result requires at least one issue")
        status = (
            OperationStatus.RETRYING
            if any(issue.retryable for issue in issues)
            else OperationStatus.FAILED
        )
        return cls(
            status=status,
            issues=tuple(issues),
            correlation_id=correlation_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "ok": self.ok,
            "retryable": self.retryable,
            "value": self.value,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "retryable": issue.retryable,
                    "component": issue.component,
                    "details": dict(issue.details),
                }
                for issue in self.issues
            ],
            "correlation_id": self.correlation_id,
            "occurred_at": self.occurred_at.isoformat(),
        }


class OperationalFailure(UniversitySystemError):
    """Raised when a boundary cannot return a structured result."""

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        context = dict(details or {})
        context.update(operation=operation, retryable=retryable)
        super().__init__(
            message,
            code="OPERATIONAL_FAILURE",
            details=context,
        )


class EventDeliveryError(OperationalFailure):
    """An important event could not be durably accepted or delivered."""

    def __init__(
        self,
        message: str,
        *,
        operation: str = "event_delivery",
        retryable: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            operation=operation,
            retryable=retryable,
            details=details,
        )


__all__ = [
    "EventDeliveryError",
    "OperationResult",
    "OperationStatus",
    "OperationalFailure",
    "OperationalIssue",
]
