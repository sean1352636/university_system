"""Tutorials — the scheduled 1:1 reviews a personal tutor holds.

Every FE learner has a personal tutor and a required number of recorded
tutorials per year. The count and the interval matter for inspection, so
"is this learner overdue a tutorial?" is answered here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

TUTORIAL_TYPES = ("Individual review", "Group tutorial", "Progress review", "Cause for concern")

TUTORIAL_STATUSES = ("scheduled", "held", "missed", "cancelled")

# Colleges typically require an individual review each half-term.
TUTORIAL_INTERVAL_DAYS = 42
REQUIRED_TUTORIALS_PER_YEAR = 6


@dataclass
class Tutorial:
    """One tutorial record."""

    tutorial_id: int | None
    student_id: str
    tutor_id: str
    tutorial_type: str = "Individual review"
    status: str = "scheduled"
    scheduled_for: date | None = None
    held_on: date | None = None
    attendance_discussed: bool = False
    progress_discussed: bool = False
    targets_set: str = ""
    notes: str = ""
    student_comment: str = ""

    @property
    def is_recorded(self) -> bool:
        return self.status == "held"

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("A tutorial needs a student")
        if not self.tutor_id.strip():
            raise ValidationError("A tutorial needs a tutor")
        if self.tutorial_type not in TUTORIAL_TYPES:
            raise ValidationError(f"Unknown tutorial type '{self.tutorial_type}'")
        if self.status not in TUTORIAL_STATUSES:
            raise ValidationError(f"Unknown tutorial status '{self.status}'")
        if self.status == "held":
            if self.held_on is None:
                raise ValidationError("A held tutorial must record the date it took place")
            if not self.notes.strip():
                raise ValidationError("A held tutorial must record what was discussed")
        if self.held_on and self.held_on > date.today():
            raise ValidationError("A tutorial cannot be recorded as held in the future")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "tutor_id": optional_ref(self.tutor_id),
            "tutorial_type": self.tutorial_type,
            "status": self.status,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "held_on": self.held_on.isoformat() if self.held_on else None,
            "attendance_discussed": 1 if self.attendance_discussed else 0,
            "progress_discussed": 1 if self.progress_discussed else 0,
            "targets_set": self.targets_set.strip(),
            "notes": self.notes.strip(),
            "student_comment": self.student_comment.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Tutorial":
        d = dict(row)
        return cls(
            tutorial_id=d.get("tutorial_id"),
            student_id=d.get("student_id") or "",
            tutor_id=d.get("tutor_id") or "",
            tutorial_type=d.get("tutorial_type") or "Individual review",
            status=d.get("status") or "scheduled",
            scheduled_for=parse_date(d.get("scheduled_for")),
            held_on=parse_date(d.get("held_on")),
            attendance_discussed=bool(d.get("attendance_discussed")),
            progress_discussed=bool(d.get("progress_discussed")),
            targets_set=d.get("targets_set") or "",
            notes=d.get("notes") or "",
            student_comment=d.get("student_comment") or "",
        )


def is_tutorial_overdue(last_held: date | None, on: date | None = None) -> bool:
    """Whether a learner is past due an individual review.

    A learner with no tutorial on record is overdue, not exempt.
    """
    ref = on or date.today()
    if last_held is None:
        return True
    return (ref - last_held).days > TUTORIAL_INTERVAL_DAYS


def next_tutorial_due(last_held: date | None, on: date | None = None) -> date:
    """The date the next individual review falls due."""
    base = last_held or (on or date.today())
    return base + timedelta(days=TUTORIAL_INTERVAL_DAYS)


__all__ = [
    "REQUIRED_TUTORIALS_PER_YEAR",
    "TUTORIAL_INTERVAL_DAYS",
    "TUTORIAL_STATUSES",
    "TUTORIAL_TYPES",
    "Tutorial",
    "is_tutorial_overdue",
    "next_tutorial_due",
]
