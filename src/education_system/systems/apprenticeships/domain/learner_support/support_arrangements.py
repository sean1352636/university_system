"""Reasonable adjustments and the support around them.

An arrangement names a need, the adjustment made for it, and who is
responsible for making it happen. Two things make it more than a note:

* It has a review date. Needs change, and an adjustment agreed at
  induction and never looked at again is how an apprentice ends up
  struggling with support that stopped fitting months ago. An
  arrangement whose review date has passed is flagged.
* It records consent. Information about a disability or a mental-health
  condition is special-category data; the employer sees an arrangement
  only when the apprentice has agreed to share it, and never the notes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

ENDED = "Ended"


@dataclass
class SupportNote:
    """One entry in an arrangement's history."""

    note_id: int
    arrangement_id: int
    author: str
    author_role: str
    body: str
    created_at: str = ""

    @property
    def author_label(self) -> str:
        return f"{self.author} ({config.ROLE_LABELS.get(self.author_role, self.author_role)})"


@dataclass
class SupportArrangement:
    """One reasonable adjustment or support arrangement."""

    arrangement_id: int
    apprentice_id: int
    need_category: str
    adjustment: str
    arrangements: str | None = None
    responsible_staff_id: int | None = None
    review_date: str | None = None
    status: str = "Active"
    share_with_employer: bool = False
    created_by: str | None = None
    created_at: str = ""
    updated_at: str = ""
    # Denormalised by the list query.
    apprentice_name: str = ""
    responsible_staff_name: str | None = None
    # Newest first; left empty for anyone who may not read the history.
    notes: list[SupportNote] = field(default_factory=list)

    @property
    def is_in_force(self) -> bool:
        return self.status != ENDED

    def is_review_overdue(self, today: date) -> bool:
        review = _parse(self.review_date)
        return self.is_in_force and review is not None and review < today

    def rag(self, today: date) -> str | None:
        """Red once the review is overdue, Amber when it is close, else Green.

        None for an ended arrangement, which is no longer being reviewed.
        """
        if not self.is_in_force:
            return None
        if self.is_review_overdue(today):
            return "Red"
        review = _parse(self.review_date)
        if review is not None and review <= today + timedelta(
            days=config.SUPPORT_REVIEW_DUE_SOON_DAYS
        ):
            return "Amber"
        return "Green"


@dataclass
class SupportRecord:
    """Everything about one apprentice's support that the viewer may see."""

    apprentice_id: int
    # The free-text support needs from enrolment, shown as context. Older
    # than the structured arrangements and not migrated into them; None
    # for anyone who may not read it (an employer).
    support_needs: str | None = None
    arrangements: list[SupportArrangement] = field(default_factory=list)

    @property
    def in_force(self) -> list[SupportArrangement]:
        return [a for a in self.arrangements if a.is_in_force]

    def overdue(self, today: date) -> list[SupportArrangement]:
        return [a for a in self.arrangements if a.is_review_overdue(today)]


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def validate_category(value: str | None) -> str:
    return _one_of(value, config.SUPPORT_NEED_CATEGORIES, "Need category")


def validate_status(value: str | None) -> str:
    return _one_of(value or "Active", config.SUPPORT_STATUSES, "Status")


def validate_text(value: object, label: str, *, required: bool = False,
                  limit: int | None = None) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    limit = limit or config.LEARNER_SUPPORT_NOTE_MAX_LENGTH
    if len(text) > limit:
        raise ValidationError(f"{label} must be {limit} characters or fewer")
    return text


def validate_review_date(value: object, *, status: str, today: date,
                         current: str | None = None) -> str | None:
    """A review date for an arrangement in *status*.

    An arrangement still in force needs one — that is the point of it.
    A new date must not already have passed; an unchanged date may have,
    because editing an overdue arrangement's wording must not be blocked
    by the overdue review it is waiting for.
    """
    text = str(value or "").strip()
    if not text:
        if status != ENDED:
            raise ValidationError("An arrangement in force needs a review date")
        return None
    try:
        review = date.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError("Review date must be a date in YYYY-MM-DD format") from exc
    iso = review.isoformat()
    if iso != current and status != ENDED and review < today:
        raise ValidationError("A review date cannot already have passed")
    return iso


def visible_to_employer(arrangement: SupportArrangement) -> bool:
    """Only what the apprentice has agreed to share."""
    return arrangement.share_with_employer


def _one_of(value: str | None, allowed: tuple[str, ...], label: str) -> str:
    cleaned = (value or "").strip()
    match = next((a for a in allowed if a.casefold() == cleaned.casefold()), None)
    if match is None:
        raise ValidationError(f"{label} must be one of: {', '.join(allowed)}")
    return match


def _parse(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None
