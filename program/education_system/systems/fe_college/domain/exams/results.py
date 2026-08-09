"""Exam results and the post-results services a learner can request.

Results arrive against entries. A learner who is unhappy has a fixed window to
request a review of marking or a copy of their script, and the window closes
absolutely — so it is computed here rather than eyeballed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.fe_college.domain.students.grades import is_pass
from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    parse_date,
)

RESULT_STATUSES = ("provisional", "confirmed", "under_review", "amended", "pending")

# Post-results services offered by awarding bodies, and the days from results
# day in which each must be requested.
POST_RESULT_SERVICES = {
    "Copy of script": 30,
    "Review of marking": 30,
    "Review of moderation": 30,
    "Appeal": 60,
}


@dataclass
class ExamResult:
    """One result against one entry."""

    result_id: int | None
    entry_id: int
    student_id: str
    unit_id: str
    grade: str = ""
    marks: int | None = None
    ums: int | None = None           # uniform mark, where the body reports one
    status: str = "provisional"
    released_on: date | None = None
    qualification_type: str = ""
    review_requested: str = ""
    review_outcome: str = ""

    @property
    def achieved(self) -> bool:
        return bool(self.grade) and is_pass(self.grade)

    @property
    def is_final(self) -> bool:
        return self.status in ("confirmed", "amended")

    def review_deadline(self, service: str = "Review of marking") -> date | None:
        """Last date a post-results service can be requested."""
        if self.released_on is None:
            return None
        days = POST_RESULT_SERVICES.get(service)
        if days is None:
            return None
        return self.released_on + timedelta(days=days)

    def can_request(self, service: str, on: date | None = None) -> bool:
        deadline = self.review_deadline(service)
        if deadline is None:
            return False
        return (on or date.today()) <= deadline

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("A result needs a student")
        if not self.unit_id.strip():
            raise ValidationError("A result needs a unit")
        if self.status not in RESULT_STATUSES:
            raise ValidationError(f"Unknown result status '{self.status}'")
        if self.marks is not None and self.marks < 0:
            raise ValidationError("Marks cannot be negative")
        if self.ums is not None and self.ums < 0:
            raise ValidationError("UMS cannot be negative")
        if self.review_requested and self.review_requested not in POST_RESULT_SERVICES:
            raise ValidationError(f"Unknown post-results service '{self.review_requested}'")
        if self.is_final and not self.grade:
            raise ValidationError(f"A {self.status} result must carry a grade")
        if self.grade and self.qualification_type:
            # Reuse the grade-scale rules so an exam result cannot carry a
            # grade its qualification does not use.
            from education_system.systems.fe_college.domain.students.grades import (
                validate_grade,
            )
            validate_grade(self.grade, self.qualification_type)

    def to_row(self) -> dict:
        return {
            "entry_id": int(self.entry_id),
            "student_id": self.student_id.strip(),
            "unit_id": self.unit_id.strip().upper(),
            "grade": self.grade.strip(),
            "marks": self.marks,
            "ums": self.ums,
            "status": self.status,
            "released_on": self.released_on.isoformat() if self.released_on else None,
            "qualification_type": self.qualification_type.strip(),
            "review_requested": self.review_requested.strip(),
            "review_outcome": self.review_outcome.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "ExamResult":
        d = dict(row)
        return cls(
            result_id=d.get("result_id"),
            entry_id=int(d.get("entry_id") or 0),
            student_id=d.get("student_id") or "",
            unit_id=d.get("unit_id") or "",
            grade=d.get("grade") or "",
            marks=d.get("marks"),
            ums=d.get("ums"),
            status=d.get("status") or "provisional",
            released_on=parse_date(d.get("released_on")),
            qualification_type=d.get("qualification_type") or "",
            review_requested=d.get("review_requested") or "",
            review_outcome=d.get("review_outcome") or "",
        )


__all__ = ["POST_RESULT_SERVICES", "RESULT_STATUSES", "ExamResult"]
