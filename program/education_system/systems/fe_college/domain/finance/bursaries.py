"""Bursary awards — financial support paid to learners.

The 16-19 Bursary Fund has two strands: a fixed national amount for defined
vulnerable groups, and a discretionary amount the college sets. Most colleges
also make discretionary payments conditional on attendance, which is why an
award carries an attendance threshold the payments run checks against.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.config import BURSARY_TYPES
from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

BURSARY_STATUSES = ("applied", "approved", "declined", "paying", "completed", "suspended")

# The statutory annual amount for the vulnerable-student bursary.
VULNERABLE_BURSARY_ANNUAL = 1200.00

# Discretionary awards are commonly conditional on this attendance level.
DEFAULT_ATTENDANCE_CONDITION = 90.0


@dataclass
class Bursary:
    """One bursary award to one learner."""

    bursary_id: int | None
    student_id: str
    bursary_type: str
    status: str = "applied"
    amount_awarded: float = 0.0
    amount_paid: float = 0.0
    academic_year: str = ""
    attendance_condition_pct: float = DEFAULT_ATTENDANCE_CONDITION
    applied_on: date | None = None
    decided_on: date | None = None
    decided_by: str = ""             # staff_id
    evidence: str = ""
    notes: str = ""

    @property
    def balance(self) -> float:
        return round(max(0.0, self.amount_awarded - self.amount_paid), 2)

    @property
    def is_live(self) -> bool:
        return self.status in ("approved", "paying")

    @property
    def is_statutory(self) -> bool:
        return self.bursary_type == "Vulnerable Student"

    def meets_condition(self, attendance_pct: float | None) -> bool:
        """Whether the learner's attendance clears the payment condition.

        A statutory vulnerable-student bursary is *not* conditional on
        attendance, so it always passes. Unknown attendance (no marks yet) is
        treated as not meeting the condition, so payment is held for review
        rather than released on no evidence.
        """
        if self.is_statutory:
            return True
        if self.attendance_condition_pct <= 0:
            return True
        if attendance_pct is None:
            return False
        return attendance_pct >= self.attendance_condition_pct

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("A bursary needs a student")
        if self.bursary_type not in BURSARY_TYPES:
            raise ValidationError(f"Unknown bursary type '{self.bursary_type}'")
        if self.status not in BURSARY_STATUSES:
            raise ValidationError(f"Unknown bursary status '{self.status}'")
        if self.amount_awarded < 0:
            raise ValidationError("Award amount cannot be negative")
        if self.amount_paid < 0:
            raise ValidationError("Paid amount cannot be negative")
        if self.amount_paid > self.amount_awarded:
            raise ValidationError(
                f"Payments of £{self.amount_paid:.2f} exceed the £{self.amount_awarded:.2f} award"
            )
        if not (0 <= self.attendance_condition_pct <= 100):
            raise ValidationError("Attendance condition must be between 0 and 100 percent")
        if self.status in ("approved", "declined") and self.decided_on is None:
            raise ValidationError(f"A {self.status} bursary must record its decision date")
        if self.status == "approved" and not self.decided_by.strip():
            raise ValidationError("An approved bursary must record who approved it")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "bursary_type": self.bursary_type,
            "status": self.status,
            "amount_awarded": round(float(self.amount_awarded), 2),
            "amount_paid": round(float(self.amount_paid), 2),
            "academic_year": self.academic_year.strip(),
            "attendance_condition_pct": float(self.attendance_condition_pct),
            "applied_on": self.applied_on.isoformat() if self.applied_on else None,
            "decided_on": self.decided_on.isoformat() if self.decided_on else None,
            "decided_by": optional_ref(self.decided_by),
            "evidence": self.evidence.strip(),
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Bursary":
        d = dict(row)
        return cls(
            bursary_id=d.get("bursary_id"),
            student_id=d.get("student_id") or "",
            bursary_type=d.get("bursary_type") or BURSARY_TYPES[0],
            status=d.get("status") or "applied",
            amount_awarded=float(d.get("amount_awarded") or 0),
            amount_paid=float(d.get("amount_paid") or 0),
            academic_year=d.get("academic_year") or "",
            # 0 means "no attendance condition" and must survive the round
            # trip — only a missing value takes the default.
            attendance_condition_pct=float(
                d["attendance_condition_pct"]
                if d.get("attendance_condition_pct") is not None
                else DEFAULT_ATTENDANCE_CONDITION
            ),
            applied_on=parse_date(d.get("applied_on")),
            decided_on=parse_date(d.get("decided_on")),
            decided_by=d.get("decided_by") or "",
            evidence=d.get("evidence") or "",
            notes=d.get("notes") or "",
        )


__all__ = [
    "BURSARY_STATUSES",
    "DEFAULT_ATTENDANCE_CONDITION",
    "VULNERABLE_BURSARY_ANNUAL",
    "Bursary",
]
