"""Parents' evenings: events, teachers, appointments, schedules and follow-up.

Kept from the old Parents' Evenings:

* Events with name, date, year group, location, start and end times, slot
  length, status (Scheduled, Open for Booking, Closed for Booking, In
  Progress, Completed, Cancelled) and notes; slots run from the start at the
  slot length and must line up with it.
* Bookings: which pupil's family meets which teacher at which slot, with
  status (Booked, Attended, No-Show, Cancelled), parent name and notes. A
  teacher can't have two bookings in one slot.
* Teacher and pupil schedules (free slots shown), the event summary and the
  overall summary.

New:

* **Teachers from teaching groups.** The teachers taking part are the
  teachers of the event's year group's teaching groups this school year
  (:mod:`modules.curriculum.domain.teaching_groups`, read only), kept in step by
  :func:`sync_teachers`. A pupil is booked with the teachers who teach them.
  Teachers keep their own room, breaks, availability and notes.
* **Break slots** for the whole evening, **in-person / online** (with a
  meeting link) and a **booking window** for families.
* **No double booking** of a teacher, a pupil or a family: parents of two
  children can't be in two places at once (siblings share a contact e-mail,
  phone or portal login), and a pupil sees each teacher once.
* **Who.** :data:`PARENTS_EVENING_EDITORS` set up evenings and book anyone;
  teachers book, mark and write notes for their own appointments. Families
  book through the portal with :func:`book_for_family` (the login must be
  linked to the pupil as a parent).
* **Attendance** (attended / missed) and teacher notes per appointment.
* **E-mail** (prepared in the school outbox): invitations to the year
  group's families and each family's appointment list (siblings together).
* **Reports**: booking rates by teacher and by form; CSV / text schedules.

Every change is in ``parents_evening_audit`` and the activity log (ids only).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    PARENTS_EVENING_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import year_of
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

EVENT_STATUSES: tuple[str, ...] = (
    "Scheduled", "Open for Booking", "Closed for Booking", "In Progress", "Completed",
    "Cancelled")
DEFAULT_EVENT_STATUS = "Scheduled"
OPEN_EVENT_STATUSES: tuple[str, ...] = (
    "Scheduled", "Open for Booking", "Closed for Booking", "In Progress")
BOOKING_STATUSES: tuple[str, ...] = ("Booked", "Attended", "No-Show", "Cancelled")
DEFAULT_BOOKING_STATUS = "Booked"
MISSED = "No-Show"
MODES: tuple[str, ...] = ("In person", "Online", "In person or online")
DEFAULT_MODE = "In person"
YEAR_CHOICES: tuple[str, ...] = ("All years", *(str(y) for y in P.YEAR_GROUPS))
MIN_SLOT, MAX_SLOT = 3, 60
TEMPLATE_INVITE = "parents_evening_invitation"
TEMPLATE_SCHEDULE = "parents_evening_schedule"

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS parents_evening_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    event_date          TEXT NOT NULL,
    academic_year       TEXT NOT NULL,
    year_group          INTEGER CHECK (year_group IS NULL OR year_group BETWEEN 7 AND 11),
    location            TEXT,
    mode                TEXT NOT NULL DEFAULT 'In person',
    meeting_link        TEXT,
    start_time          TEXT NOT NULL,
    end_time            TEXT NOT NULL,
    slot_minutes        INTEGER NOT NULL DEFAULT 10 CHECK (slot_minutes BETWEEN 3 AND 60),
    break_slots         TEXT,
    booking_opens       TEXT,
    booking_closes      TEXT,
    status              TEXT NOT NULL DEFAULT 'Scheduled',
    notes               TEXT,
    invitations_sent_at TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_pe_events_date ON parents_evening_events (event_date);
CREATE TABLE IF NOT EXISTS parents_evening_teachers (
    event_id      INTEGER NOT NULL REFERENCES parents_evening_events (event_id) ON DELETE CASCADE,
    teacher_key   TEXT NOT NULL,
    teacher_name  TEXT NOT NULL,
    teacher_email TEXT,
    groups        TEXT,
    room          TEXT,
    breaks        TEXT,
    available     INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
    source        TEXT NOT NULL DEFAULT 'groups' CHECK (source IN ('groups', 'added')),
    notes         TEXT,
    PRIMARY KEY (event_id, teacher_key)
);
CREATE TABLE IF NOT EXISTS parents_evening_bookings (
    booking_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id         INTEGER NOT NULL REFERENCES parents_evening_events (event_id)
                     ON DELETE CASCADE,
    pupil_id         INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    teacher_key      TEXT NOT NULL,
    teacher_name     TEXT NOT NULL,
    slot_time        TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Booked'
                     CHECK (status IN ('Booked', 'Attended', 'No-Show', 'Cancelled')),
    parent_name      TEXT,
    notes            TEXT,
    teacher_notes    TEXT,
    booked_via       TEXT NOT NULL DEFAULT 'staff' CHECK (booked_via IN ('staff', 'portal')),
    booked_by        TEXT,
    schedule_sent_at TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_pe_bookings_event ON parents_evening_bookings (event_id, slot_time);
CREATE INDEX IF NOT EXISTS ix_pe_bookings_pupil ON parents_evening_bookings (pupil_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_pe_bookings_teacher_slot
    ON parents_evening_bookings (event_id, teacher_key, slot_time) WHERE status != 'Cancelled';
CREATE UNIQUE INDEX IF NOT EXISTS ux_pe_bookings_pupil_slot
    ON parents_evening_bookings (event_id, pupil_id, slot_time) WHERE status != 'Cancelled';
CREATE UNIQUE INDEX IF NOT EXISTS ux_pe_bookings_pupil_teacher
    ON parents_evening_bookings (event_id, pupil_id, teacher_key) WHERE status != 'Cancelled';
CREATE TABLE IF NOT EXISTS parents_evening_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   INTEGER,
    booking_id INTEGER,
    pupil_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("parents_evenings", _SCHEMA)


@dataclass(frozen=True)
class Event:
    event_id: int
    name: str
    event_date: str
    academic_year: str
    year_group: int | None
    location: str | None
    mode: str
    meeting_link: str | None
    start_time: str
    end_time: str
    slot_minutes: int
    break_slots: str | None
    booking_opens: str | None
    booking_closes: str | None
    status: str
    notes: str | None
    invitations_sent_at: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str

    @property
    def year_label(self) -> str:
        return f"Year {self.year_group}" if self.year_group else "All years"

    @property
    def times(self) -> str:
        return f"{self.start_time}-{self.end_time}"

    @property
    def breaks(self) -> list[str]:
        return [b for b in (self.break_slots or "").split(",") if b]

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_EVENT_STATUSES

    @property
    def venue(self) -> str:
        if self.mode == "Online":
            return "Online" + (f" ({self.meeting_link})" if self.meeting_link else "")
        where = self.location or "school"
        if self.mode == "In person or online":
            return f"{where} or online" + (f" ({self.meeting_link})" if self.meeting_link
                                           else "")
        return where


@dataclass(frozen=True)
class Teacher:
    event_id: int
    teacher_key: str
    teacher_name: str
    teacher_email: str | None
    groups: str | None
    room: str | None
    breaks: str | None
    available: bool
    source: str
    notes: str | None

    @property
    def break_list(self) -> list[str]:
        return [b for b in (self.breaks or "").split(",") if b]


@dataclass(frozen=True)
class Booking:
    booking_id: int
    event_id: int
    pupil_id: int
    teacher_key: str
    teacher_name: str
    slot_time: str
    status: str
    parent_name: str | None
    notes: str | None
    teacher_notes: str | None
    booked_via: str
    booked_by: str | None
    schedule_sent_at: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None

    @property
    def active(self) -> bool:
        return self.status != "Cancelled"


def _event_row(r) -> Event:
    return Event(**{k: r[k] for k in Event.__dataclass_fields__})


def _teacher_row(r) -> Teacher:
    v = {k: r[k] for k in Teacher.__dataclass_fields__}
    v["available"] = bool(v["available"])
    return Teacher(**v)


_BOOK_SELECT = ("SELECT b.*, p.legal_last_name, p.legal_first_name, p.preferred_name, "
                "p.admission_no, p.year_group AS pupil_year, p.form_group "
                "FROM parents_evening_bookings b JOIN pupils p USING (pupil_id)")
_BOOK_BASE = tuple(f for f in Booking.__dataclass_fields__
                   if f not in ("pupil_name", "admission_no", "pupil_year", "form_group"))


def _booking_row(r) -> Booking:
    return Booking(**{k: r[k] for k in _BOOK_BASE},
                   pupil_name=f"{r['legal_last_name']}, "
                              f"{r['preferred_name'] or r['legal_first_name']}",
                   admission_no=r["admission_no"], pupil_year=r["pupil_year"],
                   form_group=r["form_group"])


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in PARENTS_EVENING_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"parents_evenings.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can manage parents' evenings.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the parents' evening organisers can do that.")


def teacher_key_for(actor: Principal) -> str:
    return (actor.username or "").strip().lower()


def is_teacher(actor: Principal, teacher_key: str) -> bool:
    return bool(actor.username) and actor.role in STAFF_ROLES and \
        teacher_key == teacher_key_for(actor)


def can_manage(actor: Principal, teacher_key: str) -> bool:
    """Book, mark and note a teacher's appointments: the organisers, or the
    teacher themselves."""
    return is_editor(actor) or is_teacher(actor, teacher_key)


def _audit(conn, action: str, actor: Principal | str, *, event_id: int | None = None,
           booking_id: int | None = None, pupil_id: int | None = None, **detail: Any) -> None:
    who = actor if isinstance(actor, str) else (actor.username or "unknown")
    conn.execute("INSERT INTO parents_evening_audit (event_id, booking_id, pupil_id, action, "
                 "detail, actor) VALUES (?, ?, ?, ?, ?, ?)",
                 (event_id, booking_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None, who))


def history(event_id: int | None = None, *, booking_id: int | None = None,
            pupil_id: int | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM parents_evening_audit", [], []
    for col, val in (("event_id", event_id), ("booking_id", booking_id),
                     ("pupil_id", pupil_id)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(int(val))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "event_id": r["event_id"], "booking_id": r["booking_id"],
                 "pupil_id": r["pupil_id"], "action": r["action"], "actor": r["actor"],
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


def _time(value: Any, label: str, problems: list[str]) -> str | None:
    v = str(value or "").strip()
    if not v:
        return None
    m = _TIME_RE.match(v)
    if not m:
        problems.append(f"{label} must be a time (HH:MM)")
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _mins(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _hhmm(n: int) -> str:
    return f"{n // 60:02d}:{n % 60:02d}"


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


def _year(value: Any, problems: list[str]) -> int | None:
    v = str(value if value is not None else "").strip().lower().replace("year", "").strip()
    if v in ("", "all", "all years", "both", "none"):
        return None
    try:
        n = int(v)
    except ValueError:
        n = 0
    if n not in P.YEAR_GROUPS:
        problems.append("Year group must be 7 to 11 (or All years)")
        return None
    return n


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


def slots_between(start: str, end: str, minutes: int) -> list[str]:
    """Slot start times from *start* while a whole slot fits before *end*."""
    out, t, stop = [], _mins(start), _mins(end)
    while t + minutes <= stop:
        out.append(_hhmm(t))
        t += minutes
    return out


def _breaks(value: Any, slots: list[str], label: str, problems: list[str]) -> str | None:
    raw = [x for x in re.split(r"[,;\s]+", str(value or "")) if x]
    out = []
    for x in raw:
        t = _time(x, label, problems)
        if t is None:
            continue
        if t not in slots:
            problems.append(f"{label}: {t} isn't one of the slots")
        elif t not in out:
            out.append(t)
    return ",".join(sorted(out)) or None


EVENT_FIELDS = ("name", "event_date", "year_group", "location", "mode", "meeting_link",
                "start_time", "end_time", "slot_minutes", "break_slots", "booking_opens",
                "booking_closes", "status", "notes")


def _clean_event(data: dict[str, Any], current: Event | None
                 ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in EVENT_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in EVENT_FIELDS})
    out: dict[str, Any] = {}
    out["name"] = " ".join(str(merged.get("name") or "").split())[:120]
    if not out["name"]:
        problems.append("Name is required")
    out["event_date"] = _date(merged.get("event_date"), "Date", problems)
    if out["event_date"] is None and not any(p.startswith("Date") for p in problems):
        problems.append("Date is required")
    out["year_group"] = _year(merged.get("year_group"), problems)
    out["location"] = _text(merged.get("location"), 120)
    out["mode"] = _choice(merged.get("mode"), MODES, "Mode", problems, DEFAULT_MODE)
    out["meeting_link"] = _text(merged.get("meeting_link"), 300)
    out["start_time"] = _time(merged.get("start_time"), "Start time", problems)
    out["end_time"] = _time(merged.get("end_time"), "End time", problems)
    for k, label in (("start_time", "Start time"), ("end_time", "End time")):
        if out[k] is None and not any(p.startswith(label) for p in problems):
            problems.append(f"{label} is required")
    try:
        out["slot_minutes"] = int(str(merged.get("slot_minutes") or 10).strip())
    except ValueError:
        out["slot_minutes"] = 0
    if not MIN_SLOT <= out["slot_minutes"] <= MAX_SLOT:
        problems.append(f"Slot length must be {MIN_SLOT} to {MAX_SLOT} minutes")
    slots: list[str] = []
    if out["start_time"] and out["end_time"]:
        if out["end_time"] <= out["start_time"]:
            problems.append("End time must be after the start time")
        elif MIN_SLOT <= out["slot_minutes"] <= MAX_SLOT:
            slots = slots_between(out["start_time"], out["end_time"], out["slot_minutes"])
            if not slots:
                problems.append("No slot fits between the start and end times")
    out["break_slots"] = _breaks(merged.get("break_slots"), slots, "Break slots", problems) \
        if slots else None
    out["booking_opens"] = _date(merged.get("booking_opens"), "Booking opens", problems)
    out["booking_closes"] = _date(merged.get("booking_closes"), "Booking closes", problems)
    if out["booking_opens"] and out["booking_closes"] and \
            out["booking_closes"] < out["booking_opens"]:
        problems.append("Booking can't close before it opens")
    if out["booking_closes"] and out["event_date"] and out["booking_closes"] > out["event_date"]:
        problems.append("Booking must close by the day of the evening")
    if out["mode"] != "In person" and not out["meeting_link"]:
        problems.append("Give the meeting link for online appointments")
    if out["mode"] != "Online" and not out["location"]:
        problems.append("Location is required for in-person appointments")
    out["status"] = _choice(merged.get("status"), EVENT_STATUSES, "Status", problems,
                            DEFAULT_EVENT_STATUS)
    out["notes"] = _text(merged.get("notes"), 2000)
    return out, problems


# ── Events ───────────────────────────────────────────────────────────

def get_event(event_id: int) -> Event:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM parents_evening_events WHERE event_id = ?",
                         (int(event_id),)).fetchone()
    if r is None:
        raise NotFound(f"No parents' evening #{event_id}")
    return _event_row(r)


def find_event(event_id: int) -> Event | None:
    try:
        return get_event(event_id)
    except NotFound:
        return None


def list_events(*, year_group: int | str | None = None, status: str | None = None,
                open_only: bool = False, upcoming: bool = False,
                date_from: str | None = None, date_to: str | None = None) -> list[Event]:
    """Events, soonest first (the old filters: year, status, open only)."""
    where, params = [], []
    if year_group not in (None, ""):
        problems: list[str] = []
        y = _year(year_group, problems)
        where.append("year_group IS NULL" if y is None else "(year_group = ? OR year_group "
                                                            "IS NULL)")
        if y is not None:
            params.append(y)
    if status:
        where.append("status = ?")
        params.append(status)
    if open_only:
        where.append(f"status IN ({', '.join('?' * len(OPEN_EVENT_STATUSES))})")
        params += list(OPEN_EVENT_STATUSES)
    if upcoming:
        where.append("event_date >= ? AND status != 'Cancelled'")
        params.append(_today().isoformat())
    if date_from:
        where.append("event_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("event_date <= ?")
        params.append(date_to)
    sql = "SELECT * FROM parents_evening_events" + (
        " WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY event_date, start_time, event_id"
    with database.connect() as conn:
        return [_event_row(r) for r in conn.execute(sql, params)]


def event_slots(event: Event | int, *, include_breaks: bool = False) -> list[str]:
    """The evening's slot times (breaks left out unless *include_breaks*)."""
    e = event if isinstance(event, Event) else get_event(event)
    slots = slots_between(e.start_time, e.end_time, e.slot_minutes)
    return slots if include_breaks else [s for s in slots if s not in e.breaks]


def create_event(data: dict[str, Any], *, actor: Principal) -> Event:
    """The old New event; the teachers are filled in from teaching groups."""
    _require_editor(actor, "create")
    c, problems = _clean_event(data, None)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        eid = conn.execute(
            f"INSERT INTO parents_evening_events ({', '.join(EVENT_FIELDS)}, academic_year, "
            f"created_by, updated_by) VALUES ({', '.join('?' * len(EVENT_FIELDS))}, ?, ?, ?)",
            (*(c[k] for k in EVENT_FIELDS), year_of(c["event_date"]), actor.username,
             actor.username)).lastrowid
        _audit(conn, "create", actor, event_id=eid, year=c["year_group"])
    activity_log.record("parents_evenings.create", target=f"event:{eid}", principal=actor)
    sync_teachers(eid, actor=actor)
    return get_event(eid)


def update_event(event_id: int, changes: dict[str, Any], *, actor: Principal) -> Event:
    """The old Edit event. Slots with bookings can't be taken away."""
    cur = get_event(event_id)
    _require_editor(actor, "update", f"event:{cur.event_id}")
    c, problems = _clean_event(changes, cur)
    changed = [k for k in EVENT_FIELDS if c[k] != getattr(cur, k)]
    if not problems and any(k in changed for k in ("start_time", "end_time", "slot_minutes",
                                                   "break_slots")):
        slots = set(slots_between(c["start_time"], c["end_time"], c["slot_minutes"])) - \
            set((c["break_slots"] or "").split(","))
        lost = [b for b in list_bookings(event_id=cur.event_id) if b.active and
                b.slot_time not in slots]
        if lost:
            problems.append(f"{len(lost)} booking(s) would fall outside the new slots (e.g. "
                            f"{lost[0].slot_time} {lost[0].teacher_name}) - move or cancel "
                            "them first")
    if problems:
        raise ValidationError(problems)
    if not changed:
        return cur
    with database.connect() as conn:
        conn.execute("UPDATE parents_evening_events SET "
                     + ", ".join(f"{k} = ?" for k in changed)
                     + ", academic_year = ?, updated_by = ?, updated_at = datetime('now') "
                       "WHERE event_id = ?",
                     (*(c[k] for k in changed), year_of(c["event_date"]), actor.username,
                      cur.event_id))
        _audit(conn, "update", actor, event_id=cur.event_id, fields=changed)
    activity_log.record("parents_evenings.update", target=f"event:{cur.event_id}",
                        principal=actor, fields=",".join(changed))
    if "year_group" in changed or "event_date" in changed:
        sync_teachers(cur.event_id, actor=actor)
    return get_event(cur.event_id)


def set_event_status(event_id: int, status: str, *, actor: Principal) -> Event:
    """The old Status."""
    return update_event(event_id, {"status": status}, actor=actor)


def delete_event(event_id: int, *, actor: Principal) -> bool:
    """The old Delete (its bookings go with it). An evening with attendance
    recorded is kept - cancel it instead."""
    e = get_event(event_id)
    _require_editor(actor, "delete", f"event:{e.event_id}")
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM parents_evening_bookings WHERE event_id = ? "
                         "AND status IN ('Attended', 'No-Show')", (e.event_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"{n} appointment(s) have attendance recorded - keep the "
                                   "evening (set it to Completed or Cancelled)"])
        conn.execute("DELETE FROM parents_evening_events WHERE event_id = ?", (e.event_id,))
        _audit(conn, "delete", actor, event_id=e.event_id)
    activity_log.record("parents_evenings.delete", target=f"event:{e.event_id}",
                        principal=actor)
    return True


# ── Teachers ─────────────────────────────────────────────────────────

def _key(username: str | None, name: str | None) -> str | None:
    if username and username.strip():
        return username.strip().lower()
    if name and name.strip():
        return "name:" + " ".join(name.split()).lower()
    return None


def derived_teachers(event: Event | int) -> dict[str, dict[str, Any]]:
    """Teachers of the event's year group's teaching groups this school year
    (key -> name, e-mail, group codes)."""
    e = event if isinstance(event, Event) else get_event(event)
    out: dict[str, dict[str, Any]] = {}
    for g in TG.list_groups(academic_year=e.academic_year, year_group=e.year_group):
        k = _key(g.teacher_username, g.teacher_name)
        if k is None:
            continue
        t = out.setdefault(k, {"name": g.teacher_name or g.teacher_username,
                               "email": g.teacher_email, "groups": []})
        t["groups"].append(g.code)
    return out


def sync_teachers(event_id: int, *, actor: Principal) -> dict[str, int]:
    """Bring the teacher list into step with the teaching groups: new
    teachers added, group lists refreshed, teachers who no longer teach the
    year (and have no bookings) taken off. Hand-added teachers are kept."""
    e = get_event(event_id)
    _require_editor(actor, "sync", f"event:{e.event_id}")
    found = derived_teachers(e)
    added = removed = 0
    with database.connect() as conn:
        have = {r["teacher_key"]: r for r in conn.execute(
            "SELECT * FROM parents_evening_teachers WHERE event_id = ?", (e.event_id,))}
        booked = {r[0] for r in conn.execute(
            "SELECT DISTINCT teacher_key FROM parents_evening_bookings WHERE event_id = ? "
            "AND status != 'Cancelled'", (e.event_id,))}
        for k, t in found.items():
            groups = ", ".join(sorted(t["groups"]))
            if k in have:
                conn.execute("UPDATE parents_evening_teachers SET groups = ?, teacher_name = ?, "
                             "teacher_email = COALESCE(?, teacher_email) WHERE event_id = ? "
                             "AND teacher_key = ?", (groups, t["name"], t["email"], e.event_id,
                                                     k))
            else:
                conn.execute("INSERT INTO parents_evening_teachers (event_id, teacher_key, "
                             "teacher_name, teacher_email, groups) VALUES (?, ?, ?, ?, ?)",
                             (e.event_id, k, t["name"], t["email"], groups))
                added += 1
        for k, r in have.items():
            if k not in found and r["source"] == "groups" and k not in booked:
                conn.execute("DELETE FROM parents_evening_teachers WHERE event_id = ? AND "
                             "teacher_key = ?", (e.event_id, k))
                removed += 1
        _audit(conn, "sync", actor, event_id=e.event_id, added=added, removed=removed)
    activity_log.record("parents_evenings.sync", target=f"event:{e.event_id}", principal=actor,
                        added=added, removed=removed)
    return {"added": added, "removed": removed, "teachers": len(list_teachers(e.event_id))}


def list_teachers(event_id: int, *, available_only: bool = False) -> list[Teacher]:
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM parents_evening_teachers WHERE event_id = ?"
            + (" AND available = 1" if available_only else "")
            + " ORDER BY teacher_name COLLATE NOCASE", (int(event_id),)).fetchall()
    return [_teacher_row(r) for r in rows]


def get_teacher(event_id: int, teacher_key: str) -> Teacher:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM parents_evening_teachers WHERE event_id = ? AND "
                         "teacher_key = ?", (int(event_id), str(teacher_key))).fetchone()
    if r is None:
        raise NotFound(f"{teacher_key} isn't taking part in evening #{event_id}")
    return _teacher_row(r)


def add_teacher(event_id: int, *, actor: Principal, username: str | None = None,
                name: str | None = None, email: str | None = None,
                room: str | None = None) -> Teacher:
    """Add a member of staff who doesn't teach the year (a head of year, the
    SENCO)."""
    e = get_event(event_id)
    _require_editor(actor, "teacher_add", f"event:{e.event_id}")
    login = None
    if username:
        login = next((t for t in TG.teacher_choices()
                      if t["username"].lower() == username.strip().lower()), None)
        if login is None:
            raise ValidationError([f"No staff login called '{username.strip()}'"])
    k = _key(login["username"] if login else None, name)
    if k is None:
        raise ValidationError(["Choose a staff login or type a name"])
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM parents_evening_teachers WHERE event_id = ? AND "
                        "teacher_key = ?", (e.event_id, k)).fetchone():
            raise ValidationError(["Already taking part"])
        conn.execute("INSERT INTO parents_evening_teachers (event_id, teacher_key, teacher_name, "
                     "teacher_email, room, source) VALUES (?, ?, ?, ?, ?, 'added')",
                     (e.event_id, k, (login["display_name"] if login else
                                      " ".join((name or "").split()))[:100],
                      (email or (login["email"] if login else None) or None), _text(room, 30)))
        _audit(conn, "teacher_add", actor, event_id=e.event_id, teacher=k)
    activity_log.record("parents_evenings.teacher_add", target=f"event:{e.event_id}",
                        principal=actor)
    return get_teacher(e.event_id, k)


def update_teacher(event_id: int, teacher_key: str, changes: dict[str, Any], *,
                   actor: Principal) -> Teacher:
    """A teacher's own room, breaks, availability and notes (the teacher or
    the organisers). Breaks and unavailability can't drop booked slots."""
    e = get_event(event_id)
    t = get_teacher(e.event_id, teacher_key)
    if not can_manage(actor, t.teacher_key):
        _deny(actor, "teacher_update", f"event:{e.event_id}",
              "Only the organisers or the teacher can change a teacher's slots.")
    problems: list[str] = []
    vals: dict[str, Any] = {}
    if "room" in changes:
        vals["room"] = _text(changes["room"], 30)
    if "notes" in changes:
        vals["notes"] = _text(changes["notes"], 1000)
    if "breaks" in changes:
        vals["breaks"] = _breaks(changes["breaks"], event_slots(e, include_breaks=True),
                                 "Breaks", problems)
    if "available" in changes:
        a = changes["available"]
        vals["available"] = 1 if (a is True or str(a).strip().lower() in
                                  ("1", "true", "yes", "y")) else 0
    mine = [b for b in list_bookings(event_id=e.event_id, teacher_key=t.teacher_key) if b.active]
    if vals.get("available") == 0 and mine:
        problems.append(f"{t.teacher_name} has {len(mine)} booking(s) - cancel or move them "
                        "first")
    if vals.get("breaks"):
        hit = [b.slot_time for b in mine if b.slot_time in vals["breaks"].split(",")]
        if hit:
            problems.append("Booked slot(s) can't be breaks: " + ", ".join(hit))
    if problems:
        raise ValidationError(problems)
    if not vals:
        return t
    with database.connect() as conn:
        conn.execute("UPDATE parents_evening_teachers SET " + ", ".join(f"{k} = ?" for k in vals)
                     + " WHERE event_id = ? AND teacher_key = ?",
                     (*vals.values(), e.event_id, t.teacher_key))
        _audit(conn, "teacher_update", actor, event_id=e.event_id, teacher=t.teacher_key,
               fields=sorted(vals))
    activity_log.record("parents_evenings.teacher_update", target=f"event:{e.event_id}",
                        principal=actor)
    return get_teacher(e.event_id, t.teacher_key)


def remove_teacher(event_id: int, teacher_key: str, *, actor: Principal) -> bool:
    e = get_event(event_id)
    _require_editor(actor, "teacher_remove", f"event:{e.event_id}")
    t = get_teacher(e.event_id, teacher_key)
    if any(b.active for b in list_bookings(event_id=e.event_id, teacher_key=t.teacher_key)):
        raise ValidationError([f"{t.teacher_name} has bookings - cancel them first, or mark "
                               "the teacher unavailable"])
    with database.connect() as conn:
        conn.execute("DELETE FROM parents_evening_teachers WHERE event_id = ? AND "
                     "teacher_key = ?", (e.event_id, t.teacher_key))
        _audit(conn, "teacher_remove", actor, event_id=e.event_id, teacher=t.teacher_key)
    return True


def teachers_for_pupil(event_id: int, pupil_id: int) -> list[dict[str, Any]]:
    """The pupil's teachers taking part: [{teacher, subjects, groups}]."""
    e = get_event(event_id)
    by_key = {t.teacher_key: t for t in list_teachers(e.event_id)}
    out: dict[str, dict[str, Any]] = {}
    for gi in TG.groups_for_pupil(int(pupil_id), e.academic_year):
        k = _key(gi.group.teacher_username, gi.group.teacher_name)
        if k in by_key:
            x = out.setdefault(k, {"teacher": by_key[k], "subjects": [], "groups": []})
            x["subjects"].append(gi.subject.name)
            x["groups"].append(gi.group.code)
    return sorted(out.values(), key=lambda x: x["teacher"].teacher_name.lower())


def my_events(actor: Principal) -> list[tuple[Event, Teacher]]:
    """Upcoming evenings the signed-in teacher is taking part in."""
    k = teacher_key_for(actor)
    if not k:
        return []
    out = []
    for e in list_events(upcoming=True):
        try:
            out.append((e, get_teacher(e.event_id, k)))
        except NotFound:
            continue
    return out


# ── Families ─────────────────────────────────────────────────────────

def family_keys(pupil_id: int) -> set[str]:
    """What identifies the pupil's family: the e-mail, phone and portal login
    of contacts with parental responsibility."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    out: set[str] = set()
    for c in C.list_for_pupil(int(pupil_id)):
        if not c.parental_responsibility:
            continue
        if c.email:
            out.add("email:" + c.email.lower())
        digits = re.sub(r"\D", "", c.phone or "")
        if len(digits) >= 7:
            out.add("phone:" + digits[-10:])
    for link in PA.links_for_pupil(int(pupil_id)):
        if link.kind == "parent" and link.active:
            out.add("login:" + link.username.lower())
    return out


def siblings(pupil_id: int) -> list[P.Pupil]:
    """Other on-roll pupils who share a parent with the pupil."""
    mine = family_keys(pupil_id)
    if not mine:
        return []
    emails = [k[6:] for k in mine if k.startswith("email:")]
    ids: set[int] = set()
    with database.connect() as conn:
        for e in emails:
            ids |= {r[0] for r in conn.execute(
                "SELECT pupil_id FROM pupil_contacts WHERE lower(email) = ? AND "
                "parental_responsibility = 1", (e,))}
        for k in mine:
            if k.startswith("login:"):
                ids |= {r[0] for r in conn.execute(
                    "SELECT pupil_id FROM portal_links WHERE username = ? AND kind = 'parent' "
                    "AND status = 'active'", (k[6:],))}
            if k.startswith("phone:"):
                for r in conn.execute("SELECT pupil_id, phone FROM pupil_contacts WHERE "
                                      "parental_responsibility = 1 AND phone IS NOT NULL"):
                    if re.sub(r"\D", "", r["phone"])[-10:] == k[6:]:
                        ids.add(r["pupil_id"])
    out = []
    for pid in sorted(ids - {int(pupil_id)}):
        p = P.get_pupil(pid)
        if p and p.roll_status == "on_roll":
            out.append(p)
    return out


def parent_names(pupil_id: int) -> str:
    """The pupil's contacts with parental responsibility, for a booking."""
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    return " and ".join(c.full_name for c in C.list_for_pupil(int(pupil_id))
                        if c.parental_responsibility)[:100]


def staff_choices() -> list[dict]:
    """Staff logins to add as a teacher (empty if the login list can't be read)."""
    return TG.teacher_choices()


# ── Bookings ─────────────────────────────────────────────────────────

def get_booking(booking_id: int) -> Booking:
    with database.connect() as conn:
        r = conn.execute(_BOOK_SELECT + " WHERE b.booking_id = ?", (int(booking_id),)).fetchone()
    if r is None:
        raise NotFound(f"No booking #{booking_id}")
    return _booking_row(r)


def list_bookings(*, event_id: int | None = None, pupil_id: int | None = None,
                  teacher_key: str | None = None, status: str | None = None,
                  include_cancelled: bool = True) -> list[Booking]:
    """Bookings by slot (the old Bookings list)."""
    where, params = [], []
    for col, val in (("b.event_id", event_id), ("b.pupil_id", pupil_id),
                     ("b.teacher_key", teacher_key), ("b.status", status)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if not include_cancelled:
        where.append("b.status != 'Cancelled'")
    sql = _BOOK_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY b.event_id, b.slot_time, b.teacher_name COLLATE NOCASE"
    with database.connect() as conn:
        return [_booking_row(r) for r in conn.execute(sql, params)]


def _busy_family_slots(event_id: int, pupil_id: int, skip: int | None = None
                       ) -> dict[str, str]:
    """Slots where the pupil or a sibling already has an appointment
    (slot -> who)."""
    family = {int(pupil_id)} | {p.pupil_id for p in siblings(pupil_id)}
    out = {}
    for b in list_bookings(event_id=event_id, include_cancelled=False):
        if b.pupil_id in family and b.booking_id != skip:
            out[b.slot_time] = f"{b.pupil_name} with {b.teacher_name}"
    return out


def free_slots(event_id: int, teacher_key: str, *, pupil_id: int | None = None,
               skip: int | None = None) -> list[str]:
    """The teacher's free slots (breaks and booked slots left out); with
    *pupil_id*, also slots when the family is already elsewhere."""
    e = get_event(event_id)
    t = get_teacher(e.event_id, teacher_key)
    if not t.available:
        return []
    taken = {b.slot_time for b in list_bookings(event_id=e.event_id, teacher_key=t.teacher_key,
                                                include_cancelled=False)
             if b.booking_id != skip}
    busy = set(_busy_family_slots(e.event_id, pupil_id, skip)) if pupil_id else set()
    return [s for s in event_slots(e) if s not in t.break_list and s not in taken and
            s not in busy]


def free_slots_for_staff(event_id: int, staff_id: str) -> list[str]:
    """The old name."""
    return free_slots(event_id, staff_id)


def _check_booking(e: Event, p: P.Pupil | None, t: Teacher | None, slot: str | None,
                   *, skip: int | None, problems: list[str], strict_teacher: bool) -> None:
    if not e.is_open:
        problems.append(f"The evening is {e.status.lower()} - bookings can't be made")
    if p is None:
        return
    if p.roll_status != "on_roll":
        problems.append(f"{p.display_name} is not on roll")
    if e.year_group and p.year_group != e.year_group:
        problems.append(f"{p.display_name} is in Year {p.year_group}, the evening is for "
                        f"{e.year_label}")
    if t is None or slot is None:
        return
    if not t.available:
        problems.append(f"{t.teacher_name} isn't available that evening")
    if strict_teacher and t.teacher_key not in {x["teacher"].teacher_key for x in
                                                teachers_for_pupil(e.event_id, p.pupil_id)}:
        problems.append(f"{t.teacher_name} doesn't teach {p.display_name}")
    all_slots = event_slots(e, include_breaks=True)
    if slot not in all_slots:
        problems.append(f"{slot} isn't a slot (slots run every {e.slot_minutes} minutes "
                        f"from {e.start_time})")
        return
    if slot in e.breaks or slot in t.break_list:
        problems.append(f"{slot} is a break")
    for b in list_bookings(event_id=e.event_id, include_cancelled=False):
        if b.booking_id == skip:
            continue
        if b.teacher_key == t.teacher_key and b.slot_time == slot:
            problems.append(f"{t.teacher_name} already has {b.pupil_name} at {slot}")
        if b.pupil_id == p.pupil_id and b.teacher_key == t.teacher_key:
            problems.append(f"{p.display_name} already has an appointment with "
                            f"{t.teacher_name} (at {b.slot_time})")
    busy = _busy_family_slots(e.event_id, p.pupil_id, skip)
    if slot in busy:
        problems.append(f"The family is already booked at {slot} ({busy[slot]})")


def _insert_booking(e: Event, p: P.Pupil, t: Teacher, slot: str, *, actor: Principal,
                    via: str, parent_name: str | None, notes: str | None) -> int:
    with database.connect() as conn:
        bid = conn.execute(
            "INSERT INTO parents_evening_bookings (event_id, pupil_id, teacher_key, "
            "teacher_name, slot_time, parent_name, notes, booked_via, booked_by, updated_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (e.event_id, p.pupil_id, t.teacher_key, t.teacher_name, slot,
             _text(parent_name, 100), _text(notes, 1000), via, actor.username,
             actor.username)).lastrowid
        _audit(conn, "book", actor, event_id=e.event_id, booking_id=bid, pupil_id=p.pupil_id,
               via=via, slot=slot)
    activity_log.record("parents_evenings.book", target=p.admission_no, principal=actor,
                        event=e.event_id, booking=bid, via=via)
    return int(bid)


def create_booking(event_id: int, data: dict[str, Any], *, actor: Principal) -> Booking:
    """Staff book a family's appointment (the old New booking). *data*:
    ``pupil_id`` (id or admission no.), ``teacher_key`` (or the old
    ``staff_id``), ``slot_time``, ``parent_name``, ``notes``, ``status``."""
    e = get_event(event_id)
    _require_staff(actor, "book", f"event:{e.event_id}")
    problems: list[str] = []
    ref = data.get("pupil_id") or data.get("student_id") or data.get("pupil")
    p = _pupil(ref)
    if p is None:
        problems.append("Pupil is required" if not ref else f"No pupil {ref}")
    key = str(data.get("teacher_key") or data.get("staff_id") or "").strip()
    t = None
    if not key:
        problems.append("Teacher is required")
    else:
        try:
            t = get_teacher(e.event_id, key)
        except NotFound as ex:
            problems.append(str(ex))
    if t is not None and not can_manage(actor, t.teacher_key):
        _deny(actor, "book", f"event:{e.event_id}",
              "You can book appointments with yourself; the organisers book any teacher.")
    slot = _time(data.get("slot_time"), "Slot", problems)
    if slot is None and not any(x.startswith("Slot") for x in problems):
        problems.append("Slot is required")
    _check_booking(e, p, t, slot, skip=None, problems=problems,
                   strict_teacher=not is_editor(actor))
    status = _choice(data.get("status"), BOOKING_STATUSES, "Status", problems,
                     DEFAULT_BOOKING_STATUS)
    if status in ("Attended", MISSED) and e.event_date > _today().isoformat():
        problems.append("Attendance can be recorded from the day of the evening")
    if status == "Cancelled":
        problems.append("A new booking can't start cancelled")
    if problems:
        raise ValidationError(problems)
    assert p is not None and t is not None and slot is not None
    bid = _insert_booking(e, p, t, slot, actor=actor, via="staff",
                          parent_name=data.get("parent_name"), notes=data.get("notes"))
    if status != DEFAULT_BOOKING_STATUS:
        return set_booking_status(bid, status, actor=actor)
    return get_booking(bid)


def book(event_id: int, pupil_id: int | str, teacher_key: str, slot_time: str, *,
         actor: Principal, parent_name: str | None = None, notes: str | None = None
         ) -> Booking:
    return create_booking(event_id, {"pupil_id": pupil_id, "teacher_key": teacher_key,
                                     "slot_time": slot_time, "parent_name": parent_name,
                                     "notes": notes}, actor=actor)


def book_for_family(principal: Principal, event_id: int, pupil_id: int, teacher_key: str,
                    slot_time: str, *, notes: str | None = None) -> Booking:
    """A parent books through the portal: the login must be linked to the
    pupil as a parent, booking must be open, and the teacher must teach the
    pupil."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    if principal.is_staff and not PA.has_children(principal):
        raise PermissionDenied("Staff book appointments in Parents' Evenings.")
    p = PA.require_pupil(principal, int(pupil_id), "parent")
    e = get_event(event_id)
    problems: list[str] = []
    if e.status != "Open for Booking":
        problems.append("Booking isn't open for this evening")
    today = _today().isoformat()
    if e.booking_opens and today < e.booking_opens:
        problems.append(f"Booking opens on {e.booking_opens}")
    if (e.booking_closes and today > e.booking_closes) or e.event_date < today:
        problems.append("Booking has closed")
    try:
        t = get_teacher(e.event_id, str(teacher_key))
    except NotFound:
        t = None
        problems.append("That teacher isn't taking part")
    slot = _time(slot_time, "Slot", problems)
    _check_booking(e, p, t, slot, skip=None, problems=problems, strict_teacher=True)
    if problems:
        activity_log.record("parents_evenings.book", target=p.admission_no, outcome="invalid",
                            principal=principal, via="portal")
        raise ValidationError(problems)
    assert t is not None and slot is not None
    name = None
    try:
        from education_system.systems.secondary.infrastructure.authentication import accounts
        login = accounts.find_login(principal.username)
        name = (login or {}).get("display_name")
    except Exception:  # noqa: BLE001 - the name is a convenience
        name = None
    bid = _insert_booking(e, p, t, slot, actor=principal, via="portal",
                          parent_name=name or principal.username, notes=notes)
    return get_booking(bid)


def cancel_for_family(principal: Principal, booking_id: int) -> Booking:
    """A parent cancels their own child's appointment before booking closes."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    b = get_booking(booking_id)
    PA.require_pupil(principal, b.pupil_id, "parent")
    e = get_event(b.event_id)
    today = _today().isoformat()
    if b.status != "Booked" or e.event_date < today or (e.booking_closes and
                                                        today > e.booking_closes):
        raise ValidationError(["This appointment can't be cancelled online now - please "
                               "contact the school"])
    with database.connect() as conn:
        conn.execute("UPDATE parents_evening_bookings SET status = 'Cancelled', updated_by = ?, "
                     "updated_at = datetime('now') WHERE booking_id = ?",
                     (principal.username, b.booking_id))
        _audit(conn, "cancel", principal, event_id=b.event_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id, via="portal")
    activity_log.record("parents_evenings.cancel", target=b.admission_no, principal=principal,
                        booking=b.booking_id, via="portal")
    return get_booking(b.booking_id)


def family_overview(principal: Principal, pupil_id: int) -> list[dict[str, Any]]:
    """What the portal shows for one child: upcoming evenings for their year,
    each teacher with the booking or the free slots."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    p = PA.require_pupil(principal, int(pupil_id), "parent")
    out = []
    for e in list_events(upcoming=True):
        if e.year_group and e.year_group != p.year_group:
            continue
        mine = {b.teacher_key: b for b in list_bookings(event_id=e.event_id,
                                                        pupil_id=p.pupil_id,
                                                        include_cancelled=False)}
        rows = []
        for x in teachers_for_pupil(e.event_id, p.pupil_id):
            t = x["teacher"]
            rows.append({"teacher_key": t.teacher_key, "teacher": t.teacher_name,
                         "subjects": x["subjects"], "room": t.room,
                         "booking": mine.get(t.teacher_key),
                         "free": [] if t.teacher_key in mine or e.status != "Open for Booking"
                         else free_slots(e.event_id, t.teacher_key, pupil_id=p.pupil_id)})
        out.append({"event": e, "can_book": e.status == "Open for Booking", "teachers": rows})
    return out


def update_booking(booking_id: int, changes: dict[str, Any], *, actor: Principal) -> Booking:
    """The old Edit booking: slot, teacher, status, parent name, notes,
    teacher notes."""
    b = get_booking(booking_id)
    if not can_manage(actor, b.teacher_key):
        _deny(actor, "booking_update", b.admission_no,
              "Only the organisers or the teacher can change this appointment.")
    e = get_event(b.event_id)
    problems: list[str] = []
    vals: dict[str, Any] = {}
    key = str(changes.get("teacher_key") or changes.get("staff_id") or b.teacher_key)
    slot = _time(changes.get("slot_time"), "Slot", problems) or b.slot_time
    if key != b.teacher_key or slot != b.slot_time:
        try:
            t = get_teacher(e.event_id, key)
        except NotFound as ex:
            raise ValidationError([str(ex)]) from None
        if key != b.teacher_key and not is_editor(actor):
            _deny(actor, "booking_update", b.admission_no,
                  "Only the organisers can move an appointment to another teacher.")
        _check_booking(e, P.get_pupil(b.pupil_id), t, slot, skip=b.booking_id,
                       problems=problems, strict_teacher=False)
        vals.update(teacher_key=t.teacher_key, teacher_name=t.teacher_name, slot_time=slot)
    if "status" in changes and changes["status"] not in (None, ""):
        st = _choice("No-Show" if str(changes["status"]).lower() == "missed" else
                     changes["status"], BOOKING_STATUSES, "Status", problems, b.status)
        if st in ("Attended", "No-Show") and e.event_date > _today().isoformat():
            problems.append("Attendance can be recorded from the day of the evening")
        if st != b.status:
            vals["status"] = st
    for k, limit in (("parent_name", 100), ("notes", 1000), ("teacher_notes", 4000)):
        if k in changes:
            v = _text(changes[k], limit)
            if v != getattr(b, k):
                vals[k] = v
    if b.status == "Cancelled" and vals.get("status", "Cancelled") != "Cancelled" and \
            not problems:
        _check_booking(e, P.get_pupil(b.pupil_id), get_teacher(e.event_id, vals.get(
            "teacher_key", b.teacher_key)), vals.get("slot_time", b.slot_time),
            skip=b.booking_id, problems=problems, strict_teacher=False)
    if problems:
        raise ValidationError(problems)
    if not vals:
        return b
    with database.connect() as conn:
        conn.execute("UPDATE parents_evening_bookings SET " + ", ".join(f"{k} = ?" for k in vals)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE booking_id = ?",
                     (*vals.values(), actor.username, b.booking_id))
        _audit(conn, "booking_update", actor, event_id=b.event_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id, fields=sorted(vals))
    activity_log.record("parents_evenings.booking_update", target=b.admission_no,
                        principal=actor, booking=b.booking_id, fields=",".join(sorted(vals)))
    return get_booking(b.booking_id)


def set_booking_status(booking_id: int, status: str, *, actor: Principal) -> Booking:
    """The old Status (Booked / Attended / No-Show / Cancelled)."""
    return update_booking(booking_id, {"status": status}, actor=actor)


def cancel_booking(booking_id: int, *, actor: Principal) -> Booking:
    return set_booking_status(booking_id, "Cancelled", actor=actor)


def record_attendance(booking_id: int, attended: bool, *, actor: Principal,
                      teacher_notes: str | None = None) -> Booking:
    """Attended or missed, with the teacher's notes."""
    changes: dict[str, Any] = {"status": "Attended" if attended else MISSED}
    if teacher_notes is not None:
        changes["teacher_notes"] = teacher_notes
    return update_booking(booking_id, changes, actor=actor)


def add_teacher_notes(booking_id: int, notes: str, *, actor: Principal) -> Booking:
    return update_booking(booking_id, {"teacher_notes": notes}, actor=actor)


def delete_booking(booking_id: int, *, actor: Principal) -> bool:
    """The old Delete booking (the organisers; teachers cancel instead)."""
    b = get_booking(booking_id)
    _require_editor(actor, "booking_delete", b.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM parents_evening_bookings WHERE booking_id = ?",
                     (b.booking_id,))
        _audit(conn, "booking_delete", actor, event_id=b.event_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id)
    activity_log.record("parents_evenings.booking_delete", target=b.admission_no,
                        principal=actor, booking=b.booking_id)
    return True


# ── Schedules ────────────────────────────────────────────────────────

def teacher_schedule(event_id: int, teacher_key: str) -> list[dict[str, Any]]:
    """Every slot for the teacher: {'slot', 'kind' (booked/free/break),
    'booking'}."""
    e = get_event(event_id)
    t = get_teacher(e.event_id, teacher_key)
    booked = {b.slot_time: b for b in list_bookings(event_id=e.event_id,
                                                    teacher_key=t.teacher_key,
                                                    include_cancelled=False)}
    out = []
    for s in event_slots(e, include_breaks=True):
        if s in booked:
            out.append({"slot": s, "kind": "booked", "booking": booked[s]})
        elif s in e.breaks or s in t.break_list or not t.available:
            out.append({"slot": s, "kind": "break", "booking": None})
        else:
            out.append({"slot": s, "kind": "free", "booking": None})
    return out


def staff_schedule(event_id: int, staff_id: str) -> list[Booking]:
    """The old staff schedule: the teacher's bookings by slot."""
    return [x["booking"] for x in teacher_schedule(event_id, staff_id) if x["booking"]]


def pupil_schedule(event_id: int, pupil_id: int) -> list[Booking]:
    return list_bookings(event_id=event_id, pupil_id=int(pupil_id), include_cancelled=False)


student_schedule = pupil_schedule


def family_schedule(event_id: int, pupil_id: int) -> list[Booking]:
    """The pupil's and their siblings' appointments, by slot."""
    ids = {int(pupil_id)} | {p.pupil_id for p in siblings(pupil_id)}
    return sorted((b for b in list_bookings(event_id=event_id, include_cancelled=False)
                   if b.pupil_id in ids), key=lambda b: b.slot_time)


def teacher_schedule_text(event_id: int, teacher_key: str) -> str:
    """A printable schedule for one teacher."""
    e = get_event(event_id)
    t = get_teacher(e.event_id, teacher_key)
    lines = [f"{e.name} - {e.event_date} {e.times}", f"{t.teacher_name}"
             + (f", room {t.room}" if t.room else "") + f"   ({e.venue})", ""]
    for x in teacher_schedule(e.event_id, t.teacher_key):
        b = x["booking"]
        if b:
            lines.append(f"{x['slot']}  {b.pupil_name} ({b.form_group or '-'})"
                         + (f"  - {b.parent_name}" if b.parent_name else "")
                         + (f"  [{b.status}]" if b.status != "Booked" else ""))
        else:
            lines.append(f"{x['slot']}  {'(break)' if x['kind'] == 'break' else '-'}")
    return "\n".join(lines)


def export_schedule_csv(event_id: int, path: str | Path, *, actor: Principal,
                        teacher_key: str | None = None) -> int:
    """Every appointment (or one teacher's slots) as CSV."""
    _require_staff(actor, "export")
    e = get_event(event_id)
    keys = [teacher_key] if teacher_key else [t.teacher_key for t in list_teachers(e.event_id)]
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["event", "date", "teacher", "room", "slot", "pupil", "admission_no",
                    "form", "parent", "status", "notes"])
        for k in keys:
            t = get_teacher(e.event_id, k)
            for x in teacher_schedule(e.event_id, k):
                b = x["booking"]
                if teacher_key is None and b is None:
                    continue
                w.writerow([_safe(e.name), e.event_date, _safe(t.teacher_name), _safe(t.room),
                            x["slot"], _safe(b.pupil_name) if b else x["kind"],
                            _safe(b.admission_no) if b else "",
                            _safe(b.form_group) if b else "",
                            _safe(b.parent_name) if b else "", b.status if b else "",
                            _safe(b.notes) if b else ""])
                n += 1
    activity_log.record("parents_evenings.export", principal=actor, event=e.event_id, rows=n)
    return n


# ── E-mail ───────────────────────────────────────────────────────────

def _year_pupils(e: Event) -> list[P.Pupil]:
    return P.list_pupils(year_group=e.year_group) if e.year_group else P.list_pupils()


def _pr_contacts(pupil_ids: list[int]) -> dict[int, list[Any]]:
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    return {pid: [c for c in cs if c.email and c.parental_responsibility]
            for pid, cs in C.emailable_for_pupils(pupil_ids).items()}


def send_invitations(event_id: int, *, actor: Principal, note: str | None = None
                     ) -> dict[str, Any]:
    """E-mail the invitation to the families of the evening's year group
    (one e-mail per address, naming each of their children). Returns
    {'message_id', 'emails', 'no_email'}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    e = get_event(event_id)
    _require_editor(actor, "invite", f"event:{e.event_id}")
    if not e.is_open:
        raise ValidationError([f"The evening is {e.status.lower()}"])
    pupils = _year_pupils(e)
    contacts = _pr_contacts([p.pupil_id for p in pupils])
    by_addr: dict[str, dict[str, Any]] = {}
    no_email = []
    for p in pupils:
        found = contacts.get(p.pupil_id, [])
        if not found:
            no_email.append(p)
        for c in found:
            x = by_addr.setdefault(c.email.lower(), {"name": c.full_name, "pupils": []})
            x["pupils"].append(p.preferred_name or p.legal_first_name)
    if not by_addr:
        return {"message_id": None, "emails": 0, "no_email": no_email}
    template = email_templates.load_template(TEMPLATE_INVITE)
    how = ("Book through the parent portal" + (f" from {e.booking_opens}" if e.booking_opens
                                               else "")
           + (f" until {e.booking_closes}" if e.booking_closes else "")
           + ", or contact the school office to book.")
    letters = []
    for addr, x in by_addr.items():
        names = " and ".join([", ".join(x["pupils"][:-1]), x["pupils"][-1]]) \
            if len(x["pupils"]) > 1 else x["pupils"][0]
        subject, body = template.render({
            "recipient_name": x["name"], "pupil_names": names, "event_name": e.name,
            "event_date": e.event_date, "times": e.times, "venue": e.venue,
            "slot_minutes": e.slot_minutes, "booking_info": how,
            "note": (note or "").strip()})
        letters.append((addr, x["name"], subject, body))
    mid = E.save_prepared("parents_evening_invitation", f"Invitation: {e.name}",
                          f"Invitation: {e.name}", "(one invitation per family)", letters,
                          actor=actor)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with database.connect() as conn:
        conn.execute("UPDATE parents_evening_events SET invitations_sent_at = ? WHERE "
                     "event_id = ?", (now, e.event_id))
        _audit(conn, "invite", actor, event_id=e.event_id, emails=len(letters))
    activity_log.record("parents_evenings.invite", target=f"event:{e.event_id}",
                        principal=actor, emails=len(letters))
    return {"message_id": mid, "emails": len(letters), "no_email": no_email}


def email_schedules(event_id: int, *, actor: Principal, pupil_ids: list[int] | None = None,
                    unsent_only: bool = False) -> dict[str, Any]:
    """E-mail each family their appointment list (siblings in one e-mail).
    Organisers send to all; teachers to families booked with them."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    e = get_event(event_id)
    _require_staff(actor, "schedules", f"event:{e.event_id}")
    rows = list_bookings(event_id=e.event_id, include_cancelled=False)
    if not is_editor(actor):
        mine = {b.pupil_id for b in rows if is_teacher(actor, b.teacher_key)}
        if not mine:
            _deny(actor, "schedules", f"event:{e.event_id}",
                  "You can e-mail schedules to families booked with you.")
        rows = [b for b in rows if b.pupil_id in mine]
    if pupil_ids:
        wanted = {int(x) for x in pupil_ids}
        rows = [b for b in rows if b.pupil_id in wanted]
    if unsent_only:
        rows = [b for b in rows if not b.schedule_sent_at]
    pids = sorted({b.pupil_id for b in rows})
    contacts = _pr_contacts(pids)
    teachers = {t.teacher_key: t for t in list_teachers(e.event_id)}
    by_addr: dict[str, dict[str, Any]] = {}
    no_email = []
    for pid in pids:
        found = contacts.get(pid, [])
        if not found:
            no_email.append(P.get_pupil(pid))
        for c in found:
            by_addr.setdefault(c.email.lower(), {"name": c.full_name, "pupils": set()})[
                "pupils"].add(pid)
    if not by_addr:
        return {"message_id": None, "emails": 0, "no_email": no_email}
    template = email_templates.load_template(TEMPLATE_SCHEDULE)
    letters = []
    for addr, x in by_addr.items():
        lines = []
        for b in sorted((b for b in rows if b.pupil_id in x["pupils"]),
                        key=lambda b: b.slot_time):
            p = P.get_pupil(b.pupil_id)
            room = teachers.get(b.teacher_key)
            lines.append(f"{b.slot_time}  {b.teacher_name}"
                         + (f" (room {room.room})" if room and room.room else "")
                         + f" - {p.preferred_name or p.legal_first_name if p else ''}")
        subject, body = template.render({
            "recipient_name": x["name"], "event_name": e.name, "event_date": e.event_date,
            "venue": e.venue, "slot_minutes": e.slot_minutes,
            "appointments": "\n".join(lines)})
        letters.append((addr, x["name"], subject, body))
    mid = E.save_prepared("parents_evening_schedule", f"Appointments: {e.name}",
                          f"Appointments: {e.name}", "(one schedule per family)", letters,
                          actor=actor)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    ids = [b.booking_id for b in rows if b.pupil_id not in {p.pupil_id for p in no_email if p}]
    with database.connect() as conn:
        conn.executemany("UPDATE parents_evening_bookings SET schedule_sent_at = ? WHERE "
                         "booking_id = ?", [(now, i) for i in ids])
        _audit(conn, "schedules", actor, event_id=e.event_id, emails=len(letters))
    activity_log.record("parents_evenings.schedules", target=f"event:{e.event_id}",
                        principal=actor, emails=len(letters))
    return {"message_id": mid, "emails": len(letters), "no_email": no_email}


# ── Reports ──────────────────────────────────────────────────────────

def booking_rates(event_id: int, *, by: str = "teacher") -> list[dict[str, Any]]:
    """Booking rates. By teacher: pupils they teach in the year vs pupils
    booked with them. By form: pupils in the form vs pupils with at least one
    appointment. Rows: {'group', 'pupils', 'booked', 'appointments',
    'attended', 'missed', 'rate'}."""
    e = get_event(event_id)
    rows = list_bookings(event_id=e.event_id, include_cancelled=False)
    out = []
    if by == "teacher":
        groups = {g.group_id: g for g in TG.list_groups(academic_year=e.academic_year,
                                                        year_group=e.year_group)}
        for t in list_teachers(e.event_id):
            taught: set[int] = set()
            for g in groups.values():
                if _key(g.teacher_username, g.teacher_name) == t.teacher_key:
                    taught |= {p.pupil_id for p in TG.members(g.group_id)}
            mine = [b for b in rows if b.teacher_key == t.teacher_key]
            booked = {b.pupil_id for b in mine}
            out.append(_rate_row(t.teacher_name, len(taught | booked), mine, booked))
    elif by == "form":
        pupils = _year_pupils(e)
        forms: dict[str, set[int]] = {}
        for p in pupils:
            forms.setdefault(p.form_group or "(no form)", set()).add(p.pupil_id)
        for f, ids in sorted(forms.items()):
            mine = [b for b in rows if b.pupil_id in ids]
            out.append(_rate_row(f, len(ids), mine, {b.pupil_id for b in mine}))
    else:
        raise ValidationError(["Report by teacher or form"])
    return out


def _rate_row(group: str, pupils: int, mine: list[Booking], booked: set[int]
              ) -> dict[str, Any]:
    return {"group": group, "pupils": pupils, "booked": len(booked),
            "appointments": len(mine),
            "attended": sum(1 for b in mine if b.status == "Attended"),
            "missed": sum(1 for b in mine if b.status == MISSED),
            "rate": round(100 * len(booked) / pupils) if pupils else 0}


def not_booked(event_id: int) -> list[P.Pupil]:
    """Pupils in the year with no appointment yet (to chase)."""
    e = get_event(event_id)
    have = {b.pupil_id for b in list_bookings(event_id=e.event_id, include_cancelled=False)}
    return [p for p in _year_pupils(e) if p.pupil_id not in have]


@dataclass
class EventSummary:
    event: Event
    teachers: int = 0
    total_slots: int = 0
    capacity: int = 0
    bookings: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    pupils_booked: int = 0
    pupils_in_year: int = 0

    @property
    def fill_rate(self) -> int:
        return round(100 * self.bookings / self.capacity) if self.capacity else 0


def summarize_event(event_id: int) -> EventSummary:
    e = get_event(event_id)
    teachers = list_teachers(e.event_id, available_only=True)
    slots = event_slots(e)
    rows = list_bookings(event_id=e.event_id)
    active = [b for b in rows if b.active]
    return EventSummary(event=e, teachers=len(teachers), total_slots=len(slots),
                        capacity=sum(len([s for s in slots if s not in t.break_list])
                                     for t in teachers),
                        bookings=len(active), by_status=dict(Counter(b.status for b in rows)),
                        pupils_booked=len({b.pupil_id for b in active}),
                        pupils_in_year=len(_year_pupils(e)))


@dataclass
class OverallSummary:
    total_events: int = 0
    upcoming_events: int = 0
    open_for_booking: int = 0
    completed: int = 0
    next_event: Event | None = None
    total_bookings: int = 0
    by_event_status: dict[str, int] = field(default_factory=dict)
    by_booking_status: dict[str, int] = field(default_factory=dict)


def summary() -> OverallSummary:
    """The old overall summary."""
    events = list_events()
    today = _today().isoformat()
    upcoming = [e for e in events if e.event_date >= today and e.status != "Cancelled"]
    rows = list_bookings()
    return OverallSummary(
        total_events=len(events), upcoming_events=len(upcoming),
        open_for_booking=sum(1 for e in events if e.status == "Open for Booking"),
        completed=sum(1 for e in events if e.status == "Completed"),
        next_event=upcoming[0] if upcoming else None, total_bookings=len(rows),
        by_event_status=dict(Counter(e.status for e in events)),
        by_booking_status=dict(Counter(b.status for b in rows)))


def for_pupil(pupil_id: int) -> list[Booking]:
    """Every appointment for a pupil (the pupil record)."""
    return list_bookings(pupil_id=int(pupil_id))


def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    """Bookings as CSV (filters as :func:`list_bookings`)."""
    _require_staff(actor, "export")
    rows = list_bookings(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "event", "slot", "admission_no", "pupil", "year", "form", "teacher",
                    "parent", "status", "via", "notes", "teacher_notes"])
        for b in rows:
            w.writerow([b.booking_id, b.event_id, b.slot_time, _safe(b.admission_no),
                        _safe(b.pupil_name), b.pupil_year, _safe(b.form_group),
                        _safe(b.teacher_name), _safe(b.parent_name), b.status, b.booked_via,
                        _safe(b.notes), _safe(b.teacher_notes)])
    activity_log.record("parents_evenings.export", principal=actor, rows=len(rows))
    return len(rows)
