"""Bursary Applications data layer for the Sixth Form System.

Models the 16-19 bursary fund (and similar discretionary support):

* ``bursary_applications`` — one row per application: student,
  category, year, amount requested, amount awarded, status,
  household details, decision notes.
* ``bursary_disbursements`` — payments made out against an awarded
  application (e.g. weekly lunch top-up, monthly transport grant,
  one-off equipment payment).

Balance for an application:
    paid = sum(disbursement.amount where status='Paid')
    remaining = (amount_awarded or 0) - paid

Status lifecycle:
    Submitted → Under Review → Approved → Paid in Full
                             ↘ Partially Paid
                             ↘ Rejected / Cancelled / Withdrawn

When an application is Approved with no payments yet → 'Approved'.
When paid < awarded → 'Partially Paid'.
When paid >= awarded → 'Paid in Full'. (Computed on the fly when
``view_application`` is used; the stored ``status`` is what staff
explicitly set.)
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from typing import Any
from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.BURSARIES_DB

BURSARY_TYPES: tuple[str, ...] = (
    "Vulnerable Bursary", "Discretionary Bursary",
    "Free Meals (FSM)", "Transport", "Travel Pass",
    "Books & Equipment", "Uniform", "Trips & Visits",
    "Exam Fees", "UCAS / Open Days", "Childcare",
    "Hardship Fund", "Other",
)
DEFAULT_TYPE: str = "Discretionary Bursary"

# 'Vulnerable Bursary' has a statutory student-level entitlement check
# (looked-after children, care leavers, UC recipients in own name,
# Income Support, DLA/PIP). We don't try to enforce eligibility here
# — staff log the basis in `eligibility_basis`.
ELIGIBILITY_BASES: tuple[str, ...] = (
    "Looked-After Child", "Care Leaver",
    "Universal Credit (own name)", "Income Support",
    "Disability Benefits (DLA/PIP)",
    "Free School Meals (Y11)",
    "Household income < £20k",
    "Household income < £30k",
    "Discretionary (staff judgement)",
    "Other",
)

STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Awaiting Evidence", "Under Review",
    "Approved", "Partially Paid", "Paid in Full",
    "Rejected", "Cancelled", "Withdrawn",
)
DEFAULT_STATUS: str = "Submitted"
ACTIVE_STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Awaiting Evidence", "Under Review",
    "Approved", "Partially Paid")
APPROVED_STATUSES: tuple[str, ...] = (
    "Approved", "Partially Paid", "Paid in Full")

DISBURSEMENT_METHODS: tuple[str, ...] = (
    "Bank Transfer", "Card / Voucher", "Cash",
    "Cheque", "Travel Pass", "Lunch Card",
    "Direct to Supplier", "Other",
)
DEFAULT_DISBURSEMENT_METHOD: str = "Bank Transfer"

DISBURSEMENT_STATUSES: tuple[str, ...] = (
    "Paid", "Pending", "Failed", "Reversed",
)
DEFAULT_DISBURSEMENT_STATUS: str = "Paid"

CURRENCY_SYMBOL: str = "£"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bursary_applications (
    application_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    bursary_type      TEXT NOT NULL DEFAULT 'Discretionary Bursary',
    academic_year     TEXT,
    application_date  TEXT NOT NULL,
    amount_requested  REAL,
    amount_awarded    REAL,
    status            TEXT NOT NULL DEFAULT 'Submitted',
    eligibility_basis TEXT,
    household_income  REAL,
    household_size    INTEGER,
    evidence_received INTEGER NOT NULL DEFAULT 0,
    evidence_note     TEXT,
    reason            TEXT,
    assessed_by       TEXT,
    assessed_on       TEXT,
    decision_note     TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id)  REFERENCES students(student_id)
        ON DELETE CASCADE,
    FOREIGN KEY (assessed_by) REFERENCES staff(staff_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS bursary_disbursements (
    disbursement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  INTEGER NOT NULL,
    amount          REAL NOT NULL,
    paid_on         TEXT NOT NULL,
    method          TEXT NOT NULL DEFAULT 'Bank Transfer',
    status          TEXT NOT NULL DEFAULT 'Paid',
    reference       TEXT,
    recorded_by     TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (application_id)
        REFERENCES bursary_applications(application_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bur_student  ON bursary_applications(student_id);
CREATE INDEX IF NOT EXISTS idx_bur_year     ON bursary_applications(academic_year);
CREATE INDEX IF NOT EXISTS idx_bur_status   ON bursary_applications(status);
CREATE INDEX IF NOT EXISTS idx_bur_type     ON bursary_applications(bursary_type);
CREATE INDEX IF NOT EXISTS idx_bd_app       ON bursary_disbursements(application_id);
CREATE INDEX IF NOT EXISTS idx_bd_paid_on   ON bursary_disbursements(paid_on);
"""


@dataclass
class Application:
    application_id: int
    student_id: str
    bursary_type: str
    academic_year: str | None
    application_date: str
    amount_requested: float | None
    amount_awarded: float | None
    status: str
    eligibility_basis: str | None
    household_income: float | None
    household_size: int | None
    evidence_received: bool
    evidence_note: str | None
    reason: str | None
    assessed_by: str | None
    assessed_on: str | None
    decision_note: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_approved(self) -> bool:
        return self.status in APPROVED_STATUSES

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES


@dataclass
class Disbursement:
    disbursement_id: int
    application_id: int
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
class ApplicationView:
    app: Application
    paid: float
    remaining: float
    derived_status: str
    disbursement_count: int
    student_name: str


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    from education_system.sixthform_system.modules.domain.staff import staff
    from education_system.sixthform_system.modules.domain.students import students as _staff
    from education_system.sixthform_system.modules.domain.students import students as _students
    _students.init_db()
    _staff.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Bursaries schema ready at %s", DB_PATH)


def _row_app(r: sqlite3.Row) -> Application:
    return Application(
        application_id=r["application_id"], student_id=r["student_id"],
        bursary_type=r["bursary_type"],
        academic_year=r["academic_year"],
        application_date=r["application_date"],
        amount_requested=r["amount_requested"],
        amount_awarded=r["amount_awarded"],
        status=r["status"],
        eligibility_basis=r["eligibility_basis"],
        household_income=r["household_income"],
        household_size=r["household_size"],
        evidence_received=bool(r["evidence_received"]),
        evidence_note=r["evidence_note"], reason=r["reason"],
        assessed_by=r["assessed_by"], assessed_on=r["assessed_on"],
        decision_note=r["decision_note"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_disb(r: sqlite3.Row) -> Disbursement:
    return Disbursement(
        disbursement_id=r["disbursement_id"],
        application_id=r["application_id"],
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
                       required: bool = False,
                       allow_zero: bool = True) -> float | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{label} must be a number") from None
    if d.as_tuple().exponent < -2:
        raise ValidationError(
            f"{label} must have at most 2 decimal places")
    if d < 0:
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
    from education_system.sixthform_system.modules.domain.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_staff(v: Any) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    sid = str(v).strip().upper()
    from education_system.sixthform_system.modules.domain.staff import staff as _staff
    if _staff.get_staff(sid) is None:
        raise ValidationError(f"No staff with id {sid}")
    return sid


def _validate_app_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(d.get("student_id"))

    btype = (d.get("bursary_type") or DEFAULT_TYPE).strip()
    if btype not in BURSARY_TYPES:
        raise ValidationError(
            f"Bursary type must be one of: {', '.join(BURSARY_TYPES)}")
    out["bursary_type"] = btype

    out["academic_year"] = (d.get("academic_year") or "").strip() or None
    out["application_date"] = _validate_date(
        d.get("application_date") or _date.today().isoformat(),
        "Application date", required=True)

    out["amount_requested"] = _validate_amount(
        d.get("amount_requested"), "Amount requested")
    out["amount_awarded"] = _validate_amount(
        d.get("amount_awarded"), "Amount awarded")

    status = (d.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    basis = (d.get("eligibility_basis") or "").strip()
    if basis:
        if basis not in ELIGIBILITY_BASES:
            raise ValidationError(
                "Eligibility basis must be one of: "
                f"{', '.join(ELIGIBILITY_BASES)} (or empty)")
        out["eligibility_basis"] = basis
    else:
        out["eligibility_basis"] = None

    out["household_income"] = _validate_amount(
        d.get("household_income"), "Household income")
    hs = d.get("household_size")
    if hs in (None, ""):
        out["household_size"] = None
    else:
        try:
            h = int(hs)
        except (TypeError, ValueError):
            raise ValidationError(
                "Household size must be a whole number") from None
        if h < 1 or h > 30:
            raise ValidationError("Household size must be 1..30")
        out["household_size"] = h

    out["evidence_received"] = bool(d.get("evidence_received"))
    out["evidence_note"] = (d.get("evidence_note") or "").strip() or None
    out["reason"]        = (d.get("reason") or "").strip() or None
    out["assessed_by"]   = _validate_staff(d.get("assessed_by"))
    out["assessed_on"]   = _validate_date(d.get("assessed_on"),
                                            "Assessed on")
    out["decision_note"] = (d.get("decision_note") or "").strip() or None
    out["notes"]         = (d.get("notes") or "").strip() or None

    # Light cross-field rules.
    if status in APPROVED_STATUSES and out["amount_awarded"] is None:
        raise ValidationError(
            "Approved applications must have an awarded amount")
    if status in ("Rejected", "Cancelled", "Withdrawn") \
            and out["amount_awarded"] not in (None, 0.0) \
            and out["amount_awarded"] > 0:
        # Awarding then rejecting is weird; warn via validation.
        # Not strictly invalid — allow it but require a decision note.
        if not out["decision_note"]:
            raise ValidationError(
                "When marking a previously-awarded application as "
                f"{status}, please add a decision note explaining why.")

    if (out["amount_requested"] is not None
            and out["amount_awarded"] is not None
            and out["amount_awarded"] > out["amount_requested"]
            and not out["decision_note"]):
        # Allowed but requires a note.
        raise ValidationError(
            "Amount awarded exceeds requested — please add a "
            "decision note explaining the uplift.")
    return out


def _validate_disb_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["amount"] = _validate_amount(
        d.get("amount"), "Amount", required=True, allow_zero=False)
    out["paid_on"] = _validate_date(
        d.get("paid_on") or _date.today().isoformat(),
        "Paid on", required=True)

    method = (d.get("method") or DEFAULT_DISBURSEMENT_METHOD).strip()
    if method not in DISBURSEMENT_METHODS:
        raise ValidationError(
            "Method must be one of: "
            f"{', '.join(DISBURSEMENT_METHODS)}")
    out["method"] = method

    status = (d.get("status") or DEFAULT_DISBURSEMENT_STATUS).strip()
    if status not in DISBURSEMENT_STATUSES:
        raise ValidationError(
            "Status must be one of: "
            f"{', '.join(DISBURSEMENT_STATUSES)}")
    out["status"] = status

    out["reference"]   = (d.get("reference") or "").strip() or None
    out["recorded_by"] = (d.get("recorded_by") or "").strip() or None
    out["notes"]       = (d.get("notes") or "").strip() or None
    return out


# ── Application CRUD ─────────────────────────────────────────────

def create_application(d: dict[str, Any]) -> Application:
    init_db()
    p = _validate_app_payload(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO bursary_applications (
                  student_id, bursary_type, academic_year,
                  application_date, amount_requested, amount_awarded,
                  status, eligibility_basis, household_income,
                  household_size, evidence_received, evidence_note,
                  reason, assessed_by, assessed_on, decision_note,
                  notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["bursary_type"], p["academic_year"],
             p["application_date"], p["amount_requested"],
             p["amount_awarded"], p["status"], p["eligibility_basis"],
             p["household_income"], p["household_size"],
             int(p["evidence_received"]), p["evidence_note"],
             p["reason"], p["assessed_by"], p["assessed_on"],
             p["decision_note"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_application(new_id)
    assert out is not None
    logger.info(
        "Created bursary application #%d for %s (%s, status=%s)",
        new_id, p["student_id"], p["bursary_type"], p["status"])
    return out


def get_application(application_id: int) -> Application | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM bursary_applications "
            "WHERE application_id = ?",
            (application_id,)).fetchone()
        return _row_app(r) if r else None


def list_applications(
    *,
    student_id: str | None = None,
    bursary_type: str | None = None,
    status: str | None = None,
    academic_year: str | None = None,
    assessed_by: str | None = None,
    active_only: bool = False,
    approved_only: bool = False,
) -> list[Application]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if bursary_type:
        if bursary_type not in BURSARY_TYPES:
            raise ValidationError(
                f"Bursary type must be one of: "
                f"{', '.join(BURSARY_TYPES)}")
        clauses.append("bursary_type = ?")
        args.append(bursary_type)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year.strip())
    if assessed_by:
        clauses.append("assessed_by = ?")
        args.append(assessed_by.strip().upper())
    if active_only:
        ph = ",".join("?" * len(ACTIVE_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(ACTIVE_STATUSES)
    if approved_only:
        ph = ",".join("?" * len(APPROVED_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(APPROVED_STATUSES)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM bursary_applications {where} "
           "ORDER BY application_date DESC, application_id DESC")
    with _connect() as conn:
        return [_row_app(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_application(application_id: int,
                         d: dict[str, Any]) -> Application:
    init_db()
    existing = get_application(application_id)
    if existing is None:
        raise ValidationError(f"No application #{application_id}")
    merged = {
        "student_id":        existing.student_id,
        "bursary_type":      d.get("bursary_type", existing.bursary_type),
        "academic_year":     d.get("academic_year",
                                     existing.academic_year),
        "application_date":  d.get("application_date",
                                     existing.application_date),
        "amount_requested":  d.get("amount_requested",
                                     existing.amount_requested),
        "amount_awarded":    d.get("amount_awarded",
                                     existing.amount_awarded),
        "status":            d.get("status", existing.status),
        "eligibility_basis": d.get("eligibility_basis",
                                     existing.eligibility_basis),
        "household_income":  d.get("household_income",
                                     existing.household_income),
        "household_size":    d.get("household_size",
                                     existing.household_size),
        "evidence_received": d.get("evidence_received",
                                     existing.evidence_received),
        "evidence_note":     d.get("evidence_note",
                                     existing.evidence_note),
        "reason":            d.get("reason", existing.reason),
        "assessed_by":       d.get("assessed_by", existing.assessed_by),
        "assessed_on":       d.get("assessed_on", existing.assessed_on),
        "decision_note":     d.get("decision_note",
                                     existing.decision_note),
        "notes":             d.get("notes", existing.notes),
    }
    p = _validate_app_payload(merged)

    paid = _paid_total(application_id)
    if (p["amount_awarded"] is not None and p["amount_awarded"] < paid):
        raise ValidationError(
            f"Awarded {CURRENCY_SYMBOL}{p['amount_awarded']:.2f} is less than "
            f"already-paid {CURRENCY_SYMBOL}{paid:.2f}")

    with _connect() as conn:
        conn.execute(
            """UPDATE bursary_applications SET
                  bursary_type=?, academic_year=?, application_date=?,
                  amount_requested=?, amount_awarded=?, status=?,
                  eligibility_basis=?, household_income=?, household_size=?,
                  evidence_received=?, evidence_note=?, reason=?,
                  assessed_by=?, assessed_on=?, decision_note=?, notes=?,
                  updated_at=datetime('now')
               WHERE application_id=?""",
            (p["bursary_type"], p["academic_year"], p["application_date"],
             p["amount_requested"], p["amount_awarded"], p["status"],
             p["eligibility_basis"], p["household_income"],
             p["household_size"], int(p["evidence_received"]),
             p["evidence_note"], p["reason"], p["assessed_by"],
             p["assessed_on"], p["decision_note"], p["notes"],
             application_id),
        )
        conn.commit()
    out = get_application(application_id)
    assert out is not None
    logger.info(
        "Updated bursary application #%d (status=%s, awarded=%s)",
        application_id, out.status, out.amount_awarded)
    return out


def approve(application_id: int, amount_awarded: float,
              assessed_by: str | None = None,
              decision_note: str | None = None) -> Application:
    today = _date.today().isoformat()
    return update_application(application_id, {
        "status": "Approved",
        "amount_awarded": amount_awarded,
        "assessed_by": assessed_by,
        "assessed_on": today,
        "decision_note": decision_note,
    })


def reject(application_id: int,
             decision_note: str,
             assessed_by: str | None = None) -> Application:
    if not (decision_note or "").strip():
        raise ValidationError(
            "A decision note is required when rejecting")
    today = _date.today().isoformat()
    return update_application(application_id, {
        "status": "Rejected",
        "assessed_by": assessed_by,
        "assessed_on": today,
        "decision_note": decision_note,
    })


def set_status(application_id: int, status: str) -> Application:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_application(application_id, {"status": status})


def delete_application(application_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM bursary_applications WHERE application_id = ?",
            (application_id,))
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Deleted bursary application #%d (and its disbursements)",
                application_id)
            return True
        return False


# ── Disbursement CRUD ────────────────────────────────────────────

def _paid_total(application_id: int) -> float:
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s "
            "FROM bursary_disbursements "
            "WHERE application_id = ? AND status = 'Paid'",
            (application_id,)).fetchone()
    return round(float(r["s"]), 2)


def add_disbursement(application_id: int,
                       d: dict[str, Any]) -> Disbursement:
    init_db()
    app = get_application(application_id)
    if app is None:
        raise ValidationError(f"No application #{application_id}")
    if app.status not in APPROVED_STATUSES:
        raise ValidationError(
            "Disbursements can only be added to approved "
            "applications (current status: "
            f"{app.status})")
    p = _validate_disb_payload(d)

    if p["status"] == "Paid" and app.amount_awarded is not None:
        already = _paid_total(application_id)
        if round(already + p["amount"], 2) > app.amount_awarded + 0.001:
            raise ValidationError(
                f"This disbursement would push total paid to "
                f"{CURRENCY_SYMBOL}{already + p['amount']:.2f}, "
                f"exceeding awarded "
                f"{CURRENCY_SYMBOL}{app.amount_awarded:.2f}")

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO bursary_disbursements
                 (application_id, amount, paid_on, method, status,
                  reference, recorded_by, notes,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (application_id, p["amount"], p["paid_on"], p["method"],
             p["status"], p["reference"], p["recorded_by"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid

    # Auto-roll the application status if it makes sense.
    _auto_roll_status(application_id)
    out = get_disbursement(new_id)
    assert out is not None
    logger.info(
        "Added disbursement #%d (app=%d, %s%.2f, %s)",
        new_id, application_id, CURRENCY_SYMBOL, p["amount"], p["method"])
    return out


def get_disbursement(disbursement_id: int) -> Disbursement | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM bursary_disbursements WHERE disbursement_id = ?",
            (disbursement_id,)).fetchone()
        return _row_disb(r) if r else None


def list_disbursements(
    *,
    application_id: int | None = None,
    student_id: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Disbursement]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if application_id is not None:
        clauses.append("application_id = ?")
        args.append(application_id)
    if student_id:
        clauses.append("application_id IN (SELECT application_id "
                        "  FROM bursary_applications WHERE student_id = ?)")
        args.append(student_id.strip())
    if status:
        if status not in DISBURSEMENT_STATUSES:
            raise ValidationError(
                "Status must be one of: "
                f"{', '.join(DISBURSEMENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if date_from:
        clauses.append("paid_on >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("paid_on <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM bursary_disbursements {where} "
           "ORDER BY paid_on DESC, disbursement_id DESC")
    with _connect() as conn:
        return [_row_disb(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_disbursement(disbursement_id: int,
                          d: dict[str, Any]) -> Disbursement:
    init_db()
    existing = get_disbursement(disbursement_id)
    if existing is None:
        raise ValidationError(f"No disbursement #{disbursement_id}")
    merged = {
        "amount":      d.get("amount", existing.amount),
        "paid_on":     d.get("paid_on", existing.paid_on),
        "method":      d.get("method", existing.method),
        "status":      d.get("status", existing.status),
        "reference":   d.get("reference", existing.reference),
        "recorded_by": d.get("recorded_by", existing.recorded_by),
        "notes":       d.get("notes", existing.notes),
    }
    p = _validate_disb_payload(merged)

    # Check cap (excluding self).
    app = get_application(existing.application_id)
    if (app and app.amount_awarded is not None
            and p["status"] == "Paid"):
        with _connect() as conn:
            r = conn.execute(
                """SELECT COALESCE(SUM(amount), 0) AS s
                    FROM bursary_disbursements
                    WHERE application_id = ?
                      AND status = 'Paid'
                      AND disbursement_id <> ?""",
                (existing.application_id, disbursement_id)).fetchone()
        others = float(r["s"])
        if round(others + p["amount"], 2) > app.amount_awarded + 0.001:
            raise ValidationError(
                "Edit would push total paid above the awarded amount")

    with _connect() as conn:
        conn.execute(
            """UPDATE bursary_disbursements SET
                  amount=?, paid_on=?, method=?, status=?,
                  reference=?, recorded_by=?, notes=?,
                  updated_at=datetime('now')
               WHERE disbursement_id=?""",
            (p["amount"], p["paid_on"], p["method"], p["status"],
             p["reference"], p["recorded_by"], p["notes"],
             disbursement_id),
        )
        conn.commit()
    _auto_roll_status(existing.application_id)
    out = get_disbursement(disbursement_id)
    assert out is not None
    logger.info("Updated disbursement #%d", disbursement_id)
    return out


def delete_disbursement(disbursement_id: int) -> bool:
    init_db()
    existing = get_disbursement(disbursement_id)
    if existing is None:
        return False
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM bursary_disbursements "
            "WHERE disbursement_id = ?", (disbursement_id,))
        conn.commit()
    if cur.rowcount:
        _auto_roll_status(existing.application_id)
        logger.info("Deleted disbursement #%d", disbursement_id)
        return True
    return False


def _auto_roll_status(application_id: int) -> None:
    app = get_application(application_id)
    if app is None or not app.is_approved or app.amount_awarded is None:
        return
    paid = _paid_total(application_id)
    if paid <= 0:
        new = "Approved"
    elif paid >= app.amount_awarded - 0.001:
        new = "Paid in Full"
    else:
        new = "Partially Paid"
    if new != app.status:
        with _connect() as conn:
            conn.execute(
                "UPDATE bursary_applications SET status=?, "
                "updated_at=datetime('now') WHERE application_id=?",
                (new, application_id))
            conn.commit()
        logger.info("Application #%d auto-rolled to %s",
                    application_id, new)


# ── Views ────────────────────────────────────────────────────────

def view_application(application_id: int) -> ApplicationView | None:
    app = get_application(application_id)
    if app is None:
        return None
    paid = _paid_total(application_id)
    awarded = app.amount_awarded or 0.0
    from education_system.sixthform_system.modules.domain.students import students as _students
    s = _students.get_student(app.student_id)
    name = s.full_name if s else "(unknown)"
    return ApplicationView(
        app=app,
        paid=paid,
        remaining=round(max(0.0, awarded - paid), 2),
        derived_status=app.status,
        disbursement_count=len(
            list_disbursements(application_id=application_id)),
        student_name=name,
    )


def list_views(**kwargs) -> list[ApplicationView]:
    apps = list_applications(**kwargs)
    if not apps:
        return []
        from education_system.sixthform_system.modules.domain.students import students as _students
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    with _connect() as conn:
        rows = conn.execute(
            """SELECT application_id, COALESCE(SUM(amount), 0) AS s,
                       COUNT(*) AS n
                FROM bursary_disbursements
               WHERE status = 'Paid'
               GROUP BY application_id""").fetchall()
        paid_map = {r["application_id"]: float(r["s"]) for r in rows}
        count_rows = conn.execute(
            """SELECT application_id, COUNT(*) AS n
                FROM bursary_disbursements
                GROUP BY application_id""").fetchall()
        count_map = {r["application_id"]: r["n"] for r in count_rows}
    out = []
    for app in apps:
        paid = round(paid_map.get(app.application_id, 0.0), 2)
        awarded = app.amount_awarded or 0.0
        out.append(ApplicationView(
            app=app, paid=paid,
            remaining=round(max(0.0, awarded - paid), 2),
            derived_status=app.status,
            disbursement_count=count_map.get(app.application_id, 0),
            student_name=names.get(app.student_id, "(unknown)"),
        ))
    return out


def student_summary(student_id: str) -> tuple[float, float, float]:
    """Return (total_awarded, total_paid, total_remaining) for a student
    across all approved applications."""
    views = list_views(student_id=student_id, approved_only=True)
    awarded = round(sum(v.app.amount_awarded or 0.0 for v in views), 2)
    paid = round(sum(v.paid for v in views), 2)
    remaining = round(sum(v.remaining for v in views), 2)
    return awarded, paid, remaining


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class Summary:
    total_applications: int
    submitted: int
    under_review: int
    approved_active: int        # Approved + Partially Paid
    paid_in_full: int
    rejected: int
    cancelled_withdrawn: int

    total_requested: float
    total_awarded: float
    total_paid: float
    total_remaining: float

    by_type: dict[str, int]
    by_status: dict[str, int]
    by_basis: dict[str, int]
    avg_award: float | None

    top_recipients: list[tuple[str, str, float]]  # student_id, name, paid


def summary() -> Summary:
    init_db()
    views = list_views()
    by_type = {t: 0 for t in BURSARY_TYPES}
    by_status = {s: 0 for s in STATUSES}
    by_basis = {b: 0 for b in ELIGIBILITY_BASES}
    submitted = under = active_approved = paid_full = rejected = canc = 0
    total_req = total_aw = total_paid = total_rem = 0.0
    awarded_values: list[float] = []
    paid_per_student: dict[str, float] = {}
    names: dict[str, str] = {}

    for v in views:
        app = v.app
        by_type[app.bursary_type] = (
            by_type.get(app.bursary_type, 0) + 1)
        by_status[app.status] = by_status.get(app.status, 0) + 1
        if app.eligibility_basis:
            by_basis[app.eligibility_basis] = (
                by_basis.get(app.eligibility_basis, 0) + 1)
        if app.status in ("Submitted", "Awaiting Evidence"):
            submitted += 1
        if app.status == "Under Review":
            under += 1
        if app.status in ("Approved", "Partially Paid"):
            active_approved += 1
        if app.status == "Paid in Full":
            paid_full += 1
        if app.status == "Rejected":
            rejected += 1
        if app.status in ("Cancelled", "Withdrawn"):
            canc += 1
        if app.amount_requested:
            total_req += app.amount_requested
        if app.amount_awarded:
            total_aw += app.amount_awarded
            awarded_values.append(app.amount_awarded)
        total_paid += v.paid
        total_rem += v.remaining if app.is_approved else 0
        if v.paid > 0:
            paid_per_student[app.student_id] = (
                paid_per_student.get(app.student_id, 0.0) + v.paid)
            names[app.student_id] = v.student_name

    avg = round(
        sum(awarded_values) / len(awarded_values), 2
    ) if awarded_values else None

    top = sorted(paid_per_student.items(),
                  key=lambda kv: -kv[1])[:10]
    top_list = [(sid, names.get(sid, "?"), round(p, 2))
                 for sid, p in top]

    return Summary(
        total_applications=len(views),
        submitted=submitted, under_review=under,
        approved_active=active_approved, paid_in_full=paid_full,
        rejected=rejected, cancelled_withdrawn=canc,
        total_requested=round(total_req, 2),
        total_awarded=round(total_aw, 2),
        total_paid=round(total_paid, 2),
        total_remaining=round(total_rem, 2),
        by_type=by_type, by_status=by_status, by_basis=by_basis,
        avg_award=avg, top_recipients=top_list,
    )
