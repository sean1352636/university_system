"""Application boundary for purpose-bound access to health information."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol


class HealthAccessDeniedError(PermissionError):
    """Raised when health information is requested without an adequate grant."""


class AccessDecisionLike(Protocol):
    allowed: bool
    reason: str
    grant_id: str | None


SensitiveFieldAuthorizer = Callable[..., AccessDecisionLike]


@dataclass(frozen=True, slots=True)
class HealthAccessRequest:
    actor_id: str
    actor_role: str
    subject_id: str | None
    fields: frozenset[str]
    purpose: str

    @classmethod
    def create(
        cls,
        *,
        actor_id: str,
        actor_role: str,
        subject_id: str | None,
        fields: Iterable[str],
        purpose: str,
    ) -> "HealthAccessRequest":
        return cls(
            actor_id=actor_id,
            actor_role=actor_role,
            subject_id=subject_id,
            fields=frozenset(fields),
            purpose=purpose,
        )


class HealthPrivacyService:
    """Authorize health fields without coupling callers to platform storage."""

    def __init__(
        self,
        authorizer: SensitiveFieldAuthorizer,
        *,
        db_path: str | None = None,
    ) -> None:
        self._authorizer = authorizer
        self._db_path = db_path

    def authorize(self, request: HealthAccessRequest) -> AccessDecisionLike:
        return self._authorizer(
            actor_id=request.actor_id,
            actor_role=request.actor_role,
            domain="health",
            subject_id=request.subject_id,
            fields=request.fields,
            purpose=request.purpose,
            db_path=self._db_path,
        )

    def require(self, request: HealthAccessRequest) -> AccessDecisionLike:
        decision = self.authorize(request)
        if not decision.allowed:
            raise HealthAccessDeniedError(decision.reason)
        return decision


def platform_health_privacy_service(
    *, db_path: str | None = None
) -> HealthPrivacyService:
    """Compose the health application with the shared platform policy."""
    from education_system.platform.governance.security.sensitive_access import (
        authorize_sensitive_fields,
    )

    return HealthPrivacyService(authorize_sensitive_fields, db_path=db_path)


__all__ = [
    "HealthAccessDeniedError",
    "HealthAccessRequest",
    "HealthPrivacyService",
    "platform_health_privacy_service",
]
