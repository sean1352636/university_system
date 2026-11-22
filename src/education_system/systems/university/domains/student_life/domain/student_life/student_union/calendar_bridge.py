"""Auto-publish anything the Student Union creates to the university calendar.

Every SU create flow (clubs, events, elections, competitions, bookings,
mentorship sessions, volunteering, study groups) calls :func:`mirror`
right after it commits its own row. The write itself lives in
``services.bus.student_union_bus.add_calendar_entry`` — the same writer
H&S drills and hearings use — so SU entries appear on every calendar
view without the student having to sync anything by hand.

The import is deliberately lazy and every failure is swallowed: the SU
record is already committed by the time we get here, and a calendar
hiccup must never make a successful creation look like it failed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def mirror(*, name: str, kind: str, **fields) -> str | None:
    """Add a Student Union item to the university academic calendar.

    Accepts the same keywords as
    ``student_union_bus.add_calendar_entry`` (``date``, ``date_start``,
    ``date_end``, ``description``, ``source_table``, ``source_id``,
    ``created_by``, ``start_time``, ``end_time``, ``location``,
    ``organizer``, ``conn``). Returns the calendar event id, or
    ``None`` if the entry could not be written.
    """
    try:
        from education_system.systems.university.services.bus.student_union_bus import (
            add_calendar_entry,
        )
        return add_calendar_entry(name=name, kind=kind, **fields)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("calendar mirror for %r failed: %s", name, exc)
        return None


__all__ = ["mirror"]
