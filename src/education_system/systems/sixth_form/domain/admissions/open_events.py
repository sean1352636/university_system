"""Open events — open evenings, taster days and their bookings.

``admissions_open_events`` holds the events (date, time, venue,
capacity). ``admissions_event_bookings`` holds one row per booking: who
booked (a prospective student, or a parent/carer booking for one), their
current school, the subjects they are interested in and the party size.

After the event staff mark attendance, send follow-ups to attendees who
have not yet applied, and turn a booking into an application — creating
the applicant (source "Open Evening") or, when the dedupe finds them
already, linking the booking to the existing applicant. Conversion rates
per event come from those links.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

EVENT_TYPES: tuple[str, ...] = (
    "Open Evening", "Open Morning", "Taster Day", "Subject Fair",
    "Online Event", "Other",
)
EVENT_STATUSES: tuple[str, ...] = ("Scheduled", "Completed", "Cancelled")
FOLLOW_UP_STATUSES: tuple[str, ...] = (
    "None", "Sent", "Applied", "Not interested",
)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_open_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    event_type   TEXT NOT NULL DEFAULT 'Open Evening',
    event_date   TEXT NOT NULL,
    start_time   TEXT,
    end_time     TEXT,
    venue        TEXT,
    capacity     INTEGER,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'Scheduled',
    created_by   TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_adm_oe_date ON admissions_open_events(event_date);

CREATE TABLE IF NOT EXISTS admissions_event_bookings (
    booking_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id          INTEGER NOT NULL,
    attendee_name     TEXT NOT NULL,
    is_parent         INTEGER NOT NULL DEFAULT 0,
    student_name      TEXT,
    email             TEXT,
    phone             TEXT,
    current_school    TEXT,
    year_group        TEXT,
    interests         TEXT,
    party_size        INTEGER NOT NULL DEFAULT 1,
    booked_at         TEXT DEFAULT (datetime('now')),
    attended          INTEGER,
    attendance_marked_at TEXT,
    follow_up_status  TEXT NOT NULL DEFAULT 'None',
    follow_up_at      TEXT,
    applicant_id      TEXT,
    notes             TEXT,
    FOREIGN KEY (event_id) REFERENCES admissions_open_events(event_id)
        ON DELETE CASCADE,
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_adm_bk_event ON admissions_event_bookings(event_id);
CREATE INDEX IF NOT EXISTS idx_adm_bk_app   ON admissions_event_bookings(applicant_id);
"""


@dataclass
class OpenEvent:
    event_id: int
    title: str
    event_type: str
    event_date: str
    start_time: str | None
    end_time: str | None
    venue: str | None
    capacity: int | None
    description: str | None
    status: str
    created_by: str | None
    created_at: str | None

    @property
    def label(self) -> str:
        t = f" {self.start_time}" if self.start_time else ""
        return f"{self.event_date}{t} — {self.title}"


@dataclass
class Booking:
    booking_id: int
    event_id: int
    attendee_name: str
    is_parent: bool
    student_name: str | None
    email: str | None
    phone: str | None
    current_school: str | None
    year_group: str | None
    interests: str | None
    party_size: int
    booked_at: str | None
    attended: bool | None
    attendance_marked_at: str | None
    follow_up_status: str
    follow_up_at: str | None
    applicant_id: str | None
    notes: str | None

    @property
    def prospective_name(self) -> str:
        """The prospective student's name (not the parent's)."""
        return (self.student_name if self.is_parent and self.student_name
                else self.attendee_name)

    @property
    def interest_list(self) -> list[str]:
        return [s.strip() for s in (self.interests or "").split(",")
                if s.strip()]


@dataclass
class EventStats:
    event: OpenEvent
    bookings: int
    people: int
    attended: int
    no_shows: int
    unmarked: int
    applied: int
    follow_ups_sent: int

    @property
    def conversion(self) -> float:
        base = self.attended or self.bookings
        return round(100.0 * self.applied / base, 1) if base else 0.0


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    return _adm._connect()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _adm.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _row_event(r: db.Row) -> OpenEvent:
    return OpenEvent(**{k: r[k] for k in r.keys()})


def _row_booking(r: db.Row) -> Booking:
    d = {k: r[k] for k in r.keys()}
    d["is_parent"] = bool(d["is_parent"])
    d["attended"] = None if d["attended"] is None else bool(d["attended"])
    return Booking(**d)


def _text(value: Any, label: str, *, required: bool = False,
          max_len: int = 200) -> str | None:
    s = str(value).strip() if value not in (None, "") else ""
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if len(s) > max_len:
        raise ValidationError(f"{label} is too long (max {max_len})")
    return s


def _time(value: Any, label: str) -> str | None:
    s = _text(value, label, max_len=5)
    if s and not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM")
    return s


# ── Events ─────────────────────────────────────────────────────────

def _validate_event(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = _text(d.get("title"), "Title", required=True)
    et = (d.get("event_type") or "Open Evening").strip()
    if et not in EVENT_TYPES:
        raise ValidationError(f"Event type must be one of: {', '.join(EVENT_TYPES)}")
    out["event_type"] = et
    out["event_date"] = _adm._validate_date(d.get("event_date"), "Event date",
                                            required=True)
    out["start_time"] = _time(d.get("start_time"), "Start time")
    out["end_time"] = _time(d.get("end_time"), "End time")
    if out["start_time"] and out["end_time"] and \
            out["end_time"] <= out["start_time"]:
        raise ValidationError("End time must be after the start time")
    out["venue"] = _text(d.get("venue"), "Venue")
    cap = d.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            out["capacity"] = int(cap)
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a whole number") from None
        if out["capacity"] < 1:
            raise ValidationError("Capacity must be at least 1")
    out["description"] = _text(d.get("description"), "Description",
                               max_len=2000)
    st = (d.get("status") or "Scheduled").strip()
    if st not in EVENT_STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(EVENT_STATUSES)}")
    out["status"] = st
    return out


def create_event(d: dict[str, Any], *, created_by: str | None = None
                 ) -> OpenEvent:
    init_db()
    p = _validate_event(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO admissions_open_events
                   (title, event_type, event_date, start_time, end_time,
                    venue, capacity, description, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["title"], p["event_type"], p["event_date"], p["start_time"],
             p["end_time"], p["venue"], p["capacity"], p["description"],
             p["status"], created_by))
        conn.commit()
        eid = cur.lastrowid
    logger.info("Created open event #%d %s on %s", eid, p["title"],
                p["event_date"])
    out = get_event(eid)
    assert out is not None
    return out


def get_event(event_id: int) -> OpenEvent | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM admissions_open_events "
                         "WHERE event_id = ?", (int(event_id),)).fetchone()
    return _row_event(r) if r else None


def list_events(*, upcoming_only: bool = False,
                include_cancelled: bool = True) -> list[OpenEvent]:
    init_db()
    clauses, args = [], []
    if upcoming_only:
        clauses.append("event_date >= ?")
        args.append(_dt.date.today().isoformat())
    if not include_cancelled:
        clauses.append("status != 'Cancelled'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_event(r) for r in conn.execute(
            f"SELECT * FROM admissions_open_events {where} "
            "ORDER BY event_date DESC, start_time", args).fetchall()]


def update_event(event_id: int, d: dict[str, Any]) -> OpenEvent:
    e = get_event(event_id)
    if e is None:
        raise ValidationError(f"No open event #{event_id}")
    merged = {k: d.get(k, getattr(e, k)) for k in (
        "title", "event_type", "event_date", "start_time", "end_time",
        "venue", "capacity", "description", "status")}
    p = _validate_event(merged)
    if p["capacity"] is not None and p["capacity"] < places_taken(event_id):
        raise ValidationError(
            f"Capacity {p['capacity']} is below the {places_taken(event_id)} "
            "places already booked")
    with _connect() as conn:
        conn.execute(
            """UPDATE admissions_open_events SET title = ?, event_type = ?,
                   event_date = ?, start_time = ?, end_time = ?, venue = ?,
                   capacity = ?, description = ?, status = ?
               WHERE event_id = ?""",
            (p["title"], p["event_type"], p["event_date"], p["start_time"],
             p["end_time"], p["venue"], p["capacity"], p["description"],
             p["status"], event_id))
        conn.commit()
    out = get_event(event_id)
    assert out is not None
    return out


def cancel_event(event_id: int) -> OpenEvent:
    return update_event(event_id, {"status": "Cancelled"})


def delete_event(event_id: int) -> bool:
    """Delete an event and its bookings (only sensible for mistakes)."""
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM admissions_open_events "
                           "WHERE event_id = ?", (int(event_id),))
        conn.commit()
    return cur.rowcount > 0


# ── Bookings ───────────────────────────────────────────────────────

def places_taken(event_id: int) -> int:
    init_db()
    with _connect() as conn:
        return int(conn.execute(
            "SELECT COALESCE(SUM(party_size), 0) FROM admissions_event_bookings"
            " WHERE event_id = ?", (int(event_id),)).fetchone()[0])


def places_left(event_id: int) -> int | None:
    e = get_event(event_id)
    if e is None or e.capacity is None:
        return None
    return max(0, e.capacity - places_taken(event_id))


def _validate_booking(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["attendee_name"] = _text(d.get("attendee_name"), "Name",
                                 required=True, max_len=120)
    out["is_parent"] = 1 if d.get("is_parent") else 0
    out["student_name"] = _text(d.get("student_name"), "Student name",
                                max_len=120)
    if out["is_parent"] and not out["student_name"]:
        raise ValidationError("A parent/carer booking needs the student's name")
    out["email"] = _adm._validate_email(d.get("email"))
    out["phone"] = _adm._validate_phone(d.get("phone"))
    if not (out["email"] or out["phone"]):
        raise ValidationError("An email address or phone number is required")
    out["current_school"] = _text(d.get("current_school"), "Current school",
                                  max_len=120)
    out["year_group"] = _text(d.get("year_group"), "Year group", max_len=20)
    interests = d.get("interests")
    if isinstance(interests, (list, tuple)):
        interests = ", ".join(str(x).strip() for x in interests if str(x).strip())
    out["interests"] = _text(interests, "Interests", max_len=500)
    try:
        out["party_size"] = int(d.get("party_size") or 1)
    except (TypeError, ValueError):
        raise ValidationError("Party size must be a whole number") from None
    if not 1 <= out["party_size"] <= 10:
        raise ValidationError("Party size must be between 1 and 10")
    out["notes"] = _text(d.get("notes"), "Notes", max_len=1000)
    return out


def book(event_id: int, d: dict[str, Any]) -> Booking:
    """Book a place (or several) on an event, within capacity."""
    init_db()
    e = get_event(event_id)
    if e is None:
        raise ValidationError(f"No open event #{event_id}")
    if e.status != "Scheduled":
        raise ValidationError(f"Event is {e.status.lower()} — not taking bookings")
    p = _validate_booking(d)
    left = places_left(event_id)
    if left is not None and p["party_size"] > left:
        raise ValidationError(
            f"Only {left} place(s) left on {e.title}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO admissions_event_bookings
                   (event_id, attendee_name, is_parent, student_name, email,
                    phone, current_school, year_group, interests,
                    party_size, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, p["attendee_name"], p["is_parent"], p["student_name"],
             p["email"], p["phone"], p["current_school"], p["year_group"],
             p["interests"], p["party_size"], p["notes"]))
        conn.commit()
        bid = cur.lastrowid
    logger.info("Booking #%d on open event #%d", bid, event_id)
    out = get_booking(bid)
    assert out is not None
    return out


def get_booking(booking_id: int) -> Booking | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM admissions_event_bookings "
                         "WHERE booking_id = ?", (int(booking_id),)).fetchone()
    return _row_booking(r) if r else None


def list_bookings(event_id: int | None = None, *,
                  attended_only: bool = False,
                  not_applied_only: bool = False) -> list[Booking]:
    init_db()
    clauses, args = [], []
    if event_id is not None:
        clauses.append("event_id = ?")
        args.append(int(event_id))
    if attended_only:
        clauses.append("attended = 1")
    if not_applied_only:
        clauses.append("applicant_id IS NULL")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_booking(r) for r in conn.execute(
            f"SELECT * FROM admissions_event_bookings {where} "
            "ORDER BY attendee_name COLLATE NOCASE", args).fetchall()]


def bookings_for_applicant(applicant_id: str) -> list[Booking]:
    init_db()
    with _connect() as conn:
        return [_row_booking(r) for r in conn.execute(
            "SELECT * FROM admissions_event_bookings WHERE applicant_id = ?",
            (applicant_id,)).fetchall()]


def update_booking(booking_id: int, d: dict[str, Any]) -> Booking:
    b = get_booking(booking_id)
    if b is None:
        raise ValidationError(f"No booking #{booking_id}")
    merged = {k: d.get(k, getattr(b, k)) for k in (
        "attendee_name", "is_parent", "student_name", "email", "phone",
        "current_school", "year_group", "interests", "party_size", "notes")}
    p = _validate_booking(merged)
    left = places_left(b.event_id)
    if left is not None and p["party_size"] - b.party_size > left:
        raise ValidationError(f"Only {left} more place(s) available")
    with _connect() as conn:
        conn.execute(
            """UPDATE admissions_event_bookings SET attendee_name = ?,
                   is_parent = ?, student_name = ?, email = ?, phone = ?,
                   current_school = ?, year_group = ?, interests = ?,
                   party_size = ?, notes = ?
               WHERE booking_id = ?""",
            (p["attendee_name"], p["is_parent"], p["student_name"],
             p["email"], p["phone"], p["current_school"], p["year_group"],
             p["interests"], p["party_size"], p["notes"], booking_id))
        conn.commit()
    out = get_booking(booking_id)
    assert out is not None
    return out


def cancel_booking(booking_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM admissions_event_bookings "
                           "WHERE booking_id = ?", (int(booking_id),))
        conn.commit()
    return cur.rowcount > 0


def mark_attendance(booking_id: int, attended: bool | None) -> Booking:
    """Mark a booking attended (True), no-show (False) or unmarked (None)."""
    init_db()
    if get_booking(booking_id) is None:
        raise ValidationError(f"No booking #{booking_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE admissions_event_bookings SET attended = ?, "
            "attendance_marked_at = CASE WHEN ? IS NULL THEN NULL "
            "ELSE datetime('now') END WHERE booking_id = ?",
            (None if attended is None else int(bool(attended)),
             None if attended is None else 1, booking_id))
        conn.commit()
    out = get_booking(booking_id)
    assert out is not None
    return out


# ── Follow-up ──────────────────────────────────────────────────────

def render_follow_up(booking_id: int) -> tuple[str, str]:
    """(subject, body) thank-you / invitation-to-apply email."""
    b = get_booking(booking_id)
    if b is None:
        raise ValidationError(f"No booking #{booking_id}")
    e = get_event(b.event_id)
    title = e.title if e else "our open event"
    first = (b.attendee_name or "").split(" ")[0] or "there"
    if b.attended:
        lead = f"Thank you for coming to {title}"
    else:
        lead = f"We are sorry we missed you at {title}"
    who = (f"{b.student_name}'s" if b.is_parent and b.student_name
           else "your")
    interests = (f" We hope you found out what you wanted about "
                 f"{', '.join(b.interest_list)}." if b.interest_list else "")
    body = (f"Dear {first},\n\n{lead}.{interests}\n\n"
            f"Applications for {who} place are open now — apply online or "
            f"contact the admissions team and we will help.\n\n"
            "Kind regards,\nAdmissions Team")
    return "Your visit to our Sixth Form", body


def mark_follow_up(booking_id: int, status: str = "Sent") -> Booking:
    if status not in FOLLOW_UP_STATUSES:
        raise ValidationError(f"Follow-up must be one of: "
                              f"{', '.join(FOLLOW_UP_STATUSES)}")
    init_db()
    if get_booking(booking_id) is None:
        raise ValidationError(f"No booking #{booking_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE admissions_event_bookings SET follow_up_status = ?, "
            "follow_up_at = datetime('now') WHERE booking_id = ?",
            (status, booking_id))
        conn.commit()
    out = get_booking(booking_id)
    assert out is not None
    return out


def follow_up_due(event_id: int | None = None) -> list[Booking]:
    """Attendees (or no-shows) who have not applied and not been sent a
    follow-up yet."""
    return [b for b in list_bookings(event_id, not_applied_only=True)
            if b.follow_up_status == "None" and b.attended is not None]


# ── Into an application ────────────────────────────────────────────

def link_to_applicant(booking_id: int, applicant_id: str) -> Booking:
    init_db()
    b = get_booking(booking_id)
    if b is None:
        raise ValidationError(f"No booking #{booking_id}")
    if _adm.get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    with _connect() as conn:
        conn.execute(
            "UPDATE admissions_event_bookings SET applicant_id = ?, "
            "follow_up_status = 'Applied' WHERE booking_id = ?",
            (applicant_id, booking_id))
        e = get_event(b.event_id)
        _adm._log_event(conn, applicant_id,
                        f"Linked to open event booking #{booking_id}"
                        + (f" ({e.label})" if e else ""), kind="event")
        conn.commit()
    out = get_booking(booking_id)
    assert out is not None
    return out


def application_payload(booking_id: int) -> dict[str, Any]:
    """An applicant payload pre-filled from the booking.

    Only what the booking actually holds; the caller supplies the rest
    (date of birth, predicted GCSEs …) before :func:`create_application`.
    Interests that are recognised subjects fill the subject slots.
    """
    b = get_booking(booking_id)
    if b is None:
        raise ValidationError(f"No booking #{booking_id}")
    name = b.prospective_name.split()
    first = name[0] if name else ""
    last = " ".join(name[1:]) if len(name) > 1 else ""
    payload: dict[str, Any] = {
        "first_name": first, "last_name": last,
        "email": b.email if not b.is_parent else "",
        "phone": b.phone or "",
        "previous_school": b.current_school or "",
        "application_source": "Open Evening",
        "submitted_at": _dt.date.today().isoformat(),
    }
    if b.is_parent:
        payload["notes"] = (f"Booked by parent/carer {b.attendee_name}"
                            + (f" ({b.email})" if b.email else ""))
    subjects: list[str] = []
    for s in b.interest_list:
        try:
            if _adm._validate_subject(s, "Interest"):
                subjects.append(s)
        except ValidationError:
            continue
    for i, s in enumerate(subjects[:3], start=1):
        payload[f"subject_{i}"] = s
    return payload


def create_application(booking_id: int, overrides: dict[str, Any]
                       ) -> tuple[_adm.Applicant, bool]:
    """Create the applicant for a booking (or link an existing one).

    ``overrides`` completes the pre-filled payload. Duplicates are found
    with the admissions dedupe (email, or name + date of birth); a match
    is linked instead of creating a second record. Returns
    (applicant, created).
    """
    payload = {**application_payload(booking_id),
               **{k: v for k, v in overrides.items() if v not in (None,)}}
    dupes = _adm.find_duplicates(
        email=payload.get("email") or None,
        first_name=payload.get("first_name") or None,
        last_name=payload.get("last_name") or None,
        dob=payload.get("dob") or None)
    if dupes:
        a = dupes[0]
        link_to_applicant(booking_id, a.applicant_id)
        return a, False
    a = _adm.create_applicant(payload)
    link_to_applicant(booking_id, a.applicant_id)
    return a, True


# ── Reporting ──────────────────────────────────────────────────────

def event_stats(event_id: int) -> EventStats:
    e = get_event(event_id)
    if e is None:
        raise ValidationError(f"No open event #{event_id}")
    bs = list_bookings(event_id)
    return EventStats(
        event=e, bookings=len(bs), people=sum(b.party_size for b in bs),
        attended=sum(1 for b in bs if b.attended is True),
        no_shows=sum(1 for b in bs if b.attended is False),
        unmarked=sum(1 for b in bs if b.attended is None),
        applied=sum(1 for b in bs if b.applicant_id),
        follow_ups_sent=sum(1 for b in bs if b.follow_up_status == "Sent"))


def all_event_stats() -> list[EventStats]:
    return [event_stats(e.event_id) for e in list_events()]


def interest_counts(event_id: int | None = None) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for b in list_bookings(event_id):
        for s in b.interest_list:
            counts[s] = counts.get(s, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def school_counts(event_id: int | None = None) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for b in list_bookings(event_id):
        k = b.current_school or "(not given)"
        counts[k] = counts.get(k, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
