"""One message in the college's correspondence log.

A message is addressed by *email address*, not by learner. That is the
difference between this and a learner note: an admissions enquiry from
somebody who is not yet a student, a chase to an employer about a
placement, and a fee reminder to a learner's parent all belong in the
same log, and only some of them have a ``student_id`` attached.

The rules that matter here are about not losing correspondence:

* an outgoing email must have somewhere to go, or it is not a message
* a message that claims to be Sent must record *when*, because "did we
  tell them, and when" is the question the log exists to answer
* the subject is required, since a log of untitled rows is unreadable

Delivery is deliberately out of scope. This records what the college
sent; whether SMTP accepted it is the concern of the platform's
``integrations.email`` service, and conflating the two would make an
unreachable mail server look like a lost record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from education_system.systems.fe_college.config import (
    MESSAGE_CATEGORIES,
    MESSAGE_CHANNELS,
    MESSAGE_DIRECTIONS,
    MESSAGE_PRIORITIES,
    MESSAGE_STATUSES,
)
from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    optional_ref,
)

# Deliberately permissive: enough to catch a typo like a missing "@" or a
# stray space, without rejecting the valid-but-unusual addresses that a
# stricter pattern would (plus-addressing, long TLDs, subdomains).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ID_PREFIX = "FEM"
ID_DIGITS = 4

#: Statuses that mean the message has gone. Used to decide whether a row
#: still belongs in the outbox.
CLOSED_STATUSES = ("Sent", "Received")


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def valid_email(value: str | None) -> bool:
    text = (value or "").strip()
    return bool(text) and _EMAIL_RE.match(text) is not None


@dataclass
class Message:
    """One logged message, inbound or outbound."""

    message_id: str | None
    subject: str
    body: str = ""
    direction: str = "Outgoing"
    channel: str = "Email"
    category: str = "General"
    priority: str = "Normal"
    status: str = "Draft"
    from_name: str = ""
    from_address: str = ""
    to_name: str = ""
    to_address: str = ""
    student_id: str = ""
    staff_id: str = ""
    tags: str = ""
    created_at: str | None = None
    sent_at: str | None = None
    # Joined for display, never stored.
    student_name: str | None = None
    staff_name: str | None = None

    # ── Derived ────────────────────────────────────────────────────────────

    @property
    def is_draft(self) -> bool:
        return self.status == "Draft"

    @property
    def is_sent(self) -> bool:
        return self.status in CLOSED_STATUSES

    @property
    def recipient(self) -> str:
        """Best available description of who this went to."""
        if self.to_name and self.to_address:
            return f"{self.to_name} <{self.to_address}>"
        return self.to_name or self.to_address or "—"

    @property
    def preview(self) -> str:
        """First line of the body, for a list column."""
        first = (self.body or "").strip().splitlines()
        return first[0][:80] if first else ""

    # ── Rules ──────────────────────────────────────────────────────────────

    def validate(self) -> None:
        if not (self.subject or "").strip():
            raise ValidationError("A message needs a subject")
        if self.direction not in MESSAGE_DIRECTIONS:
            raise ValidationError(f"Unknown direction '{self.direction}'")
        if self.channel not in MESSAGE_CHANNELS:
            raise ValidationError(f"Unknown channel '{self.channel}'")
        if self.category not in MESSAGE_CATEGORIES:
            raise ValidationError(f"Unknown category '{self.category}'")
        if self.priority not in MESSAGE_PRIORITIES:
            raise ValidationError(f"Unknown priority '{self.priority}'")
        if self.status not in MESSAGE_STATUSES:
            raise ValidationError(f"Unknown status '{self.status}'")

        for label, value in (("From address", self.from_address),
                             ("To address", self.to_address)):
            if (value or "").strip() and not valid_email(value):
                raise ValidationError(f"{label} is not a valid email address")

        # An outgoing email with no recipient is not a message, it is a note.
        if (self.direction == "Outgoing" and self.channel == "Email"
                and not (self.to_address or "").strip()):
            raise ValidationError("An outgoing email needs a To address")
        # An incoming message has to say who it came from, or the log cannot
        # answer "who contacted us".
        if self.direction == "Incoming" and not (
                (self.from_address or "").strip() or (self.from_name or "").strip()):
            raise ValidationError("An incoming message needs a sender")
        if self.is_sent and not (self.sent_at or "").strip():
            raise ValidationError(
                f"A message marked {self.status} must record when it was sent")

    # ── Persistence mapping ────────────────────────────────────────────────

    def to_row(self) -> dict:
        return {
            "message_id": self.message_id,
            "direction": self.direction,
            "channel": self.channel,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "subject": self.subject.strip(),
            "body": (self.body or "").strip(),
            "from_name": (self.from_name or "").strip(),
            "from_address": (self.from_address or "").strip(),
            "to_name": (self.to_name or "").strip(),
            "to_address": (self.to_address or "").strip(),
            "student_id": optional_ref(self.student_id),
            "staff_id": optional_ref(self.staff_id),
            "tags": (self.tags or "").strip(),
            "sent_at": self.sent_at,
        }

    @classmethod
    def from_row(cls, row) -> "Message":
        d = dict(row)
        return cls(
            message_id=d.get("message_id"),
            subject=d.get("subject") or "",
            body=d.get("body") or "",
            direction=d.get("direction") or "Outgoing",
            channel=d.get("channel") or "Email",
            category=d.get("category") or "General",
            priority=d.get("priority") or "Normal",
            status=d.get("status") or "Draft",
            from_name=d.get("from_name") or "",
            from_address=d.get("from_address") or "",
            to_name=d.get("to_name") or "",
            to_address=d.get("to_address") or "",
            student_id=d.get("student_id") or "",
            staff_id=d.get("staff_id") or "",
            tags=d.get("tags") or "",
            created_at=d.get("created_at"),
            sent_at=d.get("sent_at"),
            student_name=(d.get("student_name") or None),
            staff_name=(d.get("staff_name") or None),
        )


def next_message_id(existing: list[str]) -> str:
    """Return the next free ``FEM-nnnn`` reference.

    Sequential rather than random so the log reads in the order it was
    written, which is how anyone auditing correspondence reads it.
    """
    prefix = f"{ID_PREFIX}-"
    used = [
        int(mid[len(prefix):])
        for mid in existing
        if mid.startswith(prefix) and mid[len(prefix):].isdigit()
    ]
    return f"{prefix}{(max(used) + 1 if used else 1):0{ID_DIGITS}d}"


@dataclass
class Outbox:
    """Counts for the email centre's header row."""

    total: int = 0
    drafts: int = 0
    sent: int = 0
    incoming: int = 0
    failed: int = 0


__all__ = [
    "ID_PREFIX",
    "CLOSED_STATUSES",
    "Message",
    "Outbox",
    "next_message_id",
    "now_stamp",
    "valid_email",
]
