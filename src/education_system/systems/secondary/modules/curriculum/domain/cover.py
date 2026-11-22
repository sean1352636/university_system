"""Cover: who teaches a lesson when its teacher is away.

**Absences.** A teacher's absence (dates, optionally a range of periods each
day, a reason category - never medical details) finds every timetabled lesson
they teach in that time and makes a *cover request* for each. Changing the
absence dates adds or cancels requests to match; cancelling the absence
cancels the open ones. Cover can also be added by hand for a single lesson
(the old "New").

**Cover requests** keep the old fields and statuses: Pending -> Assigned ->
Confirmed -> Completed, or Cancelled. Assigning someone checks that they
aren't the absent teacher, aren't teaching or covering then, aren't away
themselves, and (for supply staff) are active and DBS-cleared - those are
refused. Going over the weekly cover limit is a warning. The absent teacher
can leave cover work; the lesson's plan (if any) is shown with it. The cover
person can be e-mailed the details.

**Supply staff** (the old Cover Agency roster) can be assigned like staff;
their periods and cost show in the supply report.

**Who.** All staff can view cover, report their own absence and set work for
their own lessons; the person covering confirms or completes it. Everything
else is for :data:`COVER_EDITORS` (the cover manager).
"""

from __future__ import annotations

import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import academic_year as _AY  # noqa: F401 - schema registered before any write
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    COVER_EDITORS,
    STAFF_ABSENCE_EDITORS,
    Principal,
)
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

STATUSES: tuple[str, ...] = ("Pending", "Assigned", "Confirmed", "Completed", "Cancelled")
OPEN = ("Pending", "Assigned", "Confirmed")
REASONS: tuple[str, ...] = ("Illness", "Training / CPD", "School trip", "Meeting",
                            "Exam duty", "Personal / family", "Other")
SUPPLY_ROLES: tuple[str, ...] = ("Supply teacher", "Cover supervisor", "Teaching assistant")
DEFAULT_WEEKLY_LIMIT = 3
MAX_ABSENCE_DAYS = 120
#: Longest absence HR (Staff Absence) may record in one go, e.g. maternity leave.
MAX_LONG_ABSENCE_DAYS = 400

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cover_absences (
    absence_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_name     TEXT NOT NULL,
    teacher_username TEXT,
    start_date       TEXT NOT NULL,
    end_date         TEXT NOT NULL,
    from_period      INTEGER,
    to_period        INTEGER,
    reason           TEXT NOT NULL,
    notes            TEXT,
    status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    created_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT
);
CREATE TABLE IF NOT EXISTS supply_staff (
    supply_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name    TEXT NOT NULL,
    agency_name  TEXT,
    role         TEXT NOT NULL DEFAULT 'Supply teacher',
    hourly_rate  REAL,
    email        TEXT,
    phone        TEXT,
    dbs_cleared  INTEGER NOT NULL DEFAULT 0,
    dbs_checked_on TEXT,
    is_active    INTEGER NOT NULL DEFAULT 1,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    created_by   TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by   TEXT
);
CREATE TABLE IF NOT EXISTS cover_requests (
    cover_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,
    period          INTEGER NOT NULL,
    group_id        INTEGER REFERENCES teaching_groups (group_id) ON DELETE SET NULL,
    lesson_id       INTEGER REFERENCES timetable_lessons (lesson_id) ON DELETE SET NULL,
    absence_id      INTEGER REFERENCES cover_absences (absence_id) ON DELETE SET NULL,
    group_code      TEXT NOT NULL,
    year_group      INTEGER,
    subject_code    TEXT,
    room            TEXT,
    absent_name     TEXT NOT NULL,
    absent_username TEXT,
    cover_name      TEXT,
    cover_username  TEXT,
    supply_id       INTEGER REFERENCES supply_staff (supply_id),
    status          TEXT NOT NULL DEFAULT 'Pending'
                    CHECK (status IN ('Pending', 'Assigned', 'Confirmed', 'Completed',
                                      'Cancelled')),
    work_set        TEXT,
    notes           TEXT,
    rate_charged    REAL,
    notified_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    created_by      TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by      TEXT
);
CREATE INDEX IF NOT EXISTS ix_cover_requests_date ON cover_requests (date, period);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cover_requests_lesson
    ON cover_requests (date, period, group_code) WHERE status != 'Cancelled';
CREATE TABLE IF NOT EXISTS cover_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS cover_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    cover_id   INTEGER,
    absence_id INTEGER,
    supply_id  INTEGER,
    action     TEXT NOT NULL,
    actor      TEXT NOT NULL,
    detail     TEXT,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("cover", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Absence:
    absence_id: int
    teacher_name: str
    teacher_username: str | None
    start_date: str
    end_date: str
    from_period: int | None
    to_period: int | None
    reason: str
    notes: str | None
    status: str
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def periods_label(self) -> str:
        if self.from_period is None and self.to_period is None:
            return "all day"
        return f"P{self.from_period or 1}-P{self.to_period or len(TT.periods())}"

    @property
    def dates_label(self) -> str:
        return self.start_date if self.start_date == self.end_date else \
            f"{self.start_date} to {self.end_date}"


@dataclass(frozen=True)
class Supply:
    supply_id: int
    full_name: str
    agency_name: str | None
    role: str
    hourly_rate: float | None
    email: str | None
    phone: str | None
    dbs_cleared: bool
    dbs_checked_on: str | None
    is_active: bool
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None


@dataclass(frozen=True)
class Cover:
    cover_id: int
    date: str
    period: int
    group_id: int | None
    lesson_id: int | None
    absence_id: int | None
    group_code: str
    year_group: int | None
    subject_code: str | None
    room: str | None
    absent_name: str
    absent_username: str | None
    cover_name: str | None
    cover_username: str | None
    supply_id: int | None
    status: str
    work_set: str | None
    notes: str | None
    rate_charged: float | None
    notified_at: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def is_open(self) -> bool:
        return self.status in OPEN

    @property
    def when(self) -> str:
        return f"{_dt.date.fromisoformat(self.date):%a %d %b} P{self.period}"


@dataclass(frozen=True)
class Candidate:
    """Someone who could cover a lesson."""
    name: str
    username: str | None
    email: str | None
    kind: str                  # "Staff" or "Supply"
    supply_id: int | None
    covers_this_week: int
    limit: int

    @property
    def over_limit(self) -> bool:
        return self.kind == "Staff" and self.covers_this_week >= self.limit

    @property
    def label(self) -> str:
        extra = (f"{self.covers_this_week} cover(s) this week" if self.kind == "Staff"
                 else "supply")
        return f"{self.name} ({extra})"


def _make(cls, r):
    out = {k: r[k] for k in cls.__dataclass_fields__}
    for k in ("dbs_cleared", "is_active"):
        if k in out:
            out[k] = bool(out[k])
    return cls(**out)


# ── Helpers ──────────────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in COVER_EDITORS


def can_record_any_absence(actor: Principal) -> bool:
    """The cover manager, or HR (Staff Absence), may record anyone's absence."""
    return is_editor(actor) or actor.role in STAFF_ABSENCE_EDITORS


def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if not actor.is_staff:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only school staff can use cover.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the cover manager can do this.")


def _audit(conn, action: str, actor: Principal, *, cover_id: int | None = None,
           absence_id: int | None = None, supply_id: int | None = None,
           detail: dict | None = None) -> None:
    conn.execute("INSERT INTO cover_audit (cover_id, absence_id, supply_id, action, actor, "
                 "detail) VALUES (?, ?, ?, ?, ?, ?)",
                 (cover_id, absence_id, supply_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


def _date(value: Any, label: str, problems: list[str]) -> _dt.date | None:
    if isinstance(value, _dt.date):
        return value
    if value in (None, ""):
        problems.append(f"{label} is required")
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be YYYY-MM-DD")
        return None


def _int(value: Any, label: str, lo: int, hi: int, problems: list[str]) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        n = lo - 1
    if not lo <= n <= hi:
        problems.append(f"{label} must be from {lo} to {hi}")
        return None
    return n


def _period_minutes(period: int) -> int:
    p = next((x for x in TT.periods() if x.period == period), None)
    if p is None:
        return 60
    return (int(p.end_time[:2]) * 60 + int(p.end_time[3:])) - (
        int(p.start_time[:2]) * 60 + int(p.start_time[3:]))


def _teaches(lesson: TT.Lesson, name: str | None, username: str | None) -> bool:
    return _same(lesson.teacher_username, username) or _same(lesson.teacher, name)


# ── Settings ─────────────────────────────────────────────────────────

def weekly_limit() -> int:
    with database.connect() as conn:
        r = conn.execute("SELECT value FROM cover_settings WHERE key = 'weekly_limit'"
                         ).fetchone()
    return int(r[0]) if r and str(r[0]).isdigit() else DEFAULT_WEEKLY_LIMIT


def set_weekly_limit(value: Any, *, actor: Principal) -> int:
    """How many covers a member of staff should do in a week before a warning."""
    _require_editor(actor, "cover.settings")
    problems: list[str] = []
    n = _int(value, "Weekly cover limit", 0, 30, problems)
    if n is None or problems:
        raise ValidationError(problems or ["Weekly cover limit must be from 0 to 30"])
    with database.connect() as conn:
        conn.execute("INSERT INTO cover_settings (key, value) VALUES ('weekly_limit', ?) "
                     "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (str(n),))
        _audit(conn, "settings", actor, detail={"weekly_limit": n})
    activity_log.record("cover.settings", principal=actor, weekly_limit=n)
    return n


# ── Supply staff (old Cover Agency roster) ───────────────────────────

_SUPPLY_FIELDS = ("full_name", "agency_name", "role", "hourly_rate", "email", "phone",
                  "dbs_cleared", "dbs_checked_on", "notes")


def get_supply(supply_id: int) -> Supply:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM supply_staff WHERE supply_id = ?",
                         (int(supply_id),)).fetchone()
    if r is None:
        raise NotFound(f"No supply staff #{supply_id}")
    return _make(Supply, r)


def list_supply(*, active_only: bool = False) -> list[Supply]:
    sql = "SELECT * FROM supply_staff" + (" WHERE is_active = 1" if active_only else "")
    with database.connect() as conn:
        return [_make(Supply, r) for r in conn.execute(
            sql + " ORDER BY is_active DESC, full_name COLLATE NOCASE")]


def _clean_supply(data: dict[str, Any], current: Supply | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(_SUPPLY_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in _SUPPLY_FIELDS} if current else {}
    merged.update(data)
    out: dict[str, Any] = {}
    out["full_name"] = P._clean_text(merged.get("full_name"), 100)
    if not out["full_name"]:
        problems.append("Name is required")
    out["agency_name"] = P._clean_text(merged.get("agency_name"), 100)
    role = P._clean_text(merged.get("role"), 40) or SUPPLY_ROLES[0]
    if role not in SUPPLY_ROLES:
        problems.append("Role must be one of: " + ", ".join(SUPPLY_ROLES))
    out["role"] = role
    rate = merged.get("hourly_rate")
    out["hourly_rate"] = None
    if rate not in (None, ""):
        try:
            out["hourly_rate"] = round(float(str(rate).strip().lstrip("£")), 2)
            if not 0 <= out["hourly_rate"] <= 500:
                raise ValueError
        except ValueError:
            problems.append("Hourly rate must be a number from 0 to 500")
    out["email"] = P._clean_text(merged.get("email"), 200)
    if out["email"]:
        out["email"] = out["email"].lower()
        if not C.valid_email(out["email"]):
            problems.append("E-mail address doesn't look right")
    out["phone"] = P._clean_text(merged.get("phone"), 30)
    out["dbs_cleared"] = P._as_bool(merged.get("dbs_cleared") or False, "DBS cleared",
                                    problems)
    checked = merged.get("dbs_checked_on")
    out["dbs_checked_on"] = None
    if checked not in (None, ""):
        d = _date(checked, "DBS checked on", problems)
        if d and d > _today():
            problems.append("DBS checked on can't be in the future")
        out["dbs_checked_on"] = d.isoformat() if d else None
    if out["dbs_cleared"] and not out["dbs_checked_on"]:
        problems.append("Record when the DBS check was seen")
    out["notes"] = P._clean_text(merged.get("notes"), 500)
    if problems:
        raise ValidationError(problems)
    return out


def create_supply(data: dict[str, Any], *, actor: Principal) -> Supply:
    _require_editor(actor, "cover.supply_create")
    clean = _clean_supply(data, None)
    with database.connect() as conn:
        cols = list(clean)
        sid = conn.execute(
            f"INSERT INTO supply_staff ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - fixed columns
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username)).lastrowid
        _audit(conn, "supply_create", actor, supply_id=sid)
    activity_log.record("cover.supply_create", target=f"supply:{sid}", principal=actor)
    return get_supply(sid)


def update_supply(supply_id: int, changes: dict[str, Any], *, actor: Principal) -> Supply:
    _require_editor(actor, "cover.supply_update", f"supply:{supply_id}")
    s = get_supply(supply_id)
    clean = _clean_supply(changes, s)
    diff = {k: v for k, v in clean.items() if getattr(s, k) != v}
    if diff:
        with database.connect() as conn:
            sets = ", ".join(f"{k} = ?" for k in diff)
            conn.execute(f"UPDATE supply_staff SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean_supply
                         "updated_by = ? WHERE supply_id = ?",
                         (*diff.values(), actor.username, s.supply_id))
            _audit(conn, "supply_update", actor, supply_id=s.supply_id,
                   detail={"fields": sorted(diff)})
        activity_log.record("cover.supply_update", target=f"supply:{s.supply_id}",
                            principal=actor, fields=sorted(diff))
    return get_supply(s.supply_id)


def toggle_supply(supply_id: int, *, actor: Principal) -> Supply:
    """Old 'Toggle active'. Turning someone off leaves their future cover unassigned."""
    _require_editor(actor, "cover.supply_toggle", f"supply:{supply_id}")
    s = get_supply(supply_id)
    with database.connect() as conn:
        conn.execute("UPDATE supply_staff SET is_active = ?, updated_at = datetime('now'), "
                     "updated_by = ? WHERE supply_id = ?",
                     (0 if s.is_active else 1, actor.username, s.supply_id))
        if s.is_active:
            conn.execute("UPDATE cover_requests SET status = 'Pending', cover_name = NULL, "
                         "supply_id = NULL, rate_charged = NULL, updated_by = ? WHERE "
                         "supply_id = ? AND date >= ? AND status IN ('Assigned', 'Confirmed')",
                         (actor.username, s.supply_id, _today().isoformat()))
        _audit(conn, "supply_toggle", actor, supply_id=s.supply_id,
               detail={"active": not s.is_active})
    activity_log.record("cover.supply_toggle", target=f"supply:{s.supply_id}", principal=actor)
    return get_supply(s.supply_id)


def delete_supply(supply_id: int, *, actor: Principal) -> None:
    _require_editor(actor, "cover.supply_delete", f"supply:{supply_id}")
    s = get_supply(supply_id)
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM cover_requests WHERE supply_id = ?",
                         (s.supply_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"{s.full_name} has covered {n} lesson(s) - make them "
                                   "inactive instead"])
        conn.execute("DELETE FROM supply_staff WHERE supply_id = ?", (s.supply_id,))
        _audit(conn, "supply_delete", actor, supply_id=s.supply_id)
    activity_log.record("cover.supply_delete", target=f"supply:{s.supply_id}", principal=actor)


# ── Reading cover ────────────────────────────────────────────────────

def get(cover_id: int) -> Cover:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM cover_requests WHERE cover_id = ?",
                         (int(cover_id),)).fetchone()
    if r is None:
        raise NotFound(f"No cover #{cover_id}")
    return _make(Cover, r)


def list_covers(*, date: Any = None, date_from: Any = None, date_to: Any = None,
                status: str | None = None, absent: str | None = None,
                cover: str | None = None, absence_id: int | None = None,
                include_cancelled: bool = True) -> list[Cover]:
    """Cover by date and period. *absent* / *cover* match a name or login."""
    where, params = [], []
    problems: list[str] = []
    for value, sql, label in ((date, "date = ?", "Date"), (date_from, "date >= ?", "From"),
                              (date_to, "date <= ?", "To")):
        if value not in (None, ""):
            d = _date(value, label, problems)
            if d:
                where.append(sql)
                params.append(d.isoformat())
    if status:
        if status not in STATUSES:
            problems.append(f"Status must be one of {', '.join(STATUSES)}")
        where.append("status = ?")
        params.append(status)
    elif not include_cancelled:
        where.append("status != 'Cancelled'")
    for value, cols in ((absent, ("absent_name", "absent_username")),
                        (cover, ("cover_name", "cover_username"))):
        if value:
            where.append(f"(lower({cols[0]}) = lower(?) OR lower({cols[1]}) = lower(?))")
            params.extend([value.strip()] * 2)
    if absence_id is not None:
        where.append("absence_id = ?")
        params.append(int(absence_id))
    if problems:
        raise ValidationError(problems)
    sql = "SELECT * FROM cover_requests" + (" WHERE " + " AND ".join(where) if where else "")
    with database.connect() as conn:
        return [_make(Cover, r) for r in conn.execute(
            sql + " ORDER BY date, period, group_code COLLATE NOCASE", params)]


def status_counts(*, date_from: Any = None, date_to: Any = None) -> dict[str, int]:
    out = {s: 0 for s in STATUSES}
    for c in list_covers(date_from=date_from, date_to=date_to):
        out[c.status] += 1
    return out


def daily_load(day: Any) -> dict[str, Any]:
    """Old 'Daily load': cover slots per person that day, and the day's cover."""
    rows = [c for c in list_covers(date=day) if c.status != "Cancelled"]
    by = Counter(c.cover_name or "(unassigned)" for c in rows)
    return {"date": rows[0].date if rows else str(day), "total": len(rows),
            "unassigned": by.pop("(unassigned)", 0), "by_cover": dict(by.most_common()),
            "covers": rows}


def cover_counts(start: Any, end: Any) -> dict[str, int]:
    """Covers done (or booked) per member of staff from *start* to *end* - for fairness."""
    out: Counter = Counter()
    for c in list_covers(date_from=start, date_to=end, include_cancelled=False):
        if c.cover_name and c.supply_id is None:
            out[c.cover_name] += 1
    return dict(out.most_common())


def supply_report(start: Any, end: Any) -> list[dict[str, Any]]:
    """Supply staff: periods covered and cost (hourly rate x period length)."""
    rows: dict[int, dict[str, Any]] = {}
    for c in list_covers(date_from=start, date_to=end, include_cancelled=False):
        if c.supply_id is None:
            continue
        s = get_supply(c.supply_id)
        r = rows.setdefault(s.supply_id, {"supply": s, "periods": 0, "minutes": 0,
                                          "cost": 0.0})
        mins = _period_minutes(c.period)
        r["periods"] += 1
        r["minutes"] += mins
        r["cost"] += round((c.rate_charged or 0) * mins / 60, 2)
    return sorted(rows.values(), key=lambda r: (r["supply"].agency_name or "",
                                                r["supply"].full_name))


def history(*, cover_id: int | None = None, absence_id: int | None = None,
            limit: int = 100) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM cover_audit", []
    if cover_id is not None:
        sql += " WHERE cover_id = ?"
        params.append(int(cover_id))
    elif absence_id is not None:
        sql += " WHERE absence_id = ?"
        params.append(int(absence_id))
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "detail": json.loads(r["detail"]) if r["detail"] else {}}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, limit))]


# ── Who is free ──────────────────────────────────────────────────────

def _absent_then(day: str, period: int) -> list[Absence]:
    return [a for a in list_absences(date_from=day, date_to=day)
            if (a.from_period or 1) <= period <= (a.to_period or 99)]


def busy_reason(day: Any, period: int, *, name: str | None = None,
                username: str | None = None, supply_id: int | None = None,
                ignore_cover: int | None = None) -> str | None:
    """Why this person can't cover then (None if they're free)."""
    problems: list[str] = []
    d = _date(day, "Date", problems)
    if d is None:
        return problems[0]
    iso = d.isoformat()
    if supply_id is None:
        lessons, _label = TT.lessons_on(d)
        for x in lessons:
            if x.period == period and _teaches(x, name, username):
                return f"teaching {x.group_code} then"
        for a in _absent_then(iso, period):
            if _same(a.teacher_username, username) or _same(a.teacher_name, name):
                return f"away ({a.reason})"
    for c in list_covers(date=iso, include_cancelled=False):
        if c.period != period or c.cover_id == ignore_cover:
            continue
        if (supply_id is not None and c.supply_id == supply_id) or (
                supply_id is None and c.supply_id is None and (
                    _same(c.cover_username, username) or _same(c.cover_name, name))):
            return f"already covering {c.group_code} then"
    return None


def _staff() -> list[dict]:
    """Staff who might cover: logins, plus teacher names on the timetable with no login."""
    people = {t["username"].lower(): {"name": t["display_name"] or t["username"],
                                      "username": t["username"], "email": t.get("email")}
              for t in TG.teacher_choices()}
    names = {p["name"].lower() for p in people.values()}
    for t in TT.teachers():
        if t.lower() not in names and t.lower() not in people:
            people[f"name:{t.lower()}"] = {"name": t, "username": None, "email": None}
            names.add(t.lower())
    return sorted(people.values(), key=lambda p: p["name"].lower())


def available(day: Any, period: int, *, cover_id: int | None = None) -> list[Candidate]:
    """Free staff (fewest covers this week first), then active DBS-cleared supply staff."""
    problems: list[str] = []
    d = _date(day, "Date", problems)
    if d is None:
        raise ValidationError(problems)
    monday = d - _dt.timedelta(days=d.weekday())
    counts = Counter()
    for c in list_covers(date_from=monday, date_to=monday + _dt.timedelta(days=6),
                         include_cancelled=False):
        if c.supply_id is None and c.cover_name:
            counts[(c.cover_username or c.cover_name).lower()] += 1
    limit = weekly_limit()
    absent = get(cover_id) if cover_id else None
    out = []
    for p in _staff():
        if absent and (_same(p["username"], absent.absent_username)
                       or _same(p["name"], absent.absent_name)):
            continue
        if busy_reason(d, period, name=p["name"], username=p["username"],
                       ignore_cover=cover_id):
            continue
        out.append(Candidate(p["name"], p["username"], p["email"], "Staff", None,
                             counts[(p["username"] or p["name"]).lower()], limit))
    out.sort(key=lambda c: (c.covers_this_week, c.name.lower()))
    for s in list_supply(active_only=True):
        if s.dbs_cleared and not busy_reason(d, period, supply_id=s.supply_id,
                                             ignore_cover=cover_id):
            out.append(Candidate(s.full_name, None, s.email, "Supply", s.supply_id, 0, limit))
    return out


# ── Absences ─────────────────────────────────────────────────────────

def get_absence(absence_id: int) -> Absence:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM cover_absences WHERE absence_id = ?",
                         (int(absence_id),)).fetchone()
    if r is None:
        raise NotFound(f"No absence #{absence_id}")
    return _make(Absence, r)


def list_absences(*, date_from: Any = None, date_to: Any = None, teacher: str | None = None,
                  include_cancelled: bool = False) -> list[Absence]:
    """Absences overlapping the dates."""
    where, params = [], []
    if date_to:
        where.append("start_date <= ?")
        params.append(str(date_to))
    if date_from:
        where.append("end_date >= ?")
        params.append(str(date_from))
    if teacher:
        where.append("(lower(teacher_name) = lower(?) OR lower(teacher_username) = lower(?))")
        params.extend([teacher.strip()] * 2)
    if not include_cancelled:
        where.append("status = 'active'")
    sql = "SELECT * FROM cover_absences" + (" WHERE " + " AND ".join(where) if where else "")
    with database.connect() as conn:
        return [_make(Absence, r) for r in conn.execute(
            sql + " ORDER BY start_date DESC, teacher_name COLLATE NOCASE", params)]


_ABSENCE_FIELDS = ("teacher_name", "teacher_username", "start_date", "end_date",
                   "from_period", "to_period", "reason", "notes")


def _clean_absence(data: dict[str, Any], current: Absence | None,
                   actor: Principal, *, max_days: int = MAX_ABSENCE_DAYS) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(_ABSENCE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in _ABSENCE_FIELDS} if current else {}
    merged.update(data)
    out: dict[str, Any] = {}
    username = P._clean_text(merged.get("teacher_username"), 100)
    name = P._clean_text(merged.get("teacher_name"), 100)
    if username:
        login = next((t for t in TG.teacher_choices()
                      if t["username"].lower() == username.lower()), None)
        if login is None:
            problems.append(f"'{username}' isn't a secondary staff login")
        else:
            username = login["username"]
            name = name or login["display_name"]
    if not name:
        problems.append("Who is away? Choose a member of staff")
    out["teacher_name"], out["teacher_username"] = name, username
    s = _date(merged.get("start_date"), "First day", problems)
    e = _date(merged.get("end_date") or merged.get("start_date"), "Last day", problems)
    if s and e:
        if e < s:
            problems.append("The last day is before the first day")
        elif (e - s).days > max_days:
            problems.append(f"At most {max_days} days at a time")
        if not can_record_any_absence(actor) and s < _today():
            problems.append("Only the cover manager can record a past absence")
    out["start_date"] = s.isoformat() if s else None
    out["end_date"] = e.isoformat() if e else None
    n = len(TT.periods())
    out["from_period"] = _int(merged.get("from_period"), "From period", 1, n, problems)
    out["to_period"] = _int(merged.get("to_period"), "To period", 1, n, problems)
    if out["from_period"] and out["to_period"] and out["to_period"] < out["from_period"]:
        problems.append("The last period is before the first")
    reason = P._clean_text(merged.get("reason"), 40) or ""
    if reason not in REASONS:
        problems.append("Reason must be one of: " + ", ".join(REASONS))
    out["reason"] = reason
    out["notes"] = P._clean_text(merged.get("notes"), 500)
    if not can_record_any_absence(actor) and not _same(actor.username, username):
        problems.append("You can record your own absence; the cover manager records others'")
    if problems:
        raise ValidationError(problems)
    return out


def _lessons_for(a: Absence | dict[str, Any]) -> list[tuple[_dt.date, TT.Lesson]]:
    g = a if isinstance(a, dict) else {k: getattr(a, k) for k in _ABSENCE_FIELDS}
    s = _dt.date.fromisoformat(g["start_date"])
    e = _dt.date.fromisoformat(g["end_date"])
    lo, hi = g["from_period"] or 1, g["to_period"] or 99
    out = []
    d = s
    while d <= e:
        lessons, _label = TT.lessons_on(d)
        out += [(d, x) for x in lessons if lo <= x.period <= hi
                and _teaches(x, g["teacher_name"], g["teacher_username"])]
        d += _dt.timedelta(days=1)
    return out


def _sync(conn, absence_id: int, actor: Principal,
          lessons: list[tuple[_dt.date, TT.Lesson]]) -> tuple[int, int]:
    """Make the absence's cover match *lessons* (worked out before the write
    transaction opened). Returns (added, cancelled)."""
    r = conn.execute("SELECT * FROM cover_absences WHERE absence_id = ?",
                     (absence_id,)).fetchone()
    a = _make(Absence, r)
    wanted = {} if a.status != "active" else {
        (d.isoformat(), x.period, x.group_code): (d, x) for d, x in lessons}
    have = {(c["date"], c["period"], c["group_code"]): c for c in conn.execute(
        "SELECT * FROM cover_requests WHERE absence_id = ? AND status != 'Cancelled'",
        (absence_id,))}
    added = cancelled = 0
    for key, (d, x) in wanted.items():
        if key in have:
            continue
        clash = conn.execute("SELECT 1 FROM cover_requests WHERE date = ? AND period = ? AND "
                             "group_code = ? AND status != 'Cancelled'", key).fetchone()
        if clash:
            continue
        cid = conn.execute(
            "INSERT INTO cover_requests (date, period, group_id, lesson_id, absence_id, "
            "group_code, year_group, subject_code, room, absent_name, absent_username, "
            "created_by, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d.isoformat(), x.period, x.group_id, x.lesson_id, absence_id, x.group_code,
             x.year_group, x.subject_code, x.room, a.teacher_name, a.teacher_username,
             actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, cover_id=cid, absence_id=absence_id)
        added += 1
    for key, c in have.items():
        if key not in wanted and c["status"] != "Completed":
            conn.execute("UPDATE cover_requests SET status = 'Cancelled', updated_at = "
                         "datetime('now'), updated_by = ?, notes = COALESCE(notes || ' · ', '')"
                         " || 'Absence changed' WHERE cover_id = ?",
                         (actor.username, c["cover_id"]))
            _audit(conn, "cancel", actor, cover_id=c["cover_id"], absence_id=absence_id)
            cancelled += 1
    return added, cancelled


def _max_days(actor: Principal, long_term: bool) -> int:
    return MAX_LONG_ABSENCE_DAYS if long_term and can_record_any_absence(actor) \
        else MAX_ABSENCE_DAYS


def create_absence(data: dict[str, Any], *, actor: Principal, long_term: bool = False
                   ) -> tuple[Absence, int]:
    """Record an absence and make cover for each lesson. Returns (absence, lessons).
    *long_term* (HR / cover manager only) allows up to :data:`MAX_LONG_ABSENCE_DAYS`."""
    _require_staff(actor, "cover.absence_create")
    clean = _clean_absence(data, None, actor, max_days=_max_days(actor, long_term))
    lessons = _lessons_for(clean)
    with database.connect() as conn:
        overlap = conn.execute(
            "SELECT 1 FROM cover_absences WHERE status = 'active' AND start_date <= ? AND "
            "end_date >= ? AND (lower(teacher_name) = lower(?) OR lower(teacher_username) = "
            "lower(?))", (clean["end_date"], clean["start_date"], clean["teacher_name"],
                          clean["teacher_username"] or "")).fetchone()
        if overlap:
            raise ValidationError([f"{clean['teacher_name']} already has an absence in those "
                                   "dates - change that one instead"])
        cols = list(clean)
        aid = conn.execute(
            f"INSERT INTO cover_absences ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - fixed columns
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username)).lastrowid
        _audit(conn, "absence_create", actor, absence_id=aid)
        added, _c = _sync(conn, aid, actor, lessons)
    activity_log.record("cover.absence_create", target=f"absence:{aid}", principal=actor,
                        lessons=added)
    return get_absence(aid), added


def update_absence(absence_id: int, changes: dict[str, Any], *, actor: Principal,
                   long_term: bool = False) -> tuple[Absence, int, int]:
    """Change an absence; cover is added or cancelled to match. Returns
    (absence, added, cancelled)."""
    _require_staff(actor, "cover.absence_update", f"absence:{absence_id}")
    a = get_absence(absence_id)
    if not can_record_any_absence(actor) and not _same(actor.username, a.teacher_username):
        raise PermissionDenied("Only the cover manager can change someone else's absence.")
    if a.status != "active":
        raise ValidationError(["This absence was cancelled"])
    clean = _clean_absence(changes, a, actor, max_days=_max_days(actor, long_term))
    diff = {k: v for k, v in clean.items() if getattr(a, k) != v}
    lessons = _lessons_for(clean)
    with database.connect() as conn:
        if diff:
            sets = ", ".join(f"{k} = ?" for k in diff)
            conn.execute(f"UPDATE cover_absences SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean_absence
                         "updated_by = ? WHERE absence_id = ?",
                         (*diff.values(), actor.username, a.absence_id))
            conn.execute("UPDATE cover_requests SET absent_name = ?, absent_username = ? "
                         "WHERE absence_id = ?", (clean["teacher_name"],
                                                  clean["teacher_username"], a.absence_id))
            _audit(conn, "absence_update", actor, absence_id=a.absence_id,
                   detail={"fields": sorted(diff)})
        added, cancelled = _sync(conn, a.absence_id, actor, lessons)
    activity_log.record("cover.absence_update", target=f"absence:{a.absence_id}",
                        principal=actor, added=added, cancelled=cancelled)
    return get_absence(a.absence_id), added, cancelled


def cancel_absence(absence_id: int, *, actor: Principal) -> int:
    """The teacher is in after all: cancel the absence and its open cover."""
    _require_staff(actor, "cover.absence_cancel", f"absence:{absence_id}")
    a = get_absence(absence_id)
    if not can_record_any_absence(actor) and not _same(actor.username, a.teacher_username):
        raise PermissionDenied("Only the cover manager can cancel someone else's absence.")
    with database.connect() as conn:
        conn.execute("UPDATE cover_absences SET status = 'cancelled', updated_at = "
                     "datetime('now'), updated_by = ? WHERE absence_id = ?",
                     (actor.username, a.absence_id))
        _audit(conn, "absence_cancel", actor, absence_id=a.absence_id)
        _added, cancelled = _sync(conn, a.absence_id, actor, [])
    activity_log.record("cover.absence_cancel", target=f"absence:{a.absence_id}",
                        principal=actor, cancelled=cancelled)
    return cancelled


def delete_absence(absence_id: int, *, actor: Principal) -> int:
    """Remove an absence recorded in error, with its cover that never happened
    (Pending or Cancelled). Refused once anyone has been assigned - cancel it
    instead. Returns how many cover requests went with it."""
    _require_staff(actor, "cover.absence_delete", f"absence:{absence_id}")
    if not can_record_any_absence(actor):
        activity_log.record("cover.absence_delete", target=f"absence:{absence_id}",
                            outcome="denied", principal=actor)
        raise PermissionDenied("Only the cover manager or HR can delete an absence.")
    a = get_absence(absence_id)
    with database.connect() as conn:
        busy = conn.execute("SELECT COUNT(*) FROM cover_requests WHERE absence_id = ? AND "
                            "status NOT IN ('Pending', 'Cancelled')",
                            (a.absence_id,)).fetchone()[0]
        if busy:
            raise ValidationError([f"{busy} cover lesson(s) for this absence are assigned or "
                                   "done - cancel the absence instead"])
        n = conn.execute("DELETE FROM cover_requests WHERE absence_id = ?",
                         (a.absence_id,)).rowcount
        conn.execute("DELETE FROM cover_absences WHERE absence_id = ?", (a.absence_id,))
        _audit(conn, "absence_delete", actor, absence_id=a.absence_id,
               detail={"start": a.start_date, "end": a.end_date, "covers": n})
    activity_log.record("cover.absence_delete", target=f"absence:{a.absence_id}",
                        principal=actor, covers=n)
    return n


def cover_by_absence(absence_ids: list[int] | None = None) -> dict[int, dict[str, int]]:
    """{absence_id: {status: count}} for the cover each absence made."""
    sql = ("SELECT absence_id, status, COUNT(*) FROM cover_requests WHERE absence_id IS NOT "
           "NULL")
    params: list[Any] = []
    if absence_ids is not None:
        if not absence_ids:
            return {}
        sql += f" AND absence_id IN ({', '.join('?' * len(absence_ids))})"  # nosec B608 - placeholders
        params = [int(x) for x in absence_ids]
    out: dict[int, dict[str, int]] = {}
    with database.connect() as conn:
        for aid, status, n in conn.execute(sql + " GROUP BY absence_id, status", params):
            out.setdefault(aid, {})[status] = n
    return out


# ── Single cover requests ────────────────────────────────────────────

def create(data: dict[str, Any], *, actor: Principal) -> Cover:
    """Old 'New': cover for one lesson - a group, date and period, and who is away."""
    _require_editor(actor, "cover.create")
    problems: list[str] = []
    d = _date(data.get("date"), "Date", problems)
    period = _int(data.get("period"), "Period", 1, len(TT.periods()), problems)
    if period is None and not any("Period" in p for p in problems):
        problems.append("Period is required")
    g = None
    try:
        g = TG.get(int(data.get("group_id")))  # type: ignore[arg-type]
    except (TypeError, ValueError, TG.NotFound):
        problems.append("Choose the teaching group")
    if g is not None and not (g.is_current and g.is_active):
        problems.append(f"{g.code} isn't one of this year's open groups")
    absent = P._clean_text(data.get("absent_name"), 100) or (g.teacher_name if g else None)
    if not absent:
        problems.append("Who is away? Enter the absent teacher")
    if problems:
        raise ValidationError(problems)
    lesson = next((x for x in TT.lessons_on(d, group_id=g.group_id)[0]
                   if x.period == period), None)
    from education_system.systems.secondary.modules.curriculum.domain import subjects as S
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM cover_requests WHERE date = ? AND period = ? AND "
                        "group_code = ? AND status != 'Cancelled'",
                        (d.isoformat(), period, g.code)).fetchone():
            raise ValidationError([f"{g.code} already has cover then"])
        cid = conn.execute(
            "INSERT INTO cover_requests (date, period, group_id, lesson_id, group_code, "
            "year_group, subject_code, room, absent_name, absent_username, notes, "
            "created_by, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d.isoformat(), period, g.group_id, lesson.lesson_id if lesson else None, g.code,
             g.year_group, S.get(g.subject_id).code,
             P._clean_text(data.get("room"), 30) or (lesson.room if lesson else g.room),
             absent, P._clean_text(data.get("absent_username"), 100)
             or (lesson.teacher_username if lesson else g.teacher_username),
             P._clean_text(data.get("notes"), 500), actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, cover_id=cid)
    activity_log.record("cover.create", target=f"cover:{cid}", principal=actor)
    return get(cid)


def update(cover_id: int, changes: dict[str, Any], *, actor: Principal) -> Cover:
    """Old 'Edit': room, notes and cover work. The absent teacher may set the work."""
    _require_staff(actor, "cover.update", f"cover:{cover_id}")
    c = get(cover_id)
    allowed = {"work_set", "notes", "room"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValidationError([f"Unknown field(s): {', '.join(sorted(unknown))}"])
    if not is_editor(actor):
        if not _same(actor.username, c.absent_username):
            raise PermissionDenied("Only the cover manager (or the absent teacher, for the "
                                   "work) can change this.")
        if set(changes) - {"work_set"}:
            raise PermissionDenied("You can set the cover work; the cover manager changes "
                                   "the rest.")
    clean = {"work_set": P._clean_text(changes.get("work_set", c.work_set), 4000),
             "notes": P._clean_text(changes.get("notes", c.notes), 500),
             "room": P._clean_text(changes.get("room", c.room), 30)}
    diff = {k: v for k, v in clean.items() if getattr(c, k) != v}
    if diff:
        with database.connect() as conn:
            sets = ", ".join(f"{k} = ?" for k in diff)
            conn.execute(f"UPDATE cover_requests SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys fixed above
                         "updated_by = ? WHERE cover_id = ?",
                         (*diff.values(), actor.username, c.cover_id))
            _audit(conn, "update", actor, cover_id=c.cover_id, detail={"fields": sorted(diff)})
        activity_log.record("cover.update", target=f"cover:{c.cover_id}", principal=actor,
                            fields=sorted(diff))
    return get(c.cover_id)


def assign(cover_id: int, *, actor: Principal, username: str | None = None,
           name: str | None = None, supply_id: int | None = None
           ) -> tuple[Cover, list[str]]:
    """Old 'Assign': a member of staff (login or name) or supply staff. Returns
    (cover, warnings)."""
    _require_editor(actor, "cover.assign", f"cover:{cover_id}")
    c = get(cover_id)
    if c.status in ("Completed", "Cancelled"):
        raise ValidationError([f"This cover is {c.status.lower()}"])
    problems: list[str] = []
    warnings: list[str] = []
    rate = None
    if supply_id not in (None, ""):
        s = get_supply(int(supply_id))
        if not s.is_active:
            problems.append(f"{s.full_name} is inactive")
        if not s.dbs_cleared:
            problems.append(f"{s.full_name} has no DBS clearance recorded - they can't cover")
        name, username, rate = s.full_name, None, s.hourly_rate
        why = busy_reason(c.date, c.period, supply_id=s.supply_id, ignore_cover=c.cover_id)
        supply_id = s.supply_id
    else:
        supply_id = None
        if username:
            login = next((t for t in TG.teacher_choices()
                          if t["username"].lower() == username.strip().lower()), None)
            if login is None:
                problems.append(f"'{username}' isn't a secondary staff login")
            else:
                username, name = login["username"], name or login["display_name"]
        name = P._clean_text(name, 100)
        if not name:
            problems.append("Choose who is covering")
        if _same(username, c.absent_username) or _same(name, c.absent_name):
            problems.append(f"{c.absent_name} is the absent teacher")
        why = busy_reason(c.date, c.period, name=name, username=username,
                          ignore_cover=c.cover_id) if name and not problems else None
    if why:
        problems.append(f"{name} is {why}")
    if problems:
        raise ValidationError(problems)
    if supply_id is None:
        d = _dt.date.fromisoformat(c.date)
        monday = d - _dt.timedelta(days=d.weekday())
        n = sum(1 for x in list_covers(date_from=monday, date_to=monday + _dt.timedelta(days=6),
                                       include_cancelled=False)
                if x.cover_id != c.cover_id and x.supply_id is None and (
                    _same(x.cover_username, username) or _same(x.cover_name, name)))
        if n >= weekly_limit():
            warnings.append(f"{name} already has {n} cover(s) that week (limit "
                            f"{weekly_limit()})")
    with database.connect() as conn:
        conn.execute("UPDATE cover_requests SET cover_name = ?, cover_username = ?, "
                     "supply_id = ?, rate_charged = ?, status = 'Assigned', notified_at = NULL, "
                     "updated_at = datetime('now'), updated_by = ? WHERE cover_id = ?",
                     (name, username, supply_id, rate, actor.username, c.cover_id))
        _audit(conn, "assign", actor, cover_id=c.cover_id,
               detail={"kind": "supply" if supply_id else "staff", "supply_id": supply_id,
                       "over_limit": bool(warnings)})
    activity_log.record("cover.assign", target=f"cover:{c.cover_id}", principal=actor,
                        kind="supply" if supply_id else "staff")
    return get(c.cover_id), warnings


def unassign(cover_id: int, *, actor: Principal) -> Cover:
    _require_editor(actor, "cover.unassign", f"cover:{cover_id}")
    c = get(cover_id)
    if c.status in ("Completed", "Cancelled"):
        raise ValidationError([f"This cover is {c.status.lower()}"])
    with database.connect() as conn:
        conn.execute("UPDATE cover_requests SET cover_name = NULL, cover_username = NULL, "
                     "supply_id = NULL, rate_charged = NULL, status = 'Pending', "
                     "notified_at = NULL, updated_at = datetime('now'), updated_by = ? "
                     "WHERE cover_id = ?", (actor.username, c.cover_id))
        _audit(conn, "unassign", actor, cover_id=c.cover_id)
    activity_log.record("cover.unassign", target=f"cover:{c.cover_id}", principal=actor)
    return get(c.cover_id)


def set_status(cover_id: int, status: str, *, actor: Principal, note: str | None = None
               ) -> Cover:
    """Old 'Set status'. The person covering may confirm or complete their own cover."""
    _require_staff(actor, "cover.status", f"cover:{cover_id}")
    c = get(cover_id)
    status = str(status or "").strip().title()
    problems: list[str] = []
    if status not in STATUSES:
        problems.append(f"Status must be one of {', '.join(STATUSES)}")
    mine = _same(actor.username, c.cover_username)
    if not is_editor(actor) and not (mine and status in ("Confirmed", "Completed")):
        raise PermissionDenied("Only the cover manager can do this (the person covering can "
                               "confirm or complete it).")
    if status in ("Assigned", "Confirmed", "Completed") and not c.cover_name:
        problems.append("Assign someone first")
    if status == "Pending" and c.cover_name:
        problems.append("Unassign the cover instead")
    if status == "Completed" and c.date > _today().isoformat():
        problems.append(f"The lesson isn't until {c.date}")
    if status == "Cancelled" and not (note or "").strip():
        problems.append("Say why the cover isn't needed (e.g. group on a trip)")
    if c.status == "Cancelled" and status != "Cancelled" and c.absence_id:
        a = get_absence(c.absence_id)
        if a.status != "active":
            problems.append("Its absence was cancelled")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        try:
            conn.execute("UPDATE cover_requests SET status = ?, notes = CASE WHEN ? IS NULL "
                         "THEN notes ELSE COALESCE(notes || ' · ', '') || ? END, updated_at = "
                         "datetime('now'), updated_by = ? WHERE cover_id = ?",
                         (status, P._clean_text(note, 300), P._clean_text(note, 300),
                          actor.username, c.cover_id))
        except database.IntegrityError:  # another cover for that lesson exists now
            raise ValidationError([f"{c.group_code} already has cover then"]) from None
        _audit(conn, "status", actor, cover_id=c.cover_id,
               detail={"from": c.status, "to": status})
    activity_log.record("cover.status", target=f"cover:{c.cover_id}", principal=actor,
                        status=status)
    return get(c.cover_id)


def delete(cover_id: int, *, actor: Principal) -> None:
    """Old 'Delete': only cover that never happened (Pending or Cancelled)."""
    _require_editor(actor, "cover.delete", f"cover:{cover_id}")
    c = get(cover_id)
    if c.status not in ("Pending", "Cancelled"):
        raise ValidationError([f"This cover is {c.status.lower()} - cancel it instead"])
    with database.connect() as conn:
        conn.execute("DELETE FROM cover_requests WHERE cover_id = ?", (c.cover_id,))
        _audit(conn, "delete", actor, cover_id=c.cover_id,
               detail={"date": c.date, "period": c.period, "group": c.group_code})
    activity_log.record("cover.delete", target=f"cover:{c.cover_id}", principal=actor)


# ── Telling people ───────────────────────────────────────────────────

def lesson_plan_for(c: Cover):
    """The lesson's plan, if the absent teacher wrote one."""
    if c.group_id is None:
        return None
    from education_system.systems.secondary.modules.curriculum.domain import lesson_plans as LP
    return LP.for_lesson(c.group_id, c.date, c.period)


def details_text(c: Cover) -> str:
    p = next((x for x in TT.periods() if x.period == c.period), None)
    plan = lesson_plan_for(c)
    lines = [f"{_dt.date.fromisoformat(c.date):%A %d %B %Y}, "
             f"{p.label + ' (' + p.times + ')' if p else 'period ' + str(c.period)}",
             f"Class: {c.group_code} ({c.subject_code or ''}, Year {c.year_group or '-'})",
             f"Room: {c.room or '-'}", f"Covering for: {c.absent_name}"]
    if c.work_set:
        lines += ["", "Cover work:", c.work_set]
    if plan:
        lines += ["", f"Lesson plan: {plan.title}"]
        if plan.objectives:
            lines.append(f"Objectives: {plan.objectives}")
        if plan.activities:
            lines.append(f"Activities: {plan.activities}")
    if not c.work_set and not plan:
        lines += ["", "No cover work has been set yet - see the cover manager."]
    return "\n".join(lines)


def notify(cover_id: int, *, actor: Principal) -> int:
    """Queue an e-mail to the person covering. Returns the message id (deliver next)."""
    _require_editor(actor, "cover.notify", f"cover:{cover_id}")
    c = get(cover_id)
    if not c.cover_name:
        raise ValidationError(["Assign someone first"])
    if c.supply_id:
        address = get_supply(c.supply_id).email
    else:
        address = next((t.get("email") for t in TG.teacher_choices()
                        if _same(t["username"], c.cover_username)), None)
    if not address:
        raise ValidationError([f"No e-mail address for {c.cover_name}"])
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    mid = E.send_to_address(address, c.cover_name, f"Cover: {c.group_code} {c.when}",
                            f"Hello {c.cover_name},\n\nPlease cover this lesson:\n\n"
                            + details_text(c) + "\n\nThank you.", actor=actor, kind="cover",
                            label=f"cover:{c.cover_id}")
    with database.connect() as conn:
        conn.execute("UPDATE cover_requests SET notified_at = datetime('now') WHERE "
                     "cover_id = ?", (c.cover_id,))
        _audit(conn, "notify", actor, cover_id=c.cover_id)
    return mid


def cover_sheet(day: Any) -> str:
    """The day's cover, for the staffroom."""
    rows = [c for c in list_covers(date=day) if c.status != "Cancelled"]
    problems: list[str] = []
    d = _date(day, "Date", problems)
    if d is None:
        raise ValidationError(problems)
    out = [f"Cover - {d:%A %d %B %Y}", ""]
    if not rows:
        out.append("No cover today.")
    for c in rows:
        out.append(f"P{c.period:<3}{c.group_code:<12}{(c.subject_code or ''):<7}"
                   f"{(c.room or ''):<7}{c.absent_name[:20]:<21}-> "
                   f"{c.cover_name or 'UNASSIGNED'}")
    return "\n".join(out) + "\n"


def my_cover(actor: Principal, start: Any = None) -> list[Cover]:
    """Cover the signed-in person is doing from *start* (default today)."""
    return [c for c in list_covers(date_from=start or _today(), include_cancelled=False)
            if _same(c.cover_username, actor.username)]
