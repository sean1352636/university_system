"""Pupil Premium: eligibility, the strategy's spending plan, who gets what,
and the impact on the gaps.

Built on the free school meals flag the pupil record already keeps
(``pupils.fsm_eligible``): a pupil with it set is counted as FSM this year
without anything else being entered, and "Record FSM from pupil records"
snapshots the flag into this year's eligibility so it becomes **Ever 6** in
later years (FSM recorded in any of the last six school years).

Kept from the old Pupil Premium window:

* One eligibility record per pupil and school year with category (Ever 6
  FSM, Free school meals, LAC, Post-LAC, Service child, Other), status
  (Eligible, Provisional, Withdrawn, Reviewing), funding, start / end date,
  eligibility source, keyworker and notes. A pupil may now hold more than one
  category (e.g. service child and Ever 6).
* Interventions paid for from the premium for a pupil (title, description,
  spend, dates, status, impact rating and notes) - now "activities", which can
  belong to a line of the spending plan.
* The record summary (spend, remaining, by status / impact) and the cohort
  summary (total, by category / status, funding, interventions, spend,
  remaining).

New:

* **Who.** :data:`PUPIL_PREMIUM_EDITORS` changes everything; all staff read.
  Changes are in ``pp_audit`` and the activity log (ids only).
* **Funding** from per-category rates for the year (editable; the default is
  the DfE secondary rate). LAC / post-LAC replaces the FSM rate; the service
  premium is added. A record's own funding overrides the rate.
* **Strategy** - the year's statement (challenges, intended outcomes,
  published / reviewed dates) and its spending plan in the three tiers
  (high-quality teaching, targeted academic support, wider strategies) with
  planned and actual cost, owner, evidence, success criteria and impact.
  The plan summary shows spend by tier against the budget.
* **Allocation** - give a plan line's activity to pupils; pupils who aren't
  eligible are flagged (the premium can benefit others, but it is worth
  checking).
* **Impact** - pupil premium vs other pupils: attendance and persistent
  absence (Attendance), behaviour points and incidents (Behaviour & Rewards),
  Attainment 8 and Progress 8 (Headline Measures), and the gap - read only.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.send.domain.send_common import (
    PUPIL_COLS,
    _blank,
    _choice,
    _date,
    _make,
    _number,
    _pupil,
    _text,
)
from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import (
    PUPIL_PREMIUM_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import current_year, next_year, year_of
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

EVER6 = "Ever 6 FSM"
FSM = "Free school meals"
LAC = "LAC (Looked-after child)"
PLAC = "Post-LAC"
SERVICE = "Service child"
CATEGORIES: tuple[str, ...] = (EVER6, FSM, LAC, PLAC, SERVICE, "Other")
DEFAULT_CATEGORY = EVER6
DEPRIVATION = frozenset({EVER6, FSM})
CARE = frozenset({LAC, PLAC})
PP_STATUSES: tuple[str, ...] = ("Eligible", "Provisional", "Withdrawn", "Reviewing")
DEFAULT_STATUS = "Eligible"
COUNTS = frozenset({"Eligible", "Reviewing"})
INTERVENTION_STATUSES: tuple[str, ...] = ("Planned", "Active", "Complete", "Cancelled")
DEFAULT_INT_STATUS = "Planned"
IMPACT_RATINGS: tuple[str, ...] = ("Not yet assessed", "Low", "Medium", "High", "Very high")
TIERS: tuple[str, ...] = ("High-quality teaching", "Targeted academic support",
                          "Wider strategies")
#: DfE pupil premium per-pupil rates for secondary schools (2025 to 2026).
DEFAULT_RATES: dict[str, float] = {EVER6: 1075.0, FSM: 1075.0, LAC: 2630.0, PLAC: 2630.0,
                                   SERVICE: 350.0, "Other": 0.0}
EVER6_YEARS = 6

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pp_eligibility (
    eligibility_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id            INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    academic_year       TEXT NOT NULL,
    category            TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'Eligible'
                        CHECK (status IN ('Eligible', 'Provisional', 'Withdrawn', 'Reviewing')),
    funding_amount      REAL CHECK (funding_amount IS NULL OR funding_amount >= 0),
    start_date          TEXT NOT NULL,
    end_date            TEXT,
    eligibility_source  TEXT,
    keyworker           TEXT,
    notes               TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (pupil_id, academic_year, category)
);
CREATE INDEX IF NOT EXISTS ix_pp_eligibility_year ON pp_eligibility (academic_year, status);
CREATE TABLE IF NOT EXISTS pp_rates (
    academic_year  TEXT NOT NULL,
    category       TEXT NOT NULL,
    amount         REAL NOT NULL CHECK (amount >= 0),
    PRIMARY KEY (academic_year, category)
);
CREATE TABLE IF NOT EXISTS pp_strategy (
    academic_year      TEXT PRIMARY KEY,
    budget_override    REAL CHECK (budget_override IS NULL OR budget_override >= 0),
    carried_forward    REAL NOT NULL DEFAULT 0,
    statement          TEXT,
    challenges         TEXT,
    intended_outcomes  TEXT,
    lead               TEXT,
    governor           TEXT,
    published_on       TEXT,
    review_date        TEXT,
    reviewed_on        TEXT,
    notes              TEXT,
    updated_by         TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS pp_spend_lines (
    line_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year     TEXT NOT NULL,
    tier              TEXT NOT NULL,
    title             TEXT NOT NULL,
    description       TEXT,
    evidence          TEXT,
    challenge         TEXT,
    success_criteria  TEXT,
    owner             TEXT,
    planned_cost      REAL NOT NULL DEFAULT 0 CHECK (planned_cost >= 0),
    actual_cost       REAL CHECK (actual_cost IS NULL OR actual_cost >= 0),
    status            TEXT NOT NULL DEFAULT 'Planned',
    impact_rating     TEXT NOT NULL DEFAULT 'Not yet assessed',
    impact_notes      TEXT,
    created_by        TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by        TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_pp_spend_lines_year ON pp_spend_lines (academic_year, tier);
CREATE TABLE IF NOT EXISTS pp_activities (
    activity_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    academic_year  TEXT NOT NULL,
    line_id        INTEGER REFERENCES pp_spend_lines (line_id) ON DELETE SET NULL,
    title          TEXT NOT NULL,
    description    TEXT,
    spend          REAL NOT NULL DEFAULT 0 CHECK (spend >= 0),
    start_date     TEXT NOT NULL,
    end_date       TEXT,
    status         TEXT NOT NULL DEFAULT 'Planned',
    impact_rating  TEXT NOT NULL DEFAULT 'Not yet assessed',
    impact_notes   TEXT,
    notes          TEXT,
    created_by     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by     TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_pp_activities_pupil ON pp_activities (pupil_id, academic_year);
CREATE INDEX IF NOT EXISTS ix_pp_activities_line ON pp_activities (line_id);
CREATE TABLE IF NOT EXISTS pp_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id   INTEGER,
    item       TEXT NOT NULL,
    item_id    INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("pupil_premium", _SCHEMA)


@dataclass(frozen=True)
class Eligibility:
    eligibility_id: int
    pupil_id: int
    academic_year: str
    category: str
    status: str
    funding_amount: float | None
    start_date: str
    end_date: str | None
    eligibility_source: str | None
    keyworker: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0

    @property
    def pp_id(self) -> int:     # the old name
        return self.eligibility_id

    @property
    def counts(self) -> bool:
        return self.status in COUNTS


@dataclass(frozen=True)
class Line:
    line_id: int
    academic_year: str
    tier: str
    title: str
    description: str | None
    evidence: str | None
    challenge: str | None
    success_criteria: str | None
    owner: str | None
    planned_cost: float
    actual_cost: float | None
    status: str
    impact_rating: str
    impact_notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str


@dataclass(frozen=True)
class Activity:
    activity_id: int
    pupil_id: int
    academic_year: str
    line_id: int | None
    title: str
    description: str | None
    spend: float
    start_date: str
    end_date: str | None
    status: str
    impact_rating: str
    impact_notes: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0

    @property
    def intervention_id(self) -> int:     # the old name
        return self.activity_id


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in PUPIL_PREMIUM_EDITORS


def _deny(actor: Principal, action: str, message: str) -> None:
    activity_log.record(f"pupil_premium.{action}", outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, "Only staff can see pupil premium records.")


def _require_editor(actor: Principal, action: str) -> None:
    if not is_editor(actor):
        _deny(actor, action, "Only the pupil premium lead can change that.")


def _audit(conn, actor: Principal, item: str, action: str, *, pupil_id: int | None = None,
           item_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO pp_audit (pupil_id, item, item_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (pupil_id, item, item_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(pupil_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM pp_audit", []
    if pupil_id is not None:
        sql += " WHERE pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        return [{"at": r["at"], "pupil_id": r["pupil_id"], "item": r["item"],
                 "item_id": r["item_id"], "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


def _year(value: Any, problems: list[str]) -> str:
    v = str(value or "").strip()
    if not v:
        return current_year()
    if len(v) != 7 or v[4] != "/" or not (v[:4] + v[5:]).isdigit() or \
            int(v[5:]) != (int(v[:4]) + 1) % 100:
        problems.append("School year must look like 2026/27")
        return current_year()
    return v


def year_bounds(year: str) -> tuple[str, str]:
    start = int(year[:4])
    return f"{start}-09-01", f"{start + 1}-08-31"


def _years_back(year: str, n: int) -> list[str]:
    start = int(year[:4])
    return [f"{y}/{(y + 1) % 100:02d}" for y in range(start - n + 1, start + 1)]


# ── Rates ────────────────────────────────────────────────────────────

def rates(academic_year: str | None = None) -> dict[str, float]:
    year = academic_year or current_year()
    out = dict(DEFAULT_RATES)
    with database.connect() as conn:
        for r in conn.execute("SELECT category, amount FROM pp_rates WHERE academic_year = ?",
                              (year,)):
            out[r["category"]] = float(r["amount"])
    return out


def set_rate(academic_year: str, category: str, amount: Any, *, actor: Principal
             ) -> dict[str, float]:
    _require_editor(actor, "rate")
    problems: list[str] = []
    year = _year(academic_year, problems)
    cat = _choice(category, CATEGORIES, "Category", problems, None)
    n = _number(amount, "Amount", problems, hi=20000)
    if cat is None or n is None:
        problems.append("Give the category and the amount")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("INSERT INTO pp_rates (academic_year, category, amount) VALUES (?, ?, ?) "
                     "ON CONFLICT (academic_year, category) DO UPDATE SET amount = "
                     "excluded.amount", (year, cat, n))
        _audit(conn, actor, "rate", "set", year=year, category=cat, amount=n)
    activity_log.record("pupil_premium.rate", principal=actor)
    return rates(year)


# ── Eligibility ──────────────────────────────────────────────────────

_EL_FIELDS = ("category", "status", "funding_amount", "start_date", "end_date",
              "eligibility_source", "keyworker", "notes")


def _el_select() -> str:
    return f"SELECT x.*, {PUPIL_COLS} FROM pp_eligibility x JOIN pupils p USING (pupil_id)"


def get(eligibility_id: int) -> Eligibility:
    with database.connect() as conn:
        r = conn.execute(_el_select() + " WHERE x.eligibility_id = ?",
                         (int(eligibility_id),)).fetchone()
    if r is None:
        raise NotFound(f"No pupil premium record #{eligibility_id}")
    return _make(Eligibility, r)


def get_for(pupil_ref: Any, academic_year: str | None = None) -> list[Eligibility]:
    """The pupil's recorded eligibility for a year (the old lookup)."""
    p = _pupil(pupil_ref)
    return list_records(pupil_id=p.pupil_id, academic_year=academic_year) if p else []


def list_records(*, pupil_id: int | None = None, academic_year: str | None = None,
                 year_group: int | str | None = None, category: str | None = None,
                 status: str | None = None, all_years: bool = False) -> list[Eligibility]:
    """Recorded eligibility (this school year unless *academic_year* or
    *all_years*), by year group then surname."""
    where, params = [], []
    year = None if all_years else (academic_year or current_year())
    for col, val in (("x.pupil_id", pupil_id), ("x.academic_year", year),
                     ("x.category", category), ("x.status", status)):
        if not _blank(val):
            where.append(f"{col} = ?")
            params.append(val)
    if not _blank(year_group):
        where.append("p.year_group = ?")
        params.append(int(year_group))  # type: ignore[arg-type]
    sql = _el_select() + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY x.academic_year DESC, p.year_group, p.legal_last_name COLLATE NOCASE"
    with database.connect() as conn:
        return [_make(Eligibility, r) for r in conn.execute(sql, params)]


def _clean_el(data: dict[str, Any], cur: Eligibility | None, problems: list[str]
              ) -> dict[str, Any]:
    m = {k: getattr(cur, k) for k in _EL_FIELDS} if cur else {}
    m.update({k: v for k, v in data.items() if k in _EL_FIELDS})
    out: dict[str, Any] = {
        "category": _choice(m.get("category"), CATEGORIES, "Category", problems,
                            DEFAULT_CATEGORY),
        "status": _choice(m.get("status"), PP_STATUSES, "Status", problems, DEFAULT_STATUS),
        "funding_amount": _number(m.get("funding_amount"), "Funding", problems, hi=20000),
        "start_date": _date(m.get("start_date"), "Start date", problems),
        "end_date": _date(m.get("end_date"), "End date", problems),
        "eligibility_source": _text(m.get("eligibility_source"), 200),
        "keyworker": _text(m.get("keyworker"), 80), "notes": _text(m.get("notes"), 2000)}
    out["start_date"] = out["start_date"] or _today().isoformat()
    if out["end_date"] and out["end_date"] < out["start_date"]:
        problems.append("End date cannot be before start date")
    if out["category"] in CARE and not out["eligibility_source"]:
        problems.append("Record the evidence for looked-after / previously looked-after "
                        "(e.g. the local authority, adoption or SGO order)")
    if out["status"] == "Withdrawn" and not out["end_date"]:
        out["end_date"] = _today().isoformat()
    return out


def upsert(data: dict[str, Any], *, actor: Principal) -> Eligibility:
    """The old Set / update eligibility: *data* carries ``pupil_id`` (id or
    admission no.) and ``academic_year`` (default this year); one record per
    pupil, year and category."""
    _require_editor(actor, "save")
    problems: list[str] = []
    ref = data.get("pupil_id") or data.get("pupil")
    p = _pupil(ref)
    if p is None:
        problems.append("Pupil ID is required" if _blank(ref) else f"No pupil {ref}")
    year = _year(data.get("academic_year"), problems)
    c = _clean_el(data, None, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        old = conn.execute("SELECT eligibility_id FROM pp_eligibility WHERE pupil_id = ? AND "
                           "academic_year = ? AND category = ?",
                           (p.pupil_id, year, c["category"])).fetchone()
        conn.execute(
            f"INSERT INTO pp_eligibility (pupil_id, academic_year, {', '.join(_EL_FIELDS)}, "
            f"created_by, updated_by) VALUES (?, ?, {', '.join('?' * len(_EL_FIELDS))}, ?, ?) "
            "ON CONFLICT (pupil_id, academic_year, category) DO UPDATE SET "
            + ", ".join(f"{k} = excluded.{k}" for k in _EL_FIELDS if k != "category")
            + ", updated_by = excluded.updated_by, updated_at = datetime('now')",
            (p.pupil_id, year, *(c[k] for k in _EL_FIELDS), actor.username, actor.username))
        eid = conn.execute("SELECT eligibility_id FROM pp_eligibility WHERE pupil_id = ? AND "
                           "academic_year = ? AND category = ?",
                           (p.pupil_id, year, c["category"])).fetchone()[0]
        _audit(conn, actor, "eligibility", "update" if old else "create", pupil_id=p.pupil_id,
               item_id=eid, year=year)
    activity_log.record("pupil_premium.save", target=p.admission_no, principal=actor,
                        record=eid)
    return get(eid)


def update(eligibility_id: int, changes: dict[str, Any], *, actor: Principal) -> Eligibility:
    """The old Edit."""
    cur = get(eligibility_id)
    _require_editor(actor, "update")
    problems: list[str] = []
    c = _clean_el(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in _EL_FIELDS if c[k] != getattr(cur, k)]
    if changed:
        try:
            with database.connect() as conn:
                conn.execute("UPDATE pp_eligibility SET "
                             + ", ".join(f"{k} = ?" for k in changed)
                             + ", updated_by = ?, updated_at = datetime('now') "
                               "WHERE eligibility_id = ?",
                             (*(c[k] for k in changed), actor.username, cur.eligibility_id))
                _audit(conn, actor, "eligibility", "update", pupil_id=cur.pupil_id,
                       item_id=cur.eligibility_id, fields=changed)
        except database.IntegrityError:
            raise ValidationError([f"{cur.pupil_name} already has a {c['category']} record "
                                   f"for {cur.academic_year}"]) from None
        activity_log.record("pupil_premium.update", target=cur.admission_no, principal=actor)
    return get(cur.eligibility_id)


def delete(eligibility_id: int, *, actor: Principal) -> bool:
    """The old Delete (the pupil's activities stay)."""
    cur = get(eligibility_id)
    _require_editor(actor, "delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM pp_eligibility WHERE eligibility_id = ?",
                     (cur.eligibility_id,))
        _audit(conn, actor, "eligibility", "delete", pupil_id=cur.pupil_id,
               item_id=cur.eligibility_id)
    activity_log.record("pupil_premium.delete", target=cur.admission_no, principal=actor)
    return True


def record_fsm_from_pupils(*, actor: Principal, academic_year: str | None = None) -> int:
    """Snapshot the pupil records' free school meals flag into this year's
    eligibility (so it counts as Ever 6 later). Returns the number added."""
    _require_editor(actor, "fsm_snapshot")
    year = academic_year or current_year()
    n = 0
    with database.connect() as conn:
        for p in P.list_pupils():
            if not p.fsm_eligible:
                continue
            n += conn.execute(
                "INSERT OR IGNORE INTO pp_eligibility (pupil_id, academic_year, category, "
                "status, start_date, eligibility_source, created_by, updated_by) VALUES "
                "(?, ?, ?, 'Eligible', ?, 'Pupil record (free school meals)', ?, ?)",
                (p.pupil_id, year, FSM, _today().isoformat(), actor.username,
                 actor.username)).rowcount
        _audit(conn, actor, "eligibility", "fsm_snapshot", year=year, added=n)
    activity_log.record("pupil_premium.fsm_snapshot", principal=actor, added=n)
    return n


def eligibility_for(pupil: P.Pupil, academic_year: str | None = None,
                    _recorded: dict[int, list[Eligibility]] | None = None,
                    _history: dict[int, set[str]] | None = None) -> list[dict[str, Any]]:
    """Every category the pupil counts under this year: what's recorded, FSM
    from the pupil record (this year), and Ever 6 from FSM in the last six
    years. [{'category', 'status', 'source', 'record'}]."""
    year = academic_year or current_year()
    rec = _recorded.get(pupil.pupil_id, []) if _recorded is not None else \
        list_records(pupil_id=pupil.pupil_id, academic_year=year)
    out = [{"category": e.category, "status": e.status, "source": e.eligibility_source or
            "recorded", "record": e} for e in rec]
    have = {e.category for e in rec}
    if pupil.fsm_eligible and year == current_year() and not have & DEPRIVATION:
        out.append({"category": FSM, "status": "Eligible", "source": "Pupil record",
                    "record": None})
        have.add(FSM)
    if not have & DEPRIVATION:
        past = _history.get(pupil.pupil_id, set()) if _history is not None else \
            _fsm_years().get(pupil.pupil_id, set())
        window = set(_years_back(year, EVER6_YEARS))
        if past & window:
            out.append({"category": EVER6, "status": "Eligible",
                        "source": f"FSM in {', '.join(sorted(past & window))}",
                        "record": None})
    return out


def _fsm_years() -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    with database.connect() as conn:
        for r in conn.execute("SELECT pupil_id, academic_year FROM pp_eligibility WHERE "
                              "category IN (?, ?) AND status IN ('Eligible', 'Reviewing')",
                              (FSM, EVER6)):
            out.setdefault(r["pupil_id"], set()).add(r["academic_year"])
    return out


def funding_for(cats: list[dict[str, Any]], rate: dict[str, float]) -> float:
    """Per-pupil funding: the care rate replaces the deprivation rate; the
    service premium is added; a record's own amount overrides its rate."""
    def amount(c: dict[str, Any]) -> float:
        e = c.get("record")
        if e is not None and e.funding_amount is not None:
            return float(e.funding_amount)
        return rate.get(c["category"], 0.0)
    live = [c for c in cats if c["status"] in COUNTS]
    care = [amount(c) for c in live if c["category"] in CARE]
    dep = [amount(c) for c in live if c["category"] in DEPRIVATION]
    main = max(care) if care else (max(dep) if dep else 0.0)
    extra = sum(amount(c) for c in live if c["category"] not in CARE | DEPRIVATION)
    return round(main + extra, 2)


def cohort(*, academic_year: str | None = None, year_group: int | str | None = None,
           form_group: str | None = None, category: str | None = None
           ) -> list[dict[str, Any]]:
    """The pupil premium cohort on roll: one row per pupil with at least one
    category that counts - {'pupil', 'categories', 'funding', 'keyworker',
    'provisional'}."""
    year = academic_year or current_year()
    rate = rates(year)
    recorded: dict[int, list[Eligibility]] = {}
    for e in list_records(academic_year=year):
        recorded.setdefault(e.pupil_id, []).append(e)
    hist = _fsm_years()
    out = []
    for p in P.list_pupils(year_group=int(year_group) if not _blank(year_group) else None,
                           form_group=form_group or None):
        cats = eligibility_for(p, year, recorded, hist)
        live = [c for c in cats if c["status"] in COUNTS]
        if not live and not any(c["status"] == "Provisional" for c in cats):
            continue
        if category and not any(c["category"] == category for c in live):
            continue
        out.append({"pupil": p, "categories": [c["category"] for c in live],
                    "provisional": [c["category"] for c in cats if c["status"] == "Provisional"],
                    "funding": funding_for(cats, rate),
                    "keyworker": next((c["record"].keyworker for c in cats
                                       if c["record"] and c["record"].keyworker), "")})
    return out


def pp_ids(academic_year: str | None = None) -> set[int]:
    return {r["pupil"].pupil_id for r in cohort(academic_year=academic_year) if r["categories"]}


def is_pupil_premium(pupil_id: int, academic_year: str | None = None) -> bool:
    p = P.get_pupil(int(pupil_id))
    return bool(p and any(c["status"] in COUNTS for c in eligibility_for(p, academic_year)))


# ── Strategy and spending plan ───────────────────────────────────────

_ST_FIELDS = ("budget_override", "carried_forward", "statement", "challenges",
              "intended_outcomes", "lead", "governor", "published_on", "review_date",
              "reviewed_on", "notes")


def strategy(academic_year: str | None = None) -> dict[str, Any]:
    year = academic_year or current_year()
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM pp_strategy WHERE academic_year = ?", (year,)).fetchone()
    out = {k: (r[k] if r else None) for k in _ST_FIELDS}
    out["carried_forward"] = out["carried_forward"] or 0.0
    out["academic_year"] = year
    return out


def save_strategy(academic_year: str | None, data: dict[str, Any], *, actor: Principal
                  ) -> dict[str, Any]:
    _require_editor(actor, "strategy")
    problems: list[str] = []
    year = _year(academic_year, problems)
    cur = strategy(year)
    m = {**cur, **{k: v for k, v in data.items() if k in _ST_FIELDS}}
    c = {"budget_override": _number(m["budget_override"], "Budget", problems, hi=10_000_000),
         "carried_forward": _number(m["carried_forward"], "Carried forward", problems,
                                    hi=10_000_000) or 0.0}
    for k in ("statement", "challenges", "intended_outcomes", "notes"):
        c[k] = _text(m[k], 8000)
    for k in ("lead", "governor"):
        c[k] = _text(m[k], 80)
    for k, label in (("published_on", "Published on"), ("review_date", "Review date"),
                     ("reviewed_on", "Reviewed on")):
        c[k] = _date(m[k], label, problems)
    if c["published_on"] and not (c["challenges"] and c["intended_outcomes"]):
        problems.append("Set out the challenges and intended outcomes before publishing the "
                        "statement")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute(
            f"INSERT INTO pp_strategy (academic_year, {', '.join(_ST_FIELDS)}, updated_by) "
            f"VALUES (?, {', '.join('?' * len(_ST_FIELDS))}, ?) ON CONFLICT (academic_year) DO "
            "UPDATE SET " + ", ".join(f"{k} = excluded.{k}" for k in _ST_FIELDS)
            + ", updated_by = excluded.updated_by, updated_at = datetime('now')",
            (year, *(c[k] for k in _ST_FIELDS), actor.username))
        _audit(conn, actor, "strategy", "save", year=year)
    activity_log.record("pupil_premium.strategy", principal=actor)
    return strategy(year)


_LINE_FIELDS = ("tier", "title", "description", "evidence", "challenge", "success_criteria",
                "owner", "planned_cost", "actual_cost", "status", "impact_rating",
                "impact_notes")


def get_line(line_id: int) -> Line:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM pp_spend_lines WHERE line_id = ?",
                         (int(line_id),)).fetchone()
    if r is None:
        raise NotFound(f"No plan line #{line_id}")
    return Line(**{k: r[k] for k in Line.__dataclass_fields__})


def list_lines(academic_year: str | None = None, *, tier: str | None = None) -> list[Line]:
    sql, params = "SELECT * FROM pp_spend_lines WHERE academic_year = ?", \
        [academic_year or current_year()]
    if tier:
        sql += " AND tier = ?"
        params.append(tier)
    order = "CASE tier " + " ".join(f"WHEN '{t}' THEN {i}" for i, t in enumerate(TIERS)) + \
        " ELSE 9 END"
    with database.connect() as conn:
        return [Line(**{k: r[k] for k in Line.__dataclass_fields__})
                for r in conn.execute(sql + f" ORDER BY {order}, title COLLATE NOCASE", params)]


def _clean_line(data: dict[str, Any], cur: Line | None, problems: list[str]) -> dict[str, Any]:
    m = {k: getattr(cur, k) for k in _LINE_FIELDS} if cur else {}
    m.update({k: v for k, v in data.items() if k in _LINE_FIELDS})
    out: dict[str, Any] = {
        "tier": _choice(m.get("tier"), TIERS, "Tier", problems, None),
        "title": _text(m.get("title"), 120),
        "status": _choice(m.get("status"), INTERVENTION_STATUSES, "Status", problems,
                          DEFAULT_INT_STATUS),
        "impact_rating": _choice(m.get("impact_rating"), IMPACT_RATINGS, "Impact", problems,
                                 IMPACT_RATINGS[0]),
        "planned_cost": _number(m.get("planned_cost"), "Planned cost", problems,
                                hi=10_000_000) or 0.0,
        "actual_cost": _number(m.get("actual_cost"), "Actual cost", problems, hi=10_000_000)}
    if not out["tier"]:
        problems.append(f"Choose the tier: {', '.join(TIERS)}")
    if not out["title"]:
        problems.append("Title is required")
    for k, n in (("description", 2000), ("evidence", 1000), ("challenge", 500),
                 ("success_criteria", 1000), ("owner", 80), ("impact_notes", 2000)):
        out[k] = _text(m.get(k), n)
    if out["status"] == "Complete" and out["impact_rating"] == IMPACT_RATINGS[0]:
        problems.append("Rate the impact when the line is complete")
    return out


def add_line(academic_year: str | None, data: dict[str, Any], *, actor: Principal) -> Line:
    _require_editor(actor, "line")
    problems: list[str] = []
    year = _year(academic_year, problems)
    c = _clean_line(data, None, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        lid = conn.execute(
            f"INSERT INTO pp_spend_lines (academic_year, {', '.join(_LINE_FIELDS)}, created_by, "
            f"updated_by) VALUES (?, {', '.join('?' * len(_LINE_FIELDS))}, ?, ?)",
            (year, *(c[k] for k in _LINE_FIELDS), actor.username, actor.username)).lastrowid
        _audit(conn, actor, "line", "create", item_id=lid, year=year)
    activity_log.record("pupil_premium.line", principal=actor, line=lid)
    return get_line(lid)


def update_line(line_id: int, changes: dict[str, Any], *, actor: Principal) -> Line:
    cur = get_line(line_id)
    _require_editor(actor, "line_update")
    problems: list[str] = []
    c = _clean_line(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in _LINE_FIELDS if c[k] != getattr(cur, k)]
    if changed:
        with database.connect() as conn:
            conn.execute("UPDATE pp_spend_lines SET " + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') WHERE line_id = ?",
                         (*(c[k] for k in changed), actor.username, cur.line_id))
            _audit(conn, actor, "line", "update", item_id=cur.line_id, fields=changed)
        activity_log.record("pupil_premium.line_update", principal=actor, line=cur.line_id)
    return get_line(cur.line_id)


def delete_line(line_id: int, *, actor: Principal) -> bool:
    cur = get_line(line_id)
    _require_editor(actor, "line_delete")
    with database.connect() as conn:
        used = conn.execute("SELECT COUNT(*) FROM pp_activities WHERE line_id = ?",
                            (cur.line_id,)).fetchone()[0]
        if used:
            raise ValidationError([f"{used} pupil activit(ies) belong to this line - remove "
                                   "them or mark the line Cancelled"])
        conn.execute("DELETE FROM pp_spend_lines WHERE line_id = ?", (cur.line_id,))
        _audit(conn, actor, "line", "delete", item_id=cur.line_id)
    activity_log.record("pupil_premium.line_delete", principal=actor, line=cur.line_id)
    return True


def copy_plan(from_year: str, to_year: str | None = None, *, actor: Principal) -> int:
    """Start next year's plan from this year's lines (costs and impact reset)."""
    _require_editor(actor, "line_copy")
    to = to_year or next_year(from_year)
    if list_lines(to):
        raise ValidationError([f"{to} already has a spending plan"])
    n = 0
    for x in list_lines(from_year):
        if x.status == "Cancelled":
            continue
        add_line(to, {"tier": x.tier, "title": x.title, "description": x.description,
                      "evidence": x.evidence, "challenge": x.challenge,
                      "success_criteria": x.success_criteria, "owner": x.owner,
                      "planned_cost": x.planned_cost}, actor=actor)
        n += 1
    return n


def budget(academic_year: str | None = None) -> dict[str, float]:
    """{'allocation' (from the cohort), 'carried_forward', 'total'} - the
    strategy's budget override replaces the allocation."""
    year = academic_year or current_year()
    st = strategy(year)
    alloc = round(sum(r["funding"] for r in cohort(academic_year=year)), 2)
    base = st["budget_override"] if st["budget_override"] is not None else alloc
    return {"allocation": alloc, "override": st["budget_override"],
            "carried_forward": st["carried_forward"],
            "total": round(base + st["carried_forward"], 2)}


def plan_summary(academic_year: str | None = None) -> dict[str, Any]:
    """Spend by tier against the budget, and warnings."""
    year = academic_year or current_year()
    lines = [x for x in list_lines(year) if x.status != "Cancelled"]
    b = budget(year)
    spent: Counter = Counter()
    for a in list_activities(academic_year=year):
        if a.line_id:
            spent[a.line_id] += a.spend
    tiers = []
    for t in TIERS:
        xs = [x for x in lines if x.tier == t]
        tiers.append({"tier": t, "lines": len(xs),
                      "planned": round(sum(x.planned_cost for x in xs), 2),
                      # the line's actual cost, else what its pupils' activities spent
                      "actual": round(sum(x.actual_cost if x.actual_cost is not None
                                          else spent[x.line_id] for x in xs), 2)})
    planned = round(sum(t["planned"] for t in tiers), 2)
    actual = round(sum(t["actual"] for t in tiers), 2)
    warnings = []
    if planned > b["total"]:
        warnings.append(f"The plan (£{planned:,.2f}) is more than the budget "
                        f"(£{b['total']:,.2f})")
    if lines and not any(x.tier == TIERS[0] for x in lines):
        warnings.append("Nothing planned for high-quality teaching - the DfE expects schools "
                        "to prioritise it")
    for t in tiers:
        t["share"] = round(100 * t["planned"] / planned, 1) if planned else None
    return {"academic_year": year, "budget": b, "tiers": tiers, "planned": planned,
            "actual": actual, "remaining": round(b["total"] - actual, 2),
            "unallocated": round(b["total"] - planned, 2), "warnings": warnings}


def strategy_text(academic_year: str | None = None) -> str:
    """The strategy statement as plain text (to publish)."""
    year = academic_year or current_year()
    st, ps = strategy(year), plan_summary(year)
    co = cohort(academic_year=year)
    roll = len(P.list_pupils())
    lines = [f"Pupil premium strategy statement {year}", "",
             f"Pupils on roll: {roll}; pupil premium pupils: {len(co)}"
             + (f" ({round(100 * len(co) / roll, 1)}%)" if roll else ""),
             f"Funding: £{ps['budget']['allocation']:,.2f}"
             + (f" + £{ps['budget']['carried_forward']:,.2f} carried forward"
                if ps['budget']['carried_forward'] else "")
             + f"; total £{ps['budget']['total']:,.2f}",
             f"Lead: {st['lead'] or '-'}    Governor: {st['governor'] or '-'}",
             f"Published: {st['published_on'] or '-'}    Next review: {st['review_date'] or '-'}",
             ""]
    for label, key in (("Statement of intent", "statement"), ("Challenges", "challenges"),
                       ("Intended outcomes", "intended_outcomes")):
        if st[key]:
            lines += [label, st[key], ""]
    for t in ps["tiers"]:
        lines.append(f"{t['tier']}: £{t['planned']:,.2f} planned, £{t['actual']:,.2f} spent")
        for x in list_lines(year, tier=t["tier"]):
            if x.status == "Cancelled":
                continue
            lines.append(f"  - {x.title} (£{x.planned_cost:,.2f})"
                         + (f": {x.description}" if x.description else ""))
            if x.evidence:
                lines.append(f"      Evidence: {x.evidence}")
            if x.impact_rating != IMPACT_RATINGS[0]:
                lines.append(f"      Impact: {x.impact_rating}"
                             + (f" - {x.impact_notes}" if x.impact_notes else ""))
        lines.append("")
    return "\n".join(lines).rstrip()


# ── Activities (the old interventions) and allocation ────────────────

_ACT_FIELDS = ("line_id", "title", "description", "spend", "start_date", "end_date", "status",
               "impact_rating", "impact_notes", "notes")


def _act_select() -> str:
    return f"SELECT x.*, {PUPIL_COLS} FROM pp_activities x JOIN pupils p USING (pupil_id)"


def get_activity(activity_id: int) -> Activity:
    with database.connect() as conn:
        r = conn.execute(_act_select() + " WHERE x.activity_id = ?",
                         (int(activity_id),)).fetchone()
    if r is None:
        raise NotFound(f"No activity #{activity_id}")
    return _make(Activity, r)


get_intervention = get_activity


def list_activities(*, pupil_id: int | None = None, academic_year: str | None = None,
                    line_id: int | None = None, status: str | None = None,
                    year_group: int | str | None = None) -> list[Activity]:
    where, params = [], []
    for col, val in (("x.pupil_id", pupil_id), ("x.academic_year", academic_year),
                     ("x.line_id", line_id), ("x.status", status)):
        if not _blank(val):
            where.append(f"{col} = ?")
            params.append(val)
    if not _blank(year_group):
        where.append("p.year_group = ?")
        params.append(int(year_group))  # type: ignore[arg-type]
    sql = _act_select() + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY x.start_date DESC, x.activity_id DESC"
    with database.connect() as conn:
        return [_make(Activity, r) for r in conn.execute(sql, params)]


def list_interventions(eligibility_id: int) -> list[Activity]:
    """The old per-record interventions: the pupil's activities that year."""
    e = get(eligibility_id)
    return list_activities(pupil_id=e.pupil_id, academic_year=e.academic_year)


def _clean_act(data: dict[str, Any], cur: Activity | None, problems: list[str]
               ) -> dict[str, Any]:
    m = {k: getattr(cur, k) for k in _ACT_FIELDS} if cur else {}
    m.update({k: v for k, v in data.items() if k in _ACT_FIELDS})
    out: dict[str, Any] = {
        "title": _text(m.get("title"), 120),
        "status": _choice(m.get("status"), INTERVENTION_STATUSES, "Status", problems,
                          DEFAULT_INT_STATUS),
        "impact_rating": _choice(m.get("impact_rating"), IMPACT_RATINGS, "Impact", problems,
                                 IMPACT_RATINGS[0]),
        "spend": _number(m.get("spend"), "Spend", problems, hi=100000) or 0.0,
        "start_date": _date(m.get("start_date"), "Start date", problems)
        or _today().isoformat(),
        "end_date": _date(m.get("end_date"), "End date", problems)}
    line = None
    if not _blank(m.get("line_id")):
        try:
            line = get_line(int(m["line_id"]))
        except (ValueError, NotFound):
            problems.append(f"No plan line #{m.get('line_id')}")
    out["line_id"] = line.line_id if line else None
    if not out["title"]:
        out["title"] = line.title if line else None
        if not out["title"]:
            problems.append("Title is required")
    for k, n in (("description", 2000), ("impact_notes", 2000), ("notes", 2000)):
        out[k] = _text(m.get(k), n)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        problems.append("End date cannot be before start date")
    if out["status"] == "Complete" and not out["end_date"]:
        out["end_date"] = _today().isoformat()
    return out


def add_activity(data: dict[str, Any], *, actor: Principal) -> Activity:
    """The old Add intervention: *data* carries ``pupil_id`` - or the old
    ``pp_id`` (an eligibility record, giving the pupil and year)."""
    _require_editor(actor, "activity")
    problems: list[str] = []
    year = None
    if not _blank(data.get("pp_id")):
        e = get(int(data["pp_id"]))
        p, year = P.get_pupil(e.pupil_id), e.academic_year
    else:
        ref = data.get("pupil_id") or data.get("pupil")
        p = _pupil(ref)
        if p is None:
            problems.append("Pupil ID is required" if _blank(ref) else f"No pupil {ref}")
    c = _clean_act(data, None, problems)
    year = year or (_year(data.get("academic_year"), problems)
                    if not _blank(data.get("academic_year")) else year_of(c["start_date"]))
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        aid = conn.execute(
            f"INSERT INTO pp_activities (pupil_id, academic_year, {', '.join(_ACT_FIELDS)}, "
            f"created_by, updated_by) VALUES (?, ?, {', '.join('?' * len(_ACT_FIELDS))}, ?, ?)",
            (p.pupil_id, year, *(c[k] for k in _ACT_FIELDS), actor.username,
             actor.username)).lastrowid
        _audit(conn, actor, "activity", "create", pupil_id=p.pupil_id, item_id=aid)
    activity_log.record("pupil_premium.activity", target=p.admission_no, principal=actor,
                        activity=aid)
    return get_activity(aid)


add_intervention = add_activity


def update_activity(activity_id: int, changes: dict[str, Any], *, actor: Principal
                    ) -> Activity:
    cur = get_activity(activity_id)
    _require_editor(actor, "activity_update")
    problems: list[str] = []
    c = _clean_act(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in _ACT_FIELDS if c[k] != getattr(cur, k)]
    if changed:
        with database.connect() as conn:
            conn.execute("UPDATE pp_activities SET " + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') "
                           "WHERE activity_id = ?",
                         (*(c[k] for k in changed), actor.username, cur.activity_id))
            _audit(conn, actor, "activity", "update", pupil_id=cur.pupil_id,
                   item_id=cur.activity_id, fields=changed)
        activity_log.record("pupil_premium.activity_update", target=cur.admission_no,
                            principal=actor)
    return get_activity(cur.activity_id)


update_intervention = update_activity


def delete_activity(activity_id: int, *, actor: Principal) -> bool:
    cur = get_activity(activity_id)
    _require_editor(actor, "activity_delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM pp_activities WHERE activity_id = ?", (cur.activity_id,))
        _audit(conn, actor, "activity", "delete", pupil_id=cur.pupil_id,
               item_id=cur.activity_id)
    activity_log.record("pupil_premium.activity_delete", target=cur.admission_no,
                        principal=actor)
    return True


delete_intervention = delete_activity


def allocate(line_id: int, pupil_ids: list[int], *, actor: Principal,
             spend_each: Any = None, start_date: str | None = None,
             status: str = "Active") -> dict[str, Any]:
    """Give a plan line's activity to pupils (skipping those who already have
    it). Spend each defaults to the line's planned cost shared between
    everyone allocated. Returns {'added', 'skipped', 'not_pp'}."""
    _require_editor(actor, "allocate")
    line = get_line(line_id)
    if not pupil_ids:
        raise ValidationError(["Choose the pupils"])
    have = {a.pupil_id for a in list_activities(line_id=line.line_id)}
    new = [int(i) for i in pupil_ids if int(i) not in have]
    problems: list[str] = []
    each = _number(spend_each, "Spend each", problems, hi=100000)
    if problems:
        raise ValidationError(problems)
    if each is None:
        each = round(line.planned_cost / max(1, len(have) + len(new)), 2)
    eligible = pp_ids(line.academic_year)
    added = []
    for pid in new:
        added.append(add_activity({"pupil_id": pid, "line_id": line.line_id,
                                   "academic_year": line.academic_year, "spend": each,
                                   "start_date": start_date, "status": status}, actor=actor))
    return {"added": added, "skipped": len(pupil_ids) - len(new),
            "not_pp": [a for a in added if a.pupil_id not in eligible]}


def record_summary(eligibility_id: int) -> dict[str, Any]:
    """The old record summary."""
    rec = get(eligibility_id)
    acts = list_interventions(eligibility_id)
    p = P.get_pupil(rec.pupil_id)
    funding = funding_for(eligibility_for(p, rec.academic_year), rates(rec.academic_year))
    spend = round(sum(a.spend for a in acts), 2)
    return {"record": rec, "interventions": acts, "total_spend": spend, "funding": funding,
            "remaining": round(funding - spend, 2),
            "by_status": dict(Counter(a.status for a in acts)),
            "by_impact": dict(Counter(a.impact_rating for a in acts))}


def cohort_summary(*, year_group: int | str | None = None,
                   academic_year: str | None = None) -> dict[str, Any]:
    """The old cohort summary (from the whole cohort, derived FSM included)."""
    year = academic_year or current_year()
    co = cohort(academic_year=year, year_group=year_group)
    ids = {r["pupil"].pupil_id for r in co}
    acts = [a for a in list_activities(academic_year=year, year_group=year_group)]
    funding = round(sum(r["funding"] for r in co), 2)
    spend = round(sum(a.spend for a in acts), 2)
    recs = list_records(academic_year=year, year_group=year_group)
    return {"total": len(co), "by_category": dict(Counter(c for r in co
                                                          for c in r["categories"])),
            "by_status": dict(Counter(e.status for e in recs)),
            "total_funding": funding, "interventions": len(acts), "total_spend": spend,
            "remaining": round(funding - spend, 2),
            "pupils_with_activities": len({a.pupil_id for a in acts} & ids),
            "pp_without_activities": len(ids - {a.pupil_id for a in acts}),
            "on_roll": len(P.list_pupils(year_group=int(year_group) if not _blank(year_group)
                                         else None))}


# ── Impact (read from Attendance, Behaviour, Headline Measures) ──────

def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 2) if xs else None


def _gap(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else round(a - b, 2)


def impact(*, academic_year: str | None = None, year_group: int | str | None = None
           ) -> dict[str, Any]:
    """Pupil premium vs other pupils on roll: {'pp': n, 'other': n,
    'measures': [{'measure', 'pp', 'other', 'gap', 'better'}]} where *better*
    says which way is good ('higher' / 'lower'). A measure no module has data
    for is None."""
    from education_system.systems.secondary.modules.assessment.domain import headline_measures as HM
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    year = academic_year or current_year()
    yg = int(year_group) if not _blank(year_group) else None
    pp = {r["pupil"].pupil_id for r in cohort(academic_year=year, year_group=yg)}
    pupils = P.list_pupils(year_group=yg)
    other = {p.pupil_id for p in pupils} - pp
    measures: list[dict[str, Any]] = []

    def add(name: str, a: float | None, b: float | None, better: str) -> None:
        measures.append({"measure": name, "pp": a, "other": b, "gap": _gap(a, b),
                         "better": better})
    start, end = year_bounds(year)
    try:
        att = {p.pupil_id: s for p, s in AT.summaries(start, min(end, _today().isoformat()),
                                                      year_group=yg)}
    except Exception:  # noqa: BLE001 - a year not started yet, or no calendar
        att = {}

    def pct(ids: set[int]) -> float | None:
        return _mean([att[i].attendance_pct for i in ids if i in att
                      and att[i].attendance_pct is not None])

    def pa(ids: set[int]) -> float | None:
        have = [i for i in ids if i in att and att[i].attendance_pct is not None]
        return round(100 * sum(1 for i in have if att[i].band) / len(have), 1) if have else None
    add("Attendance %", pct(pp), pct(other), "higher")
    add("Persistent absence %", pa(pp), pa(other), "lower")
    neg: Counter = Counter()
    pos: Counter = Counter()
    incidents: Counter = Counter()
    for e in BH.list_entries(academic_year=year, year_group=yg):
        if not e.counts:
            continue
        if e.points < 0:
            neg[e.pupil_id] += -e.points
            incidents[e.pupil_id] += 1
        else:
            pos[e.pupil_id] += e.points

    def per(c: Counter, ids: set[int]) -> float | None:
        return round(sum(c[i] for i in ids) / len(ids), 2) if ids else None
    add("Behaviour incidents per pupil", per(incidents, pp), per(incidents, other), "lower")
    add("Negative points per pupil", per(neg, pp), per(neg, other), "lower")
    add("Positive points per pupil", per(pos, pp), per(pos, other), "higher")
    a8: dict[int, float] = {}
    for source in ("Actual", "Predicted"):
        for r in HM.list_records(academic_year=year, record_source=source, year_group=yg):
            a8.setdefault(r.pupil_id, r.total_points)
    p8 = {r.pupil_id: r.progress_8 for r in HM.list_p8(academic_year=year, year_group=yg)
          if r.progress_8 is not None}
    add("Average Attainment 8", _mean([a8[i] for i in pp if i in a8]),
        _mean([a8[i] for i in other if i in a8]), "higher")
    add("Average Progress 8", _mean([p8[i] for i in pp if i in p8]),
        _mean([p8[i] for i in other if i in p8]), "higher")
    return {"academic_year": year, "year_group": yg, "pp": len(pp), "other": len(other),
            "measures": measures}


def line_impact(line_id: int) -> dict[str, Any]:
    """For one plan line: its pupils' attendance and behaviour against the
    whole pupil premium cohort."""
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    line = get_line(line_id)
    acts = list_activities(line_id=line.line_id)
    ids = {a.pupil_id for a in acts}
    pp = pp_ids(line.academic_year)

    def att(group: set[int]) -> float | None:
        vals = []
        for i in group:
            try:
                v = AT.pupil_summary(i).attendance_pct
            except Exception:  # noqa: BLE001
                v = None
            if v is not None:
                vals.append(v)
        return _mean(vals)

    def neg(group: set[int]) -> float | None:
        if not group:
            return None
        n = sum(1 for e in BH.list_entries(academic_year=line.academic_year)
                if e.pupil_id in group and e.counts and e.points < 0)
        return round(n / len(group), 2)
    return {"line": line, "pupils": len(ids), "pp_pupils": len(ids & pp),
            "spend": round(sum(a.spend for a in acts), 2),
            "by_impact": dict(Counter(a.impact_rating for a in acts)),
            "attendance": att(ids), "cohort_attendance": att(pp),
            "incidents": neg(ids), "cohort_incidents": neg(pp)}


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, academic_year: str | None = None,
               year_group: int | str | None = None) -> int:
    """The cohort with categories, funding and activities."""
    _require_staff(actor, "export")
    year = academic_year or current_year()
    rows = cohort(academic_year=year, year_group=year_group)
    acts: dict[int, list[Activity]] = {}
    for a in list_activities(academic_year=year):
        acts.setdefault(a.pupil_id, []).append(a)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["admission_no", "pupil", "year", "form", "categories", "provisional",
                    "funding", "keyworker", "activities", "spend"])
        for r in rows:
            p, mine = r["pupil"], acts.get(r["pupil"].pupil_id, [])
            w.writerow([_safe(p.admission_no), _safe(f"{p.legal_last_name}, "
                                                     f"{p.preferred_name or p.legal_first_name}"),
                        p.year_group, _safe(p.form_group), "; ".join(r["categories"]),
                        "; ".join(r["provisional"]), f"{r['funding']:.2f}",
                        _safe(r["keyworker"]), _safe("; ".join(a.title for a in mine)),
                        f"{sum(a.spend for a in mine):.2f}"])
    activity_log.record("pupil_premium.export", principal=actor, rows=len(rows))
    return len(rows)

