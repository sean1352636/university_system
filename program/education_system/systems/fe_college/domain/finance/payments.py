"""Payments received against fees.

Payments are append-only: a mistake is corrected with a reversal row, never by
editing or deleting the original. That is what makes the ledger auditable, and
it is enforced by the repository refusing to update a payment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.config import PAYMENT_METHODS
from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

PAYMENT_STATUSES = ("received", "pending", "failed", "refunded", "reversed")


@dataclass
class Payment:
    """One payment (or reversal) against a fee."""

    payment_id: int | None
    fee_id: int
    student_id: str
    amount: float
    method: str = "Card"
    status: str = "received"
    paid_on: date | None = None
    reference: str = ""
    received_by: str = ""            # staff_id, blank for online payments
    is_reversal: bool = False
    note: str = ""

    @property
    def counts_towards_balance(self) -> bool:
        """Whether this row moves the learner's balance."""
        return self.status == "received"

    @property
    def signed_amount(self) -> float:
        """Amount as it affects the balance — negative for a reversal."""
        if not self.counts_towards_balance:
            return 0.0
        return round(-self.amount if self.is_reversal else self.amount, 2)

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("A payment must belong to a student")
        if self.method not in PAYMENT_METHODS:
            raise ValidationError(f"Unknown payment method '{self.method}'")
        if self.status not in PAYMENT_STATUSES:
            raise ValidationError(f"Unknown payment status '{self.status}'")
        if self.amount <= 0:
            raise ValidationError(
                "Payment amount must be positive — record a refund as a reversal"
            )
        if self.is_reversal and not self.note.strip():
            raise ValidationError("A reversal must record why it was made")
        if self.paid_on and self.paid_on > date.today():
            raise ValidationError("A payment cannot be dated in the future")

    def to_row(self) -> dict:
        return {
            "fee_id": int(self.fee_id),
            "student_id": self.student_id.strip(),
            "amount": round(float(self.amount), 2),
            "method": self.method,
            "status": self.status,
            "paid_on": self.paid_on.isoformat() if self.paid_on else None,
            "reference": self.reference.strip(),
            "received_by": optional_ref(self.received_by),
            "is_reversal": 1 if self.is_reversal else 0,
            "note": self.note.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Payment":
        d = dict(row)
        return cls(
            payment_id=d.get("payment_id"),
            fee_id=int(d.get("fee_id") or 0),
            student_id=d.get("student_id") or "",
            amount=float(d.get("amount") or 0),
            method=d.get("method") or "Card",
            status=d.get("status") or "received",
            paid_on=parse_date(d.get("paid_on")),
            reference=d.get("reference") or "",
            received_by=d.get("received_by") or "",
            is_reversal=bool(d.get("is_reversal")),
            note=d.get("note") or "",
        )


def total_paid(payments: list[Payment]) -> float:
    """Net amount received, after reversals."""
    return round(sum(p.signed_amount for p in payments), 2)


def instalment_plan(amount: float, instalments: int, first_due: date,
                    interval_days: int = 30) -> list[tuple[date, float]]:
    """Split an amount into equal instalments, remainder on the first.

    Putting the rounding remainder on the *first* instalment rather than the
    last means the final payment is never an odd amount, which is what learners
    query. £100 over 3 becomes £33.34, £33.33, £33.33.
    """
    if instalments <= 0:
        raise ValidationError("An instalment plan needs at least one instalment")
    if amount <= 0:
        raise ValidationError("An instalment plan needs a positive amount")
    from datetime import timedelta

    pence = round(amount * 100)
    base, remainder = divmod(pence, instalments)
    plan: list[tuple[date, float]] = []
    for i in range(instalments):
        due = first_due + timedelta(days=interval_days * i)
        value = base + (remainder if i == 0 else 0)
        plan.append((due, round(value / 100, 2)))
    return plan


__all__ = ["PAYMENT_STATUSES", "Payment", "instalment_plan", "total_paid"]
