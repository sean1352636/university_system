"""Submissions — what a learner hands in against an assignment.

The lifecycle matters for FE quality assurance: a submission is *submitted*,
then *marked*, and may then be *referred* for one resubmission. A referred
submission that is resubmitted and passed is capped at a Pass under most
awarding-body rules, which the marking screen has to make visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

SUBMISSION_STATUSES = (
    "not_submitted",
    "submitted",
    "late",
    "marked",
    "referred",
    "resubmitted",
    "not_attempted",
)

# Statuses a lecturer can act on from the marking queue.
MARKABLE_STATUSES = ("submitted", "late", "resubmitted")


@dataclass
class Submission:
    """One learner's submission against one assignment."""

    submission_id: int | None
    assignment_id: int
    student_id: str
    status: str = "not_submitted"
    submitted_at: date | None = None
    marked_at: date | None = None
    marked_by: str = ""              # staff_id
    grade: str = ""
    marks: int | None = None
    is_resubmission: bool = False
    file_ref: str = ""               # relative path under FE_COLLEGE_SUBMISSIONS_DIR
    feedback: str = ""

    @property
    def awaits_marking(self) -> bool:
        return self.status in MARKABLE_STATUSES and not self.grade

    @property
    def is_capped(self) -> bool:
        """Whether awarding-body rules cap this submission at a Pass."""
        return self.is_resubmission

    def is_late(self, due: date | None) -> bool:
        if due is None or self.submitted_at is None:
            return False
        return self.submitted_at > due

    def validate(self, max_marks: int | None = None) -> None:
        if not self.student_id.strip():
            raise ValidationError("A submission needs a student")
        if self.status not in SUBMISSION_STATUSES:
            raise ValidationError(f"Unknown submission status '{self.status}'")
        if self.marks is not None and self.marks < 0:
            raise ValidationError("Marks cannot be negative")
        if max_marks and self.marks is not None and self.marks > max_marks:
            raise ValidationError(f"Marks cannot exceed the assignment maximum of {max_marks}")
        if self.status in ("submitted", "late", "resubmitted") and self.submitted_at is None:
            raise ValidationError("A submitted piece of work must have a submission date")
        if self.status == "marked" and not self.grade:
            raise ValidationError("A marked submission must carry a grade")
        if self.grade and self.marked_by == "":
            raise ValidationError("A graded submission must record who marked it")
        if self.submitted_at and self.marked_at and self.marked_at < self.submitted_at:
            raise ValidationError("A submission cannot be marked before it was submitted")

    def to_row(self) -> dict:
        return {
            "assignment_id": int(self.assignment_id),
            "student_id": self.student_id.strip(),
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "marked_at": self.marked_at.isoformat() if self.marked_at else None,
            "marked_by": optional_ref(self.marked_by),
            "grade": self.grade.strip(),
            "marks": self.marks,
            "is_resubmission": 1 if self.is_resubmission else 0,
            "file_ref": self.file_ref.strip(),
            "feedback": self.feedback.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Submission":
        d = dict(row)
        return cls(
            submission_id=d.get("submission_id"),
            assignment_id=int(d.get("assignment_id") or 0),
            student_id=d.get("student_id") or "",
            status=d.get("status") or "not_submitted",
            submitted_at=parse_date(d.get("submitted_at")),
            marked_at=parse_date(d.get("marked_at")),
            marked_by=d.get("marked_by") or "",
            grade=d.get("grade") or "",
            marks=d.get("marks"),
            is_resubmission=bool(d.get("is_resubmission")),
            file_ref=d.get("file_ref") or "",
            feedback=d.get("feedback") or "",
        )


@dataclass(frozen=True)
class SubmissionStats:
    """Hand-in position for one assignment, shown above the marking queue."""

    expected: int = 0
    submitted: int = 0
    late: int = 0
    marked: int = 0
    referred: int = 0
    missing: int = 0

    @property
    def submission_rate(self) -> float | None:
        if self.expected <= 0:
            return None
        return round(self.submitted / self.expected * 100, 1)

    @property
    def marking_progress(self) -> float | None:
        if self.submitted <= 0:
            return None
        return round(self.marked / self.submitted * 100, 1)


__all__ = [
    "MARKABLE_STATUSES",
    "SUBMISSION_STATUSES",
    "Submission",
    "SubmissionStats",
]
