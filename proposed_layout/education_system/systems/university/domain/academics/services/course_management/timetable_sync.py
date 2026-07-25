"""Derive student / instructor timetables from module_schedule.

``module_schedule`` is the canonical recurring weekly slot table —
``(module_code, day_of_week, start_time, end_time, room_id,
instructor_id, semester, year)``. ``student_timetables`` and
``instructor_schedules`` are essentially views of that joined to
``student_modules`` and ``instructors`` respectively, but stored as
real tables so they can be queried fast for portal views.

This service keeps those derived tables in sync. Two trigger directions:

- A ``module_schedule`` row is added/updated/deleted → rebuild
  ``instructor_schedules`` and ``student_timetables`` rows for that
  slot's natural key.
- A ``student_modules`` row is added/dropped → add/remove that
  student's ``student_timetables`` rows for the module's currently-
  scheduled slots.

Idempotency: each sync deletes its own rows first (matched by natural
key) and re-inserts. Re-running for the same input produces the same
state without duplicates.
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def _connect():
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        return get_connection()
    except Exception as exc:
        logger.debug("DB unavailable for timetable sync: %s", exc)
        return None


def _time_slot(start_time: Optional[str], end_time: Optional[str]) -> str:
    if not (start_time and end_time):
        return ""
    return f"{start_time}-{end_time}"


def _resolve_room_name(conn, room_id: Optional[int]) -> str:
    """Translate a rooms.id into the human-readable label used by the
    student-timetable views."""
    if not room_id:
        return ""
    try:
        row = conn.execute(
            "SELECT COALESCE(room_name, room_number, '') "
            "FROM rooms WHERE id = ?",
            (room_id,),
        ).fetchone()
        return (row[0] or "") if row else ""
    except Exception:
        return ""


# ── Rebuild from a module_schedule row ─────────────────────────────────


def sync_for_module_schedule(schedule_id: int) -> None:
    """Refresh derived timetables to reflect the current state of one
    module_schedule row.

    Deletes any prior ``instructor_schedules`` / ``student_timetables``
    rows that match the slot's (module, day, time, semester, year) key,
    then re-creates them from the live data."""
    conn = _connect()
    if conn is None:
        return
    try:
        with conn:
            slot = conn.execute(
                """SELECT module_code, day_of_week, start_time, end_time,
                          room_id, instructor_id, semester, year
                   FROM module_schedule WHERE id = ?""",
                (schedule_id,),
            ).fetchone()
            if not slot:
                return
            (mod, day, st, et, rid, inst, sem, yr) = slot
            time_slot = _time_slot(st, et)
            room_name = _resolve_room_name(conn, rid)
            ay = str(yr) if yr else None

            # Wipe any prior derived rows for this natural key so a
            # rebuild produces a clean state (handles rename/move).
            conn.execute(
                """DELETE FROM instructor_schedules
                   WHERE module_code = ?
                     AND COALESCE(day_of_week,'') = COALESCE(?,'')
                     AND COALESCE(time_slot,'') = COALESCE(?,'')
                     AND COALESCE(semester,'') = COALESCE(?,'')
                     AND COALESCE(academic_year,'') = COALESCE(?,'')""",
                (mod, day, time_slot, sem, ay),
            )
            conn.execute(
                """DELETE FROM student_timetables
                   WHERE module_code = ?
                     AND COALESCE(day_of_week,'') = COALESCE(?,'')
                     AND COALESCE(time_slot,'') = COALESCE(?,'')
                     AND COALESCE(semester,'') = COALESCE(?,'')
                     AND COALESCE(academic_year,'') = COALESCE(?,'')""",
                (mod, day, time_slot, sem, ay),
            )

            if inst:
                conn.execute(
                    """INSERT INTO instructor_schedules
                       (instructor_id, module_code, day_of_week,
                        time_slot, room, academic_year, semester)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (inst, mod, day, time_slot, room_name, ay, sem),
                )

            # Fan out to enrolled students. We treat every active
            # enrolment as in-scope for the slot's semester/year — a
            # finer-grained filter would need student_modules to also
            # carry semester/year reliably.
            students = conn.execute(
                "SELECT student_id FROM student_modules "
                "WHERE module_code = ? "
                "  AND COALESCE(status,'') != 'cancelled'",
                (mod,),
            ).fetchall()
            for (sid,) in students:
                conn.execute(
                    """INSERT INTO student_timetables
                       (student_id, module_code, day_of_week, time_slot,
                        room, instructor_id, academic_year, semester)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (sid, mod, day, time_slot, room_name, inst, ay, sem),
                )
        logger.info(
            "Synced timetables from module_schedule#%s (%s on %s %s, "
            "%d student row(s))",
            schedule_id, mod, day, time_slot, len(students),
        )
    except Exception as exc:
        logger.error("sync_for_module_schedule failed: %s", exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def unsync_for_module_schedule(schedule_id: int) -> None:
    """Remove derived rows for a module_schedule that's about to be
    deleted. Caller passes the id *before* the DELETE so we can read
    the natural key from it."""
    conn = _connect()
    if conn is None:
        return
    try:
        with conn:
            slot = conn.execute(
                """SELECT module_code, day_of_week, start_time, end_time,
                          semester, year
                   FROM module_schedule WHERE id = ?""",
                (schedule_id,),
            ).fetchone()
            if not slot:
                return
            (mod, day, st, et, sem, yr) = slot
            time_slot = _time_slot(st, et)
            ay = str(yr) if yr else None
            conn.execute(
                """DELETE FROM instructor_schedules
                   WHERE module_code = ?
                     AND COALESCE(day_of_week,'') = COALESCE(?,'')
                     AND COALESCE(time_slot,'') = COALESCE(?,'')
                     AND COALESCE(semester,'') = COALESCE(?,'')
                     AND COALESCE(academic_year,'') = COALESCE(?,'')""",
                (mod, day, time_slot, sem, ay),
            )
            conn.execute(
                """DELETE FROM student_timetables
                   WHERE module_code = ?
                     AND COALESCE(day_of_week,'') = COALESCE(?,'')
                     AND COALESCE(time_slot,'') = COALESCE(?,'')
                     AND COALESCE(semester,'') = COALESCE(?,'')
                     AND COALESCE(academic_year,'') = COALESCE(?,'')""",
                (mod, day, time_slot, sem, ay),
            )
    except Exception as exc:
        logger.error("unsync_for_module_schedule failed: %s", exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ── Rebuild from a student_modules change ──────────────────────────────


def sync_for_student_enrolment(student_id: str, module_code: str) -> int:
    """Add ``student_timetables`` rows for every ``module_schedule``
    slot the module currently has. Returns the number of rows added.
    Idempotent — existing rows for the same key are left intact."""
    if not student_id or not module_code:
        return 0
    conn = _connect()
    if conn is None:
        return 0
    try:
        added = 0
        with conn:
            slots = conn.execute(
                """SELECT day_of_week, start_time, end_time, room_id,
                          instructor_id, semester, year
                   FROM module_schedule WHERE module_code = ?""",
                (module_code,),
            ).fetchall()
            for (day, st, et, rid, inst, sem, yr) in slots:
                time_slot = _time_slot(st, et)
                ay = str(yr) if yr else None
                room_name = _resolve_room_name(conn, rid)

                exists = conn.execute(
                    """SELECT 1 FROM student_timetables
                       WHERE student_id = ? AND module_code = ?
                         AND COALESCE(day_of_week,'') = COALESCE(?,'')
                         AND COALESCE(time_slot,'') = COALESCE(?,'')
                         AND COALESCE(semester,'') = COALESCE(?,'')
                         AND COALESCE(academic_year,'') = COALESCE(?,'')
                       LIMIT 1""",
                    (str(student_id), module_code, day, time_slot,
                     sem, ay),
                ).fetchone()
                if exists:
                    continue
                conn.execute(
                    """INSERT INTO student_timetables
                       (student_id, module_code, day_of_week, time_slot,
                        room, instructor_id, academic_year, semester)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(student_id), module_code, day, time_slot,
                     room_name, inst, ay, sem),
                )
                added += 1
        return added
    except Exception as exc:
        logger.error("sync_for_student_enrolment failed: %s", exc)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def clear_for_student_drop(student_id: str, module_code: str) -> int:
    """Remove all ``student_timetables`` rows for this (student, module)
    pair. Returns the number of rows removed."""
    if not student_id or not module_code:
        return 0
    conn = _connect()
    if conn is None:
        return 0
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM student_timetables "
                "WHERE student_id = ? AND module_code = ?",
                (str(student_id), module_code),
            )
            return cur.rowcount or 0
    except Exception as exc:
        logger.error("clear_for_student_drop failed: %s", exc)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass
