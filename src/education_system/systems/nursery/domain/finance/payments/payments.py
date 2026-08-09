"""Domain layer for Payments (Nursery System).

Owns the ``payments`` table — money received from families, optionally allocated
to an invoice. Recording or removing a payment against an invoice asks the
Invoices module to re-derive that invoice's status (issued → part_paid → paid).
Payment methods include the Tax-Free Childcare / employer-voucher schemes
registered in the Vouchers module.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``payments_cli.py``, Tk GUI in ``payments_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Payments"
CATEGORY = "Finance"

ID_PREFIX = "NPAY"
ID_DIGITS = 3

METHODS = (
    "Bank transfer", "Card", "Cash", "Standing order", "Direct debit",
    "Childcare voucher (employer)", "Tax-Free Childcare", "Other",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid payment input."""


@dataclass
class Payment:
    payment_id: str
    pupil_id: str
    invoice_id: str | None
    amount: float
    method: str | None
    payment_date: str | None
    reference: str | None
    notes: str | None
    child_name: str | None = None
    invoice_period: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for payments")
        raise


_SELECT = """
SELECT pay.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       inv.period AS invoice_period
FROM payments pay
LEFT JOIN pupils p ON p.pupil_id = pay.pupil_id
LEFT JOIN invoices inv ON inv.invoice_id = pay.invoice_id
"""


def _row(r: sqlite3.Row) -> Payment:
    keys = r.keys()
    return Payment(
        payment_id=r["payment_id"],
        pupil_id=r["pupil_id"],
        invoice_id=r["invoice_id"],
        amount=r["amount"],
        method=r["method"],
        payment_date=r["payment_date"],
        reference=r["reference"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        invoice_period=r["invoice_period"] if "invoice_period" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _money(value: Any, label: str) -> float:
    raw = str(value if value is not None else "").strip().replace("£", "").replace(",", "")
    if not raw:
        raise ValidationError(f"{label} is required")
    try:
        n = float(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a number") from e
    if n <= 0:
        raise ValidationError(f"{label} must be greater than zero")
    return round(n, 2)


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid
    out["invoice_id"] = _opt(data.get("invoice_id"))
    out["amount"] = _money(data.get("amount"), "Amount")
    method = (data.get("method") or "").strip()
    if method and method not in METHODS:
        raise ValidationError("Method must be one of: " + ", ".join(METHODS))
    out["method"] = method or None
    out["payment_date"] = _opt_date(data.get("payment_date"), "Payment date")
    out["reference"] = _opt(data.get("reference"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_payment_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT payment_id FROM payments").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing payment ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        pid = f"{ID_PREFIX}{n}"
        if pid not in existing:
            return pid
    raise RuntimeError("Could not allocate a unique payment id")


def _recalc_invoice(invoice_id: str | None) -> None:
    if not invoice_id:
        return
    try:
        from education_system.systems.nursery.domain.finance.invoices import invoices
        invoices.recalc_status(invoice_id)
    except Exception:
        logger.exception("Could not recalc invoice %s status after payment",
                         invoice_id)


# ── Reads ────────────────────────────────────────────────────────────────────

def list_payments(*, pupil_id: str | None = None,
                  invoice_id: str | None = None) -> list[Payment]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("pay.pupil_id = ?")
        params.append(pupil_id)
    if invoice_id:
        clauses.append("pay.invoice_id = ?")
        params.append(invoice_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY pay.payment_date DESC, pay.payment_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_payments failed")
        raise
    return [_row(r) for r in rows]


def get_payment(payment_id: str) -> Payment | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE pay.payment_id = ?", (payment_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_payment(%s) failed", payment_id)
        raise
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def list_open_invoice_choices(pupil_id: str | None = None) -> list[tuple[str, str]]:
    """Return ``(invoice_id, "id — period £balance")`` for unpaid invoices."""
    try:
        from education_system.systems.nursery.domain.finance.invoices import invoices
        rows = invoices.list_invoices(pupil_id=pupil_id)
    except Exception:
        logger.exception("Could not load invoice choices for payments")
        return []
    out = []
    for inv in rows:
        if inv.status == "void" or inv.balance <= 0:
            continue
        out.append((inv.invoice_id,
                    f"{inv.invoice_id} — {inv.period or '-'} "
                    f"(£{inv.balance:.2f} due)"))
    return out


def summary() -> dict[str, float]:
    payments = list_payments()
    return {"count": float(len(payments)),
            "received": round(sum(p.amount for p in payments), 2)}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_payment(data: dict[str, Any]) -> Payment:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    pid = generate_payment_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            if payload["invoice_id"] and not conn.execute(
                    "SELECT 1 FROM invoices WHERE invoice_id = ?",
                    (payload["invoice_id"],)).fetchone():
                raise ValidationError(
                    f"No invoice with id {payload['invoice_id']}")
            conn.execute(
                """
                INSERT INTO payments (
                    payment_id, pupil_id, invoice_id, amount, method,
                    payment_date, reference, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, payload["pupil_id"], payload["invoice_id"],
                 payload["amount"], payload["method"], payload["payment_date"],
                 payload["reference"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for payment id=%s", pid)
        raise ValidationError(f"Could not record payment — {e}") from e
    _recalc_invoice(payload["invoice_id"])
    pay = get_payment(pid)
    assert pay is not None
    logger.info("Recorded payment %s for pupil %s (£%.2f)",
                pid, payload["pupil_id"], payload["amount"])
    return pay


def update_payment(payment_id: str, data: dict[str, Any]) -> Payment:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_payment(payment_id)
    if existing is None:
        raise ValidationError(f"No payment with id {payment_id}")
    try:
        with connect() as conn:
            if payload["invoice_id"] and not conn.execute(
                    "SELECT 1 FROM invoices WHERE invoice_id = ?",
                    (payload["invoice_id"],)).fetchone():
                raise ValidationError(
                    f"No invoice with id {payload['invoice_id']}")
            conn.execute(
                """
                UPDATE payments SET
                    invoice_id = ?, amount = ?, method = ?, payment_date = ?,
                    reference = ?, notes = ?
                WHERE payment_id = ?
                """,
                (payload["invoice_id"], payload["amount"], payload["method"],
                 payload["payment_date"], payload["reference"],
                 payload["notes"], payment_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for payment id=%s", payment_id)
        raise ValidationError(f"Could not update payment — {e}") from e
    # Recalc both the old and new invoice (allocation may have moved).
    _recalc_invoice(existing.invoice_id)
    if payload["invoice_id"] != existing.invoice_id:
        _recalc_invoice(payload["invoice_id"])
    pay = get_payment(payment_id)
    assert pay is not None
    logger.info("Updated payment %s", payment_id)
    return pay


def delete_payment(payment_id: str) -> bool:
    _ensure_schema()
    existing = get_payment(payment_id)
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM payments WHERE payment_id = ?", (payment_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting payment id=%s", payment_id)
        raise
    if deleted:
        _recalc_invoice(existing.invoice_id if existing else None)
        logger.info("Deleted payment %s", payment_id)
    return deleted
