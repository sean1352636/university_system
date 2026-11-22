"""Expense claims: staff (and others) claim back what they spent.

Kept from the old Expense Claims:

* A claim header (reference, claimant type and id, claimant name,
  department, title, description, purpose, category, incurred from / to,
  payment method, payment reference, receipts attached, notes) and its lines
  (incurred on, category, description, supplier, receipt ref, quantity, unit
  amount, mileage miles and rate, VAT, net, gross, notes).
* The statuses Draft, Submitted, Under Review, Approved, Rejected, Paid and
  Cancelled; the old Submit, Begin review, Approve, Reject, Pay, Cancel and
  Change status; the Open / Awaiting payment / Paid / All lists, the filter
  (claimant, category, status, title) and the summary (counts, values, by
  category / claimant type / status / payment method).

New:

* **Money in pence.** Every amount is whole pence. Mileage lines are miles x
  the mileage rate, a setting the expense approvers set (HMRC's 45p a mile by
  default), frozen on the line when it is entered; mileage has no VAT.
* **Budget code.** Each claim is charged to a budget line (a cost centre's
  code) from :mod:`.budgets`; required to submit. When a claim is approved
  its total is posted as spend against that line; cancelling an approved
  claim reverses the posting.
* **Separation of duties.** The holder of the claim's cost centre or an
  expense approver (:data:`EXPENSE_APPROVERS`) reviews, approves or rejects
  (rejecting needs a reason) - never the claimant. Paying is for expense
  approvers, again never their own claim.
* **Limits and receipts.** A limit per category per claim (setting); a
  receipt reference or file is needed for every non-mileage line over the
  receipt threshold (setting, £0 = every line).
* **My claims.** Every member of staff can create, edit, submit, cancel and
  reopen (after a rejection) their own claims, even though the "Expense
  Claims" menu entry is for the finance office: see :func:`my_claims`,
  :func:`create_claim` and :func:`approval_queue`.
* **Payment runs.** :func:`payment_run` takes the approved claims, writes the
  CSV for the bank / payroll and marks them paid with the run's reference.
* **Notices.** :func:`notify_claimant` e-mails a staff claimant when their
  claim is approved, rejected or paid.
* Every change is in ``expense_audit`` and the activity log (claim ids,
  never amounts with names).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.finance.domain import budgets as B  # registers the FK target
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    EXPENSE_APPROVERS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound
money = B.money
pounds = B.pounds

CLAIMANT_TYPES: tuple[str, ...] = (
    "Staff", "Student", "Governor", "Contractor", "Volunteer", "Other")
DEFAULT_CLAIMANT_TYPE = "Staff"
MILEAGE = "Mileage"
#: The old categories, with Resources and Training added ("Trip / Visit" is
#: trip costs, "Conference / CPD" conference fees).
CATEGORIES: tuple[str, ...] = (
    "Travel", MILEAGE, "Subsistence", "Accommodation", "Conference / CPD", "Training",
    "Resources", "Books / Materials", "Equipment", "Software", "Stationery", "Postage",
    "Hospitality", "Trip / Visit", "Uniform", "PPE", "Other")
DEFAULT_CATEGORY = "Travel"
PAYMENT_METHODS: tuple[str, ...] = (
    "BACS", "Cheque", "Cash", "Payroll", "Petty Cash", "Card", "Other")
DEFAULT_PAYMENT_METHOD = "BACS"
CLAIM_STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Under Review", "Approved", "Rejected", "Paid", "Cancelled")
DEFAULT_CLAIM_STATUS = "Draft"
OPEN = ("Draft", "Submitted", "Under Review")
WAITING = ("Submitted", "Under Review")
SCOPES = ("open", "awaiting", "paid", "all")

#: HMRC approved mileage allowance (cars, first 10,000 miles).
HMRC_MILEAGE_PENCE = 45
DEFAULTS = {"mileage_rate_pence": HMRC_MILEAGE_PENCE, "receipt_over_pence": 0}
_LIMITS = {"mileage_rate_pence": (1, 500, "Mileage rate (pence a mile)"),
           "receipt_over_pence": (0, 10_000_000, "Receipts needed over (pence)")}
MAX_MILES = 5000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS expense_settings (
    key    TEXT PRIMARY KEY,
    value  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS expense_limits (
    category     TEXT PRIMARY KEY,
    limit_pence  INTEGER NOT NULL CHECK (limit_pence > 0)
);
CREATE TABLE IF NOT EXISTS expense_payment_runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    reference    TEXT NOT NULL UNIQUE,
    run_date     TEXT NOT NULL,
    claims       INTEGER NOT NULL DEFAULT 0,
    total_pence  INTEGER NOT NULL DEFAULT 0,
    file_name    TEXT,
    created_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS expense_claims (
    claim_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_ref          TEXT NOT NULL UNIQUE,
    claimant_type      TEXT NOT NULL DEFAULT 'Staff',
    claimant_id        TEXT NOT NULL,
    claimant_name      TEXT,
    department         TEXT,
    title              TEXT NOT NULL,
    description        TEXT,
    purpose            TEXT,
    category           TEXT NOT NULL DEFAULT 'Travel',
    incurred_from      TEXT,
    incurred_to        TEXT,
    budget_line_id     INTEGER REFERENCES budget_lines (line_id),
    submitted_on       TEXT,
    reviewed_by        TEXT,
    approved_on        TEXT,
    approved_by        TEXT,
    rejected_on        TEXT,
    rejected_by        TEXT,
    rejection_reason   TEXT,
    paid_on            TEXT,
    paid_by            TEXT,
    payment_method     TEXT NOT NULL DEFAULT 'BACS',
    payment_reference  TEXT,
    payment_run_id     INTEGER REFERENCES expense_payment_runs (run_id),
    cancelled_on       TEXT,
    status             TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft', 'Submitted',
                       'Under Review', 'Approved', 'Rejected', 'Paid', 'Cancelled')),
    receipts_attached  INTEGER NOT NULL DEFAULT 0,
    notes              TEXT,
    created_by         TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by         TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_expense_claims_claimant ON expense_claims (claimant_type,
                                                                         claimant_id);
CREATE INDEX IF NOT EXISTS ix_expense_claims_status ON expense_claims (status);
CREATE TABLE IF NOT EXISTS expense_claim_lines (
    line_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id            INTEGER NOT NULL REFERENCES expense_claims (claim_id) ON DELETE CASCADE,
    incurred_on         TEXT NOT NULL,
    category            TEXT NOT NULL,
    description         TEXT,
    supplier            TEXT,
    receipt_ref         TEXT,
    receipt_path        TEXT,
    quantity            INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
    unit_pence          INTEGER NOT NULL DEFAULT 0 CHECK (unit_pence >= 0),
    mileage_miles       REAL,
    mileage_rate_pence  INTEGER,
    vat_pence           INTEGER NOT NULL DEFAULT 0 CHECK (vat_pence >= 0),
    net_pence           INTEGER NOT NULL DEFAULT 0,
    gross_pence         INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_expense_claim_lines_claim ON expense_claim_lines (claim_id);
CREATE TABLE IF NOT EXISTS expense_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id  INTEGER,
    action    TEXT NOT NULL,
    detail    TEXT,
    actor     TEXT NOT NULL,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("expense_claims", _SCHEMA)


@dataclass(frozen=True)
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
    budget_line_id: int | None
    submitted_on: str | None
    reviewed_by: str | None
    approved_on: str | None
    approved_by: str | None
    rejected_on: str | None
    rejected_by: str | None
    rejection_reason: str | None
    paid_on: str | None
    paid_by: str | None
    payment_method: str
    payment_reference: str | None
    payment_run_id: int | None
    cancelled_on: str | None
    status: str
    receipts_attached: int
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    line_count: int = 0
    total_pence: int = 0
    budget_code: str | None = None
    centre_id: int | None = None
    centre_name: str | None = None
    centre_holder: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status in OPEN

    @property
    def is_settled(self) -> bool:
        return self.status in ("Paid", "Rejected", "Cancelled")

    @property
    def total(self) -> str:
        return money(self.total_pence)


@dataclass(frozen=True)
class ClaimLine:
    line_id: int
    claim_id: int
    incurred_on: str
    category: str
    description: str | None
    supplier: str | None
    receipt_ref: str | None
    receipt_path: str | None
    quantity: int
    unit_pence: int
    mileage_miles: float | None
    mileage_rate_pence: int | None
    vat_pence: int
    net_pence: int
    gross_pence: int
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def has_receipt(self) -> bool:
        return bool(self.receipt_ref or self.receipt_path)


@dataclass(frozen=True)
class PaymentRun:
    run_id: int
    reference: str
    run_date: str
    claims: int
    total_pence: int
    file_name: str | None
    created_by: str | None
    created_at: str


@dataclass
class ExpenseClaimsSummary:
    """The old summary, in pence."""
    total_claims: int = 0
    drafts: int = 0
    submitted: int = 0
    under_review: int = 0
    approved: int = 0
    paid: int = 0
    rejected: int = 0
    cancelled: int = 0
    total_value: int = 0
    awaiting_payment_value: int = 0
    paid_value: int = 0
    distinct_claimants: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_claimant_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_payment_method: dict[str, int] = field(default_factory=dict)


_SELECT = """
SELECT e.*,
       (SELECT COUNT(*) FROM expense_claim_lines x WHERE x.claim_id = e.claim_id) AS line_count,
       (SELECT COALESCE(SUM(gross_pence), 0) FROM expense_claim_lines x
        WHERE x.claim_id = e.claim_id) AS total_pence,
       bl.code AS budget_code, bc.centre_id, bc.name AS centre_name, bc.holder AS centre_holder
FROM expense_claims e
LEFT JOIN budget_lines bl ON bl.line_id = e.budget_line_id
LEFT JOIN budget_cost_centres bc ON bc.centre_id = bl.centre_id
"""


def _row(r) -> Claim:
    return Claim(**{k: r[k] for k in Claim.__dataclass_fields__})


def _line_row(r) -> ClaimLine:
    return ClaimLine(**{k: r[k] for k in ClaimLine.__dataclass_fields__})


# ── Who may do what ──────────────────────────────────────────────────

def _me(actor: Principal) -> str:
    return (actor.username or "").lower()


def is_approver(actor: Principal) -> bool:
    return actor.role in EXPENSE_APPROVERS


def is_claimant(actor: Principal, c: Claim) -> bool:
    return bool(_me(actor)) and c.claimant_type == "Staff" and c.claimant_id.lower() == _me(actor)


def is_owner(actor: Principal, c: Claim) -> bool:
    """The claimant, or whoever entered the claim."""
    return is_claimant(actor, c) or bool(_me(actor) and (c.created_by or "").lower() == _me(actor))


def is_centre_holder(actor: Principal, c: Claim) -> bool:
    return bool(_me(actor) and (c.centre_holder or "").lower() == _me(actor))


def can_see(actor: Principal, c: Claim) -> bool:
    return actor.role in STAFF_ROLES and (is_approver(actor) or is_owner(actor, c)
                                          or is_centre_holder(actor, c))


def can_decide(actor: Principal, c: Claim) -> bool:
    """Review / approve / reject: the cost centre holder or an approver,
    never the claimant."""
    return (actor.role in STAFF_ROLES and not is_claimant(actor, c)
            and (is_approver(actor) or is_centre_holder(actor, c)))


def allowed_actions(actor: Principal, c: Claim) -> set[str]:
    """What *actor* can do to *c* now (screens disable everything else)."""
    out: set[str] = set()
    if not can_see(actor, c):
        return out
    owner, approver = is_owner(actor, c), is_approver(actor)
    out.update({"view", "history"})
    if c.status == "Draft" and (owner or approver):
        out.update({"edit", "lines", "submit", "delete", "cancel"})
    if c.status in WAITING and (owner or approver):
        out.add("cancel")
    if c.status in WAITING and can_decide(actor, c):
        out.update({"approve", "reject"})
        if c.status == "Submitted":
            out.add("review")
    if c.status == "Approved" and approver and not is_claimant(actor, c):
        out.update({"pay", "cancel"})
    if c.status == "Rejected" and (owner or approver):
        out.update({"reopen", "cancel"})
    if c.status == "Cancelled" and (owner or approver):
        out.add("delete")
    if approver:
        out.add("status")
        if c.claimant_type == "Staff" and c.status in ("Approved", "Rejected", "Paid"):
            out.add("notify")
    return out


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"expenses.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, None, "Only staff can make or see expense claims.")


def _require_approver(actor: Principal, action: str, target: Any = None) -> None:
    if not is_approver(actor):
        _deny(actor, action, target, "Only the finance office (expense approvers) can do that.")


def _require(actor: Principal, c: Claim, action: str, message: str) -> None:
    if action not in allowed_actions(actor, c):
        if not can_see(actor, c):
            _deny(actor, action, c.claim_id, "That claim isn't yours to see.")
        if is_claimant(actor, c) and action in ("approve", "reject", "review", "pay"):
            _deny(actor, action, c.claim_id, "You can't approve or pay your own claim - "
                                             "someone else must.")
        raise ValidationError([message])


def _audit(conn, action: str, actor: Principal, claim_id: int | None, **detail: Any) -> None:
    conn.execute("INSERT INTO expense_audit (claim_id, action, detail, actor) VALUES (?, ?, ?, ?)",
                 (claim_id, action, json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(claim_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM expense_audit", []
    if claim_id is not None:
        sql += " WHERE claim_id = ?"
        params.append(int(claim_id))
    with database.connect() as conn:
        return [{"at": r["at"], "claim_id": r["claim_id"], "action": r["action"],
                 "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Settings and limits ──────────────────────────────────────────────

def settings() -> dict[str, int]:
    with database.connect() as conn:
        saved = dict(conn.execute("SELECT key, value FROM expense_settings").fetchall())
    return {k: int(saved.get(k, v)) for k, v in DEFAULTS.items()}


def mileage_rate() -> int:
    """Pence a mile for new mileage lines."""
    return settings()["mileage_rate_pence"]


def set_settings(changes: dict[str, Any], *, actor: Principal) -> dict[str, int]:
    """Mileage rate (pence a mile) and the receipt threshold (pounds text or
    pence) - expense approvers only."""
    _require_approver(actor, "settings")
    problems: list[str] = []
    clean: dict[str, int] = {}
    for k, v in changes.items():
        if k not in DEFAULTS:
            problems.append(f"Unknown setting {k}")
            continue
        lo, hi, label = _LIMITS[k]
        if k == "receipt_over_pence":
            n = B.to_pence(v if v not in (None, "") else 0, "Receipts needed over", problems)
        else:
            try:
                n = int(str(v).strip())
            except (TypeError, ValueError):
                n = None
        if n is None or not lo <= n <= hi:
            if not problems or not problems[-1].startswith("Receipts"):
                problems.append(f"{label} must be from {lo} to {hi}")
            continue
        clean[k] = n
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.executemany("INSERT INTO expense_settings (key, value) VALUES (?, ?) ON CONFLICT "
                         "(key) DO UPDATE SET value = excluded.value", list(clean.items()))
        _audit(conn, "settings", actor, None, **clean)
    activity_log.record("expenses.settings", principal=actor, fields=",".join(clean))
    return settings()


def limits() -> dict[str, int]:
    """{category: limit in pence per claim} (categories with no limit left out)."""
    with database.connect() as conn:
        return dict(conn.execute("SELECT category, limit_pence FROM expense_limits").fetchall())


def set_limit(category: str, amount: Any, *, actor: Principal) -> dict[str, int]:
    """Set a category's limit per claim; blank or 0 removes it."""
    _require_approver(actor, "limit")
    problems: list[str] = []
    cat = _choice(category, CATEGORIES, "Category", problems, None)
    if not cat:
        problems.append("Choose a category")
    n = B.to_pence(amount if amount not in (None, "") else 0, "Limit", problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        if not n:
            conn.execute("DELETE FROM expense_limits WHERE category = ?", (cat,))
        else:
            conn.execute("INSERT INTO expense_limits (category, limit_pence) VALUES (?, ?) ON "
                         "CONFLICT (category) DO UPDATE SET limit_pence = excluded.limit_pence",
                         (cat, n))
        _audit(conn, "limit", actor, None, category=cat, limit=n)
    activity_log.record("expenses.limit", principal=actor, category=cat)
    return limits()


# ── Cleaning ─────────────────────────────────────────────────────────

_date = B._date
_text = B._text


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str | None) -> str | None:
    return B._choice(value, options, label, problems, default)


def _budget_line(data: dict[str, Any], problems: list[str]) -> tuple[bool, int | None]:
    """(given?, line id) from ``budget_line_id`` or ``budget_code`` (a code,
    or a "CODE - ..." label from a drop-down)."""
    if "budget_line_id" in data:
        raw = data["budget_line_id"]
    elif "budget_code" in data:
        raw = data["budget_code"]
    else:
        return False, None
    if raw in (None, "") or (isinstance(raw, str) and not raw.strip()):
        return True, None
    if isinstance(raw, int) or str(raw).strip().isdigit():
        try:
            ln = B.get_line(int(raw))
        except NotFound:
            problems.append(f"No budget line #{raw}")
            return True, None
    else:
        code = str(raw).strip().split(" - ", 1)[0]
        year = None
        if str(raw).rstrip().endswith(")") and "(" in str(raw):
            year = str(raw).rstrip()[:-1].rsplit("(", 1)[1]
        ln = B.find_line(code, year) if year else next(
            (B.get_line(x["line_id"]) for x in B.codes_for_claims()
             if x["code"].lower() == code.lower()), None)
        if ln is None:
            problems.append(f"No budget code {code} in an open financial year")
            return True, None
    if ln.line_id not in {x["line_id"] for x in B.codes_for_claims()}:
        problems.append(f"Budget code {ln.code} isn't open for claims (closed year or "
                        "inactive cost centre)")
    return True, ln.line_id


_HEADER = ("claim_ref", "claimant_type", "claimant_id", "claimant_name", "department", "title",
           "description", "purpose", "category", "incurred_from", "incurred_to",
           "payment_method", "receipts_attached", "notes")


def _clean(data: dict[str, Any], cur: Claim | None) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(cur, k) for k in _HEADER} if cur else {}
    merged.update({k: v for k, v in data.items() if k in _HEADER})
    out: dict[str, Any] = {}
    out["claim_ref"] = _text(merged.get("claim_ref"), 30)
    out["claimant_type"] = _choice(merged.get("claimant_type"), CLAIMANT_TYPES, "Claimant type",
                                   problems, DEFAULT_CLAIMANT_TYPE)
    out["claimant_id"] = _text(merged.get("claimant_id"), 60)
    out["claimant_name"] = _text(merged.get("claimant_name"), 120)
    out["department"] = _text(merged.get("department"), 80)
    out["title"] = _text(merged.get("title"), 120)
    if not out["title"]:
        problems.append("Title is required")
    out["description"] = _text(merged.get("description"), 2000)
    out["purpose"] = _text(merged.get("purpose"), 500)
    out["category"] = _choice(merged.get("category"), CATEGORIES, "Category", problems,
                              DEFAULT_CATEGORY)
    out["payment_method"] = _choice(merged.get("payment_method"), PAYMENT_METHODS,
                                    "Payment method", problems, DEFAULT_PAYMENT_METHOD)
    for k, label in (("incurred_from", "Incurred from"), ("incurred_to", "Incurred to")):
        out[k] = _date(merged.get(k), label, problems)
    if out["incurred_from"] and out["incurred_to"] and out["incurred_to"] < out["incurred_from"]:
        problems.append("Incurred to cannot be before incurred from")
    if out["incurred_from"] and out["incurred_from"] > _today().isoformat():
        problems.append("Incurred from can't be in the future")
    ra = merged.get("receipts_attached")
    out["receipts_attached"] = 1 if str(ra).strip().lower() in ("1", "true", "yes", "y") else 0
    out["notes"] = _text(merged.get("notes"), 2000)
    return out, problems


# ── Reading ──────────────────────────────────────────────────────────

def _get(claim_id: int) -> Claim:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE e.claim_id = ?", (int(claim_id),)).fetchone()
    if r is None:
        raise NotFound(f"No claim #{claim_id}")
    return _row(r)


def get_claim(claim_id: int, *, actor: Principal | None = None) -> Claim:
    """A claim (with *actor*: only one they may see)."""
    c = _get(claim_id)
    if actor is not None and not can_see(actor, c):
        _deny(actor, "view", c.claim_id, "That claim isn't yours to see.")
    return c


def get_claim_by_ref(claim_ref: str) -> Claim | None:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE lower(e.claim_ref) = lower(?)",
                         (str(claim_ref).strip(),)).fetchone()
    return _row(r) if r else None


def list_claims(*, scope: str | None = None, claimant_type: str | None = None,
                claimant_id: str | None = None, category: str | None = None,
                status: str | None = None, title: str | None = None,
                centre_id: int | None = None, date_from: str | None = None,
                date_to: str | None = None, actor: Principal | None = None,
                limit: int = 5000) -> list[Claim]:
    """Claims, newest first. *scope* is the old tab: open, awaiting (approved,
    not paid), paid or all. With *actor*, only the claims they may see."""
    where, params = [], []
    statuses = {"open": OPEN, "awaiting": ("Approved",), "paid": ("Paid",)}.get(scope or "")
    if statuses:
        where.append(f"e.status IN ({', '.join('?' * len(statuses))})")
        params += list(statuses)
    for col, val in (("e.claimant_type", claimant_type), ("e.category", category),
                     ("e.status", status), ("bc.centre_id", centre_id)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if claimant_id:
        where.append("lower(e.claimant_id) = lower(?)")
        params.append(str(claimant_id).strip())
    if title:
        where.append("lower(e.title) LIKE ? ESCAPE '\\'")
        esc = str(title).strip().lower().replace("\\", "\\\\").replace("%", "\\%") \
            .replace("_", "\\_")
        params.append(f"%{esc}%")
    if date_from:
        where.append("COALESCE(e.submitted_on, substr(e.created_at, 1, 10)) >= ?")
        params.append(date_from)
    if date_to:
        where.append("COALESCE(e.submitted_on, substr(e.created_at, 1, 10)) <= ?")
        params.append(date_to)
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY e.claim_id DESC LIMIT ?"
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(sql, (*params, int(limit)))]
    if actor is not None:
        _require_staff(actor, "list")
        rows = [c for c in rows if can_see(actor, c)]
    return rows


def my_claims(actor: Principal, *, status: str | None = None) -> list[Claim]:
    """The claims *actor* made (or entered) - every member of staff."""
    _require_staff(actor, "mine")
    return [c for c in list_claims(status=status) if is_owner(actor, c)]


def approval_queue(actor: Principal) -> list[Claim]:
    """Submitted / under review claims *actor* may decide (their cost
    centres', or all for an approver), oldest first; never their own."""
    _require_staff(actor, "queue")
    rows = [c for c in list_claims(scope="open") if c.status in WAITING and can_decide(actor, c)]
    return sorted(rows, key=lambda c: (c.submitted_on or "", c.claim_id))


def awaiting_my_approval(actor: Principal) -> int:
    """How many claims wait for *actor* (for My Day)."""
    if actor.role not in STAFF_ROLES:
        return 0
    return len(approval_queue(actor))


def lines_for_claim(claim_id: int) -> list[ClaimLine]:
    with database.connect() as conn:
        return [_line_row(r) for r in conn.execute(
            "SELECT * FROM expense_claim_lines WHERE claim_id = ? ORDER BY incurred_on, line_id",
            (int(claim_id),))]


def get_line(line_id: int) -> ClaimLine:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM expense_claim_lines WHERE line_id = ?",
                         (int(line_id),)).fetchone()
    if r is None:
        raise NotFound(f"No claim line #{line_id}")
    return _line_row(r)


# ── Writing claims ───────────────────────────────────────────────────

def _staff(username: str) -> dict | None:
    return next((s for s in accounts.staff_logins()
                 if s["username"].lower() == username.lower()), None)


def create_claim(data: dict[str, Any], *, actor: Principal) -> Claim:
    """A new draft claim. Staff claim for themselves; an expense approver may
    enter a claim for someone else (any claimant type)."""
    _require_staff(actor, "create")
    c, problems = _clean(data, None)
    if is_approver(actor) and not c["claimant_id"] and c["claimant_type"] != "Staff":
        problems.append("Claimant id is required")
    elif not is_approver(actor) or not c["claimant_id"]:
        if not is_approver(actor) and (c["claimant_type"] != "Staff" or (
                c["claimant_id"] and c["claimant_id"].lower() != _me(actor))):
            _deny(actor, "create", None, "You can only make a claim for yourself.")
        c["claimant_type"], c["claimant_id"] = "Staff", actor.username
    if c["claimant_type"] == "Staff":
        s = _staff(c["claimant_id"] or "")
        if s is None:
            problems.append(f"No member of staff with the login {c['claimant_id']}")
        else:
            c["claimant_id"] = s["username"]
            c["claimant_name"] = c["claimant_name"] or s["display_name"]
    _given, line_id = _budget_line(data, problems)
    if line_id and not c["department"]:
        c["department"] = B.get_line(line_id).centre_name
    if c["claim_ref"] and get_claim_by_ref(c["claim_ref"]):
        problems.append(f"A claim with ref {c['claim_ref']!r} already exists")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        cid = conn.execute(
            f"INSERT INTO expense_claims ({', '.join(_HEADER)}, budget_line_id, status, "
            f"created_by, updated_by) VALUES ({', '.join('?' * len(_HEADER))}, ?, 'Draft', ?, ?)",
            (*(c[k] if k != "claim_ref" else c[k] or f"TMP-{uuid.uuid4().hex}"
               for k in _HEADER), line_id, actor.username, actor.username)).lastrowid
        if not c["claim_ref"]:
            conn.execute("UPDATE expense_claims SET claim_ref = ? WHERE claim_id = ?",
                         (f"EXP-{_today().year}-{cid:04d}", cid))
        _audit(conn, "create", actor, cid, claimant_type=c["claimant_type"],
               budget_line=line_id)
    activity_log.record("expenses.create", target=cid, principal=actor)
    return _get(cid)


def update_claim(claim_id: int, changes: dict[str, Any], *, actor: Principal) -> Claim:
    """The old Edit claim (drafts only)."""
    cur = get_claim(claim_id, actor=actor)
    _require(actor, cur, "edit", f"Claim {cur.claim_ref} is {cur.status.lower()} - only a "
                                 "draft can be changed")
    changes = dict(changes)
    if not is_approver(actor):
        for k in ("claim_ref", "claimant_type", "claimant_id"):
            if k in changes and str(changes[k] or "") != str(getattr(cur, k) or ""):
                _deny(actor, "update", cur.claim_id,
                      "Only the finance office can change the claimant or the reference.")
            changes.pop(k, None)
    c, problems = _clean(changes, cur)
    if not c["claim_ref"]:
        problems.append("Claim reference is required")
    elif c["claim_ref"] != cur.claim_ref:
        other = get_claim_by_ref(c["claim_ref"])
        if other and other.claim_id != cur.claim_id:
            problems.append(f"A claim with ref {c['claim_ref']!r} already exists")
    if c["claimant_type"] == "Staff" and (c["claimant_id"] or "").lower() != \
            cur.claimant_id.lower() and _staff(c["claimant_id"] or "") is None:
        problems.append(f"No member of staff with the login {c['claimant_id']}")
    if not c["claimant_id"]:
        problems.append("Claimant id is required")
    given, line_id = _budget_line(changes, problems)
    if not given:
        line_id = cur.budget_line_id
    changed = [k for k in _HEADER if c[k] != getattr(cur, k)]
    if line_id != cur.budget_line_id:
        changed.append("budget_line_id")
    if problems:
        raise ValidationError(problems)
    if not changed:
        return cur
    vals = {k: c[k] for k in changed if k in _HEADER}
    if "budget_line_id" in changed:
        vals["budget_line_id"] = line_id
    with database.connect() as conn:
        conn.execute("UPDATE expense_claims SET " + ", ".join(f"{k} = ?" for k in vals)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE claim_id = ?",
                     (*vals.values(), actor.username, cur.claim_id))
        _audit(conn, "update", actor, cur.claim_id, fields=changed)
    activity_log.record("expenses.update", target=cur.claim_id, principal=actor,
                        fields=",".join(changed))
    return _get(cur.claim_id)


def delete_claim(claim_id: int, *, actor: Principal) -> bool:
    """Delete a draft or cancelled claim (never one that reached the budget)."""
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "delete", f"Claim {c.claim_ref} is {c.status.lower()} - only a draft or "
                                 "cancelled claim can be deleted")
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM budget_spend WHERE source = 'expense_claim' AND "
                        "source_id = ? LIMIT 1", (c.claim_id,)).fetchone():
            raise ValidationError(["This claim was approved and posted to the budget - keep "
                                   "it on record"])
        conn.execute("DELETE FROM expense_claims WHERE claim_id = ?", (c.claim_id,))
        _audit(conn, "delete", actor, c.claim_id, ref=c.claim_ref)
    activity_log.record("expenses.delete", target=c.claim_id, principal=actor)
    return True


# ── Lines ────────────────────────────────────────────────────────────

_LINE_FIELDS = ("incurred_on", "category", "description", "supplier", "receipt_ref",
                "receipt_path", "quantity", "unit_pence", "mileage_miles", "mileage_rate_pence",
                "vat_pence", "net_pence", "gross_pence", "notes")


def _clean_line(data: dict[str, Any], cur: ClaimLine | None, claim: Claim
                ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    base = {k: getattr(cur, k) for k in _LINE_FIELDS} if cur else {}

    def val(key: str, *alts: str) -> Any:
        for k in (key, *alts):
            if k in data:
                return data[k]
        return base.get(key)
    out: dict[str, Any] = {}
    out["incurred_on"] = _date(val("incurred_on"), "Incurred on", problems)
    if out["incurred_on"] is None and not any(p.startswith("Incurred on") for p in problems):
        problems.append("Incurred on is required")
    if out["incurred_on"]:
        if out["incurred_on"] > _today().isoformat():
            problems.append("Incurred on can't be in the future")
        if claim.incurred_from and out["incurred_on"] < claim.incurred_from:
            problems.append(f"Incurred on is before the claim's period ({claim.incurred_from})")
        if claim.incurred_to and out["incurred_on"] > claim.incurred_to:
            problems.append(f"Incurred on is after the claim's period ({claim.incurred_to})")
    out["category"] = _choice(val("category"), CATEGORIES, "Category", problems,
                              claim.category or DEFAULT_CATEGORY)
    out["description"] = _text(val("description"), 300)
    if not out["description"]:
        problems.append("Description is required")
    out["supplier"] = _text(val("supplier"), 120)
    out["receipt_ref"] = _text(val("receipt_ref"), 60)
    out["receipt_path"] = (str(val("receipt_path") or "").strip()[:500]) or None
    out["notes"] = _text(val("notes"), 1000)
    if out["category"] == MILEAGE:
        raw = val("mileage_miles", "miles")
        try:
            miles = Decimal(str(raw).strip()) if raw not in (None, "") else None
        except InvalidOperation:
            miles = None
            problems.append("Miles must be a number")
        if miles is None and not problems[-1:] == ["Miles must be a number"]:
            problems.append("Miles are required for a mileage line")
        elif miles is not None and not (0 < miles <= MAX_MILES):
            problems.append(f"Miles must be more than 0 and at most {MAX_MILES}")
        miles = (miles or Decimal(0)).quantize(Decimal("0.1"), ROUND_HALF_UP)
        rate = cur.mileage_rate_pence if cur and cur.mileage_rate_pence and \
            cur.category == MILEAGE else mileage_rate()
        vraw = val("vat_pence", "vat_amount", "vat")
        vat = B.to_pence(vraw if vraw not in (None, "") else 0, "VAT", problems)
        if vat:
            problems.append("Mileage has no VAT")
        out.update(mileage_miles=float(miles), mileage_rate_pence=rate, quantity=1,
                   vat_pence=0)
        out["net_pence"] = int((miles * rate).quantize(Decimal("1"), ROUND_HALF_UP))
        out["unit_pence"] = out["net_pence"]
    else:
        q = val("quantity")
        try:
            out["quantity"] = int(str(q).strip()) if q not in (None, "") else 1
            if out["quantity"] < 1 or out["quantity"] > 1000:
                problems.append("Quantity must be from 1 to 1000")
        except ValueError:
            problems.append("Quantity must be a whole number")
            out["quantity"] = 1
        unit = B.to_pence(val("unit_pence", "unit_amount", "amount"), "Amount", problems,
                          allow_zero=False)
        out["unit_pence"] = unit or 0
        out["net_pence"] = out["unit_pence"] * out["quantity"]
        vraw = val("vat_pence", "vat_amount", "vat")
        out["vat_pence"] = B.to_pence(vraw if vraw not in (None, "") else 0, "VAT",
                                      problems) or 0
        if out["vat_pence"] > out["net_pence"]:
            problems.append("VAT can't be more than the amount before VAT")
        out["mileage_miles"] = out["mileage_rate_pence"] = None
    out["gross_pence"] = out["net_pence"] + out["vat_pence"]
    return out, problems


def _limit_problems(conn, claim_id: int, skip_line: int | None = None,
                    extra: dict[str, int] | None = None) -> list[str]:
    caps = dict(conn.execute("SELECT category, limit_pence FROM expense_limits").fetchall())
    if not caps:
        return []
    totals = Counter()
    for r in conn.execute("SELECT line_id, category, gross_pence FROM expense_claim_lines WHERE "
                          "claim_id = ?", (claim_id,)):
        if r["line_id"] != skip_line:
            totals[r["category"]] += r["gross_pence"]
    for k, v in (extra or {}).items():
        totals[k] += v
    return [f"{cat} comes to {money(t)} on this claim - the limit is {money(caps[cat])}"
            for cat, t in totals.items() if cat in caps and t > caps[cat]]


def add_line(claim_id: int, data: dict[str, Any], *, actor: Principal) -> ClaimLine:
    """The old Add line (draft claims). Mileage lines take ``mileage_miles``
    and use the current rate; others ``unit_amount`` (pounds) or
    ``unit_pence``, ``quantity`` and ``vat_amount`` / ``vat_pence``."""
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "lines", f"Claim {c.claim_ref} is {c.status.lower()} - lines can only "
                                "be changed on a draft")
    ln, problems = _clean_line(data, None, c)
    with database.connect() as conn:
        if not problems:
            problems += _limit_problems(conn, c.claim_id, extra={ln["category"]:
                                                                 ln["gross_pence"]})
        if problems:
            raise ValidationError(problems)
        lid = conn.execute(
            f"INSERT INTO expense_claim_lines (claim_id, {', '.join(_LINE_FIELDS)}) VALUES "
            f"(?, {', '.join('?' * len(_LINE_FIELDS))})",
            (c.claim_id, *(ln[k] for k in _LINE_FIELDS))).lastrowid
        conn.execute("UPDATE expense_claims SET updated_by = ?, updated_at = datetime('now') "
                     "WHERE claim_id = ?", (actor.username, c.claim_id))
        _audit(conn, "line_add", actor, c.claim_id, line=lid, category=ln["category"])
    activity_log.record("expenses.line_add", target=c.claim_id, principal=actor, line=lid)
    return get_line(lid)


def update_line(line_id: int, changes: dict[str, Any], *, actor: Principal) -> ClaimLine:
    cur = get_line(line_id)
    c = get_claim(cur.claim_id, actor=actor)
    _require(actor, c, "lines", f"Claim {c.claim_ref} is {c.status.lower()} - lines can only "
                                "be changed on a draft")
    ln, problems = _clean_line(changes, cur, c)
    with database.connect() as conn:
        if not problems:
            problems += _limit_problems(conn, c.claim_id, skip_line=cur.line_id,
                                        extra={ln["category"]: ln["gross_pence"]})
        if problems:
            raise ValidationError(problems)
        conn.execute("UPDATE expense_claim_lines SET " + ", ".join(f"{k} = ?" for k in
                                                                   _LINE_FIELDS)
                     + ", updated_at = datetime('now') WHERE line_id = ?",
                     (*(ln[k] for k in _LINE_FIELDS), cur.line_id))
        _audit(conn, "line_update", actor, c.claim_id, line=cur.line_id)
    activity_log.record("expenses.line_update", target=c.claim_id, principal=actor,
                        line=cur.line_id)
    return get_line(cur.line_id)


def delete_line(line_id: int, *, actor: Principal) -> bool:
    cur = get_line(line_id)
    c = get_claim(cur.claim_id, actor=actor)
    _require(actor, c, "lines", f"Claim {c.claim_ref} is {c.status.lower()} - lines can only "
                                "be changed on a draft")
    with database.connect() as conn:
        conn.execute("DELETE FROM expense_claim_lines WHERE line_id = ?", (cur.line_id,))
        _audit(conn, "line_delete", actor, c.claim_id, line=cur.line_id)
    activity_log.record("expenses.line_delete", target=c.claim_id, principal=actor,
                        line=cur.line_id)
    return True


# ── Workflow ─────────────────────────────────────────────────────────

def submit_problems(claim_id: int) -> list[str]:
    """What stops a claim being submitted (empty when it can go)."""
    c = _get(claim_id)
    lines = lines_for_claim(c.claim_id)
    out: list[str] = []
    if not lines:
        out.append("Cannot submit a claim with no lines")
    elif c.total_pence <= 0:
        out.append("The claim comes to £0.00")
    if not c.budget_line_id:
        out.append("Choose the budget code (cost centre) to charge")
    elif c.budget_line_id not in {x["line_id"] for x in B.codes_for_claims()}:
        out.append(f"Budget code {c.budget_code} isn't open for claims - choose another")
    over = settings()["receipt_over_pence"]
    for ln in lines:
        if ln.category != MILEAGE and ln.gross_pence > over and not ln.has_receipt:
            out.append(f"Line #{ln.line_id} ({ln.description or ln.category}, "
                       f"{money(ln.gross_pence)}) needs a receipt reference or file")
        if ln.incurred_on > _today().isoformat():
            out.append(f"Line #{ln.line_id} is dated in the future")
    with database.connect() as conn:
        out += _limit_problems(conn, c.claim_id)
    return out


def _set(conn, c: Claim, actor: Principal, status: str, **cols: Any) -> None:
    sets = {"status": status, **cols}
    conn.execute("UPDATE expense_claims SET " + ", ".join(f"{k} = ?" for k in sets)
                 + ", updated_by = ?, updated_at = datetime('now') WHERE claim_id = ?",
                 (*sets.values(), actor.username, c.claim_id))


def submit(claim_id: int, *, actor: Principal) -> Claim:
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "submit", f"Claim {c.claim_ref} is {c.status.lower()} - only a draft "
                                 "can be submitted")
    problems = submit_problems(c.claim_id)
    if problems:
        raise ValidationError(problems)
    receipts = 1 if any(ln.has_receipt for ln in lines_for_claim(c.claim_id)) else \
        c.receipts_attached
    with database.connect() as conn:
        _set(conn, c, actor, "Submitted", submitted_on=_today().isoformat(),
             receipts_attached=receipts, rejected_on=None, rejected_by=None,
             rejection_reason=None)
        _audit(conn, "submit", actor, c.claim_id)
    activity_log.record("expenses.submit", target=c.claim_id, principal=actor)
    return _get(c.claim_id)


def begin_review(claim_id: int, *, actor: Principal) -> Claim:
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "review", f"Claim {c.claim_ref} is {c.status.lower()} - only a "
                                 "submitted claim can go under review")
    with database.connect() as conn:
        _set(conn, c, actor, "Under Review", reviewed_by=actor.username)
        _audit(conn, "review", actor, c.claim_id)
    activity_log.record("expenses.review", target=c.claim_id, principal=actor)
    return _get(c.claim_id)


def approval_warnings(claim_id: int) -> list[str]:
    """Worth a second look before approving: the budget line going over or
    past its warning percentage."""
    c = _get(claim_id)
    out: list[str] = []
    if c.budget_line_id:
        out += B.check_spend(c.budget_line_id, c.total_pence)
    return out


def approve(claim_id: int, *, actor: Principal, note: str | None = None) -> Claim:
    """Approve and post the total as spend against the claim's budget line."""
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "approve", f"Claim {c.claim_ref} is {c.status.lower()} - only a "
                                  "submitted claim can be approved")
    problems = [p for p in submit_problems(c.claim_id)
                if not p.startswith("Line #") or "future" in p]
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        sid = B.post_claim(conn, claim_id=c.claim_id, line_id=c.budget_line_id,
                           amount_pence=c.total_pence, day=_today().isoformat(),
                           description=f"Expense claim {c.claim_ref}: {c.title}",
                           reference=c.claim_ref, actor=actor)
        _set(conn, c, actor, "Approved", approved_on=_today().isoformat(),
             approved_by=actor.username,
             notes=(c.notes + "\n" if c.notes else "") + f"Approval note: {note.strip()}"
             if note and note.strip() else c.notes)
        _audit(conn, "approve", actor, c.claim_id, spend=sid, budget_line=c.budget_line_id)
    activity_log.record("expenses.approve", target=c.claim_id, principal=actor)
    return _get(c.claim_id)


def reject(claim_id: int, *, actor: Principal, reason: str | None = None) -> Claim:
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "reject", f"Claim {c.claim_ref} is {c.status.lower()} - only a "
                                 "submitted claim can be rejected")
    why = _text(reason, 500)
    if not why:
        raise ValidationError(["Give the reason for rejecting the claim"])
    with database.connect() as conn:
        _set(conn, c, actor, "Rejected", rejected_on=_today().isoformat(),
             rejected_by=actor.username, rejection_reason=why)
        _audit(conn, "reject", actor, c.claim_id)
    activity_log.record("expenses.reject", target=c.claim_id, principal=actor)
    return _get(c.claim_id)


def reopen(claim_id: int, *, actor: Principal) -> Claim:
    """A rejected claim goes back to draft so the claimant can fix it (the
    rejection reason stays visible until it is submitted again)."""
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "reopen", f"Claim {c.claim_ref} is {c.status.lower()} - only a "
                                 "rejected claim can be reopened")
    with database.connect() as conn:
        _set(conn, c, actor, "Draft", submitted_on=None, reviewed_by=None)
        _audit(conn, "reopen", actor, c.claim_id)
    activity_log.record("expenses.reopen", target=c.claim_id, principal=actor)
    return _get(c.claim_id)


def pay(claim_id: int, *, actor: Principal, payment_reference: str | None = None,
        paid_on: str | None = None, payment_method: str | None = None) -> Claim:
    """The old Pay: an approved claim is paid (approvers, not their own)."""
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "pay", "Only Approved claims can be marked Paid")
    problems: list[str] = []
    day = _date(paid_on, "Paid on", problems) or _today().isoformat()
    if c.approved_on and day < c.approved_on:
        problems.append("Paid on can't be before the approval")
    method = _choice(payment_method, PAYMENT_METHODS, "Payment method", problems,
                     c.payment_method)
    ref = _text(payment_reference, 60)
    if not ref:
        problems.append("Payment reference is required")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        _set(conn, c, actor, "Paid", paid_on=day, paid_by=actor.username,
             payment_reference=ref, payment_method=method)
        _audit(conn, "pay", actor, c.claim_id, reference=ref)
    activity_log.record("expenses.pay", target=c.claim_id, principal=actor)
    return _get(c.claim_id)


def cancel(claim_id: int, *, actor: Principal, reason: str | None = None) -> Claim:
    """Cancel a claim not yet paid. An approved claim (finance office only)
    has its budget posting reversed."""
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "cancel", f"Claim {c.claim_ref} is {c.status.lower()} - it can't be "
                                 "cancelled")
    why = _text(reason, 500)
    with database.connect() as conn:
        rev = B.reverse_claim(conn, claim_id=c.claim_id, actor=actor) \
            if c.status == "Approved" else None
        _set(conn, c, actor, "Cancelled", cancelled_on=_today().isoformat(),
             notes=(c.notes + "\n" if c.notes else "") + f"Cancelled: {why}" if why else c.notes)
        _audit(conn, "cancel", actor, c.claim_id, reversal=rev)
    activity_log.record("expenses.cancel", target=c.claim_id, principal=actor)
    return _get(c.claim_id)


def set_status(claim_id: int, new_status: str, *, actor: Principal,
               reason: str | None = None, payment_reference: str | None = None,
               paid_on: str | None = None) -> Claim:
    """The old Change status, routed through the proper step so the rules
    (separation of duties, budget posting) still hold. Approvers only."""
    _require_approver(actor, "status", claim_id)
    problems: list[str] = []
    st = _choice(new_status, CLAIM_STATUSES, "Status", problems, None)
    if problems or not st:
        raise ValidationError(problems or ["Choose a status"])
    c = get_claim(claim_id, actor=actor)
    if st == c.status:
        return c
    steps = {"Submitted": lambda: submit(c.claim_id, actor=actor),
             "Under Review": lambda: begin_review(c.claim_id, actor=actor),
             "Approved": lambda: approve(c.claim_id, actor=actor, note=reason),
             "Rejected": lambda: reject(c.claim_id, actor=actor, reason=reason),
             "Paid": lambda: pay(c.claim_id, actor=actor, payment_reference=payment_reference,
                                 paid_on=paid_on),
             "Cancelled": lambda: cancel(c.claim_id, actor=actor, reason=reason),
             "Draft": lambda: reopen(c.claim_id, actor=actor)}
    return steps[st]()


# ── Payment runs ─────────────────────────────────────────────────────

def payable(actor: Principal) -> list[Claim]:
    """Approved claims *actor* may pay (an approver's own are left out)."""
    _require_approver(actor, "payable")
    return sorted((c for c in list_claims(scope="awaiting") if "pay" in allowed_actions(actor, c)),
                  key=lambda c: (c.approved_on or "", c.claim_id))


def list_payment_runs() -> list[PaymentRun]:
    with database.connect() as conn:
        return [PaymentRun(**{k: r[k] for k in PaymentRun.__dataclass_fields__})
                for r in conn.execute("SELECT * FROM expense_payment_runs ORDER BY run_id DESC")]


_RUN_HEADER = ["run_reference", "paid_on", "claim_ref", "claimant_type", "claimant_id",
               "claimant_name", "payment_method", "budget_code", "cost_centre", "lines",
               "amount"]


def _write_run(path: str | Path, ref: str, day: str, claims: list[Claim]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(_RUN_HEADER)
        for c in claims:
            w.writerow([ref, day, _safe(c.claim_ref), c.claimant_type, _safe(c.claimant_id),
                        _safe(c.claimant_name), c.payment_method, _safe(c.budget_code),
                        _safe(c.centre_name), c.line_count, pounds(c.total_pence)])


def payment_run(path: str | Path, *, actor: Principal, claim_ids: list[int] | None = None,
                paid_on: str | None = None, method: str | None = None) -> dict[str, Any]:
    """Pay approved claims in one run: write the CSV to *path* and mark each
    claim Paid with the run's reference. *claim_ids* default to every claim
    :func:`payable` lists (optionally only one payment *method*).
    Returns {'run_id', 'reference', 'claims', 'total_pence'}."""
    _require_approver(actor, "payment_run")
    problems: list[str] = []
    day = _date(paid_on, "Paid on", problems) or _today().isoformat()
    ok = {c.claim_id: c for c in payable(actor)}
    if claim_ids is None:
        chosen = [c for c in ok.values() if not method or c.payment_method == method]
    else:
        chosen = []
        for cid in claim_ids:
            if int(cid) in ok:
                chosen.append(ok[int(cid)])
            else:
                problems.append(f"Claim #{cid} isn't approved and payable by you")
    if not chosen and not problems:
        problems.append("No approved claims to pay")
    for c in chosen:
        if c.approved_on and day < c.approved_on:
            problems.append(f"{c.claim_ref} was approved after {day}")
    if problems:
        raise ValidationError(problems)
    total = sum(c.total_pence for c in chosen)
    with database.connect() as conn:
        rid = conn.execute("INSERT INTO expense_payment_runs (reference, run_date, claims, "
                           "total_pence, file_name, created_by) VALUES (?, ?, ?, ?, ?, ?)",
                           (f"TMP-{uuid.uuid4().hex}", day, len(chosen), total,
                            Path(path).name, actor.username)).lastrowid
        ref = f"PR-{rid:04d}"
        conn.execute("UPDATE expense_payment_runs SET reference = ? WHERE run_id = ?",
                     (ref, rid))
        for c in chosen:
            _set(conn, c, actor, "Paid", paid_on=day, paid_by=actor.username,
                 payment_reference=ref, payment_run_id=rid)
            _audit(conn, "pay", actor, c.claim_id, reference=ref, run=rid)
        _write_run(path, ref, day, chosen)   # inside the transaction: a failed write rolls back
    activity_log.record("expenses.payment_run", target=ref, principal=actor,
                        claims=len(chosen))
    return {"run_id": rid, "reference": ref, "claims": len(chosen), "total_pence": total}


def export_payment_run(run_id: int, path: str | Path, *, actor: Principal) -> int:
    """Write a past run's CSV again."""
    _require_approver(actor, "payment_run_export")
    run = next((r for r in list_payment_runs() if r.run_id == int(run_id)), None)
    if run is None:
        raise NotFound(f"No payment run #{run_id}")
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(_SELECT + " WHERE e.payment_run_id = ? ORDER BY "
                                              "e.claim_id", (run.run_id,))]
    _write_run(path, run.reference, run.run_date, rows)
    activity_log.record("expenses.payment_run_export", target=run.reference, principal=actor)
    return len(rows)


# ── Notices ──────────────────────────────────────────────────────────

def notify_claimant(claim_id: int, *, actor: Principal, note: str | None = None) -> int | None:
    """Prepare an e-mail telling a staff claimant their claim was approved,
    rejected or paid. Returns the outbox message id (deliver it next), or
    None when the claimant has no e-mail address."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    c = get_claim(claim_id, actor=actor)
    _require(actor, c, "notify", "Only approved, rejected or paid staff claims have a notice")
    s = _staff(c.claimant_id)
    if s is None or not s.get("email"):
        return None
    details = {"Approved": f"It has been approved by {B.staff_name(c.approved_by)} and will "
                           "be paid in the next payment run.",
               "Rejected": f"It was not approved. Reason: {c.rejection_reason}. You can "
                           "reopen it, make changes and submit it again.",
               "Paid": f"It was paid on {c.paid_on} ({c.payment_method}, reference "
                       f"{c.payment_reference})."}[c.status]
    if note and note.strip():
        details += f"\n\n{note.strip()}"
    subject, body = email_templates.load_template("expense_claim_update").render({
        "recipient_name": s["display_name"], "claim_ref": c.claim_ref, "title": c.title,
        "status": c.status.lower(), "total": c.total, "details": details,
        "sender_name": B.staff_name(actor.username)})
    mid = E.save_prepared("expense_claim", "Expense claim update", subject, "(one notice)",
                          [(s["email"], s["display_name"], subject, body)], actor=actor)
    with database.connect() as conn:
        _audit(conn, "notify", actor, c.claim_id, message=mid)
    activity_log.record("expenses.notify", target=c.claim_id, principal=actor, message=mid)
    return mid


# ── Summary and export ───────────────────────────────────────────────

def summary(*, actor: Principal | None = None) -> ExpenseClaimsSummary:
    """The old summary (values in pence)."""
    rows = list_claims(actor=actor)
    out = ExpenseClaimsSummary(total_claims=len(rows))
    field_for = {"Draft": "drafts", "Submitted": "submitted", "Under Review": "under_review",
                 "Approved": "approved", "Paid": "paid", "Rejected": "rejected",
                 "Cancelled": "cancelled"}
    for c in rows:
        setattr(out, field_for[c.status], getattr(out, field_for[c.status]) + 1)
        if c.status == "Approved":
            out.awaiting_payment_value += c.total_pence
        elif c.status == "Paid":
            out.paid_value += c.total_pence
        if c.status not in ("Cancelled", "Rejected"):
            out.total_value += c.total_pence
    out.distinct_claimants = len({(c.claimant_type, c.claimant_id.lower()) for c in rows})
    out.by_category = dict(Counter(c.category for c in rows))
    out.by_claimant_type = dict(Counter(c.claimant_type for c in rows))
    out.by_status = dict(Counter(c.status for c in rows))
    out.by_payment_method = dict(Counter(c.payment_method for c in rows))
    return out


def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    """Claims (what *actor* may see) with their totals."""
    _require_staff(actor, "export")
    rows = list_claims(actor=actor, **filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "ref", "claimant_type", "claimant_id", "claimant", "department",
                    "title", "category", "budget_code", "cost_centre", "incurred_from",
                    "incurred_to", "submitted", "approved", "approved_by", "rejected",
                    "rejection_reason", "paid", "payment_method", "payment_reference", "status",
                    "lines", "total"])
        for c in rows:
            w.writerow([c.claim_id, _safe(c.claim_ref), c.claimant_type, _safe(c.claimant_id),
                        _safe(c.claimant_name), _safe(c.department), _safe(c.title), c.category,
                        _safe(c.budget_code), _safe(c.centre_name), c.incurred_from or "",
                        c.incurred_to or "", c.submitted_on or "", c.approved_on or "",
                        _safe(c.approved_by), c.rejected_on or "", _safe(c.rejection_reason),
                        c.paid_on or "", c.payment_method, _safe(c.payment_reference),
                        c.status, c.line_count, pounds(c.total_pence)])
    activity_log.record("expenses.export", principal=actor, rows=len(rows))
    return len(rows)
