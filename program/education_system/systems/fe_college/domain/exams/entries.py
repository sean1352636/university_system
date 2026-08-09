"""Exam entries — learners attached to a sitting.

An entry is a financial as well as an academic act: the college is invoiced by
the awarding body per entry, and a withdrawal after the deadline is still
charged. The fee logic lives here so the finance screen and the exams screen
never disagree about what is owed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.exams.models import LATE_ENTRY_FEE
from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    parse_date,
)

ENTRY_STATUSES = ("entered", "late_entry", "withdrawn", "absent", "sat", "cancelled")

ENTRY_TYPES = ("First entry", "Resit", "Cash-in", "Carry-forward")


@dataclass
class ExamEntry:
    """One learner entered for one sitting."""

    entry_id: int | None
    sitting_id: int
    student_id: str
    status: str = "entered"
    entry_type: str = "First entry"
    entered_on: date | None = None
    candidate_number: str = ""
    seat_number: str = ""
    fee: float = 0.0
    access_arrangement_id: int | None = None

    @property
    def is_active(self) -> bool:
        return self.status in ("entered", "late_entry")

    @property
    def is_chargeable(self) -> bool:
        """Whether the college is invoiced for this entry.

        A cancelled entry (made in error, pulled before the deadline) is not
        charged. Everything else is — including a withdrawal or a no-show,
        because the awarding body has already registered the candidate.
        """
        return self.status != "cancelled"

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("An exam entry needs a student")
        if self.status not in ENTRY_STATUSES:
            raise ValidationError(f"Unknown entry status '{self.status}'")
        if self.entry_type not in ENTRY_TYPES:
            raise ValidationError(f"Unknown entry type '{self.entry_type}'")
        if self.fee < 0:
            raise ValidationError("Entry fee cannot be negative")

    def to_row(self) -> dict:
        return {
            "sitting_id": int(self.sitting_id),
            "student_id": self.student_id.strip(),
            "status": self.status,
            "entry_type": self.entry_type,
            "entered_on": self.entered_on.isoformat() if self.entered_on else None,
            "candidate_number": self.candidate_number.strip(),
            "seat_number": self.seat_number.strip(),
            "fee": float(self.fee),
            "access_arrangement_id": self.access_arrangement_id,
        }

    @classmethod
    def from_row(cls, row) -> "ExamEntry":
        d = dict(row)
        return cls(
            entry_id=d.get("entry_id"),
            sitting_id=int(d.get("sitting_id") or 0),
            student_id=d.get("student_id") or "",
            status=d.get("status") or "entered",
            entry_type=d.get("entry_type") or "First entry",
            entered_on=parse_date(d.get("entered_on")),
            candidate_number=d.get("candidate_number") or "",
            seat_number=d.get("seat_number") or "",
            fee=float(d.get("fee") or 0),
            access_arrangement_id=d.get("access_arrangement_id"),
        )


def entry_fee(base_fee: float, *, is_late: bool, is_resit: bool = False) -> float:
    """Total fee for an entry, including the late surcharge.

    A resit is charged at the full unit fee — awarding bodies do not discount
    them — so the flag exists for the invoice narrative rather than the amount.
    """
    fee = max(0.0, float(base_fee))
    if is_late:
        fee += LATE_ENTRY_FEE
    return round(fee, 2)


__all__ = ["ENTRY_STATUSES", "ENTRY_TYPES", "ExamEntry", "entry_fee"]
