"""Institution-wide constraint scheduling with versioned publication."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection, transaction


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
            for room in room_values:
                conflict = any(
                    placed["slot"] == slot
                    and (
                        placed["room"] == room
                        or placed.get("staff_id") == activity.get("staff_id")
                        or set(placed.get("cohorts", ())) & set(activity.get("cohorts", ()))
                    )
                    for placed in schedule
                )
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


def publish(version_id: str, *, approved_by: str) -> None:
    with transaction() as conn:
        if conn.execute(
            "SELECT 1 FROM timetable_versions WHERE version_id=?", (version_id,)
        ).fetchone() is None:
            raise ValueError("Timetable version does not exist")
        conn.execute(
            "UPDATE timetable_versions SET status='superseded' "
            "WHERE status='published' AND version_id<>?", (version_id,)
        )
        conn.execute(
            "UPDATE timetable_versions SET status='published', "
            "published_at=CURRENT_TIMESTAMP WHERE version_id=?", (version_id,)
        )


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


__all__ = ["optimise", "publish", "published_schedule", "request_change"]
