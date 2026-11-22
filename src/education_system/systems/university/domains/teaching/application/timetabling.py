"""Institution-wide constraint scheduling with versioned publication.

Activities can be typed in by hand, or built from the live timetable with
:func:`build_from_timetable` — one activity per published ``module_schedule``
slot, its cohort the module's programme year, its rooms those big enough for
its enrolment. Publishing a version built that way writes the moved slots
back to ``module_schedule`` and tells the students and staff affected, so the
published version *is* the timetable rather than a record beside it.

Slots are either opaque labels (``MON-09``), which collide only when equal,
or ``"Monday 09:00-11:00"``, which collide when the times overlap.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterable
from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection, transaction


_SLOT_LABEL = re.compile(r"^(\w+) (\d{2}:\d{2})-(\d{2}:\d{2})$")
_TEACHING_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
_DAY_START, _DAY_END = 9 * 60, 18 * 60


def _slots_overlap(a: str, b: str) -> bool:
    ma, mb = _SLOT_LABEL.match(str(a)), _SLOT_LABEL.match(str(b))
    if not (ma and mb):
        return a == b
    return ma.group(1) == mb.group(1) and ma.group(2) < mb.group(3) and ma.group(3) > mb.group(2)


def _collides(placed: dict, activity: dict, slot: str, room: str) -> bool:
    if not _slots_overlap(placed["slot"], slot):
        return False
    same_staff = placed.get("staff_id") is not None and \
        placed.get("staff_id") == activity.get("staff_id")
    shared = set(placed.get("cohorts", ())) & set(activity.get("cohorts", ()))
    return placed["room"] == room or same_staff or bool(shared)


def optimise(
    activities: Iterable[dict[str, Any]], slots: Iterable[str], rooms: Iterable[str],
    *, academic_year: str, created_by: str,
) -> str:
    """Allocate activities without room, staff or cohort collisions."""
    ordered = sorted(
        (dict(activity) for activity in activities),
        key=lambda item: len(item.get("allowed_slots") or list(slots)),
    )
    slot_values, room_values = list(slots), list(rooms)
    schedule: list[dict[str, Any]] = []

    def assign(index: int) -> bool:
        if index == len(ordered):
            return True
        activity = ordered[index]
        allowed = activity.get("allowed_slots") or slot_values
        for slot in allowed:
            for room in activity.get("allowed_rooms") or room_values:
                conflict = any(_collides(placed, activity, slot, room) for placed in schedule)
                if conflict:
                    continue
                schedule.append({**activity, "slot": slot, "room": room})
                if assign(index + 1):
                    return True
                schedule.pop()
        return False

    if not assign(0):
        raise ValueError("No timetable satisfies the supplied institutional constraints")
    input_blob = json.dumps(ordered, sort_keys=True, default=str)
    version_id = str(uuid.uuid4())
    with transaction() as conn:
        conn.execute(
            """INSERT INTO timetable_versions
                 (version_id, academic_year, input_hash, schedule_json, created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (
                version_id, academic_year,
                hashlib.sha256(input_blob.encode()).hexdigest(),
                json.dumps(schedule, sort_keys=True), created_by,
            ),
        )
    return version_id


def publish(version_id: str, *, approved_by: str) -> int:
    """Publish a version. A version built from the live timetable is also
    applied to it; returns how many weekly slots moved (0 for a hand-typed
    version, which stays a record)."""
    from education_system.systems.university.application.teaching import occurrences as tt
    with transaction() as conn:
        row = conn.execute(
            "SELECT schedule_json FROM timetable_versions WHERE version_id=?", (version_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Timetable version does not exist")
        moved, emails = _apply_to_timetable(conn, json.loads(row[0] or "[]"), approved_by)
        conn.execute(
            "UPDATE timetable_versions SET status='superseded' "
            "WHERE status='published' AND version_id<>?", (version_id,)
        )
        conn.execute(
            "UPDATE timetable_versions SET status='published', "
            "published_at=CURRENT_TIMESTAMP WHERE version_id=?", (version_id,)
        )
    tt.send_emails(emails)
    return moved


# ── building from, and applying to, the live timetable ─────────────────


def _minutes(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:5])


def _label(day: str, start: int, end: int) -> str:
    return f"{day} {start // 60:02d}:{start % 60:02d}-{end // 60:02d}:{end % 60:02d}"


def _candidate_slots(slot: dict, preferred_days: str) -> list[str]:
    """Hourly starts Mon–Fri 09:00–18:00 with the slot's own length, its
    current time first; days limited to the instructor's preference."""
    length = _minutes(slot["end_time"]) - _minutes(slot["start_time"])
    days = [d for d in _TEACHING_DAYS if not preferred_days
            or d.lower()[:3] in [p.strip().lower()[:3] for p in preferred_days.split(",")]]
    current = _label(slot["day_of_week"], _minutes(slot["start_time"]), _minutes(slot["end_time"]))
    out = [current]
    for day in days or _TEACHING_DAYS:
        for start in range(_DAY_START, _DAY_END - length + 1, 60):
            label = _label(day, start, start + length)
            if label != current:
                out.append(label)
    return out


def activities_from_timetable(conn) -> tuple[list[dict], list[str]]:
    """One activity per published weekly slot, plus every usable room."""
    from education_system.systems.university.application.teaching import occurrences as tt
    rooms = {str(r[0]): r[1] or 0 for r in conn.execute(
        "SELECT id, capacity FROM rooms WHERE COALESCE(is_active, 1) = 1")}
    activities = []
    for slot in tt.slots(conn):
        if not (slot["start_time"] and slot["end_time"]):
            continue
        module = conn.execute("SELECT course, year FROM modules WHERE module_code = ?",
                              (slot["module_code"],)).fetchone()
        prefs = conn.execute("SELECT preferred_days FROM instructors WHERE id = ?",
                             (slot["instructor_id"],)).fetchone() if slot["instructor_id"] else None
        need = tt.enrolled_for(conn, slot["module_code"], slot["section_id"])
        fit = [rid for rid, cap in rooms.items() if not cap or cap >= need]
        current = str(slot["room_id"]) if slot["room_id"] else None
        activities.append({
            "activity_id": f"slot:{slot['id']}", "module_code": slot["module_code"],
            "staff_id": slot["instructor_id"],
            "cohorts": [f"module:{slot['module_code']}"] + (
                [f"{module[0]}-Y{module[1]}"] if module and module[0] and module[1] else []),
            "allowed_slots": _candidate_slots(slot, (prefs[0] if prefs else "") or ""),
            "allowed_rooms": ([current] if current in fit else []) + [r for r in fit if r != current]
            or ([current] if current else ["(no room)"]),
        })
    return activities, list(rooms) or ["(no room)"]


def build_from_timetable(*, academic_year: str, created_by: str) -> str:
    """A draft version of the live timetable, re-solved for clashes."""
    with get_connection() as conn:
        activities, rooms = activities_from_timetable(conn)
    if not activities:
        raise ValueError("There are no published weekly sessions to timetable")
    slots = sorted({s for a in activities for s in a["allowed_slots"]})
    return optimise(activities, slots, rooms, academic_year=academic_year,
                    created_by=created_by)


def _apply_to_timetable(conn, schedule: list[dict], actor: str) -> tuple[int, list]:
    from education_system.systems.university.application.teaching import occurrences as tt
    moved, emails = 0, []
    for placed in schedule:
        slot_id = str(placed.get("activity_id", ""))
        match = _SLOT_LABEL.match(str(placed.get("slot", "")))
        if not slot_id.startswith("slot:") or not match:
            continue
        room = None if placed.get("room") in (None, "(no room)") else int(placed["room"])
        row = conn.execute("SELECT module_code, day_of_week, start_time, end_time, room_id, "
                           "section_id, instructor_id FROM module_schedule WHERE id = ?",
                           (int(slot_id[5:]),)).fetchone()
        if row is None or tuple(row)[1:5] == (match.group(1), match.group(2), match.group(3), room):
            continue
        conn.execute("UPDATE module_schedule SET day_of_week = ?, start_time = ?, end_time = ?, "
                     "room_id = ?, modified_date = CURRENT_TIMESTAMP WHERE id = ?",
                     (match.group(1), match.group(2), match.group(3), room, int(slot_id[5:])))
        moved += 1
        emails += tt.notify(conn, row[0], f"Timetable change: {row[0]}",
                            f"Your weekly {row[0]} session on {row[1]} {row[2]} now runs "
                            f"{match.group(1)} {match.group(2)}–{match.group(3)} "
                            f"(timetable published by {actor}).",
                            section_id=row[5], instructor_id=row[6])
    return moved, emails


def request_change(
    version_id: str, proposed: dict[str, Any], *, reason: str, requested_by: str
) -> str:
    request_id = str(uuid.uuid4())
    with transaction() as conn:
        conn.execute(
            """INSERT INTO timetable_change_requests
                 (request_id, version_id, reason, proposed_json, requested_by)
               VALUES (?, ?, ?, ?, ?)""",
            (request_id, version_id, reason, json.dumps(proposed), requested_by),
        )
    return request_id


def published_schedule() -> list[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT schedule_json FROM timetable_versions "
            "WHERE status='published' ORDER BY published_at DESC LIMIT 1"
        ).fetchone()
        return json.loads(row[0]) if row else []


def list_versions(limit: int = 100) -> list[dict[str, Any]]:
    """Newest-first versions without the schedule payload."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT version_id, academic_year, status, input_hash, created_by, "
            "created_at, published_at FROM timetable_versions "
            "ORDER BY created_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(row) for row in rows]


def version_record(version_id: str) -> dict[str, Any]:
    """One version with its decoded schedule under ``schedule``."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM timetable_versions WHERE version_id=?", (version_id,)
        ).fetchone()
    if row is None:
        raise ValueError("Timetable version does not exist")
    result = dict(row)
    result["schedule"] = json.loads(result.pop("schedule_json") or "[]")
    return result


def list_change_requests(version_id: str | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if version_id:
            rows = conn.execute(
                "SELECT * FROM timetable_change_requests WHERE version_id=? "
                "ORDER BY created_at DESC",
                (version_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM timetable_change_requests ORDER BY created_at DESC"
            ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "activities_from_timetable", "build_from_timetable", "list_change_requests",
    "list_versions", "optimise", "publish", "published_schedule", "request_change",
    "version_record",
]
