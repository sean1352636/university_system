"""Tuition fee rules, remissions and invoices for the Sixth Form System.

Most sixth-form learners pay no tuition: a home learner aged 16-18 on
31 August is ESFA-funded. Fees arise for learners aged 19+ on 31 August
of the academic year (unless they are continuing a programme they
started at 16-18, or have an EHC plan and are under 25) and for
international learners. This module works the fee out and raises it.

Four tables, all in the fees database:

* ``fee_student_profiles``  — per-learner fee facts the student record
  does not hold: residency category, "continuing 19+ learner", EHC plan.
* ``fee_rules``             — the college's fee schedule: an annual fee
  per (academic year, residency category, age band, fee status). A blank
  year, residency or fee status means "any"; the most specific matching
  rule wins. The fee status is the enrolment's ILR fee status (see
  :data:`FEE_STATUSES`) — it lets the schedule tell a full-cost 19+ home
  learner from a co-funded one. This is the sixth form's only fee
  schedule: the enrolment fee screens work fees out from it too.
* ``fee_remissions``        — waivers / remission per learner per year:
  full, percentage or a fixed amount, with reason and approver.
* ``fee_invoices``          — one numbered invoice (``INV-YYYY-NNNNN``)
  per learner per year, recording how the fee was worked out. Raising an
  invoice creates the chargeable ``fee_items`` row (category Tuition),
  so payments, balances, statements and receipts all use the existing
  fees + receipts structures.

The college configures its own rules — nothing is assumed about what a
19+ or international learner pays.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domains.finance.domain import (
    finance_calendar as fc,
)
from education_system.systems.sixth_form.domains.finance.domain.fees import fees

logger = logging.getLogger(__name__)

# ``None`` follows :data:`fees.DB_PATH` (sixthform.db in production) so a
# test that redirects the fees module redirects these tables too.
DB_PATH: Any = None

CURRENCY_SYMBOL: str = fees.CURRENCY_SYMBOL

RESIDENCY_CATEGORIES: tuple[str, ...] = (
    "Home (UK national, resident 3+ years)",
    "Settled / pre-settled status (EUSS)",
    "Refugee / humanitarian protection",
    "Asylum seeker (eligible for funding)",
    "Irish citizen",
    "International (student visa)",
    "International (other / no eligible status)",
    "Other (recorded in notes)",
)

AGE_16_18: str = "16-18"
AGE_19_CONTINUING: str = "19+ continuing"
AGE_19_24_EHCP: str = "19-24 with EHCP"
AGE_19_PLUS: str = "19+"
AGE_BANDS: tuple[str, ...] = (AGE_16_18, AGE_19_CONTINUING, AGE_19_24_EHCP,
                              AGE_19_PLUS)

REMISSION_TYPES: tuple[str, ...] = ("Full", "Percentage", "Fixed amount")
REMISSION_REASONS: tuple[str, ...] = (
    "Low income / benefits", "Unemployed", "Care leaver",
    "Asylum seeker", "Staff dependant", "Hardship (discretionary)",
    "Scholarship", "Other",
)

#: The ILR fee statuses that carry a tuition fee (the same strings as
#: ``enrolments.ilr.FEE_PAYING``) — a rule may be limited to one of them.
#: 16-19 funded and 19+ fully funded learners pay nothing, so no rule
#: names them.
FEE_CO_FUNDED: str = "19+ co-funded"
FEE_FULL_COST: str = "Full cost"
FEE_OVERSEAS: str = "Overseas"
FEE_STATUSES: tuple[str, ...] = (FEE_CO_FUNDED, FEE_FULL_COST, FEE_OVERSEAS)
#: Fee statuses only a rule naming that status can price: a co-funded
#: learner pays a share of the full fee, so a general rule is never right.
FEE_STATUSES_NEEDING_OWN_RULE: tuple[str, ...] = (FEE_CO_FUNDED,)

INVOICE_STATUSES: tuple[str, ...] = ("Issued", "Cancelled")

_INVOICE_RE = re.compile(r"^INV-(\d{4})-(\d{5})$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fee_student_profiles (
    student_id          TEXT PRIMARY KEY,
    residency_category  TEXT NOT NULL,
    continuing_learner  INTEGER NOT NULL DEFAULT 0,
    has_ehcp            INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    updated_by          TEXT,
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fee_rules (
    rule_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year       TEXT,
    residency_category  TEXT,
    age_band            TEXT NOT NULL,
    fee_status          TEXT,
    annual_fee          REAL NOT NULL,
    description         TEXT,
    priority            INTEGER NOT NULL DEFAULT 100,
    active              INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fee_remissions (
    remission_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    academic_year    TEXT NOT NULL,
    remission_type   TEXT NOT NULL,
    value            REAL NOT NULL DEFAULT 0,
    reason           TEXT NOT NULL,
    approved_by      TEXT NOT NULL,
    approved_on      TEXT NOT NULL,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fee_invoices (
    invoice_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number      TEXT NOT NULL UNIQUE,
    student_id          TEXT NOT NULL,
    academic_year       TEXT NOT NULL,
    age_on_31_aug       INTEGER,
    residency_category  TEXT,
    age_band            TEXT,
    fee_status          TEXT,
    rule_id             INTEGER,
    gross_fee           REAL NOT NULL,
    remission_amount    REAL NOT NULL DEFAULT 0,
    net_fee             REAL NOT NULL,
    fee_id              INTEGER,
    status              TEXT NOT NULL DEFAULT 'Issued',
    issued_on           TEXT NOT NULL,
    due_date            TEXT,
    issued_by           TEXT,
    cancelled_reason    TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    FOREIGN KEY (fee_id) REFERENCES fee_items(fee_id) ON DELETE SET NULL,
    FOREIGN KEY (rule_id) REFERENCES fee_rules(rule_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_feerule_band  ON fee_rules(age_band);
CREATE INDEX IF NOT EXISTS idx_feerem_student ON fee_remissions(student_id, academic_year);
CREATE INDEX IF NOT EXISTS idx_feeinv_student ON fee_invoices(student_id, academic_year);
"""

ValidationError = fees.ValidationError


@dataclass
class FeeProfile:
    student_id: str
    residency_category: str
    continuing_learner: bool
    has_ehcp: bool
    notes: str | None
    updated_by: str | None
    updated_at: str | None


@dataclass
class FeeRule:
    rule_id: int
    academic_year: str | None
    residency_category: str | None
    age_band: str
    annual_fee: float
    description: str | None
    priority: int
    active: bool
    fee_status: str | None = None


@dataclass
class Remission:
    remission_id: int
    student_id: str
    academic_year: str
    remission_type: str
    value: float
    reason: str
    approved_by: str
    approved_on: str
    notes: str | None


@dataclass
class FeeCalculation:
    student_id: str
    student_name: str
    academic_year: str
    date_of_birth: str
    age_on_31_aug: int
    age_band: str
    residency_category: str
    rule: FeeRule
    gross_fee: float
    remissions: list[Remission]
    remission_amount: float
    net_fee: float
    explanation: list[str] = field(default_factory=list)
    fee_status: str | None = None


@dataclass
class Invoice:
    invoice_id: int
    invoice_number: str
    student_id: str
    academic_year: str
    age_on_31_aug: int | None
    residency_category: str | None
    age_band: str | None
    rule_id: int | None
    gross_fee: float
    remission_amount: float
    net_fee: float
    fee_id: int | None
    status: str
    issued_on: str
    due_date: str | None
    issued_by: str | None
    cancelled_reason: str | None
    notes: str | None
    fee_status: str | None = None


# ── DB plumbing ────────────────────────────────────────────────────

def _require_finance(action: str) -> None:
    """Fee rules, profiles, remissions and invoices are finance's: changing
    them needs the ``finance`` or ``funding`` capability."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    if not (p.can(access.FINANCE) or p.can(access.FUNDING)):
        p.require(access.FINANCE, action)


def _path() -> str:
    return str(DB_PATH or fees.DB_PATH)


def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(_path())
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_READY: set[str] = set()


def init_db() -> None:
    key = _path()
    if key in _READY:
        return
    if key == str(fees.DB_PATH):
        fees.init_db()          # students + fee_items (FK targets)
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY.add(key)


def _row_profile(r: db.Row) -> FeeProfile:
    return FeeProfile(student_id=r["student_id"],
                      residency_category=r["residency_category"],
                      continuing_learner=bool(r["continuing_learner"]),
                      has_ehcp=bool(r["has_ehcp"]), notes=r["notes"],
                      updated_by=r["updated_by"], updated_at=r["updated_at"])


def _row_rule(r: db.Row) -> FeeRule:
    return FeeRule(rule_id=r["rule_id"], academic_year=r["academic_year"],
                   residency_category=r["residency_category"],
                   age_band=r["age_band"], annual_fee=r["annual_fee"],
                   description=r["description"], priority=r["priority"],
                   active=bool(r["active"]), fee_status=r["fee_status"])


def _row_rem(r: db.Row) -> Remission:
    return Remission(remission_id=r["remission_id"],
                     student_id=r["student_id"],
                     academic_year=r["academic_year"],
                     remission_type=r["remission_type"], value=r["value"],
                     reason=r["reason"], approved_by=r["approved_by"],
                     approved_on=r["approved_on"], notes=r["notes"])


def _row_inv(r: db.Row) -> Invoice:
    return Invoice(**{k: r[k] for k in Invoice.__dataclass_fields__})


def _money(v: Any, label: str, *, allow_zero: bool = True) -> float:
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{label} must be a number") from None
    if d < 0 or (not allow_zero and d == 0):
        raise ValidationError(f"{label} must be more than zero"
                              if not allow_zero else
                              f"{label} cannot be negative")
    return float(d.quantize(Decimal("0.01")))


def _year(v: Any) -> str:
    try:
        return fc.normalise_year(v)
    except ValueError as exc:
        raise ValidationError(str(exc)) from None


def _student(sid: Any):
    s = (sid or "").strip() if isinstance(sid, str) else ""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(s) if s else None
    if student is None:
        raise ValidationError(f"No student with id {sid}")
    return student


# ── Profiles ──────────────────────────────────────────────────────

def set_profile(student_id: str, *, residency_category: str,
                continuing_learner: bool = False, has_ehcp: bool = False,
                notes: str | None = None, by: str | None = None) -> FeeProfile:
    """Record (or change) the fee facts for a learner."""
    _require_finance("set profile")
    init_db()
    student = _student(student_id)
    if residency_category not in RESIDENCY_CATEGORIES:
        raise ValidationError(
            "Residency must be one of: " + "; ".join(RESIDENCY_CATEGORIES))
    with _connect() as conn:
        conn.execute(
            """INSERT INTO fee_student_profiles
                   (student_id, residency_category, continuing_learner,
                    has_ehcp, notes, updated_by)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id) DO UPDATE SET
                   residency_category = excluded.residency_category,
                   continuing_learner = excluded.continuing_learner,
                   has_ehcp = excluded.has_ehcp, notes = excluded.notes,
                   updated_by = excluded.updated_by,
                   updated_at = datetime('now')""",
            (student.student_id, residency_category,
             1 if continuing_learner else 0, 1 if has_ehcp else 0,
             (notes or "").strip() or None, (by or "").strip() or None))
        conn.commit()
    out = get_profile(student.student_id)
    assert out is not None
    return out


def get_profile(student_id: str) -> FeeProfile | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM fee_student_profiles WHERE student_id = ?",
            ((student_id or "").strip(),)).fetchone()
    return _row_profile(r) if r else None


def list_profiles() -> list[FeeProfile]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM fee_student_profiles ORDER BY student_id").fetchall()
    return [_row_profile(r) for r in rows]


def age_band_for(age: int, profile: FeeProfile) -> str:
    """The funding age band for a learner of *age* on 31 August."""
    if age <= 18:
        return AGE_16_18
    if profile.has_ehcp and age <= 24:
        return AGE_19_24_EHCP
    if profile.continuing_learner:
        return AGE_19_CONTINUING
    return AGE_19_PLUS


# ── Rules ─────────────────────────────────────────────────────────

def create_rule(d: dict[str, Any]) -> FeeRule:
    _require_finance("create rule")
    init_db()
    p = _validate_rule(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO fee_rules (academic_year, residency_category,
                   age_band, fee_status, annual_fee, description, priority,
                   active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["academic_year"], p["residency_category"], p["age_band"],
             p["fee_status"], p["annual_fee"], p["description"],
             p["priority"], p["active"]))
        conn.commit()
        new_id = int(cur.lastrowid)
    out = get_rule(new_id)
    assert out is not None
    return out


def _validate_rule(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    year = d.get("academic_year")
    out["academic_year"] = _year(year) if year not in (None, "") else None
    res = (d.get("residency_category") or "").strip() or None
    if res and res not in RESIDENCY_CATEGORIES:
        raise ValidationError("Unknown residency category")
    out["residency_category"] = res
    band = (d.get("age_band") or "").strip()
    if band not in AGE_BANDS:
        raise ValidationError(f"Age band must be one of: {', '.join(AGE_BANDS)}")
    out["age_band"] = band
    status = (d.get("fee_status") or "").strip() or None
    if status and status not in FEE_STATUSES:
        raise ValidationError(
            f"Fee status must be blank (any) or one of: {', '.join(FEE_STATUSES)}")
    out["fee_status"] = status
    out["annual_fee"] = _money(d.get("annual_fee"), "Annual fee")
    out["description"] = (d.get("description") or "").strip() or None
    try:
        out["priority"] = int(d.get("priority") or 100)
    except (TypeError, ValueError):
        raise ValidationError("Priority must be a whole number") from None
    out["active"] = 1 if d.get("active", True) else 0
    return out


def get_rule(rule_id: int) -> FeeRule | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM fee_rules WHERE rule_id = ?",
                         (rule_id,)).fetchone()
    return _row_rule(r) if r else None


def list_rules(*, active_only: bool = False) -> list[FeeRule]:
    init_db()
    where = "WHERE active = 1" if active_only else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM fee_rules {where} ORDER BY "
            "COALESCE(academic_year, '') DESC, age_band, "
            "COALESCE(residency_category, ''), priority").fetchall()
    return [_row_rule(r) for r in rows]


def update_rule(rule_id: int, d: dict[str, Any]) -> FeeRule:
    _require_finance("update rule")
    existing = get_rule(rule_id)
    if existing is None:
        raise ValidationError(f"No fee rule #{rule_id}")
    p = _validate_rule({**vars(existing), **d})
    with _connect() as conn:
        conn.execute(
            """UPDATE fee_rules SET academic_year=?, residency_category=?,
                   age_band=?, fee_status=?, annual_fee=?, description=?,
                   priority=?, active=?, updated_at=datetime('now')
               WHERE rule_id=?""",
            (p["academic_year"], p["residency_category"], p["age_band"],
             p["fee_status"], p["annual_fee"], p["description"],
             p["priority"], p["active"], rule_id))
        conn.commit()
    out = get_rule(rule_id)
    assert out is not None
    return out


def deactivate_rule(rule_id: int) -> FeeRule:
    return update_rule(rule_id, {"active": False})


def match_rule(academic_year: str, residency: str, band: str,
               fee_status: str | None = None) -> FeeRule | None:
    """The most specific active rule for a (year, residency, band) and,
    when given, the learner's fee status.

    A rule naming a fee status beats one that does not, then a named
    year, then a named residency. Without a fee status only rules for any
    status match; a status in :data:`FEE_STATUSES_NEEDING_OWN_RULE` only
    matches rules that name it.
    """
    year = _year(academic_year)
    statuses: tuple[str | None, ...]
    if fee_status in FEE_STATUSES_NEEDING_OWN_RULE:
        statuses = (fee_status,)
    else:
        statuses = (None, fee_status) if fee_status else (None,)
    candidates = [r for r in list_rules(active_only=True)
                  if r.age_band == band
                  and r.fee_status in statuses
                  and r.academic_year in (None, year)
                  and r.residency_category in (None, residency)]
    if not candidates:
        return None
    candidates.sort(key=lambda r: (r.fee_status is None,
                                   r.academic_year is None,
                                   r.residency_category is None,
                                   r.priority, r.rule_id))
    return candidates[0]


# ── Remissions ────────────────────────────────────────────────────

def add_remission(d: dict[str, Any]) -> Remission:
    """Record a fee waiver / remission for a learner and year."""
    _require_finance("add remission")
    init_db()
    student = _student(d.get("student_id"))
    year = _year(d.get("academic_year"))
    rtype = (d.get("remission_type") or "").strip()
    if rtype not in REMISSION_TYPES:
        raise ValidationError(
            f"Remission type must be one of: {', '.join(REMISSION_TYPES)}")
    value = 0.0 if rtype == "Full" else _money(d.get("value"), "Value",
                                                allow_zero=False)
    if rtype == "Percentage" and value > 100:
        raise ValidationError("A percentage remission cannot exceed 100")
    reason = (d.get("reason") or "").strip()
    if reason not in REMISSION_REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(REMISSION_REASONS)}")
    approver = (d.get("approved_by") or "").strip()
    if not approver:
        raise ValidationError("A remission must name who approved it")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO fee_remissions (student_id, academic_year,
                   remission_type, value, reason, approved_by, approved_on,
                   notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (student.student_id, year, rtype, value, reason, approver,
             d.get("approved_on") or _dt.date.today().isoformat(),
             (d.get("notes") or "").strip() or None))
        conn.commit()
        new_id = int(cur.lastrowid)
    logger.info("Fee remission #%d for %s %s: %s %s", new_id,
                student.student_id, year, rtype, value)
    with _connect() as conn:
        r = conn.execute("SELECT * FROM fee_remissions WHERE remission_id=?",
                         (new_id,)).fetchone()
    return _row_rem(r)


def list_remissions(*, student_id: str | None = None,
                    academic_year: str | None = None) -> list[Remission]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(_year(academic_year))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM fee_remissions {where} "
            "ORDER BY academic_year DESC, student_id", args).fetchall()
    return [_row_rem(r) for r in rows]


def remove_remission(remission_id: int) -> bool:
    """Remove a remission not yet reflected on an issued invoice."""
    _require_finance("remove remission")
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM fee_remissions WHERE remission_id=?",
                         (remission_id,)).fetchone()
        if r is None:
            return False
        if conn.execute(
                "SELECT 1 FROM fee_invoices WHERE student_id=? AND "
                "academic_year=? AND status='Issued'",
                (r["student_id"], r["academic_year"])).fetchone():
            raise ValidationError(
                "An invoice has been issued using this remission — cancel "
                "the invoice first")
        cur = conn.execute("DELETE FROM fee_remissions WHERE remission_id=?",
                           (remission_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Calculation ───────────────────────────────────────────────────

def calculate_fee(student_id: str, academic_year: str | None = None, *,
                  fee_status: str | None = None) -> FeeCalculation:
    """Work out a learner's tuition fee for an academic year.

    Age is taken on 31 August at the start of the year; the band, the
    residency category and (when given — the enrolment's ILR fee status)
    the fee status select a rule; remissions come off the gross.
    """
    init_db()
    if fee_status is not None and fee_status not in FEE_STATUSES:
        raise ValidationError(
            f"{fee_status!r} carries no tuition fee — fee rules price only "
            f"{', '.join(FEE_STATUSES)}")
    student = _student(student_id)
    year = _year(academic_year)
    if not student.date_of_birth:
        raise ValidationError(
            f"{student.student_id} has no date of birth on record — "
            "the fee depends on age on 31 August")
    profile = get_profile(student.student_id)
    if profile is None:
        raise ValidationError(
            f"Record {student.student_id}'s residency category first")
    try:
        age = fc.age_on_31_august(student.date_of_birth, year)
    except ValueError:
        raise ValidationError(
            f"Date of birth {student.date_of_birth!r} is not a valid date"
        ) from None
    band = age_band_for(age, profile)
    rule = match_rule(year, profile.residency_category, band, fee_status)
    if rule is None:
        if fee_status in FEE_STATUSES_NEEDING_OWN_RULE:
            raise ValidationError(
                f"No fee rule for {fee_status} learners covers {band} / "
                f"{profile.residency_category} in {year} — a {fee_status} "
                "learner pays a share of the fee, so add a rule with that "
                "fee status under Fee Rules")
        raise ValidationError(
            f"No fee rule covers {band} / {profile.residency_category}"
            + (f" / {fee_status}" if fee_status else "")
            + f" in {year} — add one under Fee Rules")
    gross = rule.annual_fee
    explanation = [
        f"Age on 31 August {year[:4]}: {age} -> band '{band}'",
        f"Residency: {profile.residency_category}",
        *([f"Fee status: {fee_status}"] if fee_status else []),
        f"Rule #{rule.rule_id}"
        + (f" ({rule.description})" if rule.description else "")
        + f": {CURRENCY_SYMBOL}{gross:,.2f}",
    ]
    rems = list_remissions(student_id=student.student_id, academic_year=year)
    off = 0.0
    for rem in rems:
        if rem.remission_type == "Full":
            amt = gross
        elif rem.remission_type == "Percentage":
            amt = round(gross * rem.value / 100.0, 2)
        else:
            amt = rem.value
        explanation.append(
            f"Remission #{rem.remission_id} ({rem.remission_type}"
            f"{'' if rem.remission_type == 'Full' else ' ' + str(rem.value)}"
            f", {rem.reason}): -{CURRENCY_SYMBOL}{amt:,.2f}")
        off += amt
    off = round(min(off, gross), 2)
    net = round(gross - off, 2)
    explanation.append(f"Net fee: {CURRENCY_SYMBOL}{net:,.2f}")
    return FeeCalculation(
        student_id=student.student_id, student_name=student.full_name,
        academic_year=year, date_of_birth=student.date_of_birth,
        age_on_31_aug=age, age_band=band,
        residency_category=profile.residency_category, rule=rule,
        gross_fee=round(gross, 2), remissions=rems, remission_amount=off,
        net_fee=net, explanation=explanation, fee_status=fee_status)


# ── Invoices ──────────────────────────────────────────────────────

def _next_invoice_number(conn: db.Connection, year: int) -> str:
    rows = conn.execute(
        "SELECT invoice_number FROM fee_invoices WHERE invoice_number LIKE ?",
        (f"INV-{year}-%",)).fetchall()
    seq = 0
    for r in rows:
        m = _INVOICE_RE.match(r["invoice_number"])
        if m:
            seq = max(seq, int(m.group(2)))
    return f"INV-{year}-{seq + 1:05d}"


def generate_invoice(student_id: str, academic_year: str | None = None, *,
                     issued_by: str, due_date: str | None = None,
                     fee_status: str | None = None) -> Invoice:
    """Raise the tuition invoice for a learner and year.

    Creates a Tuition fee item for the net fee (so it appears on the
    learner's statement and takes payments and receipts like any fee)
    and the numbered invoice that explains it. One live invoice per
    learner per year; cancel it to re-raise. *fee_status* (the
    enrolment's ILR fee status) is passed to :func:`calculate_fee` and
    recorded on the invoice.
    """
    _require_finance("generate invoice")
    if not (issued_by or "").strip():
        raise ValidationError("An invoice must name who issued it")
    calc = calculate_fee(student_id, academic_year, fee_status=fee_status)
    if calc.net_fee <= 0:
        raise ValidationError(
            f"No fee payable for {calc.student_id} in {calc.academic_year} "
            f"({calc.age_band}, {calc.residency_category})")
    today = _dt.date.today().isoformat()
    due = due_date or fc.add_months(today, 1)
    with _connect() as conn:
        live = conn.execute(
            "SELECT invoice_number FROM fee_invoices WHERE student_id=? "
            "AND academic_year=? AND status='Issued'",
            (calc.student_id, calc.academic_year)).fetchone()
        if live:
            raise ValidationError(
                f"{calc.student_id} already has invoice "
                f"{live['invoice_number']} for {calc.academic_year}")
        number = _next_invoice_number(conn, _dt.date.today().year)
    item = fees.create_item({
        "student_id": calc.student_id,
        "description": f"Tuition fee {calc.academic_year} ({number})"
                       + (f" — {calc.fee_status}" if calc.fee_status else ""),
        "category": "Tuition", "amount": calc.net_fee,
        "issued_date": today, "due_date": due,
        "academic_year": calc.academic_year,
        "notes": "; ".join(calc.explanation),
    })
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO fee_invoices (invoice_number, student_id,
                   academic_year, age_on_31_aug, residency_category,
                   age_band, fee_status, rule_id, gross_fee, remission_amount,
                   net_fee, fee_id, status, issued_on, due_date, issued_by,
                   notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Issued', ?, ?, ?,
                       ?)""",
            (number, calc.student_id, calc.academic_year, calc.age_on_31_aug,
             calc.residency_category, calc.age_band, calc.fee_status,
             calc.rule.rule_id,
             calc.gross_fee, calc.remission_amount, calc.net_fee, item.fee_id,
             today, due, issued_by.strip(), "\n".join(calc.explanation)))
        conn.commit()
        new_id = int(cur.lastrowid)
    logger.info("Invoice %s raised for %s: %s%.2f", number, calc.student_id,
                CURRENCY_SYMBOL, calc.net_fee)
    out = get_invoice(new_id)
    assert out is not None
    return out


def generate_invoices(academic_year: str | None = None, *, issued_by: str,
                      due_date: str | None = None) -> dict[str, list[str]]:
    """Raise invoices for every profiled learner who owes a fee.

    Returns ``{"raised": [...], "no_fee": [...], "skipped": [...]}`` —
    skipped entries carry the reason (no DOB, no rule, already invoiced).
    """
    _require_finance("generate invoices")
    out: dict[str, list[str]] = {"raised": [], "no_fee": [], "skipped": []}
    for profile in list_profiles():
        try:
            inv = generate_invoice(profile.student_id, academic_year,
                                   issued_by=issued_by, due_date=due_date)
            out["raised"].append(f"{profile.student_id}: "
                                 f"{inv.invoice_number}")
        except ValidationError as exc:
            msg = str(exc)
            if msg.startswith("No fee payable"):
                out["no_fee"].append(profile.student_id)
            else:
                out["skipped"].append(f"{profile.student_id}: {msg}")
    return out


def get_invoice(invoice_id: int) -> Invoice | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM fee_invoices WHERE invoice_id = ?",
                         (invoice_id,)).fetchone()
    return _row_inv(r) if r else None


def list_invoices(*, student_id: str | None = None,
                  academic_year: str | None = None,
                  status: str | None = None) -> list[Invoice]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(_year(academic_year))
    if status:
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM fee_invoices {where} "
            "ORDER BY issued_on DESC, invoice_id DESC", args).fetchall()
    return [_row_inv(r) for r in rows]


def invoice_balance(invoice: Invoice) -> tuple[float, float, str]:
    """(paid, balance, status) from the invoice's fee item."""
    if invoice.status == "Cancelled" or not invoice.fee_id:
        return 0.0, 0.0, invoice.status
    view = fees.view_item(invoice.fee_id)
    if view is None:
        return 0.0, invoice.net_fee, "Outstanding"
    return view.paid, view.balance, view.effective_status


def pay_invoice(invoice_id: int, *, amount: float, method: str,
                recorded_by: str, reference: str | None = None,
                receipt: bool = True) -> tuple[Any, Any]:
    """Take a payment against an invoice and (by default) issue the
    receipt. Returns (fee payment, receipt or None)."""
    _require_finance("pay invoice")
    inv = get_invoice(invoice_id)
    if inv is None:
        raise ValidationError(f"No invoice #{invoice_id}")
    if inv.status != "Issued" or not inv.fee_id:
        raise ValidationError(f"Invoice {inv.invoice_number} is "
                              f"{inv.status.lower()}")
    payment = fees.create_payment(inv.fee_id, {
        "amount": amount, "method": method, "status": "Cleared",
        "recorded_by": recorded_by, "reference": reference or
        inv.invoice_number})
    rec = None
    if receipt:
        from education_system.systems.sixth_form.domains.finance.domain.receipts import (
            receipts as _receipts,
        )
        try:
            rec = _receipts.receipt_from_fee_payment(
                payment.payment_id, received_by=recorded_by)
        except _receipts.ValidationError as exc:
            raise ValidationError(
                f"Payment recorded (#{payment.payment_id}) but the receipt "
                f"failed: {exc}") from None
    return payment, rec


def cancel_invoice(invoice_id: int, *, reason: str, by: str) -> Invoice:
    """Cancel an invoice with nothing paid on it (its fee item too)."""
    _require_finance("cancel invoice")
    inv = get_invoice(invoice_id)
    if inv is None:
        raise ValidationError(f"No invoice #{invoice_id}")
    if inv.status == "Cancelled":
        raise ValidationError("That invoice is already cancelled")
    if not (reason or "").strip() or not (by or "").strip():
        raise ValidationError("Cancelling an invoice needs a reason and a name")
    paid, _bal, _st = invoice_balance(inv)
    if paid > 0:
        raise ValidationError(
            f"{CURRENCY_SYMBOL}{paid:.2f} has been paid on this invoice — "
            "refund it on the fee item first")
    if inv.fee_id:
        fees.set_stored_status(inv.fee_id, "Cancelled")
    with _connect() as conn:
        conn.execute(
            "UPDATE fee_invoices SET status='Cancelled', cancelled_reason=? "
            "WHERE invoice_id=?",
            (f"{reason.strip()} (by {by.strip()})", invoice_id))
        conn.commit()
    out = get_invoice(invoice_id)
    assert out is not None
    return out


@dataclass
class Summary:
    profiles: int
    rules: int
    invoices_issued: int
    invoiced_total: float
    paid_total: float
    outstanding_total: float
    remitted_total: float


def summary(academic_year: str | None = None) -> Summary:
    init_db()
    invs = list_invoices(academic_year=academic_year, status="Issued")
    paid = outstanding = 0.0
    for inv in invs:
        p, b, _s = invoice_balance(inv)
        paid += p
        outstanding += max(0.0, b)
    return Summary(
        profiles=len(list_profiles()), rules=len(list_rules(active_only=True)),
        invoices_issued=len(invs),
        invoiced_total=round(sum(i.net_fee for i in invs), 2),
        paid_total=round(paid, 2), outstanding_total=round(outstanding, 2),
        remitted_total=round(sum(i.remission_amount for i in invs), 2))
