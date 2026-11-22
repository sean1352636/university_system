"""Lockers data layer for the Sixth Form System.

Three tables:

* ``locker_banks``       — a run of lockers in one place (name,
  location, locker size).
* ``lockers``            — one row per locker: number (unique within its
  bank), combination code / key number and an operational status
  (Available / Allocated / Out of Order).
* ``locker_allocations`` — who has a locker for which academic year,
  the deposit taken, whether a key or code was issued, and how it came
  back (date, condition, deposit refunded or retained with a reason).

A locker has at most one *active* allocation (partial unique index), and
a student holds at most one active locker at a time (checked on
allocate). Returned allocations are kept as history — they are the
record of who had which locker and what happened to the deposit.

``overdue_returns`` lists active allocations whose academic year has
ended (31 July of the second calendar year): the year-end chase list.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system import paths

logger = logging.getLogger(__name__)

# One file for the whole sixth form; the students table lives here too,
# which the allocation FK needs.
DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

LOCKER_SIZES: tuple[str, ...] = ("Small", "Medium", "Large", "Full Height")
DEFAULT_LOCKER_SIZE = "Medium"

AVAILABLE = "Available"
ALLOCATED = "Allocated"
OUT_OF_ORDER = "Out of Order"
LOCKER_STATUSES: tuple[str, ...] = (AVAILABLE, ALLOCATED, OUT_OF_ORDER)

ACTIVE = "Active"
RETURNED = "Returned"
ALLOCATION_STATUSES: tuple[str, ...] = (ACTIVE, RETURNED)

DEPOSIT_NONE = "None"
DEPOSIT_DUE = "Due"
DEPOSIT_PAID = "Paid"
DEPOSIT_REFUNDED = "Refunded"
DEPOSIT_RETAINED = "Retained"
DEPOSIT_STATUSES: tuple[str, ...] = (
    DEPOSIT_NONE, DEPOSIT_DUE, DEPOSIT_PAID, DEPOSIT_REFUNDED,
    DEPOSIT_RETAINED)

RETURN_CONDITIONS: tuple[str, ...] = (
    "Good", "Minor Damage", "Damaged", "Key Lost", "Not Cleared")
# Conditions that take the locker out of use until somebody fixes it.
_OUT_OF_ORDER_CONDITIONS = ("Damaged", "Key Lost")

DEFAULT_DEPOSIT = 10.00

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YEAR_RE = re.compile(r"^(\d{4})/(\d{2})$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS locker_banks (
    bank_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    location     TEXT,
    locker_size  TEXT NOT NULL DEFAULT 'Medium',
    active       INTEGER NOT NULL DEFAULT 1,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lockers (
    locker_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id      INTEGER NOT NULL,
    number       TEXT NOT NULL,
    code         TEXT,
    key_number   TEXT,
    status       TEXT NOT NULL DEFAULT 'Available',
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(bank_id, number),
    FOREIGN KEY (bank_id) REFERENCES locker_banks(bank_id)
);

CREATE TABLE IF NOT EXISTS locker_allocations (
    allocation_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    locker_id       INTEGER NOT NULL,
    student_id      TEXT NOT NULL,
    academic_year   TEXT NOT NULL,
    allocated_on    TEXT NOT NULL,
    key_issued      INTEGER NOT NULL DEFAULT 0,
    code_issued     TEXT,
    deposit_amount  REAL NOT NULL DEFAULT 0,
    deposit_status  TEXT NOT NULL DEFAULT 'None',
    deposit_paid_on TEXT,
    returned_on     TEXT,
    return_condition TEXT,
    deposit_settled_on TEXT,
    deposit_retained_reason TEXT,
    status          TEXT NOT NULL DEFAULT 'Active',
    allocated_by    TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (locker_id)  REFERENCES lockers(locker_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lockers_bank   ON lockers(bank_id);
CREATE INDEX IF NOT EXISTS idx_lk_alloc_student
    ON locker_allocations(student_id);
CREATE INDEX IF NOT EXISTS idx_lk_alloc_year
    ON locker_allocations(academic_year);
CREATE UNIQUE INDEX IF NOT EXISTS idx_lk_alloc_one_active
    ON locker_allocations(locker_id) WHERE status = 'Active';
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class LockerBank:
    bank_id: int
    name: str
    location: str | None
    locker_size: str
    active: bool
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Locker:
    locker_id: int
    bank_id: int
    number: str
    code: str | None
    key_number: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str
    bank_name: str | None = None

    @property
    def label(self) -> str:
        return f"{self.bank_name or f'Bank #{self.bank_id}'} / {self.number}"


@dataclass
class Allocation:
    allocation_id: int
    locker_id: int
    student_id: str
    academic_year: str
    allocated_on: str
    key_issued: bool
    code_issued: str | None
    deposit_amount: float
    deposit_status: str
    deposit_paid_on: str | None
    returned_on: str | None
    return_condition: str | None
    deposit_settled_on: str | None
    deposit_retained_reason: str | None
    status: str
    allocated_by: str | None
    notes: str | None
    created_at: str
    updated_at: str
    locker_label: str | None = None
    student_name: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status == ACTIVE

    @property
    def deposit_outstanding(self) -> bool:
        return self.deposit_status == DEPOSIT_DUE


@dataclass
class LockerSummary:
    banks: int = 0
    lockers: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    active_allocations: int = 0
    overdue_returns: int = 0
    deposits_held: float = 0.0
    deposits_due: int = 0
    deposits_retained: float = 0.0
    by_bank: dict[str, dict[str, int]] = field(default_factory=dict)


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # FK target first.
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Lockers schema ready at %s", DB_PATH)
    _DB_READY = True


def _bank(r: _sql.Row) -> LockerBank:
    return LockerBank(
        bank_id=r["bank_id"], name=r["name"], location=r["location"],
        locker_size=r["locker_size"], active=bool(r["active"]),
        notes=r["notes"], created_at=r["created_at"],
        updated_at=r["updated_at"])


def _locker(r: _sql.Row) -> Locker:
    keys = r.keys()
    return Locker(
        locker_id=r["locker_id"], bank_id=r["bank_id"],
        number=r["number"], code=r["code"], key_number=r["key_number"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        bank_name=r["bank_name"] if "bank_name" in keys else None)


def _allocation(r: _sql.Row) -> Allocation:
    keys = r.keys()
    label = None
    if "bank_name" in keys and "number" in keys:
        label = f"{r['bank_name']} / {r['number']}"
    name = None
    if "first_name" in keys:
        name = " ".join(p for p in (r["first_name"], r["last_name"])
                        if p) or None
    return Allocation(
        allocation_id=r["allocation_id"], locker_id=r["locker_id"],
        student_id=r["student_id"], academic_year=r["academic_year"],
        allocated_on=r["allocated_on"], key_issued=bool(r["key_issued"]),
        code_issued=r["code_issued"],
        deposit_amount=float(r["deposit_amount"] or 0),
        deposit_status=r["deposit_status"],
        deposit_paid_on=r["deposit_paid_on"],
        returned_on=r["returned_on"],
        return_condition=r["return_condition"],
        deposit_settled_on=r["deposit_settled_on"],
        deposit_retained_reason=r["deposit_retained_reason"],
        status=r["status"], allocated_by=r["allocated_by"],
        notes=r["notes"], created_at=r["created_at"],
        updated_at=r["updated_at"], locker_label=label,
        student_name=name)


# ── Validation helpers ──────────────────────────────────────────────

def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _require(v: Any, label: str) -> str:
    s = _text(v)
    if not s:
        raise ValidationError(f"{label} is required")
    return s


def _date(v: Any, label: str, *, required: bool = False) -> str | None:
    s = _text(v)
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _money(v: Any, label: str) -> float:
    if v in (None, ""):
        return 0.0
    try:
        f = round(float(v), 2)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if f < 0:
        raise ValidationError(f"{label} cannot be negative")
    return f


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def current_academic_year(today: _dt.date | None = None) -> str:
    """``2026/27`` style label; the year turns over on 1 September."""
    d = today or _dt.date.today()
    start = d.year if d.month >= 9 else d.year - 1
    return f"{start}/{(start + 1) % 100:02d}"


def validate_academic_year(v: Any) -> str:
    s = _text(v) or current_academic_year()
    m = _YEAR_RE.match(s)
    if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
        raise ValidationError(
            "Academic year must look like 2026/27 (consecutive years)")
    return s


def academic_year_end(year: str) -> _dt.date:
    """Lockers come back by 31 July at the end of the year."""
    start = int(validate_academic_year(year)[:4])
    return _dt.date(start + 1, 7, 31)


def _validate_student(v: Any) -> str:
    sid = _require(v, "Student")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


# ── Banks ───────────────────────────────────────────────────────────

def create_bank(payload: dict[str, Any]) -> LockerBank:
    init_db()
    name = _require(payload.get("name"), "Bank name")
    size = _choice(payload.get("locker_size"), LOCKER_SIZES, "Locker size",
                   DEFAULT_LOCKER_SIZE)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO locker_banks (name, location, locker_size, "
                "active, notes) VALUES (?, ?, ?, ?, ?)",
                (name, _text(payload.get("location")), size,
                 0 if payload.get("active") is False else 1,
                 _text(payload.get("notes"))))
        except _sql.IntegrityError:
            raise ValidationError(
                f"A locker bank called '{name}' already exists") from None
        new_id = cur.lastrowid
    logger.info("Created locker bank #%d (%s)", new_id, name)
    out = get_bank(new_id)
    assert out is not None
    return out


def update_bank(bank_id: int, payload: dict[str, Any]) -> LockerBank:
    existing = get_bank(bank_id)
    if existing is None:
        raise ValidationError(f"No locker bank #{bank_id}")
    name = _require(payload.get("name", existing.name), "Bank name")
    size = _choice(payload.get("locker_size", existing.locker_size),
                   LOCKER_SIZES, "Locker size")
    active = payload.get("active", existing.active)
    with _connect() as conn:
        try:
            conn.execute(
                "UPDATE locker_banks SET name=?, location=?, locker_size=?, "
                "active=?, notes=?, updated_at=datetime('now') "
                "WHERE bank_id=?",
                (name, _text(payload.get("location", existing.location)),
                 size, 1 if active else 0,
                 _text(payload.get("notes", existing.notes)), bank_id))
        except _sql.IntegrityError:
            raise ValidationError(
                f"A locker bank called '{name}' already exists") from None
    out = get_bank(bank_id)
    assert out is not None
    return out


def get_bank(bank_id: int) -> LockerBank | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM locker_banks WHERE bank_id=?",
                         (bank_id,)).fetchone()
    return _bank(r) if r else None


def list_banks(*, active_only: bool = False) -> list[LockerBank]:
    init_db()
    sql = "SELECT * FROM locker_banks"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY name COLLATE NOCASE"
    with _connect() as conn:
        return [_bank(r) for r in conn.execute(sql).fetchall()]


def delete_bank(bank_id: int) -> bool:
    """Remove an empty bank. A bank with lockers is deactivated instead
    by the caller — the lockers carry allocation history."""
    init_db()
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM lockers WHERE bank_id=?",
                         (bank_id,)).fetchone()[0]
        if n:
            raise ValidationError(
                f"Bank #{bank_id} still has {n} locker(s) — deactivate it "
                "instead")
        cur = conn.execute("DELETE FROM locker_banks WHERE bank_id=?",
                           (bank_id,))
    return bool(cur.rowcount)


# ── Lockers ─────────────────────────────────────────────────────────

_LOCKER_SELECT = (
    "SELECT l.*, b.name AS bank_name FROM lockers l "
    "JOIN locker_banks b ON b.bank_id = l.bank_id")


def create_locker(payload: dict[str, Any]) -> Locker:
    init_db()
    try:
        bank_id = int(payload.get("bank_id"))
    except (TypeError, ValueError):
        raise ValidationError("Bank is required") from None
    if get_bank(bank_id) is None:
        raise ValidationError(f"No locker bank #{bank_id}")
    number = _require(payload.get("number"), "Locker number")
    status = _choice(payload.get("status"), (AVAILABLE, OUT_OF_ORDER),
                     "Status", AVAILABLE)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO lockers (bank_id, number, code, key_number, "
                "status, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (bank_id, number, _text(payload.get("code")),
                 _text(payload.get("key_number")), status,
                 _text(payload.get("notes"))))
        except _sql.IntegrityError:
            raise ValidationError(
                f"Locker {number} already exists in that bank") from None
        new_id = cur.lastrowid
    out = get_locker(new_id)
    assert out is not None
    return out


def add_lockers(bank_id: int, first: int, count: int, *,
                prefix: str = "", width: int = 0) -> list[Locker]:
    """Number a run of lockers into a bank: ``prefix`` + first..first+count-1
    (zero-padded to ``width``). Numbers already present are skipped."""
    if count < 1 or count > 500:
        raise ValidationError("Count must be between 1 and 500")
    if first < 0:
        raise ValidationError("First number cannot be negative")
    made: list[Locker] = []
    for n in range(first, first + count):
        number = f"{prefix}{str(n).zfill(width) if width else n}"
        try:
            made.append(create_locker({"bank_id": bank_id,
                                       "number": number}))
        except ValidationError as e:
            if "already exists" not in str(e):
                raise
    logger.info("Added %d locker(s) to bank #%d", len(made), bank_id)
    return made


def update_locker(locker_id: int, payload: dict[str, Any]) -> Locker:
    existing = get_locker(locker_id)
    if existing is None:
        raise ValidationError(f"No locker #{locker_id}")
    number = _require(payload.get("number", existing.number),
                      "Locker number")
    with _connect() as conn:
        try:
            conn.execute(
                "UPDATE lockers SET number=?, code=?, key_number=?, "
                "notes=?, updated_at=datetime('now') WHERE locker_id=?",
                (number, _text(payload.get("code", existing.code)),
                 _text(payload.get("key_number", existing.key_number)),
                 _text(payload.get("notes", existing.notes)), locker_id))
        except _sql.IntegrityError:
            raise ValidationError(
                f"Locker {number} already exists in that bank") from None
    if "status" in payload and payload["status"] != existing.status:
        return set_locker_status(locker_id, payload["status"])
    out = get_locker(locker_id)
    assert out is not None
    return out


def set_locker_status(locker_id: int, status: str) -> Locker:
    """Available <-> Out of Order. Allocated is set by :func:`allocate`
    only — a locker cannot be marked out of order while somebody has it."""
    existing = get_locker(locker_id)
    if existing is None:
        raise ValidationError(f"No locker #{locker_id}")
    status = _choice(status, (AVAILABLE, OUT_OF_ORDER), "Status")
    if existing.status == ALLOCATED:
        raise ValidationError(
            f"Locker {existing.label} is allocated — return it first")
    with _connect() as conn:
        conn.execute("UPDATE lockers SET status=?, updated_at=datetime('now')"
                     " WHERE locker_id=?", (status, locker_id))
    out = get_locker(locker_id)
    assert out is not None
    return out


def get_locker(locker_id: int) -> Locker | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_LOCKER_SELECT} WHERE l.locker_id=?",
                         (locker_id,)).fetchone()
    return _locker(r) if r else None


def list_lockers(*, bank_id: int | None = None, status: str | None = None,
                 number_like: str | None = None) -> list[Locker]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if bank_id is not None:
        clauses.append("l.bank_id = ?")
        args.append(int(bank_id))
    if status:
        clauses.append("l.status = ?")
        args.append(_choice(status, LOCKER_STATUSES, "Status"))
    if number_like:
        clauses.append("l.number LIKE ?")
        args.append(f"%{number_like.strip()}%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    # Natural-ish order: numeric part first so 2 sorts before 10.
    sql = (f"{_LOCKER_SELECT}{where} ORDER BY b.name COLLATE NOCASE, "
           "LENGTH(l.number), l.number")
    with _connect() as conn:
        return [_locker(r) for r in conn.execute(sql, args).fetchall()]


def delete_locker(locker_id: int) -> bool:
    """Remove a locker entered by mistake. One that was ever allocated is
    kept (mark it Out of Order) — the allocation history points at it."""
    init_db()
    with _connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM locker_allocations WHERE locker_id=?",
            (locker_id,)).fetchone()[0]
        if n:
            raise ValidationError(
                "This locker has allocation history — mark it Out of "
                "Order instead")
        cur = conn.execute("DELETE FROM lockers WHERE locker_id=?",
                           (locker_id,))
    return bool(cur.rowcount)


# ── Allocations ─────────────────────────────────────────────────────

_ALLOC_SELECT = (
    "SELECT a.*, l.number, b.name AS bank_name, s.first_name, s.last_name "
    "FROM locker_allocations a "
    "JOIN lockers l ON l.locker_id = a.locker_id "
    "JOIN locker_banks b ON b.bank_id = l.bank_id "
    "LEFT JOIN students s ON s.student_id = a.student_id")


def allocate(locker_id: int, student_id: str, *,
             academic_year: str | None = None,
             allocated_on: str | None = None,
             deposit_amount: float | None = None,
             deposit_paid: bool = False,
             key_issued: bool = False,
             code: str | None = None,
             allocated_by: str | None = None,
             notes: str | None = None) -> Allocation:
    """Give a student a locker for an academic year.

    ``code`` is the combination given to the student (defaults to the
    locker's current code). A deposit of 0 records "no deposit"; any
    other amount is Due until :func:`record_deposit_paid` (or pass
    ``deposit_paid=True`` when the money is taken at the desk).
    """
    init_db()
    locker = get_locker(locker_id)
    if locker is None:
        raise ValidationError(f"No locker #{locker_id}")
    if locker.status != AVAILABLE:
        raise ValidationError(
            f"Locker {locker.label} is {locker.status}")
    sid = _validate_student(student_id)
    year = validate_academic_year(academic_year)
    on = _date(allocated_on, "Allocated on") or _dt.date.today().isoformat()
    amount = _money(DEFAULT_DEPOSIT if deposit_amount is None
                    else deposit_amount, "Deposit")
    if amount == 0:
        dstatus, paid_on = DEPOSIT_NONE, None
    elif deposit_paid:
        dstatus, paid_on = DEPOSIT_PAID, on
    else:
        dstatus, paid_on = DEPOSIT_DUE, None
    with _connect() as conn:
        held = conn.execute(
            "SELECT a.allocation_id, l.number, b.name FROM "
            "locker_allocations a JOIN lockers l ON l.locker_id=a.locker_id "
            "JOIN locker_banks b ON b.bank_id=l.bank_id "
            "WHERE a.student_id=? AND a.status='Active'", (sid,)).fetchone()
        if held:
            raise ValidationError(
                f"Student {sid} already has locker {held[2]} / {held[1]}")
        try:
            cur = conn.execute(
                "INSERT INTO locker_allocations (locker_id, student_id, "
                "academic_year, allocated_on, key_issued, code_issued, "
                "deposit_amount, deposit_status, deposit_paid_on, status, "
                "allocated_by, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (locker_id, sid, year, on, 1 if key_issued else 0,
                 _text(code) or locker.code, amount, dstatus, paid_on,
                 ACTIVE, _text(allocated_by), _text(notes)))
        except _sql.IntegrityError:
            raise ValidationError(
                f"Locker {locker.label} is already allocated") from None
        conn.execute("UPDATE lockers SET status=?, updated_at=datetime('now')"
                     " WHERE locker_id=?", (ALLOCATED, locker_id))
        new_id = cur.lastrowid
    logger.info("Locker %s allocated to %s for %s", locker.label, sid, year)
    out = get_allocation(new_id)
    assert out is not None
    return out


def record_deposit_paid(allocation_id: int, *,
                        paid_on: str | None = None) -> Allocation:
    a = _require_allocation(allocation_id)
    if a.deposit_status != DEPOSIT_DUE:
        raise ValidationError(
            f"Deposit is {a.deposit_status}, not Due")
    on = _date(paid_on, "Paid on") or _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE locker_allocations SET deposit_status=?, "
            "deposit_paid_on=?, updated_at=datetime('now') "
            "WHERE allocation_id=?", (DEPOSIT_PAID, on, allocation_id))
    return _require_allocation(allocation_id)


def issue_key(allocation_id: int, *, key_issued: bool = True,
              code: str | None = None) -> Allocation:
    """Record that the key was handed over (or the code given/changed)."""
    a = _require_allocation(allocation_id)
    if not a.is_active:
        raise ValidationError("That allocation has been returned")
    with _connect() as conn:
        conn.execute(
            "UPDATE locker_allocations SET key_issued=?, "
            "code_issued=COALESCE(?, code_issued), "
            "updated_at=datetime('now') WHERE allocation_id=?",
            (1 if key_issued else 0, _text(code), allocation_id))
    return _require_allocation(allocation_id)


def return_locker(allocation_id: int, *,
                  returned_on: str | None = None,
                  condition: str = "Good",
                  refund_deposit: bool = True,
                  retain_reason: str | None = None,
                  notes: str | None = None) -> Allocation:
    """Close an allocation.

    A paid deposit is either refunded or retained — retaining needs a
    reason, because the student (or their parent) will ask. A deposit
    still Due on return is written off as Retained with the reason
    "Never paid" unless one is given. Damaged / Key Lost puts the locker
    Out of Order until it is fixed.
    """
    a = _require_allocation(allocation_id)
    if not a.is_active:
        raise ValidationError("That locker has already been returned")
    on = _date(returned_on, "Returned on") or _dt.date.today().isoformat()
    if on < a.allocated_on:
        raise ValidationError("Return date is before the allocation date")
    cond = _choice(condition, RETURN_CONDITIONS, "Condition", "Good")
    reason = _text(retain_reason)
    dstatus = a.deposit_status
    settled = None
    if a.deposit_status == DEPOSIT_PAID:
        if refund_deposit:
            dstatus, settled, reason = DEPOSIT_REFUNDED, on, None
        else:
            if not reason:
                raise ValidationError(
                    "Give a reason for retaining the deposit")
            dstatus, settled = DEPOSIT_RETAINED, on
    elif a.deposit_status == DEPOSIT_DUE:
        dstatus, settled = DEPOSIT_RETAINED, on
        reason = reason or "Never paid"
    else:
        reason = None
    new_locker_status = (OUT_OF_ORDER if cond in _OUT_OF_ORDER_CONDITIONS
                         else AVAILABLE)
    note = _text(notes)
    with _connect() as conn:
        conn.execute(
            "UPDATE locker_allocations SET status=?, returned_on=?, "
            "return_condition=?, deposit_status=?, deposit_settled_on=?, "
            "deposit_retained_reason=?, "
            "notes=CASE WHEN ? IS NULL THEN notes "
            "ELSE COALESCE(notes || '; ', '') || ? END, "
            "updated_at=datetime('now') WHERE allocation_id=?",
            (RETURNED, on, cond, dstatus, settled, reason, note, note,
             allocation_id))
        conn.execute("UPDATE lockers SET status=?, updated_at=datetime('now')"
                     " WHERE locker_id=?", (new_locker_status, a.locker_id))
    logger.info("Locker allocation #%d returned (%s, deposit %s)",
                allocation_id, cond, dstatus)
    return _require_allocation(allocation_id)


def _require_allocation(allocation_id: int) -> Allocation:
    a = get_allocation(allocation_id)
    if a is None:
        raise ValidationError(f"No locker allocation #{allocation_id}")
    return a


def get_allocation(allocation_id: int) -> Allocation | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_ALLOC_SELECT} WHERE a.allocation_id=?",
                         (allocation_id,)).fetchone()
    return _allocation(r) if r else None


def list_allocations(*, student_id: str | None = None,
                     academic_year: str | None = None,
                     locker_id: int | None = None,
                     bank_id: int | None = None,
                     active_only: bool = False,
                     deposit_status: str | None = None) -> list[Allocation]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("a.student_id = ?")
        args.append(student_id.strip())
    if academic_year:
        clauses.append("a.academic_year = ?")
        args.append(validate_academic_year(academic_year))
    if locker_id is not None:
        clauses.append("a.locker_id = ?")
        args.append(int(locker_id))
    if bank_id is not None:
        clauses.append("l.bank_id = ?")
        args.append(int(bank_id))
    if active_only:
        clauses.append("a.status = 'Active'")
    if deposit_status:
        clauses.append("a.deposit_status = ?")
        args.append(_choice(deposit_status, DEPOSIT_STATUSES, "Deposit"))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"{_ALLOC_SELECT}{where} ORDER BY a.status, "
           "b.name COLLATE NOCASE, LENGTH(l.number), l.number, "
           "a.allocated_on DESC")
    with _connect() as conn:
        return [_allocation(r) for r in conn.execute(sql, args).fetchall()]


def locker_for_student(student_id: str) -> Allocation | None:
    rows = list_allocations(student_id=student_id, active_only=True)
    return rows[0] if rows else None


def overdue_returns(*, as_of: str | None = None,
                    academic_year: str | None = None) -> list[Allocation]:
    """Active allocations whose year has ended (31 July) on ``as_of``.

    With ``academic_year`` given, every still-active allocation for that
    year is listed regardless of date — the end-of-year chase list.
    """
    day = _date(as_of, "As of") or _dt.date.today().isoformat()
    rows = list_allocations(active_only=True, academic_year=academic_year)
    if academic_year:
        return rows
    return [a for a in rows
            if academic_year_end(a.academic_year).isoformat() < day]


# ── Summary ─────────────────────────────────────────────────────────

def summary() -> LockerSummary:
    init_db()
    out = LockerSummary(by_status={s: 0 for s in LOCKER_STATUSES})
    out.banks = len(list_banks())
    for lk in list_lockers():
        out.lockers += 1
        out.by_status[lk.status] = out.by_status.get(lk.status, 0) + 1
        bank = out.by_bank.setdefault(
            lk.bank_name or str(lk.bank_id),
            {s: 0 for s in LOCKER_STATUSES})
        bank[lk.status] = bank.get(lk.status, 0) + 1
    for a in list_allocations():
        if a.is_active:
            out.active_allocations += 1
            if a.deposit_status == DEPOSIT_PAID:
                out.deposits_held += a.deposit_amount
            elif a.deposit_status == DEPOSIT_DUE:
                out.deposits_due += 1
        elif a.deposit_status == DEPOSIT_RETAINED:
            out.deposits_retained += a.deposit_amount
    out.overdue_returns = len(overdue_returns())
    out.deposits_held = round(out.deposits_held, 2)
    out.deposits_retained = round(out.deposits_retained, 2)
    return out
