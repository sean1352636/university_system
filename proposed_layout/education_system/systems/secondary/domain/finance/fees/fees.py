"""Fees data layer for the Secondary School System.

Two linked tables:

* ``fee_items``    — one row per chargeable item against a student
                     (re-sit fees, materials, lunch top-ups, trip
                     deposits, late fines, etc.). The ``amount`` is
                     the gross charge in pounds. The item's
                     ``status`` is derived live from payments and
                     due date — the stored value is set only for
                     terminal lifecycle states (Waived, Refunded,
                     Written-Off, Cancelled) and otherwise computed.
* ``fee_payments`` — one row per payment against a fee item.

Balance for an item:
    balance = amount - sum(payments where status='Cleared')

Status auto-derived:
    Waived/Refunded/Written-Off/Cancelled  → as stored
    balance <= 0                           → 'Paid'
    balance < amount                       → 'Part-Paid'
    due_date < today                       → 'Overdue'
    else                                   → 'Outstanding'
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from typing import Any
from education_system.systems.secondary.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.FEES_DB

CATEGORIES: tuple[str, ...] = (
    "Tuition", "Exam Re-sit", "Exam Entry", "UCAS", "Textbooks",
    "Materials", "Stationery", "Equipment Hire", "Lunch",
    "Trip Deposit", "Trip Balance", "Sports", "Clubs",
    "Music Lesson", "Late Fine", "Lost Library Book",
    "Damage", "Lock / Locker", "Other",
)
DEFAULT_CATEGORY: str = "Other"

STORED_STATUSES: tuple[str, ...] = (
    "Waived", "Refunded", "Written-Off", "Cancelled",
)
DERIVED_STATUSES: tuple[str, ...] = (
    "Outstanding", "Part-Paid", "Paid", "Overdue",
)
STATUSES: tuple[str, ...] = DERIVED_STATUSES + STORED_STATUSES

ACTIVE_STATUSES: tuple[str, ...] = (
    "Outstanding", "Part-Paid", "Overdue")

PAYMENT_METHODS: tuple[str, ...] = (
    "Cash", "Card", "Bank Transfer", "Cheque", "Online Portal",
    "Direct Debit", "Standing Order", "Voucher / Bursary",
    "Adjustment", "Other",
)
DEFAULT_METHOD: str = "Card"

PAYMENT_STATUSES: tuple[str, ...] = (
    "Cleared", "Pending", "Failed", "Refunded",
)
DEFAULT_PAYMENT_STATUS: str = "Cleared"

CURRENCY_SYMBOL: str = "£"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fee_items (
    fee_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    description   TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'Other',
    amount        REAL NOT NULL,
    issued_date   TEXT NOT NULL,
    due_date      TEXT,
    academic_year TEXT,
    stored_status TEXT,             -- one of STORED_STATUSES, else NULL
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fee_payments (
    payment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    fee_id      INTEGER NOT NULL,
    amount      REAL NOT NULL,
    paid_on     TEXT NOT NULL,
    method      TEXT NOT NULL DEFAULT 'Card',
    status      TEXT NOT NULL DEFAULT 'Cleared',
    reference   TEXT,
    recorded_by TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (fee_id) REFERENCES fee_items(fee_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fee_student  ON fee_items(student_id);
CREATE INDEX IF NOT EXISTS idx_fee_category ON fee_items(category);
CREATE INDEX IF NOT EXISTS idx_fee_due      ON fee_items(due_date);
CREATE INDEX IF NOT EXISTS idx_fee_stored   ON fee_items(stored_status);
CREATE INDEX IF NOT EXISTS idx_fp_fee       ON fee_payments(fee_id);
CREATE INDEX IF NOT EXISTS idx_fp_paid_on   ON fee_payments(paid_on);
CREATE INDEX IF NOT EXISTS idx_fp_status    ON fee_payments(status);
"""


@dataclass
class FeeItem:
    fee_id: int
    student_id: str
    description: str
    category: str
    amount: float
    issued_date: str
    due_date: str | None
    academic_year: str | None
    stored_status: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Payment:
    payment_id: int
    fee_id: int
    amount: float
    paid_on: str
    method: str
    status: str
    reference: str | None
    recorded_by: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class FeeView:
    """An item with computed paid / balance / effective status fields."""
    item: FeeItem
    paid: float
    balance: float
    effective_status: str
    payment_count: int
    student_name: str

    @property
    def is_active(self) -> bool:
        return self.effective_status in ACTIVE_STATUSES


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
    from education_system.systems.secondary.domain.pastoral import _pupils_bridge as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Fees schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_item(r: sqlite3.Row) -> FeeItem:
    return FeeItem(
        fee_id=r["fee_id"], student_id=r["student_id"],
        description=r["description"], category=r["category"],
        amount=r["amount"], issued_date=r["issued_date"],
        due_date=r["due_date"], academic_year=r["academic_year"],
        stored_status=r["stored_status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_payment(r: sqlite3.Row) -> Payment:
    return Payment(
        payment_id=r["payment_id"], fee_id=r["fee_id"],
        amount=r["amount"], paid_on=r["paid_on"],
        method=r["method"], status=r["status"],
        reference=r["reference"], recorded_by=r["recorded_by"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_amount(v: Any, label: str, *,
                       allow_zero: bool = False,
                       allow_negative: bool = False) -> float:
    _require(v, label)
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


def _validate_student(v: Any) -> str:
    sid = _require(v, "Student ID").strip()
    from education_system.systems.secondary.domain.pastoral import _pupils_bridge as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_item_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"]  = _validate_student(d.get("student_id"))
    out["description"] = _require(d.get("description"),
                                     "Description").strip()
    cat = (d.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    out["amount"] = _validate_amount(d.get("amount"), "Amount")
    out["issued_date"] = _validate_date(
        d.get("issued_date") or _date.today().isoformat(),
        "Issued date", required=True)
    out["due_date"]      = _validate_date(d.get("due_date"), "Due date")
    if out["due_date"] and out["due_date"] < out["issued_date"]:
        raise ValidationError("Due date cannot be before issued date")
    out["academic_year"] = (d.get("academic_year") or "").strip() or None

    stored = d.get("stored_status")
    if stored in (None, ""):
        out["stored_status"] = None
    else:
        s = str(stored).strip()
        if s not in STORED_STATUSES:
            raise ValidationError(
                "stored_status must be one of: "
                f"{', '.join(STORED_STATUSES)} (or empty)")
        out["stored_status"] = s

    out["notes"] = (d.get("notes") or "").strip() or None
    return out


def _validate_payment_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["amount"]  = _validate_amount(d.get("amount"), "Amount",
                                          allow_negative=True)
    if out["amount"] == 0:
        raise ValidationError("Payment amount cannot be zero")
    out["paid_on"] = _validate_date(
        d.get("paid_on") or _date.today().isoformat(),
        "Paid on", required=True)

    method = (d.get("method") or DEFAULT_METHOD).strip()
    if method not in PAYMENT_METHODS:
        raise ValidationError(
            f"Method must be one of: {', '.join(PAYMENT_METHODS)}")
    out["method"] = method

    status = (d.get("status") or DEFAULT_PAYMENT_STATUS).strip()
    if status not in PAYMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(PAYMENT_STATUSES)}")
    out["status"] = status

    out["reference"]   = (d.get("reference") or "").strip() or None
    out["recorded_by"] = (d.get("recorded_by") or "").strip() or None
    out["notes"]       = (d.get("notes") or "").strip() or None
    return out


# ── Item CRUD ─────────────────────────────────────────────────────

def create_item(d: dict[str, Any]) -> FeeItem:
    init_db()
    p = _validate_item_payload(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO fee_items (
                  student_id, description, category, amount, issued_date,
                  due_date, academic_year, stored_status, notes,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["description"], p["category"], p["amount"],
             p["issued_date"], p["due_date"], p["academic_year"],
             p["stored_status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_item(new_id)
    assert out is not None
    logger.info(
        "Created fee #%d for %s: %s%.2f (%s, %s)",
        new_id, p["student_id"], CURRENCY_SYMBOL, p["amount"],
        p["category"], p["description"][:40])
    return out


def get_item(fee_id: int) -> FeeItem | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM fee_items WHERE fee_id = ?",
            (fee_id,)).fetchone()
        return _row_item(r) if r else None


def list_items(
    *,
    student_id: str | None = None,
    category: str | None = None,
    academic_year: str | None = None,
    stored_status: str | None = None,
) -> list[FeeItem]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if category:
        if category not in CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year.strip())
    if stored_status:
        if stored_status not in STORED_STATUSES:
            raise ValidationError(
                f"stored_status must be one of: "
                f"{', '.join(STORED_STATUSES)}")
        clauses.append("stored_status = ?")
        args.append(stored_status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM fee_items {where} "
           "ORDER BY COALESCE(due_date, issued_date) DESC, fee_id DESC")
    with _connect() as conn:
        return [_row_item(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_item(fee_id: int, d: dict[str, Any]) -> FeeItem:
    init_db()
    existing = get_item(fee_id)
    if existing is None:
        raise ValidationError(f"No fee with id {fee_id}")
    merged = {
        "student_id":    existing.student_id,
        "description":   d.get("description", existing.description),
        "category":      d.get("category", existing.category),
        "amount":        d.get("amount", existing.amount),
        "issued_date":   d.get("issued_date", existing.issued_date),
        "due_date":      d.get("due_date", existing.due_date),
        "academic_year": d.get("academic_year",
                                  existing.academic_year),
        "stored_status": d.get("stored_status",
                                  existing.stored_status),
        "notes":         d.get("notes", existing.notes),
    }
    p = _validate_item_payload(merged)

    # If a new amount is lower than payments cleared so far, refuse.
    paid = _paid_total(fee_id)
    if p["stored_status"] is None and p["amount"] < paid:
        raise ValidationError(
            f"Amount {CURRENCY_SYMBOL}{p['amount']:.2f} is less than "
            f"cleared payments {CURRENCY_SYMBOL}{paid:.2f}")

    with _connect() as conn:
        conn.execute(
            """UPDATE fee_items SET
                  description=?, category=?, amount=?, issued_date=?,
                  due_date=?, academic_year=?, stored_status=?, notes=?,
                  updated_at=datetime('now')
               WHERE fee_id=?""",
            (p["description"], p["category"], p["amount"], p["issued_date"],
             p["due_date"], p["academic_year"], p["stored_status"],
             p["notes"], fee_id),
        )
        conn.commit()
    out = get_item(fee_id)
    assert out is not None
    logger.info("Updated fee #%d", fee_id)
    return out


def set_stored_status(fee_id: int, status: str | None) -> FeeItem:
    if status not in (None, "", *STORED_STATUSES):
        raise ValidationError(
            "stored_status must be one of: "
            f"{', '.join(STORED_STATUSES)} (or empty)")
    return update_item(fee_id, {"stored_status": status or None})


def delete_item(fee_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM fee_items WHERE fee_id = ?", (fee_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted fee #%d (and its payments)", fee_id)
            return True
        return False


# ── Payment CRUD ─────────────────────────────────────────────────

def _paid_total(fee_id: int) -> float:
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s "
            "FROM fee_payments WHERE fee_id = ? AND status = 'Cleared'",
            (fee_id,)).fetchone()
    return round(float(r["s"]), 2)


def create_payment(fee_id: int, d: dict[str, Any]) -> Payment:
    init_db()
    item = get_item(fee_id)
    if item is None:
        raise ValidationError(f"No fee with id {fee_id}")
    p = _validate_payment_payload(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO fee_payments
                 (fee_id, amount, paid_on, method, status,
                  reference, recorded_by, notes,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (fee_id, p["amount"], p["paid_on"], p["method"],
             p["status"], p["reference"], p["recorded_by"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_payment(new_id)
    assert out is not None
    logger.info(
        "Recorded payment #%d for fee #%d: %s%.2f (%s, %s)",
        new_id, fee_id, CURRENCY_SYMBOL, p["amount"],
        p["method"], p["status"])
    return out


def get_payment(payment_id: int) -> Payment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM fee_payments WHERE payment_id = ?",
            (payment_id,)).fetchone()
        return _row_payment(r) if r else None


def list_payments(
    *,
    fee_id: int | None = None,
    student_id: str | None = None,
    method: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Payment]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if fee_id is not None:
        clauses.append("fee_id = ?")
        args.append(fee_id)
    if student_id:
        clauses.append("fee_id IN (SELECT fee_id FROM fee_items "
                        "             WHERE student_id = ?)")
        args.append(student_id.strip())
    if method:
        if method not in PAYMENT_METHODS:
            raise ValidationError(
                f"Method must be one of: {', '.join(PAYMENT_METHODS)}")
        clauses.append("method = ?")
        args.append(method)
    if status:
        if status not in PAYMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(PAYMENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if date_from:
        clauses.append("paid_on >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("paid_on <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM fee_payments {where} "
           "ORDER BY paid_on DESC, payment_id DESC")
    with _connect() as conn:
        return [_row_payment(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_payment(payment_id: int, d: dict[str, Any]) -> Payment:
    init_db()
    existing = get_payment(payment_id)
    if existing is None:
        raise ValidationError(f"No payment with id {payment_id}")
    merged = {
        "amount":      d.get("amount", existing.amount),
        "paid_on":     d.get("paid_on", existing.paid_on),
        "method":      d.get("method", existing.method),
        "status":      d.get("status", existing.status),
        "reference":   d.get("reference", existing.reference),
        "recorded_by": d.get("recorded_by", existing.recorded_by),
        "notes":       d.get("notes", existing.notes),
    }
    p = _validate_payment_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE fee_payments SET
                  amount=?, paid_on=?, method=?, status=?,
                  reference=?, recorded_by=?, notes=?,
                  updated_at=datetime('now')
               WHERE payment_id=?""",
            (p["amount"], p["paid_on"], p["method"], p["status"],
             p["reference"], p["recorded_by"], p["notes"], payment_id),
        )
        conn.commit()
    out = get_payment(payment_id)
    assert out is not None
    logger.info("Updated payment #%d", payment_id)
    return out


def delete_payment(payment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM fee_payments WHERE payment_id = ?",
            (payment_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted payment #%d", payment_id)
            return True
        return False


# ── Status derivation ────────────────────────────────────────────

def _derived_status(item: FeeItem, paid: float, today: str) -> str:
    if item.stored_status:
        return item.stored_status
    balance = round(item.amount - paid, 2)
    if balance <= 0:
        return "Paid"
    if paid > 0:
        if item.due_date and item.due_date < today:
            return "Overdue"
        return "Part-Paid"
    if item.due_date and item.due_date < today:
        return "Overdue"
    return "Outstanding"


def view_item(fee_id: int) -> FeeView | None:
    item = get_item(fee_id)
    if item is None:
        return None
    paid = _paid_total(fee_id)
    today = _date.today().isoformat()
    from education_system.systems.secondary.domain.pastoral import _pupils_bridge as _students
    s = _students.get_student(item.student_id)
    name = s.full_name if s else "(unknown)"
    return FeeView(
        item=item, paid=paid,
        balance=round(item.amount - paid, 2),
        effective_status=_derived_status(item, paid, today),
        payment_count=len(list_payments(fee_id=fee_id)),
        student_name=name,
    )


def list_views(
    *,
    student_id: str | None = None,
    category: str | None = None,
    academic_year: str | None = None,
    effective_status: str | None = None,
    active_only: bool = False,
    overdue_only: bool = False,
) -> list[FeeView]:
    items = list_items(student_id=student_id, category=category,
                        academic_year=academic_year)
    if not items:
        return []
    today = _date.today().isoformat()
    from education_system.systems.secondary.domain.pastoral import _pupils_bridge as _students
    name_map = {s.student_id: s.full_name
                 for s in _students.list_students()}

    # One query to gather all paid totals.
    with _connect() as conn:
        rows = conn.execute(
            """SELECT fee_id, COALESCE(SUM(amount), 0) AS s,
                       COUNT(*) AS n
                FROM fee_payments
               WHERE status = 'Cleared'
               GROUP BY fee_id""").fetchall()
        paid_map = {r["fee_id"]: float(r["s"]) for r in rows}
        count_rows = conn.execute(
            """SELECT fee_id, COUNT(*) AS n
                FROM fee_payments GROUP BY fee_id""").fetchall()
        count_map = {r["fee_id"]: r["n"] for r in count_rows}

    out: list[FeeView] = []
    for it in items:
        paid = round(paid_map.get(it.fee_id, 0.0), 2)
        status = _derived_status(it, paid, today)
        if effective_status and effective_status != status:
            continue
        if active_only and status not in ACTIVE_STATUSES:
            continue
        if overdue_only and status != "Overdue":
            continue
        out.append(FeeView(
            item=it, paid=paid,
            balance=round(it.amount - paid, 2),
            effective_status=status,
            payment_count=count_map.get(it.fee_id, 0),
            student_name=name_map.get(it.student_id, "(unknown)"),
        ))
    return out


def statement(student_id: str) -> list[FeeView]:
    """All fees for a student, most recent first."""
    return list_views(student_id=student_id)


def student_balance(student_id: str) -> float:
    """Total outstanding (sum of balances for active fees)."""
    return round(
        sum(v.balance for v in statement(student_id)
             if v.is_active), 2)


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class Summary:
    total_items: int
    total_charged: float
    total_paid: float
    total_outstanding: float
    overdue_count: int
    overdue_total: float
    active_students: int           # distinct students with active fees
    written_off: float
    waived: float
    refunded_payments: float
    by_category: dict[str, float]
    by_status: dict[str, int]
    by_method: dict[str, float]
    top_debtors: list[tuple[str, str, float]]  # student_id, name, balance


def summary() -> Summary:
    init_db()
    views = list_views()
    total_charged = round(sum(v.item.amount for v in views), 2)
    total_paid = round(sum(v.paid for v in views), 2)
    total_outstanding = round(
        sum(v.balance for v in views if v.is_active), 2)
    overdue = [v for v in views if v.effective_status == "Overdue"]
    by_cat: dict[str, float] = {c: 0.0 for c in CATEGORIES}
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    for v in views:
        by_cat[v.item.category] = (
            by_cat.get(v.item.category, 0.0) + v.item.amount)
        by_status[v.effective_status] = (
            by_status.get(v.effective_status, 0) + 1)

    written = round(sum(v.item.amount for v in views
                          if v.effective_status == "Written-Off"), 2)
    waived = round(sum(v.item.amount for v in views
                         if v.effective_status == "Waived"), 2)

    # Payment breakdown
    payments = list_payments()
    by_method: dict[str, float] = {m: 0.0 for m in PAYMENT_METHODS}
    refunds_total = 0.0
    for p in payments:
        if p.status == "Refunded":
            refunds_total += abs(p.amount)
            continue
        if p.status != "Cleared":
            continue
        by_method[p.method] = by_method.get(p.method, 0.0) + p.amount

    # Top debtors
    balances: dict[str, float] = {}
    names: dict[str, str] = {}
    for v in views:
        if not v.is_active:
            continue
        balances[v.item.student_id] = (
            balances.get(v.item.student_id, 0.0) + v.balance)
        names[v.item.student_id] = v.student_name
    top = sorted(balances.items(), key=lambda kv: -kv[1])[:10]
    top_list = [(sid, names.get(sid, "?"), round(bal, 2))
                 for sid, bal in top if bal > 0]

    return Summary(
        total_items=len(views),
        total_charged=total_charged,
        total_paid=total_paid,
        total_outstanding=total_outstanding,
        overdue_count=len(overdue),
        overdue_total=round(sum(v.balance for v in overdue), 2),
        active_students=len(balances),
        written_off=written, waived=waived,
        refunded_payments=round(refunds_total, 2),
        by_category={k: round(v, 2) for k, v in by_cat.items()},
        by_status=by_status,
        by_method={k: round(v, 2) for k, v in by_method.items()},
        top_debtors=top_list,
    )
