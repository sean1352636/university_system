"""Where an applicant has got to inside admissions.

Application → Offer → Enrolment. These are stages of the admissions
decision, not apprentice statuses: the person stays 'Applicant' until
they are accepted onto programme, so nothing that keys off the lifecycle
— funding, the cohort, the dashboards — has to know about them.

An offer can be amended while it stands. Enrolment follows an offer.
Accepting an applicant settles the stage at Enrolment whatever it was,
because a provider starting someone in front of them has, in effect,
offered and enrolled in one go.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

APPLICATION, OFFER, ENROLMENT = config.ADMISSION_STAGES


@dataclass
class AdmissionStage:
    """An applicant's admissions stage and the dates that go with it."""

    apprentice_id: int
    stage: str = APPLICATION
    offer_date: str | None = None
    offer_conditions: str | None = None
    enrolment_date: str | None = None
    updated_by: str | None = None
    updated_at: str = ""

    @property
    def step(self) -> int:
        """1, 2 or 3 along the way."""
        return config.ADMISSION_STAGES.index(self.stage) + 1

    @property
    def has_offer(self) -> bool:
        return self.stage in (OFFER, ENROLMENT)

    @property
    def label(self) -> str:
        if self.stage == OFFER and self.offer_conditions:
            return f"{OFFER} (conditional)"
        return self.stage


def validate_stage(value: str | None) -> str:
    cleaned = (value or "").strip() or APPLICATION
    match = next((s for s in config.ADMISSION_STAGES if s.casefold() == cleaned.casefold()), None)
    if match is None:
        raise ValidationError(
            f"Admission stage must be one of: {', '.join(config.ADMISSION_STAGES)}"
        )
    return match


def require_move(current: str, target: str) -> str:
    """Check one step through admissions and return the target stage.

    An offer may be re-made (to amend it) while it stands; enrolment
    needs an offer first and is the last stage.
    """
    target = validate_stage(target)
    if target == OFFER and current in (APPLICATION, OFFER):
        return target
    if target == ENROLMENT and current == OFFER:
        return target
    if target == ENROLMENT and current == ENROLMENT:
        raise ValidationError("Enrolment is already recorded")
    if target == ENROLMENT:
        raise ValidationError("Make an offer before recording enrolment")
    if current == ENROLMENT:
        raise ValidationError("This applicant has enrolled; the offer can no longer change")
    raise ValidationError(f"An applicant cannot move from {current} to {target}")
