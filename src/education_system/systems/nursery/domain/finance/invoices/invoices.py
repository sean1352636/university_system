"""Domain layer for Invoices & Fees (Nursery System).

Owns the ``invoices`` table — fee invoices raised to a child's account. An
invoice's ``total_amount`` is the net of gross fees less the funded-hours
deduction and any discount; the amount paid and outstanding balance are derived
live from ``payments`` rows that reference the invoice, and ``recalc_status``
keeps the invoice status (issued → part_paid → paid) in step.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``invoices_cli.py``, Tk GUI in ``invoices_views.py``.
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

FEATURE_NAME = "Invoices & Fees"
CATEGORY = "Finance"

ID_PREFIX = "NINV"
ID_DIGITS = 3

STATUSES = ("draft", "issued", "part_paid", "paid", "overdue", "void")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid invoice input."""


@dataclass
class Invoice:
    invoice_id: str
    pupil_id: str
    period: str | None
    issue_date: str | None
    due_date: str | None
    hours_billed: float | None
    hourly_rate: float | None
    gross_amount: float
    funded_deduction: float
    discount_amount: float
    total_amount: float
    status: str
    notes: str | None
    child_name: str | None = None
    room: str | None = None
    paid: float = 0.0

    @property
    def balance(self) -> float:
        return round(self.total_amount - self.paid, 2)


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for invoices")
        raise


_SELECT = """
SELECT i.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       (SELECT COALESCE(SUM(amount), 0) FROM payments pay
         WHERE pay.invoice_id = i.invoice_id) AS paid
FROM invoices i
LEFT JOIN pupils p ON p.pupil_id = i.pupil_id
"""


def _row(r: sqlite3.Row) -> Invoice:
    keys = r.keys()
    return Invoice(
        invoice_id=r["invoice_id"],
        pupil_id=r["pupil_id"],
        period=r["period"],
        issue_date=r["issue_date"],
        due_date=r["due_date"],
        hours_billed=r["hours_billed"],
        hourly_rate=r["hourly_rate"],
        gross_amount=r["gross_amount"],
        funded_deduction=r["funded_deduction"],
        discount_amount=r["discount_amount"],
        total_amount=r["total_amount"],
        status=r["status"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        paid=r["paid"] if "paid" in keys else 0.0,
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


def _money(value: Any, label: str, *, default: float = 0.0) -> float:
    raw = str(value if value is not None else "").strip().replace("£", "").replace(",", "")
    if not raw:
        return default
    try:
        n = float(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a number") from e
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    return round(n, 2)


def _opt_money(value: Any, label: str) -> float | None:
    raw = str(value if value is not None else "").strip()
    if not raw:
        return None
    return _money(value, label)


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    out["period"] = _opt(data.get("period"))
    out["issue_date"] = _opt_date(data.get("issue_date"), "Issue date")
    out["due_date"] = _opt_date(data.get("due_date"), "Due date")
    out["hours_billed"] = _opt_money(data.get("hours_billed"), "Hours billed")
    out["hourly_rate"] = _opt_money(data.get("hourly_rate"), "Hourly rate")
    out["gross_amount"] = _money(data.get("gross_amount"), "Gross amount")
    out["funded_deduction"] = _money(data.get("funded_deduction"), "Funded deduction")
    out["discount_amount"] = _money(data.get("discount_amount"), "Discount amount")
    out["total_amount"] = round(
        out["gross_amount"] - out["funded_deduction"] - out["discount_amount"], 2)
    if out["total_amount"] < 0:
        raise ValidationError(
            "Funded deduction + discount exceed the gross amount")

    out["notes"] = _opt(data.get("notes"))
    status = (data.get("status") or "draft").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_invoice_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT invoice_id FROM invoices").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing invoice ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        iid = f"{ID_PREFIX}{n}"
        if iid not in existing:
            return iid
    raise RuntimeError("Could not allocate a unique invoice id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_invoices(*, pupil_id: str | None = None,
                  status: str | None = None) -> list[Invoice]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("i.pupil_id = ?")
        params.append(pupil_id)
    if status:
        clauses.append("i.status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY i.issue_date DESC, i.invoice_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_invoices failed")
        raise
    return [_row(r) for r in rows]


def get_invoice(invoice_id: str) -> Invoice | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE i.invoice_id = ?", (invoice_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_invoice(%s) failed", invoice_id)
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


def summary() -> dict[str, float]:
    invoices = list_invoices()
    billed = sum(i.total_amount for i in invoices if i.status != "void")
    collected = sum(i.paid for i in invoices if i.status != "void")
    outstanding = sum(i.balance for i in invoices
                      if i.status not in ("void", "paid"))
    return {"count": float(len(invoices)), "billed": round(billed, 2),
            "collected": round(collected, 2),
            "outstanding": round(max(outstanding, 0.0), 2)}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_invoice(data: dict[str, Any]) -> Invoice:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    iid = generate_invoice_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO invoices (
                    invoice_id, pupil_id, period, issue_date, due_date,
                    hours_billed, hourly_rate, gross_amount, funded_deduction,
                    discount_amount, total_amount, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (iid, payload["pupil_id"], payload["period"],
                 payload["issue_date"], payload["due_date"],
                 payload["hours_billed"], payload["hourly_rate"],
                 payload["gross_amount"], payload["funded_deduction"],
                 payload["discount_amount"], payload["total_amount"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for invoice id=%s", iid)
        raise ValidationError(f"Could not create invoice — {e}") from e
    inv = get_invoice(iid)
    assert inv is not None
    logger.info("Created invoice %s for pupil %s (£%.2f)",
                iid, payload["pupil_id"], payload["total_amount"])
    return inv


def update_invoice(invoice_id: str, data: dict[str, Any]) -> Invoice:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE invoices SET
                    period = ?, issue_date = ?, due_date = ?, hours_billed = ?,
                    hourly_rate = ?, gross_amount = ?, funded_deduction = ?,
                    discount_amount = ?, total_amount = ?, status = ?, notes = ?
                WHERE invoice_id = ?
                """,
                (payload["period"], payload["issue_date"], payload["due_date"],
                 payload["hours_billed"], payload["hourly_rate"],
                 payload["gross_amount"], payload["funded_deduction"],
                 payload["discount_amount"], payload["total_amount"],
                 payload["status"], payload["notes"], invoice_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No invoice with id {invoice_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for invoice id=%s", invoice_id)
        raise ValidationError(f"Could not update invoice — {e}") from e
    inv = get_invoice(invoice_id)
    assert inv is not None
    logger.info("Updated invoice %s", invoice_id)
    return inv


def delete_invoice(invoice_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM invoices WHERE invoice_id = ?", (invoice_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting invoice id=%s", invoice_id)
        raise
    if deleted:
        logger.info("Deleted invoice %s", invoice_id)
    return deleted


def set_status(invoice_id: str, status: str) -> Invoice:
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE invoices SET status = ? WHERE invoice_id = ?",
                (status, invoice_id))
            if cur.rowcount == 0:
                raise ValidationError(f"No invoice with id {invoice_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting status for invoice %s", invoice_id)
        raise
    inv = get_invoice(invoice_id)
    assert inv is not None
    return inv


def recalc_status(invoice_id: str) -> Invoice | None:
    """Re-derive an invoice's status from the payments allocated to it.

    Called by the Payments module after a payment is recorded or removed.
    """
    inv = get_invoice(invoice_id)
    if inv is None or inv.status == "void":
        return inv
    if inv.total_amount <= 0:
        return inv
    if inv.paid >= inv.total_amount - 0.005:
        new = "paid"
    elif inv.paid > 0:
        new = "part_paid"
    else:
        new = "issued" if inv.status in ("part_paid", "paid") else inv.status
    if new != inv.status:
        return set_status(invoice_id, new)
    return inv
