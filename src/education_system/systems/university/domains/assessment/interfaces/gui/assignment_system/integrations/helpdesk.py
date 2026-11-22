"""Student-affairs helpdesk adapter — escalate grade disputes to tickets.

The ticket is raised through the support-tickets port
(``services/bus/support_tickets_bus``), so it is routed, tiered, checked
for crisis language and given its SLA like any other ticket. It arrives
by the ``assignment_dispute`` channel.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

CHANNEL = "assignment_dispute"


def escalate_dispute_to_helpdesk(
    *,
    actor,
    student_id: str,
    dispute_id: int,
    assignment_title: str,
    reason: str,
    priority: str = "medium",
    user_id=None,
) -> dict:
    """Create a helpdesk ticket linked to a grade dispute, raised by the
    signed-in ``actor`` for ``student_id`` (``user_id`` is accepted from
    older callers and ignored).

    Returns ``{'ticket_id', 'team', 'confidentiality', 'crisis'}`` — show
    ``crisis`` at once when it is set. Raises PermissionError / ValueError
    with a message fit to show.
    """
    from education_system.systems.university.services.bus import support_tickets_bus

    subject = f"Grade dispute — {assignment_title} (dispute #{dispute_id})"
    message = (
        f"A grade dispute has been filed for assignment "
        f"'{assignment_title}'. Reason from student: {reason}"
    )
    return support_tickets_bus.raise_ticket(
        actor, subject=subject, description=message, category="Academic Inquiry",
        priority=priority, channel=CHANNEL, requester=student_id or None)
