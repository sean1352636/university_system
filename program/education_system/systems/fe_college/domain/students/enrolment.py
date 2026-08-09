"""Enrolments — the link between a learner and a course.

A learner's *study programme* is the set of enrolments they hold in a year: a
main vocational qualification plus, for 16-18 learners without a grade 4, a
compulsory English and/or maths resit. The rules that make a programme valid
live here rather than in the service layer, so both the GUI and the CLI enforce
them identically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    parse_date,
)

ENROLMENT_STATUSES = ("active", "withdrawn", "completed", "transferred", "deferred")

# Withdrawal reasons follow the ESFA withdrawal codes a college must report.
WITHDRAWAL_REASONS = (
    "Transferred to another course",
    "Left for employment",
    "Personal / health reasons",
    "Financial reasons",
    "Non-attendance",
    "Behaviour / exclusion",
    "Moved away",
    "Other",
)


@dataclass
class Enrolment:
    """One learner on one course for one academic year."""

    enrolment_id: int | None
    student_id: str
    course_id: str
    academic_year: str
    status: str = "active"
    is_main_aim: bool = True
    start_date: date | None = None
    end_date: date | None = None
    expected_end_date: date | None = None
    withdrawal_reason: str = ""
    funding_source: str = ""
    predicted_grade: str = ""
    final_grade: str = ""
    created_at: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("Enrolment needs a student")
        if not self.course_id.strip():
            raise ValidationError("Enrolment needs a course")
        if not self.academic_year.strip():
            raise ValidationError("Enrolment needs an academic year")
        if self.status not in ENROLMENT_STATUSES:
            raise ValidationError(f"Unknown enrolment status '{self.status}'")
        if self.status == "withdrawn" and not self.withdrawal_reason.strip():
            raise ValidationError("A withdrawal must record a reason")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Enrolment end date cannot be before its start date")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "course_id": self.course_id.strip(),
            "academic_year": self.academic_year.strip(),
            "status": self.status,
            "is_main_aim": 1 if self.is_main_aim else 0,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "expected_end_date": (
                self.expected_end_date.isoformat() if self.expected_end_date else None
            ),
            "withdrawal_reason": self.withdrawal_reason.strip(),
            "funding_source": self.funding_source.strip(),
            "predicted_grade": self.predicted_grade.strip(),
            "final_grade": self.final_grade.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Enrolment":
        d = dict(row)
        return cls(
            enrolment_id=d.get("enrolment_id"),
            student_id=d.get("student_id") or "",
            course_id=d.get("course_id") or "",
            academic_year=d.get("academic_year") or "",
            status=d.get("status") or "active",
            is_main_aim=bool(d.get("is_main_aim", 1)),
            start_date=parse_date(d.get("start_date")),
            end_date=parse_date(d.get("end_date")),
            expected_end_date=parse_date(d.get("expected_end_date")),
            withdrawal_reason=d.get("withdrawal_reason") or "",
            funding_source=d.get("funding_source") or "",
            predicted_grade=d.get("predicted_grade") or "",
            final_grade=d.get("final_grade") or "",
            created_at=d.get("created_at") or "",
        )


def check_study_programme(enrolments: list[Enrolment]) -> list[str]:
    """Return human-readable warnings about a learner's study programme.

    Warnings, not errors: a college can legitimately hold an unusual programme
    (a mid-year transfer, an evening-only adult learner), so these surface in
    the UI as advice rather than blocking the save.
    """
    active = [e for e in enrolments if e.is_active]
    warnings: list[str] = []
    if not active:
        return ["Learner has no active enrolment."]

    main_aims = [e for e in active if e.is_main_aim]
    if not main_aims:
        warnings.append("No main learning aim — one enrolment should be the main aim.")
    elif len(main_aims) > 1:
        warnings.append(
            f"{len(main_aims)} enrolments are flagged as the main aim — only one should be."
        )

    years = {e.academic_year for e in active}
    if len(years) > 1:
        warnings.append(
            "Active enrolments span more than one academic year: " + ", ".join(sorted(years))
        )

    seen: set[tuple[str, str]] = set()
    for e in active:
        key = (e.course_id, e.academic_year)
        if key in seen:
            warnings.append(f"Duplicate active enrolment on {e.course_id} for {e.academic_year}.")
        seen.add(key)
    return warnings


__all__ = [
    "ENROLMENT_STATUSES",
    "WITHDRAWAL_REASONS",
    "Enrolment",
    "check_study_programme",
]
