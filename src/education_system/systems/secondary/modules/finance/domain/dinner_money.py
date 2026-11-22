"""Dinner Money: school meal accounts, the meal register and the till.

There was no dinner money in the old Secondary system; this is new.

* **Accounts.** Every pupil has a meal account; its balance is the sum of
  its ledger lines (whole pence, never floats). Lines are top-ups (amount,
  method - cash, cheque, card, online, bank transfer - date, reference),
  meal charges, refunds, adjustments, write-offs and the year-end carry
  forward. A mistaken line is voided (kept, with the reason), never deleted.
* **Prices.** Each meal type has a price set by :data:`DINNER_MONEY_EDITORS`
  and says whether free school meals cover it (lunch does).
* **Register.** Staff tick who had a meal each day (:func:`save_register`);
  the office charges the day's register in one go (:func:`charge_register`),
  or a single meal at the till (:func:`record_meal`). A pupil is never
  refused a meal for a low balance; the account just goes overdrawn.
* **Free school meals.** The FSM flag on the pupil record
  (``pupils.fsm_eligible``) is used, not a copy: an FSM pupil's covered meals
  are recorded on the register at no charge.
* **Dietary needs and allergies.** Dietary needs are recorded here; food
  allergies come from the medical record (Medical) and are joined with any
  note kept here, so the register shows one list and the kitchen never
  works from a second, older copy.
* **Arrears and alerts.** :func:`arrears` and :func:`low_balance`, with
  debt letters and low-balance e-mails through the outbox (not more than one
  of each kind a week unless asked for).
* **Statements** per pupil with a running balance, e-mailed on request.
* **Year end.** :func:`year_end` carries every balance into the next school
  year (two lines that net to zero); leavers' credit is refunded and debt
  written off.
* **Cash-up.** :func:`cash_up` - the day's takings by method and by who took
  them, meals served and FSM meals; :func:`takings` over a range.
* **CSV export** of balances or the ledger.

Every change is in ``dinner_audit`` and the activity log (ids only, never
amounts or names).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.trips.domain.trips import money, pence, plain
from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import (
    DINNER_MONEY_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import current_year, next_year
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

MEAL_TYPES: tuple[str, ...] = ("Lunch", "Breakfast", "Snack", "Packed lunch")
DEFAULT_MEAL = "Lunch"
METHODS: tuple[str, ...] = ("Cash", "Cheque", "Card", "Online", "Bank transfer")
DEFAULT_METHOD = "Cash"
_NEEDS_REFERENCE = frozenset({"Cheque", "Online", "Bank transfer"})
TOP_UP = "Top-up"
MEAL = "Meal"
REFUND = "Refund"
ADJUSTMENT = "Adjustment"
WRITE_OFF = "Write-off"
CARRIED_OUT = "Carried forward"
CARRIED_IN = "Brought forward"
KINDS: tuple[str, ...] = (TOP_UP, MEAL, REFUND, ADJUSTMENT, WRITE_OFF, CARRIED_OUT, CARRIED_IN)
#: Lines that are money changing hands (they go in the cash-up).
CASH_KINDS = frozenset({TOP_UP, REFUND})
DEFAULT_LOW_BALANCE = 500           # pence
LETTER_GAP_DAYS = 7
LETTER_KINDS = ("debt", "low_balance", "statement")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dinner_prices (
    meal_type    TEXT PRIMARY KEY,
    price_pence  INTEGER NOT NULL CHECK (price_pence >= 0),
    fsm_covered  INTEGER NOT NULL DEFAULT 0 CHECK (fsm_covered IN (0, 1)),
    active       INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    updated_by   TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS dinner_transactions (
    txn_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id      INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    txn_date      TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('Top-up', 'Meal', 'Refund', 'Adjustment',
                  'Write-off', 'Carried forward', 'Brought forward')),
    amount_pence  INTEGER NOT NULL CHECK (amount_pence != 0),
    meal_type     TEXT,
    method        TEXT,
    reference     TEXT,
    notes         TEXT,
    voided        INTEGER NOT NULL DEFAULT 0 CHECK (voided IN (0, 1)),
    void_reason   TEXT,
    voided_by     TEXT,
    voided_at     TEXT,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_dinner_txn_pupil ON dinner_transactions (pupil_id, txn_date);
CREATE INDEX IF NOT EXISTS ix_dinner_txn_date ON dinner_transactions (txn_date, kind);
CREATE TABLE IF NOT EXISTS dinner_meals (
    meal_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id     INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    meal_date    TEXT NOT NULL,
    meal_type    TEXT NOT NULL,
    price_pence  INTEGER NOT NULL DEFAULT 0 CHECK (price_pence >= 0),
    fsm          INTEGER NOT NULL DEFAULT 0 CHECK (fsm IN (0, 1)),
    charged      INTEGER NOT NULL DEFAULT 0 CHECK (charged IN (0, 1)),
    txn_id       INTEGER REFERENCES dinner_transactions (txn_id) ON DELETE SET NULL,
    recorded_by  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (pupil_id, meal_date, meal_type)
);
CREATE INDEX IF NOT EXISTS ix_dinner_meals_day ON dinner_meals (meal_date, meal_type);
CREATE TABLE IF NOT EXISTS dinner_needs (
    pupil_id    INTEGER PRIMARY KEY REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    dietary     TEXT,
    allergies   TEXT,
    notes       TEXT,
    updated_by  TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS dinner_settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dinner_letters (
    letter_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    kind           TEXT NOT NULL,
    balance_pence  INTEGER NOT NULL,
    message_id     INTEGER,
    sent_by        TEXT,
    sent_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_dinner_letters_pupil ON dinner_letters (pupil_id, kind, sent_at);
CREATE TABLE IF NOT EXISTS dinner_year_ends (
    academic_year  TEXT PRIMARY KEY,
    closed_on      TEXT NOT NULL,
    closed_by      TEXT,
    pupils         INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS dinner_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("dinner_money", _SCHEMA)


@dataclass(frozen=True)
class Price:
    meal_type: str
    price_pence: int
    fsm_covered: int
    active: int
    updated_by: str | None
    updated_at: str


@dataclass(frozen=True)
class Txn:
    txn_id: int
    pupil_id: int
    txn_date: str
    kind: str
    amount_pence: int
    meal_type: str | None
    method: str | None
    reference: str | None
    notes: str | None
    voided: int
    void_reason: str | None
    voided_by: str | None
    voided_at: str | None
    created_by: str | None
    created_at: str
    pupil_name: str = ""
    admission_no: str = ""

    @property
    def counts(self) -> int:
        return 0 if self.voided else self.amount_pence


@dataclass(frozen=True)
class Account:
    pupil_id: int
    pupil_name: str
    admission_no: str
    year_group: int
    form_group: str | None
    roll_status: str
    fsm: bool
    balance_pence: int
    last_top_up: str | None
    dietary: str | None
    allergies: str | None
    used: bool = False   # any (non-voided) top-up, meal or adjustment ever

    @property
    def needs_flag(self) -> str:
        bits = []
        if self.allergies:
            bits.append(f"ALLERGY: {self.allergies}")
        if self.dietary:
            bits.append(self.dietary)
        return "; ".join(bits)


@dataclass(frozen=True)
class RegisterRow:
    pupil_id: int
    pupil_name: str
    admission_no: str
    year_group: int
    form_group: str | None
    fsm: bool
    had_meal: bool
    charged: bool
    price_pence: int
    balance_pence: int
    needs: str


_NAME = "p.legal_last_name || ', ' || COALESCE(p.preferred_name, p.legal_first_name)"
_ACCOUNT_SELECT = f"""
SELECT p.pupil_id, {_NAME} AS pupil_name, p.admission_no, p.year_group, p.form_group,
       p.roll_status, p.fsm_eligible,
       COALESCE((SELECT SUM(t.amount_pence) FROM dinner_transactions t
                 WHERE t.pupil_id = p.pupil_id AND t.voided = 0), 0) AS balance_pence,
       (SELECT MAX(t.txn_date) FROM dinner_transactions t WHERE t.pupil_id = p.pupil_id
          AND t.kind = 'Top-up' AND t.voided = 0) AS last_top_up,
       EXISTS (SELECT 1 FROM dinner_transactions t WHERE t.pupil_id = p.pupil_id
               AND t.voided = 0) AS used,
       n.dietary, n.allergies
FROM pupils p LEFT JOIN dinner_needs n USING (pupil_id)
"""


def _account(r) -> Account:
    return Account(pupil_id=r["pupil_id"], pupil_name=r["pupil_name"],
                   admission_no=r["admission_no"], year_group=r["year_group"],
                   form_group=r["form_group"], roll_status=r["roll_status"],
                   fsm=bool(r["fsm_eligible"]), balance_pence=r["balance_pence"],
                   last_top_up=r["last_top_up"], dietary=r["dietary"],
                   allergies=r["allergies"], used=bool(r["used"]))


def _txn(r) -> Txn:
    base = {k: r[k] for k in Txn.__dataclass_fields__ if k not in ("pupil_name",
                                                                    "admission_no")}
    keys = r.keys()
    return Txn(**base, pupil_name=r["pupil_name"] if "pupil_name" in keys else "",
               admission_no=r["admission_no"] if "admission_no" in keys else "")


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in DINNER_MONEY_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"dinner_money.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see meal accounts.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the finance office can handle dinner money.")


def _audit(conn, action: str, actor: Principal, *, pupil_id: int | None = None,
           **detail: Any) -> None:
    conn.execute("INSERT INTO dinner_audit (pupil_id, action, detail, actor) VALUES (?, ?, ?, ?)",
                 (pupil_id, action, json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(pupil_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM dinner_audit", []
    if pupil_id is not None:
        sql += " WHERE pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        return [{"at": r["at"], "pupil_id": r["pupil_id"], "action": r["action"],
                 "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Cleaning ─────────────────────────────────────────────────────────

def _date(value: Any, label: str, problems: list[str], *, future_ok: bool = False
          ) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        d = _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None
    if not future_ok and d > _today().isoformat():
        problems.append(f"{label} can't be in the future")
    return d


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str | None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def _text(value: Any, limit: int) -> str | None:
    return (str(value or "").strip()[:limit]) or None


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


def _must_pupil(ref: Any) -> P.Pupil:
    p = _pupil(ref)
    if p is None:
        raise NotFound(f"No pupil {ref}" if ref not in (None, "") else "Choose a pupil")
    return p


# ── Settings and prices ──────────────────────────────────────────────

def low_balance_threshold() -> int:
    with database.connect() as conn:
        r = conn.execute("SELECT value FROM dinner_settings WHERE key = 'low_balance'"
                         ).fetchone()
    return int(r["value"]) if r else DEFAULT_LOW_BALANCE


def set_low_balance_threshold(amount: Any, *, actor: Principal) -> int:
    _require_editor(actor, "settings")
    n = pence(amount, "Low-balance level")
    with database.connect() as conn:
        conn.execute("INSERT INTO dinner_settings (key, value) VALUES ('low_balance', ?) "
                     "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (str(n),))
        _audit(conn, "settings", actor, low_balance=n)
    activity_log.record("dinner_money.settings", principal=actor)
    return int(n or 0)


def list_prices(*, active_only: bool = False) -> list[Price]:
    with database.connect() as conn:
        rows = [Price(**dict(r)) for r in conn.execute(
            "SELECT * FROM dinner_prices" + (" WHERE active = 1" if active_only else "")
            + " ORDER BY meal_type")]
    order = {m: i for i, m in enumerate(MEAL_TYPES)}
    return sorted(rows, key=lambda x: (order.get(x.meal_type, 99), x.meal_type))


def get_price(meal_type: str) -> Price | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM dinner_prices WHERE meal_type = ?",
                         (meal_type,)).fetchone()
    return Price(**dict(r)) if r else None


def set_price(meal_type: str, price: Any, *, actor: Principal, fsm_covered: bool | None = None,
              active: bool = True) -> Price:
    """Set a meal type's price (finance office). Lunch is covered by free
    school meals unless told otherwise."""
    _require_editor(actor, "price")
    problems: list[str] = []
    name = " ".join(str(meal_type or "").split())[:40]
    if not name:
        problems.append("Meal type is required")
    n = pence(price, "Price", problems, required=True)
    if problems:
        raise ValidationError(problems)
    covered = (name.lower() == "lunch") if fsm_covered is None else bool(fsm_covered)
    with database.connect() as conn:
        conn.execute("INSERT INTO dinner_prices (meal_type, price_pence, fsm_covered, active, "
                     "updated_by) VALUES (?, ?, ?, ?, ?) ON CONFLICT (meal_type) DO UPDATE SET "
                     "price_pence = excluded.price_pence, fsm_covered = excluded.fsm_covered, "
                     "active = excluded.active, updated_by = excluded.updated_by, "
                     "updated_at = datetime('now')",
                     (name, n, int(covered), int(bool(active)), actor.username))
        _audit(conn, "price", actor, meal_type=name)
    activity_log.record("dinner_money.price", principal=actor)
    return get_price(name)


def _price_or_fail(meal_type: str) -> Price:
    pr = get_price(meal_type)
    if pr is None or not pr.active:
        raise ValidationError([f"Set the price of {meal_type} first (Prices)"])
    return pr


# ── Dietary needs ────────────────────────────────────────────────────

def get_needs(pupil_id: int) -> dict[str, str | None]:
    with database.connect() as conn:
        r = conn.execute("SELECT dietary, allergies, notes FROM dinner_needs WHERE pupil_id = ?",
                         (int(pupil_id),)).fetchone()
    return dict(r) if r else {"dietary": None, "allergies": None, "notes": None}


def set_needs(pupil_id: Any, *, actor: Principal, dietary: str | None = None,
              allergies: str | None = None, notes: str | None = None) -> dict[str, str | None]:
    """Dietary requirements and allergies shown on the register."""
    _require_editor(actor, "needs")
    p = _must_pupil(pupil_id)
    vals = (_text(dietary, 200), _text(allergies, 300), _text(notes, 500))
    with database.connect() as conn:
        if not any(vals):
            conn.execute("DELETE FROM dinner_needs WHERE pupil_id = ?", (p.pupil_id,))
        else:
            conn.execute("INSERT INTO dinner_needs (pupil_id, dietary, allergies, notes, "
                         "updated_by) VALUES (?, ?, ?, ?, ?) ON CONFLICT (pupil_id) DO UPDATE "
                         "SET dietary = excluded.dietary, allergies = excluded.allergies, "
                         "notes = excluded.notes, updated_by = excluded.updated_by, "
                         "updated_at = datetime('now')", (p.pupil_id, *vals, actor.username))
        _audit(conn, "needs", actor, pupil_id=p.pupil_id)
    activity_log.record("dinner_money.needs", target=p.admission_no, principal=actor)
    return get_needs(p.pupil_id)


# ── Accounts ─────────────────────────────────────────────────────────

def balance(pupil_id: int) -> int:
    with database.connect() as conn:
        return int(conn.execute("SELECT COALESCE(SUM(amount_pence), 0) FROM dinner_transactions "
                                "WHERE pupil_id = ? AND voided = 0",
                                (int(pupil_id),)).fetchone()[0])


def _medical_allergies(pupil_id: int | None = None) -> dict[int, list[str]]:
    """pupil id -> active food / other allergies from the medical record
    (with ANAPHYLAXIS marked), the one store for allergies."""
    try:
        from education_system.systems.secondary.modules.medical.domain import medical as M
        rows = M.list_allergies(pupil_id=pupil_id)
    except Exception:  # noqa: BLE001 - no medical data yet: this module's notes only
        logger.exception("Medical allergies could not be read for dinner money")
        return {}
    out: dict[int, list[str]] = {}
    for a in rows:
        if a.kind not in ("Food", "Other"):
            continue
        out.setdefault(a.pupil_id, []).append(
            a.allergen + (" (ANAPHYLAXIS)" if a.anaphylaxis else ""))
    return out


def _with_medical(rows: list[Account], pupil_id: int | None = None) -> list[Account]:
    med = _medical_allergies(pupil_id)
    out = []
    for a in rows:
        found = med.get(a.pupil_id)
        if found:
            extra = a.allergies if a.allergies and not any(
                a.allergies.lower() in x.lower() for x in found) else None
            a = replace(a, allergies="; ".join([*found, *([extra] if extra else [])]))
        out.append(a)
    return out


def account(pupil_id: Any) -> Account:
    p = _must_pupil(pupil_id)
    with database.connect() as conn:
        a = _account(conn.execute(_ACCOUNT_SELECT + " WHERE p.pupil_id = ?",
                                  (p.pupil_id,)).fetchone())
    return _with_medical([a], p.pupil_id)[0]


def accounts(*, year_group: int | str | None = None, form_group: str | None = None,
             search: str | None = None, roll_status: str | None = "on_roll",
             fsm: bool | None = None, nonzero: bool = False) -> list[Account]:
    """Every pupil's meal account (the Accounts tab)."""
    where, params = [], []
    if roll_status:
        where.append("p.roll_status = ?")
        params.append(roll_status)
    if year_group not in (None, ""):
        where.append("p.year_group = ?")
        params.append(int(year_group))
    if form_group:
        where.append("upper(p.form_group) = upper(?)")
        params.append(form_group.strip())
    if fsm is not None:
        where.append("p.fsm_eligible = ?")
        params.append(int(fsm))
    for term in (search or "").split():
        where.append("(p.legal_first_name LIKE ? OR p.legal_last_name LIKE ? OR "
                     "p.preferred_name LIKE ? OR p.admission_no LIKE ?)")
        params += [f"%{term}%"] * 4
    sql = _ACCOUNT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY p.legal_last_name COLLATE NOCASE, p.legal_first_name COLLATE NOCASE"
    with database.connect() as conn:
        rows = [_account(r) for r in conn.execute(sql, params)]
    rows = _with_medical(rows)
    return [a for a in rows if a.balance_pence] if nonzero else rows


def transactions(*, pupil_id: int | None = None, date_from: str | None = None,
                 date_to: str | None = None, kind: str | None = None,
                 method: str | None = None, include_voided: bool = True,
                 limit: int = 5000) -> list[Txn]:
    where, params = [], []
    for col, val in (("t.pupil_id", pupil_id), ("t.kind", kind), ("t.method", method)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if date_from:
        where.append("t.txn_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.txn_date <= ?")
        params.append(date_to)
    if not include_voided:
        where.append("t.voided = 0")
    sql = (f"SELECT t.*, {_NAME} AS pupil_name, p.admission_no FROM dinner_transactions t "
           "JOIN pupils p USING (pupil_id)" + (" WHERE " + " AND ".join(where) if where else "")
           + " ORDER BY t.txn_date DESC, t.txn_id DESC LIMIT ?")
    with database.connect() as conn:
        return [_txn(r) for r in conn.execute(sql, (*params, int(limit)))]


def get_txn(txn_id: int) -> Txn:
    with database.connect() as conn:
        r = conn.execute(f"SELECT t.*, {_NAME} AS pupil_name, p.admission_no FROM "
                         "dinner_transactions t JOIN pupils p USING (pupil_id) WHERE "
                         "t.txn_id = ?", (int(txn_id),)).fetchone()
    if r is None:
        raise NotFound(f"No transaction #{txn_id}")
    return _txn(r)


def _insert(conn, pupil_id: int, kind: str, amount: int, actor: Principal, *, day: str,
            meal_type: str | None = None, method: str | None = None,
            reference: str | None = None, notes: str | None = None) -> int:
    return conn.execute(
        "INSERT INTO dinner_transactions (pupil_id, txn_date, kind, amount_pence, meal_type, "
        "method, reference, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (pupil_id, day, kind, amount, meal_type, method, reference, notes,
         actor.username)).lastrowid


def top_up(pupil_id: Any, amount: Any, *, actor: Principal, method: str = DEFAULT_METHOD,
           day: str | None = None, reference: str | None = None,
           notes: str | None = None) -> Txn:
    """Money paid into a pupil's meal account."""
    _require_editor(actor, "top_up")
    p = _must_pupil(pupil_id)
    problems: list[str] = []
    n = pence(amount, "Amount", problems, required=True, allow_zero=False)
    m = _choice(method, METHODS, "Method", problems, DEFAULT_METHOD)
    d = _date(day, "Date", problems) or _today().isoformat()
    ref = _text(reference, 120)
    if m in _NEEDS_REFERENCE and not ref:
        problems.append(f"A {m.lower()} payment needs its reference")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        tid = _insert(conn, p.pupil_id, TOP_UP, n, actor, day=d, method=m, reference=ref,
                      notes=_text(notes, 500))
        _audit(conn, "top_up", actor, pupil_id=p.pupil_id, txn=tid)
    activity_log.record("dinner_money.top_up", target=p.admission_no, principal=actor, txn=tid)
    return get_txn(tid)


def adjust(pupil_id: Any, amount: Any, *, actor: Principal, reason: str,
           day: str | None = None) -> Txn:
    """A correction: *amount* may be negative ("-1.20") to take money off."""
    _require_editor(actor, "adjust")
    p = _must_pupil(pupil_id)
    problems: list[str] = []
    text = str(amount or "").strip()
    neg = text.startswith("-")
    n = pence(text.lstrip("-"), "Amount", problems, required=True, allow_zero=False)
    why = _text(reason, 300)
    if not why:
        problems.append("Say why the account is adjusted")
    d = _date(day, "Date", problems) or _today().isoformat()
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        tid = _insert(conn, p.pupil_id, ADJUSTMENT, -n if neg else n, actor, day=d, notes=why)
        _audit(conn, "adjust", actor, pupil_id=p.pupil_id, txn=tid)
    activity_log.record("dinner_money.adjust", target=p.admission_no, principal=actor, txn=tid)
    return get_txn(tid)


def void(txn_id: int, *, actor: Principal, reason: str) -> Txn:
    """Cancel a mistaken line (it stays on record). Voiding a meal charge
    leaves the meal on the register, uncharged."""
    t = get_txn(txn_id)
    _require_editor(actor, "void", t.admission_no)
    why = _text(reason, 300)
    problems = []
    if t.voided:
        problems.append("Already voided")
    if not why:
        problems.append("Say why the line is voided")
    if t.kind in (CARRIED_OUT, CARRIED_IN):
        problems.append("A year-end line can't be voided")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE dinner_transactions SET voided = 1, void_reason = ?, voided_by = ?, "
                     "voided_at = datetime('now') WHERE txn_id = ?",
                     (why, actor.username, t.txn_id))
        conn.execute("UPDATE dinner_meals SET charged = 0, txn_id = NULL WHERE txn_id = ?",
                     (t.txn_id,))
        _audit(conn, "void", actor, pupil_id=t.pupil_id, txn=t.txn_id)
    activity_log.record("dinner_money.void", target=t.admission_no, principal=actor,
                        txn=t.txn_id)
    return get_txn(t.txn_id)


def refund_balance(pupil_id: Any, *, actor: Principal, method: str = DEFAULT_METHOD,
                   reference: str | None = None, notes: str | None = None,
                   amount: Any = None) -> Txn:
    """Pay credit back to the family (a leaver, or on request)."""
    _require_editor(actor, "refund")
    p = _must_pupil(pupil_id)
    bal = balance(p.pupil_id)
    problems: list[str] = []
    n = pence(amount, "Amount", problems) if amount not in (None, "") else bal
    m = _choice(method, METHODS, "Method", problems, DEFAULT_METHOD)
    if bal <= 0:
        problems.append("The account isn't in credit")
    elif n is not None and (n <= 0 or n > bal):
        problems.append(f"Refund up to the balance ({money(bal)})")
    if m in _NEEDS_REFERENCE and not _text(reference, 120):
        problems.append(f"A {m.lower()} refund needs its reference")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        tid = _insert(conn, p.pupil_id, REFUND, -n, actor, day=_today().isoformat(), method=m,
                      reference=_text(reference, 120),
                      notes=_text(notes, 500) or ("Leaving" if p.roll_status == "left"
                                                  else None))
        _audit(conn, "refund", actor, pupil_id=p.pupil_id, txn=tid)
    activity_log.record("dinner_money.refund", target=p.admission_no, principal=actor, txn=tid)
    return get_txn(tid)


def write_off(pupil_id: Any, *, actor: Principal, reason: str) -> Txn:
    """Clear a debt that won't be paid (usually a leaver)."""
    _require_editor(actor, "write_off")
    p = _must_pupil(pupil_id)
    bal = balance(p.pupil_id)
    problems = []
    if bal >= 0:
        problems.append("The account isn't overdrawn")
    why = _text(reason, 300)
    if not why:
        problems.append("Say why the debt is written off")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        tid = _insert(conn, p.pupil_id, WRITE_OFF, -bal, actor, day=_today().isoformat(),
                      notes=why)
        _audit(conn, "write_off", actor, pupil_id=p.pupil_id, txn=tid)
    activity_log.record("dinner_money.write_off", target=p.admission_no, principal=actor,
                        txn=tid)
    return get_txn(tid)


# ── The meal register ────────────────────────────────────────────────

def register(day: Any = None, meal_type: str = DEFAULT_MEAL, *,
             year_group: int | str | None = None, form_group: str | None = None
             ) -> list[RegisterRow]:
    """On-roll pupils for the day's register: who had the meal, FSM, charged,
    balance and the dietary / allergy flag."""
    iso = str(day or _today().isoformat())
    with database.connect() as conn:
        had = {r["pupil_id"]: r for r in conn.execute(
            "SELECT * FROM dinner_meals WHERE meal_date = ? AND meal_type = ?",
            (iso, meal_type))}
    price = get_price(meal_type)
    out = []
    for a in accounts(year_group=year_group, form_group=form_group):
        m = had.get(a.pupil_id)
        fsm_free = a.fsm and bool(price and price.fsm_covered)
        out.append(RegisterRow(
            pupil_id=a.pupil_id, pupil_name=a.pupil_name, admission_no=a.admission_no,
            year_group=a.year_group, form_group=a.form_group, fsm=a.fsm, had_meal=m is not None,
            charged=bool(m and m["charged"]),
            price_pence=(m["price_pence"] if m and m["charged"] else (0 if fsm_free else
                                                     (price.price_pence if price else 0))),
            balance_pence=a.balance_pence, needs=a.needs_flag))
    return out


def meals(*, day: str | None = None, pupil_id: int | None = None,
          meal_type: str | None = None, uncharged: bool = False) -> list[dict[str, Any]]:
    where, params = [], []
    for col, val in (("meal_date", day), ("pupil_id", pupil_id), ("meal_type", meal_type)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if uncharged:
        where.append("charged = 0")
    with database.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM dinner_meals" + (" WHERE " + " AND ".join(where) if where else "")
            + " ORDER BY meal_date DESC, meal_id DESC", params)]


def save_register(day: Any, meal_type: str, pupil_ids: list[int], *, actor: Principal,
                  scope: list[int] | None = None) -> dict[str, int]:
    """Who had *meal_type* on *day*: ticks are added, unticked pupils (within
    *scope*, default everyone on the register) are taken off. Taking off a
    charged meal voids its charge (finance office only)."""
    _require_staff(actor, "register")
    problems: list[str] = []
    iso = _date(day, "Date", problems) or _today().isoformat()
    _price_or_fail(meal_type)
    wanted = {int(x) for x in pupil_ids}
    with database.connect() as conn:
        existing = {r["pupil_id"]: r for r in conn.execute(
            "SELECT * FROM dinner_meals WHERE meal_date = ? AND meal_type = ?", (iso, meal_type))}
    within = set(scope) if scope is not None else set(existing) | wanted
    remove = [existing[p] for p in existing if p in within and p not in wanted]
    if any(r["charged"] for r in remove) and not is_editor(actor):
        problems.append("Some of those meals have been charged - ask the finance office to "
                        "take them off")
    for pid in wanted - set(existing):
        p = P.get_pupil(pid)
        if p is None:
            problems.append(f"No pupil #{pid}")
        elif p.roll_status != "on_roll":
            problems.append(f"{p.display_name} is not on roll")
    if problems:
        raise ValidationError(problems)
    added = 0
    with database.connect() as conn:
        for pid in sorted(wanted - set(existing)):
            conn.execute("INSERT INTO dinner_meals (pupil_id, meal_date, meal_type, "
                         "recorded_by) VALUES (?, ?, ?, ?)", (pid, iso, meal_type,
                                                              actor.username))
            added += 1
        for r in remove:
            if r["txn_id"]:
                conn.execute("UPDATE dinner_transactions SET voided = 1, void_reason = ?, "
                             "voided_by = ?, voided_at = datetime('now') WHERE txn_id = ?",
                             ("Taken off the meal register", actor.username, r["txn_id"]))
            conn.execute("DELETE FROM dinner_meals WHERE meal_id = ?", (r["meal_id"],))
        _audit(conn, "register", actor, day=iso, meal_type=meal_type, added=added,
               removed=len(remove))
    activity_log.record("dinner_money.register", principal=actor, added=added,
                        removed=len(remove))
    return {"added": added, "removed": len(remove)}


def charge_register(day: Any = None, meal_type: str | None = None, *, actor: Principal
                    ) -> dict[str, int]:
    """Charge every uncharged meal on the day's register (one meal type, or
    all). FSM pupils' covered meals are recorded at no charge.
    Returns {'charged', 'fsm', 'total_pence'}."""
    _require_editor(actor, "charge")
    problems: list[str] = []
    iso = _date(day, "Date", problems) or _today().isoformat()
    if problems:
        raise ValidationError(problems)
    rows = meals(day=iso, meal_type=meal_type, uncharged=True)
    if not rows:
        raise ValidationError(["Nothing to charge on that register"])
    prices = {r["meal_type"]: _price_or_fail(r["meal_type"]) for r in rows}
    charged = fsm = total = 0
    with database.connect() as conn:
        for r in rows:
            p = P.get_pupil(r["pupil_id"])
            pr = prices[r["meal_type"]]
            if p is not None and p.fsm_eligible and pr.fsm_covered:
                conn.execute("UPDATE dinner_meals SET charged = 1, fsm = 1, price_pence = 0 "
                             "WHERE meal_id = ?", (r["meal_id"],))
                fsm += 1
                continue
            tid = None
            if pr.price_pence:
                tid = _insert(conn, r["pupil_id"], MEAL, -pr.price_pence, actor, day=iso,
                              meal_type=r["meal_type"])
            conn.execute("UPDATE dinner_meals SET charged = 1, fsm = 0, price_pence = ?, "
                         "txn_id = ? WHERE meal_id = ?", (pr.price_pence, tid, r["meal_id"]))
            charged += 1
            total += pr.price_pence
        _audit(conn, "charge", actor, day=iso, meal_type=meal_type, charged=charged, fsm=fsm)
    activity_log.record("dinner_money.charge", principal=actor, charged=charged, fsm=fsm)
    return {"charged": charged, "fsm": fsm, "total_pence": total}


def record_meal(pupil_id: Any, meal_type: str = DEFAULT_MEAL, *, actor: Principal,
                day: str | None = None) -> dict[str, Any]:
    """One meal at the till: on the register and charged at once (free for
    a pupil on FSM when the meal is covered). Never refused for a low
    balance - the account goes overdrawn."""
    _require_editor(actor, "meal")
    p = _must_pupil(pupil_id)
    problems: list[str] = []
    iso = _date(day, "Date", problems) or _today().isoformat()
    if p.roll_status != "on_roll":
        problems.append(f"{p.display_name} is not on roll")
    if problems:
        raise ValidationError(problems)
    pr = _price_or_fail(meal_type)
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM dinner_meals WHERE pupil_id = ? AND meal_date = ? AND "
                        "meal_type = ?", (p.pupil_id, iso, pr.meal_type)).fetchone():
            raise ValidationError([f"{p.display_name} already has {pr.meal_type} on {iso}"])
        free = bool(p.fsm_eligible and pr.fsm_covered)
        tid = None if free or not pr.price_pence else _insert(
            conn, p.pupil_id, MEAL, -pr.price_pence, actor, day=iso, meal_type=pr.meal_type)
        conn.execute("INSERT INTO dinner_meals (pupil_id, meal_date, meal_type, price_pence, "
                     "fsm, charged, txn_id, recorded_by) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                     (p.pupil_id, iso, pr.meal_type, 0 if free else pr.price_pence, int(free),
                      tid, actor.username))
        _audit(conn, "meal", actor, pupil_id=p.pupil_id, fsm=free)
    activity_log.record("dinner_money.meal", target=p.admission_no, principal=actor)
    return {"fsm": free, "price_pence": 0 if free else pr.price_pence,
            "balance_pence": balance(p.pupil_id)}


# ── Arrears, alerts and letters ──────────────────────────────────────

def arrears(*, min_debt: int = 1, year_group: int | str | None = None,
            include_leavers: bool = False) -> list[Account]:
    """Overdrawn accounts, biggest debt first."""
    rows = accounts(year_group=year_group, roll_status=None if include_leavers else "on_roll")
    return sorted((a for a in rows if a.balance_pence <= -abs(min_debt)),
                  key=lambda a: a.balance_pence)


def low_balance(threshold: int | None = None, *, year_group: int | str | None = None
                ) -> list[Account]:
    """On-roll, non-FSM pupils in credit but below the low-balance level. An
    account that has never been used (no top-up or meal, so £0.00) isn't low."""
    level = low_balance_threshold() if threshold is None else threshold
    return sorted((a for a in accounts(year_group=year_group, fsm=False)
                   if is_low(a, level)), key=lambda a: a.balance_pence)


def is_low(a: Account, level: int | None = None) -> bool:
    """In credit but under the low-balance level; never for FSM pupils or for
    a never-used £0.00 account (a family that doesn't use school dinners)."""
    level = low_balance_threshold() if level is None else level
    return 0 <= a.balance_pence < level and not a.fsm and a.used


def leavers_with_balance() -> list[Account]:
    return [a for a in accounts(roll_status="left") if a.balance_pence]


def last_letters(pupil_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM dinner_letters WHERE pupil_id = ? ORDER BY letter_id DESC",
            (int(pupil_id),))]


def _recently_sent(pupil_ids: list[int], kind: str) -> set[int]:
    since = (_dt.datetime.now() - _dt.timedelta(days=LETTER_GAP_DAYS)).strftime(
        "%Y-%m-%d %H:%M:%S")
    with database.connect() as conn:
        return {r[0] for r in conn.execute(
            "SELECT DISTINCT pupil_id FROM dinner_letters WHERE kind = ? AND sent_at >= ?",
            (kind, since)) if r[0] in set(pupil_ids)}


def _staff_name(actor: Principal) -> str:
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    return BH._staff_name(actor)


def _send_letters(kind: str, template_name: str, label: str,
                  items: list[tuple[Account, dict[str, Any]]], actor: Principal
                  ) -> dict[str, Any]:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    template = email_templates.load_template(template_name)
    contacts = C.emailable_for_pupils([a.pupil_id for a, _v in items])
    letters, sent, no_email = [], [], []
    for a, values in items:
        to = [(x.email, x.full_name) for x in contacts.get(a.pupil_id, [])
              if x.email and x.parental_responsibility]
        if not to:
            no_email.append(a)
            continue
        sent.append(a)
        first = a.pupil_name.split(", ", 1)[-1]
        for address, name in to:
            subject, body = template.render({"recipient_name": name, "pupil_name": first,
                                             "sender_name": _staff_name(actor), **values})
            letters.append((address, name, subject, body))
    if not letters:
        return {"message_id": None, "emails": 0, "sent": [], "no_email": no_email,
                "skipped": []}
    mid = E.save_prepared(f"dinner_{kind}", label, label, "(one letter per contact)", letters,
                          actor=actor)
    with database.connect() as conn:
        for a in sent:
            conn.execute("INSERT INTO dinner_letters (pupil_id, kind, balance_pence, message_id,"
                         " sent_by) VALUES (?, ?, ?, ?, ?)",
                         (a.pupil_id, kind, a.balance_pence, mid, actor.username))
            _audit(conn, f"letter_{kind}", actor, pupil_id=a.pupil_id, message=mid)
    activity_log.record(f"dinner_money.letter_{kind}", principal=actor, emails=len(letters))
    return {"message_id": mid, "emails": len(letters), "sent": sent, "no_email": no_email,
            "skipped": []}


def _recent_lines(pupil_id: int, n: int = 8) -> str:
    rows = transactions(pupil_id=pupil_id, include_voided=False, limit=n)
    return "Recent activity:\n" + "\n".join(
        f"  {t.txn_date}  {t.kind:<16} {t.meal_type or t.method or '':<12} "
        f"{money(t.amount_pence):>9}" for t in reversed(rows)) if rows else ""


def send_debt_letters(*, actor: Principal, pupil_ids: list[int] | None = None
                      ) -> dict[str, Any]:
    """E-mail the families of overdrawn pupils (chosen ones, or everyone not
    sent one in the last week)."""
    _require_editor(actor, "letter_debt")
    rows = arrears()
    skipped: list[Account] = []
    if pupil_ids:
        rows = [a for a in rows if a.pupil_id in {int(x) for x in pupil_ids}]
    else:
        recent = _recently_sent([a.pupil_id for a in rows], "debt")
        skipped = [a for a in rows if a.pupil_id in recent]
        rows = [a for a in rows if a.pupil_id not in recent]
    if not rows:
        raise ValidationError(["No overdrawn accounts to write to"
                               + (" (all had a letter this week)" if skipped else "")])
    res = _send_letters("debt", "dinner_money_debt", "School meals - account overdrawn",
                        [(a, {"debt": money(-a.balance_pence),
                              "details": _recent_lines(a.pupil_id)}) for a in rows], actor)
    res["skipped"] = skipped
    return res


def send_low_balance_alerts(*, actor: Principal, pupil_ids: list[int] | None = None
                            ) -> dict[str, Any]:
    _require_editor(actor, "letter_low")
    level = low_balance_threshold()
    rows = low_balance(level)
    skipped: list[Account] = []
    if pupil_ids:
        rows = [a for a in rows if a.pupil_id in {int(x) for x in pupil_ids}]
    else:
        recent = _recently_sent([a.pupil_id for a in rows], "low_balance")
        skipped = [a for a in rows if a.pupil_id in recent]
        rows = [a for a in rows if a.pupil_id not in recent]
    if not rows:
        raise ValidationError(["No low balances to alert"
                               + (" (all had an alert this week)" if skipped else "")])
    res = _send_letters("low_balance", "dinner_money_low_balance",
                        "School meals - balance running low",
                        [(a, {"balance": money(a.balance_pence), "threshold": money(level)})
                         for a in rows], actor)
    res["skipped"] = skipped
    return res


# ── Statements ───────────────────────────────────────────────────────

def statement(pupil_id: Any, *, date_from: str | None = None, date_to: str | None = None
              ) -> dict[str, Any]:
    """{'account', 'from', 'to', 'opening_pence', 'lines': [(Txn, running)],
    'closing_pence', 'meals', 'fsm_meals'}. Voided lines are listed but don't
    count."""
    a = account(pupil_id)
    problems: list[str] = []
    lo = _date(date_from, "From", problems, future_ok=True) or "0000-01-01"
    hi = _date(date_to, "To", problems, future_ok=True) or "9999-12-31"
    if lo > hi:
        problems.append("From must be before To")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        opening = int(conn.execute("SELECT COALESCE(SUM(amount_pence), 0) FROM "
                                   "dinner_transactions WHERE pupil_id = ? AND voided = 0 AND "
                                   "txn_date < ?", (a.pupil_id, lo)).fetchone()[0])
    rows = sorted(transactions(pupil_id=a.pupil_id, date_from=lo, date_to=hi),
                  key=lambda t: (t.txn_date, t.txn_id))
    running, lines = opening, []
    for t in rows:
        running += t.counts
        lines.append((t, running))
    served = [m for m in meals(pupil_id=a.pupil_id) if lo <= m["meal_date"] <= hi]
    return {"account": a, "from": None if lo.startswith("0000") else lo,
            "to": None if hi.startswith("9999") else hi, "opening_pence": opening,
            "lines": lines, "closing_pence": running, "meals": len(served),
            "fsm_meals": sum(1 for m in served if m["fsm"])}


def statement_text(s: dict[str, Any]) -> str:
    a: Account = s["account"]
    out = [f"{a.pupil_name} ({a.admission_no}), Year {a.year_group}"
           + (" - free school meals" if a.fsm else ""),
           f"Period: {s['from'] or 'start'} to {s['to'] or 'today'}", "",
           f"{'Opening balance':<52}{money(s['opening_pence']):>11}"]
    for t, run in s["lines"]:
        what = t.meal_type or t.method or ""
        line = f"{t.txn_date}  {t.kind:<16} {what:<14}{money(t.amount_pence):>10}"
        out.append(line + (f"{'(void)':>11}" if t.voided else f"{money(run):>11}"))
    out += [f"{'Closing balance':<52}{money(s['closing_pence']):>11}", "",
            f"Meals: {s['meals']} (free school meals: {s['fsm_meals']})"]
    return "\n".join(out)


def email_statement(pupil_id: Any, *, actor: Principal, date_from: str | None = None,
                    date_to: str | None = None) -> dict[str, Any]:
    _require_editor(actor, "letter_statement")
    s = statement(pupil_id, date_from=date_from, date_to=date_to)
    return _send_letters("statement", "dinner_money_statement", "School meals statement",
                         [(s["account"], {"period": f"{s['from'] or 'start'} to "
                                                    f"{s['to'] or _today().isoformat()}",
                                          "statement": statement_text(s)})], actor)


# ── Year end ─────────────────────────────────────────────────────────

def year_ends() -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM dinner_year_ends ORDER BY academic_year DESC")]


def year_end(academic_year: str | None = None, *, actor: Principal) -> dict[str, Any]:
    """Carry every on-roll balance into the next school year: a "Carried
    forward" line on 31 August and a "Brought forward" line on 1 September
    (they net to zero). Done once a year. Leavers are listed for a refund or
    write-off instead. Returns {'pupils', 'credit_pence', 'debt_pence',
    'leavers'}."""
    _require_editor(actor, "year_end")
    year = academic_year or current_year()
    if len(year) != 7 or not year[:4].isdigit():
        raise ValidationError(["School year looks like 2025/26"])
    end = f"{int(year[:4]) + 1}-08-31"
    start = f"{int(year[:4]) + 1}-09-01"
    if end >= _today().isoformat() and year == current_year():
        raise ValidationError([f"{year} hasn't finished (it ends on {end})"])
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM dinner_year_ends WHERE academic_year = ?",
                        (year,)).fetchone():
            raise ValidationError([f"{year} has already been carried forward"])
    with database.connect() as conn:
        at_end = {r[0]: int(r[1]) for r in conn.execute(
            "SELECT pupil_id, SUM(amount_pence) FROM dinner_transactions WHERE voided = 0 AND "
            "txn_date <= ? GROUP BY pupil_id", (end,))}
    rows = [(a, at_end.get(a.pupil_id, 0)) for a in accounts()]
    rows = [(a, b) for a, b in rows if b]
    credit = sum(b for _a, b in rows if b > 0)
    debt = sum(b for _a, b in rows if b < 0)
    with database.connect() as conn:
        for a, bal in rows:
            note = f"{year} into {next_year(year)}"
            _insert(conn, a.pupil_id, CARRIED_OUT, -bal, actor, day=end, notes=note)
            _insert(conn, a.pupil_id, CARRIED_IN, bal, actor, day=start, notes=note)
        conn.execute("INSERT INTO dinner_year_ends (academic_year, closed_on, closed_by, pupils) "
                     "VALUES (?, ?, ?, ?)", (year, _today().isoformat(), actor.username,
                                             len(rows)))
        _audit(conn, "year_end", actor, year=year, pupils=len(rows))
    activity_log.record("dinner_money.year_end", principal=actor, pupils=len(rows))
    return {"pupils": len(rows), "credit_pence": credit, "debt_pence": debt,
            "leavers": leavers_with_balance()}


# ── Cash-up and reports ──────────────────────────────────────────────

def cash_up(day: Any = None) -> dict[str, Any]:
    """The day's takings: top-ups and refunds by method and by who took them,
    meals served by type, FSM meals and meal charges."""
    iso = str(day or _today().isoformat())
    lines = [t for t in transactions(date_from=iso, date_to=iso, include_voided=False)]
    by_method: Counter[str] = Counter()
    by_person: Counter[str] = Counter()
    count: Counter[str] = Counter()
    for t in lines:
        if t.kind in CASH_KINDS:
            by_method[t.method or "-"] += t.amount_pence
            by_person[t.created_by or "-"] += t.amount_pence
            count[t.method or "-"] += 1
    served = meals(day=iso)
    by_meal: Counter[str] = Counter(m["meal_type"] for m in served)
    return {"day": iso, "by_method": dict(by_method), "count_by_method": dict(count),
            "by_person": dict(by_person),
            "top_ups_pence": sum(t.amount_pence for t in lines if t.kind == TOP_UP),
            "refunds_pence": -sum(t.amount_pence for t in lines if t.kind == REFUND),
            "net_pence": sum(by_method.values()),
            "cash_pence": by_method.get("Cash", 0),
            "meals": dict(by_meal), "fsm_meals": sum(1 for m in served if m["fsm"]),
            "uncharged": sum(1 for m in served if not m["charged"]),
            "charges_pence": -sum(t.amount_pence for t in lines if t.kind == MEAL)}


def cash_up_text(c: dict[str, Any]) -> str:
    out = [f"Cash-up for {c['day']}", "", "Takings by method:"]
    for m in METHODS:
        if m in c["by_method"]:
            out.append(f"  {m:<16}{c['count_by_method'].get(m, 0):>4} line(s)"
                       f"{money(c['by_method'][m]):>12}")
    out += [f"  {'Top-ups':<28}{money(c['top_ups_pence']):>12}",
            f"  {'Refunds paid out':<28}{money(-c['refunds_pence']):>12}",
            f"  {'Net':<28}{money(c['net_pence']):>12}",
            f"  {'Cash to bank':<28}{money(c['cash_pence']):>12}", "", "By who took it:"]
    out += [f"  {k:<28}{money(v):>12}" for k, v in sorted(c["by_person"].items())]
    out += ["", "Meals served:"]
    out += [f"  {k:<20}{v:>6}" for k, v in sorted(c["meals"].items())]
    out += [f"  {'Free school meals':<20}{c['fsm_meals']:>6}",
            f"  {'Not charged yet':<20}{c['uncharged']:>6}",
            f"  {'Meal charges':<28}{money(c['charges_pence']):>12}"]
    return "\n".join(out)


def takings(date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Daily takings over a range: {'day', 'by_method', 'net_pence', 'meals'}."""
    problems: list[str] = []
    lo = _date(date_from, "From", problems, future_ok=True)
    hi = _date(date_to, "To", problems, future_ok=True)
    if not lo or not hi:
        problems.append("Give both dates")
    if problems:
        raise ValidationError(problems)
    days: dict[str, dict[str, Any]] = defaultdict(lambda: {"by_method": Counter(),
                                                           "meals": 0})
    for t in transactions(date_from=lo, date_to=hi, include_voided=False, limit=100000):
        if t.kind in CASH_KINDS:
            days[t.txn_date]["by_method"][t.method or "-"] += t.amount_pence
    with database.connect() as conn:
        for r in conn.execute("SELECT meal_date, COUNT(*) FROM dinner_meals WHERE meal_date "
                              "BETWEEN ? AND ? GROUP BY meal_date", (lo, hi)):
            days[r[0]]["meals"] = r[1]
    return [{"day": d, "by_method": dict(v["by_method"]),
             "net_pence": sum(v["by_method"].values()), "meals": v["meals"]}
            for d, v in sorted(days.items())]


def summary() -> dict[str, Any]:
    rows = accounts()
    return {"pupils": len(rows), "fsm": sum(1 for a in rows if a.fsm),
            "credit_pence": sum(a.balance_pence for a in rows if a.balance_pence > 0),
            "debt_pence": -sum(a.balance_pence for a in rows if a.balance_pence < 0),
            "overdrawn": sum(1 for a in rows if a.balance_pence < 0),
            "low": len(low_balance()), "low_level": low_balance_threshold(),
            "needs": sum(1 for a in rows if a.needs_flag)}


# ── Families ─────────────────────────────────────────────────────────

def for_family(pupil_id: int) -> dict[str, Any]:
    """What the portal shows: balance, low / overdrawn, FSM and the last
    lines of the account."""
    a = account(pupil_id)
    level = low_balance_threshold()
    return {"balance": money(a.balance_pence), "balance_pence": a.balance_pence,
            "overdrawn": a.balance_pence < 0,
            "low": is_low(a, level), "fsm": a.fsm,
            "recent": [{"date": t.txn_date, "what": t.kind if not t.meal_type
                        else f"{t.kind} ({t.meal_type})", "amount": money(t.amount_pence)}
                       for t in transactions(pupil_id=a.pupil_id, include_voided=False,
                                             limit=10)]}


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, kind: str = "balances",
               **filters: Any) -> int:
    """``kind`` "balances" (one row per pupil) or "transactions" (the ledger;
    filters: pupil_id, date_from, date_to, kind, method)."""
    _require_staff(actor, "export")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if kind == "transactions":
            txn_kind = filters.pop("txn_kind", None)
            rows = transactions(kind=txn_kind, limit=1_000_000, **filters)
            w.writerow(["txn", "date", "admission_no", "pupil", "kind", "amount", "meal_type",
                        "method", "reference", "notes", "voided", "void_reason", "by"])
            for t in rows:
                w.writerow([t.txn_id, t.txn_date, _safe(t.admission_no), _safe(t.pupil_name),
                            t.kind, plain(t.amount_pence), t.meal_type or "", t.method or "",
                            _safe(t.reference), _safe(t.notes), t.voided,
                            _safe(t.void_reason), _safe(t.created_by)])
        else:
            rows = accounts(**filters)
            w.writerow(["admission_no", "pupil", "year", "form", "fsm", "balance",
                        "last_top_up", "dietary", "allergies"])
            for a in rows:
                w.writerow([_safe(a.admission_no), _safe(a.pupil_name), a.year_group,
                            _safe(a.form_group), int(a.fsm), plain(a.balance_pence),
                            a.last_top_up or "", _safe(a.dietary), _safe(a.allergies)])
    activity_log.record("dinner_money.export", principal=actor, rows=len(rows), kind=kind)
    return len(rows)
