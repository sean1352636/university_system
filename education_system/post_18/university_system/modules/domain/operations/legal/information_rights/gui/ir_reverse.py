"""Reverse drill-throughs — actions other GUIs invoke to push state
*into* the Information Rights module.

Pattern matches ``qa_reverse``: each helper performs the side effect
via the IR service, then opens (or focuses) the IR window at the
relevant tab via ``set_focus``.
"""

from __future__ import annotations

import logging
from typing import Optional

from education_system.post_18.university_system.modules.domain.operations.legal.information_rights.services.information_rights_core import (
    InformationRightsService,
)

logger = logging.getLogger(__name__)


def _ensure_window(app) -> Optional[object]:
    """Open the IR window if not already, return the live instance."""
    win = getattr(app, "_ir_window", None)
    if win is not None:
        try:
            if win.root.winfo_exists():
                win.root.lift()
                return win
        except Exception:
            pass
    fn = getattr(app, "show_information_rights_gui", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            logger.exception("could not open Information Rights GUI")
    return getattr(app, "_ir_window", None)


def log_sar_for_student(app, student_id: str | int,
                         requester_name: str,
                         requester_email: str,
                         subject_summary: str = "Subject access request",
                         scope_details: str = "",
                         actor: str = "reverse_drill") -> Optional[str]:
    """Right-click on a student record → "Log SAR for this subject".

    Creates a SAR with ``subject_id`` recorded in scope_details so the
    forward drill can resolve it back, then focuses the IR detail tab
    on the new request. Returns the request ``reference`` (e.g.
    ``SAR-2026-0042``)."""
    svc = InformationRightsService()
    note = f"subject_id={student_id}; {scope_details}".strip("; ")
    try:
        req = svc.create_request(
            request_type="SAR",
            requester_name=requester_name,
            requester_email=requester_email,
            subject_summary=subject_summary,
            scope_details=note,
            actor=actor,
        )
    except Exception:
        logger.exception("log_sar_for_student failed")
        return None
    ref = req.get("reference")
    win = _ensure_window(app)
    if win is not None and ref:
        try:
            win.set_focus(reference=ref, tab="detail")
        except Exception:
            pass
    return ref


def log_foi_from_audit_event(app, requester_name: str,
                              requester_email: str,
                              subject_summary: str,
                              source_event_id: int | None = None,
                              actor: str = "reverse_drill") -> Optional[str]:
    """Right-click on an audit event → "Open as FOI request".

    Creates an FOI request, capturing the originating event id in
    ``scope_details`` for traceability."""
    svc = InformationRightsService()
    scope = (f"originating_audit_event={source_event_id}"
             if source_event_id else "")
    try:
        req = svc.create_request(
            request_type="FOI",
            requester_name=requester_name,
            requester_email=requester_email,
            subject_summary=subject_summary,
            scope_details=scope,
            actor=actor,
        )
    except Exception:
        logger.exception("log_foi_from_audit_event failed")
        return None
    ref = req.get("reference")
    win = _ensure_window(app)
    if win is not None and ref:
        try:
            win.set_focus(reference=ref, tab="detail")
        except Exception:
            pass
    return ref


def log_communication_to_request(app, reference: str,
                                   direction: str,
                                   channel: str,
                                   summary: str,
                                   body: str = "",
                                   actor: str = "reverse_drill") -> bool:
    """Right-click in Communication Hub → "Attach to IR request".

    Appends a comms log entry to the named request and focuses the IR
    detail tab on it."""
    svc = InformationRightsService()
    try:
        req = svc.get_by_reference(reference)
    except Exception:
        return False
    try:
        svc.log_communication(
            request_id=req["id"],
            direction=direction,
            channel=channel,
            summary=summary,
            body=body,
            actor=actor,
        )
    except Exception:
        logger.exception("log_communication_to_request failed")
        return False
    win = _ensure_window(app)
    if win is not None:
        try:
            win.set_focus(reference=reference, tab="detail")
        except Exception:
            pass
    return True


__all__ = [
    "log_sar_for_student",
    "log_foi_from_audit_event",
    "log_communication_to_request",
]
