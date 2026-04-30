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
# Registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "balance":            tool_balance,
    "active_holds":       tool_active_holds,
    "module_grade":       tool_module_grade,
    "module_timeline":    tool_module_timeline,
    "current_period":     tool_current_period,
    "find_free_rooms":    tool_find_free_rooms,
    "qualified_for":      tool_qualified_for,
    "instructor_workload": tool_instructor_workload,
    "certs_expiring":     tool_certs_expiring,
    "documents_for":      tool_documents_for,
    "pending_messages":   tool_pending_messages,
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
