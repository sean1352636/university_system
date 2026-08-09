"""Assignments — the briefs learners are assessed against.

A BTEC assignment brief targets specific unit criteria and carries a hand-out
and a hand-in date. Everything downstream (submissions, marking, resubmission
windows) hangs off those two dates, so they are validated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

ASSIGNMENT_STATUSES = ("draft", "issued", "closed", "archived")

# Awarding bodies allow one resubmission within 15 working days of feedback,
# authorised by the lead internal verifier. Approximated as calendar days here.
RESUBMISSION_WINDOW_DAYS = 21


@dataclass
class Assignment:
    """One assignment brief issued to a course or group."""

    assignment_id: int | None
    course_id: str
    title: str
    unit_id: str = ""
    group_id: str = ""
    status: str = "draft"
    set_by: str = ""                 # staff_id
    issue_date: date | None = None
    due_date: date | None = None
    criteria: str = ""               # e.g. "P1, P2, M1"
    max_marks: int = 0
    brief: str = ""
    created_at: str = ""

    @property
    def is_open(self) -> bool:
        return self.status == "issued"

    def is_overdue(self, on: date | None = None) -> bool:
        return bool(self.is_open and self.due_date and self.due_date < (on or date.today()))

    def days_remaining(self, on: date | None = None) -> int | None:
        if self.due_date is None:
            return None
        return (self.due_date - (on or date.today())).days

    @property
    def resubmission_deadline(self) -> date | None:
        """Last date a resubmission may be accepted, from the hand-in date."""
        if self.due_date is None:
            return None
        return self.due_date + timedelta(days=RESUBMISSION_WINDOW_DAYS)

    @property
    def criteria_list(self) -> tuple[str, ...]:
        return tuple(c.strip() for c in self.criteria.split(",") if c.strip())

    def validate(self) -> None:
        if not self.course_id.strip():
            raise ValidationError("An assignment must belong to a course")
        if not self.title.strip():
            raise ValidationError("Assignment title is required")
        if self.status not in ASSIGNMENT_STATUSES:
            raise ValidationError(f"Unknown assignment status '{self.status}'")
        if self.max_marks < 0:
            raise ValidationError("Maximum marks cannot be negative")
        if self.issue_date and self.due_date and self.due_date < self.issue_date:
            raise ValidationError("Hand-in date cannot be before the hand-out date")
        if self.status == "issued" and self.due_date is None:
            raise ValidationError("An issued assignment must have a hand-in date")

    def to_row(self) -> dict:
        return {
            "course_id": self.course_id.strip().upper(),
            "title": self.title.strip(),
            "unit_id": self.unit_id.strip().upper(),
            "group_id": self.group_id.strip().upper(),
            "status": self.status,
            "set_by": optional_ref(self.set_by),
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "criteria": self.criteria.strip(),
            "max_marks": int(self.max_marks),
            "brief": self.brief.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Assignment":
        d = dict(row)
        return cls(
            assignment_id=d.get("assignment_id"),
            course_id=d.get("course_id") or "",
            title=d.get("title") or "",
            unit_id=d.get("unit_id") or "",
            group_id=d.get("group_id") or "",
            status=d.get("status") or "draft",
            set_by=d.get("set_by") or "",
            issue_date=parse_date(d.get("issue_date")),
            due_date=parse_date(d.get("due_date")),
            criteria=d.get("criteria") or "",
            max_marks=int(d.get("max_marks") or 0),
            brief=d.get("brief") or "",
            created_at=d.get("created_at") or "",
        )


__all__ = ["ASSIGNMENT_STATUSES", "RESUBMISSION_WINDOW_DAYS", "Assignment"]
