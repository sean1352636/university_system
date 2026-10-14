"""Push virtual-session attendance into the central attendance records.

``session_participants.attendance_status`` used to be the only place an
online session's attendance was written. Nothing outside this package
read that table, so a student marked absent from an online lecture was
absent nowhere else — not in the attendance reports, not in the risk
jobs, not in the absence dashboard. Online teaching simply did not
count towards attendance.

This module copies those participant rows into ``attendance_records``,
the table the rest of the university reads, using the same columns the
QR and manual check-in paths write. It is deliberately a one-way copy
run when a session ends: the virtual tables stay the working record of
what happened in the meeting, and ``attendance_records`` becomes the
single place anything asks "did this student attend?".
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# session_participants.attendance_status -> attendance_records.status.
# 'left_early' counts as attended: the student was present, and the
# duration is preserved in the note rather than being lost as an absence.
_STATUS_MAP = {
    "present": "Present",
    "late": "Late",
    "left_early": "Present",
    "absent": "Absent",
}

CHECK_IN_METHOD = "virtual"
RECORDED_BY = "Virtual Classroom"


def _session_id_key(virtual_session_id) -> str:
    """Namespaced key for attendance_records.session_id.

    That column holds free text (UUIDs from QR sessions, timetable keys
    from module scheduling), so virtual sessions get a ``VC-`` prefix
    to keep their integer IDs from colliding with anything else.
    """
    return f"VC-{virtual_session_id}"


def _resolve_module_code(conn, classroom_row) -> Optional[str]:
    """Work out which module a classroom's attendance belongs to.

    ``virtual_classrooms.module_code`` is the authoritative answer when
    set. Older rows only carry ``course_id``, which holds a course code
    ('CS'), not a module code ('CS101') — attendance is recorded per
    module, so a course-only classroom cannot be synced and says so
    rather than inventing a module.
    """
    keys = classroom_row.keys() if hasattr(classroom_row, "keys") else []
    module_code = classroom_row["module_code"] if "module_code" in keys else None
    if module_code:
        return str(module_code)

    course_id = classroom_row["course_id"] if "course_id" in keys else None
    if not course_id:
        return None
    # A course whose code doubles as a module code (single-module courses)
    # is safe to use; anything else is ambiguous.
    row = conn.execute(
        "SELECT module_code FROM modules WHERE module_code = ?",
        (str(course_id),),
    ).fetchone()
    return str(course_id) if row else None


def ensure_module_code_column(conn) -> None:
    """Add ``virtual_classrooms.module_code`` if this DB predates it."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(virtual_classrooms)")}
    if "module_code" not in cols:
        conn.execute("ALTER TABLE virtual_classrooms ADD COLUMN module_code TEXT")


def sync_session_attendance(session_id: int, db_path: Optional[str] = None,
                            conn=None) -> Dict[str, Any]:
    """Copy one virtual session's participants into ``attendance_records``.

    Returns a summary dict with ``written``, ``skipped``, ``module_code``
    and ``reason`` (set when nothing could be written). Safe to call
    repeatedly — a participant already recorded for that session is
    updated rather than duplicated.
    """
    summary: Dict[str, Any] = {
        "session_id": session_id, "written": 0, "skipped": 0,
        "module_code": None, "reason": None,
    }

    owns_conn = conn is None
    if owns_conn:
        try:
            from education_system.systems.university.infrastructure.database.db import (
                get_connection,
            )
            conn = get_connection(db_path) if db_path else get_connection()
        except Exception as exc:
            summary["reason"] = f"database unavailable: {exc}"
            logger.debug("attendance sync could not connect", exc_info=True)
            return summary

    try:
        ensure_module_code_column(conn)

        session = conn.execute(
            "SELECT s.session_id, s.classroom_id, s.start_time, s.actual_start_time "
            "FROM virtual_sessions s WHERE s.session_id = ?",
            (session_id,),
        ).fetchone()
        if session is None:
            summary["reason"] = "session not found"
            return summary

        classroom = conn.execute(
            "SELECT * FROM virtual_classrooms WHERE classroom_id = ?",
            (session["classroom_id"],),
        ).fetchone()
        if classroom is None:
            summary["reason"] = "classroom not found"
            return summary

        module_code = _resolve_module_code(conn, classroom)
        if not module_code:
            summary["reason"] = (
                "no module_code on the classroom — attendance is recorded per "
                "module, so set one before syncing")
            return summary
        summary["module_code"] = module_code

        raw_date = (session["actual_start_time"] or session["start_time"] or "")
        session_date = str(raw_date)[:10] or datetime.now().strftime("%Y-%m-%d")
        key = _session_id_key(session_id)

        participants = conn.execute(
            "SELECT participant_id, user_id, user_type, attendance_status, "
            "       join_time, duration "
            "FROM session_participants WHERE session_id = ?",
            (session_id,),
        ).fetchall()

        for p in participants:
            # Instructors and guests are not marked against module attendance.
            if (p["user_type"] or "student").lower() != "student":
                summary["skipped"] += 1
                continue

            status = _STATUS_MAP.get(
                (p["attendance_status"] or "absent").lower(), "Absent")
            note = f"Online session (via {CHECK_IN_METHOD})"
            if (p["attendance_status"] or "").lower() == "left_early":
                mins = int((p["duration"] or 0) // 60)
                note = f"Online session — left early after {mins} min"

            existing = conn.execute(
                "SELECT id FROM attendance_records "
                "WHERE student_id = ? AND module_code = ? AND session_id = ?",
                (str(p["user_id"]), module_code, key),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE attendance_records "
                    "SET status = ?, notes = ?, recorded_at = ? WHERE id = ?",
                    (status, note, datetime.now().isoformat(), existing["id"]))
            else:
                conn.execute(
                    "INSERT INTO attendance_records "
                    "(student_id, module_code, date, status, notes, recorded_by, "
                    " recorded_at, check_in_method, session_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(p["user_id"]), module_code, session_date, status, note,
                     RECORDED_BY, datetime.now().isoformat(), CHECK_IN_METHOD, key))
            summary["written"] += 1

        conn.commit()
        logger.info("Virtual session %s attendance synced: %s written, %s skipped (%s)",
                    session_id, summary["written"], summary["skipped"], module_code)
        return summary

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            logger.debug("rollback failed", exc_info=True)
        summary["reason"] = str(exc)
        logger.exception("Virtual attendance sync failed for session %s", session_id)
        return summary
    finally:
        if owns_conn:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
