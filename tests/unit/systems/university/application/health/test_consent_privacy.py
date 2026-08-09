from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from education_system.systems.university.application.health.consent import (
    HealthConsent,
    HealthConsentRequiredError,
    HealthConsentService,
)
from education_system.systems.university.application.health.privacy import (
    HealthAccessDeniedError,
    HealthAccessRequest,
    HealthPrivacyService,
)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    grant_id: str | None = None


def test_consent_service_accepts_matching_active_consent():
    consent = HealthConsent.grant(
        subject_id="student-1",
        purposes={"direct_care"},
        granted_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    assert (
        HealthConsentService().require(
            consent, subject_id="student-1", purpose="direct_care"
        )
        is consent
    )


def test_consent_service_rejects_wrong_purpose():
    consent = HealthConsent.grant(
        subject_id="student-1", purposes={"student_request"}
    )

    with pytest.raises(HealthConsentRequiredError):
        HealthConsentService().require(
            consent, subject_id="student-1", purpose="direct_care"
        )


def test_privacy_service_passes_explicit_health_context():
    calls = []

    def authorize(**kwargs):
        calls.append(kwargs)
        return Decision(True, "allowed")

    request = HealthAccessRequest.create(
        actor_id="clinician-1",
        actor_role="clinician",
        subject_id="student-1",
        fields={"diagnosis", "care_plan"},
        purpose="direct_care",
    )

    decision = HealthPrivacyService(authorize, db_path="/tmp/auth.db").require(request)

    assert decision.allowed
    assert calls == [
        {
            "actor_id": "clinician-1",
            "actor_role": "clinician",
            "domain": "health",
            "subject_id": "student-1",
            "fields": frozenset({"diagnosis", "care_plan"}),
            "purpose": "direct_care",
            "db_path": "/tmp/auth.db",
        }
    ]


def test_privacy_service_raises_on_denial():
    service = HealthPrivacyService(
        lambda **_kwargs: Decision(False, "purpose not permitted")
    )
    request = HealthAccessRequest.create(
        actor_id="student-1",
        actor_role="student",
        subject_id="student-1",
        fields={"diagnosis"},
        purpose="student_request",
    )

    with pytest.raises(HealthAccessDeniedError, match="purpose not permitted"):
        service.require(request)
