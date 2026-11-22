"""Grade appeals — an academic appeal case, plus a helpdesk ticket.

The appeal itself is a case in the shared register, run through the appeals
procedure (``application.cases.appeals``: eligibility, investigation,
outcome, review, Completion of Procedures letter). A helpdesk ticket is still
raised alongside it so the enquiry shows in the support queue with its SLA.

Same shape as the assignment-side dispute path so a single helpdesk
queue can hold appeals from both subsystems. The ticket arrives by the
``grade_appeal`` channel, which distinguishes it from assignment disputes.

The ticket is raised through the support-tickets port
(``services/bus/support_tickets_bus``), so it is routed, tiered, checked
for crisis language and given its SLA like any other ticket.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

CHANNEL = "grade_appeal"


def file_grade_appeal_ticket(
    *,
    actor,
    student_id: str,
    module_code: str,
    assessment_name: str,
    current_grade: str | float,
    reason: str,
    priority: str = "medium",
    user_id=None,
    grounds: str | None = None,
    results_released_on=None,
    late_reason: str | None = None,
) -> dict:
    """File a grade appeal by ``student_id``, raised by
    the signed-in ``actor`` (``user_id`` is accepted from older callers and
    ignored: the requester is the student, by student number).

    Opens the academic appeal case (``grounds`` is one of
    ``appeals.GROUNDS``) and a helpdesk ticket linked to it. Returns
    ``{'appeal_id', 'reference', 'ticket_id', 'team', 'confidentiality',
    'crisis'}`` — show ``crisis`` at once when it is set. The ticket is
    best-effort (``ticket_id`` None if the helpdesk refused it); the appeal is
    not. Raises PermissionError / ValueError with a message fit to show.
    """
    from education_system.systems.university.application.cases import appeals

    who = appeals.who_from_user(getattr(actor, "current_user", None)
                                if not isinstance(actor, dict) else actor)
    statement = (f"Appeal of the result '{current_grade}' for assessment "
                 f"'{assessment_name}' in module {module_code}.\n\n{reason}")
    # Validate before raising a ticket, so a refused appeal leaves nothing behind.
    appeals.check_submission(who, str(student_id or "").strip(), grounds, statement)
    try:
        ticket = _raise_ticket(actor, student_id, module_code, assessment_name, current_grade,
                               reason, priority)
    except (PermissionError, ValueError):
        logger.info("Helpdesk ticket for the grade appeal was refused", exc_info=True)
        ticket = {}
    appeal_id = appeals.submit(
        who, student_id, grounds, statement, module_code=module_code or None,
        assessment_name=assessment_name or None, current_result=str(current_grade or "") or None,
        results_released_on=results_released_on, late_reason=late_reason,
        ticket_id=ticket.get("ticket_id"))
    return {**ticket, "ticket_id": ticket.get("ticket_id"), "appeal_id": appeal_id,
            "reference": f"APL-{appeal_id:05d}"}


def _raise_ticket(actor, student_id, module_code, assessment_name, current_grade, reason,
                  priority) -> dict:
    from education_system.systems.university.services.bus import support_tickets_bus

    subject = f"Grade appeal — {module_code} / {assessment_name}"
    message = (
        f"Student {student_id} is appealing the grade '{current_grade}' "
        f"recorded for assessment '{assessment_name}' in module "
        f"{module_code}.\n\nReason: {reason}"
    )
    return support_tickets_bus.raise_ticket(
        actor, subject=subject, description=message, category="Academic Inquiry",
        priority=priority, channel=CHANNEL, requester=student_id or None)
