"""Finance persistence: fees, payments, bursaries and funding allocations.

A fee's ``amount_paid`` is never stored — it is summed from the payment ledger
on read. Storing it would give two sources of truth for the same number, and
the one that drifts is always the cached one.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.fe_college.domain.finance.bursaries import Bursary
from education_system.systems.fe_college.domain.finance.fees import Fee, FeeAccount
from education_system.systems.fe_college.domain.finance.funding import FundingAllocation
from education_system.systems.fe_college.domain.finance.payments import Payment
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence import (
    read_only,
    transaction,
)

# Received payments count positive, reversals negative — the same rule the
# domain's ``signed_amount`` applies, expressed once in SQL for the join.
_PAID_SUBQUERY = """
    (SELECT COALESCE(SUM(CASE WHEN p.is_reversal = 1 THEN -p.amount ELSE p.amount END), 0)
       FROM payments p
      WHERE p.fee_id = f.fee_id AND p.status = 'received') AS amount_paid
"""


# ── Fees ────────────────────────────────────────────────────────────────────

def get_fee(fee_id: int) -> Fee | None:
    with read_only() as conn:
        row = conn.execute(
            f"SELECT f.*, {_PAID_SUBQUERY} FROM fees f WHERE f.fee_id = ?", (fee_id,)
        ).fetchone()
    return Fee.from_row(row) if row else None


def list_fees(*, student_id: str | None = None, status: str | None = None,
              course_id: str | None = None,
              outstanding_only: bool = False) -> list[Fee]:
    where, params = [], []
    if student_id:
        where.append("f.student_id = ?")
        params.append(student_id)
    if status:
        where.append("f.status = ?")
        params.append(status)
    if course_id:
        where.append("f.course_id = ?")
        params.append(course_id)
    if outstanding_only:
        where.append("f.status IN ('due', 'part_paid')")
    sql = f"SELECT f.*, {_PAID_SUBQUERY} FROM fees f"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY f.due_date IS NULL, f.due_date, f.fee_id DESC"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Fee.from_row(r) for r in rows]


def raise_fee(fee: Fee) -> Fee:
    fee.validate()
    row = fee.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO fees ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        fee.fee_id = cur.lastrowid
    return fee


def update_fee(fee: Fee) -> Fee:
    if fee.fee_id is None:
        raise ValidationError("Cannot update a fee without an ID")
    fee.validate()
    row = fee.to_row()
    assignments = ", ".join(f"{col} = ?" for col in row)
    with transaction() as conn:
        conn.execute(
            f"UPDATE fees SET {assignments} WHERE fee_id = ?", [*row.values(), fee.fee_id]
        )
    return fee


def account_for(student_id: str, on: date | None = None) -> FeeAccount:
    """A learner's overall fee position."""
    from education_system.systems.fe_college.domain.finance.fees import summarise

    fees = list_fees(student_id=student_id)
    if not fees:
        return FeeAccount(student_id=student_id)
    return summarise(fees, on)


def outstanding_totals() -> dict[str, float]:
    """Headline finance numbers for the admin dashboard, in one query."""
    with read_only() as conn:
        row = conn.execute(
            f"""
            SELECT COALESCE(SUM(f.amount), 0) AS charged,
                   COALESCE(SUM(CASE WHEN f.status = 'waived' THEN f.amount ELSE 0 END), 0)
                       AS waived,
                   COALESCE(SUM(paid.amount_paid), 0) AS paid
            FROM fees f
            LEFT JOIN (SELECT fee_id,
                              SUM(CASE WHEN is_reversal = 1 THEN -amount ELSE amount END)
                                  AS amount_paid
                         FROM payments WHERE status = 'received'
                        GROUP BY fee_id) paid ON paid.fee_id = f.fee_id
            """
        ).fetchone()
    charged = round(row["charged"] or 0, 2)
    waived = round(row["waived"] or 0, 2)
    paid = round(row["paid"] or 0, 2)
    return {
        "charged": charged,
        "paid": paid,
        "waived": waived,
        "outstanding": round(charged - waived - paid, 2),
    }


# ── Payments ────────────────────────────────────────────────────────────────

def list_payments(*, student_id: str | None = None,
                  fee_id: int | None = None) -> list[Payment]:
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if fee_id is not None:
        where.append("fee_id = ?")
        params.append(fee_id)
    sql = "SELECT * FROM payments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY paid_on DESC, payment_id DESC"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Payment.from_row(r) for r in rows]


def record_payment(payment: Payment) -> Payment:
    """Append a payment and re-derive the parent fee's status.

    Both happen in one transaction: a payment that lands without its fee being
    marked paid would show a settled learner as still owing money.
    """
    payment.validate()
    row = payment.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        fee_row = conn.execute(
            "SELECT amount, status FROM fees WHERE fee_id = ?", (payment.fee_id,)
        ).fetchone()
        if fee_row is None:
            raise ValidationError(f"No fee with ID {payment.fee_id}")

        cur = conn.execute(
            f"INSERT INTO payments ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        payment.payment_id = cur.lastrowid

        paid = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN is_reversal = 1 THEN -amount ELSE amount END), 0) "
            "FROM payments WHERE fee_id = ? AND status = 'received'",
            (payment.fee_id,),
        ).fetchone()[0] or 0.0

        amount = float(fee_row["amount"] or 0)
        if fee_row["status"] in ("waived", "written_off"):
            status = fee_row["status"]        # a waiver is not undone by a payment
        elif paid >= amount:
            status = "paid"
        elif paid > 0:
            status = "part_paid"
        else:
            status = "due"
        conn.execute(
            "UPDATE fees SET status = ? WHERE fee_id = ?", (status, payment.fee_id)
        )
    return payment


# ── Bursaries ───────────────────────────────────────────────────────────────

def list_bursaries(*, student_id: str | None = None, status: str | None = None,
                   academic_year: str | None = None) -> list[Bursary]:
    where, params = [], []
    for column, value in (
        ("student_id", student_id), ("status", status), ("academic_year", academic_year)
    ):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    sql = "SELECT * FROM bursaries"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY applied_on DESC, bursary_id DESC"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Bursary.from_row(r) for r in rows]


def save_bursary(bursary: Bursary) -> Bursary:
    bursary.validate()
    row = bursary.to_row()
    if bursary.bursary_id is None:
        placeholders = ", ".join("?" for _ in row)
        with transaction() as conn:
            cur = conn.execute(
                f"INSERT INTO bursaries ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
            bursary.bursary_id = cur.lastrowid
    else:
        assignments = ", ".join(f"{col} = ?" for col in row)
        with transaction() as conn:
            conn.execute(
                f"UPDATE bursaries SET {assignments} WHERE bursary_id = ?",
                [*row.values(), bursary.bursary_id],
            )
    return bursary


def bursary_totals(academic_year: str | None = None) -> dict[str, float]:
    sql = (
        "SELECT COALESCE(SUM(amount_awarded), 0) AS awarded, "
        "COALESCE(SUM(amount_paid), 0) AS paid, COUNT(*) AS learners "
        "FROM bursaries WHERE status IN ('approved', 'paying', 'completed')"
    )
    params: list = []
    if academic_year:
        sql += " AND academic_year = ?"
        params.append(academic_year)
    with read_only() as conn:
        row = conn.execute(sql, params).fetchone()
    return {
        "awarded": round(row["awarded"] or 0, 2),
        "paid": round(row["paid"] or 0, 2),
        "learners": row["learners"] or 0,
    }


# ── Funding allocations ─────────────────────────────────────────────────────

def list_allocations(academic_year: str | None = None) -> list[FundingAllocation]:
    sql = "SELECT * FROM funding_allocations"
    params: list = []
    if academic_year:
        sql += " WHERE academic_year = ?"
        params.append(academic_year)
    sql += " ORDER BY academic_year DESC, funding_source"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [FundingAllocation.from_row(r) for r in rows]


def save_allocation(allocation: FundingAllocation) -> FundingAllocation:
    allocation.validate()
    row = allocation.to_row()
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(
        f"{c} = excluded.{c}" for c in row
        if c not in ("funding_source", "academic_year")
    )
    with transaction() as conn:
        conn.execute(
            f"INSERT INTO funding_allocations ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(funding_source, academic_year) DO UPDATE SET {updates}",
            list(row.values()),
        )
    return allocation


__all__ = [
    "account_for",
    "bursary_totals",
    "get_fee",
    "list_allocations",
    "list_bursaries",
    "list_fees",
    "list_payments",
    "outstanding_totals",
    "raise_fee",
    "record_payment",
    "save_allocation",
    "save_bursary",
    "update_fee",
]
