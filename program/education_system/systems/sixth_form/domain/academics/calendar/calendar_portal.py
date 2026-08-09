"""The parent/student portal's view of the Sixth Form Calendar.

Sibling to :mod:`calendar`. The portal has never shown an event: a
parent finds out about the trip when the consent form surfaces from
the bottom of a bag. This module is the calendar's public face —
one read function per portal surface, each already filtered to what
that viewer is allowed to see, so no route ever re-implements the
visibility rules.

The reads:

* :func:`feed_for_parent` — Public events for parents' audiences,
  the term at a glance.
* :func:`feed_for_student` — the college's day-to-day calendar for
  a student, with anything they have *booked* pinned to the top;
  your own trip matters more than the whole college's fixtures.
* :func:`upcoming_highlights` — the handful of headline events a
  portal landing page shows before any filter is applied.

Everything routes through :func:`calendar_governance.visible_events`
— the one place the visibility ladder lives. This module decides
*ordering and shape*; it never re-decides *permission*.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
    calendar_bookings as bookings,
    calendar_governance as governance,
)

logger = logging.getLogger(__name__)

ValidationError = core.ValidationError

# Which audiences each portal viewer cares about. A parent reads
# events aimed at parents, students and everyone; nobody's portal
# shows Staff briefings.
_PARENT_AUDIENCES: tuple[str, ...] = (
    "All", "Parents", "Students", "Year 12", "Year 13",
)
_STUDENT_AUDIENCES: tuple[str, ...] = (
    "All", "Students", "Year 12", "Year 13",
)

# Landing-page headliners, most interesting first.
_HIGHLIGHT_TYPES: tuple[str, ...] = (
    "Open Day", "Parents' Evening", "Trip", "Exam", "Mock Exam",
    "Social", "Sports Fixture",
)


@dataclass
class PortalEvent:
    """One event, flattened to what a portal template needs."""

    event_id: int
    title: str
    event_type: str
    start_date: str
    end_date: str
    time_label: str
    location: str | None
    audience: str
    is_booked: bool = False
    booking_state: str | None = None
    rsvp_required: bool = False
    cost: float | None = None

    @property
    def is_multiday(self) -> bool:
        return self.start_date != self.end_date

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "event_type": self.event_type,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "time_label": self.time_label,
            "location": self.location,
            "audience": self.audience,
            "is_booked": self.is_booked,
            "booking_state": self.booking_state,
            "rsvp_required": self.rsvp_required,
            "cost": self.cost,
        }


@dataclass
class PortalFeed:
    viewer: str
    events: list[PortalEvent] = field(default_factory=list)

    @property
    def booked(self) -> list[PortalEvent]:
        return [e for e in self.events if e.is_booked]

    def to_dict(self) -> dict[str, Any]:
        return {"viewer": self.viewer,
                "events": [e.to_dict() for e in self.events]}


def _shape(event: core.Event, *,
           booking_state: str | None = None) -> PortalEvent:
    return PortalEvent(
        event_id=event.event_id, title=event.title,
        event_type=event.event_type, start_date=event.start_date,
        end_date=event.end_date, time_label=event.time_label,
        location=event.location, audience=event.audience,
        is_booked=booking_state is not None,
        booking_state=booking_state,
        rsvp_required=event.rsvp_required, cost=event.cost)


def _window(days_ahead: int) -> tuple[str, str]:
    today = _dt.date.today()
    return (today.isoformat(),
            (today + _dt.timedelta(days=days_ahead)).isoformat())


# ── The feeds ───────────────────────────────────────────────────────

def feed_for_parent(*, days_ahead: int = 90) -> PortalFeed:
    """What a parent's portal calendar shows: Public events aimed at
    families, soonest first."""
    date_from, date_to = _window(days_ahead)
    rows = governance.visible_events(
        "parent", date_from=date_from, date_to=date_to,
        status="Scheduled")
    feed = PortalFeed(viewer="parent")
    feed.events = [_shape(e) for e in rows
                   if e.audience in _PARENT_AUDIENCES]
    return feed


def feed_for_student(student_id: str, *,
                     days_ahead: int = 90) -> PortalFeed:
    """A student's calendar: their own booked events first, then the
    college's, soonest first within each half."""
    who = (student_id or "").strip()
    if not who:
        raise ValidationError("Student ID is required")
    date_from, date_to = _window(days_ahead)
    rows = governance.visible_events(
        "student", date_from=date_from, date_to=date_to,
        status="Scheduled")
    states = {b.event_id: b.state
              for b in bookings.bookings_for_person(who)}
    mine: list[PortalEvent] = []
    rest: list[PortalEvent] = []
    for e in rows:
        if e.event_id in states:
            mine.append(_shape(e, booking_state=states[e.event_id]))
        elif e.audience in _STUDENT_AUDIENCES:
            rest.append(_shape(e))
    feed = PortalFeed(viewer="student")
    feed.events = mine + rest
    return feed


def upcoming_highlights(*, limit: int = 5,
                        days_ahead: int = 120) -> list[PortalEvent]:
    """The landing page's headline strip: the next few big public
    events, in type order of interest then date."""
    date_from, date_to = _window(days_ahead)
    rows = governance.visible_events(
        "public", date_from=date_from, date_to=date_to,
        status="Scheduled")
    rank = {t: i for i, t in enumerate(_HIGHLIGHT_TYPES)}
    picked = [e for e in rows if e.event_type in rank]
    picked.sort(key=lambda e: (e.start_date, rank[e.event_type]))
    return [_shape(e) for e in picked[:max(1, limit)]]
