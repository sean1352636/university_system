"""Room & Resource Booking data layer.

Two tables:

* ``rb_resources`` — bookable rooms / AV equipment / sports kit, with
  a capacity, location, and notes. Names are unique
  (case-insensitive).
* ``rb_bookings`` — one row per booking, with date, start/end time,
  who booked, purpose, attendee count, status (Pending / Confirmed /
  Cancelled) and notes.

Clash detection: ``create_booking`` and ``update_booking`` refuse to
double-book a non-Cancelled resource within an overlapping
(date, start_time, end_time) window. Use ``find_clashes`` to preview
clashes for a proposed booking before saving.

Cascade: deleting a resource is blocked while bookings reference it
(matching the work-experience pattern).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.ROOM_BOOKING_DB

RESOURCE_TYPES: tuple[str, ...] = (
    "Room", "AV Equipment", "Sports Facility", "Lab",
    "Meeting Room", "Hall", "Other",
)
DEFAULT_RESOURCE_TYPE: str = "Room"

BOOKING_STATUSES: tuple[str, ...] = (
    "Pending", "Confirmed", "Cancelled",
)
DEFAULT_BOOKING_STATUS: str = "Confirmed"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rb_resources (
    resource_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    resource_type  TEXT NOT NULL DEFAULT 'Room',
    capacity       INTEGER,
    location       TEXT,
    notes          TEXT,
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_rb_resources_name
    ON rb_resources(LOWER(name));
CREATE INDEX IF NOT EXISTS idx_rb_resources_type
    ON rb_resources(resource_type);

CREATE TABLE IF NOT EXISTS rb_bookings (
    booking_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id     INTEGER NOT NULL,
    booking_date    TEXT NOT NULL,
    start_time      TEXT NOT NULL,
    end_time        TEXT NOT NULL,
    booked_by       TEXT NOT NULL,
    purpose         TEXT NOT NULL,
    attendee_count  INTEGER,
    status          TEXT NOT NULL DEFAULT 'Confirmed',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (resource_id) REFERENCES rb_resources(resource_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_rb_book_resource ON rb_bookings(resource_id);
CREATE INDEX IF NOT EXISTS idx_rb_book_date     ON rb_bookings(booking_date);
CREATE INDEX IF NOT EXISTS idx_rb_book_status   ON rb_bookings(status);
"""


@dataclass
class Resource:
    resource_id: int
    name: str
    resource_type: str
    capacity: int | None
    location: str | None
    notes: str | None
    active: bool
    created_at: str
    updated_at: str


@dataclass
class Booking:
    booking_id: int
    resource_id: int
    booking_date: str
    start_time: str
    end_time: str
    booked_by: str
    purpose: str
    attendee_count: int | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class BookingRow:
    booking: Booking
    resource_name: str
    resource_type: str


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
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Room-booking schema ready at %s", DB_PATH)
    _DB_READY = True


def _row_resource(r: sqlite3.Row) -> Resource:
    return Resource(
        resource_id=r["resource_id"], name=r["name"],
        resource_type=r["resource_type"],
        capacity=r["capacity"], location=r["location"],
        notes=r["notes"], active=bool(r["active"]),
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_booking(r: sqlite3.Row) -> Booking:
    return Booking(
        booking_id=r["booking_id"], resource_id=r["resource_id"],
        booking_date=r["booking_date"],
        start_time=r["start_time"], end_time=r["end_time"],
        booked_by=r["booked_by"], purpose=r["purpose"],
        attendee_count=r["attendee_count"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid room-booking input."""


class ClashError(ValidationError):
    """Raised when a booking overlaps existing non-cancelled bookings."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str) -> str:
    s = str(_require(value, label)).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real calendar date") from None
    return s


def _validate_time(value: Any, label: str) -> str:
    s = str(_require(value, label)).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24h)")
    h, m = s.split(":")
    try:
        ih, im = int(h), int(m)
    except ValueError:
        raise ValidationError(f"{label} must be HH:MM (24h)") from None
    if not (0 <= ih <= 23 and 0 <= im <= 59):
        raise ValidationError(f"{label} is not a valid time")
    return f"{ih:02d}:{im:02d}"


def _validate_resource_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(data.get("name"), "Resource name").strip()
    rtype = (data.get("resource_type") or DEFAULT_RESOURCE_TYPE).strip()
    if rtype not in RESOURCE_TYPES:
        raise ValidationError(
            f"Resource type must be one of: {', '.join(RESOURCE_TYPES)}")
    out["resource_type"] = rtype

    cap = data.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            c = int(cap)
        except (TypeError, ValueError):
            raise ValidationError(
                "Capacity must be a whole number") from None
        if c < 0 or c > 100000:
            raise ValidationError("Capacity must be between 0 and 100000")
        out["capacity"] = c

    active = data.get("active", True)
    out["active"] = 1 if active in (True, 1, "1", "y", "yes") else 0

    out["location"] = (data.get("location") or "").strip() or None
    out["notes"]    = (data.get("notes") or "").strip() or None
    return out


def _validate_booking_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    rid = data.get("resource_id")
    if rid in (None, ""):
        raise ValidationError("Resource is required")
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        raise ValidationError("Resource id must be a number") from None
    resource = get_resource(rid)
    if resource is None:
        raise ValidationError(f"No resource with id {rid}")
    if not resource.active:
        raise ValidationError(
            f"Resource {resource.name!r} is inactive — reactivate "
            "it before booking.")
    out["resource_id"] = rid

    out["booking_date"] = _validate_date(
        data.get("booking_date"), "Booking date")
    start = _validate_time(data.get("start_time"), "Start time")
    end   = _validate_time(data.get("end_time"), "End time")
    if start >= end:
        raise ValidationError("End time must be after start time")
    out["start_time"] = start
    out["end_time"]   = end

    out["booked_by"] = _require(data.get("booked_by"),
                                  "Booked by").strip()
    out["purpose"]   = _require(data.get("purpose"),
                                  "Purpose").strip()

    att = data.get("attendee_count")
    if att in (None, ""):
        out["attendee_count"] = None
    else:
        try:
            n = int(att)
        except (TypeError, ValueError):
            raise ValidationError(
                "Attendee count must be a whole number") from None
        if n < 0 or n > 100000:
            raise ValidationError(
                "Attendee count must be between 0 and 100000")
        out["attendee_count"] = n
        if (resource.capacity is not None
                and n > resource.capacity):
            logger.warning(
                "Booking attendees (%d) exceeds %s capacity (%d)",
                n, resource.name, resource.capacity)

    status = (data.get("status") or DEFAULT_BOOKING_STATUS).strip()
    if status not in BOOKING_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BOOKING_STATUSES)}")
    out["status"] = status

    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Clash detection ──────────────────────────────────────────────

def find_clashes(
    *,
    resource_id: int,
    booking_date: str,
    start_time: str,
    end_time: str,
    exclude_booking_id: int | None = None,
) -> list[Booking]:
    """Return non-cancelled bookings for ``resource_id`` on
    ``booking_date`` whose times overlap the proposed window.
    """
    init_db()
    sql = (
        "SELECT * FROM rb_bookings "
        "WHERE resource_id = ? AND booking_date = ? "
        "  AND status != 'Cancelled' "
        "  AND start_time < ? AND end_time > ?"
    )
    args: list[Any] = [resource_id, booking_date, end_time, start_time]
    if exclude_booking_id is not None:
        sql += " AND booking_id != ?"
        args.append(exclude_booking_id)
    with _connect() as conn:
        return [_row_booking(r)
                for r in conn.execute(sql, args).fetchall()]


# ── Resource CRUD ────────────────────────────────────────────────

def create_resource(data: dict[str, Any]) -> Resource:
    init_db()
    try:
        p = _validate_resource_payload(data)
    except ValidationError as e:
        logger.warning("create_resource validation failed: %s", e)
        raise
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO rb_resources
                       (name, resource_type, capacity, location,
                        notes, active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["name"], p["resource_type"], p["capacity"],
                 p["location"], p["notes"], p["active"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"Resource named {p['name']!r} already exists") from None
        logger.exception("create_resource DB error")
        raise
    out = get_resource(new_id)
    assert out is not None
    logger.info("Created resource #%d %s (%s)",
                new_id, p["name"], p["resource_type"])
    return out


def get_resource(resource_id: int) -> Resource | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM rb_resources WHERE resource_id = ?",
            (resource_id,),
        ).fetchone()
        return _row_resource(r) if r else None


def list_resources(
    *,
    resource_type: str | None = None,
    name_like: str | None = None,
    active_only: bool = False,
) -> list[Resource]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if resource_type:
        if resource_type not in RESOURCE_TYPES:
            raise ValidationError(
                f"Resource type must be one of: {', '.join(RESOURCE_TYPES)}")
        clauses.append("resource_type = ?")
        args.append(resource_type)
    if name_like:
        clauses.append("name LIKE ?")
        args.append(f"%{name_like.strip()}%")
    if active_only:
        clauses.append("active = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM rb_resources {where} "
           "ORDER BY name COLLATE NOCASE")
    with _connect() as conn:
        return [_row_resource(r)
                for r in conn.execute(sql, args).fetchall()]


def update_resource(resource_id: int, data: dict[str, Any]) -> Resource:
    init_db()
    existing = get_resource(resource_id)
    if existing is None:
        raise ValidationError(f"No resource with id {resource_id}")
    p = _validate_resource_payload({
        "name":          data.get("name", existing.name),
        "resource_type": data.get("resource_type", existing.resource_type),
        "capacity":      data.get("capacity", existing.capacity),
        "location":      data.get("location", existing.location),
        "notes":         data.get("notes", existing.notes),
        "active":        data.get("active", existing.active),
    })
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE rb_resources SET
                       name = ?, resource_type = ?, capacity = ?,
                       location = ?, notes = ?, active = ?,
                       updated_at = datetime('now')
                   WHERE resource_id = ?""",
                (p["name"], p["resource_type"], p["capacity"],
                 p["location"], p["notes"], p["active"], resource_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"Resource named {p['name']!r} already exists") from None
        raise
    out = get_resource(resource_id)
    assert out is not None
    logger.info("Updated resource #%d (%s, active=%s)",
                resource_id, out.name, out.active)
    return out


def delete_resource(resource_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM rb_resources WHERE resource_id = ?",
                (resource_id,),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValidationError(
            "Cannot delete resource: bookings still reference it. "
            "Cancel or reassign those bookings first, or mark the "
            "resource inactive.") from None
    if cur.rowcount:
        logger.info("Deleted resource #%d", resource_id)
        return True
    return False


# ── Booking CRUD ─────────────────────────────────────────────────

def create_booking(data: dict[str, Any],
                    *, ignore_clashes: bool = False) -> Booking:
    init_db()
    p = _validate_booking_payload(data)
    if not ignore_clashes and p["status"] != "Cancelled":
        clashes = find_clashes(
            resource_id=p["resource_id"],
            booking_date=p["booking_date"],
            start_time=p["start_time"],
            end_time=p["end_time"],
        )
        if clashes:
            resource = get_resource(p["resource_id"])
            rname = resource.name if resource else f"#{p['resource_id']}"
            ids = ", ".join(f"#{b.booking_id} "
                              f"{b.start_time}–{b.end_time}"
                              for b in clashes)
            raise ClashError(
                f"{rname} is already booked on {p['booking_date']} "
                f"during that window: {ids}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO rb_bookings
                   (resource_id, booking_date, start_time, end_time,
                    booked_by, purpose, attendee_count, status, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["resource_id"], p["booking_date"],
             p["start_time"], p["end_time"], p["booked_by"],
             p["purpose"], p["attendee_count"], p["status"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_booking(new_id)
    assert out is not None
    logger.info(
        "Created booking #%d: resource#%d %s %s–%s by %s (%s)",
        new_id, p["resource_id"], p["booking_date"],
        p["start_time"], p["end_time"], p["booked_by"], p["status"],
    )
    return out


def get_booking(booking_id: int) -> Booking | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM rb_bookings WHERE booking_id = ?",
            (booking_id,),
        ).fetchone()
        return _row_booking(r) if r else None


def list_bookings(
    *,
    resource_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    booked_by_like: str | None = None,
) -> list[Booking]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if resource_id is not None:
        clauses.append("resource_id = ?")
        args.append(resource_id)
    if status:
        if status not in BOOKING_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(BOOKING_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if date_from:
        clauses.append("booking_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("booking_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if booked_by_like:
        clauses.append("booked_by LIKE ?")
        args.append(f"%{booked_by_like.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM rb_bookings {where} "
           "ORDER BY booking_date DESC, start_time ASC, booking_id DESC")
    with _connect() as conn:
        return [_row_booking(r)
                for r in conn.execute(sql, args).fetchall()]


def list_bookings_with_detail(**kwargs) -> list[BookingRow]:
    rows = list_bookings(**kwargs)
    if not rows:
        return []
    resources = {r.resource_id: r for r in list_resources()}
    out: list[BookingRow] = []
    for b in rows:
        res = resources.get(b.resource_id)
        out.append(BookingRow(
            booking=b,
            resource_name=(res.name if res else "(unknown)"),
            resource_type=(res.resource_type if res else "?"),
        ))
    return out


def update_booking(booking_id: int, data: dict[str, Any],
                    *, ignore_clashes: bool = False) -> Booking:
    init_db()
    existing = get_booking(booking_id)
    if existing is None:
        raise ValidationError(f"No booking with id {booking_id}")
    p = _validate_booking_payload({
        "resource_id":     data.get("resource_id", existing.resource_id),
        "booking_date":    data.get("booking_date", existing.booking_date),
        "start_time":      data.get("start_time", existing.start_time),
        "end_time":        data.get("end_time", existing.end_time),
        "booked_by":       data.get("booked_by", existing.booked_by),
        "purpose":         data.get("purpose", existing.purpose),
        "attendee_count":  data.get("attendee_count",
                                      existing.attendee_count),
        "status":          data.get("status", existing.status),
        "notes":           data.get("notes", existing.notes),
    })
    if not ignore_clashes and p["status"] != "Cancelled":
        clashes = find_clashes(
            resource_id=p["resource_id"],
            booking_date=p["booking_date"],
            start_time=p["start_time"],
            end_time=p["end_time"],
            exclude_booking_id=booking_id,
        )
        if clashes:
            resource = get_resource(p["resource_id"])
            rname = resource.name if resource else f"#{p['resource_id']}"
            ids = ", ".join(f"#{b.booking_id} "
                              f"{b.start_time}–{b.end_time}"
                              for b in clashes)
            raise ClashError(
                f"{rname} is already booked on {p['booking_date']} "
                f"during that window: {ids}")
    with _connect() as conn:
        conn.execute(
            """UPDATE rb_bookings SET
                   resource_id = ?, booking_date = ?,
                   start_time = ?, end_time = ?, booked_by = ?,
                   purpose = ?, attendee_count = ?, status = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE booking_id = ?""",
            (p["resource_id"], p["booking_date"],
             p["start_time"], p["end_time"], p["booked_by"],
             p["purpose"], p["attendee_count"], p["status"],
             p["notes"], booking_id),
        )
        conn.commit()
    out = get_booking(booking_id)
    assert out is not None
    logger.info(
        "Updated booking #%d (status=%s, %s %s–%s)",
        booking_id, out.status, out.booking_date,
        out.start_time, out.end_time,
    )
    return out


def cancel_booking(booking_id: int) -> Booking:
    return update_booking(booking_id, {"status": "Cancelled"},
                          ignore_clashes=True)


def delete_booking(booking_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM rb_bookings WHERE booking_id = ?",
            (booking_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted booking #%d", booking_id)
            return True
        return False


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class RoomBookingSummary:
    total_resources: int
    active_resources: int
    total_bookings: int
    by_status: dict[str, int]
    by_resource_type: dict[str, int]
    upcoming_bookings: int     # confirmed/pending within next 14 days
    bookings_today: int


def summary(*, upcoming_window_days: int = 14) -> RoomBookingSummary:
    init_db()
    today = _dt.date.today()
    today_iso = today.isoformat()
    upcoming_cutoff = (today + _dt.timedelta(days=upcoming_window_days)
                       ).isoformat()

    resources = list_resources()
    active = sum(1 for r in resources if r.active)
    by_type = {t: 0 for t in RESOURCE_TYPES}
    for r in resources:
        by_type[r.resource_type] = by_type.get(r.resource_type, 0) + 1

    bookings = list_bookings()
    by_status = {s: 0 for s in BOOKING_STATUSES}
    upcoming = 0
    today_n = 0
    for b in bookings:
        by_status[b.status] = by_status.get(b.status, 0) + 1
        if (b.status != "Cancelled"
                and today_iso <= b.booking_date <= upcoming_cutoff):
            upcoming += 1
        if b.booking_date == today_iso and b.status != "Cancelled":
            today_n += 1

    return RoomBookingSummary(
        total_resources=len(resources),
        active_resources=active,
        total_bookings=len(bookings),
        by_status=by_status,
        by_resource_type=by_type,
        upcoming_bookings=upcoming,
        bookings_today=today_n,
    )
