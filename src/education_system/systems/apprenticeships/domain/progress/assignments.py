"""Assignments: work the provider sets, the apprentice submits, a marker
grades and a second person moderates.

Three rules carry the weight here.

* **A Refer is not the end.** Work graded Refer goes back to the
  apprentice for another attempt, up to the assignment's attempt limit.
  Only a Refer on the final attempt stands as the result.
* **Nobody moderates their own marking.** Moderation is a second opinion;
  the marker giving it would make the record say two people agreed when
  one did.
* **Late work is accepted and flagged.** Refusing it would punish the
  apprentice for an employer who did not release them; recording it keeps
  the pattern visible. The flag is fixed when the work is handed in, so
  moving the due date afterwards does not rewrite what happened.

Each attempt keeps its own submission row with its own grade and
feedback, so a referral and resubmission leave the whole history in
place rather than overwriting it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.programmes.models import validate_ksb_code

REFER = config.ASSIGNMENT_REFER_GRADE

# Waiting on the apprentice: the only statuses a submission may be made in.
WITH_APPRENTICE: frozenset[str] = frozenset({"Set", "Referred"})

# Graded, with a moderation still possible on the current attempt.
MODERATABLE: frozenset[str] = frozenset({"Marked", "Referred"})

_TRANSITIONS: dict[str, frozenset[str]] = {
    "Set": frozenset({"Submitted", "Withdrawn"}),
    "Submitted": frozenset({"Marked", "Referred"}),
    # Moderation may confirm the grade, or turn it into a Refer with
    # attempts left, which reopens the work.
    "Marked": frozenset({"Moderated", "Referred"}),
    # A moderator may lift a Refer to a pass; the apprentice may resubmit.
    "Referred": frozenset({"Submitted", "Moderated", "Withdrawn"}),
    "Moderated": frozenset(),
    "Withdrawn": frozenset(),
}


@dataclass
class AssignmentSubmission:
    """One attempt at an assignment, and how it was marked."""

    submission_id: int
    assignment_id: int
    attempt: int
    submitted_by: str
    body: str | None = None
    evidence_id: int | None = None
    submitted_at: str = ""
    is_late: bool = False
    grade: str | None = None
    feedback: str | None = None
    marked_by: str | None = None
    marked_at: str | None = None
    # Denormalised from the portfolio for display.
    evidence_title: str | None = None


@dataclass
class AssignmentModeration:
    """A second opinion on the grade given to one attempt."""

    moderation_id: int
    assignment_id: int
    attempt: int
    moderator: str
    outcome: str
    original_grade: str | None = None
    adjusted_grade: str | None = None
    notes: str | None = None
    moderated_at: str = ""

    @property
    def final_grade(self) -> str | None:
        return self.adjusted_grade if self.outcome == "Adjusted" else self.original_grade


@dataclass
class Assignment:
    """One piece of assessed work set for one apprentice.

    The row describes the *current* attempt; earlier attempts are in
    ``submissions``, which the repository fills when asked.
    """

    assignment_id: int
    apprentice_id: int
    title: str
    assignment_type: str
    brief: str | None = None
    ksb_codes: str | None = None
    set_by: str | None = None
    set_at: str = ""
    due_date: str | None = None
    status: str = "Set"
    attempt: int = 1
    max_attempts: int = config.ASSIGNMENT_MAX_ATTEMPTS
    grade: str | None = None
    feedback: str | None = None
    marked_by: str | None = None
    marked_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    submissions: list[AssignmentSubmission] = field(default_factory=list)
    moderations: list[AssignmentModeration] = field(default_factory=list)
    # Denormalised for list screens, filled by the join.
    apprentice_name: str = ""
    employer_id: int | None = None
    tutor_id: int | None = None
    # Whether the current attempt has been moderated; filled by the join
    # so the moderation queue does not need the children loaded.
    current_moderated: bool = False

    @property
    def is_with_apprentice(self) -> bool:
        return self.status in WITH_APPRENTICE

    @property
    def attempts_used(self) -> int:
        """Attempts handed in so far. ``attempt`` names the current one,
        which has not been used until it is submitted."""
        return self.attempt - 1 if self.status == "Set" else self.attempt

    @property
    def attempts_left(self) -> int:
        return max(0, self.max_attempts - self.attempts_used)

    @property
    def next_attempt(self) -> int:
        """The attempt number a submission made now would be."""
        return self.attempt + 1 if self.status == "Referred" else self.attempt

    @property
    def current_submission(self) -> AssignmentSubmission | None:
        return next((s for s in self.submissions if s.attempt == self.attempt), None)

    @property
    def current_moderation(self) -> AssignmentModeration | None:
        return next((m for m in self.moderations if m.attempt == self.attempt), None)

    @property
    def is_late(self) -> bool:
        """The current attempt was handed in after the due date."""
        current = self.current_submission
        return bool(current and current.is_late)

    @property
    def awaiting_moderation(self) -> bool:
        return (
            self.status in MODERATABLE
            and bool(self.marked_by)
            and not self.current_moderated
            and self.current_moderation is None
        )

    @property
    def is_passed(self) -> bool:
        return self.status in ("Marked", "Moderated") and self.grade not in (None, REFER)

    @property
    def is_failed(self) -> bool:
        """Referred on the final attempt: the Refer stands."""
        return self.status in ("Marked", "Moderated") and self.grade == REFER

    def is_overdue(self, today: date) -> bool:
        return self.is_with_apprentice and bool(self.due_date) and self.due_date < today.isoformat()

    def is_due_soon(self, today: date) -> bool:
        if not self.is_with_apprentice or not self.due_date or self.is_overdue(today):
            return False
        horizon = today + timedelta(days=config.ASSIGNMENT_DUE_SOON_DAYS)
        return self.due_date <= horizon.isoformat()

    def rag(self, today: date) -> str | None:
        """Red overdue or failed, Amber due soon or waiting on a marker,
        Green once passed. None otherwise."""
        if self.is_overdue(today) or self.is_failed:
            return "Red"
        if self.is_due_soon(today) or self.status == "Submitted":
            return "Amber"
        if self.is_passed:
            return "Green"
        return None


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def validate_assignment_type(value: str | None) -> str:
    return _match(value, config.ASSIGNMENT_TYPES, "Assignment type")


def validate_grade(value: str | None) -> str:
    return _match(value, config.ASSIGNMENT_GRADES, "Grade")


def validate_moderation_outcome(value: str | None) -> str:
    return _match(value, config.ASSIGNMENT_MODERATION_OUTCOMES, "Moderation outcome")


def validate_max_attempts(value: object) -> int:
    """An attempt limit from 1 up to the configured cap; blank takes the cap."""
    text = str(value if value is not None else "").strip()
    if not text:
        return config.ASSIGNMENT_MAX_ATTEMPTS
    try:
        attempts = int(text)
    except ValueError as exc:
        raise ValidationError("Attempts allowed must be a whole number") from exc
    if not 1 <= attempts <= config.ASSIGNMENT_MAX_ATTEMPTS:
        raise ValidationError(
            f"Attempts allowed must be from 1 to {config.ASSIGNMENT_MAX_ATTEMPTS}"
        )
    return attempts


def parse_ksb_codes(value: str | None) -> list[str]:
    """Normalise a comma-separated KSB list: ``"k1, s3 ,K1"`` -> ``["K1", "S3"]``."""
    codes: list[str] = []
    for part in (value or "").replace(";", ",").split(","):
        if not part.strip():
            continue
        code, _ = validate_ksb_code(part)
        if code not in codes:
            codes.append(code)
    return codes


def require_assignment_status(current: str, target: str) -> None:
    """Check an assignment status move is legal. Moderated and Withdrawn are final."""
    if target not in config.ASSIGNMENT_STATUSES:
        raise ValidationError(f"{target!r} is not an assignment status")
    allowed = _TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        options = ", ".join(sorted(allowed)) or "nothing"
        raise ValidationError(
            f"Cannot move an assignment from {current!r} to {target!r}. Allowed: {options}"
        )


def status_after_mark(grade: str, attempt: int, max_attempts: int) -> str:
    """Referred when a Refer leaves attempts to spare; Marked otherwise."""
    if grade == REFER and attempt < max_attempts:
        return "Referred"
    return "Marked"


def status_after_moderation(final_grade: str | None, attempt: int, max_attempts: int) -> str:
    """Where moderation leaves the work.

    A Refer that stands with attempts left sends it back to the apprentice
    (Referred) — moderation must not take away a resubmission they are
    entitled to. Anything else is settled: Moderated.
    """
    if final_grade == REFER and attempt < max_attempts:
        return "Referred"
    return "Moderated"


def require_different_moderator(moderator: str, marked_by: str | None) -> None:
    if not marked_by:
        raise ValidationError("This attempt has not been marked, so there is nothing to moderate")
    if moderator.strip().casefold() == marked_by.strip().casefold():
        raise ValidationError(
            "You marked this attempt, so you cannot moderate it. Moderation is a second "
            "opinion and needs a second person."
        )


def submitted_late(due_date: str | None, submitted_on: date) -> bool:
    """Handed in after the day it was due. Work due today is on time all day."""
    return bool(due_date) and submitted_on.isoformat() > str(due_date)


def validate_submission(body: str | None, *, has_evidence: bool) -> str | None:
    """The submission text: optional when portfolio evidence is attached."""
    text = (body or "").strip()
    if not text and not has_evidence:
        raise ValidationError(
            "A submission needs some work in it: write it here or attach portfolio evidence"
        )
    if len(text) > config.ASSIGNMENT_SUBMISSION_MAX_LENGTH:
        raise ValidationError(
            f"A submission must be {config.ASSIGNMENT_SUBMISSION_MAX_LENGTH} characters or fewer"
        )
    return text or None


def _match(value: str | None, options: tuple[str, ...], label: str) -> str:
    cleaned = (value or "").strip()
    found = next((o for o in options if o.casefold() == cleaned.casefold()), None)
    if found is None:
        raise ValidationError(f"{label} must be one of: {', '.join(options)}")
    return found
