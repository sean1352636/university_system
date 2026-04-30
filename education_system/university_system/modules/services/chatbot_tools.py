"""Chatbot tool surface — bridges the chatbot to existing services.

Rather than build a new query API for the chatbot, expose the
already-canonical services as named tool functions. The chatbot's
intent handlers / function-calling layer dispatches into these.

Each tool returns a small dict shaped for direct templating into a
chat reply. Errors degrade gracefully — the chatbot should never
expose a stack trace to the user.

Tool registry (``TOOLS``) lets the chatbot enumerate what's
available and pick by name; it's also what the function-calling
layer hands to the LLM.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

def tool_balance(student_id: str | int) -> dict[str, Any]:
    """What's the student's current finance balance?"""
    try:
        from education_system.university_system.modules.services.finance_bus import (
            student_balance,
        )
        return {"ok": True, "balance": student_balance(student_id),
                "currency": "GBP"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_active_holds(student_id: str | int) -> dict[str, Any]:
    """List active finance holds blocking the student."""
    try:
        from education_system.university_system.modules.services.finance_bus import (
            list_active_holds,
        )
        return {"ok": True, "holds": list_active_holds(student_id)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Academic
# ---------------------------------------------------------------------------

def tool_module_grade(student_id: str | int, module_code: str) -> dict[str, Any]:
    """Compute the weighted grade for one module."""
    try:
        from education_system.university_system.modules.domain.academics.gui._cross_services import (
            compute_module_grade,
        )
        return {"ok": True, "result": compute_module_grade(student_id, module_code)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_module_timeline(module_code: str) -> dict[str, Any]:
    """Lecture / assessment / exam events for a module."""
    try:
        from education_system.university_system.modules.domain.academics.gui._cross_services import (
            module_timeline,
        )
        return {"ok": True, "events": module_timeline(module_code)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_current_period(kind: str = "term") -> dict[str, Any]:
    """Current academic period (term / exam_window / submission_window / ...)."""
    try:
        from education_system.university_system.modules.domain.academics.gui._cross_services import (
            current_period,
        )
        return {"ok": True, "kind": kind, "period": current_period(kind)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_find_free_rooms(day_of_week: str, start_time: str, end_time: str,
                         min_capacity: int | None = None) -> dict[str, Any]:
    """Free rooms for a recurring weekday slot."""
    try:
        from education_system.university_system.modules.domain.academics.gui._cross_services import (
            find_free_rooms,
        )
        rooms = find_free_rooms(
            day_of_week=day_of_week,
            start_time=start_time, end_time=end_time,
            min_capacity=min_capacity,
        )
        return {"ok": True, "rooms": rooms}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# HR / Certs
# ---------------------------------------------------------------------------

def tool_qualified_for(instructor_id: int | str, module_code: str) -> dict[str, Any]:
    try:
        from education_system.university_system.modules.services.staff_hr_bus import (
            is_qualified_for,
        )
        return {"ok": True, "qualified": is_qualified_for(instructor_id, module_code)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_instructor_workload(instructor_id: int | str) -> dict[str, Any]:
    try:
        from education_system.university_system.modules.domain.academics.gui._cross_services import (
            instructor_workload,
        )
        return {"ok": True, "workload": instructor_workload(instructor_id=int(instructor_id))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_certs_expiring(within_days: int = 30,
                        kind: str | None = None) -> dict[str, Any]:
    try:
        from education_system.university_system.modules.services.cert_bus import (
            expiring_certifications,
        )
        return {"ok": True,
                "certs": expiring_certifications(within_days, kind=kind)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def tool_documents_for(domain: str, ref_id: str | int) -> dict[str, Any]:
    try:
        from education_system.university_system.modules.services.document_bus import (
            get_documents_for,
        )
        return {"ok": True, "documents": get_documents_for(domain, ref_id)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

def tool_pending_messages(user_id: str | int) -> dict[str, Any]:
    """Return queued contextual notifications for the user."""
    try:
        from education_system.university_system.modules.services.chatbot_inbox import (
            pop_messages_for,
        )
        return {"ok": True, "messages": pop_messages_for(user_id)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Aggregator: one call → full module snapshot
# ---------------------------------------------------------------------------

def tool_summarise_module(module_code: str,
                          *, student_id: str | int | None = None) -> dict[str, Any]:
    """Aggregate timeline + grade + conflicts + workload for a module.

    Single canonical call powering "tell me about CS101" replies.
    Each sub-section is best-effort — a failure in one branch doesn't
    drop the rest.
    """
    if not module_code:
        return {"ok": False, "error": "module_code required"}
    out: dict[str, Any] = {"ok": True, "module_code": module_code}
    try:
        from education_system.university_system.modules.domain.academics.gui._cross_services import (
            module_timeline, find_conflicts_for_module,
            compute_module_grade, instructor_workload,
        )
        from education_system.university_system.infrastructure.database.db import (
            get_connection,
        )
        try:
            out["timeline"] = module_timeline(module_code)
        except Exception:
            out["timeline"] = []
        try:
            out["conflicts"] = find_conflicts_for_module(module_code)
        except Exception:
            out["conflicts"] = []
        if student_id:
            try:
                out["grade"] = compute_module_grade(student_id, module_code)
            except Exception:
                out["grade"] = None
        # Instructor lookup via module_schedule.
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT instructor_id FROM module_schedule "
                    "WHERE module_code = ? AND instructor_id IS NOT NULL "
                    "LIMIT 1", (module_code,),
                ).fetchone()
                if row and row[0] is not None:
                    out["instructor"] = instructor_workload(
                        instructor_id=int(row[0]),
                    )
        except Exception:
            pass
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return out


# ---------------------------------------------------------------------------
# Mutation tools — wrap canonical writers so the chatbot can act, not
# just observe. All writers preserve the gates the GUIs hit.
# ---------------------------------------------------------------------------

def tool_move_slot(schedule_id: int,
                   *, new_day: str | None = None,
                   new_start_time: str | None = None,
                   new_end_time: str | None = None,
                   new_room_id: int | None = None,
                   moved_by: str = "chatbot") -> dict[str, Any]:
    """Move a module_schedule row through the canonical writer."""
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling.slot_writer import (
            move_slot,
        )
        return {"ok": True, "result": move_slot(
            schedule_id,
            new_day=new_day, new_start_time=new_start_time,
            new_end_time=new_end_time, new_room_id=new_room_id,
            moved_by=moved_by,
        )}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_book_room(*, day_of_week: str | None = None,
                   on_date: str | None = None,
                   start_time: str, end_time: str,
                   min_capacity: int | None = None) -> dict[str, Any]:
    """Find free rooms for the window and return the top suggestion.

    Read-only — the chatbot still asks the user to confirm before
    a write tool is called. Mirrors the dialog flow Exam uses.
    """
    try:
        from education_system.university_system.modules.domain.academics.gui._cross_services import (
            find_free_rooms,
        )
        rows = find_free_rooms(
            day_of_week=day_of_week, on_date=on_date,
            start_time=start_time, end_time=end_time,
            min_capacity=min_capacity,
        )
        return {"ok": True, "rooms": rows[:5], "total": len(rows)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_schedule_exam(*, module_code: str, date: str,
                       start_time: str, end_time: str,
                       room: str | None = None,
                       instructor_id: int | None = None,
                       module_name: str | None = None,
                       students_enrolled: int = 0,
                       enrolled_student_ids: list | None = None,
                       ) -> dict[str, Any]:
    """Save a new exam through the existing data manager.

    Hits the same date-window + holiday gate the GUI does. Returns
    the new exam_id on success.
    """
    if not module_code or not date or not start_time or not end_time:
        return {"ok": False, "error": "module_code/date/start_time/end_time required"}
    try:
        from education_system.university_system.modules.domain.academics.gui.exam_management.models import (
            Exam,
        )
        from education_system.university_system.modules.domain.academics.gui.exam_management.data_manager import (
            ExamDataManager,
        )
        exam = Exam(
            id=0,
            module_code=module_code,
            module_name=module_name or module_code,
            date=date, start_time=start_time, end_time=end_time,
            room=room or "",
            instructor_id=instructor_id,
            instructor_name="",
            students_enrolled=int(students_enrolled or 0),
            enrolled_student_ids=list(enrolled_student_ids or []),
        )
        dm = ExamDataManager()
        dm._save_exam_to_db(exam, is_new=True)
        return {"ok": True, "exam_id": exam.id}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_queue_message(user_id: str | int, message: str,
                       *, source: str = "chatbot") -> dict[str, Any]:
    """Queue a message for another user via the chatbot inbox."""
    try:
        from education_system.university_system.modules.services.chatbot_inbox import (
            queue_message_for,
        )
        msg_id = queue_message_for(user_id, message, source=source)
        return {"ok": bool(msg_id), "msg_id": msg_id}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_my_open_cases(user_id: str | int) -> dict[str, Any]:
    """List active misconduct + disciplinary cases against the user."""
    try:
        from education_system.university_system.modules.services.cases_bus import (
            list_open,
        )
        return {"ok": True, "cases": list_open(user_id)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_my_clubs(user_id: str | int) -> dict[str, Any]:
    """List Student Union club memberships for the user."""
    try:
        from education_system.university_system.modules.services.student_union_bus import (
            list_clubs_for,
        )
        return {"ok": True, "clubs": list_clubs_for(user_id)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_request_su_advocacy(user_id: str | int, case_id: int,
                             *, kind: str = "disciplinary") -> dict[str, Any]:
    """Opt the user into SU advocacy for an open case."""
    try:
        from education_system.university_system.modules.services.student_union_bus import (
            request_advocacy,
        )
        rid = request_advocacy(user_id, int(case_id), case_kind=kind)
        return {"ok": bool(rid), "request_id": rid}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    # Read-only
    "balance":             tool_balance,
    "active_holds":        tool_active_holds,
    "module_grade":        tool_module_grade,
    "module_timeline":     tool_module_timeline,
    "current_period":      tool_current_period,
    "find_free_rooms":     tool_find_free_rooms,
    "qualified_for":       tool_qualified_for,
    "instructor_workload": tool_instructor_workload,
    "certs_expiring":      tool_certs_expiring,
    "documents_for":       tool_documents_for,
    "pending_messages":    tool_pending_messages,
    "summarise_module":    tool_summarise_module,
    # Mutations — go through canonical writers so all gates fire.
    "move_slot":           tool_move_slot,
    "book_room":           tool_book_room,
    "schedule_exam":       tool_schedule_exam,
    "queue_message":       tool_queue_message,
    "my_open_cases":       tool_my_open_cases,
    "my_clubs":            tool_my_clubs,
    "request_su_advocacy": tool_request_su_advocacy,
}


def call_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    fn = TOOLS.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        return fn(**kwargs)
    except TypeError as exc:
        return {"ok": False, "error": f"bad arguments: {exc}"}


__all__ = ["TOOLS", "call_tool"]
