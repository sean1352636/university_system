"""Qualifications an apprentice holds, is taking, or has achieved.

Prior qualifications matter twice over. They decide eligibility — an
apprenticeship may not duplicate learning the person already has — and,
when relevant, they are recognised prior learning that shortens the
programme and reduces its price. So a prior qualification flagged as
relevant prior learning is a funding fact, not a CV line, and the rules
here keep that flag on the qualifications it can honestly apply to.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

PRIOR_STATUS = "Held (prior)"
ACHIEVED_STATUS = "Achieved"
IN_PROGRESS_STATUS = "In progress"


@dataclass
class Qualification:
    """One qualification on an apprentice's record."""

    qualification_id: int
    apprentice_id: int
    title: str
    level: str | None = None
    awarding_body: str | None = None
    reference: str | None = None
    status: str = IN_PROGRESS_STATUS
    grade: str | None = None
    start_date: str | None = None
    achieved_date: str | None = None
    certificate_ref: str | None = None
    relevant_prior_learning: bool = False
    notes: str | None = None
    recorded_by: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_prior(self) -> bool:
        return self.status == PRIOR_STATUS

    @property
    def is_achieved(self) -> bool:
        """Held before the programme or achieved during it — either is a qualification held."""
        return self.status in (PRIOR_STATUS, ACHIEVED_STATUS)

    @property
    def awaiting_certificate(self) -> bool:
        """Achieved during the programme with no certificate recorded yet."""
        return self.status == ACHIEVED_STATUS and not self.certificate_ref


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def validate_status(value: str | None) -> str:
    cleaned = (value or IN_PROGRESS_STATUS).strip()
    match = next(
        (s for s in config.QUALIFICATION_STATUSES if s.casefold() == cleaned.casefold()), None
    )
    if match is None:
        allowed = ", ".join(config.QUALIFICATION_STATUSES)
        raise ValidationError(f"Qualification status must be one of: {allowed}")
    return match


def validate_level(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    match = next(
        (lv for lv in config.QUALIFICATION_LEVELS if lv.casefold() == cleaned.casefold()), None
    )
    if match is None:
        allowed = ", ".join(config.QUALIFICATION_LEVELS)
        raise ValidationError(f"Qualification level must be one of: {allowed}")
    return match


def settle_dates(
    status: str,
    start_date: str | None,
    achieved_date: str | None,
    today: date,
) -> str | None:
    """The achieved date a qualification in *status* should carry.

    An achievement is stamped today when no date is given — the usual
    case is recording it the day the result arrives. A qualification
    still in progress has not been achieved, so any date given is
    dropped rather than refused: a tutor moving one back to In progress
    need not clear the field first. Neither kind of date may be in the
    future, and nothing is achieved before it was started.
    """
    if status == IN_PROGRESS_STATUS:
        achieved = None
    elif status == ACHIEVED_STATUS:
        achieved = achieved_date or today.isoformat()
    else:
        achieved = achieved_date

    if achieved and date.fromisoformat(achieved) > today:
        raise ValidationError("An achieved date cannot be in the future")
    if achieved and start_date and achieved < start_date:
        raise ValidationError("A qualification cannot be achieved before it was started")
    return achieved


def check_prior_learning(status: str, relevant_prior_learning: bool) -> None:
    """Recognised prior learning is learning done *before* the programme.

    Something taken or achieved during the apprenticeship cannot shorten
    it, so the flag is refused on anything but a prior qualification.
    """
    if relevant_prior_learning and status != PRIOR_STATUS:
        raise ValidationError(
            "Only a qualification held before the programme can count as prior learning"
        )
