"""Clash detection and slot suggestion for the Sixth Form Calendar.

Sibling to :mod:`calendar`. Nothing has ever stopped two events being
put in the Main Hall at the same time; the double-booking is
discovered by whoever arrives second, in front of their audience.

:func:`check` answers "what would collide with this?" before the save.
It looks in three places:

* **This calendar** — another event at the same location whose times
  overlap.
* **The room-booking book** — :mod:`room_booking` is a separate
  ledger with its own idea of who has the hall, and the two have
  never compared notes. Matching is by name, because a calendar
  event's ``location`` is free text and a room resource has a name;
  where they spell the room the same way, the clash is caught.
* **The organiser's own diary** — the same person down to run two
  things at once, which is usually a data error and occasionally a
  colleague who needs rescuing.

Everything comes back as a *warning*, not a refusal. The college
legitimately runs two things in the sports hall with a divider, and a
Deadline "at" the library clashes with nothing. The views surface the
warnings and let a human decide; :func:`check` just refuses to let
the collision be a surprise.

:func:`suggest_slots` is the constructive half: given a duration and
optionally a location, it walks the coming days and returns windows
where nothing collides.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)

logger = logging.getLogger(__name__)

ValidationError = core.ValidationError


# Event types that occupy nobody and nowhere — a deadline or a
# holiday "clashes" with nothing.
NON_BLOCKING_TYPES: tuple[str, ...] = ("Deadline", "Holiday")

# The whole teaching-relevant day, for all-day events and suggestion
# windows.
DAY_START: str = "08:00:00"
DAY_END: str = "18:00:00"


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Clash:
    """One thing the proposed event would collide with."""

    kind: str            # "location" | "room-booking" | "organiser"
    date: str
    detail: str
    event_id: int | None = None      # the calendar event hit, if any

    @property
    def label(self) -> str:
        return f"[{self.kind}] {self.date}: {self.detail}"


@dataclass
class ClashReport:
    clashes: list[Clash] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.clashes

    @property
    def summary(self) -> str:
        if self.clean:
            return "No clashes."
        return "\n".join(c.label for c in self.clashes)


@dataclass
class Slot:
    """A free window :func:`suggest_slots` found."""

    date: str
    start_time: str
    end_time: str

    @property
    def label(self) -> str:
        return (f"{self.date} {self.start_time[:5]}–"
                f"{self.end_time[:5]}")


# ── Internals ───────────────────────────────────────────────────────

def _times(event_like: Any) -> tuple[str, str]:
    """The window an event occupies on a given day. All-day and
    open-ended events block the whole working day — claiming the hall
    "all day" means exactly that."""
    start = getattr(event_like, "start_time", None)
    end = getattr(event_like, "end_time", None)
    if getattr(event_like, "all_day", False) or not start:
        return DAY_START, DAY_END
    return start, (end or DAY_END)


def _overlaps(a_start: str, a_end: str,
              b_start: str, b_end: str) -> bool:
    return a_start < b_end and b_start < a_end


def _dates_of(start_date: str, end_date: str) -> list[str]:
    sd = _dt.date.fromisoformat(start_date)
    ed = _dt.date.fromisoformat(end_date)
    return [(sd + _dt.timedelta(days=i)).isoformat()
            for i in range((ed - sd).days + 1)]


def _proposed(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate through the core rules so the checker reasons about
    the event as it would actually be saved."""
    return core._validate_payload(payload)


# ── The checks ──────────────────────────────────────────────────────

def _location_clashes(p: dict[str, Any],
                      exclude_event_id: int | None) -> list[Clash]:
    if not p["location"]:
        return []
    start, end = _times(_P(p))
    out: list[Clash] = []
    for date in _dates_of(p["start_date"], p["end_date"]):
        for other in core.events_on(date):
            if other.event_id == exclude_event_id:
                continue
            if other.status in ("Cancelled", "Postponed"):
                continue
            if other.event_type in NON_BLOCKING_TYPES:
                continue
            if (other.location or "").strip().lower() != \
                    p["location"].strip().lower():
                continue
            o_start, o_end = _times(other)
            if _overlaps(start, end, o_start, o_end):
                out.append(Clash(
                    kind="location", date=date,
                    event_id=other.event_id,
                    detail=(f"{p['location']} already has "
                            f"#{other.event_id} {other.title!r} "
                            f"({other.time_label})")))
    return out


def _room_booking_clashes(p: dict[str, Any]) -> list[Clash]:
    """Ask the room-booking ledger about rooms whose *name* matches
    the event's free-text location. Import failures degrade to "no
    answer" — the calendar must not fall over because the room book
    is absent in some install."""
    if not p["location"]:
        return []
    try:
        from education_system.systems.sixth_form.domain.academics.room_booking import (  # noqa: E501
            room_booking as rb,
        )
        resources = [r for r in rb.list_resources(active_only=True)
                     if r.name.strip().lower()
                     == p["location"].strip().lower()]
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Room-booking lookup unavailable", exc_info=True)
        return []
    if not resources:
        return []
    start, end = _times(_P(p))
    out: list[Clash] = []
    for date in _dates_of(p["start_date"], p["end_date"]):
        for res in resources:
            try:
                hits = rb.find_clashes(
                    resource_id=res.resource_id, booking_date=date,
                    start_time=start, end_time=end)
            except Exception:               # pragma: no cover - defensive
                logger.debug("find_clashes failed for %s", res.name,
                             exc_info=True)
                continue
            for b in hits:
                out.append(Clash(
                    kind="room-booking", date=date,
                    detail=(f"{res.name} is booked "
                            f"{b.start_time[:5]}–{b.end_time[:5]} "
                            f"(booking #{b.booking_id})")))
    return out


def _organiser_clashes(p: dict[str, Any],
                       exclude_event_id: int | None) -> list[Clash]:
    if not p["organiser"]:
        return []
    start, end = _times(_P(p))
    out: list[Clash] = []
    for date in _dates_of(p["start_date"], p["end_date"]):
        for other in core.events_on(date):
            if other.event_id == exclude_event_id:
                continue
            if other.status in ("Cancelled", "Postponed"):
                continue
            if other.event_type in NON_BLOCKING_TYPES:
                continue
            if (other.organiser or "").strip().lower() != \
                    p["organiser"].strip().lower():
                continue
            o_start, o_end = _times(other)
            if _overlaps(start, end, o_start, o_end):
                out.append(Clash(
                    kind="organiser", date=date,
                    event_id=other.event_id,
                    detail=(f"{p['organiser']} is already running "
                            f"#{other.event_id} {other.title!r} "
                            f"({other.time_label})")))
    return out


class _P:
    """Duck-typed shim so _times() can read a validated payload the
    same way it reads an Event."""

    def __init__(self, p: dict[str, Any]) -> None:
        self.start_time = p.get("start_time")
        self.end_time = p.get("end_time")
        self.all_day = p.get("all_day", False)


def check(payload: dict[str, Any], *,
          exclude_event_id: int | None = None) -> ClashReport:
    """Everything a proposed event would collide with.

    ``exclude_event_id`` keeps an edit from clashing with itself.
    Pass the same payload you are about to hand to
    :func:`calendar.create_event`.
    """
    core.init_db()
    p = _proposed(payload)
    if p["event_type"] in NON_BLOCKING_TYPES:
        return ClashReport()
    report = ClashReport()
    report.clashes.extend(_location_clashes(p, exclude_event_id))
    report.clashes.extend(_room_booking_clashes(p))
    report.clashes.extend(_organiser_clashes(p, exclude_event_id))
    if report.clashes:
        logger.info("Clash check for %r: %d hit(s)", p["title"],
                    len(report.clashes))
    return report


# ── Suggestion ──────────────────────────────────────────────────────

def suggest_slots(
    *,
    duration_minutes: int,
    location: str | None = None,
    organiser: str | None = None,
    date_from: str | None = None,
    days_to_search: int = 14,
    earliest: str = "09:00",
    latest: str = "17:00",
    max_suggestions: int = 5,
) -> list[Slot]:
    """Windows where the proposed thing fits.

    Walks each day from ``date_from`` (default tomorrow) in
    half-hour steps and keeps the first windows in which
    :func:`check` comes back clean. Weekends are skipped — this is a
    college.
    """
    core.init_db()
    if duration_minutes < 5:
        raise ValidationError("Duration must be at least 5 minutes")
    first = (core._validate_date(date_from, "date_from")
             if date_from
             else (_dt.date.today() + _dt.timedelta(days=1)).isoformat())
    day = _dt.date.fromisoformat(first)
    lo = _dt.datetime.strptime(earliest, "%H:%M").time()
    hi = _dt.datetime.strptime(latest, "%H:%M").time()

    out: list[Slot] = []
    for _ in range(max(1, days_to_search)):
        if day.weekday() < 5:               # Mon–Fri only
            cursor = _dt.datetime.combine(day, lo)
            day_end = _dt.datetime.combine(day, hi)
            while cursor + _dt.timedelta(
                    minutes=duration_minutes) <= day_end:
                start_t = cursor.time().isoformat()
                end_t = (cursor + _dt.timedelta(
                    minutes=duration_minutes)).time().isoformat()
                probe = {
                    "title": "(probe)",
                    "start_date": day.isoformat(),
                    "start_time": start_t[:5],
                    "end_time": end_t[:5],
                    "location": location,
                    "organiser": organiser,
                }
                if check(probe).clean:
                    out.append(Slot(date=day.isoformat(),
                                    start_time=start_t,
                                    end_time=end_t))
                    if len(out) >= max_suggestions:
                        return out
                    break       # one suggestion per day is plenty
                cursor += _dt.timedelta(minutes=30)
        day += _dt.timedelta(days=1)
    return out
