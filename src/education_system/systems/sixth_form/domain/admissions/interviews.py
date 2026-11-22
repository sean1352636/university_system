"""Interview rooms, slots and bookings for sixth-form admissions.

Before this the applicant row held a bare ``interview_date`` and
``interviewer``, the interview room lived in a JSON side file used by
the CLI, and nothing stopped a past date, two applicants in one room,
or one interviewer on two panels at once.

* **Rooms** (``admissions_interview_rooms``) — the rooms admissions
  interviews in, optionally linked to a room-booking resource
  (``rb_resources``) so that room's bookings, lessons and exams count as
  clashes. :func:`list_rooms` / :func:`add_room` / :func:`remove_room`
  (removal is a soft "inactive", refused while future slots use it).
* **Slots** (``admissions_interview_slots``) — date, start/end time,
  room, panel members (staff usernames or names) and a capacity (how
  many applicants the slot takes). Creating or changing a slot refuses
  a past time, a room already used by an overlapping slot (or booked in
  room booking), and a panel member already on an overlapping slot.
* **Bookings** (``admissions_interview_bookings``) — an applicant in a
  slot. Booking refuses a past slot, a full slot, and an applicant who
  already holds a booking. Cancelling or rescheduling never deletes:
  the booking is marked Cancelled / Rescheduled (the new booking points
  back to it), so :func:`booking_history` shows everything.

Booking, rescheduling and cancelling drive
:func:`admissions.schedule_interview`, :func:`admissions.reschedule_interview`
and :func:`admissions.cancel_interview`, so the applicant status,
``interview_date`` / ``interviewer`` and the timeline stay as before.
Panel scoring stays with the admissions interview scorecard
(:func:`admissions.save_interview_score`).

Everything needs the ``admissions`` capability.
"""

from __future__ import annotations

import contextlib
import contextvars
import datetime as _dt
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.systems.sixth_form.domain.admissions import (
    _guard,
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

SLOT_STATUSES: tuple[str, ...] = ("Open", "Cancelled")
BOOKING_STATUSES: tuple[str, ...] = ("Booked", "Attended", "No-show",
                                     "Rescheduled", "Cancelled")
#: A booking in one of these holds the applicant's place.
ACTIVE_BOOKING: str = "Booked"

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_interview_rooms (
    room_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    capacity     INTEGER,
    resource_id  INTEGER,
    notes        TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    created_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    removed_by   TEXT,
    removed_at   TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_adm_iv_room_name
    ON admissions_interview_rooms(LOWER(name));

CREATE TABLE IF NOT EXISTS admissions_interview_slots (
    slot_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_date     TEXT NOT NULL,
    start_time    TEXT NOT NULL,
    end_time      TEXT NOT NULL,
    room_id       INTEGER,
    panel_json    TEXT NOT NULL DEFAULT '[]',
    capacity      INTEGER NOT NULL DEFAULT 1,
    notes         TEXT,
    status        TEXT NOT NULL DEFAULT 'Open',
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    cancelled_by  TEXT,
    cancelled_at  TEXT,
    cancel_reason TEXT,
    FOREIGN KEY (room_id) REFERENCES admissions_interview_rooms(room_id)
);
CREATE INDEX IF NOT EXISTS idx_adm_iv_slot_date
    ON admissions_interview_slots(slot_date);

CREATE TABLE IF NOT EXISTS admissions_interview_bookings (
    booking_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id         INTEGER NOT NULL,
    applicant_id    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Booked',
    booked_by       TEXT,
    booked_at       TEXT NOT NULL DEFAULT (datetime('now')),
    ended_by        TEXT,
    ended_at        TEXT,
    reason          TEXT,
    replaces_id     INTEGER,
    FOREIGN KEY (slot_id) REFERENCES admissions_interview_slots(slot_id),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE,
    FOREIGN KEY (replaces_id) REFERENCES admissions_interview_bookings(booking_id)
);
CREATE INDEX IF NOT EXISTS idx_adm_iv_book_slot
    ON admissions_interview_bookings(slot_id);
CREATE INDEX IF NOT EXISTS idx_adm_iv_book_aid
    ON admissions_interview_bookings(applicant_id);
"""


@dataclass
class Room:
    room_id: int
    name: str
    capacity: int | None
    resource_id: int | None
    notes: str | None
    active: bool


@dataclass
class Slot:
    slot_id: int
    slot_date: str
    start_time: str
    end_time: str
    room_id: int | None
    room_name: str | None
    panel: list[str]
    capacity: int
    notes: str | None
    status: str
    booked: int = 0
    cancel_reason: str | None = None

    @property
    def places_left(self) -> int:
        return max(self.capacity - self.booked, 0)

    @property
    def is_full(self) -> bool:
        return self.booked >= self.capacity

    @property
    def panel_label(self) -> str:
        return ", ".join(self.panel)

    @property
    def label(self) -> str:
        where = f" — {self.room_name}" if self.room_name else ""
        return f"{self.slot_date} {self.start_time}–{self.end_time}{where}"


@dataclass
class Booking:
    booking_id: int
    slot_id: int
    applicant_id: str
    status: str
    booked_by: str | None
    booked_at: str
    ended_by: str | None
    ended_at: str | None
    reason: str | None
    replaces_id: int | None
    slot: Slot | None = None


@dataclass
class ClashReport:
    room: list[str] = field(default_factory=list)
    panel: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.room or self.panel)

    def message(self) -> str:
        return "; ".join(self.room + self.panel)


# ── DB plumbing ────────────────────────────────────────────────────

_READY = False


def init_db() -> None:
    global _READY
    if _READY:
        return
    _adm.init_db()
    with _adm._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY = True


_driving: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "adm_interview_slot_driving", default=False)


@contextlib.contextmanager
def _drive() -> Iterator[None]:
    """Mark that the slot code is the caller of the admissions interview
    functions (so they do not route back here)."""
    token = _driving.set(True)
    try:
        yield
    finally:
        _driving.reset(token)


def driving() -> bool:
    """True while this module is updating the applicant's interview."""
    return _driving.get()


def _now() -> _dt.datetime:
    return _dt.datetime.now()


def _clean_time(value: Any, label: str) -> str:
    s = (str(value or "")).strip()
    if len(s) == 4 and s[1] == ":":
        s = "0" + s
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    return s


def _clean_panel(panel: Any) -> list[str]:
    if panel is None:
        return []
    items = panel.split(",") if isinstance(panel, str) else list(panel)
    out: list[str] = []
    for p in items:
        name = (str(p or "")).strip()
        if name and name.lower() not in {x.lower() for x in out}:
            out.append(name)
    return out


def _starts(slot_date: str, start_time: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(f"{slot_date}T{start_time}")


# ── Rooms ──────────────────────────────────────────────────────────

def _room(r: Any) -> Room:
    return Room(room_id=r["room_id"], name=r["name"], capacity=r["capacity"],
                resource_id=r["resource_id"], notes=r["notes"],
                active=bool(r["active"]))


def list_rooms(*, active_only: bool = True) -> list[Room]:
    """Interview rooms (active ones unless ``active_only=False``)."""
    init_db()
    _guard.require("interview rooms")
    sql = "SELECT * FROM admissions_interview_rooms"
    if active_only:
        sql += " WHERE active = 1"
    with _adm._connect() as conn:
        rows = conn.execute(sql + " ORDER BY name COLLATE NOCASE").fetchall()
    return [_room(r) for r in rows]


def get_room(room_id: int) -> Room | None:
    init_db()
    _guard.require("interview rooms")
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_interview_rooms "
                         "WHERE room_id = ?", (room_id,)).fetchone()
    return _room(r) if r else None


def room_booking_rooms() -> list[tuple[int, str]]:
    """(resource_id, name) of active room-booking rooms, for linking an
    interview room to the college's room list."""
    try:
        from education_system.systems.sixth_form.domain.academics.room_booking import (
            room_booking as _rb,
        )
        return [(r.resource_id, r.name)
                for r in _rb.list_resources(active_only=True)
                if r.resource_type in ("Room", "Meeting Room", "Hall", "Lab")]
    except Exception:  # noqa: BLE001 — room booking is optional here
        logger.warning("Room-booking rooms not read", exc_info=True)
        return []


def add_room(name: str, *, capacity: int | None = None,
             resource_id: int | None = None,
             notes: str | None = None) -> Room:
    """Add an interview room (or re-activate one with the same name).

    ``resource_id`` links it to a room-booking room; when only a name is
    given and a room-booking room has that name, it is linked
    automatically."""
    init_db()
    _guard.require("changing interview rooms")
    name = (name or "").strip()
    if not name:
        raise ValidationError("Room name is required")
    if capacity not in (None, ""):
        try:
            capacity = int(capacity)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a whole number") from None
        if capacity < 1:
            raise ValidationError("Capacity must be at least 1")
    else:
        capacity = None
    known = dict(room_booking_rooms())
    if resource_id is not None:
        if int(resource_id) not in known:
            raise ValidationError(f"No active room-booking room #{resource_id}")
        resource_id = int(resource_id)
    else:
        resource_id = next((rid for rid, n in known.items()
                            if n.lower() == name.lower()), None)
    with _adm._connect() as conn:
        old = conn.execute("SELECT * FROM admissions_interview_rooms "
                           "WHERE LOWER(name) = LOWER(?)", (name,)).fetchone()
        if old is not None:
            if old["active"]:
                raise ValidationError(f"Room {name!r} is already listed")
            conn.execute(
                "UPDATE admissions_interview_rooms SET active = 1, "
                "capacity = COALESCE(?, capacity), "
                "resource_id = COALESCE(?, resource_id), "
                "notes = COALESCE(?, notes), removed_by = NULL, "
                "removed_at = NULL WHERE room_id = ?",
                (capacity, resource_id, (notes or "").strip() or None,
                 old["room_id"]))
            room_id = old["room_id"]
        else:
            cur = conn.execute(
                "INSERT INTO admissions_interview_rooms (name, capacity, "
                "resource_id, notes, created_by) VALUES (?, ?, ?, ?, ?)",
                (name, capacity, resource_id, (notes or "").strip() or None,
                 _guard.actor()))
            room_id = cur.lastrowid
        conn.commit()
    out = get_room(room_id)
    assert out is not None
    return out


def remove_room(room_id: int) -> bool:
    """Take a room off the list (kept for history). Refused while an open
    future slot uses it."""
    init_db()
    _guard.require("changing interview rooms")
    today = _dt.date.today().isoformat()
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_interview_rooms "
                         "WHERE room_id = ?", (room_id,)).fetchone()
        if r is None or not r["active"]:
            return False
        used = conn.execute(
            "SELECT COUNT(*) FROM admissions_interview_slots WHERE room_id = ? "
            "AND status = 'Open' AND slot_date >= ?", (room_id, today)
        ).fetchone()[0]
        if used:
            raise ValidationError(
                f"{r['name']} is used by {used} upcoming slot(s); move or "
                "cancel them first")
        conn.execute(
            "UPDATE admissions_interview_rooms SET active = 0, removed_by = ?, "
            "removed_at = datetime('now') WHERE room_id = ?",
            (_guard.actor(), room_id))
        conn.commit()
    return True


def import_room_names(names: Any) -> int:
    """Add each room name not already listed (e.g. the values of the old
    ``admissions_interview_rooms.json`` side file). Returns how many were
    added."""
    added = 0
    have = {r.name.lower() for r in list_rooms(active_only=False)}
    for n in names or ():
        n = (str(n or "")).strip()
        if not n or n.upper() == "TBC" or n.lower() in have:
            continue
        add_room(n)
        have.add(n.lower())
        added += 1
    return added


# ── Slots ──────────────────────────────────────────────────────────

_SLOT_SQL = """
SELECT s.*, r.name AS room_name,
       (SELECT COUNT(*) FROM admissions_interview_bookings b
         WHERE b.slot_id = s.slot_id AND b.status IN ('Booked', 'Attended',
               'No-show')) AS booked
  FROM admissions_interview_slots s
  LEFT JOIN admissions_interview_rooms r ON r.room_id = s.room_id
"""


def _slot(r: Any) -> Slot:
    try:
        panel = json.loads(r["panel_json"] or "[]")
    except ValueError:
        panel = []
    return Slot(slot_id=r["slot_id"], slot_date=r["slot_date"],
                start_time=r["start_time"], end_time=r["end_time"],
                room_id=r["room_id"], room_name=r["room_name"],
                panel=list(panel), capacity=r["capacity"], notes=r["notes"],
                status=r["status"], booked=r["booked"] or 0,
                cancel_reason=r["cancel_reason"])


def get_slot(slot_id: int) -> Slot | None:
    init_db()
    _guard.require("interview slots")
    with _adm._connect() as conn:
        r = conn.execute(_SLOT_SQL + " WHERE s.slot_id = ?",
                         (slot_id,)).fetchone()
    return _slot(r) if r else None


def list_slots(*, date_from: str | None = None, date_to: str | None = None,
               include_cancelled: bool = False,
               available_only: bool = False) -> list[Slot]:
    """Slots in date/time order. ``available_only`` keeps open, future
    slots with a place left."""
    init_db()
    _guard.require("interview slots")
    clauses, args = [], []
    if date_from:
        clauses.append("s.slot_date >= ?")
        args.append(_adm._validate_date(date_from, "From"))
    if date_to:
        clauses.append("s.slot_date <= ?")
        args.append(_adm._validate_date(date_to, "To"))
    if not include_cancelled or available_only:
        clauses.append("s.status = 'Open'")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _adm._connect() as conn:
        rows = conn.execute(_SLOT_SQL + where + " ORDER BY s.slot_date, "
                            "s.start_time, s.slot_id", args).fetchall()
    out = [_slot(r) for r in rows]
    if available_only:
        now = _now()
        out = [s for s in out if not s.is_full
               and _starts(s.slot_date, s.start_time) > now]
    return out


def find_clashes(*, slot_date: str, start_time: str, end_time: str,
                 room_id: int | None, panel: list[str],
                 exclude_slot_id: int | None = None) -> ClashReport:
    """Room and panel clashes for a proposed slot: other open slots that
    overlap in time and share the room or a panel member, plus (for a
    room linked to room booking) that room's bookings, lessons and
    exams."""
    init_db()
    report = ClashReport()
    with _adm._connect() as conn:
        rows = conn.execute(
            _SLOT_SQL + " WHERE s.status = 'Open' AND s.slot_date = ? AND "
            "s.start_time < ? AND s.end_time > ? AND s.slot_id != ?",
            (slot_date, end_time, start_time, exclude_slot_id or -1)
        ).fetchall()
        room = conn.execute("SELECT * FROM admissions_interview_rooms "
                            "WHERE room_id = ?", (room_id,)).fetchone() \
            if room_id else None
    wanted = {p.lower() for p in panel}
    for r in rows:
        other = _slot(r)
        if room_id and other.room_id == room_id:
            report.room.append(f"{other.room_name} is used by slot "
                               f"#{other.slot_id} ({other.label})")
        shared = [p for p in other.panel if p.lower() in wanted]
        for p in shared:
            report.panel.append(f"{p} is on slot #{other.slot_id} "
                                f"({other.label})")
    if room is not None and room["resource_id"]:
        try:
            from education_system.systems.sixth_form.domain.academics.room_booking import (
                room_booking as _rb,
            )
            for b in _rb.find_clashes(resource_id=room["resource_id"],
                                      booking_date=slot_date,
                                      start_time=start_time,
                                      end_time=end_time):
                report.room.append(
                    f"{room['name']} is booked {b.start_time}–{b.end_time} "
                    f"({b.purpose})")
            for c in _rb.external_clashes(resource_id=room["resource_id"],
                                          booking_date=slot_date,
                                          start_time=start_time,
                                          end_time=end_time):
                report.room.append(f"{room['name']}: {c}")
        except Exception:  # noqa: BLE001 — the slot checks above still apply
            logger.warning("Room-booking clash check failed", exc_info=True)
    return report


def _slot_values(data: dict[str, Any]) -> dict[str, Any]:
    day = _adm._validate_date(data.get("slot_date"), "Slot date",
                              required=True)
    start = _clean_time(data.get("start_time"), "Start time")
    end = _clean_time(data.get("end_time"), "End time")
    if end <= start:
        raise ValidationError("End time must be after the start time")
    if _starts(day, start) <= _now():
        raise ValidationError("An interview slot cannot be in the past")
    try:
        cap = int(data.get("capacity") or 1)
    except (TypeError, ValueError):
        raise ValidationError("Capacity must be a whole number") from None
    if cap < 1:
        raise ValidationError("Capacity must be at least 1")
    room_id = data.get("room_id")
    if room_id in ("", None):
        room_id = None
    else:
        room = get_room(int(room_id))
        if room is None or not room.active:
            raise ValidationError(f"No active interview room #{room_id}")
        room_id = room.room_id
        if room.capacity is not None and cap > room.capacity:
            raise ValidationError(
                f"{room.name} holds {room.capacity}; the slot capacity is "
                f"{cap}")
    panel = _clean_panel(data.get("panel"))
    if not panel:
        raise ValidationError("Name at least one panel member")
    return {"slot_date": day, "start_time": start, "end_time": end,
            "room_id": room_id, "panel": panel, "capacity": cap,
            "notes": (data.get("notes") or "").strip() or None}


def create_slot(data: dict[str, Any]) -> Slot:
    """Create an interview slot. ``data``: slot_date, start_time,
    end_time, room_id (optional), panel (list or comma-separated),
    capacity (default 1), notes."""
    init_db()
    _guard.require("creating interview slots")
    v = _slot_values(data)
    clashes = find_clashes(slot_date=v["slot_date"], start_time=v["start_time"],
                           end_time=v["end_time"], room_id=v["room_id"],
                           panel=v["panel"])
    if clashes:
        raise ValidationError("Clash: " + clashes.message())
    with _adm._connect() as conn:
        cur = conn.execute(
            "INSERT INTO admissions_interview_slots (slot_date, start_time, "
            "end_time, room_id, panel_json, capacity, notes, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (v["slot_date"], v["start_time"], v["end_time"], v["room_id"],
             json.dumps(v["panel"]), v["capacity"], v["notes"],
             _guard.actor()))
        conn.commit()
        sid = cur.lastrowid
    out = get_slot(sid)
    assert out is not None
    logger.info("Interview slot #%d created (%s)", sid, out.label)
    return out


def update_slot(slot_id: int, data: dict[str, Any]) -> Slot:
    """Change an open, future slot. The capacity cannot drop below the
    applicants already booked. Booked applicants keep their booking; a
    date change is copied onto each applicant."""
    init_db()
    _guard.require("changing interview slots")
    old = get_slot(slot_id)
    if old is None:
        raise ValidationError(f"No interview slot #{slot_id}")
    if old.status != "Open":
        raise ValidationError(f"Slot #{slot_id} is {old.status}")
    merged = {"slot_date": old.slot_date, "start_time": old.start_time,
              "end_time": old.end_time, "room_id": old.room_id,
              "panel": old.panel, "capacity": old.capacity,
              "notes": old.notes, **data}
    v = _slot_values(merged)
    if v["capacity"] < old.booked:
        raise ValidationError(
            f"{old.booked} applicant(s) are booked; capacity cannot be "
            f"{v['capacity']}")
    clashes = find_clashes(slot_date=v["slot_date"], start_time=v["start_time"],
                           end_time=v["end_time"], room_id=v["room_id"],
                           panel=v["panel"], exclude_slot_id=slot_id)
    if clashes:
        raise ValidationError("Clash: " + clashes.message())
    with _adm._connect() as conn:
        conn.execute(
            "UPDATE admissions_interview_slots SET slot_date = ?, "
            "start_time = ?, end_time = ?, room_id = ?, panel_json = ?, "
            "capacity = ?, notes = ? WHERE slot_id = ?",
            (v["slot_date"], v["start_time"], v["end_time"], v["room_id"],
             json.dumps(v["panel"]), v["capacity"], v["notes"], slot_id))
        conn.commit()
    out = get_slot(slot_id)
    assert out is not None
    if (out.slot_date, out.panel) != (old.slot_date, old.panel):
        for b in slot_bookings(slot_id):
            with _drive():
                _adm.reschedule_interview(
                    b.applicant_id, new_date=out.slot_date,
                    interviewer=out.panel_label,
                    reason=f"slot #{slot_id} changed to {out.label}")
    return out


def cancel_slot(slot_id: int, *, reason: str) -> list[str]:
    """Cancel a slot and every booking in it (each applicant's interview
    is cancelled with the reason). Returns the applicants affected."""
    init_db()
    _guard.require("cancelling interview slots")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason is required")
    s = get_slot(slot_id)
    if s is None:
        raise ValidationError(f"No interview slot #{slot_id}")
    if s.status != "Open":
        return []
    affected = []
    for b in slot_bookings(slot_id):
        cancel_booking(b.booking_id, reason=f"slot cancelled: {reason}")
        affected.append(b.applicant_id)
    with _adm._connect() as conn:
        conn.execute(
            "UPDATE admissions_interview_slots SET status = 'Cancelled', "
            "cancelled_by = ?, cancelled_at = datetime('now'), "
            "cancel_reason = ? WHERE slot_id = ?",
            (_guard.actor(), reason, slot_id))
        conn.commit()
    return affected


# ── Bookings ───────────────────────────────────────────────────────

def _booking(r: Any, slot: Slot | None = None) -> Booking:
    return Booking(booking_id=r["booking_id"], slot_id=r["slot_id"],
                   applicant_id=r["applicant_id"], status=r["status"],
                   booked_by=r["booked_by"], booked_at=r["booked_at"],
                   ended_by=r["ended_by"], ended_at=r["ended_at"],
                   reason=r["reason"], replaces_id=r["replaces_id"],
                   slot=slot)


def get_booking(booking_id: int) -> Booking | None:
    init_db()
    _guard.require("interview bookings")
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_interview_bookings "
                         "WHERE booking_id = ?", (booking_id,)).fetchone()
    return _booking(r, get_slot(r["slot_id"])) if r else None


def slot_bookings(slot_id: int, *, active_only: bool = True) -> list[Booking]:
    init_db()
    _guard.require("interview bookings")
    sql = "SELECT * FROM admissions_interview_bookings WHERE slot_id = ?"
    if active_only:
        sql += f" AND status = '{ACTIVE_BOOKING}'"
    with _adm._connect() as conn:
        rows = conn.execute(sql + " ORDER BY booking_id", (slot_id,)).fetchall()
    return [_booking(r) for r in rows]


def active_booking(applicant_id: str) -> Booking | None:
    """The applicant's current (Booked) booking, with its slot."""
    init_db()
    with _adm._connect() as conn:
        r = conn.execute(
            "SELECT * FROM admissions_interview_bookings WHERE applicant_id = ? "
            "AND status = ? ORDER BY booking_id DESC LIMIT 1",
            (applicant_id, ACTIVE_BOOKING)).fetchone()
        if r is None:
            return None
        s = conn.execute(_SLOT_SQL + " WHERE s.slot_id = ?",
                         (r["slot_id"],)).fetchone()
    return _booking(r, _slot(s) if s else None)


def booking_history(applicant_id: str) -> list[Booking]:
    """Every booking the applicant has had, newest first (cancelled and
    rescheduled ones included)."""
    init_db()
    _guard.require("interview bookings")
    with _adm._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_interview_bookings WHERE applicant_id = ? "
            "ORDER BY booking_id DESC", (applicant_id,)).fetchall()
    return [_booking(r, get_slot(r["slot_id"])) for r in rows]


def _bookable(applicant_id: str, slot_id: int, *,
              moving_from: int | None = None) -> tuple[Any, Slot]:
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.is_archived:
        raise ValidationError(f"{applicant_id} is archived")
    s = get_slot(slot_id)
    if s is None:
        raise ValidationError(f"No interview slot #{slot_id}")
    if s.status != "Open":
        raise ValidationError(f"Slot #{slot_id} is {s.status.lower()}")
    if _starts(s.slot_date, s.start_time) <= _now():
        raise ValidationError(f"Slot #{slot_id} ({s.label}) is in the past")
    if s.is_full:
        raise ValidationError(
            f"Slot #{slot_id} ({s.label}) is full ({s.capacity} place(s))")
    current = active_booking(applicant_id)
    if current is not None and current.booking_id != moving_from:
        where = current.slot.label if current.slot else f"slot #{current.slot_id}"
        raise ValidationError(
            f"{a.full_name} is already booked for {where}; reschedule or "
            "cancel that booking instead")
    return a, s


def book(applicant_id: str, slot_id: int) -> Booking:
    """Book the applicant into a slot and schedule their interview."""
    init_db()
    _guard.require("booking interviews")
    a, s = _bookable(applicant_id, slot_id)
    from education_system.systems.sixth_form.domain.admissions import (
        status_rules,
    )
    try:
        status_rules.check(a.status, "Interview Scheduled")
    except status_rules.TransitionError as e:
        raise ValidationError(str(e)) from None
    with _adm._connect() as conn:
        cur = conn.execute(
            "INSERT INTO admissions_interview_bookings (slot_id, applicant_id, "
            "booked_by) VALUES (?, ?, ?)",
            (slot_id, applicant_id, _guard.actor()))
        conn.commit()
        bid = cur.lastrowid
    try:
        with _drive():
            _adm.schedule_interview(applicant_id, interview_date=s.slot_date,
                                    interviewer=s.panel_label)
    except Exception:
        # The applicant's status refused the interview: no booking stays.
        with _adm._connect() as conn:
            conn.execute("DELETE FROM admissions_interview_bookings "
                         "WHERE booking_id = ?", (bid,))
            conn.commit()
        raise
    with _adm._connect() as conn:
        _adm._log_event(conn, applicant_id,
                        f"Interview booked: slot #{slot_id} ({s.label}), "
                        f"panel {s.panel_label}", kind="interview")
        conn.commit()
    out = get_booking(bid)
    assert out is not None
    return out


def reschedule(applicant_id: str, new_slot_id: int, *,
               reason: str | None = None) -> Booking:
    """Move the applicant's booking to another slot. The old booking is
    kept as Rescheduled; the new one points back to it."""
    init_db()
    _guard.require("rescheduling interviews")
    current = active_booking(applicant_id)
    if current is None:
        raise ValidationError(f"{applicant_id} has no booked interview slot")
    if current.slot_id == new_slot_id:
        raise ValidationError("That is the slot already booked")
    _a, s = _bookable(applicant_id, new_slot_id,
                      moving_from=current.booking_id)
    who = _guard.actor()
    with _adm._connect() as conn:
        conn.execute(
            "UPDATE admissions_interview_bookings SET status = 'Rescheduled', "
            "ended_by = ?, ended_at = datetime('now'), reason = ? "
            "WHERE booking_id = ?",
            (who, (reason or "").strip() or None, current.booking_id))
        cur = conn.execute(
            "INSERT INTO admissions_interview_bookings (slot_id, applicant_id, "
            "booked_by, replaces_id) VALUES (?, ?, ?, ?)",
            (new_slot_id, applicant_id, who, current.booking_id))
        conn.commit()
        bid = cur.lastrowid
    with _drive():
        _adm.reschedule_interview(
            applicant_id, new_date=s.slot_date, interviewer=s.panel_label,
            reason=((reason or "").strip() or None))
    with _adm._connect() as conn:
        _adm._log_event(conn, applicant_id,
                        f"Interview moved to slot #{new_slot_id} ({s.label})",
                        kind="interview")
        conn.commit()
    out = get_booking(bid)
    assert out is not None
    return out


def cancel_booking(booking_id: int, *, reason: str | None = None) -> Booking:
    """Cancel a booking (kept as Cancelled) and the applicant's interview."""
    init_db()
    _guard.require("cancelling interviews")
    b = get_booking(booking_id)
    if b is None:
        raise ValidationError(f"No interview booking #{booking_id}")
    if b.status != ACTIVE_BOOKING:
        raise ValidationError(f"Booking #{booking_id} is {b.status}")
    with _adm._connect() as conn:
        conn.execute(
            "UPDATE admissions_interview_bookings SET status = 'Cancelled', "
            "ended_by = ?, ended_at = datetime('now'), reason = ? "
            "WHERE booking_id = ?",
            (_guard.actor(), (reason or "").strip() or None, booking_id))
        conn.commit()
    a = _adm.get_applicant(b.applicant_id)
    if a is not None and a.status == "Interview Scheduled":
        with _drive():
            _adm.cancel_interview(b.applicant_id, reason=reason)
    out = get_booking(booking_id)
    assert out is not None
    return out


def close_booking(applicant_id: str, outcome: str) -> Booking | None:
    """Mark the applicant's booking Attended or No-show (used by
    :func:`admissions.record_interview` / :func:`admissions.mark_no_show`).
    Returns None when the applicant has no booking."""
    if outcome not in ("Attended", "No-show"):
        raise ValidationError("Outcome must be Attended or No-show")
    b = active_booking(applicant_id)
    if b is None:
        return None
    with _adm._connect() as conn:
        conn.execute(
            "UPDATE admissions_interview_bookings SET status = ?, ended_by = ?, "
            "ended_at = datetime('now') WHERE booking_id = ?",
            (outcome, _guard.actor(), b.booking_id))
        conn.commit()
    return get_booking(b.booking_id)


def day_sheet(slot_date: str) -> list[tuple[Slot, list[Booking]]]:
    """Each open slot on a day with its booked applicants (for the panel
    and reception)."""
    return [(s, slot_bookings(s.slot_id))
            for s in list_slots(date_from=slot_date, date_to=slot_date)]


#: Applicant tables this module owns (merge and erasure walk them).
OWNED_TABLES: tuple[str, ...] = ("admissions_interview_bookings",)
