"""Expense Claims data layer for Secondary School System.

Staff and student expense reimbursement claims. A `Claim`
header rolls up many `ClaimLine` items. Claims move through
Draft → Submitted → Approved → Paid (or Rejected / Cancelled).
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.secondarysch_system.core import paths as _paths

logger = logging.getLogger(__name__)

CLAIMANT_TYPES: tuple[str, ...] = (
    "Staff",
    "Student",
    "Governor",
    "Contractor",
    "Volunteer",
    "Other",
)
DEFAULT_CLAIMANT_TYPE = "Staff"

CATEGORIES: tuple[str, ...] = (
    "Travel",
    "Mileage",
    "Subsistence",
    "Accommodation",
    "Conference / CPD",
    "Books / Materials",
    "Equipment",
    "Software",
    "Stationery",
    "Postage",
    "Hospitality",
    "Trip / Visit",
    "Uniform",
    "PPE",
    "Other",
)
DEFAULT_CATEGORY = "Travel"

PAYMENT_METHODS: tuple[str, ...] = (
    "BACS",
    "Cheque",
    "Cash",
    "Payroll",
    "Petty Cash",
    "Card",
    "Other",
)
DEFAULT_PAYMENT_METHOD = "BACS"

CLAIM_STATUSES: tuple[str, ...] = (
    "Draft",
    "Submitted",
    "Under Review",
    "Approved",
    "Rejected",
    "Paid",
    "Cancelled",
)
DEFAULT_CLAIM_STATUS = "Draft"


class ValidationError(Exception):
    pass


@dataclass
class Claim:
    claim_id: int
    claim_ref: str
    claimant_type: str
    claimant_id: str
    claimant_name: str | None
    department: str | None
    title: str
    description: str | None
    purpose: str | None
    category: str
    incurred_from: str | None
    incurred_to: str | None
    submitted_on: str | None
    approved_on: str | None
    approved_by: str | None
    rejected_on: str | None
    rejection_reason: str | None
    paid_on: str | None
    payment_method: str
    payment_reference: str | None
    status: str
    line_count: int
    total_amount: float
    receipts_attached: bool
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status in ("Draft", "Submitted",
                                       "Under Review")

    @property
    def is_settled(self) -> bool:
        return self.status in ("Paid", "Rejected",
                                       "Cancelled")


@dataclass
class ClaimLine:
    line_id: int
    claim_id: int
    incurred_on: str
    category: str
    description: str | None
    supplier: str | None
    receipt_ref: str | None
    quantity: float
    unit_amount: float
    mileage_miles: float | None
    mileage_rate: float | None
    vat_amount: float
    net_amount: float
    gross_amount: float
    notes: str | None
    created_on: str
    updated_on: str


@dataclass
class ExpenseClaimsSummary:
    total_claims: int = 0
    drafts: int = 0
    submitted: int = 0
    under_review: int = 0
    approved: int = 0
    paid: int = 0
    rejected: int = 0
    cancelled: int = 0
    total_value: float = 0.0
    awaiting_payment_value: float = 0.0
    paid_value: float = 0.0
    distinct_claimants: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_claimant_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_payment_method: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.EXPENSE_CLAIMS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS expense_claims (
              claim_id           INTEGER PRIMARY KEY AUTOINCREMENT,
              claim_ref          TEXT NOT NULL UNIQUE,
              claimant_type      TEXT NOT NULL,
              claimant_id        TEXT NOT NULL,
              claimant_name      TEXT,
              department         TEXT,
              title              TEXT NOT NULL,
              description        TEXT,
              purpose            TEXT,
              category           TEXT NOT NULL,
              incurred_from      TEXT,
              incurred_to        TEXT,
              submitted_on       TEXT,
              approved_on        TEXT,
              approved_by        TEXT,
              rejected_on        TEXT,
              rejection_reason   TEXT,
              paid_on            TEXT,
              payment_method     TEXT NOT NULL,
              payment_reference  TEXT,
              status             TEXT NOT NULL,
              line_count         INTEGER NOT NULL DEFAULT 0,
              total_amount       REAL NOT NULL DEFAULT 0,
              receipts_attached  INTEGER NOT NULL DEFAULT 0,
              notes              TEXT,
              created_on         TEXT NOT NULL,
              updated_on         TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_claims_claimant
              ON expense_claims(claimant_type, claimant_id);
            CREATE INDEX IF NOT EXISTS ix_claims_status
              ON expense_claims(status);

            CREATE TABLE IF NOT EXISTS expense_claim_lines (
              line_id        INTEGER PRIMARY KEY AUTOINCREMENT,
              claim_id       INTEGER NOT NULL REFERENCES expense_claims(claim_id) ON DELETE CASCADE,
              incurred_on    TEXT NOT NULL,
              category       TEXT NOT NULL,
              description    TEXT,
              supplier       TEXT,
              receipt_ref    TEXT,
              quantity       REAL NOT NULL DEFAULT 1,
              unit_amount    REAL NOT NULL DEFAULT 0,
              mileage_miles  REAL,
              mileage_rate   REAL,
              vat_amount     REAL NOT NULL DEFAULT 0,
              net_amount     REAL NOT NULL DEFAULT 0,
              gross_amount   REAL NOT NULL DEFAULT 0,
              notes          TEXT,
              created_on     TEXT NOT NULL,
              updated_on     TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_claim_lines_claim
              ON expense_claim_lines(claim_id);
        """)


def _check_date(label: str, value: str | None) -> None:
    if not value:
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(
            f"{label} must be YYYY-MM-DD")


def _opt_float(out: dict, key: str, label: str, *,
                  default: float | None = 0.0,
                  allow_negative: bool = False) -> None:
    v = out.get(key)
    if v in (None, ""):
        out[key] = default
        return
    try:
        out[key] = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number")
    if not allow_negative and out[key] < 0:
        raise ValidationError(f"{label} must be >= 0")


def _validate_claim(p: dict[str, Any], *,
                          existing_id: int | None = None
                          ) -> dict[str, Any]:
    out = dict(p)
    out["claim_ref"] = (out.get("claim_ref") or "").strip()
    if not out["claim_ref"]:
        raise ValidationError("Claim reference is required")

    ct = (out.get("claimant_type")
            or DEFAULT_CLAIMANT_TYPE).strip()
    if ct not in CLAIMANT_TYPES:
        raise ValidationError(
            f"Claimant type must be one of: "
            f"{', '.join(CLAIMANT_TYPES)}")
    out["claimant_type"] = ct

    out["claimant_id"] = (out.get("claimant_id") or "").strip()
    if not out["claimant_id"]:
        raise ValidationError("Claimant id is required")

    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")

    cat = (out.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    pm = (out.get("payment_method")
            or DEFAULT_PAYMENT_METHOD).strip()
    if pm not in PAYMENT_METHODS:
        raise ValidationError(
            f"Payment method must be one of: "
            f"{', '.join(PAYMENT_METHODS)}")
    out["payment_method"] = pm

    status = (out.get("status") or DEFAULT_CLAIM_STATUS).strip()
    if status not in CLAIM_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(CLAIM_STATUSES)}")
    out["status"] = status

    for k, lbl in (
            ("incurred_from", "Incurred from"),
            ("incurred_to", "Incurred to"),
            ("submitted_on", "Submitted on"),
            ("approved_on", "Approved on"),
            ("rejected_on", "Rejected on"),
            ("paid_on", "Paid on")):
        _check_date(lbl, out.get(k))

    if (out.get("incurred_from") and out.get("incurred_to")
            and out["incurred_to"] < out["incurred_from"]):
        raise ValidationError(
            "Incurred to cannot be before incurred from")

    _opt_float(out, "total_amount", "Total amount")

    lc = out.get("line_count")
    if lc in (None, ""):
        out["line_count"] = 0
    else:
        try:
            out["line_count"] = int(lc)
        except (TypeError, ValueError):
            raise ValidationError(
                "Line count must be an integer")
        if out["line_count"] < 0:
            raise ValidationError(
                "Line count must be >= 0")

    out["receipts_attached"] = bool(out.get("receipts_attached"))

    for k in ("claimant_name", "department", "description",
               "purpose", "approved_by", "rejection_reason",
               "payment_reference", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("incurred_from", "incurred_to", "submitted_on",
               "approved_on", "rejected_on", "paid_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None
                    if isinstance(v, str) else v)

    # Unique claim_ref
    with _connect() as conn:
        row = conn.execute(
            "SELECT claim_id FROM expense_claims "
            "WHERE claim_ref=?",
            (out["claim_ref"],)).fetchone()
    if row and row["claim_id"] != existing_id:
        raise ValidationError(
            f"A claim with ref {out['claim_ref']!r} "
            "already exists")
    return out


def _validate_line(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["incurred_on"] = (out.get("incurred_on") or "").strip()
    if not out["incurred_on"]:
        raise ValidationError("Incurred on is required")
    _check_date("Incurred on", out["incurred_on"])

    cat = (out.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    _opt_float(out, "quantity", "Quantity", default=1.0)
    _opt_float(out, "unit_amount", "Unit amount")
    _opt_float(out, "vat_amount", "VAT amount")
    _opt_float(out, "mileage_miles", "Mileage miles",
                  default=None)
    _opt_float(out, "mileage_rate", "Mileage rate",
                  default=None)

    # Auto-compute net/gross
    if (out.get("mileage_miles") is not None
            and out.get("mileage_rate") is not None):
        out["net_amount"] = round(
            out["mileage_miles"] * out["mileage_rate"], 2)
    else:
        out["net_amount"] = round(
            out["quantity"] * out["unit_amount"], 2)
    out["gross_amount"] = round(
        out["net_amount"] + (out.get("vat_amount") or 0.0), 2)

    for k in ("description", "supplier", "receipt_ref",
               "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    return out


def _row_claim(r: sqlite3.Row) -> Claim:
    return Claim(
        claim_id=r["claim_id"],
        claim_ref=r["claim_ref"],
        claimant_type=r["claimant_type"],
        claimant_id=r["claimant_id"],
        claimant_name=r["claimant_name"],
        department=r["department"],
        title=r["title"],
        description=r["description"],
        purpose=r["purpose"],
        category=r["category"],
        incurred_from=r["incurred_from"],
        incurred_to=r["incurred_to"],
        submitted_on=r["submitted_on"],
        approved_on=r["approved_on"],
        approved_by=r["approved_by"],
        rejected_on=r["rejected_on"],
        rejection_reason=r["rejection_reason"],
        paid_on=r["paid_on"],
        payment_method=r["payment_method"],
        payment_reference=r["payment_reference"],
        status=r["status"],
        line_count=r["line_count"],
        total_amount=r["total_amount"],
        receipts_attached=bool(r["receipts_attached"]),
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def _row_line(r: sqlite3.Row) -> ClaimLine:
    return ClaimLine(
        line_id=r["line_id"],
        claim_id=r["claim_id"],
        incurred_on=r["incurred_on"],
        category=r["category"],
        description=r["description"],
        supplier=r["supplier"],
        receipt_ref=r["receipt_ref"],
        quantity=r["quantity"],
        unit_amount=r["unit_amount"],
        mileage_miles=r["mileage_miles"],
        mileage_rate=r["mileage_rate"],
        vat_amount=r["vat_amount"],
        net_amount=r["net_amount"],
        gross_amount=r["gross_amount"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


# ── CRUD: claims ─────────────────────────────────────────

def create_claim(payload: dict[str, Any]) -> Claim:
    init_db()
    p = _validate_claim(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO expense_claims (
              claim_ref, claimant_type, claimant_id,
              claimant_name, department, title, description,
              purpose, category, incurred_from, incurred_to,
              submitted_on, approved_on, approved_by,
              rejected_on, rejection_reason, paid_on,
              payment_method, payment_reference, status,
              line_count, total_amount, receipts_attached,
              notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["claim_ref"], p["claimant_type"],
            p["claimant_id"], p["claimant_name"],
            p["department"], p["title"], p["description"],
            p["purpose"], p["category"],
            p["incurred_from"], p["incurred_to"],
            p["submitted_on"], p["approved_on"],
            p["approved_by"], p["rejected_on"],
            p["rejection_reason"], p["paid_on"],
            p["payment_method"], p["payment_reference"],
            p["status"], p["line_count"], p["total_amount"],
            1 if p["receipts_attached"] else 0,
            p["notes"], now, now,
        ))
        cid = cur.lastrowid
    return get_claim(cid)  # type: ignore[return-value]


def update_claim(claim_id: int,
                       payload: dict[str, Any]) -> Claim:
    init_db()
    if get_claim(claim_id) is None:
        raise ValidationError(f"No claim with id {claim_id}")
    p = _validate_claim(payload, existing_id=claim_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE expense_claims SET
              claim_ref=?, claimant_type=?, claimant_id=?,
              claimant_name=?, department=?, title=?,
              description=?, purpose=?, category=?,
              incurred_from=?, incurred_to=?, submitted_on=?,
              approved_on=?, approved_by=?, rejected_on=?,
              rejection_reason=?, paid_on=?,
              payment_method=?, payment_reference=?,
              status=?, line_count=?, total_amount=?,
              receipts_attached=?, notes=?, updated_on=?
            WHERE claim_id=?
        """, (
            p["claim_ref"], p["claimant_type"],
            p["claimant_id"], p["claimant_name"],
            p["department"], p["title"], p["description"],
            p["purpose"], p["category"],
            p["incurred_from"], p["incurred_to"],
            p["submitted_on"], p["approved_on"],
            p["approved_by"], p["rejected_on"],
            p["rejection_reason"], p["paid_on"],
            p["payment_method"], p["payment_reference"],
            p["status"], p["line_count"], p["total_amount"],
            1 if p["receipts_attached"] else 0,
            p["notes"], now, claim_id,
        ))
    return get_claim(claim_id)  # type: ignore[return-value]


def delete_claim(claim_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM expense_claims WHERE claim_id=?",
            (claim_id,))
        return cur.rowcount > 0


def get_claim(claim_id: int) -> Claim | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM expense_claims WHERE claim_id=?",
            (claim_id,)).fetchone()
    return _row_claim(r) if r else None


def get_claim_by_ref(claim_ref: str) -> Claim | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM expense_claims WHERE claim_ref=?",
            (claim_ref,)).fetchone()
    return _row_claim(r) if r else None


def list_claims(*,
                     claimant_type: str | None = None,
                     claimant_id: str | None = None,
                     status: str | None = None,
                     category: str | None = None,
                     payment_method: str | None = None,
                     open_only: bool = False,
                     awaiting_payment_only: bool = False,
                     paid_only: bool = False,
                     title_like: str | None = None,
                     date_from: str | None = None,
                     date_to: str | None = None,
                     ) -> list[Claim]:
    init_db()
    sql = "SELECT * FROM expense_claims WHERE 1=1"
    params: list[Any] = []
    if claimant_type:
        sql += " AND claimant_type=?"
        params.append(claimant_type)
    if claimant_id:
        sql += " AND claimant_id=?"
        params.append(claimant_id)
    if status:
        sql += " AND status=?"
        params.append(status)
    if category:
        sql += " AND category=?"
        params.append(category)
    if payment_method:
        sql += " AND payment_method=?"
        params.append(payment_method)
    if open_only:
        sql += (" AND status IN "
                  "('Draft','Submitted','Under Review')")
    if awaiting_payment_only:
        sql += " AND status='Approved'"
    if paid_only:
        sql += " AND status='Paid'"
    if title_like:
        sql += " AND title LIKE ?"
        params.append(f"%{title_like}%")
    if date_from:
        _check_date("From", date_from)
        sql += (" AND (incurred_from >= ?"
                  " OR submitted_on >= ?)")
        params.extend([date_from, date_from])
    if date_to:
        _check_date("To", date_to)
        sql += (" AND (incurred_to <= ?"
                  " OR submitted_on <= ?)")
        params.extend([date_to, date_to])
    sql += (" ORDER BY COALESCE(submitted_on, created_on)"
              " DESC, claim_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_claim(r) for r in rows]


# ── CRUD: lines ──────────────────────────────────────────

def add_line(claim_id: int,
                  payload: dict[str, Any]) -> ClaimLine:
    init_db()
    if get_claim(claim_id) is None:
        raise ValidationError(f"No claim with id {claim_id}")
    p = _validate_line(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO expense_claim_lines (
              claim_id, incurred_on, category, description,
              supplier, receipt_ref, quantity, unit_amount,
              mileage_miles, mileage_rate, vat_amount,
              net_amount, gross_amount, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?)
        """, (
            claim_id, p["incurred_on"], p["category"],
            p["description"], p["supplier"], p["receipt_ref"],
            p["quantity"], p["unit_amount"],
            p["mileage_miles"], p["mileage_rate"],
            p["vat_amount"], p["net_amount"],
            p["gross_amount"], p["notes"], now, now,
        ))
        lid = cur.lastrowid
    _recompute_totals(claim_id)
    return get_line(lid)  # type: ignore[return-value]


def update_line(line_id: int,
                     payload: dict[str, Any]) -> ClaimLine:
    init_db()
    existing = get_line(line_id)
    if existing is None:
        raise ValidationError(f"No line with id {line_id}")
    p = _validate_line(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE expense_claim_lines SET
              incurred_on=?, category=?, description=?,
              supplier=?, receipt_ref=?, quantity=?,
              unit_amount=?, mileage_miles=?,
              mileage_rate=?, vat_amount=?, net_amount=?,
              gross_amount=?, notes=?, updated_on=?
            WHERE line_id=?
        """, (
            p["incurred_on"], p["category"], p["description"],
            p["supplier"], p["receipt_ref"], p["quantity"],
            p["unit_amount"], p["mileage_miles"],
            p["mileage_rate"], p["vat_amount"],
            p["net_amount"], p["gross_amount"],
            p["notes"], now, line_id,
        ))
    _recompute_totals(existing.claim_id)
    return get_line(line_id)  # type: ignore[return-value]


def delete_line(line_id: int) -> bool:
    init_db()
    existing = get_line(line_id)
    if existing is None:
        return False
    with _connect() as conn:
        conn.execute(
            "DELETE FROM expense_claim_lines "
            "WHERE line_id=?",
            (line_id,))
    _recompute_totals(existing.claim_id)
    return True


def get_line(line_id: int) -> ClaimLine | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM expense_claim_lines "
            "WHERE line_id=?",
            (line_id,)).fetchone()
    return _row_line(r) if r else None


def lines_for_claim(claim_id: int) -> list[ClaimLine]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM expense_claim_lines "
            "WHERE claim_id=? "
            "ORDER BY incurred_on, line_id",
            (claim_id,)).fetchall()
    return [_row_line(r) for r in rows]


def _recompute_totals(claim_id: int) -> None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(gross_amount), 0) AS t "
            "FROM expense_claim_lines WHERE claim_id=?",
            (claim_id,)).fetchone()
        now = _dt.datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "UPDATE expense_claims SET line_count=?, "
            "total_amount=?, updated_on=? WHERE claim_id=?",
            (r["n"], round(r["t"], 2), now, claim_id))


# ── Workflow ──────────────────────────────────────────────

def _claim_dict(c: Claim) -> dict[str, Any]:
    return {
        "claim_ref": c.claim_ref,
        "claimant_type": c.claimant_type,
        "claimant_id": c.claimant_id,
        "claimant_name": c.claimant_name,
        "department": c.department,
        "title": c.title,
        "description": c.description,
        "purpose": c.purpose,
        "category": c.category,
        "incurred_from": c.incurred_from,
        "incurred_to": c.incurred_to,
        "submitted_on": c.submitted_on,
        "approved_on": c.approved_on,
        "approved_by": c.approved_by,
        "rejected_on": c.rejected_on,
        "rejection_reason": c.rejection_reason,
        "paid_on": c.paid_on,
        "payment_method": c.payment_method,
        "payment_reference": c.payment_reference,
        "status": c.status,
        "line_count": c.line_count,
        "total_amount": c.total_amount,
        "receipts_attached": c.receipts_attached,
        "notes": c.notes,
    }


def submit(claim_id: int) -> Claim:
    c = get_claim(claim_id)
    if c is None:
        raise ValidationError(f"No claim with id {claim_id}")
    if c.line_count == 0:
        raise ValidationError(
            "Cannot submit a claim with no lines")
    data = _claim_dict(c)
    data["status"] = "Submitted"
    data["submitted_on"] = _dt.date.today().isoformat()
    return update_claim(claim_id, data)


def begin_review(claim_id: int) -> Claim:
    c = get_claim(claim_id)
    if c is None:
        raise ValidationError(f"No claim with id {claim_id}")
    return update_claim(claim_id,
                              {**_claim_dict(c),
                                "status": "Under Review"})


def approve(claim_id: int, *,
                approved_by: str | None = None) -> Claim:
    c = get_claim(claim_id)
    if c is None:
        raise ValidationError(f"No claim with id {claim_id}")
    data = _claim_dict(c)
    data["status"] = "Approved"
    data["approved_on"] = _dt.date.today().isoformat()
    if approved_by:
        data["approved_by"] = approved_by
    return update_claim(claim_id, data)


def reject(claim_id: int, *,
                reason: str | None = None) -> Claim:
    c = get_claim(claim_id)
    if c is None:
        raise ValidationError(f"No claim with id {claim_id}")
    data = _claim_dict(c)
    data["status"] = "Rejected"
    data["rejected_on"] = _dt.date.today().isoformat()
    if reason:
        data["rejection_reason"] = reason
    return update_claim(claim_id, data)


def pay(claim_id: int, *,
              payment_reference: str | None = None,
              paid_on: str | None = None) -> Claim:
    c = get_claim(claim_id)
    if c is None:
        raise ValidationError(f"No claim with id {claim_id}")
    if c.status != "Approved":
        raise ValidationError(
            "Only Approved claims can be marked Paid")
    data = _claim_dict(c)
    data["status"] = "Paid"
    data["paid_on"] = (paid_on
                            or _dt.date.today().isoformat())
    if payment_reference:
        data["payment_reference"] = payment_reference
    return update_claim(claim_id, data)


def cancel(claim_id: int) -> Claim:
    c = get_claim(claim_id)
    if c is None:
        raise ValidationError(f"No claim with id {claim_id}")
    return update_claim(claim_id,
                              {**_claim_dict(c),
                                "status": "Cancelled"})


def set_status(claim_id: int, new_status: str) -> Claim:
    if new_status not in CLAIM_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(CLAIM_STATUSES)}")
    c = get_claim(claim_id)
    if c is None:
        raise ValidationError(f"No claim with id {claim_id}")
    return update_claim(claim_id,
                              {**_claim_dict(c),
                                "status": new_status})


# ── Summary ─────────────────────────────────────────────

def summary() -> ExpenseClaimsSummary:
    rows = list_claims()
    out = ExpenseClaimsSummary(total_claims=len(rows))
    if not rows:
        return out
    claimants: set[tuple[str, str]] = set()
    for c in rows:
        claimants.add((c.claimant_type, c.claimant_id))
        if c.status == "Draft":
            out.drafts += 1
        elif c.status == "Submitted":
            out.submitted += 1
        elif c.status == "Under Review":
            out.under_review += 1
        elif c.status == "Approved":
            out.approved += 1
            out.awaiting_payment_value += c.total_amount
        elif c.status == "Paid":
            out.paid += 1
            out.paid_value += c.total_amount
        elif c.status == "Rejected":
            out.rejected += 1
        elif c.status == "Cancelled":
            out.cancelled += 1
        if c.status != "Cancelled" and c.status != "Rejected":
            out.total_value += c.total_amount
        out.by_category[c.category] = (
            out.by_category.get(c.category, 0) + 1)
        out.by_claimant_type[c.claimant_type] = (
            out.by_claimant_type.get(c.claimant_type, 0) + 1)
        out.by_status[c.status] = (
            out.by_status.get(c.status, 0) + 1)
        out.by_payment_method[c.payment_method] = (
            out.by_payment_method.get(c.payment_method, 0) + 1)
    out.distinct_claimants = len(claimants)
    out.total_value = round(out.total_value, 2)
    out.awaiting_payment_value = round(
        out.awaiting_payment_value, 2)
    out.paid_value = round(out.paid_value, 2)
    return out


__all__ = [
    "CLAIMANT_TYPES", "DEFAULT_CLAIMANT_TYPE",
    "CATEGORIES", "DEFAULT_CATEGORY",
    "PAYMENT_METHODS", "DEFAULT_PAYMENT_METHOD",
    "CLAIM_STATUSES", "DEFAULT_CLAIM_STATUS",
    "ValidationError",
    "Claim", "ClaimLine", "ExpenseClaimsSummary",
    "init_db",
    "create_claim", "update_claim", "delete_claim",
    "get_claim", "get_claim_by_ref", "list_claims",
    "add_line", "update_line", "delete_line",
    "get_line", "lines_for_claim",
    "submit", "begin_review", "approve", "reject",
    "pay", "cancel", "set_status",
    "summary",
]
