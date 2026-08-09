"""Provider staff and their caseloads.

A caseload is the set of apprentices one tutor or skills coach is
responsible for. Its size is the single best predictor of whether
reviews happen on time, which is why the admin dashboard flags anyone
over the warning threshold rather than waiting for missed reviews to
show up as a compliance problem.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError


@dataclass
class Staff:
    """A member of provider staff."""

    staff_id: int
    full_name: str
    email: str | None = None
    phone: str | None = None
    staff_role: str = "Tutor"
    username: str | None = None
    specialisms: str | None = None
    active: bool = True
    created_at: str = ""
    updated_at: str = ""

    @property
    def specialism_list(self) -> list[str]:
        if not self.specialisms:
            return []
        return [s.strip() for s in self.specialisms.split(",") if s.strip()]

    @property
    def can_assess(self) -> bool:
        """Roles qualified to make assessment judgements."""
        return self.staff_role in ("Assessor", "Tutor", "IQA", "Skills Coach")

    @property
    def can_verify(self) -> bool:
        """Internal quality assurance is an IQA-only responsibility.

        Deliberately excludes assessors: the point of IQA is that
        somebody other than the original assessor samples the decision.
        """
        return self.staff_role == "IQA"


@dataclass
class Caseload:
    """One member of staff's caseload and the pressure on it."""

    staff: Staff
    total: int = 0
    active: int = 0
    at_gateway: int = 0
    reviews_overdue: int = 0
    otj_behind: int = 0
    evidence_awaiting_assessment: int = 0
    members: list[object] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.staff.full_name

    @property
    def is_over_threshold(self) -> bool:
        return self.active >= config.CASELOAD_WARNING_THRESHOLD

    @property
    def is_at_capacity(self) -> bool:
        return self.active >= config.CASELOAD_MAXIMUM

    @property
    def rag_rating(self) -> str:
        """Traffic light for the caseload screen.

        Red covers both an oversized caseload and an overdue-review
        backlog: either one means apprentices are not being seen, which
        is the thing the rating is there to surface.
        """
        if self.is_at_capacity or self.reviews_overdue > 3:
            return "Red"
        if self.is_over_threshold or self.reviews_overdue > 0 or self.otj_behind > 0:
            return "Amber"
        return "Green"

    @property
    def headroom(self) -> int:
        """How many more apprentices this caseload can take."""
        return max(0, config.CASELOAD_MAXIMUM - self.active)


def validate_staff_role(value: str | None) -> str:
    """Check a staff role against the recognised list."""
    cleaned = (value or "Tutor").strip().title()
    # Title-casing mangles the IQA acronym; restore it.
    if cleaned.lower() == "iqa":
        cleaned = "IQA"
    if cleaned not in config.STAFF_ROLES:
        allowed = ", ".join(config.STAFF_ROLES)
        raise ValidationError(f"Staff role must be one of: {allowed}")
    return cleaned
