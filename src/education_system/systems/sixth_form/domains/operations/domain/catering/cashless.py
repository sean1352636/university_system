"""Cashless catering for the Sixth Form System.

Each learner has a catering account; the balance is the sum of their
transactions (whole **pence**, signed: top-ups and voids credit it,
purchases and refunds debit it). Nothing is ever edited or deleted —
a mistake is put right by a reversing transaction, so the history is
the audit trail.

Tables (``sixthform.db``):

* ``catering_accounts``      — one per learner: open/closed, own
  low-balance threshold, a hashed PIN (the non-biometric alternative to
  a card), PIN lockout.
* ``catering_transactions``  — top-ups (online / cash / bursary),
  purchases at the till (with the free-meal part, how the learner was
  identified and on which till), refunds and voids.
* ``catering_cashless_settings`` — top-up limits, the default low-balance
  threshold, PIN lockout.

Built on what the college already records, never duplicating it:

* **Free meals** — the till reads the learner's entitlement and daily
  allowance from ``free_meals`` (16-19 free meals) and logs the meal
  taken there through ``free_meals.record_usage``, so the monthly claim
  and the till agree. The allowance covers the first purchase of the day
  up to its value; the learner pays any difference from their balance.
* **Bursary meal entitlements** — a ``Free Meals (FSM)`` bursary award
  tops the account up by writing a ``Lunch Card`` bursary disbursement,
  so the award's remaining balance and the catering balance move
  together.
* **Online top-ups** — paid through ``online_payments``; the credit is
  posted here once per payment (unique per request).
* **Identification** — an ID card number (``id_cards``), a PIN, or a
  biometric match, which is refused unless ``biometric_consent`` says
  there is current consent (Protection of Freedoms Act 2012). The method
  used is recorded on every purchase. No reader hardware is driven here:
  a biometric reader reports the learner it matched, and the till checks
  consent before accepting it.

Permissions: OPERATIONS for till work, cash top-ups, PINs and voids;
FINANCE for bursary top-ups and refunds of balances (money going out).
Students and parents see their own account through
:func:`statement_for_payer`.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import re
import secrets
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB
CURRENCY_SYMBOL = "£"

OPEN = "Open"
CLOSED = "Closed"
ACCOUNT_STATUSES: tuple[str, ...] = (OPEN, CLOSED)

TOPUP = "Top-up"
PURCHASE = "Purchase"
REFUND = "Refund"
VOID = "Void"
ADJUSTMENT = "Adjustment"
TXN_TYPES: tuple[str, ...] = (TOPUP, PURCHASE, REFUND, VOID, ADJUSTMENT)

TOPUP_METHODS: tuple[str, ...] = ("Online", "Cash", "Bursary")
REFUND_METHODS: tuple[str, ...] = (
    "Cash", "Bank Transfer", "Cheque", "Card", "Other")

ID_CARD = "Card"
ID_PIN = "PIN"
ID_BIOMETRIC = "Biometric"
ID_STAFF = "Staff lookup"
ID_METHODS: tuple[str, ...] = (ID_CARD, ID_PIN, ID_BIOMETRIC, ID_STAFF)
#: Non-biometric ways to identify — always available at the till.
ALTERNATIVE_ID_METHODS: tuple[str, ...] = (ID_CARD, ID_PIN, ID_STAFF)

#: Bursary types that are meal entitlements and may fund top-ups.
MEAL_BURSARY_TYPES: tuple[str, ...] = ("Free Meals (FSM)",)

DEFAULT_SETTINGS: dict[str, int] = {
    "min_topup_pence": 100,
    "max_topup_pence": 10000,
    "max_balance_pence": 20000,
    "low_balance_pence": 300,
    "pin_max_failures": 5,
    "pin_lock_minutes": 15,
}

_PBKDF2_ROUNDS = 120_000
_PIN_RE = re.compile(r"^\d{4,6}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS catering_accounts (
    student_id        TEXT PRIMARY KEY,
    status            TEXT NOT NULL DEFAULT 'Open',
    low_balance_pence INTEGER,
    pin_hash          TEXT,
    pin_salt          TEXT,
    pin_set_at        TEXT,
    pin_failures      INTEGER NOT NULL DEFAULT 0,
    pin_locked_until  TEXT,
    opened_on         TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    closed_on         TEXT,
    closed_reason     TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE TABLE IF NOT EXISTS catering_transactions (
    txn_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    txn_type          TEXT NOT NULL,
    amount_pence      INTEGER NOT NULL,
    gross_pence       INTEGER NOT NULL DEFAULT 0,
    free_meal_pence   INTEGER NOT NULL DEFAULT 0,
    method            TEXT,
    id_method         TEXT,
    till              TEXT,
    items             TEXT,
    reference         TEXT,
    online_request_id INTEGER,
    bursary_application_id  INTEGER,
    bursary_disbursement_id INTEGER,
    free_meal_usage_id INTEGER,
    receipt_id        INTEGER,
    reverses_txn_id   INTEGER,
    recorded_by       TEXT,
    note              TEXT,
    at                TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (reverses_txn_id) REFERENCES catering_transactions(txn_id)
);

CREATE INDEX IF NOT EXISTS idx_ct_student ON catering_transactions(student_id);
CREATE INDEX IF NOT EXISTS idx_ct_at      ON catering_transactions(at);
CREATE INDEX IF NOT EXISTS idx_ct_type    ON catering_transactions(txn_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ct_online_topup
    ON catering_transactions(online_request_id)
    WHERE online_request_id IS NOT NULL AND txn_type = 'Top-up';
CREATE UNIQUE INDEX IF NOT EXISTS idx_ct_one_void
    ON catering_transactions(reverses_txn_id)
    WHERE reverses_txn_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS catering_cashless_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_by TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


class ValidationError(ValueError):
    pass


class InsufficientFunds(ValidationError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Account:
    student_id: str
    status: str
    low_balance_pence: int | None
    has_pin: bool
    pin_set_at: str | None
    pin_locked_until: str | None
    opened_on: str
    closed_on: str | None
    closed_reason: str | None
    notes: str | None

    @property
    def is_open(self) -> bool:
        return self.status == OPEN


@dataclass
class Transaction:
    txn_id: int
    student_id: str
    txn_type: str
    amount_pence: int
    gross_pence: int
    free_meal_pence: int
    method: str | None
    id_method: str | None
    till: str | None
    items: str | None
    reference: str | None
    online_request_id: int | None
    bursary_application_id: int | None
    bursary_disbursement_id: int | None
    free_meal_usage_id: int | None
    receipt_id: int | None
    reverses_txn_id: int | None
    recorded_by: str | None
    note: str | None
    at: str
    student_name: str | None = None
    voided: bool = False


@dataclass
class AccountView:
    student_id: str
    student_name: str
    student_status: str
    account_status: str          # Open / Closed / "No account"
    balance_pence: int
    threshold_pence: int
    has_pin: bool
    card_number: str | None
    biometric: str               # "Allowed" / reason it is not
    free_meal_today: str         # "" / "Available £x.xx" / "Used"
    last_activity: str | None

    @property
    def is_low(self) -> bool:
        return self.account_status != CLOSED and \
            self.balance_pence < self.threshold_pence


@dataclass
class Identification:
    student_id: str
    student_name: str
    method: str
    card_number: str | None = None


@dataclass
class TillReport:
    day: str
    purchases: int = 0
    gross_pence: int = 0
    free_meal_pence: int = 0
    charged_pence: int = 0
    free_meals: int = 0
    topups_by_method: dict[str, int] = field(default_factory=dict)
    refunds_pence: int = 0
    voids: int = 0
    by_id_method: dict[str, int] = field(default_factory=dict)
    by_till: dict[str, int] = field(default_factory=dict)
    cash_taken_pence: int = 0


@dataclass
class CashlessSummary:
    accounts: int = 0
    open_accounts: int = 0
    total_balance_pence: int = 0
    low_balance: int = 0
    leavers_owed: int = 0
    leavers_owed_pence: int = 0
    with_pin: int = 0
    today: TillReport | None = None


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
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Cashless catering schema ready at %s", DB_PATH)
    _DB_READY = True


def _account(r: _sql.Row) -> Account:
    return Account(
        student_id=r["student_id"], status=r["status"],
        low_balance_pence=r["low_balance_pence"],
        has_pin=bool(r["pin_hash"]), pin_set_at=r["pin_set_at"],
        pin_locked_until=r["pin_locked_until"], opened_on=r["opened_on"],
        closed_on=r["closed_on"], closed_reason=r["closed_reason"],
        notes=r["notes"])


_TXN_SELECT = (
    "SELECT t.*, s.first_name AS s_first, s.last_name AS s_last, "
    "(SELECT 1 FROM catering_transactions v "
    "  WHERE v.reverses_txn_id = t.txn_id) AS is_voided "
    "FROM catering_transactions t "
    "LEFT JOIN students s ON s.student_id = t.student_id")


def _txn(r: _sql.Row) -> Transaction:
    keys = r.keys()
    name = None
    if "s_first" in keys and r["s_first"] is not None:
        name = f"{r['s_first']} {r['s_last'] or ''}".strip()
    return Transaction(
        txn_id=r["txn_id"], student_id=r["student_id"],
        txn_type=r["txn_type"], amount_pence=int(r["amount_pence"]),
        gross_pence=int(r["gross_pence"] or 0),
        free_meal_pence=int(r["free_meal_pence"] or 0),
        method=r["method"], id_method=r["id_method"], till=r["till"],
        items=r["items"], reference=r["reference"],
        online_request_id=r["online_request_id"],
        bursary_application_id=r["bursary_application_id"],
        bursary_disbursement_id=r["bursary_disbursement_id"],
        free_meal_usage_id=r["free_meal_usage_id"],
        receipt_id=r["receipt_id"], reverses_txn_id=r["reverses_txn_id"],
        recorded_by=r["recorded_by"], note=r["note"], at=r["at"],
        student_name=name,
        voided=bool(r["is_voided"]) if "is_voided" in keys else False)


# ── Helpers ─────────────────────────────────────────────────────────

def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def _actor() -> str:
    return _access().current().username or "system"


def _require(cap_name: str, action: str) -> None:
    a = _access()
    a.current().require(getattr(a, cap_name), action)


def _require_ops(action: str) -> None:
    _require("OPERATIONS", action)


def _require_ops_or_finance(action: str) -> None:
    a = _access()
    p = a.current()
    if not (p.can(a.OPERATIONS) or p.can(a.FINANCE)):
        p.require(a.OPERATIONS, action)


def money(pence: int | None) -> str:
    if pence is None:
        return ""
    sign = "-" if pence < 0 else ""
    return f"{sign}{CURRENCY_SYMBOL}{abs(pence) / 100:,.2f}"


def to_pence(value: Any, label: str = "Amount") -> int:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    s = str(value).strip().lstrip(CURRENCY_SYMBOL).replace(",", "")
    try:
        d = Decimal(s)
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{label} must be an amount in pounds") from None
    if d.as_tuple().exponent < -2:
        raise ValidationError(f"{label} must have at most 2 decimal places")
    if d <= 0:
        raise ValidationError(f"{label} must be more than zero")
    return int((d * 100).to_integral_value())


def _pounds(pence: int) -> float:
    return float((Decimal(pence) / 100).quantize(Decimal("0.01")))


def _today() -> str:
    return _dt.date.today().isoformat()


def _student(sid: Any):
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    s = str(sid or "").strip()
    if not s:
        raise ValidationError("Student is required")
    st = _students.get_student(s)
    if st is None:
        raise ValidationError(f"No student with id {s}")
    return st


def _text(v: Any) -> str | None:
    s = str(v).strip() if v is not None else ""
    return s or None


# ── Settings ────────────────────────────────────────────────────────

def settings() -> dict[str, int]:
    init_db()
    out = dict(DEFAULT_SETTINGS)
    with _connect() as conn:
        for r in conn.execute("SELECT key, value FROM catering_cashless_settings"):
            if r["key"] in out:
                try:
                    out[r["key"]] = int(r["value"])
                except ValueError:
                    pass
    return out


def set_setting(key: str, value: Any) -> dict[str, int]:
    """Change a limit (OPERATIONS). Money settings take pounds."""
    _require_ops("cashless catering settings")
    if key not in DEFAULT_SETTINGS:
        raise ValidationError(
            f"Setting must be one of: {', '.join(DEFAULT_SETTINGS)}")
    if key.endswith("_pence"):
        v = to_pence(value, key.replace("_pence", "").replace("_", " "))
    else:
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{key} must be a whole number") from None
        if v < 1:
            raise ValidationError(f"{key} must be at least 1")
    cur = settings()
    cur[key] = v
    if cur["min_topup_pence"] > cur["max_topup_pence"]:
        raise ValidationError("Minimum top-up cannot be above the maximum")
    if cur["max_topup_pence"] > cur["max_balance_pence"]:
        raise ValidationError("Maximum top-up cannot be above the balance cap")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO catering_cashless_settings (key, value, updated_by) "
            "VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, updated_by = excluded.updated_by, "
            "updated_at = datetime('now')", (key, str(v), _actor()))
    return settings()


# ── Accounts and balances ───────────────────────────────────────────

def get_account(student_id: str) -> Account | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM catering_accounts WHERE student_id = ?",
                         ((student_id or "").strip(),)).fetchone()
    return _account(r) if r else None


def _ensure_account(conn: _sql.Connection, student_id: str) -> Account:
    conn.execute("INSERT OR IGNORE INTO catering_accounts (student_id) "
                 "VALUES (?)", (student_id,))
    r = conn.execute("SELECT * FROM catering_accounts WHERE student_id = ?",
                     (student_id,)).fetchone()
    return _account(r)


def open_account(student_id: str, *, notes: str | None = None) -> Account:
    """Open (or re-open) a learner's catering account (OPERATIONS)."""
    _require_ops("catering accounts")
    init_db()
    st = _student(student_id)
    with _connect() as conn:
        acct = _ensure_account(conn, st.student_id)
        if not acct.is_open:
            conn.execute(
                "UPDATE catering_accounts SET status = 'Open', closed_on = NULL,"
                " closed_reason = NULL, updated_at = datetime('now') "
                "WHERE student_id = ?", (st.student_id,))
        if notes is not None:
            conn.execute("UPDATE catering_accounts SET notes = ? "
                         "WHERE student_id = ?", (_text(notes), st.student_id))
    out = get_account(st.student_id)
    assert out is not None
    return out


def balance_pence(student_id: str) -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(amount_pence), 0) AS b FROM "
            "catering_transactions WHERE student_id = ?",
            ((student_id or "").strip(),)).fetchone()
    return int(r["b"])


def _balance(conn: _sql.Connection, student_id: str) -> int:
    return int(conn.execute(
        "SELECT COALESCE(SUM(amount_pence), 0) FROM catering_transactions "
        "WHERE student_id = ?", (student_id,)).fetchone()[0])


def threshold_pence(acct: Account | None) -> int:
    if acct is not None and acct.low_balance_pence is not None:
        return acct.low_balance_pence
    return settings()["low_balance_pence"]


def set_low_balance(student_id: str, amount: Any) -> Account:
    """A learner's own low-balance threshold; blank = college default."""
    _require_ops("catering accounts")
    st = _student(student_id)
    pence = None if amount in (None, "") else to_pence(amount, "Threshold")
    with _connect() as conn:
        _ensure_account(conn, st.student_id)
        conn.execute("UPDATE catering_accounts SET low_balance_pence = ?, "
                     "updated_at = datetime('now') WHERE student_id = ?",
                     (pence, st.student_id))
    out = get_account(st.student_id)
    assert out is not None
    return out


def validate_topup_amount(student_id: str, pence: int) -> None:
    """Raise if *pence* cannot be added to this learner's account now."""
    st = _student(student_id)
    acct = get_account(st.student_id)
    if acct is not None and not acct.is_open:
        raise ValidationError(
            f"{st.full_name}'s catering account is closed")
    if not st.on_roll:
        raise ValidationError(f"{st.full_name} is not on roll ({st.status})")
    cfg = settings()
    if pence < cfg["min_topup_pence"]:
        raise ValidationError(
            f"The smallest top-up is {money(cfg['min_topup_pence'])}")
    if pence > cfg["max_topup_pence"]:
        raise ValidationError(
            f"The largest top-up is {money(cfg['max_topup_pence'])}")
    bal = balance_pence(st.student_id)
    if bal + pence > cfg["max_balance_pence"]:
        raise ValidationError(
            f"That would take the balance over the "
            f"{money(cfg['max_balance_pence'])} limit (now {money(bal)})")


def _insert(conn: _sql.Connection, **cols: Any) -> int:
    cols.setdefault("recorded_by", _actor())
    keys = list(cols)
    # db-audit: ignore[DBW001] - column names come from this module's own keyword arguments
    cur = conn.execute(
        f"INSERT INTO catering_transactions ({', '.join(keys)}) "
        f"VALUES ({', '.join('?' * len(keys))})", [cols[k] for k in keys])
    return int(cur.lastrowid)


def get_transaction(txn_id: int) -> Transaction | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_TXN_SELECT} WHERE t.txn_id = ?",
                         (int(txn_id),)).fetchone()
    return _txn(r) if r else None


# ── Top-ups ─────────────────────────────────────────────────────────

def cash_topup(student_id: str, amount: Any, *, till: str | None = None,
               note: str | None = None) -> Transaction:
    """Cash handed in at the till or office (OPERATIONS); issues a receipt."""
    _require_ops("cash top-ups")
    init_db()
    pence = to_pence(amount)
    validate_topup_amount(student_id, pence)
    st = _student(student_id)
    with _connect() as conn:
        _ensure_account(conn, st.student_id)
        tid = _insert(conn, student_id=st.student_id, txn_type=TOPUP,
                      amount_pence=pence, method="Cash", till=_text(till),
                      note=_text(note))
    from education_system.systems.sixth_form.domains.finance.domain.receipts import (
        receipts as _rc,
    )
    try:
        rc = _rc.create_receipt(
            {"payer_name": st.full_name, "student_id": st.student_id,
             "method": "Cash", "status": "Issued", "received_by": _actor(),
             "reference": f"CAT-{tid}",
             "notes": f"Catering cash top-up #{tid}"},
            [{"description": "Catering account top-up",
              "amount": _pounds(pence), "kind": "lunch", "source_id": tid}])
        with _connect() as conn:
            conn.execute("UPDATE catering_transactions SET receipt_id = ? "
                         "WHERE txn_id = ?", (rc.receipt_id, tid))
    except ValueError as e:
        logger.warning("Receipt for catering top-up #%d not created: %s", tid, e)
    logger.info("Catering cash top-up #%d: %s %s", tid, st.student_id,
                money(pence))
    out = get_transaction(tid)
    assert out is not None
    return out


def credit_from_online_payment(request_id: int) -> Transaction:
    """Post a paid online top-up (called by ``online_payments`` only).

    The amount and learner come from the payment request itself, which
    must be Paid and claimed for posting. One top-up per request (unique
    index), so a repeated call returns the existing credit.
    """
    from education_system.systems.sixth_form.domains.finance.domain.online_payments import (
        online_payments as _op,
    )
    init_db()
    req = _op.get_request(int(request_id), _check=False)
    if req is None or req.item_kind != _op.KIND_CATERING:
        raise ValidationError(f"No catering payment request #{request_id}")
    if req.status != _op.PAID or req.posting_state not in ("Claimed", "Posted"):
        raise ValidationError(f"{req.reference} is not a paid request")
    with _connect() as conn:
        r = conn.execute("SELECT txn_id FROM catering_transactions WHERE "
                         "online_request_id = ? AND txn_type = 'Top-up'",
                         (req.request_id,)).fetchone()
        if r is not None:
            tid = int(r["txn_id"])
        else:
            _ensure_account(conn, req.student_id)
            try:
                tid = _insert(
                    conn, student_id=req.student_id, txn_type=TOPUP,
                    amount_pence=req.amount_pence,
                    method="Online" if not req.is_offline else (
                        req.offline_method or "Cash"),
                    reference=req.payment_reference,
                    online_request_id=req.request_id,
                    recorded_by=req.created_by or _actor(),
                    note=f"Payment {req.reference}")
            except _sql.IntegrityError:
                conn.rollback()
                r = conn.execute(
                    "SELECT txn_id FROM catering_transactions WHERE "
                    "online_request_id = ? AND txn_type = 'Top-up'",
                    (req.request_id,)).fetchone()
                tid = int(r["txn_id"])
    out = get_transaction(tid)
    assert out is not None
    return out


def debit_for_online_refund(request_id: int, pence: int, *,
                            reason: str) -> Transaction:
    """Take a refunded online top-up back off the balance (called by
    ``online_payments.refund``, which has already checked FINANCE)."""
    from education_system.systems.sixth_form.domains.finance.domain.online_payments import (
        online_payments as _op,
    )
    req = _op.get_request(int(request_id), _check=False)
    if req is None or req.item_kind != _op.KIND_CATERING:
        raise ValidationError(f"No catering payment request #{request_id}")
    with _connect() as conn:
        if _balance(conn, req.student_id) < pence:
            raise InsufficientFunds("Balance is lower than the refund")
        tid = _insert(conn, student_id=req.student_id, txn_type=REFUND,
                      amount_pence=-int(pence), method="Card",
                      reference=req.payment_reference,
                      online_request_id=req.request_id, note=reason)
    out = get_transaction(tid)
    assert out is not None
    return out


def meal_bursaries(student_id: str) -> list[Any]:
    """Approved meal-entitlement bursary awards with money left."""
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _b,
    )
    return [v for v in _b.list_views(student_id=student_id, approved_only=True)
            if v.app.bursary_type in MEAL_BURSARY_TYPES and v.remaining > 0]


def bursary_topup(student_id: str, application_id: int, amount: Any, *,
                  note: str | None = None) -> Transaction:
    """Top up from a learner's meal-entitlement bursary (FINANCE).

    Writes a ``Lunch Card`` disbursement against the award (capped by what
    is left of it) and the matching top-up here.
    """
    _require("FINANCE", "bursary-funded catering top-ups")
    init_db()
    st = _student(student_id)
    pence = to_pence(amount)
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _b,
    )
    award = _b.view_application(int(application_id))
    if award is None:
        raise ValidationError(f"No bursary award #{application_id}")
    if award.app.student_id != st.student_id:
        raise ValidationError("That bursary belongs to a different learner")
    if award.app.bursary_type not in MEAL_BURSARY_TYPES:
        raise ValidationError(
            f"Bursary #{application_id} is {award.app.bursary_type}, not a "
            "meal entitlement")
    if not award.app.is_approved:
        raise ValidationError(
            f"Bursary #{application_id} is {award.app.status}, not approved")
    if pence > int(round(award.remaining * 100)):
        raise ValidationError(
            f"Bursary #{application_id} has only "
            f"{CURRENCY_SYMBOL}{award.remaining:.2f} left")
    validate_topup_amount(st.student_id, pence)
    try:
        disb = _b.add_disbursement(int(application_id), {
            "amount": _pounds(pence), "method": "Lunch Card", "status": "Paid",
            "recorded_by": _actor(),
            "reference": f"Catering account {st.student_id}",
            "notes": _text(note) or "Cashless catering top-up"})
    except _b.ValidationError as e:
        raise ValidationError(str(e)) from None
    with _connect() as conn:
        _ensure_account(conn, st.student_id)
        tid = _insert(conn, student_id=st.student_id, txn_type=TOPUP,
                      amount_pence=pence, method="Bursary",
                      reference=f"Bursary #{application_id}/"
                                f"disbursement #{disb.disbursement_id}",
                      bursary_application_id=int(application_id),
                      bursary_disbursement_id=disb.disbursement_id,
                      note=_text(note))
    out = get_transaction(tid)
    assert out is not None
    return out


# ── PINs (non-biometric alternative) ────────────────────────────────

def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(),
                               _PBKDF2_ROUNDS).hex()


def set_pin(student_id: str, pin: str) -> Account:
    """Set the learner's till PIN (4–6 digits; OPERATIONS)."""
    _require_ops("catering PINs")
    st = _student(student_id)
    p = (pin or "").strip()
    if not _PIN_RE.match(p):
        raise ValidationError("PIN must be 4 to 6 digits")
    if len(set(p)) == 1 or p in "0123456789" or p in "9876543210":
        raise ValidationError("PIN is too easy to guess")
    salt = secrets.token_hex(16)
    with _connect() as conn:
        _ensure_account(conn, st.student_id)
        conn.execute(
            "UPDATE catering_accounts SET pin_hash = ?, pin_salt = ?, "
            "pin_set_at = datetime('now'), pin_failures = 0, "
            "pin_locked_until = NULL, updated_at = datetime('now') "
            "WHERE student_id = ?", (_hash_pin(p, salt), salt, st.student_id))
    out = get_account(st.student_id)
    assert out is not None
    return out


def clear_pin(student_id: str) -> Account:
    _require_ops("catering PINs")
    st = _student(student_id)
    with _connect() as conn:
        _ensure_account(conn, st.student_id)
        conn.execute(
            "UPDATE catering_accounts SET pin_hash = NULL, pin_salt = NULL, "
            "pin_set_at = NULL, pin_failures = 0, pin_locked_until = NULL, "
            "updated_at = datetime('now') WHERE student_id = ?",
            (st.student_id,))
    out = get_account(st.student_id)
    assert out is not None
    return out


def _check_pin(student_id: str, pin: str) -> None:
    cfg = settings()
    now = _dt.datetime.now().isoformat(sep=" ", timespec="seconds")
    with _connect() as conn:
        r = conn.execute("SELECT * FROM catering_accounts WHERE student_id = ?",
                         (student_id,)).fetchone()
        if r is None or not r["pin_hash"]:
            raise ValidationError("No PIN is set for this learner — use their "
                                  "card or a staff lookup")
        if r["pin_locked_until"] and r["pin_locked_until"] > now:
            raise ValidationError(
                f"PIN locked after too many wrong tries until "
                f"{r['pin_locked_until'][11:16]} — use their card or a staff "
                "lookup")
        if secrets.compare_digest(_hash_pin((pin or "").strip(), r["pin_salt"]),
                                  r["pin_hash"]):
            conn.execute("UPDATE catering_accounts SET pin_failures = 0, "
                         "pin_locked_until = NULL WHERE student_id = ?",
                         (student_id,))
            return
        fails = int(r["pin_failures"] or 0) + 1
        locked = None
        if fails >= cfg["pin_max_failures"]:
            locked = (_dt.datetime.now() + _dt.timedelta(
                minutes=cfg["pin_lock_minutes"])).isoformat(
                sep=" ", timespec="seconds")
            fails = 0
        conn.execute("UPDATE catering_accounts SET pin_failures = ?, "
                     "pin_locked_until = ? WHERE student_id = ?",
                     (fails, locked, student_id))
    raise ValidationError("Wrong PIN")


# ── Identification at the till ──────────────────────────────────────

def identify(method: str, value: str, *, pin: str | None = None,
             purpose: str | None = None) -> Identification:
    """Work out who is at the till (OPERATIONS).

    * ``Card`` — *value* is the ID card number; the card must be the
      learner's Active, unexpired card.
    * ``PIN`` — *value* is the student id, *pin* their PIN.
    * ``Biometric`` — *value* is the student id the reader matched. Refused
      (``BiometricRefused``) unless there is current consent and no
      objection; the learner must then use a card or PIN.
    * ``Staff lookup`` — staff picked the learner by name (forgotten card).
    """
    _require_ops("the catering till")
    m = (method or "").strip()
    if m not in ID_METHODS:
        raise ValidationError(f"Identify by one of: {', '.join(ID_METHODS)}")
    v = (value or "").strip()
    if not v:
        raise ValidationError(
            "Card number is required" if m == ID_CARD else "Student is required")
    if m == ID_CARD:
        from education_system.systems.sixth_form.domains.operations.domain.id_cards import (
            id_cards as _ic,
        )
        card = _ic.get_card_by_number(v)
        if card is None:
            raise ValidationError(f"Card {v.upper()} is not recognised")
        if card.holder_type != "Student" or not card.student_id:
            raise ValidationError(f"Card {card.card_number} is a staff card")
        if card.status != _ic.ACTIVE:
            raise ValidationError(
                f"Card {card.card_number} is {card.status} — not accepted")
        if card.expires_on < _today():
            raise ValidationError(
                f"Card {card.card_number} expired on {card.expires_on}")
        st = _student(card.student_id)
        return Identification(st.student_id, st.full_name, m, card.card_number)
    st = _student(v)
    if m == ID_PIN:
        _check_pin(st.student_id, pin or "")
    elif m == ID_BIOMETRIC:
        from education_system.systems.sixth_form.domains.operations.domain.catering import (
            biometric_consent as _bc,
        )
        _bc.require_allowed(st.student_id, purpose or _bc.DEFAULT_PURPOSE,
                            context="catering till")
    return Identification(st.student_id, st.full_name, m)


# ── Free meals ──────────────────────────────────────────────────────

def free_meal_today(student_id: str, day: str | None = None
                    ) -> tuple[int, str]:
    """(allowance in pence still available today, explanation)."""
    from education_system.systems.sixth_form.domains.finance.domain.free_meals import (
        free_meals as _fm,
    )
    d = day or _today()
    ent = _fm.entitlement_on(student_id, d)
    if ent is None:
        return 0, ""
    if _dt.date.fromisoformat(d).weekday() >= 5:
        return 0, "Free meal entitlement (not on weekends)"
    used = [u for u in _fm.list_usage(student_id=student_id, date_from=d,
                                      date_to=d) if u.taken]
    if used:
        return 0, "Free meal already used today"
    pence = int(round(ent.daily_allowance * 100))
    return pence, f"Free meal available ({money(pence)})"


# ── Purchases ───────────────────────────────────────────────────────

def purchase(student_id: str, amount: Any, *, id_method: str,
             items: str | None = None, till: str | None = None,
             use_free_meal: bool = True,
             card_number: str | None = None) -> Transaction:
    """Charge a sale at the till (OPERATIONS).

    The free-meal allowance (if the learner is entitled today and has
    not used it) pays first, logged through ``free_meals.record_usage``;
    the rest comes off the balance, which may not go below zero.
    """
    _require_ops("the catering till")
    init_db()
    m = (id_method or "").strip()
    if m not in ID_METHODS:
        raise ValidationError(f"Identify by one of: {', '.join(ID_METHODS)}")
    st = _student(student_id)
    if m == ID_BIOMETRIC:
        # Belt and braces: never accept a biometric sale without consent,
        # whichever screen called us.
        from education_system.systems.sixth_form.domains.operations.domain.catering import (
            biometric_consent as _bc,
        )
        _bc.require_allowed(st.student_id, _bc.DEFAULT_PURPOSE,
                            context="catering purchase")
    acct = get_account(st.student_id)
    if acct is not None and not acct.is_open:
        raise ValidationError(f"{st.full_name}'s catering account is closed")
    gross = to_pence(amount, "Sale total")
    free = 0
    if use_free_meal:
        allowance, _why = free_meal_today(st.student_id)
        free = min(allowance, gross)
    charge = gross - free
    with _connect() as conn:
        _ensure_account(conn, st.student_id)
        bal = _balance(conn, st.student_id)
    if charge > bal:
        raise InsufficientFunds(
            f"{st.full_name} has {money(bal)}; this sale needs "
            f"{money(charge)}"
            + (f" after the {money(free)} free meal" if free else "")
            + ". Top up first.")
    usage_id = None
    if free:
        from education_system.systems.sixth_form.domains.finance.domain.free_meals import (
            free_meals as _fm,
        )
        try:
            usage = _fm.record_usage(st.student_id, _today(), taken=True,
                                     recorded_by=_actor(),
                                     note=f"Till {till or ''}".strip())
            usage_id = usage.usage_id
        except _fm.ValidationError as e:
            raise ValidationError(f"Free meal not recorded: {e}") from None
    with _connect() as conn:
        tid = _insert(conn, student_id=st.student_id, txn_type=PURCHASE,
                      amount_pence=-charge, gross_pence=gross,
                      free_meal_pence=free, method="Account",
                      id_method=m, till=_text(till), items=_text(items),
                      reference=_text(card_number),
                      free_meal_usage_id=usage_id)
    logger.info("Till sale #%d: %s %s (free %s, id %s)", tid,
                st.student_id, money(gross), money(free), m)
    out = get_transaction(tid)
    assert out is not None
    return out


def void_transaction(txn_id: int, *, reason: str) -> Transaction:
    """Reverse a till sale or a cash top-up taken in error (OPERATIONS).

    Online and bursary top-ups are not voided here — refund them through
    Online Payments / Bursaries so the money trail stays complete.
    """
    _require_ops("voiding catering transactions")
    why = (reason or "").strip()
    if not why:
        raise ValidationError("A reason is required")
    t = get_transaction(int(txn_id))
    if t is None:
        raise ValidationError(f"No catering transaction #{txn_id}")
    if t.voided:
        raise ValidationError(f"Transaction #{t.txn_id} is already voided")
    if t.txn_type == TOPUP and t.method != "Cash":
        raise ValidationError(
            f"{t.method} top-ups are refunded through "
            + ("Online Payments" if t.method == "Online" else "Bursaries"))
    if t.txn_type not in (PURCHASE, TOPUP):
        raise ValidationError(f"A {t.txn_type} cannot be voided")
    with _connect() as conn:
        if t.txn_type == TOPUP and _balance(conn, t.student_id) < t.amount_pence:
            raise InsufficientFunds(
                "Part of this top-up has been spent; it cannot be voided")
        try:
            tid = _insert(conn, student_id=t.student_id, txn_type=VOID,
                          amount_pence=-t.amount_pence,
                          gross_pence=-t.gross_pence,
                          free_meal_pence=-t.free_meal_pence,
                          method=t.method, till=t.till,
                          reverses_txn_id=t.txn_id, note=why)
        except _sql.IntegrityError:
            raise ValidationError(
                f"Transaction #{t.txn_id} is already voided") from None
    if t.free_meal_pence and t.free_meal_usage_id:
        from education_system.systems.sixth_form.domains.finance.domain.free_meals import (
            free_meals as _fm,
        )
        try:
            _fm.record_usage(t.student_id, t.at[:10], taken=False,
                             recorded_by=_actor(),
                             note=f"Till sale #{t.txn_id} voided: {why}")
        except _fm.ValidationError as e:
            logger.warning("Free meal for voided sale #%d not reversed: %s",
                           t.txn_id, e)
    if t.receipt_id:
        from education_system.systems.sixth_form.domains.finance.domain.receipts import (
            receipts as _rc,
        )
        try:
            _rc.void_receipt(t.receipt_id, f"Catering top-up voided: {why}")
        except ValueError as e:
            logger.warning("Receipt for voided top-up #%d: %s", t.txn_id, e)
    out = get_transaction(tid)
    assert out is not None
    return out


# ── Refunds and leavers (FINANCE) ───────────────────────────────────

def refund_balance(student_id: str, *, method: str, reason: str,
                   reference: str | None = None,
                   close: bool = False) -> Transaction | None:
    """Pay a learner's whole balance back to them (FINANCE).

    ``close`` closes the account afterwards (leaving college). Returns
    the refund transaction, or ``None`` if there was nothing to refund
    (the account is still closed when asked).
    """
    _require("FINANCE", "refunding catering balances")
    init_db()
    st = _student(student_id)
    m = (method or "").strip()
    if m not in REFUND_METHODS:
        raise ValidationError(
            f"Refund method must be one of: {', '.join(REFUND_METHODS)}")
    why = (reason or "").strip()
    if not why:
        raise ValidationError("A reason is required")
    ref = _text(reference)
    if m in ("Bank Transfer", "Cheque") and not ref:
        raise ValidationError(f"A reference is required for {m} refunds")
    tid = None
    with _connect() as conn:
        _ensure_account(conn, st.student_id)
        bal = _balance(conn, st.student_id)
        if bal > 0:
            tid = _insert(conn, student_id=st.student_id, txn_type=REFUND,
                          amount_pence=-bal, method=m, reference=ref,
                          note=why)
        if close:
            conn.execute(
                "UPDATE catering_accounts SET status = 'Closed', "
                "closed_on = date('now', 'localtime'), closed_reason = ?, "
                "updated_at = datetime('now') WHERE student_id = ?",
                (why, st.student_id))
    logger.info("Catering balance refund for %s: %s (%s)%s", st.student_id,
                money(bal), m, " — account closed" if close else "")
    return get_transaction(tid) if tid else None


def refund_on_leaving(student_id: str, *, method: str,
                      reference: str | None = None) -> Transaction | None:
    return refund_balance(student_id, method=method, reference=reference,
                          reason="Left college", close=True)


def leavers_with_balance() -> list[AccountView]:
    """Learners who have left with money still on (or an open account)."""
    _require_ops_or_finance("catering accounts")
    return [v for v in list_accounts(include_left=True)
            if v.student_status == "Left"
            and (v.balance_pence > 0 or v.account_status == OPEN)]


# ── Lists and reports ───────────────────────────────────────────────

def list_accounts(*, search: str | None = None, low_only: bool = False,
                  include_left: bool = False,
                  with_account_only: bool = False) -> list[AccountView]:
    """Every learner with their catering position (OPERATIONS/FINANCE)."""
    _require_ops_or_finance("catering accounts")
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domains.operations.domain.catering import (
        biometric_consent as _bc,
    )
    cfg = settings()
    with _connect() as conn:
        accts = {r["student_id"]: _account(r) for r in conn.execute(
            "SELECT * FROM catering_accounts")}
        bals = {r["student_id"]: int(r["b"]) for r in conn.execute(
            "SELECT student_id, SUM(amount_pence) AS b, MAX(at) AS last "
            "FROM catering_transactions GROUP BY student_id")}
        last = {r["student_id"]: r["last"] for r in conn.execute(
            "SELECT student_id, MAX(at) AS last FROM catering_transactions "
            "GROUP BY student_id")}
        cards: dict[str, str] = {}
        try:
            cards = {r["student_id"]: r["card_number"] for r in conn.execute(
                "SELECT student_id, card_number FROM id_cards WHERE status = "
                "'Active' AND student_id IS NOT NULL")}
        except _sql.OperationalError:
            cards = {}
    bio = _bc.allowed_map()
    q = (search or "").strip().lower()
    out: list[AccountView] = []
    for s in _students.list_students():
        acct = accts.get(s.student_id)
        if with_account_only and acct is None:
            continue
        if not include_left and s.status == "Left" and \
                bals.get(s.student_id, 0) == 0:
            continue
        if q and q not in s.student_id.lower() and q not in s.full_name.lower():
            continue
        thr = (acct.low_balance_pence if acct and acct.low_balance_pence
               is not None else cfg["low_balance_pence"])
        v = AccountView(
            student_id=s.student_id, student_name=s.full_name,
            student_status=s.status,
            account_status=acct.status if acct else "No account",
            balance_pence=bals.get(s.student_id, 0), threshold_pence=thr,
            has_pin=bool(acct and acct.has_pin),
            card_number=cards.get(s.student_id),
            biometric=bio.get(s.student_id, "No consent"),
            free_meal_today="", last_activity=last.get(s.student_id))
        if low_only and not (acct is not None and v.is_low
                             and s.status != "Left"):
            continue
        out.append(v)
    return out


def account_view(student_id: str) -> AccountView:
    _require_ops_or_finance("catering accounts")
    st = _student(student_id)
    rows = [v for v in list_accounts(search=st.student_id, include_left=True)
            if v.student_id == st.student_id]
    v = rows[0]
    v.free_meal_today = free_meal_today(st.student_id)[1]
    return v


def low_balance_list() -> list[AccountView]:
    """Open accounts of learners on roll below their threshold."""
    return list_accounts(low_only=True)


def list_transactions(*, student_id: str | None = None,
                      date_from: str | None = None, date_to: str | None = None,
                      txn_type: str | None = None, till: str | None = None,
                      limit: int | None = None) -> list[Transaction]:
    _require_ops_or_finance("catering transactions")
    return _transactions(student_id=student_id, date_from=date_from,
                         date_to=date_to, txn_type=txn_type, till=till,
                         limit=limit)


def _transactions(*, student_id: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  txn_type: str | None = None, till: str | None = None,
                  limit: int | None = None) -> list[Transaction]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("t.student_id = ?")
        args.append(student_id.strip())
    if date_from:
        clauses.append("date(t.at) >= ?")
        args.append(date_from)
    if date_to:
        clauses.append("date(t.at) <= ?")
        args.append(date_to)
    if txn_type:
        if txn_type not in TXN_TYPES:
            raise ValidationError(
                f"Type must be one of: {', '.join(TXN_TYPES)}")
        clauses.append("t.txn_type = ?")
        args.append(txn_type)
    if till:
        clauses.append("t.till = ?")
        args.append(till)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    lim = ""
    if limit:
        lim = f" LIMIT {int(limit)}"
    with _connect() as conn:
        # db-audit: ignore[DBW001] - where joins fixed clause literals; lim is an int
        rows = conn.execute(
            f"{_TXN_SELECT} {where} ORDER BY t.txn_id DESC{lim}",
            args).fetchall()
    return [_txn(r) for r in rows]


def statement_for_payer(payer_kind: str, payer_id: Any, student_id: str,
                        *, limit: int = 100) -> tuple[int, list[Transaction]]:
    """(balance, recent transactions) for a parent's linked child or the
    signed-in student — checked through ``online_payments.resolve_payer``."""
    from education_system.systems.sixth_form.domains.finance.domain.online_payments import (
        online_payments as _op,
    )
    payer = _op.resolve_payer(payer_kind, payer_id)
    sid = (student_id or "").strip()
    if payer.kind != _op.PAYER_STAFF and sid not in payer.student_ids:
        raise _access().AccessDenied("That student is not linked to you.")
    return balance_pence(sid), _transactions(student_id=sid, limit=limit)


def till_report(day: str | None = None) -> TillReport:
    _require_ops_or_finance("till reports")
    d = day or _today()
    try:
        _dt.date.fromisoformat(d)
    except ValueError:
        raise ValidationError("Day must be YYYY-MM-DD") from None
    rep = TillReport(day=d, topups_by_method={m: 0 for m in TOPUP_METHODS},
                     by_id_method={m: 0 for m in ID_METHODS})
    for t in _transactions(date_from=d, date_to=d):
        if t.txn_type == PURCHASE and not t.voided:
            rep.purchases += 1
            rep.gross_pence += t.gross_pence
            rep.free_meal_pence += t.free_meal_pence
            rep.charged_pence += -t.amount_pence
            rep.free_meals += 1 if t.free_meal_pence else 0
            if t.id_method:
                rep.by_id_method[t.id_method] = \
                    rep.by_id_method.get(t.id_method, 0) + 1
            key = t.till or "(no till)"
            rep.by_till[key] = rep.by_till.get(key, 0) + t.gross_pence
        elif t.txn_type == TOPUP and not t.voided:
            rep.topups_by_method[t.method or "Other"] = \
                rep.topups_by_method.get(t.method or "Other", 0) + t.amount_pence
            if t.method == "Cash":
                rep.cash_taken_pence += t.amount_pence
        elif t.txn_type == REFUND:
            rep.refunds_pence += -t.amount_pence
        elif t.txn_type == VOID:
            rep.voids += 1
    return rep


def summary() -> CashlessSummary:
    views = list_accounts(include_left=True)
    s = CashlessSummary()
    for v in views:
        if v.account_status == "No account":
            continue
        s.accounts += 1
        s.open_accounts += 1 if v.account_status == OPEN else 0
        s.total_balance_pence += v.balance_pence
        s.with_pin += 1 if v.has_pin else 0
        if v.is_low and v.student_status != "Left":
            s.low_balance += 1
        if v.student_status == "Left" and v.balance_pence > 0:
            s.leavers_owed += 1
            s.leavers_owed_pence += v.balance_pence
    s.today = till_report()
    return s
