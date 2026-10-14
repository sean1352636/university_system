"""Complaints: what was raised, where it has got to, and whether it is late.

Anyone with a stake in an apprenticeship may complain — the apprentice,
their employer, provider staff, even the end-point assessor. What makes
a complaints process trustworthy is that it moves at a known pace and
leaves a record, so a complaint carries two deadlines from the day it
is received (acknowledge by, respond by) and every status change is
checked against a fixed route. A complaint cannot be quietly closed
without ever having been answered.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

REFERENCE_PREFIX = "CMP"

# Still waiting on the provider. Resolved is answered but may yet be
# escalated; it no longer counts against the response deadline.
OPEN_COMPLAINT_STATUSES: frozenset[str] = frozenset({"Received", "Acknowledged", "Investigating"})

# Where a complaint may go next. Acknowledging is its own step because it
# is the first deadline: skipping straight to Investigating would let the
# acknowledgement clock run on unseen. Escalation follows the provider's
# own attempt — from Investigating when it has stalled, or from Resolved
# when the complainant is unhappy with the answer.
COMPLAINT_TRANSITIONS: dict[str, frozenset[str]] = {
    "Received": frozenset({"Acknowledged"}),
    "Acknowledged": frozenset({"Investigating", "Resolved"}),
    "Investigating": frozenset({"Resolved", "Escalated"}),
    "Resolved": frozenset({"Closed", "Escalated"}),
    "Escalated": frozenset({"Closed"}),
    "Closed": frozenset(),
}

# An open complaint due within this many days shows Amber.
_DUE_SOON_DAYS = 3


@dataclass
class Complaint:
    """One complaint and where it stands."""

    complaint_id: int
    reference: str
    raised_by: str
    raised_role: str
    category: str
    subject: str
    description: str
    received_at: str
    ack_due_on: str
    response_due_on: str
    status: str = "Received"
    apprentice_id: int | None = None
    employer_id: int | None = None
    handler: str | None = None
    acknowledged_at: str | None = None
    outcome: str | None = None
    closed_at: str | None = None
    escalated_to: str | None = None
    # None until the complainant says.
    satisfied: bool | None = None
    created_at: str = ""
    updated_at: str = ""
    # Joined labels, for display only.
    apprentice_name: str | None = None
    employer_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_COMPLAINT_STATUSES

    @property
    def raised_role_label(self) -> str:
        return config.ROLE_LABELS.get(self.raised_role, self.raised_role)

    def ack_overdue(self, today: date) -> bool:
        due = _parse(self.ack_due_on)
        return self.status == "Received" and due is not None and today > due

    def response_overdue(self, today: date) -> bool:
        due = _parse(self.response_due_on)
        return self.is_open and due is not None and today > due

    def is_overdue(self, today: date) -> bool:
        return self.ack_overdue(today) or self.response_overdue(today)

    def overdue_label(self, today: date) -> str:
        """What is late, in words, or an empty string."""
        if self.ack_overdue(today):
            return "Acknowledgement overdue"
        if self.response_overdue(today):
            return "Response overdue"
        return ""

    def next_deadline(self) -> str | None:
        """The deadline the provider is working to right now."""
        if self.status == "Received":
            return self.ack_due_on
        if self.is_open:
            return self.response_due_on
        return None

    def rag(self, today: date) -> str | None:
        """Red when late, Amber when a deadline is close; finished ones are not judged."""
        if not self.is_open:
            return None
        if self.is_overdue(today):
            return "Red"
        due = _parse(self.next_deadline())
        if due is not None and due <= today + timedelta(days=_DUE_SOON_DAYS):
            return "Amber"
        return None

    def allowed_next(self) -> tuple[str, ...]:
        """Statuses this complaint may move to, in the order the process runs."""
        allowed = COMPLAINT_TRANSITIONS.get(self.status, frozenset())
        return tuple(s for s in config.COMPLAINT_STATUSES if s in allowed)


@dataclass
class ComplaintUpdate:
    """One entry in a complaint's running record."""

    update_id: int
    complaint_id: int
    note: str
    author: str
    author_role: str
    visible_to_complainant: bool = False
    created_at: str = ""

    @property
    def author_label(self) -> str:
        return f"{self.author} ({config.ROLE_LABELS.get(self.author_role, self.author_role)})"


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def complaint_reference(complaint_id: int) -> str:
    return f"{REFERENCE_PREFIX}-{int(complaint_id):04d}"


def deadlines(received: date) -> tuple[str, str]:
    """``(acknowledge_by, respond_by)`` for a complaint received on *received*."""
    return (
        (received + timedelta(days=config.COMPLAINT_ACK_DAYS)).isoformat(),
        (received + timedelta(days=config.COMPLAINT_RESPONSE_DAYS)).isoformat(),
    )


def validate_category(value: str | None) -> str:
    return _match(value, config.COMPLAINT_CATEGORIES, "Complaint category")


def validate_status(value: str | None) -> str:
    return _match(value, config.COMPLAINT_STATUSES, "Complaint status")


def require_transition(current: str, new: str) -> None:
    """Raise unless a complaint may move from *current* to *new*."""
    allowed = COMPLAINT_TRANSITIONS.get(current, frozenset())
    if new in allowed:
        return
    if not allowed:
        raise ValidationError(f"A {current.lower()} complaint cannot change status")
    options = ", ".join(s for s in config.COMPLAINT_STATUSES if s in allowed)
    raise ValidationError(
        f"A complaint cannot go from {current} to {new}; next it may be: {options}"
    )


def require_status_details(
    new_status: str, *, outcome: str | None, escalated_to: str | None
) -> None:
    """The facts a status needs before a complaint may enter it.

    Resolved means the provider has answered, so the answer must be
    written down; Escalated means someone else now has it, so who.
    """
    if new_status == "Resolved" and not (outcome or "").strip():
        raise ValidationError("Record the outcome before resolving a complaint")
    if new_status == "Escalated" and not (escalated_to or "").strip():
        raise ValidationError("Say who the complaint has been escalated to")


def validate_text(value: str | None, label: str, *, max_length: int,
                  required: bool = True) -> str | None:
    text = (value or "").strip()
    if not text:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if len(text) > max_length:
        raise ValidationError(f"{label} must be {max_length} characters or fewer")
    return text


def _match(value: str | None, allowed: tuple[str, ...], label: str) -> str:
    cleaned = (value or "").strip()
    match = next((s for s in allowed if s.casefold() == cleaned.casefold()), None)
    if match is None:
        raise ValidationError(f"{label} must be one of: {', '.join(allowed)}")
    return match


def _parse(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None
