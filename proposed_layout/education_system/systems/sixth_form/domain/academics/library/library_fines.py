"""Library fines — charges raised against students and their
settlement (payment / waiver).

A fine starts ``Outstanding`` for its full ``amount``. Payments and
waivers chip away at it via ``amount_paid`` / ``amount_waived``; once
those cover the amount the status becomes ``Paid`` (or ``Waived`` if it
was cleared purely by waiver). ``outstanding`` on each row is the
still-owed remainder.

Overdue fines are raised automatically by ``library.return_loan`` using
the daily rate / per-loan cap from :mod:`library_settings`.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass

from education_system.systems.sixth_form.domain.academics.library import (
    library as _lib,
    library_settings as _settings,
)

logger = logging.getLogger(__name__)

ValidationError = _lib.ValidationError

FINE_REASONS: tuple[str, ...] = ("Overdue", "Damaged", "Lost", "Manual")
OPEN_FINE_STATUSES: tuple[str, ...] = ("Outstanding", "PartPaid")


@dataclass
class Fine:
    fine_id: int
    student_id: str
    loan_id: int | None
    reason: str
    amount: float
    amount_paid: float
    amount_waived: float
    status: str
    note: str | None
    created_at: str
    updated_at: str

    @property
    def outstanding(self) -> float:
        return round(self.amount - self.amount_paid
                     - self.amount_waived, 2)


def _row(r) -> Fine:
    return Fine(
        fine_id=r["fine_id"], student_id=r["student_id"],
        loan_id=r["loan_id"], reason=r["reason"],
        amount=r["amount"], amount_paid=r["amount_paid"],
        amount_waived=r["amount_waived"], status=r["status"],
        note=r["note"], created_at=r["created_at"],
        updated_at=r["updated_at"])


def _status_for(amount: float, paid: float, waived: float) -> str:
    if round(paid + waived, 2) >= round(amount, 2):
        return "Waived" if waived > 0 and paid == 0 else "Paid"
    if paid > 0 or waived > 0:
        return "PartPaid"
    return "Outstanding"


def create_fine(student_id: str, reason: str, amount: float, *,
                loan_id: int | None = None,
                note: str | None = None) -> Fine:
    _lib.init_db()
    sid = (student_id or "").strip()
    if not sid:
        raise ValidationError("Student is required")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    if reason not in FINE_REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(FINE_REASONS)}")
    try:
        amt = round(float(amount), 2)
    except (TypeError, ValueError):
        raise ValidationError("Amount must be a number") from None
    if amt <= 0:
        raise ValidationError("Amount must be greater than zero")
    with _lib._connect() as conn:
        cur = conn.execute(
            "INSERT INTO library_fines "
            "(student_id, loan_id, reason, amount, note, "
            " created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
            (sid, loan_id, reason, amt, (note or "").strip() or None))
        conn.commit()
        fid = cur.lastrowid
    out = get_fine(fid)
    assert out is not None
    logger.info("Raised %s fine #%d for student %s: %.2f",
                reason, fid, sid, amt)
    _notify_fine(out)
    return out


def get_fine(fine_id: int) -> Fine | None:
    _lib.init_db()
    with _lib._connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_fines WHERE fine_id = ?",
            (fine_id,)).fetchone()
    return _row(r) if r else None


def list_fines(*, student_id: str | None = None,
               status: str | None = None,
               loan_id: int | None = None,
               open_only: bool = False) -> list[Fine]:
    _lib.init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        clauses.append("status = ?")
        args.append(status)
    if loan_id is not None:
        clauses.append("loan_id = ?")
        args.append(int(loan_id))
    if open_only:
        clauses.append("status IN ('Outstanding', 'PartPaid')")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _lib._connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM library_fines {where} "
            "ORDER BY CASE status WHEN 'Outstanding' THEN 0 "
            "WHEN 'PartPaid' THEN 1 ELSE 2 END, fine_id DESC",
            args).fetchall()
    return [_row(r) for r in rows]


def student_balance(student_id: str) -> float:
    """Total still owed across a student's open fines."""
    return round(sum(f.outstanding
                     for f in list_fines(student_id=student_id,
                                         open_only=True)), 2)


def _apply(fine_id: int, *, pay: float = 0.0, waive: float = 0.0,
           note: str | None = None) -> Fine:
    fine = get_fine(fine_id)
    if fine is None:
        raise ValidationError(f"No fine #{fine_id}")
    if fine.status in ("Paid", "Waived"):
        raise ValidationError(f"Fine #{fine_id} is already settled")
    pay = round(float(pay), 2)
    waive = round(float(waive), 2)
    if pay < 0 or waive < 0:
        raise ValidationError("Amounts cannot be negative")
    if pay + waive > fine.outstanding + 0.001:
        raise ValidationError(
            f"Cannot apply {pay + waive:.2f} — only "
            f"{fine.outstanding:.2f} is outstanding")
    new_paid = round(fine.amount_paid + pay, 2)
    new_waived = round(fine.amount_waived + waive, 2)
    status = _status_for(fine.amount, new_paid, new_waived)
    merged_note = note.strip() if note and note.strip() else fine.note
    with _lib._connect() as conn:
        conn.execute(
            "UPDATE library_fines SET amount_paid = ?, "
            "amount_waived = ?, status = ?, note = ?, "
            "updated_at = datetime('now') WHERE fine_id = ?",
            (new_paid, new_waived, status, merged_note, fine_id))
        conn.commit()
    out = get_fine(fine_id)
    assert out is not None
    return out


def pay_fine(fine_id: int, amount: float, *,
             note: str | None = None) -> Fine:
    if round(float(amount), 2) <= 0:
        raise ValidationError("Payment must be greater than zero")
    out = _apply(fine_id, pay=amount, note=note)
    logger.info("Recorded payment of %.2f against fine #%d (now %s)",
                amount, fine_id, out.status)
    _notify_settled(out)
    return out


def waive_fine(fine_id: int, *, amount: float | None = None,
               reason: str) -> Fine:
    """Waive ``amount`` (or the full remainder) with a mandatory reason."""
    if not (reason or "").strip():
        raise ValidationError("A reason is required to waive a fine")
    fine = get_fine(fine_id)
    if fine is None:
        raise ValidationError(f"No fine #{fine_id}")
    waive = fine.outstanding if amount is None else round(float(amount), 2)
    if waive <= 0:
        raise ValidationError("Waiver must be greater than zero")
    note = f"Waived: {reason.strip()}"
    if fine.note:
        note = f"{fine.note} | {note}"
    out = _apply(fine_id, waive=waive, note=note)
    logger.info("Waived %.2f of fine #%d (%s) — reason: %s",
                waive, fine_id, out.status, reason.strip())
    _notify_settled(out)
    return out


# ── Automatic charges ─────────────────────────────────────────────

def charge_overdue(loan, returned_on: str) -> Fine | None:
    """Raise an overdue fine for a loan returned after its due date.

    Returns the new ``Fine`` or ``None`` if it wasn't actually late or
    the computed charge rounds to zero.
    """
    try:
        due = _dt.date.fromisoformat(loan.due_on)
        back = _dt.date.fromisoformat(returned_on)
    except ValueError:
        return None
    days_late = (back - due).days
    if days_late <= 0:
        return None
    rate = float(_settings.get_setting("fine_daily_rate"))
    cap = float(_settings.get_setting("fine_max_per_loan"))
    amount = round(min(days_late * rate, cap), 2)
    if amount <= 0:
        return None
    return create_fine(
        loan.student_id, "Overdue", amount, loan_id=loan.loan_id,
        note=f"{days_late} day(s) overdue on loan #{loan.loan_id}")


def _notify_fine(fine: Fine) -> None:
    """Best-effort fine-issued notification (item 18)."""
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_notifications as _notifs,
        )
        _notifs.notify_fine_issued(fine)
    except Exception:
        logger.debug("Fine notification skipped for #%d",
                     fine.fine_id, exc_info=True)


def _notify_settled(fine: Fine) -> None:
    """Best-effort fine-settled receipt (payment / waiver)."""
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_notifications as _notifs,
        )
        _notifs.notify_fine_settled(fine)
    except Exception:
        logger.debug("Settlement notification skipped for #%d",
                     fine.fine_id, exc_info=True)
