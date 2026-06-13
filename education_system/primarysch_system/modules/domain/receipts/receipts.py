"""Receipts data layer for the Primary School System.

A receipt is the formal record handed back to whoever paid: one
sequentially-numbered document per payment event, with line items.
Receipts can be linked back to a fee payment, a trip payment, a
bursary disbursement, or be free-standing (cash handed in at the
office for something the system doesn't model elsewhere).

Two tables:

* ``receipts``      — header (receipt_number, issued_date, payer,
                      method, status, total, void info).
* ``receipt_lines`` — one row per chargeable item (description,
                      amount, source kind/id).

Numbering: ``R-YYYY-NNNNN`` — year + 5-digit sequence reset annually.
The number is allocated on creation and never changes (voided
receipts keep their number so audit trails stay intact).

Status lifecycle:
    Draft   → may be edited or deleted
    Issued  → frozen: edits limited to notes; cannot be hard-deleted
    Voided  → terminal; must record a reason; total still counts in
              cash audit but not in revenue
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from typing import Any
from education_system.primarysch_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.RECEIPTS_DB

PAYMENT_METHODS: tuple[str, ...] = (
    "Cash", "Card", "Bank Transfer", "Cheque",
    "Online Portal", "Direct Debit", "Voucher / Bursary",
    "Adjustment", "Other",
)
DEFAULT_METHOD: str = "Card"

STATUSES: tuple[str, ...] = ("Draft", "Issued", "Voided")
DEFAULT_STATUS: str = "Draft"

LINE_KINDS: tuple[str, ...] = (
    "general", "fee", "trip", "bursary", "lunch", "exam", "other",
)
DEFAULT_LINE_KIND: str = "general"

CURRENCY_SYMBOL: str = "£"
NUMBER_PREFIX: str = "R"
NUMBER_DIGITS: int = 5

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUMBER_RE = re.compile(r"^R-(\d{4})-(\d{5})$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_number  TEXT NOT NULL UNIQUE,
    issued_date     TEXT NOT NULL,
    payer_name      TEXT NOT NULL,
    student_id      TEXT,
    method          TEXT NOT NULL DEFAULT 'Card',
    status          TEXT NOT NULL DEFAULT 'Draft',
    total_amount    REAL NOT NULL DEFAULT 0,
    received_by     TEXT,
    reference       TEXT,
    notes           TEXT,
    voided_at       TEXT,
    void_reason     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS receipt_lines (
    line_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id  INTEGER NOT NULL,
    description TEXT NOT NULL,
    amount      REAL NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'general',
    source_id   INTEGER,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (receipt_id) REFERENCES receipts(receipt_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rcp_date    ON receipts(issued_date);
CREATE INDEX IF NOT EXISTS idx_rcp_student ON receipts(student_id);
CREATE INDEX IF NOT EXISTS idx_rcp_status  ON receipts(status);
CREATE INDEX IF NOT EXISTS idx_rcp_method  ON receipts(method);
CREATE INDEX IF NOT EXISTS idx_rl_receipt  ON receipt_lines(receipt_id);
CREATE INDEX IF NOT EXISTS idx_rl_kind     ON receipt_lines(kind);
"""


@dataclass
class ReceiptLine:
    line_id: int
    receipt_id: int
    description: str
    amount: float
    kind: str
    source_id: int | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Receipt:
    receipt_id: int
    receipt_number: str
    issued_date: str
    payer_name: str
    student_id: str | None
    method: str
    status: str
    total_amount: float
    received_by: str | None
    reference: str | None
    notes: str | None
    voided_at: str | None
    void_reason: str | None
    created_at: str
    updated_at: str

    @property
    def is_voided(self) -> bool:
        return self.status == "Voided"

    @property
    def is_issued(self) -> bool:
        return self.status == "Issued"


@dataclass
class ReceiptView:
    receipt: Receipt
    lines: list[ReceiptLine]
    student_name: str | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.primarysch_system.modules.domain import _pupils_bridge as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Receipts schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_receipt(r: sqlite3.Row) -> Receipt:
    return Receipt(
        receipt_id=r["receipt_id"], receipt_number=r["receipt_number"],
        issued_date=r["issued_date"], payer_name=r["payer_name"],
        student_id=r["student_id"], method=r["method"],
        status=r["status"], total_amount=r["total_amount"],
        received_by=r["received_by"], reference=r["reference"],
        notes=r["notes"], voided_at=r["voided_at"],
        void_reason=r["void_reason"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_line(r: sqlite3.Row) -> ReceiptLine:
    return ReceiptLine(
        line_id=r["line_id"], receipt_id=r["receipt_id"],
        description=r["description"], amount=r["amount"],
        kind=r["kind"], source_id=r["source_id"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Receipt numbers ──────────────────────────────────────────────

def _next_receipt_number(conn: sqlite3.Connection,
                            issued_date: str) -> str:
    year = issued_date[:4]
    like = f"{NUMBER_PREFIX}-{year}-%"
    r = conn.execute(
        "SELECT receipt_number FROM receipts "
        "WHERE receipt_number LIKE ? "
        "ORDER BY receipt_number DESC LIMIT 1",
        (like,)).fetchone()
    if r is None:
        n = 1
    else:
        m = _NUMBER_RE.match(r["receipt_number"])
        n = int(m.group(2)) + 1 if m else 1
    return f"{NUMBER_PREFIX}-{year}-{n:0{NUMBER_DIGITS}d}"


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_amount(v: Any, label: str, *,
                       required: bool = True,
                       allow_zero: bool = False,
                       allow_negative: bool = False) -> float:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if not required:
            return 0.0
        raise ValidationError(f"{label} is required")
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{label} must be a number") from None
    if d.as_tuple().exponent < -2:
        raise ValidationError(
            f"{label} must have at most 2 decimal places")
    if not allow_negative and d < 0:
        raise ValidationError(f"{label} cannot be negative")
    if not allow_zero and d == 0:
        raise ValidationError(f"{label} cannot be zero")
    return float(d.quantize(Decimal("0.01")))


def _validate_date(v: Any, label: str, *,
                    required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_student(v: Any) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    sid = str(v).strip()
    from education_system.primarysch_system.modules.domain import _pupils_bridge as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_method(v: Any) -> str:
    m = (v or DEFAULT_METHOD).strip()
    if m not in PAYMENT_METHODS:
        raise ValidationError(
            f"Method must be one of: {', '.join(PAYMENT_METHODS)}")
    return m


def _validate_kind(v: Any) -> str:
    k = (v or DEFAULT_LINE_KIND).strip().lower()
    if k not in LINE_KINDS:
        raise ValidationError(
            f"Line kind must be one of: {', '.join(LINE_KINDS)}")
    return k


def _validate_line(d: dict[str, Any], *,
                     allow_negative: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["description"] = _require(d.get("description"),
                                     "Description").strip()
    out["amount"] = _validate_amount(
        d.get("amount"), "Amount", allow_negative=allow_negative)
    out["kind"]   = _validate_kind(d.get("kind"))
    sid = d.get("source_id")
    if sid in (None, ""):
        out["source_id"] = None
    else:
        try:
            out["source_id"] = int(sid)
        except (TypeError, ValueError):
            raise ValidationError(
                "source_id must be a whole number") from None
    out["notes"] = (d.get("notes") or "").strip() or None
    return out


def _validate_header(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["issued_date"] = _validate_date(
        d.get("issued_date") or _date.today().isoformat(),
        "Issued date", required=True)
    out["payer_name"]  = _require(d.get("payer_name"),
                                     "Payer name").strip()
    out["student_id"]  = _validate_student(d.get("student_id"))
    out["method"]      = _validate_method(d.get("method"))

    status = (d.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["received_by"] = (d.get("received_by") or "").strip() or None
    out["reference"]   = (d.get("reference") or "").strip() or None
    out["notes"]       = (d.get("notes") or "").strip() or None
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_receipt(header: dict[str, Any],
                     lines: list[dict[str, Any]]) -> Receipt:
    """Create a receipt + line items in one transaction. Allocates
    the next receipt number for the issued year."""
    init_db()
    if not lines:
        raise ValidationError("A receipt needs at least one line item")
    h = _validate_header(header)
    line_payloads = [_validate_line(l) for l in lines]
    total = round(sum(l["amount"] for l in line_payloads), 2)
    if total <= 0:
        raise ValidationError(
            "Receipt total must be greater than zero")

    with _connect() as conn:
        number = _next_receipt_number(conn, h["issued_date"])
        cur = conn.execute(
            """INSERT INTO receipts (
                  receipt_number, issued_date, payer_name, student_id,
                  method, status, total_amount, received_by, reference,
                  notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (number, h["issued_date"], h["payer_name"], h["student_id"],
             h["method"], h["status"], total, h["received_by"],
             h["reference"], h["notes"]),
        )
        new_id = cur.lastrowid
        for lp in line_payloads:
            conn.execute(
                """INSERT INTO receipt_lines (
                      receipt_id, description, amount, kind, source_id,
                      notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (new_id, lp["description"], lp["amount"], lp["kind"],
                 lp["source_id"], lp["notes"]),
            )
        conn.commit()
    out = get_receipt(new_id)
    assert out is not None
    logger.info("Created receipt %s (#%d) — %d line(s), %s%.2f",
                number, new_id, len(line_payloads),
                CURRENCY_SYMBOL, total)
    return out


def get_receipt(receipt_id: int) -> Receipt | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM receipts WHERE receipt_id = ?",
            (receipt_id,)).fetchone()
        return _row_receipt(r) if r else None


def get_by_number(receipt_number: str) -> Receipt | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM receipts WHERE receipt_number = ?",
            (receipt_number.strip().upper(),)).fetchone()
        return _row_receipt(r) if r else None


def list_lines(receipt_id: int) -> list[ReceiptLine]:
    init_db()
    with _connect() as conn:
        return [_row_line(r)
                 for r in conn.execute(
                     "SELECT * FROM receipt_lines "
                     "WHERE receipt_id = ? ORDER BY line_id",
                     (receipt_id,)).fetchall()]


def view_receipt(receipt_id: int) -> ReceiptView | None:
    r = get_receipt(receipt_id)
    if r is None:
        return None
    name = None
    if r.student_id:
        from education_system.primarysch_system.modules.domain import _pupils_bridge as _students
        s = _students.get_student(r.student_id)
        if s:
            name = s.full_name
    return ReceiptView(receipt=r, lines=list_lines(receipt_id),
                         student_name=name)


def list_receipts(
    *,
    student_id: str | None = None,
    status: str | None = None,
    method: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    issued_only: bool = False,
    voided_only: bool = False,
) -> list[Receipt]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if method:
        if method not in PAYMENT_METHODS:
            raise ValidationError(
                f"Method must be one of: {', '.join(PAYMENT_METHODS)}")
        clauses.append("method = ?")
        args.append(method)
    if date_from:
        clauses.append("issued_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("issued_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if issued_only:
        clauses.append("status = 'Issued'")
    if voided_only:
        clauses.append("status = 'Voided'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM receipts {where} "
           "ORDER BY issued_date DESC, receipt_id DESC")
    with _connect() as conn:
        return [_row_receipt(r)
                 for r in conn.execute(sql, args).fetchall()]


def search_receipts(q: str) -> list[Receipt]:
    init_db()
    q = (q or "").strip()
    if not q:
        return list_receipts()
    like = f"%{q}%"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM receipts
                WHERE receipt_number LIKE ?
                   OR payer_name LIKE ?
                   OR reference LIKE ?
                   OR student_id LIKE ?
                ORDER BY issued_date DESC, receipt_id DESC""",
            (like, like, like, like),
        ).fetchall()
    return [_row_receipt(r) for r in rows]


def update_receipt(receipt_id: int,
                     header: dict[str, Any],
                     lines: list[dict[str, Any]] | None = None
                     ) -> Receipt:
    """Update a Draft receipt's header and (optionally) lines.
    Issued receipts can only have notes/reference/received_by edited;
    voided receipts can't be edited at all (use the dedicated
    void-management functions if needed)."""
    init_db()
    existing = get_receipt(receipt_id)
    if existing is None:
        raise ValidationError(f"No receipt #{receipt_id}")
    if existing.status == "Voided":
        raise ValidationError(
            "Cannot edit a voided receipt")
    if existing.status == "Issued":
        return _limited_edit_issued(existing, header)

    merged_header = {
        "issued_date": header.get("issued_date", existing.issued_date),
        "payer_name":  header.get("payer_name", existing.payer_name),
        "student_id":  header.get("student_id", existing.student_id),
        "method":      header.get("method", existing.method),
        "status":      header.get("status", existing.status),
        "received_by": header.get("received_by", existing.received_by),
        "reference":   header.get("reference", existing.reference),
        "notes":       header.get("notes", existing.notes),
    }
    h = _validate_header(merged_header)

    if lines is None:
        # Keep the existing lines; recompute total from them.
        existing_lines = list_lines(receipt_id)
        total = round(sum(l.amount for l in existing_lines), 2)
        new_lines = None
    else:
        line_payloads = [_validate_line(l) for l in lines]
        if not line_payloads:
            raise ValidationError(
                "A receipt must have at least one line")
        total = round(sum(l["amount"] for l in line_payloads), 2)
        if total <= 0:
            raise ValidationError(
                "Receipt total must be greater than zero")
        new_lines = line_payloads

    with _connect() as conn:
        conn.execute(
            """UPDATE receipts SET
                  issued_date=?, payer_name=?, student_id=?, method=?,
                  status=?, total_amount=?, received_by=?, reference=?,
                  notes=?, updated_at=datetime('now')
               WHERE receipt_id=?""",
            (h["issued_date"], h["payer_name"], h["student_id"],
             h["method"], h["status"], total, h["received_by"],
             h["reference"], h["notes"], receipt_id),
        )
        if new_lines is not None:
            conn.execute(
                "DELETE FROM receipt_lines WHERE receipt_id = ?",
                (receipt_id,))
            for lp in new_lines:
                conn.execute(
                    """INSERT INTO receipt_lines (
                          receipt_id, description, amount, kind,
                          source_id, notes, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?,
                               datetime('now'), datetime('now'))""",
                    (receipt_id, lp["description"], lp["amount"],
                     lp["kind"], lp["source_id"], lp["notes"]),
                )
        conn.commit()
    out = get_receipt(receipt_id)
    assert out is not None
    logger.info("Updated receipt %s (#%d)",
                out.receipt_number, receipt_id)
    return out


def _limited_edit_issued(existing: Receipt,
                            header: dict[str, Any]) -> Receipt:
    """Issued receipts can have notes / reference / received_by
    updated. Everything else is frozen."""
    allowed = {"notes", "reference", "received_by"}
    extras = set(header.keys()) - allowed
    if extras:
        # Quietly drop anything not in the allowed set — but
        # raise if it would actually change a value.
        for k in extras:
            cur = getattr(existing, k, None)
            new = header.get(k)
            if new is None:
                continue
            if str(new).strip() == (str(cur).strip() if cur else ""):
                continue
            raise ValidationError(
                f"Cannot change '{k}' on an Issued receipt — "
                f"void it first")
    notes = header.get("notes", existing.notes)
    ref   = header.get("reference", existing.reference)
    by    = header.get("received_by", existing.received_by)
    init_db()
    with _connect() as conn:
        conn.execute(
            """UPDATE receipts SET
                  notes=?, reference=?, received_by=?,
                  updated_at=datetime('now')
               WHERE receipt_id=?""",
            ((notes or "").strip() or None,
             (ref or "").strip() or None,
             (by or "").strip() or None,
             existing.receipt_id),
        )
        conn.commit()
    out = get_receipt(existing.receipt_id)
    assert out is not None
    logger.info("Updated issued receipt %s (notes/ref/by only)",
                out.receipt_number)
    return out


def issue(receipt_id: int) -> Receipt:
    """Move a Draft receipt to Issued."""
    init_db()
    existing = get_receipt(receipt_id)
    if existing is None:
        raise ValidationError(f"No receipt #{receipt_id}")
    if existing.status == "Voided":
        raise ValidationError("Cannot issue a voided receipt")
    if existing.status == "Issued":
        return existing
    with _connect() as conn:
        conn.execute(
            "UPDATE receipts SET status='Issued', "
            "updated_at=datetime('now') WHERE receipt_id=?",
            (receipt_id,))
        conn.commit()
    out = get_receipt(receipt_id)
    assert out is not None
    logger.info("Issued receipt %s", out.receipt_number)
    return out


def void_receipt(receipt_id: int, reason: str) -> Receipt:
    """Move a receipt to Voided. Requires a reason."""
    init_db()
    if not (reason or "").strip():
        raise ValidationError("A reason is required to void a receipt")
    existing = get_receipt(receipt_id)
    if existing is None:
        raise ValidationError(f"No receipt #{receipt_id}")
    if existing.status == "Voided":
        return existing
    with _connect() as conn:
        conn.execute(
            "UPDATE receipts SET status='Voided', "
            "voided_at=datetime('now'), void_reason=?, "
            "updated_at=datetime('now') WHERE receipt_id=?",
            (reason.strip(), receipt_id))
        conn.commit()
    out = get_receipt(receipt_id)
    assert out is not None
    logger.info("Voided receipt %s — %s",
                out.receipt_number, reason.strip()[:60])
    return out


def delete_receipt(receipt_id: int) -> bool:
    """Hard-delete a *Draft* receipt. Issued/Voided receipts must be
    kept for audit; void them instead."""
    init_db()
    existing = get_receipt(receipt_id)
    if existing is None:
        return False
    if existing.status != "Draft":
        raise ValidationError(
            f"Only Draft receipts can be deleted "
            f"(this one is {existing.status}). Void it instead.")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM receipts WHERE receipt_id = ?",
            (receipt_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted draft receipt %s",
                        existing.receipt_number)
            return True
        return False


# ── Per-student helper ───────────────────────────────────────────

def receipts_for_student(student_id: str) -> list[Receipt]:
    return list_receipts(student_id=student_id)


# ── Import helpers from other modules ────────────────────────────

def receipt_from_fee_payment(payment_id: int,
                                received_by: str | None = None,
                                issued: bool = True) -> Receipt:
    """Create a receipt for an existing fee payment (status=Cleared
    only). The line's source_id links back to the fee item."""
    from education_system.primarysch_system.modules.domain.fees import fees as _fees
    p = _fees.get_payment(payment_id)
    if p is None:
        raise ValidationError(f"No fee payment #{payment_id}")
    if p.status != "Cleared":
        raise ValidationError(
            "Only cleared fee payments can be receipted")
    item = _fees.get_item(p.fee_id)
    if item is None:
        raise ValidationError(f"Fee #{p.fee_id} not found")
    from education_system.primarysch_system.modules.domain import _pupils_bridge as _students
    student = _students.get_student(item.student_id)
    payer = student.full_name if student else item.student_id
    method = p.method if p.method in PAYMENT_METHODS else DEFAULT_METHOD
    return create_receipt(
        {
            "issued_date": p.paid_on,
            "payer_name":  payer,
            "student_id":  item.student_id,
            "method":      method,
            "status":      "Issued" if issued else "Draft",
            "received_by": received_by or p.recorded_by,
            "reference":   p.reference,
            "notes":       f"Imported from fee payment #{payment_id}",
        },
        [{
            "description": item.description,
            "amount":      p.amount,
            "kind":        "fee",
            "source_id":   item.fee_id,
        }],
    )


def receipt_from_trip_payment(payment_id: int,
                                 received_by: str | None = None,
                                 issued: bool = True) -> Receipt:
    """Create a receipt for an existing trip payment (Cleared only)."""
    from education_system.primarysch_system.modules.domain.trips import trips as _trips
    p = _trips.get_payment(payment_id)
    if p is None:
        raise ValidationError(f"No trip payment #{payment_id}")
    if p.status != "Cleared":
        raise ValidationError(
            "Only cleared trip payments can be receipted")
    booking = _trips.get_booking(p.booking_id)
    if booking is None:
        raise ValidationError(f"Booking #{p.booking_id} not found")
    trip = _trips.get_trip(booking.trip_id)
    if trip is None:
        raise ValidationError(f"Trip #{booking.trip_id} not found")
    from education_system.primarysch_system.modules.domain import _pupils_bridge as _students
    student = _students.get_student(booking.student_id)
    payer = student.full_name if student else booking.student_id
    method = p.method if p.method in PAYMENT_METHODS else DEFAULT_METHOD
    return create_receipt(
        {
            "issued_date": p.paid_on,
            "payer_name":  payer,
            "student_id":  booking.student_id,
            "method":      method,
            "status":      "Issued" if issued else "Draft",
            "received_by": received_by or p.recorded_by,
            "reference":   p.reference,
            "notes":       f"Imported from trip payment #{payment_id}",
        },
        [{
            "description":
                f"{trip.name} — trip payment",
            "amount":      p.amount,
            "kind":        "trip",
            "source_id":   trip.trip_id,
        }],
    )


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class Summary:
    total_receipts: int
    drafts: int
    issued: int
    voided: int
    total_issued_amount: float
    total_voided_amount: float
    by_method: dict[str, float]   # cash audit: by method (Issued only)
    by_kind: dict[str, float]     # by line kind (Issued only)
    daily_today: float
    daily_this_week: float
    daily_this_month: float
    top_payers: list[tuple[str, float]]  # name, paid (Issued only)


def summary() -> Summary:
    import datetime as _dt
    init_db()
    today = _dt.date.today()
    today_s = today.isoformat()
    week_start = (today - _dt.timedelta(days=today.weekday())
                   ).isoformat()
    month_start = today.replace(day=1).isoformat()

    rows = list_receipts()
    drafts = sum(1 for r in rows if r.status == "Draft")
    issued = sum(1 for r in rows if r.status == "Issued")
    voided = sum(1 for r in rows if r.status == "Voided")
    total_issued = round(sum(r.total_amount for r in rows
                               if r.status == "Issued"), 2)
    total_voided = round(sum(r.total_amount for r in rows
                               if r.status == "Voided"), 2)

    by_method = {m: 0.0 for m in PAYMENT_METHODS}
    for r in rows:
        if r.status != "Issued":
            continue
        by_method[r.method] = by_method.get(r.method, 0.0) + r.total_amount

    # Line-kind breakdown (only Issued)
    with _connect() as conn:
        lk = conn.execute(
            """SELECT rl.kind, COALESCE(SUM(rl.amount), 0) AS s
                  FROM receipt_lines rl
                  JOIN receipts r ON r.receipt_id = rl.receipt_id
                 WHERE r.status = 'Issued'
                 GROUP BY rl.kind""").fetchall()
        by_kind = {k: 0.0 for k in LINE_KINDS}
        for row in lk:
            by_kind[row["kind"]] = by_kind.get(row["kind"], 0.0) + row["s"]

    def _sum_since(date_iso: str) -> float:
        return round(sum(r.total_amount for r in rows
                          if r.status == "Issued"
                          and r.issued_date >= date_iso), 2)

    payer_totals: dict[str, float] = {}
    for r in rows:
        if r.status != "Issued":
            continue
        payer_totals[r.payer_name] = (
            payer_totals.get(r.payer_name, 0.0) + r.total_amount)
    top = sorted(payer_totals.items(), key=lambda kv: -kv[1])[:10]

    return Summary(
        total_receipts=len(rows),
        drafts=drafts, issued=issued, voided=voided,
        total_issued_amount=total_issued,
        total_voided_amount=total_voided,
        by_method={k: round(v, 2) for k, v in by_method.items()},
        by_kind={k: round(v, 2) for k, v in by_kind.items()},
        daily_today=_sum_since(today_s),
        daily_this_week=_sum_since(week_start),
        daily_this_month=_sum_since(month_start),
        top_payers=[(name, round(amt, 2)) for name, amt in top],
    )
