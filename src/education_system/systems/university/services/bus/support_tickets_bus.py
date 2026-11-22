"""Port: raise and list support tickets from outside Pastoral.

Support tickets (Student Support and the Helpdesk share one ticket model)
belong to the Pastoral slice. Other slices — a grade appeal from Grade
Tracking, a grade dispute from the assignment system — raise and list them
here rather than importing Pastoral or writing ``support_tickets``.

Everything goes through the ticket service, so a ticket raised here is
routed to its team, classified into its confidentiality tier, checked for
crisis language (the result's ``'crisis'`` carries the contacts to show at
once), given its SLA and announced by e-mail; a list holds only the tickets
the caller may see, with a confidential ticket's text never shown.

``actor`` is the signed-in user: an auth object with ``current_user`` or
the ``current_user`` dict.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SUPPORT = "education_system.systems.university.domains.student_support.domain"


def _support():
    import importlib
    return importlib.import_module(f"{_SUPPORT}.student_support.service")


def _helpdesk():
    import importlib
    return importlib.import_module(f"{_SUPPORT}.helpdesk.tickets.service")


def _support_auth():
    import importlib
    return importlib.import_module(f"{_SUPPORT}.student_support.auth")


def raise_ticket(actor: Any, *, subject: str, description: str, category: str,
                 channel: str, priority: str = "medium", requester: Optional[str] = None,
                 source: str = "helpdesk") -> dict:
    """Raise a ticket; returns ``{'ticket_id', 'team', 'confidentiality',
    'crisis'}``.

    ``requester`` (a username or student number) is whom the ticket is for.
    Support staff may raise a ticket for someone else; anyone else who asks
    to (a lecturer filing a student's appeal) raises it as themselves, the
    description naming the student. ``source`` is 'helpdesk' or 'support'.
    Raises PermissionError / ValueError with a message fit to show.
    """
    fields = dict(subject=subject, description=description, category=category,
                  priority=priority, channel=channel)

    def submit(who):
        if source == "support":
            return _support().submit_ticket(actor, source="support", requester=who, **fields)
        return _helpdesk().submit_helpdesk_ticket(actor, requester=who, **fields)

    try:
        return submit(requester)
    except PermissionError:
        if requester is None:
            raise
        return submit(None)


def recent_tickets(actor: Any, *, channel: str, limit: int = 25) -> list[dict]:
    """The newest tickets that came in by ``channel`` (e.g. 'grade_appeal')
    which ``actor`` may see — every visible one for support staff, else the
    ones they raised. Summaries only: no description or replies."""
    if actor is None:
        return []
    try:
        staff = _support_auth().is_case_worker(actor)
        out = []
        for t in _helpdesk().iter_tickets(actor, mine=not staff):
            if (t.get("channel") or t.get("source")) != channel:
                continue
            out.append({
                "ticket_id": t["ticket_id"],
                "requester": t.get("requester_username"),
                "student_id": t.get("student_id"),
                "subject": t.get("subject"),
                "status": t.get("status_label") or t.get("status"),
                "priority": t.get("priority"),
                "team": t.get("team"),
                "confidentiality": t.get("confidentiality"),
                "created_at": t.get("created_at"),
            })
            if len(out) >= limit:
                break
        return out
    except PermissionError:
        return []
    except Exception:
        logger.warning("Could not list %s tickets", channel, exc_info=True)
        return []


def tickets_for_student(actor: Any, student: str) -> list[dict]:
    """``student``'s tickets (a username or student number) that ``actor``
    may see: support staff by team and tier, the student their own; anyone
    else none. Summaries only: no description or replies."""
    if actor is None or not student:
        return []
    svc = _support()
    try:
        if _support_auth().is_case_worker(actor):
            pages = lambda page: svc.list_tickets_for_requester(actor, student, None, page, 500)
        else:
            me = _support_auth().current_requester(actor)
            if str(student) not in (me.username, str(me.student_id or '')):
                return []
            pages = lambda page: svc.list_my_tickets(actor, None, page, 500)
        out, page = [], 1
        while True:
            result = pages(page)
            for t in result["tickets"]:
                out.append({
                    "ticket_id": t["ticket_id"], "subject": t.get("subject"),
                    "category": t.get("category"),
                    "status": t.get("status_label") or t.get("status"),
                    "created_at": t.get("created_at"), "resolved_at": t.get("resolved_at"),
                    "team": t.get("team"), "confidentiality": t.get("confidentiality"),
                })
            if page >= result["total_pages"]:
                return out
            page += 1
    except (PermissionError, ValueError):
        return []


__all__ = ["raise_ticket", "recent_tickets", "tickets_for_student"]
