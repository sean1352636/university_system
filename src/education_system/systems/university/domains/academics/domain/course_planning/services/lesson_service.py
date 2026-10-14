"""Lesson CRUD for the planner CLI — now over the merged scheduling model.

This used to be plain CRUD over ``lesson_plans`` and ``lesson_courses``, the
Lesson Planner's private timetable and course list. Both are retired: the
timetable lives in ``module_schedule`` (one store, with room and instructor
foreign keys, terms, draft/published status and conflict detection), and the
course catalogue is the canonical ``courses``/``modules`` pair.

What survives is lesson *content* — a title, delivery type and notes attached
to a scheduled slot — which is what
``domain.services.module_scheduling.lesson_plans`` owns. This module stays as
the CLI's shape of that: the planner CLI kept its signatures, so the
translation happens here rather than in the menu code.

A lesson can no longer invent its own day, time or room: those belong to the
slot it hangs off, and are changed in Module Scheduling.
"""

from __future__ import annotations

from typing import Any, Optional

from education_system.systems.university.domains.academics.domain.services.module_scheduling import (
    lesson_plans as _content,
)

# Re-exported so the CLI can offer the same list the GUI does.
LESSON_TYPES = _content.LESSON_TYPES


def list_slots(search: Optional[str] = None) -> list[dict[str, Any]]:
    """Every scheduled slot, with its lesson content where one exists."""
    slots = _content.scheduled_slots()
    if search:
        needle = search.lower()
        slots = [s for s in slots
                 if needle in " ".join(str(s.get(k) or "") for k in
                                       ("module_code", "module_name", "title",
                                        "day_of_week", "room", "instructor")).lower()]
    return slots


def list_lessons(search: Optional[str] = None) -> list[dict[str, Any]]:
    """Slots that have lesson content, plus any lesson with no slot."""
    lessons = [s for s in list_slots(search) if s.get("lesson_id")]
    return lessons + _content.unscheduled_lessons()


def get_slot(schedule_id: int) -> Optional[dict[str, Any]]:
    for slot in _content.scheduled_slots():
        if str(slot.get("schedule_id")) == str(schedule_id):
            return slot
    return None


def set_lesson(schedule_id: int, title: str, *, lesson_type: str = "",
               notes: str = "", updated_by: str = "") -> Optional[int]:
    """Attach (or update) the lesson on a scheduled slot."""
    slot = get_slot(schedule_id)
    if slot is None:
        raise ValueError(f"No scheduled slot with id {schedule_id}")
    return _content.save_lesson(
        schedule_id, title=title, lesson_type=lesson_type, notes=notes,
        module_code=slot.get("module_code"), lesson_id=slot.get("lesson_id"),
        updated_by=updated_by,
    )


def clear_lesson(lesson_id: int) -> bool:
    """Remove lesson content. The scheduled slot is left alone."""
    return _content.delete_lesson(lesson_id)


def attach_lesson(lesson_id: int, schedule_id: int) -> bool:
    """Give an unscheduled lesson a slot."""
    return _content.attach_to_slot(lesson_id, schedule_id)


def unscheduled() -> list[dict[str, Any]]:
    """Lesson content with no slot — usually a module that no longer exists."""
    return _content.unscheduled_lessons()


def weekly_hours() -> list[dict[str, Any]]:
    """Planned contact hours per module, from the schedule itself."""
    totals: dict[str, float] = {}
    for slot in _content.scheduled_slots():
        code = slot.get("module_code") or "?"
        totals[code] = totals.get(code, 0.0) + _slot_hours(slot)
    return [{"module_code": code, "hours": round(hours, 2)}
            for code, hours in sorted(totals.items())]


def _slot_hours(slot: dict) -> float:
    def minutes(value):
        try:
            hours, mins = str(value).split(":")[:2]
            return int(hours) * 60 + int(mins)
        except (ValueError, AttributeError):
            return None

    start, end = minutes(slot.get("start_time")), minutes(slot.get("end_time"))
    if start is None or end is None or end <= start:
        return 0.0
    return (end - start) / 60.0
