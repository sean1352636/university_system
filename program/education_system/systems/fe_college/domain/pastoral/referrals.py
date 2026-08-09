"""Referrals to college support services.

A referral is a handover with a clock on it: safeguarding referrals must be
picked up the same day, everything else within a few working days. The
response-time rules are here so the referrals screen can sort by urgency
rather than by whoever shouted loudest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.fe_college.config import REFERRAL_STATUSES, REFERRAL_TYPES
from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

URGENCIES = ("routine", "priority", "urgent")

# Working-day response targets by referral type, approximated in calendar days.
RESPONSE_TARGET_DAYS = {
    "Safeguarding": 1,
    "Wellbeing / Mental Health": 2,
    "Attendance": 5,
    "Learning Support": 5,
    "Financial Support": 5,
    "Careers": 10,
}


@dataclass
class Referral:
    """One referral of a learner to a support service."""

    referral_id: int | None
    student_id: str
    referral_type: str
    reason: str
    status: str = "open"
    urgency: str = "routine"
    referred_by: str = ""            # staff_id
    referred_on: date | None = None
    assigned_to: str = ""            # staff_id
    actioned_on: date | None = None
    closed_on: date | None = None
    outcome: str = ""

    @property
    def is_open(self) -> bool:
        return self.status in ("open", "in_progress")

    @property
    def is_safeguarding(self) -> bool:
        return self.referral_type == "Safeguarding"

    @property
    def response_due(self) -> date | None:
        """Date by which this referral should have been picked up."""
        if self.referred_on is None:
            return None
        days = RESPONSE_TARGET_DAYS.get(self.referral_type, 5)
        # An urgent flag halves the target, with a floor of same-day.
        if self.urgency == "urgent":
            days = max(1, days // 2)
        return self.referred_on + timedelta(days=days)

    def is_breaching(self, on: date | None = None) -> bool:
        """Whether an open referral has passed its response target."""
        if not self.is_open or self.actioned_on is not None:
            return False
        due = self.response_due
        return due is not None and due < (on or date.today())

    def days_open(self, on: date | None = None) -> int | None:
        if self.referred_on is None:
            return None
        end = self.closed_on or on or date.today()
        return (end - self.referred_on).days

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("A referral needs a student")
        if self.referral_type not in REFERRAL_TYPES:
            raise ValidationError(f"Unknown referral type '{self.referral_type}'")
        if self.status not in REFERRAL_STATUSES:
            raise ValidationError(f"Unknown referral status '{self.status}'")
        if self.urgency not in URGENCIES:
            raise ValidationError(f"Unknown urgency '{self.urgency}'")
        if not self.reason.strip():
            raise ValidationError("A referral needs a reason")
        if not self.referred_by.strip():
            raise ValidationError("A referral must record who made it")
        if self.status == "closed":
            if self.closed_on is None:
                raise ValidationError("A closed referral must record its closing date")
            if not self.outcome.strip():
                raise ValidationError("A closed referral must record its outcome")
        if self.referred_on and self.closed_on and self.closed_on < self.referred_on:
            raise ValidationError("A referral cannot be closed before it was made")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "referral_type": self.referral_type,
            "reason": self.reason.strip(),
            "status": self.status,
            "urgency": self.urgency,
            "referred_by": optional_ref(self.referred_by),
            "referred_on": self.referred_on.isoformat() if self.referred_on else None,
            "assigned_to": optional_ref(self.assigned_to),
            "actioned_on": self.actioned_on.isoformat() if self.actioned_on else None,
            "closed_on": self.closed_on.isoformat() if self.closed_on else None,
            "outcome": self.outcome.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Referral":
        d = dict(row)
        return cls(
            referral_id=d.get("referral_id"),
            student_id=d.get("student_id") or "",
            referral_type=d.get("referral_type") or REFERRAL_TYPES[0],
            reason=d.get("reason") or "",
            status=d.get("status") or "open",
            urgency=d.get("urgency") or "routine",
            referred_by=d.get("referred_by") or "",
            referred_on=parse_date(d.get("referred_on")),
            assigned_to=d.get("assigned_to") or "",
            actioned_on=parse_date(d.get("actioned_on")),
            closed_on=parse_date(d.get("closed_on")),
            outcome=d.get("outcome") or "",
        )


__all__ = ["RESPONSE_TARGET_DAYS", "URGENCIES", "Referral"]
