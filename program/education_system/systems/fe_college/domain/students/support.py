"""Learning support records — additional needs and the support put in place.

Kept separate from the learner record because support plans have their own
lifecycle (reviewed each term, may end mid-year) and their own access rules:
the staff-facing screens show the *provision*, not the underlying diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

SUPPORT_TYPES = (
    "Exam access arrangements",
    "In-class support",
    "1:1 tutoring",
    "Assistive technology",
    "Note-taker",
    "Mentoring",
    "Counselling",
    "ESOL support",
    "Physical access",
)

SUPPORT_STATUSES = ("proposed", "active", "under_review", "ended")


@dataclass
class SupportPlan:
    """One strand of support for one learner."""

    plan_id: int | None
    student_id: str
    support_type: str
    status: str = "proposed"
    detail: str = ""
    hours_per_week: float = 0.0
    start_date: date | None = None
    review_date: date | None = None
    end_date: date | None = None
    coordinator: str = ""       # staff_id of the learning-support coordinator
    created_at: str = ""

    @property
    def is_active(self) -> bool:
        return self.status in ("active", "under_review")

    def is_review_due(self, on: date | None = None) -> bool:
        """Whether the review date has passed on an active plan."""
        if not self.is_active or self.review_date is None:
            return False
        return self.review_date <= (on or date.today())

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("Support plan needs a student")
        if self.support_type not in SUPPORT_TYPES:
            raise ValidationError(f"Unknown support type '{self.support_type}'")
        if self.status not in SUPPORT_STATUSES:
            raise ValidationError(f"Unknown support status '{self.status}'")
        if self.hours_per_week < 0:
            raise ValidationError("Support hours cannot be negative")
        if self.hours_per_week > 40:
            raise ValidationError("Support hours per week cannot exceed 40")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Support end date cannot be before its start date")
        if self.status == "ended" and self.end_date is None:
            raise ValidationError("An ended support plan must record an end date")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "support_type": self.support_type,
            "status": self.status,
            "detail": self.detail.strip(),
            "hours_per_week": float(self.hours_per_week),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "review_date": self.review_date.isoformat() if self.review_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "coordinator": optional_ref(self.coordinator),
        }

    @classmethod
    def from_row(cls, row) -> "SupportPlan":
        d = dict(row)
        return cls(
            plan_id=d.get("plan_id"),
            student_id=d.get("student_id") or "",
            support_type=d.get("support_type") or SUPPORT_TYPES[0],
            status=d.get("status") or "proposed",
            detail=d.get("detail") or "",
            hours_per_week=float(d.get("hours_per_week") or 0),
            start_date=parse_date(d.get("start_date")),
            review_date=parse_date(d.get("review_date")),
            end_date=parse_date(d.get("end_date")),
            coordinator=d.get("coordinator") or "",
            created_at=d.get("created_at") or "",
        )


__all__ = ["SUPPORT_STATUSES", "SUPPORT_TYPES", "SupportPlan"]
