"""Cross-domain staff/HR services for the scheduling GUIs.

HR is the canonical writer of staff/instructor records and
availability. Module Scheduling, Exam, Timetable, and Grade should
read from here rather than touching the underlying tables, so that:

* A new "qualifications" rule, leave window, or contract field added
  in HR shows up everywhere immediately.
* Sickness / leave / sabbatical writes broadcast on the bus
  (``EVENT_STAFF_AVAILABILITY_CHANGED``) so every open scheduler
  refreshes.

Public surface:

- ``is_qualified_for(instructor_id, module_code)`` → bool
- ``is_available_on(instructor_id, date)``       → bool
- ``list_unavailable_dates(instructor_id, ...)``  → list[date strings]
- ``publish_availability_change(staff_id, ...)``  → fires the bus
- ``update_instructor(instructor_id, **fields)``  → bool, single writer

Soft-fails open everywhere — a missing qualifications table or a
broken HR query must never block legitimate scheduling.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.post_18.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Qualifications
# ---------------------------------------------------------------------------

def is_qualified_for(instructor_id: int | str, module_code: str) -> bool:
    """Return True if the instructor is recorded as qualified for the module.

    Reads ``teaching_qualifications`` matched on ``user_id`` and
    either ``course_code`` (preferred) or ``subject_area`` (the
    department/subject the module belongs to). Verified rows count
    as qualified; unverified rows count as a soft pass with a
    warning log so partial deployments still work.

    Returns ``True`` if the qualifications table is missing or empty
    for this instructor — we never block scheduling on absent data.
    """
    if instructor_id is None or not module_code:
        return True
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='teaching_qualifications'"
            ).fetchone()
            if not tbl:
                return True
            rows = conn.execute(
                "SELECT verified, course_code, subject_area "
                "FROM teaching_qualifications WHERE user_id = ?",
                (str(instructor_id),),
            ).fetchall()
            if not rows:
                return True

            mc = module_code.strip().lower()
            # Pull the module's department for subject-area fallback.
            dept = None
            try:
                row = conn.execute(
                    "SELECT department FROM modules WHERE module_code = ?",
                    (module_code,),
                ).fetchone()
                if row:
                    dept = (row[0] or "").strip().lower()
            except sqlite3.OperationalError:
                pass

            for r in rows:
                course_code = (r["course_code"] or "").strip().lower()
                subject = (r["subject_area"] or "").strip().lower()
                if course_code and course_code == mc:
                    if not r["verified"]:
                        logger.info(
                            "instructor %s has unverified qualification "
                            "for %s — allowing", instructor_id, module_code,
                        )
                    return True
                if dept and subject and subject == dept:
                    return True
            return False
    except Exception as exc:
        logger.warning("is_qualified_for(%s, %s) failed: %s — allowing",
                       instructor_id, module_code, exc)
        return True


# ---------------------------------------------------------------------------
# Availability (leave / sickness / sabbatical)
# ---------------------------------------------------------------------------

def is_available_on(instructor_id: int | str, on_date: str) -> bool:
    """Return False if the instructor is on approved leave on ``on_date``."""
    if instructor_id is None or not on_date:
        return True
    target = on_date[:10]
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='leave_requests'"
            ).fetchone()
            if not tbl:
                return True
            row = conn.execute(
                "SELECT 1 FROM leave_requests "
                "WHERE user_id = ? AND LOWER(status) = 'approved' "
                "  AND start_date <= ? AND end_date >= ? LIMIT 1",
                (str(instructor_id), target, target),
            ).fetchone()
            return row is None
    except Exception as exc:
        logger.warning("is_available_on(%s, %s) failed: %s",
                       instructor_id, on_date, exc)
        return True


def list_unavailable_ranges(instructor_id: int | str | None = None,
                            *, since: str | None = None) -> list[dict[str, Any]]:
    """List approved leave windows. Empty list on any failure.

    ``since`` is a YYYY-MM-DD floor; default is today.
    """
    from datetime import date as _date
    since = (since or _date.today().isoformat())[:10]
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='leave_requests'"
            ).fetchone()
            if not tbl:
                return out
            sql = (
                "SELECT user_id, leave_type_id, start_date, end_date, status "
                "FROM leave_requests "
                "WHERE LOWER(status) = 'approved' AND end_date >= ? "
            )
            params: list[Any] = [since]
            if instructor_id is not None:
                sql += "AND user_id = ? "
                params.append(str(instructor_id))
            sql += "ORDER BY start_date"
            for r in conn.execute(sql, tuple(params)).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_unavailable_ranges failed: %s", exc)
    return out


# ---------------------------------------------------------------------------
# Bus publishers
# ---------------------------------------------------------------------------

def publish_availability_change(staff_id: int | str,
                                *, action: str = "updated",
                                start_date: str | None = None,
                                end_date: str | None = None,
                                leave_type: str | None = None,
                                source: str | None = None) -> None:
    """Broadcast that ``staff_id``'s availability has changed.

    Subscribers (Module Scheduling, Exam, Timetable, Grade) repaint
    the affected slots / queues. Best-effort — never raises.
    """
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import (
            publish, EVENT_STAFF_AVAILABILITY_CHANGED,
        )
        publish(
            EVENT_STAFF_AVAILABILITY_CHANGED,
            staff_id=str(staff_id), action=action,
            start_date=start_date, end_date=end_date,
            leave_type=leave_type, source=source,
        )
    except Exception as exc:
        logger.debug("availability bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Single-writer instructor mutation
# ---------------------------------------------------------------------------

_INSTRUCTOR_WRITABLE = (
    "first_name", "last_name", "email", "department", "specialization",
    "max_courses_per_semester", "max_hours_per_week",
    "preferred_days", "preferred_times", "status", "is_active",
)


def update_instructor(instructor_id: int, **fields: Any) -> bool:
    """Canonical update path for ``instructors``.

    Only fields in ``_INSTRUCTOR_WRITABLE`` are persisted; unknown
    keys are silently ignored so callers can pass a wider dict
    without worrying. Returns True on a successful UPDATE.
    """
    if instructor_id is None:
        return False
    payload = {k: v for k, v in fields.items() if k in _INSTRUCTOR_WRITABLE}
    if not payload:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in payload)
    params = list(payload.values()) + [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        int(instructor_id),
    ]
    try:
        with get_connection() as conn:
            conn.execute(
                f"UPDATE instructors SET {set_clause}, updated_at = ? "
                f"WHERE id = ?",
                params,
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("update_instructor(%s) failed: %s",
                       instructor_id, exc)
        return False


__all__ = [
    "is_qualified_for",
    "is_available_on",
    "list_unavailable_ranges",
    "publish_availability_change",
    "update_instructor",
]
