"""Mirror recurring lectures from module_schedule onto the academic
calendar.

The university's master calendar (``academic_calendar_events``) already
shows exams, semester periods and registration windows (added by the
exam scheduler and the calendar service). Recurring lectures are the
natural third stream: students and staff pulling up the calendar
expect to see lecture slots there too.

Each ``module_schedule`` row maps to one calendar event spanning the
semester: ``date_start`` is the first occurrence of the slot's
``day_of_week`` on or after the semester start, ``date_end`` is the
last occurrence on or before the semester end. The description names
the recurrence pattern (e.g. "Weekly Monday 10:00–11:00 in Hall A").

If no ``semesters`` row matches the slot's (academic_year, semester),
a 16-week window from today is used as a fallback so the entry is
still useful for ad-hoc setups.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_TERM_WEEKS = 16

_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday",
              "Friday", "Saturday", "Sunday")


def _connect():
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        return get_connection()
    except Exception as exc:
        logger.debug("DB unavailable for lecture calendar sync: %s", exc)
        return None


def _calendar_event_id(module_schedule_id: int) -> str:
    return f"LEC-{module_schedule_id}"


def _resolve_semester_span(conn, semester: Optional[str],
                           year) -> Tuple[str, str]:
    """Return ``(start_date, end_date)`` for the slot's semester, or a
    16-week default starting today if no row matches."""
    today = datetime.now().date()
    fallback_end = today + timedelta(weeks=_DEFAULT_TERM_WEEKS)

    if not semester or year is None:
        return today.isoformat(), fallback_end.isoformat()
    try:
        # academic_year_id can take many forms ("2099-2100", "2099/2100",
        # or just "2099"); match against a few likely shapes.
        candidates = {str(year), f"{year}-{int(year) + 1}",
                      f"{year}/{int(year) + 1}"}
        placeholders = ",".join(["?"] * len(candidates))
        row = conn.execute(
            f"SELECT start_date, end_date FROM semesters "  # nosec B608
            f"WHERE name = ? AND academic_year_id IN ({placeholders}) "
            f"LIMIT 1",
            (semester, *candidates),
        ).fetchone()
        if row and row[0] and row[1]:
            return row[0], row[1]
    except Exception:
        pass
    return today.isoformat(), fallback_end.isoformat()


def _first_dow_on_or_after(date_str: str, dow_name: str) -> Optional[str]:
    """Return the first ``date >= date_str`` whose weekday matches
    ``dow_name`` (e.g. 'Monday'). Returns the ISO date or None."""
    try:
        target = _DAY_NAMES.index(dow_name)
    except ValueError:
        return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    delta = (target - d.weekday()) % 7
    return (d + timedelta(days=delta)).isoformat()


def _last_dow_on_or_before(date_str: str, dow_name: str) -> Optional[str]:
    try:
        target = _DAY_NAMES.index(dow_name)
    except ValueError:
        return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    delta = (d.weekday() - target) % 7
    return (d - timedelta(days=delta)).isoformat()


def _resolve_room_name(conn, room_id) -> str:
    if not room_id:
        return ""
    try:
        row = conn.execute(
            "SELECT COALESCE(room_name, room_number, '') FROM rooms "
            "WHERE id = ?",
            (room_id,),
        ).fetchone()
        return (row[0] or "") if row else ""
    except Exception:
        return ""


def sync_lecture_to_calendar(module_schedule_id: int) -> bool:
    """Upsert one ``academic_calendar_events`` row for this lecture slot.

    Idempotent — calling again refreshes the row in place. Returns
    True if a row was written, False if the slot doesn't exist or
    the necessary fields are missing.
    """
    conn = _connect()
    if conn is None:
        return False
    try:
        with conn:
            slot = conn.execute(
                """SELECT module_code, day_of_week, start_time, end_time,
                          room_id, semester, year
                   FROM module_schedule WHERE id = ?""",
                (module_schedule_id,),
            ).fetchone()
            if not slot:
                return False
            (mod, dow, st, et, rid, sem, yr) = slot
            if not (dow and st and et):
                return False  # Nothing useful to surface

            sem_start, sem_end = _resolve_semester_span(conn, sem, yr)
            date_start = _first_dow_on_or_after(sem_start, dow) or sem_start
            date_end = _last_dow_on_or_before(sem_end, dow) or sem_end
            if date_end < date_start:
                date_end = date_start

            room_name = _resolve_room_name(conn, rid)
            event_id = _calendar_event_id(module_schedule_id)
            name = f"Lecture: {mod} ({dow})"
            description = (
                f"Weekly {dow} {st}–{et}"
                + (f" in {room_name}" if room_name else "")
                + (f" — {sem} {yr}" if sem and yr else "")
            )

            now = datetime.now().isoformat()
            existing = conn.execute(
                "SELECT 1 FROM academic_calendar_events WHERE id = ?",
                (event_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE academic_calendar_events
                       SET name = ?, date_start = ?, date_end = ?,
                           description = ?, event_type = 'Lecture',
                           last_modified = ?
                       WHERE id = ?""",
                    (name, date_start, date_end, description, now, event_id),
                )
            else:
                conn.execute(
                    """INSERT INTO academic_calendar_events
                       (id, name, date_start, date_end, description,
                        event_type, date_added, last_modified)
                       VALUES (?, ?, ?, ?, ?, 'Lecture', ?, ?)""",
                    (event_id, name, date_start, date_end, description,
                     now, now),
                )
        logger.info(
            "Synced module_schedule#%s to calendar (%s %s %s–%s)",
            module_schedule_id, mod, dow, date_start, date_end,
        )
        return True
    except Exception as exc:
        logger.error("sync_lecture_to_calendar failed: %s", exc)
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def remove_lecture_from_calendar(module_schedule_id: int) -> bool:
    """Delete the calendar event linked to a module_schedule row."""
    conn = _connect()
    if conn is None:
        return False
    try:
        with conn:
            conn.execute(
                "DELETE FROM academic_calendar_events WHERE id = ?",
                (_calendar_event_id(module_schedule_id),),
            )
        return True
    except Exception as exc:
        logger.error("remove_lecture_from_calendar failed: %s", exc)
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass
