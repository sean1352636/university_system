"""Keeping in touch with an employer: the contact log and commitments.

The contact log is the record of every conversation with an employer —
by phone, email, a workplace visit — and what has to happen next. Its
follow-up dates are what turn a conversation into a task.

Commitments are what the employer has undertaken to do: release the
apprentice for off-the-job training, provide a mentor, turn up to
reviews. They are tracked because an employer who stops keeping them is
the commonest reason an apprenticeship fails, and an overdue commitment
is chased by escalating it, one level at a time, until somebody senior
enough on both sides deals with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError


@dataclass
class ContactLogEntry:
    """One conversation with an employer."""

    log_id: int
    employer_id: int
    contacted_on: str
    channel: str
    summary: str
    logged_by: str
    contact_id: int | None = None
    apprentice_id: int | None = None
    follow_up_date: str | None = None
    follow_up_done_at: str | None = None
    follow_up_done_by: str | None = None
    logged_by_role: str | None = None
    created_at: str = ""
    # Joined labels, for lists.
    employer_name: str | None = None
    contact_name: str | None = None
    apprentice_name: str | None = None

    @property
    def follow_up_open(self) -> bool:
        return bool(self.follow_up_date) and not self.follow_up_done_at

    def follow_up_overdue(self, today: date) -> bool:
        return self.follow_up_open and (self.follow_up_date or "") < today.isoformat()

    def follow_up_rag(self, today: date) -> str | None:
        """Red when the follow-up is late, Amber when it is close."""
        if not self.follow_up_open:
            return None
        if self.follow_up_overdue(today):
            return "Red"
        soon = (today + timedelta(days=config.CONTACT_FOLLOW_UP_SOON_DAYS)).isoformat()
        if (self.follow_up_date or "") <= soon:
            return "Amber"
        return None


@dataclass
class EmployerCommitment:
    """Something the employer has undertaken to do for an apprenticeship."""

    commitment_id: int
    employer_id: int
    commitment: str
    category: str = "Other"
    apprentice_id: int | None = None
    due_date: str | None = None
    status: str = "Open"
    escalation_level: int = 0
    escalated_at: str | None = None
    escalated_by: str | None = None
    escalation_reason: str | None = None
    closed_at: str | None = None
    notes: str | None = None
    created_by: str | None = None
    created_at: str = ""
    updated_at: str = ""
    employer_name: str | None = None
    apprentice_name: str | None = None

    @property
    def is_outstanding(self) -> bool:
        return self.status in config.OUTSTANDING_COMMITMENT_STATUSES

    def is_overdue(self, today: date) -> bool:
        return self.is_outstanding and bool(self.due_date) and self.due_date < today.isoformat()

    @property
    def can_escalate(self) -> bool:
        return self.is_outstanding and self.escalation_level < config.COMMITMENT_MAX_ESCALATION

    @property
    def escalation_label(self) -> str:
        return config.COMMITMENT_ESCALATION_LEVELS.get(
            self.escalation_level, f"Level {self.escalation_level}"
        )

    def rag(self, today: date) -> str | None:
        """Red when overdue, Amber while escalated, nothing otherwise."""
        if not self.is_outstanding:
            return "Green" if self.status == "Met" else None
        if self.is_overdue(today):
            return "Red"
        if self.escalation_level > 0:
            return "Amber"
        return None


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def validate_contact_role(value: str | None) -> str | None:
    """A role from the list, or None for a contact with no set role."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    return _match(cleaned, config.EMPLOYER_CONTACT_ROLES, "Contact role")


def validate_channel(value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError("Say how the contact was made")
    return _match(cleaned, config.CONTACT_CHANNELS, "Channel")


def validate_category(value: str | None) -> str:
    cleaned = (value or "").strip() or "Other"
    return _match(cleaned, config.COMMITMENT_CATEGORIES, "Commitment category")


def validate_commitment_status(value: str | None) -> str:
    cleaned = (value or "").strip() or "Open"
    return _match(cleaned, config.COMMITMENT_STATUSES, "Commitment status")


def validate_text(value: str | None, label: str, *, limit: int) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > limit:
        raise ValidationError(f"{label} must be {limit} characters or fewer")
    return text


def next_escalation_level(commitment: EmployerCommitment) -> int:
    """The level an escalation takes this commitment to, or raise."""
    if not commitment.is_outstanding:
        raise ValidationError(
            f"This commitment is {commitment.status}; only an open one can be escalated"
        )
    if commitment.escalation_level >= config.COMMITMENT_MAX_ESCALATION:
        raise ValidationError(
            "This commitment is already escalated as far as it goes "
            f"({config.COMMITMENT_ESCALATION_LEVELS[config.COMMITMENT_MAX_ESCALATION]})"
        )
    return commitment.escalation_level + 1


def validate_closure(commitment: EmployerCommitment, status: str) -> str:
    """Closing a commitment means marking it Met or Withdrawn, once."""
    target = validate_commitment_status(status)
    if target not in ("Met", "Withdrawn"):
        raise ValidationError("A commitment is closed as Met or Withdrawn")
    if not commitment.is_outstanding:
        raise ValidationError(f"This commitment is already {commitment.status}")
    return target


def _match(value: str, allowed: tuple[str, ...], label: str) -> str:
    match = next((a for a in allowed if a.casefold() == value.casefold()), None)
    if match is None:
        raise ValidationError(f"{label} must be one of: {', '.join(allowed)}")
    return match
