"""Target grades and SMART targets set at tutorial reviews.

Two different things a college calls a "target", kept apart deliberately:

* a **target grade** — the qualification outcome a learner is aiming for,
  usually generated from prior attainment and reviewed once a term;
* a **SMART target** — a short, specific action agreed at a tutorial
  ("submit Unit 3 draft by 14 March"), which is completed or missed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

TARGET_STATUSES = ("set", "in_progress", "achieved", "missed", "cancelled")

# Prior attainment on entry -> the minimum target grade a college would set.
# A starting point for the tutor, not a ceiling: the GUI pre-fills from this
# and the tutor can raise it.
_ASPIRATION = {
    "Level 3 with merit or above": "Distinction",
    "Level 2 with merit or above": "Distinction",
    "Level 2 pass": "Merit",
    "Level 1 pass": "Pass",
    "No formal qualifications": "Pass",
}


def suggested_target(prior_attainment: str) -> str:
    """Suggest a target grade from prior attainment; blank when unknown."""
    return _ASPIRATION.get(prior_attainment.strip(), "")


@dataclass
class Target:
    """A SMART target agreed with a learner at a tutorial."""

    target_id: int | None
    student_id: str
    description: str
    status: str = "set"
    course_id: str = ""
    set_by: str = ""            # staff_id of the tutor who set it
    set_date: date | None = None
    due_date: date | None = None
    completed_date: date | None = None
    review_note: str = ""
    created_at: str = ""

    @property
    def is_open(self) -> bool:
        return self.status in ("set", "in_progress")

    def is_overdue(self, on: date | None = None) -> bool:
        return bool(self.is_open and self.due_date and self.due_date < (on or date.today()))

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("Target needs a student")
        if not self.description.strip():
            raise ValidationError("Target needs a description")
        if self.status not in TARGET_STATUSES:
            raise ValidationError(f"Unknown target status '{self.status}'")
        if self.set_date and self.due_date and self.due_date < self.set_date:
            raise ValidationError("Target due date cannot be before the date it was set")
        if self.status == "achieved" and self.completed_date is None:
            raise ValidationError("An achieved target must record a completion date")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "description": self.description.strip(),
            "status": self.status,
            "course_id": self.course_id.strip(),
            "set_by": optional_ref(self.set_by),
            "set_date": self.set_date.isoformat() if self.set_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_date": (
                self.completed_date.isoformat() if self.completed_date else None
            ),
            "review_note": self.review_note.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Target":
        d = dict(row)
        return cls(
            target_id=d.get("target_id"),
            student_id=d.get("student_id") or "",
            description=d.get("description") or "",
            status=d.get("status") or "set",
            course_id=d.get("course_id") or "",
            set_by=d.get("set_by") or "",
            set_date=parse_date(d.get("set_date")),
            due_date=parse_date(d.get("due_date")),
            completed_date=parse_date(d.get("completed_date")),
            review_note=d.get("review_note") or "",
            created_at=d.get("created_at") or "",
        )


__all__ = ["TARGET_STATUSES", "Target", "suggested_target"]
