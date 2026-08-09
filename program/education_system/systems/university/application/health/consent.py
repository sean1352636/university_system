"""Consent decisions used by health application workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable


class HealthConsentRequiredError(PermissionError):
    """Raised when no active consent covers the requested health purpose."""


@dataclass(frozen=True, slots=True)
class HealthConsent:
    subject_id: str
    purposes: frozenset[str]
    granted_at: datetime
    withdrawn_at: datetime | None = None

    @classmethod
    def grant(
        cls,
        *,
        subject_id: str,
        purposes: Iterable[str],
        granted_at: datetime | None = None,
    ) -> "HealthConsent":
        normalized = frozenset(purpose.strip() for purpose in purposes if purpose.strip())
        if not normalized:
            raise ValueError("Consent must cover at least one purpose")
        return cls(
            subject_id=subject_id,
            purposes=normalized,
            granted_at=granted_at or datetime.now(UTC),
        )

    def covers(self, purpose: str, *, at: datetime | None = None) -> bool:
        checked_at = at or datetime.now(UTC)
        return (
            purpose in self.purposes
            and self.granted_at <= checked_at
            and (self.withdrawn_at is None or checked_at < self.withdrawn_at)
        )


class HealthConsentService:
    """Enforce consent independently of CLI and persistence concerns."""

    def require(
        self,
        consent: HealthConsent | None,
        *,
        subject_id: str,
        purpose: str,
        at: datetime | None = None,
    ) -> HealthConsent:
        if (
            consent is None
            or consent.subject_id != subject_id
            or not consent.covers(purpose, at=at)
        ):
            raise HealthConsentRequiredError(
                f"Active consent is required for health purpose {purpose!r}"
            )
        return consent


__all__ = [
    "HealthConsent",
    "HealthConsentRequiredError",
    "HealthConsentService",
]
