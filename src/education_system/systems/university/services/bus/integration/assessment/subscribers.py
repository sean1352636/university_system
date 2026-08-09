"""Focused components extracted from the legacy integration bus."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.events.in_process import (
    EVENT_CASE_OPENED,
    EVENT_CERT_CHANGED,
    EVENT_CHARGE_RAISED,
    EVENT_COURSE_CHANGED,
    EVENT_ENROLMENT_CHANGED,
    EVENT_EXAM_CHANGED,
    EVENT_INCIDENT_LOGGED,
    EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_SELECTION_CHANGED,
    EVENT_STAFF_AVAILABILITY_CHANGED,
    EVENT_TERM_CHANGED,
    publish,
    subscribe,
)

logger = logging.getLogger(__name__)
from education_system.systems.university.services.bus.integration.finance.reporting import _admin_user_id
from education_system.systems.university.services.bus.integration.publishing import log_and_publish

def _enrolled_students_for_module(module_code: str) -> list[str]:
    """Best-effort roster lookup. Tries student_enrolment, then plan_courses."""
    if not module_code:
        return []
    try:
        with get_connection() as conn:
            for sql in (
                "SELECT DISTINCT student_id FROM student_enrolment WHERE module_code = ?",
                "SELECT DISTINCT sp.student_id FROM plan_courses pc "
                "JOIN student_plans sp ON sp.plan_id = pc.plan_id "
                "WHERE pc.course_code = ?",
            ):
                try:
                    rows = conn.execute(sql, (module_code,)).fetchall()
                    if rows:
                        return [str(r[0]) for r in rows if r[0]]
                except Exception:
                    continue
    except Exception:
        pass
    return []

def _on_exam_event(**payload: Any) -> None:
    action = payload.get("action")
    if action == "published":
        _fanout_exam_published(payload)
    elif action == "graded":
        _fanout_exam_graded(payload)

def _fanout_exam_published(payload: dict[str, Any]) -> None:
    module_code = payload.get("module_code") or ""
    students = _enrolled_students_for_module(module_code)
    try:
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
        ctx = {
            "exam_title": payload.get("exam_title") or f"Exam #{payload.get('exam_id')}",
            "module_code": module_code,
            "start_time": payload.get("start_time") or "TBA",
            "duration_minutes": payload.get("duration_minutes") or "?",
            "pass_mark": payload.get("pass_mark") or 50,
        }
        for sid in students:
            try:
                send_templated(sid, "exam.scheduled", ctx,
                               related_to=f"exam:{payload.get('exam_id')}")
            except Exception as exc:
                logger.debug("exam.scheduled email failed for %s: %s", sid, exc)
    except Exception as exc:
        logger.debug("email_bus unavailable for exam roster: %s", exc)

def _fanout_exam_graded(payload: dict[str, Any]) -> None:
    sid = payload.get("student_id")
    if not sid:
        return
    try:
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
        send_templated(
            sid, "exam.graded",
            {
                "exam_title": payload.get("exam_title")
                              or f"Exam #{payload.get('exam_id')}",
                "score": payload.get("score") or 0,
                "total_marks": payload.get("total_marks") or 0,
                "percentage": round(payload.get("percentage") or 0.0, 1),
                "result": "passed" if payload.get("passed") else "review",
            },
            related_to=f"exam:{payload.get('exam_id')}",
        )
    except Exception as exc:
        logger.debug("exam.graded email failed: %s", exc)

def _on_module_schedule_changed_for_exams(**payload: Any) -> None:
    if payload.get("action") == "timetable_locked":
        return  # already handled by Feature 4
    module_code = payload.get("module_code")
    if not module_code:
        return
    new_start = payload.get("start_time")
    new_end = payload.get("end_time")
    new_room = payload.get("room_id")
    if not (new_start and new_end):
        return
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='exam_portal_exams'"
            ).fetchone()
            if not tbl:
                return
            rows = conn.execute(
                "SELECT id, title, start_time, end_time, room_id "
                "FROM exam_portal_exams "
                "WHERE module_code = ? AND status = 'published' "
                "  AND start_time IS NOT NULL AND end_time IS NOT NULL",
                (module_code,),
            ).fetchall()
    except Exception:
        return

    for exam in rows:
        if not _windows_overlap(new_start, new_end,
                                 exam["start_time"], exam["end_time"]):
            continue
        if new_room and exam["room_id"] and new_room != exam["room_id"]:
            continue  # different rooms, no real conflict
        log_and_publish(
            EVENT_INCIDENT_LOGGED,
            source="integration_bus",
            kind="exam_room_conflict",
            severity="medium",
            module_code=module_code,
            exam_id=exam["id"],
            exam_title=exam["title"],
            location=exam["room_id"] or new_room,
        )
        # Notify the scheduler/admin via email_bus.
        try:
            from education_system.systems.university.services.bus.email_bus import (
                send_templated,
            )
            send_templated(
                _admin_user_id() or "admin", "exam.room_conflict",
                {
                    "exam_title": exam["title"] or f"Exam #{exam['id']}",
                    "module_code": module_code,
                    "when": exam["start_time"],
                },
                related_to=f"exam:{exam['id']}",
                force=True,
            )
        except Exception as exc:
            logger.debug("conflict email failed: %s", exc)

def _windows_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    try:
        return not (a_end <= b_start or b_end <= a_start)
    except Exception:
        return False
