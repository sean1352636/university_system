"""School calendar events: assemblies, trips, exams, parents' evenings, fixtures…

Rules shared by the GUI and CLI:

* All staff can read the calendar and add events. The person who added an
  event can change, cancel or delete it; :data:`access.CALENDAR_EDITORS` can
  do so for any event.
* An event has a date range, and times unless it is all day (end after start
  on a one-day event). Capacity and cost can't be negative.
* Status: Draft / Scheduled / Postponed / Cancelled / Completed. Cancelling
  needs a reason; an event can only be marked Completed once it has started.
* An event on a weekend, in a school holiday or on a closure day is allowed
  (trips, open days) but :func:`warnings_for` says so, so screens can ask.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, fields
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import CALENDAR_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

EVENT_TYPES: tuple[str, ...] = (
    "Assembly", "Tutor Time", "Meeting", "Trip", "Exam", "Mock Exam", "Deadline",
    "Parents' Evening", "Open Day", "Sports Fixture", "Social", "INSET", "Holiday",
    "Training", "Assembly Practice", "Other",
)
AUDIENCES: tuple[str, ...] = (
    "All", "Staff", "Pupils", *(f"Year {y}" for y in P.YEAR_GROUPS), "Parents", "External",
)
STATUSES: tuple[str, ...] = ("Scheduled", "Draft", "Postponed", "Cancelled", "Completed")
EDITABLE_FIELDS: tuple[str, ...] = (
    "title", "event_type", "description", "start_date", "end_date", "start_time", "end_time",
    "all_day", "location", "organiser", "audience", "status", "capacity", "rsvp_required",
    "cost", "notes",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    description   TEXT,
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    start_time    TEXT,
    end_time      TEXT,
    all_day       INTEGER NOT NULL DEFAULT 0 CHECK (all_day IN (0, 1)),
    location      TEXT,
    organiser     TEXT,
    audience      TEXT NOT NULL DEFAULT 'All',
    status        TEXT NOT NULL DEFAULT 'Scheduled'
                  CHECK (status IN ('Scheduled', 'Draft', 'Postponed', 'Cancelled', 'Completed')),
    status_reason TEXT,
    capacity      INTEGER CHECK (capacity IS NULL OR capacity >= 0),
    rsvp_required INTEGER NOT NULL DEFAULT 0 CHECK (rsvp_required IN (0, 1)),
    cost          REAL CHECK (cost IS NULL OR cost >= 0),
    notes         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    created_by    TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by    TEXT
);
CREATE INDEX IF NOT EXISTS ix_calendar_events_dates ON calendar_events (start_date, end_date);
"""

database.register_schema("calendar_events", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class Event:
    event_id: int
    title: str
    event_type: str
    description: str | None
    start_date: str
    end_date: str
    start_time: str | None
    end_time: str | None
    all_day: int
    location: str | None
    organiser: str | None
    audience: str
    status: str
    status_reason: str | None
    capacity: int | None
    rsvp_required: int
    cost: float | None
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def when(self) -> str:
        days = self.start_date if self.start_date == self.end_date else \
            f"{self.start_date} to {self.end_date}"
        if self.all_day:
            return f"{days} (all day)"
        return f"{days} {self.start_time or ''}-{self.end_time or ''}".rstrip("-")


def _row(r) -> Event:
    return Event(**{f.name: r[f.name] for f in fields(Event)})


_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _time(value: Any, label: str, problems: list[str]) -> str | None:
    text = P._clean_text(value, 5)
    if not text:
        return None
    m = _TIME_RE.match(text)
    if not m:
        problems.append(f"{label} must be a time like 09:30")
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {"title": P._clean_text(data.get("title"), 120)}
    if not out["title"]:
        problems.append("Title is required")
    out["event_type"] = P._clean_text(data.get("event_type"), 30) or "Other"
    if out["event_type"] not in EVENT_TYPES:
        problems.append("Type must be one of: " + ", ".join(EVENT_TYPES))
    out["audience"] = P._clean_text(data.get("audience"), 20) or "All"
    if out["audience"] not in AUDIENCES:
        problems.append("Audience must be one of: " + ", ".join(AUDIENCES))
    out["status"] = P._clean_text(data.get("status"), 20) or "Scheduled"
    if out["status"] not in STATUSES:
        problems.append("Status must be one of: " + ", ".join(STATUSES))
    start = P._parse_date(data.get("start_date"), "Start date", problems)
    if start is None and not any(p.startswith("Start date") for p in problems):
        problems.append("Start date is required")
    end = P._parse_date(data.get("end_date"), "End date", problems) or start
    if start and end and end < start:
        problems.append("The end date can't be before the start date")
    out["start_date"], out["end_date"] = start, end
    out["all_day"] = int(P._as_bool(data.get("all_day"), "All day", problems))
    st = _time(data.get("start_time"), "Start time", problems)
    et = _time(data.get("end_time"), "End time", problems)
    if out["all_day"]:
        st = et = None
    elif not st and not any(p.startswith("Start time") for p in problems):
        problems.append("Give a start time, or tick All day")
    if st and et and start == end and et <= st:
        problems.append("The end time must be after the start time")
    out["start_time"], out["end_time"] = st, et
    for key, limit in (("description", 2000), ("location", 120), ("organiser", 120),
                       ("notes", 2000)):
        out[key] = P._clean_text(data.get(key), limit)
    raw = data.get("capacity")
    out["capacity"] = None
    if raw not in (None, ""):
        try:
            out["capacity"] = int(str(raw).strip())
            if out["capacity"] < 0:
                raise ValueError
        except ValueError:
            problems.append("Capacity must be a whole number, 0 or more")
    raw = data.get("cost")
    out["cost"] = None
    if raw not in (None, ""):
        try:
            out["cost"] = round(float(str(raw).replace("£", "").strip()), 2)
            if out["cost"] < 0:
                raise ValueError
        except ValueError:
            problems.append("Cost must be an amount, 0 or more")
    out["rsvp_required"] = int(P._as_bool(data.get("rsvp_required"), "RSVP required",
                                          problems))
    if problems:
        raise ValidationError(problems)
    return out


def warnings_for(start_date: str, end_date: str | None = None) -> list[str]:
    """Notes about holding an event on these days (not errors)."""
    out = []
    try:
        start = _dt.date.fromisoformat(start_date)
        end = _dt.date.fromisoformat(end_date or start_date)
    except ValueError:
        return out
    if (end - start).days > 31:
        return out
    d = start
    while d <= end:
        info = AY.day_info(d)
        if info.year is not None and not info.is_school_day:
            out.append(f"{d:%a %d %b %Y}: {info.label}")
        d += _dt.timedelta(days=1)
    return out


def _can_change(actor: Principal, ev: Event | None) -> bool:
    if actor.role in CALENDAR_EDITORS:
        return True
    return actor.is_staff and (ev is None or ev.created_by == actor.username)


def _require(actor: Principal, ev: Event | None, action: str) -> None:
    if not _can_change(actor, ev):
        activity_log.record(action, target=f"event:{ev.event_id}" if ev else None,
                            outcome="denied", principal=actor)
        raise PermissionDenied("You can change events you added; ask an administrator "
                               "to change this one." if ev else
                               "Only school staff can add events.")


def can_change(actor: Principal, ev: Event) -> bool:
    return _can_change(actor, ev)


# ── Read ─────────────────────────────────────────────────────────────

def get_event(event_id: int) -> Event | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM calendar_events WHERE event_id = ?",
                         (int(event_id),)).fetchone()
    return _row(r) if r else None


def list_events(*, start: str | None = None, end: str | None = None,
                event_type: str | None = None, audience: str | None = None,
                status: str | None = None, search: str | None = None,
                include_cancelled: bool = True) -> list[Event]:
    """Events overlapping [start, end], soonest first."""
    where, params = [], []
    if start:
        where.append("end_date >= ?")
        params.append(start)
    if end:
        where.append("start_date <= ?")
        params.append(end)
    if event_type:
        where.append("event_type = ?")
        params.append(event_type)
    if audience:
        where.append("audience = ?")
        params.append(audience)
    if status:
        where.append("status = ?")
        params.append(status)
    elif not include_cancelled:
        where.append("status != 'Cancelled'")
    if search and search.strip():
        where.append("(lower(title) LIKE ? OR lower(coalesce(location, '')) LIKE ?)")
        params += [f"%{search.strip().lower()}%"] * 2
    sql = "SELECT * FROM calendar_events" + (" WHERE " + " AND ".join(where) if where else "")
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY start_date, coalesce(start_time, ''), event_id",
                            params).fetchall()
    return [_row(r) for r in rows]


def events_on(day: _dt.date) -> list[Event]:
    iso = day.isoformat()
    return list_events(start=iso, end=iso)


def counts_by_day(start: _dt.date, end: _dt.date) -> dict[_dt.date, int]:
    """Live (not cancelled) events per day, for the month grid."""
    out: dict[_dt.date, int] = {}
    for ev in list_events(start=start.isoformat(), end=end.isoformat(),
                          include_cancelled=False):
        d = max(start, _dt.date.fromisoformat(ev.start_date))
        last = min(end, _dt.date.fromisoformat(ev.end_date))
        while d <= last:
            out[d] = out.get(d, 0) + 1
            d += _dt.timedelta(days=1)
    return out


@dataclass(frozen=True)
class Summary:
    total: int
    upcoming: list[Event]
    by_type: dict[str, int]
    by_status: dict[str, int]


def summary(*, days: int = 14, today: _dt.date | None = None) -> Summary:
    today = today or _dt.date.today()
    all_events = list_events()
    upcoming = list_events(start=today.isoformat(),
                           end=(today + _dt.timedelta(days=days)).isoformat(),
                           include_cancelled=False)
    by_type: dict[str, int] = {}
    by_status = {s: 0 for s in STATUSES}
    for ev in all_events:
        by_type[ev.event_type] = by_type.get(ev.event_type, 0) + 1
        by_status[ev.status] = by_status.get(ev.status, 0) + 1
    return Summary(len(all_events), upcoming, dict(sorted(by_type.items())), by_status)


# ── Write ────────────────────────────────────────────────────────────

def create_event(data: dict[str, Any], *, actor: Principal) -> Event:
    _require(actor, None, "calendar.event.create")
    try:
        clean = _validate(data)
        if clean["status"] in {"Cancelled", "Completed"}:
            raise ValidationError(["A new event can't start out cancelled or completed"])
    except ValidationError as e:
        activity_log.record("calendar.event.create", outcome="invalid", principal=actor,
                            problems=len(e.problems))
        raise
    cols = list(clean)
    with database.connect() as conn:
        e_id = conn.execute(
            f"INSERT INTO calendar_events ({', '.join(cols)}, created_by, updated_by) "
            f"VALUES ({', '.join('?' for _ in cols)}, ?, ?)",
            [*clean.values(), actor.username, actor.username]).lastrowid
    activity_log.record("calendar.event.create", target=f"event:{e_id}", principal=actor,
                        type=clean["event_type"])
    return get_event(e_id)  # type: ignore[return-value]


def _get_or_raise(event_id: int, action: str, actor: Principal) -> Event:
    ev = get_event(event_id)
    if ev is None:
        activity_log.record(action, target=f"event:{event_id}", outcome="not_found",
                            principal=actor)
        raise NotFound(f"No event {event_id}")
    return ev


def update_event(event_id: int, changes: dict[str, Any], *, actor: Principal) -> Event:
    """Change fields (status changes go through :func:`set_status`)."""
    ev = _get_or_raise(event_id, "calendar.event.update", actor)
    _require(actor, ev, "calendar.event.update")
    merged = {k: getattr(ev, k) for k in EDITABLE_FIELDS}
    merged.update(changes)
    try:
        if merged["status"] != ev.status:
            raise ValidationError(["Use Status / Cancel / Complete to change the status"])
        clean = _validate(merged)
    except ValidationError as e:
        activity_log.record("calendar.event.update", target=f"event:{event_id}",
                            outcome="invalid", principal=actor, problems=len(e.problems))
        raise
    changed = [k for k, v in clean.items() if getattr(ev, k) != v]
    if changed:
        with database.connect() as conn:
            conn.execute(f"UPDATE calendar_events SET {', '.join(f'{k} = ?' for k in changed)}, "
                         "updated_at = datetime('now'), updated_by = ? WHERE event_id = ?",
                         [clean[k] for k in changed] + [actor.username, event_id])
    activity_log.record("calendar.event.update", target=f"event:{event_id}", principal=actor,
                        outcome="ok" if changed else "no_change", fields=changed or None)
    return get_event(event_id)  # type: ignore[return-value]


def set_status(event_id: int, status: str, *, actor: Principal, reason: str | None = None,
               today: _dt.date | None = None) -> Event:
    today = today or _dt.date.today()
    ev = _get_or_raise(event_id, "calendar.event.status", actor)
    _require(actor, ev, "calendar.event.status")
    reason = P._clean_text(reason, 300)
    problems = []
    if status not in STATUSES:
        problems.append("Status must be one of: " + ", ".join(STATUSES))
    elif status == ev.status:
        problems.append(f"Already {status.lower()}")
    elif status == "Cancelled" and not reason:
        problems.append("Say why the event is cancelled")
    elif status == "Completed" and ev.start_date > today.isoformat():
        problems.append("An event can't be completed before it has started")
    if problems:
        activity_log.record("calendar.event.status", target=f"event:{event_id}",
                            outcome="invalid", principal=actor, problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE calendar_events SET status = ?, status_reason = ?, updated_at = "
                     "datetime('now'), updated_by = ? WHERE event_id = ?",
                     (status, reason, actor.username, event_id))
    activity_log.record("calendar.event.status", target=f"event:{event_id}", principal=actor,
                        status=status)
    return get_event(event_id)  # type: ignore[return-value]


def cancel_event(event_id: int, *, actor: Principal, reason: str) -> Event:
    return set_status(event_id, "Cancelled", actor=actor, reason=reason)


def complete_event(event_id: int, *, actor: Principal,
                   today: _dt.date | None = None) -> Event:
    return set_status(event_id, "Completed", actor=actor, today=today)


def delete_event(event_id: int, *, actor: Principal) -> Event:
    """Remove an event added in error (to call one off, cancel it instead so
    the calendar still shows it was called off)."""
    ev = _get_or_raise(event_id, "calendar.event.delete", actor)
    _require(actor, ev, "calendar.event.delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM calendar_events WHERE event_id = ?", (event_id,))
    activity_log.record("calendar.event.delete", target=f"event:{event_id}", principal=actor)
    return ev
