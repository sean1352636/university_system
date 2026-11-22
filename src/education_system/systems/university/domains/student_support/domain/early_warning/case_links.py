"""Links a student's support case to their Early Warning record.

Support cases (``intervention_records``, one per student) and Early
Warning interventions (``early_warning_interventions``, many per
student, measured by ``intervention_outcomes``) share only the student
ID. This module is the join: one student's whole picture for the
Student Overview tab and CLI, and the two actions that cross over —
raising an Early Warning intervention from a case, and completing one —
each of which writes a line to the case history so the caseworker sees
it there.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from education_system.systems.university.domains.student_support.domain.early_warning import (
    early_warning_queries as queries,
)
from education_system.systems.university.domains.student_support.domain.early_warning.early_warning_core import (
    InterventionManager,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.student_wellbeing.services.intervention_records import (
    InterventionRecordsError, InterventionRecordsService,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CaseLinkError", "TRIGGER_TYPES", "INTERVENTION_TYPES", "PRIORITIES", "OUTCOMES",
    "suggest_intervention", "case_from_student", "student_choices",
    "student_overview", "raise_intervention", "complete_intervention",
]

# The Early Warning window's own choices.
TRIGGER_TYPES = ("academic", "attendance", "engagement", "financial", "other")
INTERVENTION_TYPES = ("auto_email", "manual_meeting", "coaching", "tutoring", "counseling")
PRIORITIES = ("low", "medium", "high", "critical")
OUTCOMES = ("successful", "partially_successful", "unsuccessful", "no_response")

#: Support-case intervention type -> (Early Warning trigger, intervention type).
_FROM_SUPPORT_TYPE = {
    "Academic Advising": ("academic", "coaching"),
    "Tutoring": ("academic", "tutoring"),
    "Counseling": ("other", "counseling"),
    "Mental Health Support": ("other", "counseling"),
    "Financial Aid": ("financial", "manual_meeting"),
    "Disability Services": ("other", "manual_meeting"),
    "Career Services": ("engagement", "manual_meeting"),
    "Peer Mentoring": ("engagement", "coaching"),
}

#: Early Warning risk level -> support-case risk.
_CASE_RISK = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}


class CaseLinkError(Exception):
    """Raised when a student can't be linked (e.g. not a student record)."""


def _records(actor: str = "") -> InterventionRecordsService:
    return InterventionRecordsService(actor=actor)


def suggest_intervention(case: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Defaults for raising an Early Warning intervention from a case."""
    if not case:
        return {"trigger_type": "academic", "intervention_type": "coaching",
                "priority": "high", "description": ""}
    trigger, itype = _FROM_SUPPORT_TYPE.get(case.get("intervention") or "",
                                            ("academic", "coaching"))
    priority = (case.get("risk") or "High").lower()
    return {
        "trigger_type": trigger,
        "intervention_type": itype,
        "priority": priority if priority in PRIORITIES else "high",
        "description": f"Raised from support case ({case.get('intervention') or 'support'}, "
                       f"{case.get('status') or 'Active'}).",
    }


def case_from_student(student_id: str) -> Dict[str, Any]:
    """A new support case filled from the student record and risk profile."""
    stu = queries.student(student_id)
    if not stu:
        raise CaseLinkError(f"{student_id} is not a student record.")
    profile = queries.risk_profile(student_id) or {}
    return {
        "student_id": stu["student_id"],
        "name": f"{stu.get('first_name') or ''} {stu.get('last_name') or ''}".strip(),
        "program": stu.get("program") or stu.get("course") or "",
        "gpa": "",
        "email": stu.get("email_address") or "",
        "risk": _CASE_RISK.get(str(profile.get("risk_level") or "").lower(), "Low"),
        "status": "Active",
        "intervention": "Academic Advising",
        "last_contact": "",
        "notes": "",
    }


def student_choices() -> List[Dict[str, Any]]:
    """Everyone the overview can show: every student, plus any support
    case whose ID isn't a student record (flagged ``linked=False``)."""
    out = [{"student_id": str(s["student_id"]),
            "label": f"{s['student_id']} - {s.get('first_name') or ''} {s.get('last_name') or ''}".strip(),
            "linked": True}
           for s in queries.student_picker()]
    known = {c["student_id"] for c in out}
    for case in _records().load_all():
        if case["student_id"] not in known:
            out.append({"student_id": case["student_id"],
                        "label": f"{case['student_id']} - {case.get('name') or ''} (support case only)",
                        "linked": False})
    return out


def student_overview(student_id: str) -> Dict[str, Any]:
    """Everything recorded about one student across the three areas."""
    from education_system.systems.university.domains.student_support.domain.early_warning.outcomes import (
        InterventionOutcomesService,
    )
    stu = queries.student(student_id)
    interventions = queries.interventions_for_student(student_id) if stu else []
    outcomes: Dict[int, Dict[str, Any]] = {}
    summary: Dict[str, Any] = {}
    if stu:
        svc = InterventionOutcomesService()
        outcomes = {r["intervention_id"]: r
                    for r in svc.list_with_outcomes(student_id=student_id)}
        summary = svc.summary(student_id=student_id)
    return {
        "student_id": student_id,
        "student": stu,
        "is_student": stu is not None,
        "case": _records().get(student_id),
        "profile": queries.risk_profile(student_id) if stu else None,
        "interventions": interventions,
        "outcomes": outcomes,
        "outcome_summary": summary,
        "indicators": queries.indicators_for_student(student_id) if stu else [],
        "coaching": queries.coach_assignments_for_student(student_id) if stu else [],
        "tutoring": queries.tutoring_for_student(student_id) if stu else [],
    }


def _note_on_case(student_id: str, text: str, actor: str) -> bool:
    """Write to the case history if the student has a case."""
    records = _records(actor)
    if not records.get(student_id):
        return False
    try:
        records.append_note(student_id, text)
        return True
    except InterventionRecordsError:
        logger.exception("Could not note Early Warning action on case %s", student_id)
        return False


def raise_intervention(student_id: str, trigger_type: str, intervention_type: str,
                       priority: str, description: str, assigned_to: str = "",
                       actor: str = "") -> int:
    """Create an Early Warning intervention and note it on the case."""
    if not queries.student(student_id):
        raise CaseLinkError(
            f"{student_id} is not a student record, so it can't have an Early "
            "Warning intervention. Use a support case for a real student.")
    iid = InterventionManager.create_intervention(
        student_id=student_id, trigger_type=trigger_type,
        intervention_type=intervention_type, priority=priority,
        description=description, assigned_to=assigned_to,
    )
    _note_on_case(student_id,
                  f"Early Warning intervention #{iid} raised ({intervention_type}, "
                  f"{priority}) by {actor or 'staff'}.", actor)
    logger.info("Early Warning intervention %s raised for %s by %s", iid, student_id, actor)
    return iid


def complete_intervention(intervention_id: int, outcome: str, notes: str = "",
                          actor: str = "") -> None:
    """Complete an Early Warning intervention and note it on the case."""
    student_id = queries.intervention_student(intervention_id)
    if student_id is None:
        raise CaseLinkError(f"Intervention {intervention_id} not found.")
    InterventionManager.complete_intervention(int(intervention_id), outcome, notes)
    _note_on_case(student_id,
                  f"Early Warning intervention #{intervention_id} completed: {outcome}"
                  + (f" — {notes}" if notes else "") + ".", actor)
