"""Tripartite progress reviews.

Every twelve weeks the provider, apprentice and employer sit down
together, agree how it is going, and set targets for the next period.
The review is worthless as evidence until all three have signed — an
unsigned review proves only that a meeting was scheduled — so
:class:`Review` treats signatures as the completion condition rather
than a formality tacked on the end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError


@dataclass
class ReviewSignature:
    """One party's signature on a review."""

    signature_id: int
    review_id: int
    signatory: str
    signed_by: str
    signed_at: str


@dataclass
class ReviewTarget:
    """A SMART target agreed at a review — an action on the action plan.

    The owner, priority and completion stamp make it something the person
    responsible can pick up and move, not only something the next review
    judges. See ``domain/reviews/action_plans.py`` for the rules.
    """

    target_id: int
    review_id: int
    description: str
    due_date: str | None = None
    ksb_codes: str | None = None
    status: str = "Open"
    outcome_note: str | None = None
    owner: str = config.ACTION_DEFAULT_OWNER
    priority: str = config.ACTION_DEFAULT_PRIORITY
    completed_at: str | None = None
    # Set on a copy made by carrying an outstanding action forward.
    carried_from: int | None = None
    carry_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    # Denormalised for the action-plan screens, filled by the join.
    apprentice_id: int | None = None
    apprentice_name: str = ""
    employer_id: int | None = None
    tutor_id: int | None = None
    review_date: str | None = None
    review_status: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status == "Open"

    @property
    def is_overdue(self) -> bool:
        return self.overdue_on(date.today())

    @property
    def is_carried(self) -> bool:
        """This is a copy brought forward from an earlier review."""
        return self.carried_from is not None or self.carry_count > 0

    def overdue_on(self, today: date) -> bool:
        return self.is_open and bool(self.due_date) and self.due_date < today.isoformat()

    def is_due_soon(self, today: date) -> bool:
        """Open, not yet overdue, and due within the action warning window."""
        if not self.is_open or not self.due_date or self.overdue_on(today):
            return False
        horizon = today + timedelta(days=config.ACTION_DUE_SOON_DAYS)
        return self.due_date <= horizon.isoformat()

    def rag(self, today: date) -> str | None:
        """Red when overdue, Amber when due within the week, Green once met.

        Anything else is untagged: an open action with time in hand needs
        no colour, and one closed Not Met or carried forward has been
        dealt with at a review.
        """
        if self.status == "Met":
            return "Green"
        if self.overdue_on(today):
            return "Red"
        if self.is_due_soon(today):
            return "Amber"
        return None


@dataclass
class Review:
    """One progress review."""

    review_id: int
    apprentice_id: int
    scheduled_date: str
    held_date: str | None = None
    status: str = "Scheduled"
    conducted_by: int | None = None
    progress_rating: str | None = None
    otj_on_track: bool | None = None
    summary: str | None = None
    apprentice_comments: str | None = None
    employer_comments: str | None = None
    next_review_date: str | None = None
    created_at: str = ""
    updated_at: str = ""
    signatures: list[ReviewSignature] = field(default_factory=list)
    targets: list[ReviewTarget] = field(default_factory=list)
    # Denormalised for list screens, filled by the join.
    apprentice_name: str = ""
    conductor_name: str | None = None

    @property
    def signed_by(self) -> set[str]:
        return {s.signatory for s in self.signatures}

    @property
    def missing_signatures(self) -> list[str]:
        """Parties still to sign, in the canonical order."""
        signed = self.signed_by
        return [s for s in config.REVIEW_SIGNATORIES if s not in signed]

    @property
    def is_fully_signed(self) -> bool:
        return not self.missing_signatures

    @property
    def is_complete(self) -> bool:
        return self.status == "Complete"

    @property
    def is_overdue(self) -> bool:
        """Scheduled date has passed and the meeting has not happened."""
        return (
            self.status in ("Scheduled", "In Progress")
            and self.scheduled_date < date.today().isoformat()
        )

    @property
    def open_targets(self) -> list[ReviewTarget]:
        return [t for t in self.targets if t.is_open]

    @property
    def overdue_targets(self) -> list[ReviewTarget]:
        return [t for t in self.targets if t.is_overdue]

    def can_sign(self, signatory: str) -> bool:
        """May *signatory* still add their signature?

        Signing requires the meeting to have happened — you cannot
        sign off a review that has not been held — and each party
        signs at most once.
        """
        if signatory not in config.REVIEW_SIGNATORIES:
            return False
        if self.status in ("Scheduled", "Missed"):
            return False
        return signatory not in self.signed_by


@dataclass
class EmployerFeedback:
    """An employer's satisfaction rating."""

    feedback_id: int
    employer_id: int
    satisfaction: str
    apprentice_id: int | None = None
    review_id: int | None = None
    comments: str | None = None
    submitted_by: str | None = None
    submitted_at: str = ""

    @property
    def score(self) -> int:
        """1-5 for averaging; 0 if the label is unrecognised."""
        try:
            return config.SATISFACTION_SCALE.index(self.satisfaction) + 1
        except ValueError:
            return 0

    @property
    def is_positive(self) -> bool:
        return self.score >= 4


def next_review_date(from_iso: str | None = None) -> str:
    """When the following review falls due."""
    base = date.fromisoformat(from_iso) if from_iso else date.today()
    return (base + timedelta(weeks=config.REVIEW_INTERVAL_WEEKS)).isoformat()


def validate_rating(rating: str | None) -> str | None:
    """Check a RAG progress rating."""
    if rating is None or not str(rating).strip():
        return None
    cleaned = str(rating).strip().title()
    if cleaned not in config.RAG_RATINGS:
        allowed = ", ".join(config.RAG_RATINGS)
        raise ValidationError(f"Progress rating must be one of: {allowed}")
    return cleaned


def validate_signatory(signatory: str | None) -> str:
    """Check a signatory role."""
    cleaned = (signatory or "").strip().lower()
    if cleaned not in config.REVIEW_SIGNATORIES:
        allowed = ", ".join(config.REVIEW_SIGNATORIES)
        raise ValidationError(f"Signatory must be one of: {allowed}")
    return cleaned


def validate_satisfaction(value: str | None) -> str:
    """Check an employer satisfaction rating."""
    cleaned = (value or "").strip()
    if cleaned not in config.SATISFACTION_SCALE:
        allowed = ", ".join(config.SATISFACTION_SCALE)
        raise ValidationError(f"Satisfaction must be one of: {allowed}")
    return cleaned


def validate_target_status(value: str | None) -> str:
    """Check a target outcome status."""
    cleaned = (value or "").strip().title()
    if cleaned not in config.TARGET_STATUSES:
        allowed = ", ".join(config.TARGET_STATUSES)
        raise ValidationError(f"Target status must be one of: {allowed}")
    return cleaned


def require_review_status(current: str, target: str) -> None:
    """Check a review status move is legal.

    Note there is no route out of Complete. A completed review is signed
    evidence; correcting one means holding another, not editing history.
    """
    if target not in config.REVIEW_STATUSES:
        raise ValidationError(f"{target!r} is not a review status")
    allowed: dict[str, frozenset[str]] = {
        "Scheduled": frozenset({"In Progress", "Missed"}),
        "In Progress": frozenset({"Awaiting Signatures", "Scheduled"}),
        "Awaiting Signatures": frozenset({"Complete", "In Progress"}),
        "Complete": frozenset(),
        # A missed review is rescheduled rather than resurrected.
        "Missed": frozenset({"Scheduled"}),
    }
    if target not in allowed.get(current, frozenset()):
        options = ", ".join(sorted(allowed.get(current, frozenset()))) or "nothing"
        raise ValidationError(
            f"Cannot move review from {current!r} to {target!r}. Allowed: {options}"
        )
