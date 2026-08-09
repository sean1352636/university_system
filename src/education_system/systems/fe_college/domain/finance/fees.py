"""Fees charged to a learner, and the balance derived from them.

Money is held in pence internally in the repository layer but exposed as a
float here for display; every arithmetic result is rounded to 2dp at the point
it is produced so a balance never drifts by fractions of a penny.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.config import FEE_TYPES
from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

FEE_STATUSES = ("due", "part_paid", "paid", "waived", "written_off", "refunded")

# Statuses where the college is still owed money.
OUTSTANDING_STATUSES = ("due", "part_paid")


@dataclass
class Fee:
    """One charge raised against a learner."""

    fee_id: int | None
    student_id: str
    fee_type: str
    amount: float
    status: str = "due"
    course_id: str = ""
    academic_year: str = ""
    description: str = ""
    due_date: date | None = None
    raised_on: date | None = None
    waiver_reason: str = ""
    amount_paid: float = 0.0         # derived from payments by the repository

    @property
    def balance(self) -> float:
        """Amount still owed on this fee."""
        if self.status in ("paid", "waived", "written_off", "refunded"):
            return 0.0
        return round(max(0.0, self.amount - self.amount_paid), 2)

    @property
    def is_outstanding(self) -> bool:
        return self.status in OUTSTANDING_STATUSES and self.balance > 0

    def is_overdue(self, on: date | None = None) -> bool:
        return bool(self.is_outstanding and self.due_date and self.due_date < (on or date.today()))

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("A fee must be raised against a student")
        if self.fee_type not in FEE_TYPES:
            raise ValidationError(f"Unknown fee type '{self.fee_type}'")
        if self.status not in FEE_STATUSES:
            raise ValidationError(f"Unknown fee status '{self.status}'")
        if self.amount < 0:
            raise ValidationError("A fee cannot be negative — raise a credit note instead")
        if self.amount_paid < 0:
            raise ValidationError("Amount paid cannot be negative")
        if self.amount_paid > self.amount:
            raise ValidationError(
                f"Payments of £{self.amount_paid:.2f} exceed the £{self.amount:.2f} charge"
            )
        if self.status == "waived" and not self.waiver_reason.strip():
            raise ValidationError("A waived fee must record why it was waived")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "fee_type": self.fee_type,
            "amount": round(float(self.amount), 2),
            "status": self.status,
            "course_id": optional_ref(self.course_id.upper()),
            "academic_year": self.academic_year.strip(),
            "description": self.description.strip(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "raised_on": self.raised_on.isoformat() if self.raised_on else None,
            "waiver_reason": self.waiver_reason.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Fee":
        d = dict(row)
        return cls(
            fee_id=d.get("fee_id"),
            student_id=d.get("student_id") or "",
            fee_type=d.get("fee_type") or FEE_TYPES[0],
            amount=float(d.get("amount") or 0),
            status=d.get("status") or "due",
            course_id=d.get("course_id") or "",
            academic_year=d.get("academic_year") or "",
            description=d.get("description") or "",
            due_date=parse_date(d.get("due_date")),
            raised_on=parse_date(d.get("raised_on")),
            waiver_reason=d.get("waiver_reason") or "",
            amount_paid=float(d.get("amount_paid") or 0),
        )


@dataclass(frozen=True)
class FeeAccount:
    """A learner's overall fee position, as shown on their finance tab."""

    student_id: str
    charged: float = 0.0
    paid: float = 0.0
    waived: float = 0.0
    overdue: float = 0.0

    @property
    def balance(self) -> float:
        return round(self.charged - self.paid - self.waived, 2)

    @property
    def is_clear(self) -> bool:
        return self.balance <= 0

    @property
    def status(self) -> str:
        if self.is_clear:
            return "clear"
        if self.overdue > 0:
            return f"£{self.overdue:.2f} overdue"
        return f"£{self.balance:.2f} outstanding"


def summarise(fees: list[Fee], on: date | None = None) -> FeeAccount:
    """Roll a learner's fees up into their account position."""
    if not fees:
        return FeeAccount(student_id="")
    return FeeAccount(
        student_id=fees[0].student_id,
        charged=round(sum(f.amount for f in fees if f.status != "waived"), 2),
        paid=round(sum(f.amount_paid for f in fees), 2),
        waived=round(sum(f.amount for f in fees if f.status == "waived"), 2),
        overdue=round(sum(f.balance for f in fees if f.is_overdue(on)), 2),
    )


__all__ = ["FEE_STATUSES", "OUTSTANDING_STATUSES", "Fee", "FeeAccount", "summarise"]
