"""Fire drills and recurring premises checks — part of Health & Safety.

Sits beside the incident register in :mod:`.health_safety`. Four tables:

* ``fire_drills`` — the fire log: date and time, type (planned or
  unannounced drill, real evacuation, false alarm, lockdown drill), the
  scenario / zone, how long the building took to clear, the assembly
  point, whether the roll call was completed and how long it took, and
  the issues found. A drill can be linked to the emergency roll call run
  in :mod:`academics.attendance.attendance_rollcall`; linking copies the
  roll call's figures (expected, accounted for, missing, duration) onto
  the drill so the log still reads correctly if the roll call is later
  reopened.
* ``premises_check_types`` — what has to be checked and how often:
  weekly fire alarm test, monthly emergency lighting flick test, annual
  full-duration test, legionella temperatures, extinguishers… Frequency
  and a "due soon" warning are configurable per type.
  :func:`install_default_check_types` adds a standard UK list on request
  (configuration, not data — nothing is marked as done).
* ``premises_checks`` — each check carried out: date, where (call point,
  zone, outlet), result Pass / Advisory / Fail and findings.
* ``premises_actions`` — follow-up actions raised from a drill or a
  check (owner, due date, done / cancelled).

:func:`overdue_checks` is the register a fire officer asks for: each
active check type with its last date, next due date and state, plus a
"Fire evacuation drill" line due once a term.

Access: recording anything needs ``OPERATIONS``; reading needs
``OPERATIONS``, ``GOVERNANCE`` or ``REPORTS``. Records are never deleted.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

DRILL_TYPES: tuple[str, ...] = (
    "Planned drill", "Unannounced drill", "Real evacuation", "False alarm",
    "Lockdown drill", "Night / out-of-hours drill")
DEFAULT_DRILL_TYPE = "Planned drill"
#: Drill types that count as "an evacuation drill was held this term".
PRACTICE_TYPES = ("Planned drill", "Unannounced drill",
                  "Night / out-of-hours drill", "Real evacuation")
#: At least one evacuation drill a term.
DRILL_INTERVAL_DAYS = 122
DRILL_DUE_SOON_DAYS = 21

#: Roll-call kind → drill type when a drill is logged from a roll call.
_ROLLCALL_KIND_TO_TYPE = {"Drill": "Planned drill",
                          "Evacuation": "Real evacuation",
                          "Lockdown": "Lockdown drill"}

FREQUENCIES: dict[str, int] = {
    "Daily": 1, "Weekly": 7, "Fortnightly": 14, "Monthly": 31,
    "Quarterly": 92, "Six-monthly": 183, "Annual": 366,
    "Biennial": 731, "Five-yearly": 1827,
}
CHECK_CATEGORIES: tuple[str, ...] = (
    "Fire", "Emergency lighting", "Water / legionella", "Electrical",
    "Gas", "Security", "Lifts / equipment", "Asbestos", "General")

PASS = "Pass"
ADVISORY = "Pass with advisory"
FAIL = "Fail"
RESULTS: tuple[str, ...] = (PASS, ADVISORY, FAIL)

ACTION_OPEN = "Open"
ACTION_DONE = "Done"
ACTION_CANCELLED = "Cancelled"
ACTION_STATUSES: tuple[str, ...] = (ACTION_OPEN, ACTION_DONE,
                                    ACTION_CANCELLED)

OK = "In date"
DUE_SOON = "Due soon"
OVERDUE = "Overdue"
NEVER = "Never done"

#: A standard UK list: (name, category, frequency, due-soon days, guidance).
DEFAULT_CHECK_TYPES: tuple[tuple[str, str, str, int, str], ...] = (
    ("Fire alarm test (call point)", "Fire", "Weekly", 2,
     "BS 5839-1: test a different call point each week, same time"),
    ("Fire doors and escape routes", "Fire", "Weekly", 2,
     "Doors close fully, routes and exits unobstructed"),
    ("Fire extinguishers — visual check", "Fire", "Monthly", 7,
     "In place, pin and seal intact, pressure in green"),
    ("Fire extinguishers — service", "Fire", "Annual", 30,
     "BS 5306-3 annual service by a competent person"),
    ("Fire alarm system — service", "Fire", "Six-monthly", 21,
     "BS 5839-1 periodic inspection by a competent person"),
    ("Emergency lighting — flick test", "Emergency lighting", "Monthly", 7,
     "BS 5266-1: brief functional test of every fitting"),
    ("Emergency lighting — full duration", "Emergency lighting", "Annual",
     30, "BS 5266-1: full rated-duration discharge test"),
    ("Water temperatures (legionella)", "Water / legionella", "Monthly", 7,
     "Sentinel outlets: hot ≥ 50 °C within 1 min, cold < 20 °C within 2 min"),
    ("Flush little-used outlets", "Water / legionella", "Weekly", 2,
     "ACOP L8: run little-used outlets"),
    ("Fire risk assessment review", "Fire", "Annual", 30,
     "Regulatory Reform (Fire Safety) Order 2005"),
    ("Portable appliance testing", "Electrical", "Annual", 30,
     "Inspection and testing of in-service electrical equipment"),
    ("Fixed wiring (EICR)", "Electrical", "Five-yearly", 90,
     "BS 7671 electrical installation condition report"),
    ("Gas safety inspection", "Gas", "Annual", 30,
     "Gas Safety (Installation and Use) Regulations"),
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fire_drills (
    drill_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    drill_date          TEXT NOT NULL,
    drill_time          TEXT,
    drill_type          TEXT NOT NULL DEFAULT 'Planned drill',
    scenario            TEXT,
    evacuation_seconds  INTEGER,
    assembly_point      TEXT,
    people_evacuated    INTEGER,
    rollcall_id         INTEGER,
    rollcall_expected   INTEGER,
    rollcall_accounted  INTEGER,
    rollcall_missing    INTEGER,
    rollcall_seconds    INTEGER,
    rollcall_complete   INTEGER NOT NULL DEFAULT 0,
    issues_found        TEXT,
    led_by              TEXT,
    recorded_by         TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_fire_drills_date ON fire_drills(drill_date);

CREATE TABLE IF NOT EXISTS premises_check_types (
    type_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    category       TEXT NOT NULL DEFAULT 'General',
    frequency      TEXT NOT NULL DEFAULT 'Monthly',
    due_soon_days  INTEGER NOT NULL DEFAULT 7,
    guidance       TEXT,
    responsible    TEXT,
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_premises_check_type_name
    ON premises_check_types(LOWER(name));

CREATE TABLE IF NOT EXISTS premises_checks (
    check_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id      INTEGER NOT NULL,
    checked_on   TEXT NOT NULL,
    checked_at   TEXT,
    location     TEXT,
    result       TEXT NOT NULL DEFAULT 'Pass',
    findings     TEXT,
    checked_by   TEXT,
    recorded_by  TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (type_id) REFERENCES premises_check_types(type_id)
);
CREATE INDEX IF NOT EXISTS idx_premises_checks_type
    ON premises_checks(type_id, checked_on);

CREATE TABLE IF NOT EXISTS premises_actions (
    action_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    drill_id      INTEGER,
    check_id      INTEGER,
    action        TEXT NOT NULL,
    owner         TEXT,
    due_date      TEXT,
    status        TEXT NOT NULL DEFAULT 'Open',
    completed_on  TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    CHECK ((drill_id IS NULL) <> (check_id IS NULL)),
    FOREIGN KEY (drill_id) REFERENCES fire_drills(drill_id),
    FOREIGN KEY (check_id) REFERENCES premises_checks(check_id)
);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class FireDrill:
    drill_id: int
    drill_date: str
    drill_time: str | None
    drill_type: str
    scenario: str | None
    evacuation_seconds: int | None
    assembly_point: str | None
    people_evacuated: int | None
    rollcall_id: int | None
    rollcall_expected: int | None
    rollcall_accounted: int | None
    rollcall_missing: int | None
    rollcall_seconds: int | None
    rollcall_complete: bool
    issues_found: str | None
    led_by: str | None
    recorded_by: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def evacuation_label(self) -> str:
        return fmt_duration(self.evacuation_seconds)


@dataclass
class CheckType:
    type_id: int
    name: str
    category: str
    frequency: str
    due_soon_days: int
    guidance: str | None
    responsible: str | None
    active: bool
    created_at: str
    updated_at: str


@dataclass
class PremisesCheck:
    check_id: int
    type_id: int
    checked_on: str
    checked_at: str | None
    location: str | None
    result: str
    findings: str | None
    checked_by: str | None
    recorded_by: str | None
    created_at: str
    type_name: str | None = None


@dataclass
class PremisesAction:
    action_id: int
    drill_id: int | None
    check_id: int | None
    action: str
    owner: str | None
    due_date: str | None
    status: str
    completed_on: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def source(self) -> str:
        return (f"Drill #{self.drill_id}" if self.drill_id
                else f"Check #{self.check_id}")

    @property
    def is_overdue(self) -> bool:
        return (self.status == ACTION_OPEN and bool(self.due_date)
                and self.due_date < _dt.date.today().isoformat())


@dataclass
class DueLine:
    """One row of the overdue-checks register."""
    type_id: int | None
    name: str
    category: str
    frequency: str
    last_done: str | None
    last_result: str | None
    next_due: str | None
    state: str
    days_overdue: int = 0


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
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Premises checks schema ready at %s", DB_PATH)
    _DB_READY = True


def _drill(r: _sql.Row) -> FireDrill:
    d = {k: r[k] for k in FireDrill.__dataclass_fields__}
    d["rollcall_complete"] = bool(d["rollcall_complete"])
    return FireDrill(**d)


def _ctype(r: _sql.Row) -> CheckType:
    d = {k: r[k] for k in CheckType.__dataclass_fields__}
    d["active"] = bool(d["active"])
    return CheckType(**d)


def _check(r: _sql.Row) -> PremisesCheck:
    keys = r.keys()
    return PremisesCheck(
        **{k: r[k] for k in PremisesCheck.__dataclass_fields__
           if k != "type_name"},
        type_name=r["type_name"] if "type_name" in keys else None)


def _action(r: _sql.Row) -> PremisesAction:
    return PremisesAction(**{k: r[k]
                             for k in PremisesAction.__dataclass_fields__})


# ── Helpers ─────────────────────────────────────────────────────────

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


def _date(v: Any, label: str, *, required: bool = False,
          not_future: bool = False) -> str | None:
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
    if not_future and s > _dt.date.today().isoformat():
        raise ValidationError(f"{label} cannot be in the future")
    return s


def _time(v: Any, label: str) -> str | None:
    s = _text(v)
    if not s:
        return None
    if len(s) == 4 and s[1] == ":":
        s = "0" + s
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    return s


def _int(v: Any, label: str) -> int | None:
    if v in (None, ""):
        return None
    try:
        n = int(str(v).strip())
    except ValueError:
        raise ValidationError(f"{label} must be a whole number") from None
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    return n


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def parse_duration(v: Any, label: str = "Evacuation time") -> int | None:
    """``"3:45"`` (m:ss), ``"225"`` (seconds) or ``"4m"`` → seconds."""
    s = _text(v)
    if not s:
        return None
    s = s.lower().replace(" ", "")
    try:
        if ":" in s:
            m, _, sec = s.partition(":")
            if not sec.isdigit() or int(sec) > 59:
                raise ValueError
            n = int(m) * 60 + int(sec)
        elif s.endswith("m"):
            n = int(float(s[:-1]) * 60)
        else:
            n = int(s.rstrip("s"))
    except ValueError:
        raise ValidationError(f"{label} must be m:ss or a number of "
                              "seconds") from None
    if n < 0 or n > 6 * 3600:
        raise ValidationError(f"{label} looks wrong ({n} seconds)")
    return n


def fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


def _writer(action: str) -> access.Principal:
    p = access.current()
    p.require(access.OPERATIONS, action)
    return p


def _reader() -> None:
    p = access.current()
    if not (p.can(access.OPERATIONS) or p.can(access.GOVERNANCE)
            or p.can(access.REPORTS)):
        p.require(access.OPERATIONS, "fire and premises records")


def _who(p: access.Principal) -> str | None:
    return p.staff_name or p.username or None


# ── Fire drills ─────────────────────────────────────────────────────

_DRILL_FIELDS = ("drill_date", "drill_time", "drill_type", "scenario",
                 "evacuation_seconds", "assembly_point", "people_evacuated",
                 "rollcall_complete", "rollcall_seconds", "issues_found",
                 "led_by", "notes")


def _drill_payload(payload: dict[str, Any],
                   existing: FireDrill | None) -> dict[str, Any]:
    def get(k: str) -> Any:
        return payload.get(k, getattr(existing, k) if existing else None)
    evac = payload.get("evacuation_time")
    return {
        "drill_date": _date(get("drill_date"), "Drill date", required=True,
                            not_future=True),
        "drill_time": _time(get("drill_time"), "Time of alarm"),
        "drill_type": _choice(get("drill_type"), DRILL_TYPES, "Drill type",
                              DEFAULT_DRILL_TYPE),
        "scenario": _text(get("scenario")),
        "evacuation_seconds": (parse_duration(evac) if evac not in (None, "")
                               else _int(get("evacuation_seconds"),
                                         "Evacuation seconds")),
        "assembly_point": _text(get("assembly_point")),
        "people_evacuated": _int(get("people_evacuated"),
                                 "People evacuated"),
        "rollcall_complete": 1 if get("rollcall_complete") else 0,
        "rollcall_seconds": (parse_duration(payload["rollcall_time"],
                                            "Roll call time")
                             if payload.get("rollcall_time")
                             else _int(get("rollcall_seconds"),
                                       "Roll call seconds")),
        "issues_found": _text(get("issues_found")),
        "led_by": _text(get("led_by")),
        "notes": _text(get("notes")),
    }


def log_drill(payload: dict[str, Any]) -> FireDrill:
    """Record a drill, evacuation or false alarm in the fire log.

    ``evacuation_time`` may be given as m:ss. Pass ``rollcall_id`` to link
    the emergency roll call and copy its figures.
    """
    p = _writer("record fire drills")
    init_db()
    d = _drill_payload(payload, None)
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO fire_drills ({', '.join(_DRILL_FIELDS)}, "  # DBW001: literal column list
            f"recorded_by) VALUES ({', '.join('?' * len(_DRILL_FIELDS))}, ?)",
            (*[d[k] for k in _DRILL_FIELDS], _who(p)))
        new_id = cur.lastrowid
    if payload.get("rollcall_id"):
        return link_rollcall(new_id, int(payload["rollcall_id"]))
    return get_drill(new_id)


def update_drill(drill_id: int, payload: dict[str, Any]) -> FireDrill:
    _writer("record fire drills")
    existing = get_drill(drill_id)
    d = _drill_payload(payload, existing)
    with _connect() as conn:
        conn.execute(
            "UPDATE fire_drills SET "
            + ", ".join(f"{k}=?" for k in _DRILL_FIELDS)  # DBW001: literal column list
            + ", updated_at=datetime('now') WHERE drill_id=?",
            (*[d[k] for k in _DRILL_FIELDS], existing.drill_id))
    return get_drill(existing.drill_id)


def get_drill(drill_id: int) -> FireDrill:
    _reader()
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM fire_drills WHERE drill_id=?",
                         (int(drill_id),)).fetchone()
    if r is None:
        raise ValidationError(f"No fire drill #{drill_id}")
    return _drill(r)


def list_drills(*, date_from: str | None = None, date_to: str | None = None,
                drill_type: str | None = None) -> list[FireDrill]:
    _reader()
    init_db()
    clauses, args = [], []
    if date_from:
        clauses.append("drill_date >= ?")
        args.append(_date(date_from, "From"))
    if date_to:
        clauses.append("drill_date <= ?")
        args.append(_date(date_to, "To"))
    if drill_type:
        clauses.append("drill_type = ?")
        args.append(_choice(drill_type, DRILL_TYPES, "Drill type"))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_drill(r) for r in conn.execute(
            f"SELECT * FROM fire_drills{where} "  # DBW001: literal clauses
            "ORDER BY drill_date DESC, drill_time DESC", args).fetchall()]


def _rollcall():
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_rollcall as _rc,
    )
    return _rc


def recent_rollcalls(limit: int = 30) -> list[Any]:
    """Emergency roll calls (from attendance) that a drill can link to."""
    _reader()
    return _rollcall().list_drills(limit=limit)


def link_rollcall(drill_id: int, rollcall_id: int) -> FireDrill:
    """Link the attendance roll call for this drill and copy its figures.

    The roll call is complete when it was closed with nobody missing; its
    duration (alarm to all-clear) is kept as the roll-call time. The
    evacuation time stays whatever the fire marshal timed.
    """
    _writer("record fire drills")
    d = get_drill(drill_id)
    rc = _rollcall()
    call = rc.get_drill(int(rollcall_id))
    if call is None:
        raise ValidationError(f"No roll call #{rollcall_id}")
    rep = rc.drill_report(call.drill_id)
    missing = len(rep["missing"])
    complete = 1 if call.state == rc.CLOSED and missing == 0 else 0
    with _connect() as conn:
        conn.execute(
            "UPDATE fire_drills SET rollcall_id=?, rollcall_expected=?, "
            "rollcall_accounted=?, rollcall_missing=?, rollcall_seconds=?, "
            "rollcall_complete=?, "
            "assembly_point=COALESCE(assembly_point, ?), "
            "updated_at=datetime('now') WHERE drill_id=?",
            (int(rollcall_id), rep["expected"],
             rep["accounted"] + rep["excused"], missing,
             rep["duration_seconds"], complete, rep["assembly_point"],
             d.drill_id))
    return get_drill(d.drill_id)


def log_drill_from_rollcall(rollcall_id: int, *,
                            scenario: str | None = None,
                            issues_found: str | None = None,
                            led_by: str | None = None) -> FireDrill:
    """Start a fire-log entry from a closed roll call (date, time, type
    and figures come from the roll call)."""
    _writer("record fire drills")
    rc = _rollcall()
    r = rc.get_drill(int(rollcall_id))
    if r is None:
        raise ValidationError(f"No roll call #{rollcall_id}")
    with _connect() as conn:
        dup = conn.execute("SELECT drill_id FROM fire_drills WHERE "
                           "rollcall_id=?", (int(rollcall_id),)).fetchone()
    if dup:
        raise ValidationError(f"Roll call #{rollcall_id} is already logged "
                              f"as fire drill #{dup[0]}")
    started = r.started_at.replace("T", " ")
    return log_drill({
        "drill_date": r.date,
        "drill_time": started[11:16] if len(started) >= 16 else None,
        "drill_type": _ROLLCALL_KIND_TO_TYPE.get(r.kind, DEFAULT_DRILL_TYPE),
        "scenario": scenario, "issues_found": issues_found,
        "led_by": led_by or r.started_by, "rollcall_id": r.drill_id})


# ── Check types ─────────────────────────────────────────────────────

def _type_payload(payload: dict[str, Any],
                  existing: CheckType | None) -> dict[str, Any]:
    def get(k: str) -> Any:
        return payload.get(k, getattr(existing, k) if existing else None)
    due = _int(get("due_soon_days"), "Due-soon warning (days)")
    return {
        "name": _require(get("name"), "Check name"),
        "category": _choice(get("category"), CHECK_CATEGORIES, "Category",
                            "General"),
        "frequency": _choice(get("frequency"), tuple(FREQUENCIES),
                             "Frequency", "Monthly"),
        "due_soon_days": 7 if due is None else due,
        "guidance": _text(get("guidance")),
        "responsible": _text(get("responsible")),
        "active": 0 if get("active") is False else 1,
    }


def create_check_type(payload: dict[str, Any]) -> CheckType:
    _writer("configure premises checks")
    init_db()
    p = _type_payload(payload, None)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO premises_check_types (name, category, frequency,"
                " due_soon_days, guidance, responsible, active) VALUES "
                "(:name, :category, :frequency, :due_soon_days, :guidance, "
                ":responsible, :active)", p)
        except _sql.IntegrityError:
            raise ValidationError(f"A check called '{p['name']}' already "
                                  "exists") from None
        new_id = cur.lastrowid
    return get_check_type(new_id)


def update_check_type(type_id: int, payload: dict[str, Any]) -> CheckType:
    _writer("configure premises checks")
    existing = get_check_type(type_id)
    p = _type_payload(payload, existing)
    p["type_id"] = existing.type_id
    with _connect() as conn:
        try:
            conn.execute(
                "UPDATE premises_check_types SET name=:name, "
                "category=:category, frequency=:frequency, "
                "due_soon_days=:due_soon_days, guidance=:guidance, "
                "responsible=:responsible, active=:active, "
                "updated_at=datetime('now') WHERE type_id=:type_id", p)
        except _sql.IntegrityError:
            raise ValidationError(f"A check called '{p['name']}' already "
                                  "exists") from None
    return get_check_type(existing.type_id)


def get_check_type(type_id: int) -> CheckType:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM premises_check_types WHERE "
                         "type_id=?", (int(type_id),)).fetchone()
    if r is None:
        raise ValidationError(f"No premises check type #{type_id}")
    return _ctype(r)


def list_check_types(*, active_only: bool = False,
                     category: str | None = None) -> list[CheckType]:
    init_db()
    clauses, args = [], []
    if active_only:
        clauses.append("active = 1")
    if category:
        clauses.append("category = ?")
        args.append(_choice(category, CHECK_CATEGORIES, "Category"))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_ctype(r) for r in conn.execute(
            f"SELECT * FROM premises_check_types{where} "  # DBW001: literal clauses
            "ORDER BY category, name COLLATE NOCASE", args).fetchall()]


def install_default_check_types() -> list[CheckType]:
    """Add the standard UK check list for any name not already present."""
    _writer("configure premises checks")
    have = {t.name.lower() for t in list_check_types()}
    made = []
    for name, cat, freq, soon, guide in DEFAULT_CHECK_TYPES:
        if name.lower() in have:
            continue
        made.append(create_check_type({
            "name": name, "category": cat, "frequency": freq,
            "due_soon_days": soon, "guidance": guide}))
    return made


# ── Checks ──────────────────────────────────────────────────────────

_CHECK_SELECT = ("SELECT c.*, t.name AS type_name FROM premises_checks c "
                 "JOIN premises_check_types t ON t.type_id = c.type_id")


def record_check(payload: dict[str, Any]) -> PremisesCheck:
    """Record a check. A Fail (or advisory) should say what was found;
    pass ``action`` to raise a follow-up action at the same time."""
    p = _writer("record premises checks")
    tid = _int(payload.get("type_id"), "Check type")
    if not tid:
        raise ValidationError("Check type is required")
    t = get_check_type(tid)
    result = _choice(payload.get("result"), RESULTS, "Result", PASS)
    findings = _text(payload.get("findings"))
    if result != PASS and not findings:
        raise ValidationError("Say what was found when a check is not a "
                              "clean pass")
    on = _date(payload.get("checked_on"), "Checked on", not_future=True) \
        or _dt.date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO premises_checks (type_id, checked_on, checked_at, "
            "location, result, findings, checked_by, recorded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (t.type_id, on, _time(payload.get("checked_at"), "Time"),
             _text(payload.get("location")), result, findings,
             _text(payload.get("checked_by")) or _who(p), _who(p)))
        new_id = cur.lastrowid
    if _text(payload.get("action")):
        add_action({"check_id": new_id, "action": payload["action"],
                    "owner": payload.get("action_owner"),
                    "due_date": payload.get("action_due")})
    return get_check(new_id)


def get_check(check_id: int) -> PremisesCheck:
    _reader()
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_CHECK_SELECT} WHERE c.check_id=?",
                         (int(check_id),)).fetchone()
    if r is None:
        raise ValidationError(f"No premises check #{check_id}")
    return _check(r)


def list_checks(*, type_id: int | None = None, result: str | None = None,
                date_from: str | None = None, date_to: str | None = None,
                limit: int = 500) -> list[PremisesCheck]:
    _reader()
    init_db()
    clauses, args = [], []
    if type_id is not None:
        clauses.append("c.type_id = ?")
        args.append(int(type_id))
    if result:
        clauses.append("c.result = ?")
        args.append(_choice(result, RESULTS, "Result"))
    if date_from:
        clauses.append("c.checked_on >= ?")
        args.append(_date(date_from, "From"))
    if date_to:
        clauses.append("c.checked_on <= ?")
        args.append(_date(date_to, "To"))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        return [_check(r) for r in conn.execute(
            f"{_CHECK_SELECT}{where} "  # DBW001: literal clauses
            "ORDER BY c.checked_on DESC, c.check_id DESC LIMIT ?",
            args).fetchall()]


# ── Actions ─────────────────────────────────────────────────────────

def add_action(payload: dict[str, Any]) -> PremisesAction:
    _writer("record premises actions")
    drill_id = _int(payload.get("drill_id"), "Drill")
    check_id = _int(payload.get("check_id"), "Check")
    if bool(drill_id) == bool(check_id):
        raise ValidationError("An action belongs to one drill or one check")
    if drill_id:
        get_drill(drill_id)
    else:
        get_check(check_id)
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO premises_actions (drill_id, check_id, action, owner,"
            " due_date, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (drill_id, check_id, _require(payload.get("action"), "Action"),
             _text(payload.get("owner")),
             _date(payload.get("due_date"), "Due date"),
             _text(payload.get("notes"))))
        new_id = cur.lastrowid
    return get_action(new_id)


def get_action(action_id: int) -> PremisesAction:
    _reader()
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM premises_actions WHERE action_id=?",
                         (int(action_id),)).fetchone()
    if r is None:
        raise ValidationError(f"No premises action #{action_id}")
    return _action(r)


def list_actions(*, open_only: bool = False, drill_id: int | None = None,
                 check_id: int | None = None) -> list[PremisesAction]:
    _reader()
    init_db()
    clauses, args = [], []
    if open_only:
        clauses.append("status = 'Open'")
    if drill_id is not None:
        clauses.append("drill_id = ?")
        args.append(int(drill_id))
    if check_id is not None:
        clauses.append("check_id = ?")
        args.append(int(check_id))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_action(r) for r in conn.execute(
            f"SELECT * FROM premises_actions{where} "  # DBW001: literal clauses
            "ORDER BY status, due_date IS NULL, due_date, action_id",
            args).fetchall()]


def set_action_status(action_id: int, status: str, *,
                      notes: str | None = None) -> PremisesAction:
    _writer("record premises actions")
    a = get_action(action_id)
    new = _choice(status, ACTION_STATUSES, "Status")
    if new == ACTION_CANCELLED and not _text(notes):
        raise ValidationError("Say why the action is cancelled")
    note = _text(notes)
    with _connect() as conn:
        conn.execute(
            "UPDATE premises_actions SET status=?, completed_on=?, "
            "notes=CASE WHEN ? IS NULL THEN notes "
            "ELSE COALESCE(notes || '; ', '') || ? END, "
            "updated_at=datetime('now') WHERE action_id=?",
            (new, _dt.date.today().isoformat() if new == ACTION_DONE
             else None, note, note, a.action_id))
    return get_action(a.action_id)


# ── Reports ─────────────────────────────────────────────────────────

def _due_state(next_due: str | None, soon_days: int,
               today: _dt.date) -> tuple[str, int]:
    if next_due is None:
        return NEVER, 0
    nd = _dt.date.fromisoformat(next_due)
    if nd < today:
        return OVERDUE, (today - nd).days
    if (nd - today).days <= soon_days:
        return DUE_SOON, 0
    return OK, 0


def check_register(*, today: str | None = None) -> list[DueLine]:
    """Every active check type (and the termly fire drill) with its last
    date, next due date and state."""
    _reader()
    init_db()
    day = _dt.date.fromisoformat(today) if today else _dt.date.today()
    with _connect() as conn:
        last = {r["type_id"]: (r["checked_on"], r["result"]) for r in
                conn.execute(
                    "SELECT c.type_id, c.checked_on, c.result FROM "
                    "premises_checks c JOIN (SELECT type_id, "
                    "MAX(checked_on) AS m FROM premises_checks GROUP BY "
                    "type_id) x ON x.type_id = c.type_id AND "
                    "x.m = c.checked_on ORDER BY c.check_id")}
        drill = conn.execute(
            "SELECT MAX(drill_date) FROM fire_drills WHERE drill_type IN "
            f"({','.join('?' * len(PRACTICE_TYPES))})",
            PRACTICE_TYPES).fetchone()[0]
    out = []
    for t in list_check_types(active_only=True):
        done, result = last.get(t.type_id, (None, None))
        nxt = ((_dt.date.fromisoformat(done)
                + _dt.timedelta(days=FREQUENCIES[t.frequency])).isoformat()
               if done else None)
        state, late = _due_state(nxt, t.due_soon_days, day)
        out.append(DueLine(t.type_id, t.name, t.category, t.frequency, done,
                           result, nxt, state, late))
    nxt = ((_dt.date.fromisoformat(drill)
            + _dt.timedelta(days=DRILL_INTERVAL_DAYS)).isoformat()
           if drill else None)
    state, late = _due_state(nxt, DRILL_DUE_SOON_DAYS, day)
    out.append(DueLine(None, "Fire evacuation drill", "Fire", "Termly",
                       drill, None, nxt, state, late))
    return out


def overdue_checks(*, include_due_soon: bool = False,
                   today: str | None = None) -> list[DueLine]:
    """Checks that are overdue or have never been done (and optionally
    those due soon), most overdue first."""
    wanted = {OVERDUE, NEVER} | ({DUE_SOON} if include_due_soon else set())
    rows = [d for d in check_register(today=today) if d.state in wanted]
    return sorted(rows, key=lambda d: (d.state != NEVER, -d.days_overdue,
                                       d.next_due or ""))


def failed_checks(*, open_actions_only: bool = False,
                  days: int = 90) -> list[PremisesCheck]:
    """Fails and advisories in the last ``days`` days."""
    since = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    rows = [c for c in list_checks(date_from=since) if c.result != PASS]
    if open_actions_only:
        open_ids = {a.check_id for a in list_actions(open_only=True)}
        rows = [c for c in rows if c.check_id in open_ids]
    return rows


def drill_report(*, date_from: str | None = None,
                 date_to: str | None = None) -> dict[str, Any]:
    """Drill statistics for the period: count by type, average and worst
    evacuation time, roll calls completed, issues raised."""
    drills = list_drills(date_from=date_from, date_to=date_to)
    times = [d.evacuation_seconds for d in drills
             if d.evacuation_seconds is not None]
    by_type: dict[str, int] = {}
    for d in drills:
        by_type[d.drill_type] = by_type.get(d.drill_type, 0) + 1
    ids = {d.drill_id for d in drills}
    acts = [a for a in list_actions() if a.drill_id in ids]
    return {
        "drills": len(drills), "by_type": by_type,
        "average_evacuation": fmt_duration(
            round(sum(times) / len(times)) if times else None),
        "slowest_evacuation": fmt_duration(max(times) if times else None),
        "rollcalls_linked": sum(1 for d in drills if d.rollcall_id),
        "rollcalls_complete": sum(1 for d in drills if d.rollcall_complete),
        "with_issues": sum(1 for d in drills if d.issues_found),
        "actions": len(acts),
        "actions_open": sum(1 for a in acts if a.status == ACTION_OPEN),
    }
