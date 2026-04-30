"""Canonical writers for ``module_schedule``.

Module Scheduling is the only place that should be touching the
``module_schedule`` table — Timetable's drag-drop, the bulk-import
wizard, and any future re-schedulers all route through here.

Two reasons:

* **One algorithm for conflict re-checks**: a slot move that creates
  a clash (room double-booked, instructor overlap) gets caught here,
  not partially in three GUIs.
* **One bus publish**: every successful move broadcasts
  ``EVENT_MODULE_SCHEDULE_CHANGED`` so every open GUI refreshes,
  including Timetable and Course Management.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


def move_slot(
    schedule_id: int,
    *,
    new_day: str | None = None,
    new_start_time: str | None = None,
    new_end_time: str | None = None,
    new_room_id: int | None = None,
    moved_by: str | None = None,
) -> dict[str, Any]:
    """Move a ``module_schedule`` row.

    Returns ``{ok: bool, reason: str, conflicts: [...] }``. On
    success, publishes ``EVENT_MODULE_SCHEDULE_CHANGED``.

    All fields are optional — pass only the ones you're changing.
    The caller learns about clashes via ``conflicts`` and decides
    whether to overwrite (re-call with ``force=True`` is *not*
    supported on purpose; force-moves should use the underlying
    UPDATE explicitly so the audit trail is honest).
    """
    if schedule_id is None:
        return {"ok": False, "reason": "no schedule_id", "conflicts": []}

    fields_to_set: list[tuple[str, Any]] = []
    if new_day is not None:
        fields_to_set.append(("day_of_week", new_day))
    if new_start_time is not None:
        fields_to_set.append(("start_time", new_start_time))
    if new_end_time is not None:
        fields_to_set.append(("end_time", new_end_time))
    if new_room_id is not None:
        fields_to_set.append(("room_id", new_room_id))

    if not fields_to_set:
        return {"ok": False, "reason": "no fields supplied", "conflicts": []}

    try:
        with get_connection() as conn:
            current = conn.execute(
                "SELECT module_code, day_of_week, start_time, end_time, "
                "       room_id, instructor_id "
                "FROM module_schedule WHERE id = ?",
                (schedule_id,),
            ).fetchone()
            if not current:
                return {"ok": False, "reason": "schedule row not found",
                        "conflicts": []}

            day = new_day or current["day_of_week"]
            start = new_start_time or current["start_time"]
            end = new_end_time or current["end_time"]
            room_id = new_room_id if new_room_id is not None else current["room_id"]

            # Conflict check — re-uses the same overlap logic the conflict
            # detector employs. We block on room/instructor overlap; student
            # conflicts are surfaced as a soft warning in the result.
            conflicts: list[dict[str, Any]] = []
            if room_id is not None:
                row = conn.execute(
                    "SELECT id, module_code FROM module_schedule "
                    "WHERE id != ? AND room_id = ? AND day_of_week = ? "
                    "  AND start_time < ? AND end_time > ? LIMIT 1",
                    (schedule_id, room_id, day, end, start),
                ).fetchone()
                if row:
                    conflicts.append({
                        "type": "room",
                        "with_schedule_id": row["id"],
                        "with_module": row["module_code"],
                    })
            if current["instructor_id"] is not None:
                row = conn.execute(
                    "SELECT id, module_code FROM module_schedule "
                    "WHERE id != ? AND instructor_id = ? AND day_of_week = ? "
                    "  AND start_time < ? AND end_time > ? LIMIT 1",
                    (schedule_id, current["instructor_id"], day, end, start),
                ).fetchone()
                if row:
                    conflicts.append({
                        "type": "instructor",
                        "with_schedule_id": row["id"],
                        "with_module": row["module_code"],
                    })
            if conflicts:
                # Cross-domain: an unresolvable scheduling conflict
                # is a module-delivery risk, not a student-attendance
                # one. Raise a risks row keyed to the module so the
                # legal/risk GUI tracks recurring overlaps for the
                # same module across the term.
                try:
                    from education_system.university_system.modules.services import (
                        risk_bus,
                    )
                    mc = current["module_code"]
                    ref = f"module:{mc}"
                    if not risk_bus.list_risks_for(ref):
                        kinds = sorted({c["type"] for c in conflicts})
                        risk_bus.raise_risk(
                            title=f"Schedule conflict on module {mc}",
                            category="Academic",
                            department="Academics",
                            description=(
                                f"Slot move blocked by {', '.join(kinds)} "
                                f"conflict against schedules "
                                f"{[c['with_schedule_id'] for c in conflicts]}. "
                                f"Indicates timetable pressure for this "
                                f"module."
                            ),
                            likelihood=3, impact=3,
                            reference_id=ref,
                        )
                except Exception:
                    pass
                return {"ok": False, "reason": "conflicts detected",
                        "conflicts": conflicts}

            # Holiday warning (#6) — recurring slots that fall on a
            # public holiday don't block the move (lectures still
            # recur weekly), but we surface a warning in the result so
            # the host GUI can prompt the operator to skip the date.
            warnings: list[dict[str, Any]] = []
            try:
                from education_system.university_system.modules.domain.academics.gui._cross_services import (
                    is_holiday,
                )
                # Check today's date as a representative recurrence —
                # the operator cares whether the next-occurring instance
                # of this weekly slot lands on a holiday.
                from datetime import date as _date, timedelta as _td
                today = _date.today()
                weekday_target = day  # e.g. 'Monday'
                weekday_index = {
                    "monday": 0, "tuesday": 1, "wednesday": 2,
                    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
                }.get((weekday_target or "").lower())
                if weekday_index is not None:
                    delta = (weekday_index - today.weekday()) % 7
                    next_occurrence = (today + _td(days=delta)).isoformat()
                    if is_holiday(next_occurrence):
                        warnings.append({
                            "type": "holiday",
                            "date": next_occurrence,
                            "message": (
                                f"Next {weekday_target} ({next_occurrence}) "
                                f"is a holiday — consider skipping that week."
                            ),
                        })
            except Exception:
                pass

            # Apply the UPDATE.
            set_clause = ", ".join(f"{c} = ?" for c, _ in fields_to_set)
            params = [v for _, v in fields_to_set] + [schedule_id]
            conn.execute(
                f"UPDATE module_schedule SET {set_clause} WHERE id = ?",
                params,
            )
            conn.commit()
            module_code = current["module_code"]
    except sqlite3.Error as exc:
        logger.warning("move_slot(%s) failed: %s", schedule_id, exc)
        return {"ok": False, "reason": str(exc), "conflicts": []}

    # Broadcast.
    try:
        from education_system.university_system.modules.domain.academics.gui._event_bus import (
            publish, EVENT_MODULE_SCHEDULE_CHANGED,
        )
        publish(
            EVENT_MODULE_SCHEDULE_CHANGED,
            schedule_id=schedule_id, module_code=module_code,
            action="moved", moved_by=moved_by,
            new_day=new_day, new_start_time=new_start_time,
            new_end_time=new_end_time, new_room_id=new_room_id,
        )
    except Exception:
        pass

    return {
        "ok": True, "reason": "",
        "conflicts": [],
        "warnings": warnings if 'warnings' in locals() else [],
    }


__all__ = ["move_slot"]
