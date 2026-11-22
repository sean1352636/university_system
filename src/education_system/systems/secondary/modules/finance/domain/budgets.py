"""Budgets: financial years, cost centres, budget lines, virements,
commitments, spend and the monthly profile.

There was no budgets screen before the rebuild (the old Departments record
had a free-standing "budget total / allocated / spent" in pounds); this is
new, and it is where Expense Claims post their spend.

* **Financial year.** Maintained schools run April-March, academies
  September-August: the start month is a setting (:func:`settings`,
  ``year_start_month``). Each year is a row with its own start and end date
  (changing the setting only affects years created afterwards). A closed year
  takes no more changes, orders or spend.
* **Cost centres** (departments, pastoral, premises, trips, CPD ...) per year,
  each with a holder - a staff login username (``accounts.staff_logins``).
  Cost centres are keyed on a free-text name, unique within the year.
* **Budget lines** per cost centre: code (unique within the year),
  description and allocation. Money is always whole pence.
* **Virements** move budget between two lines of the same year. The holder of
  the "from" cost centre or a budget editor asks, with a reason. The holder
  of the "from" cost centre may approve or reject it - their own request
  included (it is their budget); a budget editor (:data:`BUDGET_EDITORS`)
  who doesn't hold it may decide any virement except one they asked for.
  Only approved virements change a line's budget.
* **Commitments** are orders raised and not yet paid. Settling one turns it
  into spend (at the amount actually paid); cancelling releases it.
* **Spend** is entered by hand (finance office) or posted by an approved
  expense claim (:mod:`.expense_claims`); a cancelled approved claim is
  reversed with a negative entry, so the history stays.
* **Position**: budget = allocation + virements in - virements out;
  remaining = budget - committed - spent. A line is "warn" once committed +
  spent reach the warning percentage (setting, default 90%) and "over" when
  remaining goes below zero (:func:`overspends`, :func:`check_spend`).
* **Monthly profile** (how the budget is expected to be spent through the
  year) is stored as weights, so it still adds up after a virement; even
  when not set. :func:`variance` compares profile with actual spend by month.
* **Holder view** (:func:`my_centres`), CSV export, and :func:`roll_forward`
  to copy centres, lines (with an optional uplift) and profiles to the next
  year.

Who: budget editors do everything; a cost centre's holder sees their own
cost centres, raises and cancels orders on them and asks for virements from
them. Other staff can only list budget codes (no amounts) to choose one on an
expense claim. Every change is in ``budget_audit`` and the activity log
(ids only, no amounts with names).
"""

from __future__ import annotations

import calendar
import csv
import datetime as _dt
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    BUDGET_EDITORS,
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

CENTRE_KINDS: tuple[str, ...] = (
    "Department", "Pastoral", "Premises", "Trips", "CPD", "Curriculum", "Administration",
    "ICT", "SEND", "Catering", "Governance", "Other")
DEFAULT_KIND = "Department"
YEAR_STATUSES: tuple[str, ...] = ("Open", "Closed")
VIREMENT_STATUSES: tuple[str, ...] = ("Pending", "Approved", "Rejected", "Cancelled")
COMMITMENT_STATUSES: tuple[str, ...] = ("Open", "Paid", "Cancelled")
SPEND_SOURCES: tuple[str, ...] = ("manual", "expense_claim", "commitment")

#: Maintained schools (April) and academies (September).
YEAR_START_PRESETS = {"Maintained (April-March)": 4, "Academy (September-August)": 9}
DEFAULTS = {"year_start_month": 4, "warn_percent": 90}
_LIMITS = {"year_start_month": (1, 12, "Year start month"),
           "warn_percent": (1, 100, "Warning percentage")}
MAX_PENCE = 100_000_000_000   # £1bn - anything bigger is a typing slip

_SCHEMA = """
CREATE TABLE IF NOT EXISTS budget_settings (
    key    TEXT PRIMARY KEY,
    value  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS budget_years (
    year_label  TEXT PRIMARY KEY,
    start_date  TEXT NOT NULL,
    end_date    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Closed')),
    created_by  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS budget_cost_centres (
    centre_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    year_label  TEXT NOT NULL REFERENCES budget_years (year_label) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'Department',
    holder      TEXT,
    notes       TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    created_by  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by  TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (year_label, name COLLATE NOCASE)
);
CREATE INDEX IF NOT EXISTS ix_budget_centres_holder ON budget_cost_centres (holder);
CREATE TABLE IF NOT EXISTS budget_lines (
    line_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_id         INTEGER NOT NULL REFERENCES budget_cost_centres (centre_id),
    code              TEXT NOT NULL,
    description       TEXT NOT NULL,
    allocation_pence  INTEGER NOT NULL DEFAULT 0 CHECK (allocation_pence >= 0),
    notes             TEXT,
    created_by        TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by        TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_budget_lines_centre ON budget_lines (centre_id);
CREATE TABLE IF NOT EXISTS budget_profile (
    line_id  INTEGER NOT NULL REFERENCES budget_lines (line_id) ON DELETE CASCADE,
    month    INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    weight   INTEGER NOT NULL CHECK (weight >= 0),
    PRIMARY KEY (line_id, month)
);
CREATE TABLE IF NOT EXISTS budget_virements (
    virement_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    from_line_id   INTEGER NOT NULL REFERENCES budget_lines (line_id),
    to_line_id     INTEGER NOT NULL REFERENCES budget_lines (line_id),
    amount_pence   INTEGER NOT NULL CHECK (amount_pence > 0),
    reason         TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Pending'
                   CHECK (status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')),
    requested_by   TEXT NOT NULL,
    requested_at   TEXT NOT NULL DEFAULT (datetime('now')),
    decided_by     TEXT,
    decided_at     TEXT,
    decision_note  TEXT
);
CREATE TABLE IF NOT EXISTS budget_commitments (
    commitment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id        INTEGER NOT NULL REFERENCES budget_lines (line_id),
    raised_on      TEXT NOT NULL,
    supplier       TEXT,
    description    TEXT NOT NULL,
    order_ref      TEXT,
    amount_pence   INTEGER NOT NULL CHECK (amount_pence > 0),
    status         TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Paid', 'Cancelled')),
    closed_on      TEXT,
    created_by     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_budget_commitments_line ON budget_commitments (line_id, status);
CREATE TABLE IF NOT EXISTS budget_spend (
    spend_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id        INTEGER NOT NULL REFERENCES budget_lines (line_id),
    spend_date     TEXT NOT NULL,
    description    TEXT NOT NULL,
    supplier       TEXT,
    reference      TEXT,
    amount_pence   INTEGER NOT NULL CHECK (amount_pence != 0),
    source         TEXT NOT NULL DEFAULT 'manual'
                   CHECK (source IN ('manual', 'expense_claim', 'commitment')),
    source_id      INTEGER,
    created_by     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_budget_spend_line ON budget_spend (line_id, spend_date);
CREATE INDEX IF NOT EXISTS ix_budget_spend_source ON budget_spend (source, source_id);
CREATE TABLE IF NOT EXISTS budget_audit (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    year_label  TEXT,
    centre_id   INTEGER,
    line_id     INTEGER,
    action      TEXT NOT NULL,
    detail      TEXT,
    actor       TEXT NOT NULL,
    at          TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("budgets", _SCHEMA)


# ── Money ────────────────────────────────────────────────────────────

def money(pence: int | None) -> str:
    """1234567 -> '£12,345.67' (negative: '-£5.00')."""
    if pence is None:
        return ""
    sign = "-" if pence < 0 else ""
    p = abs(int(pence))
    return f"{sign}£{p // 100:,}.{p % 100:02d}"


def to_pence(value: Any, label: str, problems: list[str], *, allow_negative: bool = False,
             allow_zero: bool = True, required: bool = True) -> int | None:
    """An amount as whole pence. An ``int`` is already pence; text is pounds
    ("12.50", "£1,234", "-3")."""
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            problems.append(f"{label} is required")
        return None
    if isinstance(value, bool):
        problems.append(f"{label} must be an amount")
        return None
    if isinstance(value, int):
        n = value
    else:
        text = str(value).strip().replace("£", "").replace(",", "").replace(" ", "")
        try:
            d = Decimal(text)
        except InvalidOperation:
            problems.append(f"{label} must be an amount in pounds (e.g. 12.50)")
            return None
        if not d.is_finite() or d != d.quantize(Decimal("0.01")):
            problems.append(f"{label} can't have fractions of a penny")
            return None
        n = int(d * 100)
    if n < 0 and not allow_negative:
        problems.append(f"{label} can't be negative")
    elif n == 0 and not allow_zero:
        problems.append(f"{label} must be more than £0.00")
    elif abs(n) > MAX_PENCE:
        problems.append(f"{label} is too large")
    return n


def pounds(pence: int | None) -> str:
    """Pence as editable pounds text ('12.50'), for forms."""
    if pence is None:
        return ""
    sign = "-" if pence < 0 else ""
    p = abs(int(pence))
    return f"{sign}{p // 100}.{p % 100:02d}"


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Year:
    year_label: str
    start_date: str
    end_date: str
    status: str
    created_by: str | None
    created_at: str

    @property
    def is_open(self) -> bool:
        return self.status == "Open"


@dataclass(frozen=True)
class CostCentre:
    centre_id: int
    year_label: str
    name: str
    kind: str
    holder: str | None
    notes: str | None
    active: int
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    lines: int = 0


@dataclass(frozen=True)
class Line:
    line_id: int
    centre_id: int
    code: str
    description: str
    allocation_pence: int
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    centre_name: str = ""
    holder: str | None = None
    year_label: str = ""


@dataclass(frozen=True)
class Position:
    """A budget line's money: all pence."""
    line_id: int
    code: str
    description: str
    centre_id: int
    centre_name: str
    holder: str | None
    year_label: str
    allocation: int
    virements_in: int
    virements_out: int
    committed: int
    spent: int

    @property
    def budget(self) -> int:
        return self.allocation + self.virements_in - self.virements_out

    @property
    def remaining(self) -> int:
        return self.budget - self.committed - self.spent

    @property
    def used_percent(self) -> int:
        used = self.committed + self.spent
        if self.budget <= 0:
            return 100 if used > 0 else 0
        return (used * 100) // self.budget

    def state(self, warn_percent: int | None = None) -> str:
        """'over', 'warn' or 'ok'."""
        if self.remaining < 0:
            return "over"
        warn = warn_percent if warn_percent is not None else settings()["warn_percent"]
        return "warn" if self.used_percent >= warn and (self.committed + self.spent) else "ok"


@dataclass(frozen=True)
class Virement:
    virement_id: int
    from_line_id: int
    to_line_id: int
    amount_pence: int
    reason: str
    status: str
    requested_by: str
    requested_at: str
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None
    from_code: str = ""
    to_code: str = ""
    year_label: str = ""


@dataclass(frozen=True)
class Commitment:
    commitment_id: int
    line_id: int
    raised_on: str
    supplier: str | None
    description: str
    order_ref: str | None
    amount_pence: int
    status: str
    closed_on: str | None
    created_by: str | None
    created_at: str
    code: str = ""
    centre_name: str = ""


@dataclass(frozen=True)
class Spend:
    spend_id: int
    line_id: int
    spend_date: str
    description: str
    supplier: str | None
    reference: str | None
    amount_pence: int
    source: str
    source_id: int | None
    created_by: str | None
    created_at: str
    code: str = ""
    centre_name: str = ""


def _make(cls, r, **extra):
    return cls(**{k: r[k] for k in cls.__dataclass_fields__ if k in r.keys()}, **extra)


_LINE_SELECT = ("SELECT l.*, c.name AS centre_name, c.holder, c.year_label FROM budget_lines l "
                "JOIN budget_cost_centres c USING (centre_id)")
_CENTRE_SELECT = ("SELECT c.*, (SELECT COUNT(*) FROM budget_lines l WHERE l.centre_id = "
                  "c.centre_id) AS lines FROM budget_cost_centres c")
_VIREMENT_SELECT = (
    "SELECT v.*, f.code AS from_code, t.code AS to_code, fc.year_label FROM budget_virements v "
    "JOIN budget_lines f ON f.line_id = v.from_line_id "
    "JOIN budget_lines t ON t.line_id = v.to_line_id "
    "JOIN budget_cost_centres fc ON fc.centre_id = f.centre_id")
_COMMIT_SELECT = ("SELECT m.*, l.code, c.name AS centre_name FROM budget_commitments m "
                  "JOIN budget_lines l USING (line_id) JOIN budget_cost_centres c USING (centre_id)")
_SPEND_SELECT = ("SELECT s.*, l.code, c.name AS centre_name FROM budget_spend s "
                 "JOIN budget_lines l USING (line_id) JOIN budget_cost_centres c USING (centre_id)")


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in BUDGET_EDITORS


def is_holder(actor: Principal, centre: CostCentre | Line | Position) -> bool:
    holder = getattr(centre, "holder", None)
    return bool(holder and actor.username and holder.lower() == actor.username.lower())


def holds_any(actor: Principal) -> bool:
    """True if *actor* holds at least one cost centre (any year)."""
    if not actor.username:
        return False
    with database.connect() as conn:
        return conn.execute("SELECT 1 FROM budget_cost_centres WHERE lower(holder) = lower(?) "
                            "LIMIT 1", (actor.username,)).fetchone() is not None


def can_view(actor: Principal, centre: CostCentre | Line | Position) -> bool:
    return actor.role in STAFF_ROLES and (is_editor(actor) or is_holder(actor, centre))


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"budgets.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, None, "Only staff can see budgets.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the finance office (budget editors) can do that.")


def _require_view(actor: Principal, thing: Any, action: str) -> None:
    if not can_view(actor, thing):
        _deny(actor, action, getattr(thing, "centre_id", None),
              "Only the budget holder or the finance office can see this cost centre.")


def _require_holder_or_editor(actor: Principal, thing: Any, action: str) -> None:
    if not (actor.role in STAFF_ROLES and (is_editor(actor) or is_holder(actor, thing))):
        _deny(actor, action, getattr(thing, "centre_id", None),
              "Only the budget holder or the finance office can do that.")


def _audit(conn, action: str, actor: Principal, *, year: str | None = None,
           centre_id: int | None = None, line_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO budget_audit (year_label, centre_id, line_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (year, centre_id, line_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(*, year: str | None = None, centre_id: int | None = None,
            line_id: int | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM budget_audit", [], []
    for col, val in (("year_label", year), ("centre_id", centre_id), ("line_id", line_id)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "year": r["year_label"], "centre_id": r["centre_id"],
                 "line_id": r["line_id"], "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Cleaning ─────────────────────────────────────────────────────────

def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


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
    return (" ".join(str(value or "").split())[:limit]) or None


def staff_usernames() -> dict[str, str]:
    """{username (lower case): display name} of active staff logins."""
    return {s["username"].lower(): s["display_name"] for s in accounts.staff_logins()}


def staff_name(username: str | None) -> str:
    if not username:
        return ""
    try:
        return staff_usernames().get(username.lower(), username)
    except Exception:  # noqa: BLE001 - a name is a nicety
        return username


def _holder(value: Any, problems: list[str]) -> str | None:
    v = str(value or "").strip()
    if not v:
        return None
    if " (" in v and v.endswith(")"):     # "Ann Teacher (ann)" from a drop-down
        v = v.rsplit(" (", 1)[1][:-1]
    known = {s["username"].lower(): s["username"] for s in accounts.staff_logins()}
    if v.lower() not in known:
        problems.append(f"The holder must be a member of staff with a login (no '{v}')")
        return None
    return known[v.lower()]


# ── Settings ─────────────────────────────────────────────────────────

def settings() -> dict[str, int]:
    with database.connect() as conn:
        saved = dict(conn.execute("SELECT key, value FROM budget_settings").fetchall())
    return {k: int(saved.get(k, v)) for k, v in DEFAULTS.items()}


def set_settings(changes: dict[str, Any], *, actor: Principal) -> dict[str, int]:
    _require_editor(actor, "settings")
    problems, clean = [], {}
    for k, v in changes.items():
        if k not in DEFAULTS:
            problems.append(f"Unknown setting {k}")
            continue
        lo, hi, label = _LIMITS[k]
        if isinstance(v, str) and v in YEAR_START_PRESETS:
            v = YEAR_START_PRESETS[v]
        try:
            n = int(str(v).strip())
        except (TypeError, ValueError):
            n = lo - 1
        if not lo <= n <= hi:
            problems.append(f"{label} must be from {lo} to {hi}")
        clean[k] = n
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.executemany("INSERT INTO budget_settings (key, value) VALUES (?, ?) ON CONFLICT "
                         "(key) DO UPDATE SET value = excluded.value", list(clean.items()))
        _audit(conn, "settings", actor, **clean)
    activity_log.record("budgets.settings", principal=actor, fields=",".join(clean))
    return settings()


# ── Financial years ──────────────────────────────────────────────────

def label_for_start(start: _dt.date) -> str:
    """'2026-27' for a year starting in 2026 (or '2026' for a January start)."""
    return str(start.year) if start.month == 1 else f"{start.year}-{(start.year + 1) % 100:02d}"


def year_bounds(start_year: int, start_month: int | None = None) -> tuple[_dt.date, _dt.date]:
    m = start_month or settings()["year_start_month"]
    start = _dt.date(int(start_year), m, 1)
    nxt = _dt.date(start.year + 1, m, 1)
    return start, nxt - _dt.timedelta(days=1)


def year_start_for(day: _dt.date | None = None) -> int:
    """The calendar year in which the financial year holding *day* starts."""
    d = day or _today()
    m = settings()["year_start_month"]
    return d.year if d.month >= m else d.year - 1


def _year_row(conn, label: str):
    return conn.execute("SELECT * FROM budget_years WHERE year_label = ?", (label,)).fetchone()


def get_year(label: str) -> Year:
    with database.connect() as conn:
        r = _year_row(conn, str(label))
    if r is None:
        raise NotFound(f"No financial year {label}")
    return _make(Year, r)


def list_years() -> list[Year]:
    with database.connect() as conn:
        return [_make(Year, r) for r in conn.execute(
            "SELECT * FROM budget_years ORDER BY start_date DESC")]


def year_of_date(day: str | _dt.date) -> Year | None:
    """The recorded financial year holding *day*, if any."""
    iso = day.isoformat() if isinstance(day, _dt.date) else str(day)
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM budget_years WHERE start_date <= ? AND end_date >= ? "
                         "ORDER BY start_date DESC LIMIT 1", (iso, iso)).fetchone()
    return _make(Year, r) if r else None


def current_year_label() -> str | None:
    """The year holding today, else the newest year, else None."""
    y = year_of_date(_today())
    if y:
        return y.year_label
    ys = list_years()
    return ys[0].year_label if ys else None


def create_year(start_year: int | str | None = None, *, actor: Principal) -> Year:
    """Add a financial year starting in *start_year* (default: the one
    holding today) on the configured start month."""
    _require_editor(actor, "year_create")
    try:
        sy = int(str(start_year).strip()[:4]) if start_year not in (None, "") \
            else year_start_for()
    except ValueError:
        raise ValidationError(["Start year must be a year, e.g. 2026"]) from None
    if not 2000 <= sy <= 2100:
        raise ValidationError(["Start year must be between 2000 and 2100"])
    start, end = year_bounds(sy)
    label = label_for_start(start)
    with database.connect() as conn:
        if _year_row(conn, label):
            raise ValidationError([f"Financial year {label} already exists"])
        clash = conn.execute("SELECT year_label FROM budget_years WHERE start_date <= ? AND "
                             "end_date >= ?", (end.isoformat(), start.isoformat())).fetchone()
        if clash:
            raise ValidationError([f"Those dates overlap financial year {clash[0]}"])
        conn.execute("INSERT INTO budget_years (year_label, start_date, end_date, created_by) "
                     "VALUES (?, ?, ?, ?)", (label, start.isoformat(), end.isoformat(),
                                             actor.username))
        _audit(conn, "year_create", actor, year=label, start=start.isoformat())
    activity_log.record("budgets.year_create", target=label, principal=actor)
    return get_year(label)


def set_year_status(label: str, status: str, *, actor: Principal) -> Year:
    """Close a year (no more changes, orders or spend) or reopen it."""
    _require_editor(actor, "year_status", label)
    y = get_year(label)
    problems: list[str] = []
    st = _choice(status, YEAR_STATUSES, "Status", problems, None)
    if problems or not st:
        raise ValidationError(problems or ["Choose Open or Closed"])
    if st == y.status:
        return y
    with database.connect() as conn:
        if st == "Closed":
            n = conn.execute(
                "SELECT COUNT(*) FROM budget_commitments m JOIN budget_lines l USING (line_id) "
                "JOIN budget_cost_centres c USING (centre_id) WHERE c.year_label = ? AND "
                "m.status = 'Open'", (label,)).fetchone()[0]
            if n:
                raise ValidationError([f"{n} order(s) are still open in {label} - settle or "
                                       "cancel them first"])
            n = conn.execute(
                "SELECT COUNT(*) FROM budget_virements v JOIN budget_lines l ON l.line_id = "
                "v.from_line_id JOIN budget_cost_centres c USING (centre_id) WHERE "
                "c.year_label = ? AND v.status = 'Pending'", (label,)).fetchone()[0]
            if n:
                raise ValidationError([f"{n} virement(s) are waiting for a decision"])
        conn.execute("UPDATE budget_years SET status = ? WHERE year_label = ?", (st, label))
        _audit(conn, "year_status", actor, year=label, status=st)
    activity_log.record("budgets.year_status", target=label, principal=actor, status=st)
    return get_year(label)


def _require_open_year(label: str, problems: list[str]) -> None:
    y = get_year(label)
    if not y.is_open:
        problems.append(f"Financial year {label} is closed")


# ── Cost centres ─────────────────────────────────────────────────────

def get_centre(centre_id: int) -> CostCentre:
    with database.connect() as conn:
        r = conn.execute(_CENTRE_SELECT + " WHERE c.centre_id = ?", (int(centre_id),)).fetchone()
    if r is None:
        raise NotFound(f"No cost centre #{centre_id}")
    return _make(CostCentre, r)


def list_centres(year: str | None = None, *, actor: Principal | None = None,
                 holder: str | None = None, kind: str | None = None,
                 include_inactive: bool = True) -> list[CostCentre]:
    """Cost centres by name. With *actor*, only those they may see."""
    where, params = [], []
    if year:
        where.append("c.year_label = ?")
        params.append(year)
    if holder:
        where.append("lower(c.holder) = lower(?)")
        params.append(holder)
    if kind:
        where.append("c.kind = ?")
        params.append(kind)
    if not include_inactive:
        where.append("c.active = 1")
    sql = _CENTRE_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY c.year_label DESC, lower(c.name)"
    with database.connect() as conn:
        rows = [_make(CostCentre, r) for r in conn.execute(sql, params)]
    if actor is not None:
        _require_staff(actor, "list")
        rows = [c for c in rows if can_view(actor, c)]
    return rows


def centre_names(year: str | None = None) -> list[str]:
    """Cost centre names (no amounts) - for drop-downs anywhere."""
    return [c.name for c in list_centres(year, include_inactive=False)]


_CENTRE_FIELDS = ("name", "kind", "holder", "notes", "active")


def _clean_centre(data: dict[str, Any], cur: CostCentre | None
                  ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(cur, k) for k in _CENTRE_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in _CENTRE_FIELDS})
    out: dict[str, Any] = {}
    out["name"] = _text(merged.get("name"), 80)
    if not out["name"]:
        problems.append("Name is required")
    out["kind"] = _choice(merged.get("kind"), CENTRE_KINDS, "Type", problems, DEFAULT_KIND)
    out["holder"] = _holder(merged.get("holder"), problems) if "holder" in data or not cur \
        else merged.get("holder")
    out["notes"] = _text(merged.get("notes"), 1000)
    a = merged.get("active", 1)
    out["active"] = 0 if str(a).strip().lower() in ("0", "false", "no", "") else 1
    return out, problems


def create_centre(data: dict[str, Any], *, actor: Principal) -> CostCentre:
    """A cost centre in ``data['year']`` (default: the current year)."""
    _require_editor(actor, "centre_create")
    year = str(data.get("year") or data.get("year_label") or current_year_label() or "")
    if not year:
        raise ValidationError(["Set up a financial year first"])
    c, problems = _clean_centre(data, None)
    _require_open_year(year, problems)
    with database.connect() as conn:
        if c["name"] and conn.execute(
                "SELECT 1 FROM budget_cost_centres WHERE year_label = ? AND lower(name) = "
                "lower(?)", (year, c["name"])).fetchone():
            problems.append(f"There is already a cost centre called {c['name']} in {year}")
        if problems:
            raise ValidationError(problems)
        cid = conn.execute(
            "INSERT INTO budget_cost_centres (year_label, name, kind, holder, notes, active, "
            "created_by, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (year, c["name"], c["kind"], c["holder"], c["notes"], c["active"], actor.username,
             actor.username)).lastrowid
        _audit(conn, "centre_create", actor, year=year, centre_id=cid, holder=c["holder"])
    activity_log.record("budgets.centre_create", target=cid, principal=actor, year=year)
    return get_centre(cid)


def update_centre(centre_id: int, changes: dict[str, Any], *, actor: Principal) -> CostCentre:
    cur = get_centre(centre_id)
    _require_editor(actor, "centre_update", cur.centre_id)
    c, problems = _clean_centre(changes, cur)
    _require_open_year(cur.year_label, problems)
    changed = [k for k in _CENTRE_FIELDS if c[k] != getattr(cur, k)]
    with database.connect() as conn:
        if "name" in changed and conn.execute(
                "SELECT 1 FROM budget_cost_centres WHERE year_label = ? AND lower(name) = "
                "lower(?) AND centre_id != ?", (cur.year_label, c["name"], cur.centre_id)
        ).fetchone():
            problems.append(f"There is already a cost centre called {c['name']}")
        if problems:
            raise ValidationError(problems)
        if not changed:
            return cur
        conn.execute("UPDATE budget_cost_centres SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE centre_id = ?",
                     (*(c[k] for k in changed), actor.username, cur.centre_id))
        _audit(conn, "centre_update", actor, year=cur.year_label, centre_id=cur.centre_id,
               fields=changed)
    activity_log.record("budgets.centre_update", target=cur.centre_id, principal=actor,
                        fields=",".join(changed))
    return get_centre(cur.centre_id)


def _line_used(conn, line_id: int) -> list[str]:
    out = []
    for table, what in (("budget_spend", "spend"), ("budget_commitments", "orders")):
        if conn.execute(f"SELECT 1 FROM {table} WHERE line_id = ? LIMIT 1",  # nosec B608 - fixed names
                        (line_id,)).fetchone():
            out.append(what)
    if conn.execute("SELECT 1 FROM budget_virements WHERE from_line_id = ? OR to_line_id = ? "
                    "LIMIT 1", (line_id, line_id)).fetchone():
        out.append("virements")
    has_claims = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = "
                              "'expense_claims'").fetchone()
    if has_claims and conn.execute("SELECT 1 FROM expense_claims WHERE budget_line_id = ? "
                                   "LIMIT 1", (line_id,)).fetchone():
        out.append("expense claims")
    return out


def delete_centre(centre_id: int, *, actor: Principal) -> bool:
    """Delete a cost centre and its lines - only while nothing has been
    spent, ordered, vired or claimed against them (otherwise make it
    inactive)."""
    c = get_centre(centre_id)
    _require_editor(actor, "centre_delete", c.centre_id)
    problems: list[str] = []
    _require_open_year(c.year_label, problems)
    with database.connect() as conn:
        for r in conn.execute("SELECT line_id, code FROM budget_lines WHERE centre_id = ?",
                              (c.centre_id,)).fetchall():
            used = _line_used(conn, r["line_id"])
            if used:
                problems.append(f"Line {r['code']} has {', '.join(used)} - make the cost "
                                "centre inactive instead")
        if problems:
            raise ValidationError(problems)
        conn.execute("DELETE FROM budget_lines WHERE centre_id = ?", (c.centre_id,))
        conn.execute("DELETE FROM budget_cost_centres WHERE centre_id = ?", (c.centre_id,))
        _audit(conn, "centre_delete", actor, year=c.year_label, centre_id=c.centre_id)
    activity_log.record("budgets.centre_delete", target=c.centre_id, principal=actor)
    return True


# ── Budget lines ─────────────────────────────────────────────────────

def get_line(line_id: int) -> Line:
    with database.connect() as conn:
        r = conn.execute(_LINE_SELECT + " WHERE l.line_id = ?", (int(line_id),)).fetchone()
    if r is None:
        raise NotFound(f"No budget line #{line_id}")
    return _make(Line, r)


def list_lines(*, year: str | None = None, centre_id: int | None = None,
               actor: Principal | None = None) -> list[Line]:
    where, params = [], []
    if year:
        where.append("c.year_label = ?")
        params.append(year)
    if centre_id is not None:
        where.append("l.centre_id = ?")
        params.append(int(centre_id))
    sql = _LINE_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY lower(c.name), l.code"
    with database.connect() as conn:
        rows = [_make(Line, r) for r in conn.execute(sql, params)]
    if actor is not None:
        _require_staff(actor, "list")
        rows = [r for r in rows if can_view(actor, r)]
    return rows


def find_line(code: str, year: str | None = None) -> Line | None:
    """A line by its code in *year* (default: current)."""
    y = year or current_year_label()
    with database.connect() as conn:
        r = conn.execute(_LINE_SELECT + " WHERE c.year_label = ? AND lower(l.code) = lower(?)",
                         (y, str(code).strip())).fetchone()
    return _make(Line, r) if r else None


def codes_for_claims(year: str | None = None) -> list[dict[str, Any]]:
    """Budget codes anyone on the staff may charge a claim to (no amounts):
    [{'line_id', 'code', 'description', 'centre', 'label'}] in open years,
    active cost centres."""
    where = "c.active = 1 AND y.status = 'Open'"
    params: list[Any] = []
    if year:
        where += " AND c.year_label = ?"
        params.append(year)
    with database.connect() as conn:
        rows = conn.execute(
            _LINE_SELECT + " JOIN budget_years y ON y.year_label = c.year_label WHERE " + where
            + " ORDER BY c.year_label DESC, lower(c.name), l.code", params).fetchall()
    return [{"line_id": r["line_id"], "code": r["code"], "description": r["description"],
             "centre": r["centre_name"], "year": r["year_label"],
             "label": f"{r['code']} - {r['centre_name']}: {r['description']} ({r['year_label']})"}
            for r in rows]


def _clean_line(data: dict[str, Any], cur: Line | None) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    out: dict[str, Any] = {}
    code = str(data.get("code", cur.code if cur else "") or "").strip().upper()
    if not code:
        problems.append("Code is required")
    elif len(code) > 30 or not all(ch.isalnum() or ch in "-_/." for ch in code):
        problems.append("Code must be up to 30 letters, digits, - _ / or .")
    out["code"] = code
    out["description"] = _text(data.get("description", cur.description if cur else ""), 200)
    if not out["description"]:
        problems.append("Description is required")
    if "allocation" in data or "allocation_pence" in data or cur is None:
        raw = data.get("allocation", data.get("allocation_pence"))
        out["allocation_pence"] = to_pence(raw if raw not in (None, "") else 0, "Allocation",
                                           problems)
    else:
        out["allocation_pence"] = cur.allocation_pence
    out["notes"] = _text(data.get("notes", cur.notes if cur else ""), 1000)
    return out, problems


def _code_taken(conn, year: str, code: str, skip: int | None = None) -> bool:
    return conn.execute(
        "SELECT 1 FROM budget_lines l JOIN budget_cost_centres c USING (centre_id) WHERE "
        "c.year_label = ? AND lower(l.code) = lower(?) AND l.line_id != ?",
        (year, code, skip or 0)).fetchone() is not None


def create_line(centre_id: int, data: dict[str, Any], *, actor: Principal) -> Line:
    c = get_centre(centre_id)
    _require_editor(actor, "line_create", c.centre_id)
    ln, problems = _clean_line(data, None)
    _require_open_year(c.year_label, problems)
    with database.connect() as conn:
        if ln["code"] and _code_taken(conn, c.year_label, ln["code"]):
            problems.append(f"Code {ln['code']} is already used in {c.year_label}")
        if problems:
            raise ValidationError(problems)
        lid = conn.execute(
            "INSERT INTO budget_lines (centre_id, code, description, allocation_pence, notes, "
            "created_by, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (c.centre_id, ln["code"], ln["description"], ln["allocation_pence"], ln["notes"],
             actor.username, actor.username)).lastrowid
        _audit(conn, "line_create", actor, year=c.year_label, centre_id=c.centre_id,
               line_id=lid, allocation=ln["allocation_pence"])
    activity_log.record("budgets.line_create", target=lid, principal=actor)
    return get_line(lid)


def update_line(line_id: int, changes: dict[str, Any], *, actor: Principal) -> Line:
    cur = get_line(line_id)
    _require_editor(actor, "line_update", cur.line_id)
    ln, problems = _clean_line(changes, cur)
    _require_open_year(cur.year_label, problems)
    changed = [k for k in ("code", "description", "allocation_pence", "notes")
               if ln[k] != getattr(cur, k)]
    with database.connect() as conn:
        if "code" in changed and _code_taken(conn, cur.year_label, ln["code"], cur.line_id):
            problems.append(f"Code {ln['code']} is already used in {cur.year_label}")
        if problems:
            raise ValidationError(problems)
        if not changed:
            return cur
        conn.execute("UPDATE budget_lines SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE line_id = ?",
                     (*(ln[k] for k in changed), actor.username, cur.line_id))
        _audit(conn, "line_update", actor, year=cur.year_label, centre_id=cur.centre_id,
               line_id=cur.line_id, fields=changed,
               **({"allocation_from": cur.allocation_pence, "allocation_to":
                   ln["allocation_pence"]} if "allocation_pence" in changed else {}))
    activity_log.record("budgets.line_update", target=cur.line_id, principal=actor,
                        fields=",".join(changed))
    return get_line(cur.line_id)


def delete_line(line_id: int, *, actor: Principal) -> bool:
    ln = get_line(line_id)
    _require_editor(actor, "line_delete", ln.line_id)
    problems: list[str] = []
    _require_open_year(ln.year_label, problems)
    with database.connect() as conn:
        used = _line_used(conn, ln.line_id)
        if used:
            problems.append(f"Line {ln.code} has {', '.join(used)} - it can't be deleted")
        if problems:
            raise ValidationError(problems)
        conn.execute("DELETE FROM budget_lines WHERE line_id = ?", (ln.line_id,))
        _audit(conn, "line_delete", actor, year=ln.year_label, centre_id=ln.centre_id,
               line_id=ln.line_id, code=ln.code)
    activity_log.record("budgets.line_delete", target=ln.line_id, principal=actor)
    return True


# ── Positions ────────────────────────────────────────────────────────

_POSITION_SQL = """
SELECT l.line_id, l.code, l.description, l.centre_id, c.name AS centre_name, c.holder,
       c.year_label, l.allocation_pence AS allocation,
       COALESCE((SELECT SUM(amount_pence) FROM budget_virements v WHERE v.to_line_id = l.line_id
                 AND v.status = 'Approved'), 0) AS virements_in,
       COALESCE((SELECT SUM(amount_pence) FROM budget_virements v
                 WHERE v.from_line_id = l.line_id AND v.status = 'Approved'), 0) AS virements_out,
       COALESCE((SELECT SUM(amount_pence) FROM budget_commitments m WHERE m.line_id = l.line_id
                 AND m.status = 'Open'), 0) AS committed,
       COALESCE((SELECT SUM(amount_pence) FROM budget_spend s WHERE s.line_id = l.line_id), 0)
           AS spent
FROM budget_lines l JOIN budget_cost_centres c USING (centre_id)
"""


def positions(year: str | None = None, *, centre_id: int | None = None,
              line_id: int | None = None, actor: Principal | None = None) -> list[Position]:
    where, params = [], []
    for col, val in (("c.year_label", year), ("l.centre_id", centre_id),
                     ("l.line_id", line_id)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    sql = _POSITION_SQL + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY lower(c.name), l.code"
    with database.connect() as conn:
        rows = [_make(Position, r) for r in conn.execute(sql, params)]
    if actor is not None:
        _require_staff(actor, "positions")
        rows = [p for p in rows if can_view(actor, p)]
    return rows


def position(line_id: int) -> Position:
    rows = positions(line_id=int(line_id))
    if not rows:
        raise NotFound(f"No budget line #{line_id}")
    return rows[0]


def centre_totals(year: str, *, actor: Principal | None = None) -> list[dict[str, Any]]:
    """Per cost centre: {'centre_id', 'name', 'holder', 'budget', 'committed', 'spent',
    'remaining', 'over'} (pence)."""
    out: dict[int, dict[str, Any]] = {}
    for p in positions(year, actor=actor):
        t = out.setdefault(p.centre_id, {"centre_id": p.centre_id, "name": p.centre_name,
                                         "holder": p.holder, "budget": 0, "committed": 0,
                                         "spent": 0, "remaining": 0, "over": 0})
        t["budget"] += p.budget
        t["committed"] += p.committed
        t["spent"] += p.spent
        t["remaining"] += p.remaining
        t["over"] += 1 if p.remaining < 0 else 0
    return list(out.values())


def overspends(year: str | None = None, *, actor: Principal | None = None
               ) -> list[tuple[Position, str]]:
    """Lines over budget or past the warning percentage, worst first."""
    warn = settings()["warn_percent"]
    rows = [(p, p.state(warn)) for p in positions(year or current_year_label(), actor=actor)]
    rows = [x for x in rows if x[1] != "ok"]
    return sorted(rows, key=lambda x: (x[1] != "over", x[0].remaining))


def check_spend(line_id: int, amount_pence: int) -> list[str]:
    """Warnings for adding *amount_pence* of spend or orders to a line."""
    p = position(line_id)
    after = p.remaining - int(amount_pence)
    warn = settings()["warn_percent"]
    out: list[str] = []
    if after < 0:
        out.append(f"This takes {p.code} over budget by {money(-after)} "
                   f"(remaining now {money(p.remaining)}).")
    elif p.budget > 0 and (p.committed + p.spent + amount_pence) * 100 >= warn * p.budget:
        out.append(f"{p.code} will have used {((p.committed + p.spent + amount_pence) * 100) // p.budget}% "
                   f"of its budget (warning at {warn}%).")
    return out


# ── Virements ────────────────────────────────────────────────────────

def get_virement(virement_id: int) -> Virement:
    with database.connect() as conn:
        r = conn.execute(_VIREMENT_SELECT + " WHERE v.virement_id = ?",
                         (int(virement_id),)).fetchone()
    if r is None:
        raise NotFound(f"No virement #{virement_id}")
    return _make(Virement, r)


def list_virements(year: str | None = None, *, status: str | None = None,
                   actor: Principal | None = None) -> list[Virement]:
    where, params = [], []
    if year:
        where.append("fc.year_label = ?")
        params.append(year)
    if status:
        where.append("v.status = ?")
        params.append(status)
    sql = _VIREMENT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY v.virement_id DESC"
    with database.connect() as conn:
        rows = [_make(Virement, r) for r in conn.execute(sql, params)]
    if actor is not None and not is_editor(actor):
        _require_staff(actor, "virements")
        mine = {ln.line_id for ln in list_lines(year=year, actor=actor)}
        rows = [v for v in rows if v.from_line_id in mine or v.to_line_id in mine
                or v.requested_by.lower() == (actor.username or "").lower()]
    return rows


def request_virement(data: dict[str, Any], *, actor: Principal) -> Virement:
    """Ask to move budget: ``from_line_id``, ``to_line_id``, ``amount``, ``reason``."""
    problems: list[str] = []
    try:
        src = get_line(int(str(data.get("from_line_id") or "").strip()))
        dst = get_line(int(str(data.get("to_line_id") or "").strip()))
    except ValueError:
        raise ValidationError(["Choose the line to move from and the line to move to"]) \
            from None
    _require_holder_or_editor(actor, src, "virement_request")
    amount = to_pence(data.get("amount", data.get("amount_pence")), "Amount", problems,
                      allow_zero=False)
    reason = _text(data.get("reason"), 500)
    if not reason:
        problems.append("Give a reason for the virement")
    if src.line_id == dst.line_id:
        problems.append("Choose two different lines")
    if src.year_label != dst.year_label:
        problems.append("Both lines must be in the same financial year")
    _require_open_year(src.year_label, problems)
    if amount and not problems:
        rem = position(src.line_id).remaining
        if amount > rem:
            problems.append(f"{src.code} has only {money(rem)} left to move")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        vid = conn.execute(
            "INSERT INTO budget_virements (from_line_id, to_line_id, amount_pence, reason, "
            "requested_by) VALUES (?, ?, ?, ?, ?)",
            (src.line_id, dst.line_id, amount, reason, actor.username)).lastrowid
        _audit(conn, "virement_request", actor, year=src.year_label, line_id=src.line_id,
               virement=vid, to_line=dst.line_id, amount=amount)
    activity_log.record("budgets.virement_request", target=vid, principal=actor)
    return get_virement(vid)


def can_decide_virement(actor: Principal, v: Virement) -> bool:
    """The holder of the "from" cost centre (their own request too), or a
    budget editor."""
    if actor.role not in STAFF_ROLES:
        return False
    return is_editor(actor) or is_holder(actor, get_line(v.from_line_id))


def decide_virement(virement_id: int, decision: str, *, actor: Principal,
                    note: str | None = None) -> Virement:
    """Approve or reject a pending virement: the "from" cost centre's holder
    (who may decide their own request) or a budget editor (who may not)."""
    v = get_virement(virement_id)
    if not can_decide_virement(actor, v):
        _deny(actor, "virement_decide", v.virement_id,
              "Only the budget holder or the finance office can decide a virement.")
    own_budget = is_holder(actor, get_line(v.from_line_id))
    problems: list[str] = []
    dec = _choice(decision, ("Approved", "Rejected"), "Decision", problems, None)
    if not dec:
        problems.append("Choose Approved or Rejected")
    if v.status != "Pending":
        problems.append(f"Virement #{v.virement_id} is already {v.status.lower()}")
    if v.requested_by.lower() == (actor.username or "").lower() and not own_budget:
        problems.append("Someone else must decide a virement you asked for "
                        "(unless it is from a budget you hold)")
    note = _text(note, 500)
    if dec == "Rejected" and not note:
        problems.append("Give the reason for rejecting it")
    _require_open_year(v.year_label, problems)
    if dec == "Approved" and not problems:
        rem = position(v.from_line_id).remaining
        if v.amount_pence > rem:
            problems.append(f"{v.from_code} now has only {money(rem)} left - the virement "
                            "would overspend it")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE budget_virements SET status = ?, decided_by = ?, decided_at = "
                     "datetime('now'), decision_note = ? WHERE virement_id = ?",
                     (dec, actor.username, note, v.virement_id))
        _audit(conn, "virement_" + dec.lower(), actor, year=v.year_label,
               line_id=v.from_line_id, virement=v.virement_id)
    activity_log.record("budgets.virement_decide", target=v.virement_id, principal=actor,
                        decision=dec)
    return get_virement(v.virement_id)


def cancel_virement(virement_id: int, *, actor: Principal) -> Virement:
    v = get_virement(virement_id)
    if v.requested_by.lower() != (actor.username or "").lower() and not is_editor(actor):
        _deny(actor, "virement_cancel", v.virement_id,
              "Only the person who asked, or the finance office, can cancel it.")
    if v.status != "Pending":
        raise ValidationError([f"Virement #{v.virement_id} is already {v.status.lower()}"])
    with database.connect() as conn:
        conn.execute("UPDATE budget_virements SET status = 'Cancelled', decided_by = ?, "
                     "decided_at = datetime('now') WHERE virement_id = ?",
                     (actor.username, v.virement_id))
        _audit(conn, "virement_cancel", actor, year=v.year_label, line_id=v.from_line_id,
               virement=v.virement_id)
    activity_log.record("budgets.virement_cancel", target=v.virement_id, principal=actor)
    return get_virement(v.virement_id)


# ── Commitments (orders) ─────────────────────────────────────────────

def _in_year(line: Line, day: str, label: str, problems: list[str]) -> None:
    y = get_year(line.year_label)
    if not y.start_date <= day <= y.end_date:
        problems.append(f"{label} must be in financial year {y.year_label} "
                        f"({y.start_date} to {y.end_date})")


def get_commitment(commitment_id: int) -> Commitment:
    with database.connect() as conn:
        r = conn.execute(_COMMIT_SELECT + " WHERE m.commitment_id = ?",
                         (int(commitment_id),)).fetchone()
    if r is None:
        raise NotFound(f"No order #{commitment_id}")
    return _make(Commitment, r)


def list_commitments(*, year: str | None = None, line_id: int | None = None,
                     centre_id: int | None = None, status: str | None = None,
                     actor: Principal | None = None) -> list[Commitment]:
    where, params = [], []
    for col, val in (("c.year_label", year), ("m.line_id", line_id),
                     ("l.centre_id", centre_id), ("m.status", status)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    sql = _COMMIT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY m.raised_on DESC, m.commitment_id DESC"
    with database.connect() as conn:
        rows = [_make(Commitment, r) for r in conn.execute(sql, params)]
    if actor is not None and not is_editor(actor):
        mine = {ln.line_id for ln in list_lines(year=year, actor=actor)}
        rows = [m for m in rows if m.line_id in mine]
    return rows


def add_commitment(line_id: int, data: dict[str, Any], *, actor: Principal) -> Commitment:
    """Raise an order against a line (holder or finance office)."""
    ln = get_line(line_id)
    _require_holder_or_editor(actor, ln, "commitment_add")
    problems: list[str] = []
    amount = to_pence(data.get("amount", data.get("amount_pence")), "Amount", problems,
                      allow_zero=False)
    day = _date(data.get("raised_on"), "Order date", problems) or _today().isoformat()
    desc = _text(data.get("description"), 300)
    if not desc:
        problems.append("Description is required")
    _require_open_year(ln.year_label, problems)
    if not problems:
        _in_year(ln, day, "Order date", problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        mid = conn.execute(
            "INSERT INTO budget_commitments (line_id, raised_on, supplier, description, "
            "order_ref, amount_pence, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ln.line_id, day, _text(data.get("supplier"), 120), desc,
             _text(data.get("order_ref"), 60), amount, actor.username)).lastrowid
        _audit(conn, "commitment_add", actor, year=ln.year_label, centre_id=ln.centre_id,
               line_id=ln.line_id, commitment=mid, amount=amount)
    activity_log.record("budgets.commitment_add", target=mid, principal=actor)
    return get_commitment(mid)


def cancel_commitment(commitment_id: int, *, actor: Principal) -> Commitment:
    m = get_commitment(commitment_id)
    ln = get_line(m.line_id)
    _require_holder_or_editor(actor, ln, "commitment_cancel")
    problems: list[str] = []
    if m.status != "Open":
        problems.append(f"Order #{m.commitment_id} is already {m.status.lower()}")
    _require_open_year(ln.year_label, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE budget_commitments SET status = 'Cancelled', closed_on = ? "
                     "WHERE commitment_id = ?", (_today().isoformat(), m.commitment_id))
        _audit(conn, "commitment_cancel", actor, year=ln.year_label, line_id=ln.line_id,
               commitment=m.commitment_id)
    activity_log.record("budgets.commitment_cancel", target=m.commitment_id, principal=actor)
    return get_commitment(m.commitment_id)


def settle_commitment(commitment_id: int, *, actor: Principal, amount: Any = None,
                      paid_on: str | None = None, reference: str | None = None) -> Spend:
    """The invoice is paid: the order becomes spend (at *amount*, default the
    order value) and stops being a commitment. Finance office only."""
    m = get_commitment(commitment_id)
    ln = get_line(m.line_id)
    _require_editor(actor, "commitment_settle", m.commitment_id)
    problems: list[str] = []
    paid = to_pence(amount if amount not in (None, "") else m.amount_pence, "Amount paid",
                    problems, allow_zero=False)
    day = _date(paid_on, "Paid on", problems) or _today().isoformat()
    if m.status != "Open":
        problems.append(f"Order #{m.commitment_id} is already {m.status.lower()}")
    _require_open_year(ln.year_label, problems)
    if not problems:
        _in_year(ln, day, "Paid on", problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE budget_commitments SET status = 'Paid', closed_on = ? WHERE "
                     "commitment_id = ?", (day, m.commitment_id))
        sid = conn.execute(
            "INSERT INTO budget_spend (line_id, spend_date, description, supplier, reference, "
            "amount_pence, source, source_id, created_by) VALUES (?, ?, ?, ?, ?, ?, "
            "'commitment', ?, ?)",
            (ln.line_id, day, m.description, m.supplier, _text(reference, 60) or m.order_ref,
             paid, m.commitment_id, actor.username)).lastrowid
        _audit(conn, "commitment_settle", actor, year=ln.year_label, line_id=ln.line_id,
               commitment=m.commitment_id, spend=sid, amount=paid)
    activity_log.record("budgets.commitment_settle", target=m.commitment_id, principal=actor)
    return get_spend(sid)


# ── Spend ────────────────────────────────────────────────────────────

def get_spend(spend_id: int) -> Spend:
    with database.connect() as conn:
        r = conn.execute(_SPEND_SELECT + " WHERE s.spend_id = ?", (int(spend_id),)).fetchone()
    if r is None:
        raise NotFound(f"No spend entry #{spend_id}")
    return _make(Spend, r)


def list_spend(*, year: str | None = None, line_id: int | None = None,
               centre_id: int | None = None, source: str | None = None,
               date_from: str | None = None, date_to: str | None = None,
               actor: Principal | None = None) -> list[Spend]:
    where, params = [], []
    for col, val in (("c.year_label", year), ("s.line_id", line_id),
                     ("l.centre_id", centre_id), ("s.source", source)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if date_from:
        where.append("s.spend_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("s.spend_date <= ?")
        params.append(date_to)
    sql = _SPEND_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY s.spend_date DESC, s.spend_id DESC"
    with database.connect() as conn:
        rows = [_make(Spend, r) for r in conn.execute(sql, params)]
    if actor is not None and not is_editor(actor):
        mine = {ln.line_id for ln in list_lines(year=year, actor=actor)}
        rows = [s for s in rows if s.line_id in mine]
    return rows


def add_spend(line_id: int, data: dict[str, Any], *, actor: Principal) -> Spend:
    """Record actual spend by hand (finance office). A negative amount is a
    refund or credit note."""
    ln = get_line(line_id)
    _require_editor(actor, "spend_add", ln.line_id)
    problems: list[str] = []
    amount = to_pence(data.get("amount", data.get("amount_pence")), "Amount", problems,
                      allow_negative=True, allow_zero=False)
    day = _date(data.get("spend_date"), "Date", problems) or _today().isoformat()
    desc = _text(data.get("description"), 300)
    if not desc:
        problems.append("Description is required")
    _require_open_year(ln.year_label, problems)
    if not problems:
        _in_year(ln, day, "Date", problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        sid = conn.execute(
            "INSERT INTO budget_spend (line_id, spend_date, description, supplier, reference, "
            "amount_pence, source, created_by) VALUES (?, ?, ?, ?, ?, ?, 'manual', ?)",
            (ln.line_id, day, desc, _text(data.get("supplier"), 120),
             _text(data.get("reference"), 60), amount, actor.username)).lastrowid
        _audit(conn, "spend_add", actor, year=ln.year_label, centre_id=ln.centre_id,
               line_id=ln.line_id, spend=sid, amount=amount)
    activity_log.record("budgets.spend_add", target=sid, principal=actor)
    return get_spend(sid)


def delete_spend(spend_id: int, *, actor: Principal) -> bool:
    """Remove a hand-entered spend line (claims and settled orders are
    reversed at source, not deleted here)."""
    s = get_spend(spend_id)
    ln = get_line(s.line_id)
    _require_editor(actor, "spend_delete", s.spend_id)
    problems: list[str] = []
    if s.source != "manual":
        problems.append("This came from an expense claim or an order - change it there")
    _require_open_year(ln.year_label, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("DELETE FROM budget_spend WHERE spend_id = ?", (s.spend_id,))
        _audit(conn, "spend_delete", actor, year=ln.year_label, line_id=ln.line_id,
               spend=s.spend_id, amount=s.amount_pence)
    activity_log.record("budgets.spend_delete", target=s.spend_id, principal=actor)
    return True


def post_claim(conn, *, claim_id: int, line_id: int, amount_pence: int, day: str,
               description: str, reference: str | None, actor: Principal) -> int:
    """Post an approved expense claim as spend, inside the caller's
    transaction (used by :mod:`.expense_claims`). Returns the spend id."""
    r = conn.execute("SELECT c.year_label, y.status, y.start_date, y.end_date, l.centre_id "
                     "FROM budget_lines l JOIN budget_cost_centres c USING (centre_id) "
                     "JOIN budget_years y ON y.year_label = c.year_label WHERE l.line_id = ?",
                     (int(line_id),)).fetchone()
    if r is None:
        raise ValidationError(["The claim's budget code no longer exists"])
    if r["status"] != "Open":
        raise ValidationError([f"Financial year {r['year_label']} is closed - choose a budget "
                               "code in an open year"])
    posted = conn.execute("SELECT COALESCE(SUM(amount_pence), 0) FROM budget_spend WHERE "
                          "source = 'expense_claim' AND source_id = ?", (claim_id,)).fetchone()[0]
    if posted:
        raise ValidationError([f"Claim #{claim_id} is already posted to the budget"])
    when = min(max(day, r["start_date"]), r["end_date"])
    sid = conn.execute(
        "INSERT INTO budget_spend (line_id, spend_date, description, reference, amount_pence, "
        "source, source_id, created_by) VALUES (?, ?, ?, ?, ?, 'expense_claim', ?, ?)",
        (int(line_id), when, description[:300], reference, int(amount_pence), claim_id,
         actor.username)).lastrowid
    _audit(conn, "claim_post", actor, year=r["year_label"], centre_id=r["centre_id"],
           line_id=int(line_id), claim=claim_id, spend=sid)
    return int(sid)


def reverse_claim(conn, *, claim_id: int, actor: Principal, day: str | None = None) -> int | None:
    """Undo an approved claim's posting with a negative entry (history kept).
    Returns the reversal's spend id, or None if nothing was posted."""
    rows = conn.execute("SELECT line_id, COALESCE(SUM(amount_pence), 0) AS net FROM budget_spend "
                        "WHERE source = 'expense_claim' AND source_id = ? GROUP BY line_id",
                        (claim_id,)).fetchall()
    sid = None
    for r in rows:
        if not r["net"]:
            continue
        y = conn.execute("SELECT y.* FROM budget_lines l JOIN budget_cost_centres c USING "
                         "(centre_id) JOIN budget_years y ON y.year_label = c.year_label "
                         "WHERE l.line_id = ?", (r["line_id"],)).fetchone()
        if y["status"] != "Open":
            raise ValidationError([f"Financial year {y['year_label']} is closed - the claim's "
                                   "spend can't be reversed"])
        when = min(max(day or _today().isoformat(), y["start_date"]), y["end_date"])
        sid = conn.execute(
            "INSERT INTO budget_spend (line_id, spend_date, description, amount_pence, source, "
            "source_id, created_by) VALUES (?, ?, ?, ?, 'expense_claim', ?, ?)",
            (r["line_id"], when, f"Reversal of expense claim #{claim_id}", -int(r["net"]),
             claim_id, actor.username)).lastrowid
        _audit(conn, "claim_reverse", actor, year=y["year_label"], line_id=r["line_id"],
               claim=claim_id, spend=sid)
    return sid


# ── Monthly profile and variance ─────────────────────────────────────

def months(year: str) -> list[str]:
    """The year's twelve months as 'YYYY-MM', in order."""
    y = get_year(year)
    d = _dt.date.fromisoformat(y.start_date)
    out = []
    for i in range(12):
        m = (d.month - 1 + i) % 12 + 1
        yr = d.year + (d.month - 1 + i) // 12
        out.append(f"{yr}-{m:02d}")
    return out


def _split(total: int, weights: list[int]) -> list[int]:
    """Share *total* pence by *weights*, exactly (largest remainders)."""
    s = sum(weights)
    if s <= 0:
        weights, s = [1] * 12, 12
    sign = -1 if total < 0 else 1
    t = abs(total)
    raw = [t * w for w in weights]
    parts = [x // s for x in raw]
    left = t - sum(parts)
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] % s), i))
    for i in order[:left]:
        parts[i] += 1
    return [sign * p for p in parts]


def profile(line_id: int) -> list[int]:
    """The line's budget spread over the twelve months (pence, adds up to
    the budget). Even when no profile is set."""
    p = position(line_id)
    with database.connect() as conn:
        rows = dict(conn.execute("SELECT month, weight FROM budget_profile WHERE line_id = ?",
                                 (p.line_id,)).fetchall())
    weights = [int(rows.get(i, 0)) for i in range(1, 13)] if rows else [1] * 12
    return _split(p.budget, weights)


def has_profile(line_id: int) -> bool:
    with database.connect() as conn:
        return conn.execute("SELECT 1 FROM budget_profile WHERE line_id = ? LIMIT 1",
                            (int(line_id),)).fetchone() is not None


def set_profile(line_id: int, amounts: list[Any] | None, *, actor: Principal) -> list[int]:
    """Set the monthly profile from twelve amounts (pounds text or pence).
    They are kept as weights, so the profile follows the budget after a
    virement. ``None`` clears it (even spread)."""
    ln = get_line(line_id)
    _require_editor(actor, "profile", ln.line_id)
    problems: list[str] = []
    _require_open_year(ln.year_label, problems)
    weights: list[int] = []
    if amounts is not None:
        if len(amounts) != 12:
            problems.append("Give an amount for each of the 12 months")
        else:
            for i, a in enumerate(amounts, 1):
                n = to_pence(a if a not in (None, "") else 0, f"Month {i}", problems)
                weights.append(n or 0)
            if not problems and sum(weights) <= 0:
                problems.append("The months can't all be zero")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("DELETE FROM budget_profile WHERE line_id = ?", (ln.line_id,))
        if weights:
            conn.executemany("INSERT INTO budget_profile (line_id, month, weight) VALUES "
                             "(?, ?, ?)", [(ln.line_id, i, w) for i, w in enumerate(weights, 1)])
        _audit(conn, "profile", actor, year=ln.year_label, line_id=ln.line_id,
               cleared=not weights)
    activity_log.record("budgets.profile", target=ln.line_id, principal=actor)
    return profile(ln.line_id)


def variance(year: str, *, line_id: int | None = None, centre_id: int | None = None,
             actor: Principal | None = None) -> list[dict[str, Any]]:
    """Month by month: {'month', 'profiled', 'actual', 'variance', 'cum_profiled',
    'cum_actual', 'cum_variance'} (pence; variance = profiled - actual, so
    negative means spending ahead of profile)."""
    lines = positions(year, centre_id=centre_id, line_id=line_id, actor=actor)
    ms = months(year)
    prof = [0] * 12
    for p in lines:
        for i, v in enumerate(profile(p.line_id)):
            prof[i] += v
    ids = {p.line_id for p in lines}
    actual = [0] * 12
    idx = {m: i for i, m in enumerate(ms)}
    for s in list_spend(year=year):
        if s.line_id in ids and s.spend_date[:7] in idx:
            actual[idx[s.spend_date[:7]]] += s.amount_pence
    out, cp, ca = [], 0, 0
    for i, m in enumerate(ms):
        cp += prof[i]
        ca += actual[i]
        out.append({"month": m, "profiled": prof[i], "actual": actual[i],
                    "variance": prof[i] - actual[i], "cum_profiled": cp, "cum_actual": ca,
                    "cum_variance": cp - ca})
    return out


# ── Holder view, export, roll forward ────────────────────────────────

def my_centres(actor: Principal, year: str | None = None) -> list[dict[str, Any]]:
    """The cost centres *actor* holds, with their lines' positions:
    [{'centre': CostCentre, 'lines': [Position], 'budget', 'committed', 'spent',
    'remaining'}]."""
    _require_staff(actor, "mine")
    y = year or current_year_label()
    out = []
    for c in list_centres(y, holder=actor.username):
        ps = positions(y, centre_id=c.centre_id)
        out.append({"centre": c, "lines": ps, "budget": sum(p.budget for p in ps),
                    "committed": sum(p.committed for p in ps),
                    "spent": sum(p.spent for p in ps),
                    "remaining": sum(p.remaining for p in ps)})
    return out


def export_csv(path: str | Path, *, actor: Principal, year: str,
               centre_id: int | None = None) -> int:
    """Lines with their positions (pounds, two decimals)."""
    _require_staff(actor, "export")
    rows = positions(year, centre_id=centre_id, actor=actor)
    warn = settings()["warn_percent"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "cost_centre", "holder", "code", "description", "allocation",
                    "virements_in", "virements_out", "budget", "committed", "spent",
                    "remaining", "used_percent", "state"])
        for p in rows:
            w.writerow([p.year_label, _safe(p.centre_name), _safe(p.holder), _safe(p.code),
                        _safe(p.description), pounds(p.allocation), pounds(p.virements_in),
                        pounds(p.virements_out), pounds(p.budget), pounds(p.committed),
                        pounds(p.spent), pounds(p.remaining), p.used_percent, p.state(warn)])
    activity_log.record("budgets.export", principal=actor, rows=len(rows), year=year)
    return len(rows)


def export_transactions_csv(path: str | Path, *, actor: Principal, year: str,
                            centre_id: int | None = None) -> int:
    """Every spend entry and open order in the year (what the holder can see)."""
    _require_staff(actor, "export")
    spend = list_spend(year=year, centre_id=centre_id, actor=actor)
    orders = list_commitments(year=year, centre_id=centre_id, status="Open", actor=actor)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["type", "id", "date", "cost_centre", "code", "description", "supplier",
                    "reference", "amount", "source"])
        for s in spend:
            w.writerow(["spend", s.spend_id, s.spend_date, _safe(s.centre_name), _safe(s.code),
                        _safe(s.description), _safe(s.supplier), _safe(s.reference),
                        pounds(s.amount_pence), s.source])
        for m in orders:
            w.writerow(["order", m.commitment_id, m.raised_on, _safe(m.centre_name),
                        _safe(m.code), _safe(m.description), _safe(m.supplier),
                        _safe(m.order_ref), pounds(m.amount_pence), "commitment"])
    activity_log.record("budgets.export", principal=actor, rows=len(spend) + len(orders),
                        year=year, kind="transactions")
    return len(spend) + len(orders)


def roll_forward(from_year: str, *, actor: Principal, uplift_percent: Any = 0,
                 include_profiles: bool = True) -> dict[str, Any]:
    """Copy *from_year*'s active cost centres (with holders), their lines
    (allocation + *uplift_percent*, to the penny) and profiles into the next
    financial year, creating it if needed. Centres already there by name are
    skipped. Returns {'year', 'centres', 'lines', 'skipped'}."""
    _require_editor(actor, "roll_forward", from_year)
    src = get_year(from_year)
    try:
        uplift = Decimal(str(uplift_percent or 0).strip().rstrip("%"))
    except InvalidOperation:
        raise ValidationError(["Uplift must be a percentage, e.g. 2.5"]) from None
    if not Decimal("-100") < uplift <= Decimal("100"):
        raise ValidationError(["Uplift must be between -100% and 100%"])
    next_start = _dt.date.fromisoformat(src.end_date) + _dt.timedelta(days=1)
    with database.connect() as conn:
        target = conn.execute("SELECT year_label FROM budget_years WHERE start_date = ?",
                              (next_start.isoformat(),)).fetchone()
    if target:
        label = target[0]
        if not get_year(label).is_open:
            raise ValidationError([f"Financial year {label} is closed"])
    else:
        nxt_end = _dt.date(next_start.year + 1, next_start.month, 1) - _dt.timedelta(days=1)
        label = label_for_start(next_start)
        with database.connect() as conn:
            if _year_row(conn, label):
                raise ValidationError([f"Financial year {label} exists with other dates"])
            conn.execute("INSERT INTO budget_years (year_label, start_date, end_date, "
                         "created_by) VALUES (?, ?, ?, ?)",
                         (label, next_start.isoformat(), nxt_end.isoformat(), actor.username))
            _audit(conn, "year_create", actor, year=label, rolled_from=from_year)
    centres = lines = 0
    skipped: list[str] = []
    with database.connect() as conn:
        existing = {r[0].lower() for r in conn.execute(
            "SELECT name FROM budget_cost_centres WHERE year_label = ?", (label,))}
        codes = {r[0].lower() for r in conn.execute(
            "SELECT l.code FROM budget_lines l JOIN budget_cost_centres c USING (centre_id) "
            "WHERE c.year_label = ?", (label,))}
        for c in conn.execute("SELECT * FROM budget_cost_centres WHERE year_label = ? AND "
                              "active = 1 ORDER BY centre_id", (from_year,)).fetchall():
            if c["name"].lower() in existing:
                skipped.append(c["name"])
                continue
            cid = conn.execute(
                "INSERT INTO budget_cost_centres (year_label, name, kind, holder, notes, "
                "created_by, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (label, c["name"], c["kind"], c["holder"], c["notes"], actor.username,
                 actor.username)).lastrowid
            centres += 1
            for ln in conn.execute("SELECT * FROM budget_lines WHERE centre_id = ? ORDER BY "
                                   "line_id", (c["centre_id"],)).fetchall():
                if ln["code"].lower() in codes:
                    skipped.append(ln["code"])
                    continue
                alloc = int((Decimal(ln["allocation_pence"]) * (100 + uplift) / 100)
                            .quantize(Decimal("1")))
                lid = conn.execute(
                    "INSERT INTO budget_lines (centre_id, code, description, allocation_pence, "
                    "notes, created_by, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (cid, ln["code"], ln["description"], max(0, alloc), ln["notes"],
                     actor.username, actor.username)).lastrowid
                codes.add(ln["code"].lower())
                lines += 1
                if include_profiles:
                    conn.execute("INSERT INTO budget_profile (line_id, month, weight) SELECT ?, "
                                 "month, weight FROM budget_profile WHERE line_id = ?",
                                 (lid, ln["line_id"]))
        _audit(conn, "roll_forward", actor, year=label, rolled_from=from_year, centres=centres,
               lines=lines, uplift=str(uplift))
    activity_log.record("budgets.roll_forward", target=label, principal=actor, centres=centres,
                        lines=lines)
    return {"year": label, "centres": centres, "lines": lines, "skipped": skipped}


def month_name(ym: str) -> str:
    y, m = ym.split("-")
    return f"{calendar.month_abbr[int(m)]} {y}"
