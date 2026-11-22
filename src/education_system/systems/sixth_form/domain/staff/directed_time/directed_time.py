"""Directed time budgets for the Sixth Form System.

Each member of staff has a directed-time budget per academic year: the
contracted directed hours (1265 for a full-time teacher under the STPCD)
pro-rata by FTE. Time is drawn down by:

* **Logged activities** (``directed_time_activities``) — meetings,
  duties, open evenings, INSET, anything a leader directs. An activity
  can repeat (``occurrences`` × ``hours``, e.g. a weekly duty).
* **Derived time** — read live from the records that already exist,
  never copied in:

  - timetabled teaching (Staff Timetable load × teaching weeks), when the
    budget counts teaching (``include_teaching``);
  - parents' evenings the person has bookings at (event start → end);
  - CPD attended / completed (``cpd_records``), when ``include_cpd``;
  - internal cover they were allocated (one period per covered lesson).

``balance`` gives remaining hours; ``over_allocation_report`` lists the
people whose directed time exceeds their budget.

Permissions: budgets are set by HR or the person's line manager (the
``staff.line_manager`` of the record). Activities may be logged by those
people or by the member of staff for themselves. A balance is visible to
HR, the line manager and the person themself.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STAFF_DB

FULL_TIME_DIRECTED_HOURS = 1265.0
DEFAULT_TEACHING_WEEKS = 38

CATEGORIES: tuple[str, ...] = (
    "Meeting", "Parents' Evening", "Duty", "CPD / INSET", "Open Evening",
    "Cover", "Trip / Visit", "Exam Invigilation", "Other",
)
DEFAULT_CATEGORY = "Meeting"

PLANNED = "Planned"
COMPLETED = "Completed"
CANCELLED = "Cancelled"
ACTIVITY_STATUSES: tuple[str, ...] = (PLANNED, COMPLETED, CANCELLED)

SOURCE_MANUAL = "Logged"
SOURCE_TEACHING = "Teaching"
SOURCE_PARENTS = "Parents' Evening"
SOURCE_CPD = "CPD"
SOURCE_COVER = "Cover"

NEAR_LIMIT_PERCENT = 95.0

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YEAR_RE = re.compile(r"^(\d{4})/(\d{2})$")

# No foreign key to staff: like the HR records, a directed-time history
# outlives the staff row. The staff id is checked on write instead.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS directed_time_budgets (
    budget_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id          TEXT NOT NULL,
    academic_year     TEXT NOT NULL,
    contracted_hours  REAL NOT NULL DEFAULT 1265,
    fte_percent       REAL NOT NULL DEFAULT 100,
    allocated_hours   REAL NOT NULL,
    include_teaching  INTEGER NOT NULL DEFAULT 1,
    include_cpd       INTEGER NOT NULL DEFAULT 1,
    teaching_weeks    INTEGER NOT NULL DEFAULT 38,
    notes             TEXT,
    set_by            TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    UNIQUE (staff_id, academic_year)
);

CREATE TABLE IF NOT EXISTS directed_time_activities (
    activity_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id       TEXT NOT NULL,
    academic_year  TEXT NOT NULL,
    activity_date  TEXT NOT NULL,
    category       TEXT NOT NULL DEFAULT 'Meeting',
    title          TEXT NOT NULL,
    hours          REAL NOT NULL,
    occurrences    INTEGER NOT NULL DEFAULT 1,
    status         TEXT NOT NULL DEFAULT 'Planned',
    notes          TEXT,
    recorded_by    TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dtb_year  ON directed_time_budgets(academic_year);
CREATE INDEX IF NOT EXISTS idx_dta_staff ON directed_time_activities(staff_id, academic_year);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Budget:
    budget_id: int
    staff_id: str
    academic_year: str
    contracted_hours: float
    fte_percent: float
    allocated_hours: float
    include_teaching: bool
    include_cpd: bool
    teaching_weeks: int
    notes: str | None
    set_by: str | None
    created_at: str
    updated_at: str
    staff_name: str | None = None


@dataclass
class Activity:
    activity_id: int
    staff_id: str
    academic_year: str
    activity_date: str
    category: str
    title: str
    hours: float
    occurrences: int
    status: str
    notes: str | None
    recorded_by: str | None
    created_at: str
    updated_at: str
    staff_name: str | None = None

    @property
    def total_hours(self) -> float:
        return round(self.hours * self.occurrences, 2)


@dataclass
class DirectedItem:
    """One line of a person's directed time, logged or derived."""
    source: str
    ref: str
    date: str | None
    category: str
    title: str
    hours: float
    status: str


@dataclass
class Balance:
    staff_id: str
    name: str
    academic_year: str
    has_budget: bool
    allocated: float = 0.0
    logged: float = 0.0
    planned: float = 0.0
    teaching: float = 0.0
    parents_evenings: float = 0.0
    cpd: float = 0.0
    cover: float = 0.0

    @property
    def used(self) -> float:
        return round(self.logged + self.teaching + self.parents_evenings
                     + self.cpd + self.cover, 2)

    @property
    def remaining(self) -> float:
        return round(self.allocated - self.used, 2)

    @property
    def over(self) -> bool:
        return self.has_budget and self.used > self.allocated + 1e-9

    @property
    def percent_used(self) -> float | None:
        if not self.allocated:
            return None
        return round(100 * self.used / self.allocated, 1)


# ── Plumbing ────────────────────────────────────────────────────────

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


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _staff_mod():
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    return _staff


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def _names() -> dict[str, str]:
    return {s.staff_id: " ".join(f"{s.first_name} {s.last_name}".split())
            for s in _staff_mod().list_staff()}


def _budget(r: _sql.Row, names: dict[str, str] | None = None) -> Budget:
    return Budget(
        budget_id=r["budget_id"], staff_id=r["staff_id"],
        academic_year=r["academic_year"],
        contracted_hours=float(r["contracted_hours"]),
        fte_percent=float(r["fte_percent"]),
        allocated_hours=float(r["allocated_hours"]),
        include_teaching=bool(r["include_teaching"]),
        include_cpd=bool(r["include_cpd"]),
        teaching_weeks=int(r["teaching_weeks"]), notes=r["notes"],
        set_by=r["set_by"], created_at=r["created_at"],
        updated_at=r["updated_at"],
        staff_name=(names or {}).get(r["staff_id"]))


def _activity(r: _sql.Row, names: dict[str, str] | None = None) -> Activity:
    return Activity(
        activity_id=r["activity_id"], staff_id=r["staff_id"],
        academic_year=r["academic_year"], activity_date=r["activity_date"],
        category=r["category"], title=r["title"], hours=float(r["hours"]),
        occurrences=int(r["occurrences"]), status=r["status"],
        notes=r["notes"], recorded_by=r["recorded_by"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        staff_name=(names or {}).get(r["staff_id"]))


# ── Validation ──────────────────────────────────────────────────────

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


def _number(v: Any, label: str, *, lo: float = 0.0,
            hi: float | None = None, default: float | None = None) -> float:
    if v in (None, ""):
        if default is None:
            raise ValidationError(f"{label} is required")
        return default
    try:
        f = round(float(v), 2)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if f < lo or (hi is not None and f > hi):
        raise ValidationError(
            f"{label} must be between {lo:g} and {hi:g}" if hi is not None
            else f"{label} cannot be below {lo:g}")
    return f


def _int(v: Any, label: str, *, lo: int, hi: int, default: int) -> int:
    if v in (None, ""):
        return default
    try:
        n = int(str(v).strip())
    except ValueError:
        raise ValidationError(f"{label} must be a whole number") from None
    if not lo <= n <= hi:
        raise ValidationError(f"{label} must be between {lo} and {hi}")
    return n


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def _bool(v: Any, default: bool = True) -> bool:
    if v is None or v == "":
        return default
    if isinstance(v, str):
        return v.strip().lower() in ("1", "y", "yes", "true", "on")
    return bool(v)


def current_academic_year(today: _dt.date | None = None) -> str:
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


def year_bounds(year: str) -> tuple[str, str]:
    """1 September → 31 August."""
    start = int(validate_academic_year(year)[:4])
    return f"{start}-09-01", f"{start + 1}-08-31"


def year_of(date_s: str) -> str:
    return current_academic_year(_dt.date.fromisoformat(date_s))


def _require_staff(v: Any) -> Any:
    sid = _require(v, "Staff member").upper()
    st = _staff_mod().get_staff(sid)
    if st is None:
        raise ValidationError(f"No staff member {sid}")
    return st


# ── Permissions ─────────────────────────────────────────────────────

def _is_line_manager(p: Any, staff_obj: Any) -> bool:
    return bool(p.staff_id and staff_obj is not None
                and (staff_obj.line_manager or "").upper()
                == p.staff_id.upper())


def can_manage(staff_id: str, principal: Any = None) -> bool:
    """HR, the line manager, or an admin may set this person's budget."""
    access = _access()
    p = principal or access.current()
    if p.is_admin or p.can(access.HR):
        return True
    return _is_line_manager(p, _staff_mod().get_staff(staff_id))


def can_view(staff_id: str, principal: Any = None) -> bool:
    access = _access()
    p = principal or access.current()
    if p.staff_id and p.staff_id.upper() == (staff_id or "").upper():
        return True
    return can_manage(staff_id, p)


def _require_manage(staff_id: str, action: str) -> Any:
    access = _access()
    p = access.current()
    if not can_manage(staff_id, p):
        raise access.AccessDenied(
            f"{p.username or 'This account'} may not {action} for "
            f"{staff_id} — HR or their line manager only.")
    return p


def _require_view(staff_id: str) -> None:
    access = _access()
    p = access.current()
    if not can_view(staff_id, p):
        raise access.AccessDenied(
            f"{p.username or 'This account'} may not see directed time "
            f"for {staff_id}.")


def _require_log(staff_id: str) -> Any:
    """HR / line manager, or the person logging their own time."""
    access = _access()
    p = access.current()
    if p.staff_id and p.staff_id.upper() == staff_id.upper():
        return p
    return _require_manage(staff_id, "log directed time")


def _who(p: Any) -> str | None:
    return p.staff_name or p.username or None


def visible_staff_ids(principal: Any = None) -> set[str] | None:
    """None = everybody (HR/admin); otherwise self + line reports."""
    access = _access()
    p = principal or access.current()
    if p.is_admin or p.can(access.HR):
        return None
    out = {p.staff_id.upper()} if p.staff_id else set()
    if p.staff_id:
        out |= {s.staff_id for s in _staff_mod().list_staff()
                if (s.line_manager or "").upper() == p.staff_id.upper()}
    return out


# ── Budgets ─────────────────────────────────────────────────────────

def default_fte(staff_id: str) -> float:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        staff_timetable as _st,
    )
    return _st.fte_for(staff_id)


def _budget_values(payload: dict[str, Any], existing: Budget | None,
                   staff_id: str) -> dict[str, Any]:
    def g(k: str, dflt: Any) -> Any:
        return payload.get(k, getattr(existing, k) if existing else dflt)

    contracted = _number(g("contracted_hours", FULL_TIME_DIRECTED_HOURS),
                         "Contracted directed hours", lo=0, hi=2000,
                         default=FULL_TIME_DIRECTED_HOURS)
    fte_default = existing.fte_percent if existing else default_fte(staff_id)
    fte = _number(payload.get("fte_percent", fte_default), "FTE %",
                  lo=1, hi=100, default=fte_default)
    alloc_raw = payload.get("allocated_hours")
    if alloc_raw in (None, ""):
        allocated = round(contracted * fte / 100, 2)
    else:
        allocated = _number(alloc_raw, "Allocated hours", lo=0, hi=2000)
    return {
        "contracted_hours": contracted, "fte_percent": fte,
        "allocated_hours": allocated,
        "include_teaching": 1 if _bool(g("include_teaching", True)) else 0,
        "include_cpd": 1 if _bool(g("include_cpd", True)) else 0,
        "teaching_weeks": _int(g("teaching_weeks", DEFAULT_TEACHING_WEEKS),
                               "Teaching weeks", lo=1, hi=52,
                               default=DEFAULT_TEACHING_WEEKS),
        "notes": _text(g("notes", None)),
    }


def create_budget(payload: dict[str, Any]) -> Budget:
    """Set a person's budget for a year. Allocated hours default to
    contracted × FTE / 100 (FTE from Staff HR when not given)."""
    init_db()
    st = _require_staff(payload.get("staff_id"))
    p = _require_manage(st.staff_id, "set a directed-time budget")
    year = validate_academic_year(payload.get("academic_year"))
    v = _budget_values(payload, None, st.staff_id)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO directed_time_budgets (staff_id, academic_year,"
                " contracted_hours, fte_percent, allocated_hours, "
                "include_teaching, include_cpd, teaching_weeks, notes, "
                "set_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (st.staff_id, year, v["contracted_hours"], v["fte_percent"],
                 v["allocated_hours"], v["include_teaching"],
                 v["include_cpd"], v["teaching_weeks"], v["notes"], _who(p)))
        except _sql.IntegrityError:
            raise ValidationError(
                f"{st.staff_id} already has a budget for {year}") from None
        new_id = cur.lastrowid
    logger.info("Directed-time budget #%d set for %s %s (%.1f h)",
                new_id, st.staff_id, year, v["allocated_hours"])
    return _require_budget(new_id)


def update_budget(budget_id: int, payload: dict[str, Any]) -> Budget:
    b = _require_budget(budget_id)
    p = _require_manage(b.staff_id, "change a directed-time budget")
    if "contracted_hours" in payload or "fte_percent" in payload:
        payload.setdefault("allocated_hours", None)
    elif "allocated_hours" not in payload:
        payload["allocated_hours"] = b.allocated_hours
    v = _budget_values(payload, b, b.staff_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE directed_time_budgets SET contracted_hours=?, "
            "fte_percent=?, allocated_hours=?, include_teaching=?, "
            "include_cpd=?, teaching_weeks=?, notes=?, set_by=?, "
            "updated_at=datetime('now') WHERE budget_id=?",
            (v["contracted_hours"], v["fte_percent"], v["allocated_hours"],
             v["include_teaching"], v["include_cpd"], v["teaching_weeks"],
             v["notes"], _who(p), budget_id))
    return _require_budget(budget_id)


def delete_budget(budget_id: int) -> bool:
    """Remove a budget set by mistake. Logged activities stay — they are
    the record of what the person was directed to do."""
    b = _require_budget(budget_id)
    _require_manage(b.staff_id, "remove a directed-time budget")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM directed_time_budgets WHERE budget_id=?",
            (budget_id,))
    return bool(cur.rowcount)


def get_budget(budget_id: int) -> Budget | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM directed_time_budgets "
                         "WHERE budget_id=?", (budget_id,)).fetchone()
    return _budget(r, _names()) if r else None


def _require_budget(budget_id: int) -> Budget:
    b = get_budget(int(budget_id))
    if b is None:
        raise ValidationError(f"No directed-time budget #{budget_id}")
    return b


def budget_for(staff_id: str, academic_year: str | None = None
               ) -> Budget | None:
    init_db()
    year = validate_academic_year(academic_year)
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM directed_time_budgets WHERE staff_id=? AND "
            "academic_year=?", ((staff_id or "").upper(), year)).fetchone()
    return _budget(r, _names()) if r else None


def list_budgets(*, academic_year: str | None = None,
                 staff_id: str | None = None) -> list[Budget]:
    """Budgets the signed-in user may see."""
    init_db()
    clauses, args = [], []
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(validate_academic_year(academic_year))
    if staff_id:
        clauses.append("staff_id = ?")
        args.append(staff_id.strip().upper())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM directed_time_budgets{where} "
            "ORDER BY academic_year DESC, staff_id", args).fetchall()
    names = _names()
    allowed = visible_staff_ids()
    return [_budget(r, names) for r in rows
            if allowed is None or r["staff_id"] in allowed]


def create_default_budgets(academic_year: str | None = None, *,
                           roles: tuple[str, ...] | None = None
                           ) -> list[Budget]:
    """Give every active teaching member of staff without a budget for
    the year the standard 1265 h pro-rata by their HR FTE. HR only."""
    access = _access()
    access.current().require(access.HR, "set directed-time budgets in bulk")
    from education_system.systems.sixth_form.domain.academics.cover import (
        cover as _cover,
    )
    year = validate_academic_year(academic_year)
    wanted = roles or _cover.COVER_ROLES
    have = {b.staff_id for b in list_budgets(academic_year=year)}
    made = []
    for st in _staff_mod().list_staff(active_only=True):
        if st.role in wanted and st.staff_id not in have:
            made.append(create_budget({"staff_id": st.staff_id,
                                       "academic_year": year}))
    return made


# ── Activities ──────────────────────────────────────────────────────

def _activity_values(payload: dict[str, Any], existing: Activity | None
                     ) -> dict[str, Any]:
    def g(k: str, dflt: Any = None) -> Any:
        return payload.get(k, getattr(existing, k) if existing else dflt)

    day = _date(g("activity_date", _dt.date.today().isoformat()),
                "Date", required=True)
    return {
        "activity_date": day,
        "academic_year": year_of(day),
        "category": _choice(g("category", DEFAULT_CATEGORY), CATEGORIES,
                            "Category", DEFAULT_CATEGORY),
        "title": _require(g("title"), "Title"),
        "hours": _number(g("hours"), "Hours", lo=0.25, hi=24),
        "occurrences": _int(g("occurrences", 1), "Occurrences", lo=1,
                            hi=200, default=1),
        "status": _choice(g("status", PLANNED), ACTIVITY_STATUSES, "Status",
                          PLANNED),
        "notes": _text(g("notes")),
    }


def log_activity(payload: dict[str, Any]) -> Activity:
    """Log directed time against someone. The academic year comes from
    the date. ``hours`` is per occurrence."""
    init_db()
    st = _require_staff(payload.get("staff_id"))
    p = _require_log(st.staff_id)
    v = _activity_values(payload, None)
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO directed_time_activities (staff_id, academic_year,"
            " activity_date, category, title, hours, occurrences, status, "
            "notes, recorded_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (st.staff_id, v["academic_year"], v["activity_date"],
             v["category"], v["title"], v["hours"], v["occurrences"],
             v["status"], v["notes"], _who(p)))
        new_id = cur.lastrowid
    return _require_activity(new_id)


def log_activity_for_many(staff_ids: list[str], payload: dict[str, Any]
                          ) -> list[Activity]:
    """The same meeting / INSET for several people at once."""
    ids = [s.strip().upper() for s in staff_ids if s and s.strip()]
    if not ids:
        raise ValidationError("Choose at least one member of staff")
    return [log_activity({**payload, "staff_id": sid})
            for sid in dict.fromkeys(ids)]


def update_activity(activity_id: int, payload: dict[str, Any]) -> Activity:
    a = _require_activity(activity_id)
    _require_log(a.staff_id)
    v = _activity_values(payload, a)
    with _connect() as conn:
        conn.execute(
            "UPDATE directed_time_activities SET academic_year=?, "
            "activity_date=?, category=?, title=?, hours=?, occurrences=?, "
            "status=?, notes=?, updated_at=datetime('now') "
            "WHERE activity_id=?",
            (v["academic_year"], v["activity_date"], v["category"],
             v["title"], v["hours"], v["occurrences"], v["status"],
             v["notes"], activity_id))
    return _require_activity(activity_id)


def set_activity_status(activity_id: int, status: str) -> Activity:
    return update_activity(activity_id, {"status": status})


def delete_activity(activity_id: int) -> bool:
    a = _require_activity(activity_id)
    _require_log(a.staff_id)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM directed_time_activities WHERE activity_id=?",
            (activity_id,))
    return bool(cur.rowcount)


def get_activity(activity_id: int) -> Activity | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM directed_time_activities "
                         "WHERE activity_id=?", (activity_id,)).fetchone()
    return _activity(r, _names()) if r else None


def _require_activity(activity_id: int) -> Activity:
    a = get_activity(int(activity_id))
    if a is None:
        raise ValidationError(f"No directed-time activity #{activity_id}")
    return a


def list_activities(*, staff_id: str | None = None,
                    academic_year: str | None = None,
                    category: str | None = None,
                    status: str | None = None) -> list[Activity]:
    init_db()
    clauses, args = [], []
    if staff_id:
        clauses.append("staff_id = ?")
        args.append(staff_id.strip().upper())
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(validate_academic_year(academic_year))
    if category:
        clauses.append("category = ?")
        args.append(_choice(category, CATEGORIES, "Category"))
    if status:
        clauses.append("status = ?")
        args.append(_choice(status, ACTIVITY_STATUSES, "Status"))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM directed_time_activities{where} "
            "ORDER BY activity_date DESC, activity_id DESC", args).fetchall()
    names = _names()
    allowed = visible_staff_ids()
    return [_activity(r, names) for r in rows
            if allowed is None or r["staff_id"] in allowed]


# ── Derived time ────────────────────────────────────────────────────

def _minutes_between(a: str, b: str) -> int:
    try:
        ha, ma = (int(x) for x in a.split(":"))
        hb, mb = (int(x) for x in b.split(":"))
    except (AttributeError, ValueError):
        return 0
    return max(0, (hb * 60 + mb) - (ha * 60 + ma))


def _parents_evening_items(staff_id: str, year: str) -> list[DirectedItem]:
    from education_system.systems.sixth_form.domains.communications.domain.parents_evenings import (
        parents_evenings as _pe,
    )
    lo, hi = year_bounds(year)
    booked = {b.event_id for b in _pe.list_bookings(staff_id=staff_id)
              if b.status != "Cancelled"}
    out = []
    for ev_id in sorted(booked):
        ev = _pe.get_event(ev_id)
        if ev is None or ev.status == "Cancelled" \
                or not lo <= ev.event_date <= hi:
            continue
        out.append(DirectedItem(
            SOURCE_PARENTS, f"parents_evening:{ev.event_id}", ev.event_date,
            "Parents' Evening", ev.name,
            round(_minutes_between(ev.start_time, ev.end_time) / 60, 2),
            COMPLETED if ev.event_date <= _dt.date.today().isoformat()
            else PLANNED))
    return out


def _cpd_items(staff_id: str, year: str) -> list[DirectedItem]:
    from education_system.systems.sixth_form.domain.staff.cpd import (
        cpd as _cpd,
    )
    lo, hi = year_bounds(year)
    out = []
    for r in _cpd.records_for_staff(staff_id):
        if r.status not in ("Attended", "Completed"):
            continue
        act = _cpd.get_activity(r.activity_id) if r.activity_id else None
        day = r.attended_on or (act.activity_date if act else None) \
            or r.booked_on
        if not day or not lo <= day[:10] <= hi:
            continue
        hours = r.hours_completed
        if hours is None and act is not None:
            hours = act.hours
        if not hours:
            continue
        out.append(DirectedItem(
            SOURCE_CPD, f"cpd:{r.record_id}", day[:10], "CPD / INSET",
            act.title if act else (r.activity_title_cache or "CPD"), round(float(hours), 2), COMPLETED))
    return out


def _cover_items(staff_obj: Any, year: str) -> list[DirectedItem]:
    from education_system.systems.sixth_form.domain.academics.cover import (
        cover as _cover,
    )
    from education_system.systems.sixth_form.domain.academics.timetable import (
        staff_timetable as _st,
    )
    lo, hi = year_bounds(year)
    aliases = _cover.staff_aliases(staff_obj)
    out = []
    for req in _cover.list_requests(date_from=lo, date_to=hi):
        if req.status not in ("Allocated", "Confirmed", "Completed") \
                or req.cover_type != "Internal" \
                or " ".join((req.cover_staff or "").split()).lower() \
                not in aliases:
            continue
        periods = sorted(_cover._periods_of(req)) or [0]
        minutes = sum(_st.period_minutes(p) if p else 55 for p in periods)
        out.append(DirectedItem(
            SOURCE_COVER, f"cover:{req.cover_id}", req.absent_date, "Cover",
            f"Cover for {req.absent_teacher}"
            + (f" ({req.subject})" if req.subject else ""),
            round(minutes / 60, 2),
            COMPLETED if req.status == "Completed" else PLANNED))
    return out


def _teaching_item(staff_id: str, year: str, weeks: int
                   ) -> DirectedItem | None:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        staff_timetable as _st,
    )
    load = _st.teaching_load(staff_id)
    if not load.periods:
        return None
    return DirectedItem(
        SOURCE_TEACHING, "timetable", None, "Teaching",
        f"Timetabled teaching: {load.periods} period(s), {load.hours:g} h"
        f"/week × {weeks} weeks", round(load.hours * weeks, 2), PLANNED)


def directed_items(staff_id: str, academic_year: str | None = None
                   ) -> list[DirectedItem]:
    """Every line counted against this person's year, logged first."""
    st = _require_staff(staff_id)
    _require_view(st.staff_id)
    year = validate_academic_year(academic_year)
    budget = budget_for(st.staff_id, year)
    include_teaching = budget.include_teaching if budget else True
    include_cpd = budget.include_cpd if budget else True
    weeks = budget.teaching_weeks if budget else DEFAULT_TEACHING_WEEKS
    items: list[DirectedItem] = []
    for a in list_activities(staff_id=st.staff_id, academic_year=year):
        items.append(DirectedItem(
            SOURCE_MANUAL, f"activity:{a.activity_id}", a.activity_date,
            a.category,
            a.title + (f" (×{a.occurrences})" if a.occurrences > 1 else ""),
            a.total_hours, a.status))
    if include_teaching:
        t = _teaching_item(st.staff_id, year, weeks)
        if t:
            items.append(t)
    items.extend(_parents_evening_items(st.staff_id, year))
    if include_cpd:
        items.extend(_cpd_items(st.staff_id, year))
    items.extend(_cover_items(st, year))
    return items


def balance(staff_id: str, academic_year: str | None = None) -> Balance:
    st = _require_staff(staff_id)
    year = validate_academic_year(academic_year)
    budget = budget_for(st.staff_id, year)
    out = Balance(staff_id=st.staff_id,
                  name=" ".join(f"{st.first_name} {st.last_name}".split()),
                  academic_year=year, has_budget=budget is not None,
                  allocated=budget.allocated_hours if budget else 0.0)
    for it in directed_items(st.staff_id, year):
        if it.status == CANCELLED:
            continue
        if it.source == SOURCE_MANUAL:
            out.logged += it.hours
            if it.status == PLANNED:
                out.planned += it.hours
        elif it.source == SOURCE_TEACHING:
            out.teaching += it.hours
        elif it.source == SOURCE_PARENTS:
            out.parents_evenings += it.hours
        elif it.source == SOURCE_CPD:
            out.cpd += it.hours
        elif it.source == SOURCE_COVER:
            out.cover += it.hours
    for k in ("logged", "planned", "teaching", "parents_evenings", "cpd",
              "cover"):
        setattr(out, k, round(getattr(out, k), 2))
    return out


def balances(academic_year: str | None = None) -> list[Balance]:
    """A balance for every budget the user may see."""
    year = validate_academic_year(academic_year)
    return [balance(b.staff_id, year)
            for b in list_budgets(academic_year=year)]


def over_allocation_report(academic_year: str | None = None, *,
                           near_limit_percent: float = NEAR_LIMIT_PERCENT
                           ) -> tuple[list[Balance], list[Balance]]:
    """``(over, near)``: people past their budget (largest excess first)
    and people at or above ``near_limit_percent`` but not over."""
    rows = balances(academic_year)
    over = sorted([b for b in rows if b.over], key=lambda b: b.remaining)
    near = sorted([b for b in rows if not b.over and b.percent_used is not
                   None and b.percent_used >= near_limit_percent],
                  key=lambda b: -(b.percent_used or 0))
    return over, near


def staff_without_budget(academic_year: str | None = None) -> list[Any]:
    """Active teaching staff with no budget for the year (HR view)."""
    from education_system.systems.sixth_form.domain.academics.cover import (
        cover as _cover,
    )
    year = validate_academic_year(academic_year)
    have = {b.staff_id for b in list_budgets(academic_year=year)}
    allowed = visible_staff_ids()
    return [s for s in _staff_mod().list_staff(active_only=True)
            if s.role in _cover.COVER_ROLES and s.staff_id not in have
            and (allowed is None or s.staff_id in allowed)]
