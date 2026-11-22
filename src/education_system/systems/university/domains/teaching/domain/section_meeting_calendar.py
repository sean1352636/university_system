"""Mirror course-section meetings onto the academic calendar.

A ``section_meetings`` row is a *weekly rule* — "ACC-001, Mondays 09:00-10:00"
— scoped to a term. The academic calendar stores *dated* events in
``unified_events``. This module expands the rule into one calendar occurrence
per week and keeps the two in step.

Three properties matter:

* **Idempotent.** Each occurrence is linked on ``(source_type,
  source_event_id)`` via :func:`link_source_event`, with the source id
  ``"<meeting_id>:<date>"``. Re-syncing a meeting updates its occurrences
  rather than duplicating them.
* **Forward-only.** Occurrences are materialised from today to the end of the
  term. Back-filling a year of past classes would add rows nobody reads — the
  ``summer`` term alone spans ~52 weeks.
* **Addressed to real people.** ``participants`` carries the students enrolled
  in the section's course and ``organizer_name`` the instructor, so the
  meeting lands on the calendar of everyone who has to attend rather than on a
  shared list nobody owns.

The course→module hop goes through ``timetable_bridge``: sections are keyed by
``course_code`` while enrolment lives in ``student_modules`` keyed by
``module_code``, and those two vocabularies are only equal by convention.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.database.schemas.unified_events_link import (
    link_source_event,
)

logger = logging.getLogger(__name__)

#: ``unified_events.source_type`` for rows this module owns. Distinct from
#: ``academic_calendar`` so a re-sync can never disturb hand-entered events.
SOURCE_TYPE = "section_meeting"

#: Guard against a mis-entered term (the seeded ``summer`` term spans a year).
MAX_OCCURRENCES = 60

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt).date()
        except ValueError:
            continue
    return None


def occurrence_dates(day_of_week: str, term_start: str | None,
                     term_end: str | None, *, today: date | None = None,
                     limit: int = MAX_OCCURRENCES) -> list[date]:
    """Weekly dates for *day_of_week* between today and the term end."""
    weekday = _WEEKDAYS.get(str(day_of_week or "").strip().lower())
    if weekday is None:
        return []
    start = _parse_date(term_start)
    end = _parse_date(term_end)
    if end is None:
        return []
    today = today or date.today()
    cursor = max(start or today, today)
    # Advance to the first matching weekday on or after the cursor.
    cursor += timedelta(days=(weekday - cursor.weekday()) % 7)
    out: list[date] = []
    while cursor <= end and len(out) < limit:
        out.append(cursor)
        cursor += timedelta(days=7)
    return out


def _meeting_context(conn, meeting_id: int) -> dict[str, Any] | None:
    """Everything needed to describe one meeting on a calendar."""
    row = conn.execute(
        """SELECT m.id, m.section_id, m.day_of_week, m.start_time, m.end_time,
                  m.location, m.room_id,
                  s.course_code, s.section_number, s.instructor, s.term_id,
                  t.name AS term_name, t.start_date, t.end_date
             FROM section_meetings m
             JOIN course_sections s ON s.id = m.section_id
             LEFT JOIN academic_terms t ON t.id = s.term_id
            WHERE m.id = ?""",
        (meeting_id,),
    ).fetchone()
    if row is None:
        return None
    try:
        return dict(row)
    except (TypeError, ValueError):
        keys = ("id", "section_id", "day_of_week", "start_time", "end_time",
                "location", "room_id", "course_code", "section_number",
                "instructor", "term_id", "term_name", "start_date", "end_date")
        return dict(zip(keys, row))


def _participants_for_course(conn, course_code: str) -> list[dict[str, Any]]:
    """Users enrolled in the modules linked to *course_code*.

    Returns the ``[{"user_id": .., "username": ..}]`` shape the calendar
    already uses. A student with no ``users`` row is skipped rather than
    guessed at — the two id spaces are not interchangeable.
    """
    if not course_code:
        return []
    module_codes = {course_code}
    try:
        for r in conn.execute(
                "SELECT module_code FROM course_module_map WHERE course_code = ?",
                (course_code,)).fetchall():
            module_codes.add(r[0])
    except Exception:
        logger.debug("course_module_map unavailable", exc_info=True)

    placeholders = ",".join("?" * len(module_codes))
    try:
        rows = conn.execute(
            # db-audit: ignore[DBW001] - join of placeholders
            f"""SELECT DISTINCT u.id, u.username
                  FROM student_modules sm
                  JOIN users u ON u.student_id = sm.student_id
                 WHERE sm.module_code IN ({placeholders})
                   AND COALESCE(sm.status, 'Enrolled') NOT IN
                       ('Withdrawn', 'Dropped', 'Cancelled')""",
            list(module_codes),
        ).fetchall()
    except Exception:
        logger.debug("Could not resolve participants for %s", course_code,
                     exc_info=True)
        return []
    return [{"user_id": r[0], "username": r[1]} for r in rows]


def sync_meeting(meeting_id: int, conn=None) -> int:
    """Mirror one meeting onto the calendar. Returns occurrences written.

    Safe to call after every edit: stale occurrences for this meeting are
    cleared first, so moving a class from Monday to Tuesday does not leave the
    Monday entries behind.
    """
    owns = conn is None
    conn = conn or get_connection()
    try:
        ctx = _meeting_context(conn, meeting_id)
        if ctx is None:
            return 0
        dates = occurrence_dates(ctx["day_of_week"], ctx.get("start_date"),
                                 ctx.get("end_date"))
        participants = _participants_for_course(conn, ctx.get("course_code"))
        # Clear first: the day or time may have changed, and an occurrence that
        # no longer exists has no source row to update.
        _delete_occurrences(conn, meeting_id)
        if not dates:
            conn.commit()
            return 0

        label = f"{ctx.get('course_code') or 'Course'}"
        if ctx.get("section_number"):
            label += f"-{ctx['section_number']}"
        location = (ctx.get("location") or "").strip()
        now = datetime.now().isoformat(timespec="seconds")

        written = 0
        for occurrence in dates:
            fields = {
                "title": f"{label} class",
                "description": (
                    f"{label} — {ctx.get('day_of_week')} "
                    f"{ctx.get('start_time')}–{ctx.get('end_time')}"
                    + (f" in {location}" if location else "")
                    + (f" ({ctx['term_name']})" if ctx.get("term_name") else "")
                ),
                "event_type": "Class",
                "event_date": occurrence.isoformat(),
                "start_time": ctx.get("start_time"),
                "end_time": ctx.get("end_time"),
                "location": location or None,
                "room_id": ctx.get("room_id"),
                "organizer_name": ctx.get("instructor") or None,
                "audience": "Course",
                "participants": json.dumps(participants),
                "status": "scheduled",
                "is_active": 1,
                "created_at": now,
                "updated_at": now,
            }
            link_source_event(conn, SOURCE_TYPE,
                              f"{meeting_id}:{occurrence.isoformat()}", fields)
            written += 1
        conn.commit()
        return written
    finally:
        if owns:
            conn.close()


def _delete_occurrences(conn, meeting_id: int) -> int:
    cur = conn.execute(
        "DELETE FROM unified_events "
        "WHERE source_type = ? AND source_event_id LIKE ?",
        (SOURCE_TYPE, f"{meeting_id}:%"),
    )
    return cur.rowcount or 0


def clear_occurrences(conn, meeting_ids) -> int:
    """Remove these meetings from the calendar in the caller's transaction."""
    return sum(_delete_occurrences(conn, meeting_id) for meeting_id in meeting_ids)


def unsync_meeting(meeting_id: int, conn=None) -> int:
    """Remove every calendar occurrence for a deleted meeting."""
    owns = conn is None
    conn = conn or get_connection()
    try:
        removed = _delete_occurrences(conn, meeting_id)
        conn.commit()
        return removed
    finally:
        if owns:
            conn.close()


def sync_section(section_id: int) -> int:
    """Re-sync every meeting on a section. Returns occurrences written."""
    with transaction() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM section_meetings WHERE section_id = ?",
            (section_id,)).fetchall()]
        return sum(sync_meeting(mid, conn) for mid in ids)


def calendar_summary(meeting_id: int, conn=None) -> dict[str, Any]:
    """What the calendar currently holds for a meeting — for the GUI to show."""
    owns = conn is None
    conn = conn or get_connection()
    try:
        rows = conn.execute(
            "SELECT event_date FROM unified_events "
            "WHERE source_type = ? AND source_event_id LIKE ? "
            "ORDER BY event_date",
            (SOURCE_TYPE, f"{meeting_id}:%"),
        ).fetchall()
        dates = [r[0] for r in rows]
        return {"count": len(dates),
                "first": dates[0] if dates else None,
                "last": dates[-1] if dates else None}
    finally:
        if owns:
            conn.close()


__all__ = [
    "SOURCE_TYPE", "occurrence_dates", "sync_meeting", "unsync_meeting", "clear_occurrences",
    "sync_section", "calendar_summary",
]
