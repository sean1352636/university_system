"""Parents' Evenings data layer for the Primary School System.

Two linked tables:

* ``parents_evenings`` — one row per event (date, year group target,
  location, slot length, opening/closing times, status, notes).
* ``parents_evening_bookings`` — one row per scheduled meeting in an
  event: which staff member meets which student's parents at which
  slot time, plus a status (Booked/Attended/No-Show/Cancelled).

Invariants enforced at the data layer:
* Slot time must fall within the event window.
* Slot times must align to the event's ``slot_minutes`` cadence.
* Within one event, a staff member can't have two bookings at the
  same slot time (DB unique index).
* Within one event, the same student can't be booked with the same
  staff at the same slot (DB unique index).

Cascade: deleting an event removes all its bookings. Deleting a
student or staff member clears their bookings.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from education_system.primarysch_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.PARENTS_EVENINGS_DB

YEAR_GROUPS: tuple[str, ...] = ("Year 12", "Year 13", "Both")
DEFAULT_YEAR_GROUP: str = "Both"

EVENT_STATUSES: tuple[str, ...] = (
    "Scheduled", "Open for Booking", "Closed for Booking",
    "In Progress", "Completed", "Cancelled",
)
DEFAULT_EVENT_STATUS: str = "Scheduled"
OPEN_EVENT_STATUSES: tuple[str, ...] = (
    "Scheduled", "Open for Booking", "Closed for Booking", "In Progress")

BOOKING_STATUSES: tuple[str, ...] = (
    "Booked", "Attended", "No-Show", "Cancelled",
)
DEFAULT_BOOKING_STATUS: str = "Booked"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS parents_evenings (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    event_date    TEXT NOT NULL,
    year_group    TEXT NOT NULL DEFAULT 'Both',
    location      TEXT,
    start_time    TEXT NOT NULL,
    end_time      TEXT NOT NULL,
    slot_minutes  INTEGER NOT NULL DEFAULT 10,
    status        TEXT NOT NULL DEFAULT 'Scheduled',
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS parents_evening_bookings (
    booking_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    staff_id    TEXT NOT NULL,
    slot_time   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Booked',
    parent_name TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (event_id)   REFERENCES parents_evenings(event_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    FOREIGN KEY (staff_id)   REFERENCES staff(staff_id)
        ON DELETE CASCADE,
    UNIQUE (event_id, staff_id, slot_time),
    UNIQUE (event_id, student_id, staff_id, slot_time)
);

CREATE INDEX IF NOT EXISTS idx_pe_date    ON parents_evenings(event_date);
CREATE INDEX IF NOT EXISTS idx_pe_status  ON parents_evenings(status);
CREATE INDEX IF NOT EXISTS idx_peb_event  ON parents_evening_bookings(event_id);
CREATE INDEX IF NOT EXISTS idx_peb_student ON parents_evening_bookings(student_id);
CREATE INDEX IF NOT EXISTS idx_peb_staff  ON parents_evening_bookings(staff_id);
CREATE INDEX IF NOT EXISTS idx_peb_slot   ON parents_evening_bookings(event_id, slot_time);
"""


@dataclass
class Event:
    event_id: int
    name: str
    event_date: str
    year_group: str
    location: str | None
    start_time: str
    end_time: str
    slot_minutes: int
    status: str
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Booking:
    booking_id: int
    event_id: int
    student_id: str
    staff_id: str
    slot_time: str
    status: str
    parent_name: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class BookingRow:
    booking: Booking
    student_name: str
    staff_name: str
    event_name: str
    event_date: str


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.primarysch_system.modules.domain import _pupils_bridge as _students
    from education_system.primarysch_system.modules.domain.staff import staff as _staff
    _students.init_db()
    _staff.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Parents-evenings schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_event(r: sqlite3.Row) -> Event:
    return Event(
        event_id=r["event_id"], name=r["name"],
        event_date=r["event_date"], year_group=r["year_group"],
        location=r["location"], start_time=r["start_time"],
        end_time=r["end_time"], slot_minutes=r["slot_minutes"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_booking(r: sqlite3.Row) -> Booking:
    return Booking(
        booking_id=r["booking_id"], event_id=r["event_id"],
        student_id=r["student_id"], staff_id=r["staff_id"],
        slot_time=r["slot_time"], status=r["status"],
        parent_name=r["parent_name"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_date(v: Any, label: str, *,
                    required: bool = True) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_time(v: Any, label: str) -> str:
    s = _require(v, label).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24h)")
    return s


def _time_to_minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _validate_event_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(d.get("name"), "Name").strip()
    out["event_date"] = _validate_date(d.get("event_date"), "Event date")

    yg = _require(d.get("year_group") or DEFAULT_YEAR_GROUP,
                   "Year group").strip()
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg

    out["location"] = (d.get("location") or "").strip() or None
    out["start_time"] = _validate_time(d.get("start_time"), "Start time")
    out["end_time"]   = _validate_time(d.get("end_time"), "End time")
    if _time_to_minutes(out["end_time"]) \
            <= _time_to_minutes(out["start_time"]):
        raise ValidationError("End time must be after start time")

    sm = d.get("slot_minutes") or 10
    try:
        sm = int(sm)
    except (TypeError, ValueError):
        raise ValidationError("Slot minutes must be a whole number") from None
    if sm < 1 or sm > 60:
        raise ValidationError("Slot minutes must be between 1 and 60")
    out["slot_minutes"] = sm

    window = (_time_to_minutes(out["end_time"])
              - _time_to_minutes(out["start_time"]))
    if window % sm != 0:
        raise ValidationError(
            f"Event window ({window} min) must be a multiple of "
            f"the slot length ({sm} min)")

    status = (d.get("status") or DEFAULT_EVENT_STATUS).strip()
    if status not in EVENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(EVENT_STATUSES)}")
    out["status"] = status

    out["notes"] = (d.get("notes") or "").strip() or None
    return out


def _validate_booking_payload(event: Event,
                                 d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sid = _require(d.get("student_id"), "Student ID").strip()
    from education_system.primarysch_system.modules.domain import _pupils_bridge as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    stid = _require(d.get("staff_id"), "Staff ID").strip().upper()
    from education_system.primarysch_system.modules.domain.staff import staff as _staff
    if _staff.get_staff(stid) is None:
        raise ValidationError(f"No staff with id {stid}")
    out["staff_id"] = stid

    slot = _validate_time(d.get("slot_time"), "Slot time")
    sm = _time_to_minutes(slot)
    start = _time_to_minutes(event.start_time)
    end = _time_to_minutes(event.end_time)
    if sm < start or sm >= end:
        raise ValidationError(
            f"Slot time must be within event window "
            f"{event.start_time}–{event.end_time}")
    if (sm - start) % event.slot_minutes != 0:
        raise ValidationError(
            f"Slot time must align to "
            f"{event.slot_minutes}-minute boundaries from "
            f"{event.start_time}")
    out["slot_time"] = slot

    status = (d.get("status") or DEFAULT_BOOKING_STATUS).strip()
    if status not in BOOKING_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BOOKING_STATUSES)}")
    out["status"] = status

    out["parent_name"] = (d.get("parent_name") or "").strip() or None
    out["notes"]       = (d.get("notes") or "").strip() or None
    return out


# ── Event CRUD ────────────────────────────────────────────────────

def create_event(d: dict[str, Any]) -> Event:
    init_db()
    p = _validate_event_payload(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO parents_evenings
                  (name, event_date, year_group, location, start_time,
                   end_time, slot_minutes, status, notes,
                   created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["event_date"], p["year_group"], p["location"],
             p["start_time"], p["end_time"], p["slot_minutes"],
             p["status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_event(new_id)
    assert out is not None
    logger.info("Created parents' evening #%d %s on %s",
                new_id, p["name"], p["event_date"])
    return out


def get_event(event_id: int) -> Event | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM parents_evenings WHERE event_id = ?",
            (event_id,)).fetchone()
        return _row_event(r) if r else None


def list_events(
    *,
    year_group: str | None = None,
    status: str | None = None,
    open_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Event]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if status:
        if status not in EVENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(EVENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        ph = ",".join("?" * len(OPEN_EVENT_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_EVENT_STATUSES)
    if date_from:
        clauses.append("event_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("event_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM parents_evenings {where} "
           "ORDER BY event_date DESC, start_time, event_id")
    with _connect() as conn:
        return [_row_event(r) for r in conn.execute(sql, args).fetchall()]


def update_event(event_id: int, d: dict[str, Any]) -> Event:
    init_db()
    existing = get_event(event_id)
    if existing is None:
        raise ValidationError(f"No event with id {event_id}")
    merged = {
        "name":         d.get("name", existing.name),
        "event_date":   d.get("event_date", existing.event_date),
        "year_group":   d.get("year_group", existing.year_group),
        "location":     d.get("location", existing.location),
        "start_time":   d.get("start_time", existing.start_time),
        "end_time":     d.get("end_time", existing.end_time),
        "slot_minutes": d.get("slot_minutes", existing.slot_minutes),
        "status":       d.get("status", existing.status),
        "notes":        d.get("notes", existing.notes),
    }
    p = _validate_event_payload(merged)

    # If window changed, existing bookings outside the new window must be
    # caught and reported (we don't silently drop bookings).
    with _connect() as conn:
        bad = conn.execute(
            """SELECT slot_time FROM parents_evening_bookings
                WHERE event_id = ?
                  AND (slot_time < ? OR slot_time >= ?)""",
            (event_id, p["start_time"], p["end_time"]),
        ).fetchall()
        if bad:
            raise ValidationError(
                f"Cannot shrink window — {len(bad)} existing booking(s) "
                f"would fall outside it. Move or cancel them first.")

        conn.execute(
            """UPDATE parents_evenings SET
                  name=?, event_date=?, year_group=?, location=?,
                  start_time=?, end_time=?, slot_minutes=?, status=?,
                  notes=?, updated_at=datetime('now')
               WHERE event_id=?""",
            (p["name"], p["event_date"], p["year_group"], p["location"],
             p["start_time"], p["end_time"], p["slot_minutes"],
             p["status"], p["notes"], event_id),
        )
        conn.commit()
    out = get_event(event_id)
    assert out is not None
    logger.info("Updated parents' evening #%d", event_id)
    return out


def set_event_status(event_id: int, status: str) -> Event:
    if status not in EVENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(EVENT_STATUSES)}")
    return update_event(event_id, {"status": status})


def delete_event(event_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM parents_evenings WHERE event_id = ?",
            (event_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted parents' evening #%d (and bookings)",
                        event_id)
            return True
        return False


# ── Slot helpers ──────────────────────────────────────────────────

def event_slots(event: Event) -> list[str]:
    """Return all slot start times within the event window."""
    out: list[str] = []
    start = _time_to_minutes(event.start_time)
    end = _time_to_minutes(event.end_time)
    t = start
    while t < end:
        out.append(f"{t // 60:02d}:{t % 60:02d}")
        t += event.slot_minutes
    return out


# ── Booking CRUD ──────────────────────────────────────────────────

def _row_booking_or_error(r: sqlite3.Row | None,
                            booking_id: int) -> Booking:
    if r is None:
        raise ValidationError(f"No booking with id {booking_id}")
    return _row_booking(r)


def create_booking(event_id: int, d: dict[str, Any]) -> Booking:
    init_db()
    event = get_event(event_id)
    if event is None:
        raise ValidationError(f"No event with id {event_id}")
    p = _validate_booking_payload(event, d)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO parents_evening_bookings
                      (event_id, student_id, staff_id, slot_time, status,
                       parent_name, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (event_id, p["student_id"], p["staff_id"], p["slot_time"],
                 p["status"], p["parent_name"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"That slot is already taken — staff {p['staff_id']} "
                f"already has a booking at {p['slot_time']} for "
                f"this event.") from e
        raise
    out = get_booking(new_id)
    assert out is not None
    logger.info(
        "Created booking #%d (event=%d, student=%s, staff=%s, slot=%s)",
        new_id, event_id, p["student_id"], p["staff_id"], p["slot_time"])
    return out


def get_booking(booking_id: int) -> Booking | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM parents_evening_bookings WHERE booking_id = ?",
            (booking_id,)).fetchone()
        return _row_booking(r) if r else None


def list_bookings(
    *,
    event_id: int | None = None,
    student_id: str | None = None,
    staff_id: str | None = None,
    status: str | None = None,
    slot_time: str | None = None,
) -> list[Booking]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if event_id is not None:
        clauses.append("event_id = ?")
        args.append(event_id)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if staff_id:
        clauses.append("staff_id = ?")
        args.append(staff_id.strip().upper())
    if status:
        if status not in BOOKING_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(BOOKING_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if slot_time:
        clauses.append("slot_time = ?")
        args.append(_validate_time(slot_time, "Slot time"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM parents_evening_bookings {where} "
           "ORDER BY event_id, slot_time, staff_id, student_id")
    with _connect() as conn:
        return [_row_booking(r)
                 for r in conn.execute(sql, args).fetchall()]


def list_bookings_with_detail(**kwargs) -> list[BookingRow]:
    rows = list_bookings(**kwargs)
    if not rows:
        return []
    from education_system.primarysch_system.modules.domain.staff import staff as _staff
    from education_system.primarysch_system.modules.domain import _pupils_bridge as _students
    s_names = {s.student_id: s.full_name
                for s in _students.list_students()}
    t_names = {t.staff_id: t.full_name
                for t in _staff.list_staff()}
    events: dict[int, Event] = {}
    out: list[BookingRow] = []
    for b in rows:
        if b.event_id not in events:
            ev = get_event(b.event_id)
            events[b.event_id] = ev
        ev = events[b.event_id]
        out.append(BookingRow(
            booking=b,
            student_name=s_names.get(b.student_id, "(unknown)"),
            staff_name=t_names.get(b.staff_id, "(unknown)"),
            event_name=ev.name if ev else "(deleted event)",
            event_date=ev.event_date if ev else "—",
        ))
    return out


def update_booking(booking_id: int, d: dict[str, Any]) -> Booking:
    init_db()
    existing = get_booking(booking_id)
    if existing is None:
        raise ValidationError(f"No booking with id {booking_id}")
    event = get_event(existing.event_id)
    if event is None:
        raise ValidationError(f"Parent event {existing.event_id} "
                               f"no longer exists")
    merged = {
        "student_id": d.get("student_id", existing.student_id),
        "staff_id":   d.get("staff_id", existing.staff_id),
        "slot_time":  d.get("slot_time", existing.slot_time),
        "status":     d.get("status", existing.status),
        "parent_name": d.get("parent_name", existing.parent_name),
        "notes":      d.get("notes", existing.notes),
    }
    p = _validate_booking_payload(event, merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE parents_evening_bookings SET
                      student_id=?, staff_id=?, slot_time=?, status=?,
                      parent_name=?, notes=?, updated_at=datetime('now')
                   WHERE booking_id=?""",
                (p["student_id"], p["staff_id"], p["slot_time"],
                 p["status"], p["parent_name"], p["notes"], booking_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"That slot is already taken for staff {p['staff_id']} "
                f"at {p['slot_time']}.") from e
        raise
    out = get_booking(booking_id)
    assert out is not None
    logger.info("Updated booking #%d (status=%s)", booking_id, out.status)
    return out


def set_booking_status(booking_id: int, status: str) -> Booking:
    if status not in BOOKING_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BOOKING_STATUSES)}")
    return update_booking(booking_id, {"status": status})


def delete_booking(booking_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM parents_evening_bookings WHERE booking_id = ?",
            (booking_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted booking #%d", booking_id)
            return True
        return False


# ── Schedule views ────────────────────────────────────────────────

def free_slots_for_staff(event_id: int, staff_id: str) -> list[str]:
    event = get_event(event_id)
    if event is None:
        raise ValidationError(f"No event with id {event_id}")
    taken = {b.slot_time
              for b in list_bookings(event_id=event_id,
                                       staff_id=staff_id)
              if b.status != "Cancelled"}
    return [s for s in event_slots(event) if s not in taken]


def staff_schedule(event_id: int, staff_id: str) -> list[Booking]:
    return [b for b in list_bookings(event_id=event_id,
                                        staff_id=staff_id)
            if b.status != "Cancelled"]


def student_schedule(event_id: int, student_id: str) -> list[Booking]:
    return [b for b in list_bookings(event_id=event_id,
                                        student_id=student_id)
            if b.status != "Cancelled"]


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class EventSummary:
    event: Event
    total_slots: int
    booked: int
    attended: int
    no_shows: int
    cancelled: int
    distinct_students: int
    distinct_staff: int
    distinct_staff_total_slots: int   # slots * staff bookable
    fill_rate: float | None           # % of (active) bookings / slots*staff


def summarize_event(event_id: int) -> EventSummary:
    event = get_event(event_id)
    if event is None:
        raise ValidationError(f"No event with id {event_id}")
    bookings = list_bookings(event_id=event_id)
    slots = event_slots(event)
    booked = sum(1 for b in bookings if b.status == "Booked")
    attended = sum(1 for b in bookings if b.status == "Attended")
    no_shows = sum(1 for b in bookings if b.status == "No-Show")
    cancelled = sum(1 for b in bookings if b.status == "Cancelled")
    distinct_students = len({b.student_id for b in bookings
                                if b.status != "Cancelled"})
    distinct_staff = len({b.staff_id for b in bookings
                            if b.status != "Cancelled"})
    capacity = len(slots) * distinct_staff if distinct_staff else 0
    active = booked + attended + no_shows
    fill = round(100.0 * active / capacity, 1) if capacity else None
    return EventSummary(
        event=event, total_slots=len(slots),
        booked=booked, attended=attended, no_shows=no_shows,
        cancelled=cancelled,
        distinct_students=distinct_students,
        distinct_staff=distinct_staff,
        distinct_staff_total_slots=capacity,
        fill_rate=fill,
    )


@dataclass
class OverallSummary:
    total_events: int
    upcoming_events: int
    open_for_booking: int
    completed: int
    total_bookings: int
    by_event_status: dict[str, int]
    by_booking_status: dict[str, int]
    next_event: Event | None


def summary() -> OverallSummary:
    init_db()
    today = datetime.now().date().isoformat()
    events = list_events()
    bookings = list_bookings()
    by_es = {s: 0 for s in EVENT_STATUSES}
    by_bs = {s: 0 for s in BOOKING_STATUSES}
    for e in events:
        by_es[e.status] = by_es.get(e.status, 0) + 1
    for b in bookings:
        by_bs[b.status] = by_bs.get(b.status, 0) + 1
    upcoming = [e for e in events if e.event_date >= today
                 and e.status != "Cancelled"]
    upcoming.sort(key=lambda e: (e.event_date, e.start_time))
    return OverallSummary(
        total_events=len(events),
        upcoming_events=len(upcoming),
        open_for_booking=by_es.get("Open for Booking", 0),
        completed=by_es.get("Completed", 0),
        total_bookings=len(bookings),
        by_event_status=by_es,
        by_booking_status=by_bs,
        next_event=upcoming[0] if upcoming else None,
    )
