"""Bookings and waitlists for Sixth Form Calendar events.

Sibling to :mod:`calendar`. The events table has carried ``capacity``
and ``rsvp_required`` since day one and nothing has ever booked
against either — a 40-seat theatre trip "with RSVP" was a number and a
tick-box, and the sign-up sheet lived on paper.

One row here is one person's relationship with one event. The rules
are the ones the paper sheet had, made mechanical:

* A full event waitlists you rather than turning you away.
* Cancelling frees a place, and the longest-waiting person gets it
  automatically — nobody has to remember to do the promotion.
* One booking per person per event. Booking again after cancelling
  revives your row rather than growing a duplicate, though a revived
  booking joins the queue where the queue now is, not where you used
  to be.

Check-in (:func:`check_in`) turns the list into a register on the
day, which is what trips actually need it for — the coach leaves when
the attended count matches the booked count, not when somebody has
ticked a printout.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_CALENDAR_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

BOOKED: str = "Booked"
WAITLISTED: str = "Waitlisted"
CANCELLED: str = "Cancelled"
ATTENDED: str = "Attended"
STATES: tuple[str, ...] = (BOOKED, WAITLISTED, CANCELLED, ATTENDED)

# States that occupy a place against capacity.
_HOLDING: tuple[str, ...] = (BOOKED, ATTENDED)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_bookings (
    booking_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     INTEGER NOT NULL,
    person       TEXT NOT NULL,
    person_name  TEXT,
    state        TEXT NOT NULL DEFAULT 'Booked',
    note         TEXT,
    booked_at    TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(event_id, person)
);

CREATE INDEX IF NOT EXISTS idx_cal_book_event
    ON calendar_bookings(event_id);
CREATE INDEX IF NOT EXISTS idx_cal_book_person
    ON calendar_bookings(person);
CREATE INDEX IF NOT EXISTS idx_cal_book_state
    ON calendar_bookings(state);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Booking:
    booking_id: int
    event_id: int
    person: str
    person_name: str | None
    state: str
    note: str | None
    booked_at: str | None
    updated_at: str | None

    @property
    def holds_place(self) -> bool:
        return self.state in _HOLDING

    @property
    def label(self) -> str:
        who = self.person_name or self.person
        return f"{who} — {self.state}"


@dataclass
class BookingSummary:
    """Where one event stands against its capacity."""

    event_id: int
    capacity: int | None
    booked: int
    waitlisted: int
    attended: int
    cancelled: int

    @property
    def taken(self) -> int:
        return self.booked + self.attended

    @property
    def places_left(self) -> int | None:
        if self.capacity is None:
            return None
        return max(0, self.capacity - self.taken)

    @property
    def is_full(self) -> bool:
        return self.places_left == 0

    @property
    def label(self) -> str:
        cap = "∞" if self.capacity is None else str(self.capacity)
        tail = (f", {self.waitlisted} waiting" if self.waitlisted
                else "")
        return f"{self.taken}/{cap} taken{tail}"


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Calendar bookings schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Booking:
    return Booking(
        booking_id=r["booking_id"], event_id=r["event_id"],
        person=r["person"], person_name=r["person_name"],
        state=r["state"], note=r["note"],
        booked_at=r["booked_at"], updated_at=r["updated_at"])


# ── Guards ──────────────────────────────────────────────────────────

def _bookable_event(event_id: int) -> core.Event:
    event = core.get_event(event_id)
    if event is None or event.is_deleted:
        raise ValidationError(f"No event #{event_id}")
    if event.status in ("Cancelled", "Completed"):
        raise ValidationError(
            f"Event #{event_id} is {event.status.lower()} — "
            "bookings are closed")
    return event


def _set_state(booking_id: int, state: str,
               *, note: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE calendar_bookings SET state = ?, "
            "note = COALESCE(?, note), updated_at = datetime('now') "
            "WHERE booking_id = ?", (state, note, booking_id))
        conn.commit()


# ── Booking ─────────────────────────────────────────────────────────

def book(event_id: int, person: str, *,
         person_name: str | None = None,
         note: str | None = None) -> Booking:
    """Take (or queue for) a place. Full events waitlist; a person
    who cancelled earlier is revived rather than duplicated."""
    init_db()
    event = _bookable_event(event_id)
    who = (person or "").strip()
    if not who:
        raise ValidationError("Person is required")

    existing = booking_for(event_id, who)
    if existing and existing.state != CANCELLED:
        raise ValidationError(
            f"{who} already has a booking for event #{event_id} "
            f"({existing.state})")

    summ = booking_summary(event_id)
    state = (WAITLISTED if summ.capacity is not None and summ.is_full
             else BOOKED)

    with _connect() as conn:
        if existing:
            # Rejoin at the back: a revived booking keeps its row but
            # not its old place in the queue.
            conn.execute(
                "UPDATE calendar_bookings SET state = ?, note = ?, "
                "person_name = COALESCE(?, person_name), "
                "booked_at = datetime('now'), "
                "updated_at = datetime('now') WHERE booking_id = ?",
                (state, (note or "").strip() or None,
                 (person_name or "").strip() or None,
                 existing.booking_id))
            conn.commit()
            new_id = existing.booking_id
        else:
            cur = conn.execute(
                "INSERT INTO calendar_bookings "
                "(event_id, person, person_name, state, note) "
                "VALUES (?, ?, ?, ?, ?)",
                (event_id, who, (person_name or "").strip() or None,
                 state, (note or "").strip() or None))
            conn.commit()
            new_id = cur.lastrowid
    out = get_booking(new_id)
    assert out is not None
    logger.info("Event #%d: %s %s", event_id, who, state.lower())
    return out


def cancel(event_id: int, person: str) -> Booking:
    """Give the place up. The longest-waiting person is promoted into
    it in the same breath."""
    init_db()
    existing = booking_for(event_id, (person or "").strip())
    if existing is None or existing.state == CANCELLED:
        raise ValidationError(
            f"No live booking for {person!r} on event #{event_id}")
    held_place = existing.holds_place
    _set_state(existing.booking_id, CANCELLED)
    if held_place:
        promote_waitlist(event_id)
    out = get_booking(existing.booking_id)
    assert out is not None
    return out


def check_in(event_id: int, person: str) -> Booking:
    """Mark somebody as actually here. Only a booked place can check
    in — a waitlisted person at the door goes through :func:`book`
    logic first, not around it."""
    init_db()
    existing = booking_for(event_id, (person or "").strip())
    if existing is None or existing.state != BOOKED:
        state = existing.state if existing else "missing"
        raise ValidationError(
            f"Cannot check in {person!r} on event #{event_id} "
            f"(booking is {state})")
    _set_state(existing.booking_id, ATTENDED)
    out = get_booking(existing.booking_id)
    assert out is not None
    return out


def promote_waitlist(event_id: int) -> list[Booking]:
    """Fill every free place from the front of the queue.

    Also the thing to call after raising an event's capacity — the
    new places go to the people already waiting, in order.
    """
    init_db()
    event = core.get_event(event_id)
    if event is None:
        raise ValidationError(f"No event #{event_id}")
    promoted: list[Booking] = []
    while True:
        summ = booking_summary(event_id)
        if summ.capacity is not None and summ.is_full:
            break
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM calendar_bookings "
                "WHERE event_id = ? AND state = ? "
                "ORDER BY booked_at, booking_id LIMIT 1",
                (event_id, WAITLISTED)).fetchone()
        if r is None:
            break
        _set_state(r["booking_id"], BOOKED)
        got = get_booking(r["booking_id"])
        assert got is not None
        promoted.append(got)
        logger.info("Event #%d: promoted %s from the waitlist",
                    event_id, got.person)
    return promoted


# ── Reads ───────────────────────────────────────────────────────────

def get_booking(booking_id: int) -> Booking | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM calendar_bookings WHERE booking_id = ?",
            (booking_id,)).fetchone()
    return _row(r) if r else None


def booking_for(event_id: int, person: str) -> Booking | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM calendar_bookings "
            "WHERE event_id = ? AND person = ?",
            (event_id, person)).fetchone()
    return _row(r) if r else None


def attendance_list(event_id: int, *,
                    state: str | None = None) -> list[Booking]:
    """The sheet: holders first in booking order, then the queue,
    then cancellations at the bottom."""
    init_db()
    if state is not None and state not in STATES:
        raise ValidationError(
            f"State must be one of: {', '.join(STATES)}")
    clauses = ["event_id = ?"]
    args: list[Any] = [event_id]
    if state:
        clauses.append("state = ?")
        args.append(state)
    order = {BOOKED: 0, ATTENDED: 0, WAITLISTED: 1, CANCELLED: 2}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM calendar_bookings "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY booked_at, booking_id", args).fetchall()
    out = [_row(r) for r in rows]
    out.sort(key=lambda b: order.get(b.state, 3))
    return out


def bookings_for_person(person: str, *,
                        upcoming_only: bool = True) -> list[Booking]:
    """Everything one person is signed up to — their side of the
    story, for a student view or the portal."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT b.* FROM calendar_bookings b "
            "JOIN calendar_events e ON e.event_id = b.event_id "
            "WHERE b.person = ? AND b.state != ? "
            "AND e.deleted_at IS NULL "
            + ("AND e.end_date >= date('now') " if upcoming_only else "")
            + "ORDER BY e.start_date, b.event_id",
            ((person or "").strip(), CANCELLED)).fetchall()
    return [_row(r) for r in rows]


def booking_summary(event_id: int) -> BookingSummary:
    init_db()
    event = core.get_event(event_id)
    if event is None:
        raise ValidationError(f"No event #{event_id}")
    counts = dict.fromkeys(STATES, 0)
    with _connect() as conn:
        for r in conn.execute(
                "SELECT state, COUNT(*) AS n FROM calendar_bookings "
                "WHERE event_id = ? GROUP BY state", (event_id,)):
            counts[r["state"]] = r["n"]
    return BookingSummary(
        event_id=event_id, capacity=event.capacity,
        booked=counts[BOOKED], waitlisted=counts[WAITLISTED],
        attended=counts[ATTENDED], cancelled=counts[CANCELLED])
