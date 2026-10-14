"""Put transition dates and reminders on the cross-system calendar.

A transfer has dates both institutions plan around — the day the learner
starts at the destination, and the reminders the workflow schedules on the
bus (``transition.reminder`` published with a future ``available_at``).
Neither appeared on the shared calendar, so a college's open-day planner
could not see that forty Year 11s were due to start the same week.

Two entry kinds, each keyed by a ``source_ref`` so re-syncing updates rather
than duplicates:

``transition:<id>:effective``   the destination start date
``reminder:<event_id>``         a scheduled reminder, on its due date

Entries carry system labels and ids only — the calendar is visible to staff
in every system, which is not the audience for a learner's name.

Driven two ways: as a shared bus consumer on the workflow events, and by
:func:`sync_transition_dates` (a full re-scan, which is also the only way
to see reminders *before* they fall due — the bus does not dispatch an
event until its ``available_at``).
"""

from __future__ import annotations

import logging

from education_system.paths import SYSTEM_LABELS
from education_system.platform.integrations.external import cross_system_bus

logger = logging.getLogger(__name__)

HANDLER_NAME = "platform.features.calendar.transition_sync"

_WATCHED: frozenset[str] = frozenset({
    cross_system_bus.EVENT_PROGRESSION_EXPECTED,
    cross_system_bus.EVENT_APPLICATION_SUBMITTED,
    cross_system_bus.EVENT_PLACE_OFFERED,
    cross_system_bus.EVENT_PLACE_ACCEPTED,
    cross_system_bus.EVENT_HANDOVER_APPROVED,
    cross_system_bus.EVENT_HANDOVER_ACKNOWLEDGED,
    cross_system_bus.EVENT_ENROLMENT_CREATED,
    cross_system_bus.EVENT_PROGRESSION_COMPLETED,
    cross_system_bus.EVENT_PROGRESSION_CANCELLED,
    cross_system_bus.EVENT_PROGRESSION_REJECTED,
})

_REMOVED_ON: frozenset[str] = frozenset({"cancelled", "rejected"})

_registered = False


def _label(system: str | None) -> str:
    if not system:
        return "external"
    return SYSTEM_LABELS.get(system, system.replace("_", " ").title())


def _calendar(db_path: str | None):
    from education_system.platform.features.calendar.calendar_service import (
        CrossSystemCalendarService,
    )
    return CrossSystemCalendarService(db_path=db_path)


def _systems_field(*systems: str | None) -> str:
    keys = sorted({s for s in systems if s})
    return ",".join(keys) or "all"


def _effective_from_events(transition_id: str, db_path: str | None) -> str | None:
    """The newest effective/start date recorded against a transition.

    Reads the workflow's own step trail where it exists (each step can
    carry an ``effective_date``), else the dates published on the bus.
    """
    from education_system.platform.features.analytics import transfer_monitor

    events, _source = transfer_monitor.transition_events(transition_id,
                                                         db_path=db_path)
    for event in reversed(events):  # newest first
        for value in (event.get("effective_date"),
                      (event.get("payload") or {}).get("effective_date"),
                      (event.get("payload") or {}).get("start_date")):
            if value:
                return str(value)[:10]
    return None


def sync_transition(transition_id: str, *, db_path: str | None = None,
                    calendar=None) -> int:
    """Bring one transition's calendar entries up to date. Returns entries written."""
    from education_system.platform.features.analytics import transfer_monitor

    calendar = calendar or _calendar(db_path)
    row = transfer_monitor.get_transition(transition_id, db_path=db_path)
    ref = f"transition:{transition_id}:effective"
    if row is None or row.get("status") in _REMOVED_ON:
        # A cancelled move is not happening; leaving its start date on the
        # calendar would have both institutions planning for a learner who
        # is not coming.
        calendar.remove_sourced_events(ref)
        return 0
    when = row.get("effective_date") or _effective_from_events(transition_id, db_path)
    written = 0
    if when:
        src, dst = row.get("source_system"), row["destination_system"]
        calendar.upsert_sourced_event(
            ref,
            title=f"Transfer {_label(src)} to {_label(dst)} takes effect",
            description=(f"Transition {transition_id} (journey "
                         f"{row['journey_id']}), status {row['status']}."),
            date=when, systems=_systems_field(src, dst), event_type="transition")
        written += 1
    return written


def sync_reminders(*, db_path: str | None = None, calendar=None) -> int:
    """Mirror every still-scheduled ``transition.reminder`` onto the calendar."""
    calendar = calendar or _calendar(db_path)
    written = 0
    for event in cross_system_bus.list_events(
            event_name=cross_system_bus.EVENT_TRANSITION_REMINDER,
            status="scheduled", limit=1000, db_path=db_path):
        payload = event.get("payload") or {}
        due = str(event.get("available_at") or "")[:10]
        if not due:
            continue
        src = event.get("source_system")
        dst = payload.get("destination_system") or event.get("target_system")
        what = payload.get("reminder") or payload.get("kind") or "transfer deadline"
        calendar.upsert_sourced_event(
            f"reminder:{event['event_id']}",
            title=f"Reminder: {what} ({_label(src)} to {_label(dst)})",
            description=(f"Transition {payload.get('transition_id') or '—'} "
                         f"(journey {event.get('journey_id') or '—'})."),
            date=due, systems=_systems_field(src, dst), event_type="reminder")
        written += 1
    return written


def sync_transition_dates(*, db_path: str | None = None) -> dict[str, int]:
    """Full re-sync: every open transition's start date, plus reminders."""
    from education_system.platform.features.analytics import transfer_monitor

    calendar = _calendar(db_path)
    transitions = 0
    for row in transfer_monitor.search_transitions(open_only=True, limit=2000,
                                                   db_path=db_path):
        transitions += sync_transition(row["transition_id"], db_path=db_path,
                                       calendar=calendar)
    reminders = sync_reminders(db_path=db_path, calendar=calendar)
    return {"transitions": transitions, "reminders": reminders}


def handle(envelope: dict) -> None:
    """Bus handler: refresh the calendar for the transition an event concerns."""
    if envelope.get("event_name") not in _WATCHED:
        return
    tid = (envelope.get("payload") or {}).get("transition_id")
    if tid:
        sync_transition(tid, db_path=cross_system_bus.current_dispatch_db_path())


def register_consumer() -> None:
    global _registered
    if _registered:
        return
    for name in sorted(_WATCHED):
        cross_system_bus.subscribe(name, handle, handler_name=HANDLER_NAME)
    _registered = True


def reset_for_test() -> None:
    global _registered
    _registered = False


__all__ = [
    "HANDLER_NAME",
    "handle",
    "register_consumer",
    "sync_reminders",
    "sync_transition",
    "sync_transition_dates",
]
