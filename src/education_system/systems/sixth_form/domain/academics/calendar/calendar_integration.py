"""Bridges between the Sixth Form Calendar and the rest of the college.

Sibling to :mod:`calendar`. The calendar has been an island: a trip
takes a teacher out and the cover book never hears about it, EPQ
deadlines live only in the EPQ screens, an Open Day is invisible to
the other four systems, and a lesson clash is discovered by thirty
students standing in a corridor.

Each bridge here is one function with a boring name that does the
walking between two modules that have never spoken:

* :func:`raise_cover_for_trip` — a Trip with an organiser becomes
  cover requests, one per teaching day out (F29).
* :func:`lesson_collisions` — which timetable slots a timed event
  tramples (F30).
* :func:`create_activity_register` — an off-timetable event becomes
  an attendance activity, so the trip day still takes a register
  (F31).
* :func:`sync_epq_deadlines` / :func:`sync_enrichment_series` —
  EPQ milestone due dates become Deadline events; a weekly
  enrichment activity becomes a recurring series (F34).
* :func:`upcoming_open_days` — the admissions-facing feed of Open
  Day events (F35).
* :func:`publish_cross_system` — push an event to the platform's
  cross-system calendar, where the other four systems can see it
  (F36).

Every bridge degrades to a :class:`ValidationError` or an empty
result when the far side is missing — an integration must never be
the reason the calendar itself falls over.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
    calendar_recurrence as recurrence,
)

logger = logging.getLogger(__name__)

ValidationError = core.ValidationError

# Sync-generated rows are tagged in their notes so a re-run can find
# its own work and nobody mistakes them for hand-entered events.
_EPQ_MARK = "[auto:epq]"
_ENRICH_MARK = "[auto:enrichment]"

_WEEKDAY_NUMS: dict[str, int] = {
    "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4,
    "friday": 5, "saturday": 6, "sunday": 7,
}


@dataclass
class SyncOutcome:
    """What one sync pass did, in countable terms."""

    created: int = 0
    skipped: int = 0
    details: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return f"{self.created} created, {self.skipped} skipped"


# ── F29: cover ──────────────────────────────────────────────────────

def raise_cover_for_trip(event_id: int, *,
                         reason: str | None = None) -> list[Any]:
    """One cover request per trip day for the organiser.

    Weekends inside a residential are skipped — nobody covers
    Saturday. Returns the created requests. Raises if the event is
    not a Trip or names no organiser: a cover request for nobody
    helps nobody.
    """
    event = core.get_event(event_id)
    if event is None or event.is_deleted:
        raise ValidationError(f"No event #{event_id}")
    if event.event_type != "Trip":
        raise ValidationError(
            f"Event #{event_id} is a {event.event_type}, not a Trip")
    if not event.organiser:
        raise ValidationError(
            f"Event #{event_id} has no organiser to cover")
    try:
        from education_system.systems.sixth_form.domain.academics.cover import (
            cover,
        )
    except Exception:                       # pragma: no cover - optional dep
        raise ValidationError(
            "The cover module is not available") from None

    sd = _dt.date.fromisoformat(event.start_date)
    ed = _dt.date.fromisoformat(event.end_date)
    out = []
    for i in range((ed - sd).days + 1):
        day = sd + _dt.timedelta(days=i)
        if day.weekday() >= 5:
            continue
        req = cover.create_request({
            "absent_teacher": event.organiser,
            "absent_date": day.isoformat(),
            # `absent_reason` is a fixed vocabulary over there; the
            # specifics travel in the notes.
            "absent_reason": "Trip Cover",
            "notes": (reason
                      or f"Trip: {event.title} "
                         f"(event #{event.event_id})"),
        })
        out.append(req)
    logger.info("Trip #%d: raised %d cover request(s) for %s",
                event_id, len(out), event.organiser)
    return out


# ── F30: timetable overlay ──────────────────────────────────────────

def lesson_collisions(event_id: int) -> list[str]:
    """Which timetable slots a timed event tramples, as readable
    lines ("Wed P3 Room 12, group #4").

    Compares by weekday and time window; a slot without stored times
    borrows the college's default period times. All-day events
    collide with the whole day. Weekend days collide with nothing.
    """
    event = core.get_event(event_id)
    if event is None or event.is_deleted:
        raise ValidationError(f"No event #{event_id}")
    try:
        from education_system.systems.sixth_form.domain.academics.timetable import (  # noqa: E501
            timetable as tt,
        )
        grid = tt.weekly_grid()
        period_times = tt.DEFAULT_PERIOD_TIMES
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Timetable unavailable", exc_info=True)
        return []

    if event.all_day or not event.start_time:
        ev_start, ev_end = "00:00", "23:59"
    else:
        ev_start = event.start_time[:5]
        ev_end = (event.end_time or "23:59")[:5]

    sd = _dt.date.fromisoformat(event.start_date)
    ed = _dt.date.fromisoformat(event.end_date)
    weekdays = {(sd + _dt.timedelta(days=i)).weekday() + 1
                for i in range((ed - sd).days + 1)}

    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
    out: list[str] = []
    for (day, period), slots in sorted(grid.items()):
        if day not in weekdays or day not in day_names:
            continue
        default = period_times.get(period, ("00:00", "23:59"))
        for slot in slots:
            s_start = (slot.start_time or default[0])[:5]
            s_end = (slot.end_time or default[1])[:5]
            if s_start < ev_end and ev_start < s_end:
                room = f" {slot.room}" if slot.room else ""
                out.append(f"{day_names[day]} P{period}{room} "
                           f"({s_start}–{s_end}, group "
                           f"#{slot.group_id})")
    return out


# ── F31: off-timetable register ─────────────────────────────────────

def create_activity_register(event_id: int, *,
                             kind: str = "Other") -> Any:
    """Mint an attendance activity for an event so its day still
    takes a register. Returns the created activity; enrol members
    through :mod:`attendance_activities` as usual."""
    event = core.get_event(event_id)
    if event is None or event.is_deleted:
        raise ValidationError(f"No event #{event_id}")
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_activities as acts,
        )
    except Exception:                       # pragma: no cover - optional dep
        raise ValidationError(
            "The attendance activities module is not available"
        ) from None
    payload = {
        "name": f"{event.title} (event #{event.event_id})",
        "kind": kind,
        "room": event.location,
        "staff": event.organiser,
        "start_date": event.start_date,
        "end_date": event.end_date,
        "start_time": (event.start_time or "")[:5] or None,
        "end_time": (event.end_time or "")[:5] or None,
        "active": True,
        "notes": f"Created from calendar event #{event.event_id}",
    }
    activity = acts.create_activity(payload)
    logger.info("Event #%d: activity register #%d created",
                event_id, activity.activity_id)
    return activity


# ── F34: EPQ deadlines ──────────────────────────────────────────────

def sync_epq_deadlines(*, horizon_days: int = 180,
                       actor: str | None = None) -> SyncOutcome:
    """EPQ milestone due dates become Deadline events.

    One event per (project, milestone) with a due date inside the
    horizon. Idempotent: re-runs find their own tagged rows by title
    and date and skip them. Completed milestones are not deadlines
    any more and are left out.
    """
    out = SyncOutcome()
    try:
        from education_system.systems.sixth_form.domain.academics.epq import (
            epq,
        )
        projects = epq.list_projects()
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("EPQ unavailable", exc_info=True)
        return out
    today = _dt.date.today()
    stop = (today + _dt.timedelta(days=horizon_days)).isoformat()
    existing = {
        (e.title, e.start_date)
        for e in core.list_events(event_type="Deadline",
                                  text_like=_EPQ_MARK,
                                  include_deleted=True)
    }
    for project in projects:
        try:
            milestones = epq.list_milestones(project.project_id)
        except Exception:                   # pragma: no cover - defensive
            continue
        for ms in milestones:
            if not ms.due_date or ms.status == "Completed":
                continue
            if not today.isoformat() <= ms.due_date <= stop:
                continue
            title = (f"EPQ {ms.milestone_type}: "
                     f"{project.working_title} ({project.student_id})")
            if (title, ms.due_date) in existing:
                out.skipped += 1
                continue
            core.create_event({
                "title": title,
                "event_type": "Deadline",
                "start_date": ms.due_date,
                "all_day": True,
                "audience": "Students",
                "organiser": project.supervisor,
                "notes": f"{_EPQ_MARK} project #{project.project_id}, "
                         f"milestone #{ms.milestone_id}",
            }, actor=actor)
            out.created += 1
            out.details.append(f"{title} on {ms.due_date}")
    logger.info("EPQ deadline sync: %s", out.summary)
    return out


# ── F34: enrichment series ──────────────────────────────────────────

def sync_enrichment_series(*, start_date: str, until_date: str,
                           actor: str | None = None) -> SyncOutcome:
    """Each running weekly enrichment activity becomes a recurring
    series between the given dates (a term, in practice).

    Idempotent by series title; materialisation itself is left to
    the caller / launch sweep, which is where it already happens for
    every other series.
    """
    out = SyncOutcome()
    try:
        from education_system.systems.sixth_form.domain.academics.enrichment import (  # noqa: E501
            enrichment,
        )
        activities = enrichment.list_activities()
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Enrichment unavailable", exc_info=True)
        return out
    start = core._validate_date(start_date, "Start date")
    until = core._validate_date(until_date, "Until date")
    existing_titles = {s.title for s in
                       recurrence.list_series(active_only=False)}
    # Enrichment's running statuses; Closed/Archived/Draft clubs are
    # not on anybody's week.
    running = ("Open", "Full", "Waitlist")
    for act in activities:
        if getattr(act, "status", "Open") not in running:
            continue
        day_num = _WEEKDAY_NUMS.get((act.day_of_week or "").strip()
                                    .lower())
        if day_num is None or day_num > 5:
            continue        # unscheduled or weekend clubs stay manual
        title = f"Enrichment: {act.name}"
        if title in existing_titles:
            out.skipped += 1
            continue
        # Anchor the series on the first matching weekday >= start.
        anchor = _dt.date.fromisoformat(start)
        while anchor.weekday() + 1 != day_num:
            anchor += _dt.timedelta(days=1)
        recurrence.create_series({
            "title": title,
            "frequency": "Weekly",
            "start_date": anchor.isoformat(),
            "until_date": until,
            "template": {
                "event_type": "Other",
                "start_time": (act.start_time or "")[:5] or None,
                "end_time": (act.end_time or "")[:5] or None,
                "location": act.location,
                "organiser": act.lead_staff,
                "audience": "Students",
                "notes": f"{_ENRICH_MARK} activity "
                         f"#{act.activity_id}",
            },
        }, actor=actor)
        out.created += 1
        out.details.append(f"{title} ({act.day_of_week})")
    logger.info("Enrichment series sync: %s", out.summary)
    return out


# ── F35: admissions feed ────────────────────────────────────────────

def upcoming_open_days(*, limit: int = 10) -> list[core.Event]:
    """The next Open Day events — the list an admissions screen or
    enquiry page shows. Live, public-facing statuses only."""
    today = _dt.date.today().isoformat()
    rows = core.list_events(event_type="Open Day", date_from=today,
                            status="Scheduled", limit=limit)
    return rows


# ── F36: cross-system publish ───────────────────────────────────────

# How this calendar's types map onto the platform service's smaller
# vocabulary.
_CROSS_TYPE_MAP: dict[str, str] = {
    "Open Day": "open_day",
    "INSET": "training",
    "Training": "training",
    "Holiday": "holiday",
    "Meeting": "meeting",
}


def publish_cross_system(event_id: int, *,
                         systems: str = "all",
                         actor: str | None = None) -> dict | None:
    """Push one event to the platform's cross-system calendar, where
    the other four systems' dashboards can see it. Returns the
    created cross-system event dict."""
    event = core.get_event(event_id)
    if event is None or event.is_deleted:
        raise ValidationError(f"No event #{event_id}")
    try:
        from education_system.platform.features.calendar.calendar_service import (  # noqa: E501
            CrossSystemCalendarService,
        )
        service = CrossSystemCalendarService()
    except Exception:                       # pragma: no cover - optional dep
        raise ValidationError(
            "The cross-system calendar service is not available"
        ) from None
    created = service.create_event(
        title=event.title,
        description=event.description or "",
        date=event.start_date,
        time=(event.start_time or "")[:5],
        end_date=(event.end_date
                  if event.end_date != event.start_date else ""),
        systems=systems,
        event_type=_CROSS_TYPE_MAP.get(event.event_type, "other"),
        created_by=actor or event.created_by or "",
        created_system="sixth_form",
    )
    logger.info("Event #%d published cross-system (%s)", event_id,
                systems)
    return created
