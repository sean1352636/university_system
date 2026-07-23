"""Materialise attendance sessions from module_schedule on demand.

The attendance domain stores per-occurrence sessions in
``attendance_sessions`` and per-student rows in ``attendance_records``.
Historically those have been created by hand — an instructor opens the
register and is presented with a blank session, or the recording call
inserts records without a session_id.

This service connects ``attendance_sessions`` back to its source of
truth, ``module_schedule``: given a ``(module_code, date)`` pair, find
the matching weekly slot and find-or-create the session row. Records
written via :func:`record_attendance_with_session` get the session_id
stamped automatically.

Two complementary use modes:

- **Lazy** — :func:`find_or_create_session` is called from the
  attendance recording flow when a marker opens the register for a
  given date.
- **Eager** — :func:`generate_sessions_for_module` materialises rows
  for an entire date range in one go (useful for dashboards that need
  to count expected sessions without driving the recording flow).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


def _connect():
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        return get_connection()
    except Exception as exc:
        logger.debug("DB unavailable for attendance session sync: %s", exc)
        return None


_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday",
              "Friday", "Saturday", "Sunday")


def _day_of_week(date_str: str) -> Optional[str]:
    try:
        return _DAY_NAMES[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except (ValueError, TypeError):
        return None


def _session_id(module_code: str, date_str: str, start_time: str) -> str:
    """Deterministic session id keyed on module + date + start time, so
    a module with multiple slots on one day still gets distinct ids."""
    safe = (start_time or "00:00").replace(":", "")
    return f"MS-{module_code}-{date_str}-{safe}"


def _resolve_room_name(conn, room_id: Optional[int]) -> str:
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


def find_or_create_session(module_code: str, date_str: str
                           ) -> Optional[str]:
    """Find or create an attendance_sessions row for the given module
    and date by consulting module_schedule.

    Returns the ``session_id`` text key, or None if no module_schedule
    slot matches the day-of-week (e.g. asking about a Saturday for a
    weekday-only module).
    """
    if not module_code or not date_str:
        return None
    dow = _day_of_week(date_str)
    if not dow:
        return None
    conn = _connect()
    if conn is None:
        return None
    try:
        with conn:
            # If multiple slots exist (e.g. lecture + lab on the same
            # day), pick the earliest start_time deterministically.
            slot = conn.execute(
                """SELECT start_time, end_time, room_id, instructor_id
                   FROM module_schedule
                   WHERE module_code = ? AND day_of_week = ?
                     AND COALESCE(status,'') != 'cancelled'
                   ORDER BY start_time ASC LIMIT 1""",
                (module_code, dow),
            ).fetchone()
            if not slot:
                return None
            start_time, end_time, room_id, _instr = slot
            sid = _session_id(module_code, date_str, start_time or "")
            room_name = _resolve_room_name(conn, room_id)

            existing = conn.execute(
                "SELECT session_id FROM attendance_sessions "
                "WHERE session_id = ?",
                (sid,),
            ).fetchone()
            if existing:
                return sid

            conn.execute(
                """INSERT INTO attendance_sessions
                   (session_id, module_code, date, start_time, end_time,
                    location_name, session_type, status, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, 'lecture', 'active',
                           'module_schedule')""",
                (sid, module_code, date_str, start_time, end_time,
                 room_name),
            )
            return sid
    except Exception as exc:
        logger.error("find_or_create_session failed: %s", exc)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def generate_sessions_for_module(module_code: str,
                                  start_date: str,
                                  end_date: str) -> List[str]:
    """Walk every date in the range and call :func:`find_or_create_session`
    for it. Returns the list of session ids that exist (created or
    pre-existing) at the end.
    """
    out: List[str] = []
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d").date()
        e = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return out
    if e < s:
        return out

    cur = s
    while cur <= e:
        sid = find_or_create_session(module_code, cur.isoformat())
        if sid:
            out.append(sid)
        cur += timedelta(days=1)
    return out


def get_canonical_roster(module_code: str) -> List[str]:
    """Return the active enrolment for a module straight from
    ``student_modules``. Lets an attendance UI render every student who
    *should* be present, in the same shape the exam scheduler uses."""
    if not module_code:
        return []
    conn = _connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT student_id FROM student_modules "
            "WHERE module_code = ? "
            "  AND COALESCE(status,'') != 'cancelled' "
            "ORDER BY student_id",
            (module_code,),
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception as exc:
        logger.debug("get_canonical_roster failed: %s", exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass
