"""Mirror teaching assignments into the HR workload tables.

When a course schedule names an instructor, that's a real teaching
commitment. HR's workload planning lives in two tables:

- ``workload_allocations`` — itemised activities (teaching a specific
  course, supervising research, sitting on a committee, …) with weekly
  hours and a weighting factor.
- ``staff_workload`` — aggregate per (user, academic_year, semester)
  rolling up teaching / research / admin / service hours.

This service keeps the teaching slice in sync with whatever course
management writes to ``course_schedule``. Allocation rows are matched by
``(user_id, course_code, year, semester)`` so re-running for the same
schedule updates the existing row rather than producing duplicates.

Note on identifiers: ``course_schedule.instructor_id`` is an INTEGER
referring to ``instructors.id``. ``workload_allocations.user_id`` is
TEXT — we use the instructor id stringified, matching the convention
already in use by other workload writers.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default weighting for direct teaching hours. Workload planning often
# multiplies contact time (e.g. ×1.5) to account for prep/marking; this
# matches a typical UK norm so the rolled-up totals look right.
DEFAULT_TEACHING_WEIGHT = 1.5


def _connect():
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        return get_connection()
    except Exception as exc:
        logger.debug("DB unavailable for workload sync: %s", exc)
        return None


def _hours_per_week(start_time: Optional[str], end_time: Optional[str],
                    days_csv: Optional[str]) -> float:
    """Compute weekly contact hours from a course_schedule row.

    Returns 0.0 if the slot is incomplete (TBA times or no days).
    """
    if not (start_time and end_time and days_csv):
        return 0.0
    try:
        from datetime import datetime
        s = datetime.strptime(start_time, "%H:%M")
        e = datetime.strptime(end_time, "%H:%M")
        if e <= s:
            return 0.0
        per_session = (e - s).total_seconds() / 3600.0
    except ValueError:
        return 0.0
    days = [d.strip() for d in days_csv.split(",") if d.strip()]
    return round(per_session * len(days), 2)


def _recompute_staff_workload(conn, user_id: str, academic_year: str,
                              semester: Optional[str]) -> None:
    """Roll teaching allocations up into the staff_workload aggregate."""
    teaching = conn.execute(
        "SELECT COALESCE(SUM(weighted_hours), 0) "
        "FROM workload_allocations "
        "WHERE user_id = ? AND academic_year = ? "
        "  AND COALESCE(semester,'') = COALESCE(?,'') "
        "  AND activity_type = 'teaching'",
        (user_id, academic_year, semester),
    ).fetchone()[0] or 0

    existing = conn.execute(
        "SELECT workload_id FROM staff_workload "
        "WHERE user_id = ? AND academic_year = ? "
        "  AND COALESCE(semester,'') = COALESCE(?,'')",
        (user_id, academic_year, semester),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE staff_workload SET teaching_hours = ?, "
            "  updated_at = datetime('now') WHERE workload_id = ?",
            (teaching, existing[0]),
        )
    else:
        conn.execute(
            "INSERT INTO staff_workload "
            "(user_id, academic_year, semester, teaching_hours) "
            "VALUES (?, ?, ?, ?)",
            (user_id, academic_year, semester, teaching),
        )


def record_teaching_workload(instructor_id: Optional[int],
                              course_code: str,
                              academic_year: Optional[str],
                              semester: Optional[str],
                              start_time: Optional[str],
                              end_time: Optional[str],
                              days_of_week: Optional[str],
                              weight: float = DEFAULT_TEACHING_WEIGHT) -> bool:
    """Upsert a teaching allocation for the instructor on this course
    and refresh the staff_workload aggregate. Returns True on success.

    Idempotent: calling again for the same (instructor, course, year,
    semester) updates the same allocation row.
    """
    if instructor_id is None or not course_code or not academic_year:
        return False
    conn = _connect()
    if conn is None:
        return False
    user_id = str(instructor_id)
    contact_h = _hours_per_week(start_time, end_time, days_of_week)
    weighted = round(contact_h * float(weight), 2)
    try:
        with conn:
            existing = conn.execute(
                "SELECT allocation_id FROM workload_allocations "
                "WHERE user_id = ? AND academic_year = ? "
                "  AND COALESCE(semester,'') = COALESCE(?,'') "
                "  AND activity_name = ? AND activity_type = 'teaching'",
                (user_id, academic_year, semester, course_code),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE workload_allocations SET "
                    "  hours_per_week = ?, weighting_factor = ?, "
                    "  weighted_hours = ?, updated_at = datetime('now') "
                    "WHERE allocation_id = ?",
                    (contact_h, weight, weighted, existing[0]),
                )
            else:
                conn.execute(
                    "INSERT INTO workload_allocations "
                    "(user_id, academic_year, semester, activity_name, "
                    " activity_type, hours_per_week, weighting_factor, "
                    " weighted_hours, created_by) "
                    "VALUES (?, ?, ?, ?, 'teaching', ?, ?, ?, ?)",
                    (user_id, academic_year, semester, course_code,
                     contact_h, weight, weighted, "course_management"),
                )
            _recompute_staff_workload(conn, user_id, academic_year, semester)
        logger.info(
            "Workload synced: instructor %s teaching %s for %s %s "
            "(%.1fh/wk × %.1f = %.1f weighted)",
            instructor_id, course_code, academic_year, semester or "year",
            contact_h, weight, weighted,
        )
        return True
    except Exception as exc:
        logger.error("record_teaching_workload failed: %s", exc)
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def clear_teaching_workload(instructor_id: Optional[int],
                             course_code: str,
                             academic_year: Optional[str],
                             semester: Optional[str]) -> bool:
    """Remove the teaching allocation when an instructor stops teaching
    a course (schedule deleted, instructor reassigned). Refreshes the
    staff_workload aggregate. Returns True if a row was removed.
    """
    if instructor_id is None or not course_code:
        return False
    conn = _connect()
    if conn is None:
        return False
    user_id = str(instructor_id)
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM workload_allocations "
                "WHERE user_id = ? AND activity_name = ? "
                "  AND activity_type = 'teaching' "
                "  AND COALESCE(academic_year,'') = COALESCE(?,'') "
                "  AND COALESCE(semester,'') = COALESCE(?,'')",
                (user_id, course_code, academic_year, semester),
            )
            removed = (cur.rowcount or 0) > 0
            if academic_year:
                _recompute_staff_workload(
                    conn, user_id, academic_year, semester)
        return removed
    except Exception as exc:
        logger.error("clear_teaching_workload failed: %s", exc)
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass
