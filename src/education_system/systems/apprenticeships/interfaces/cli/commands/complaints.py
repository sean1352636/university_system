"""Complaints: raise one, follow your own, or handle them all.

Exposes: menu.

The menu works out from the actor what to offer: anyone may raise and
follow their own complaints; a holder of ``complaint.manage`` also sees
every complaint, the late ones, and the actions that move them along.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.quality.complaints import Complaint
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.quality import complaint_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (("Ref", 8), ("Received", 10), ("From", 16), ("Category", 20), ("Subject", 26),
            ("Status", 13), ("Due", 10), ("", 9))
_UPDATE_COLUMNS = (("When", 16), ("From", 26), ("Shared", 6), ("Note", 50))


def menu(actor: Actor) -> None:
    manager = actor.can("complaint.manage")
    entries: list[tuple[str, Callable[[], None]]] = []
    if manager:
        entries += [
            ("All open complaints", partial(_list, actor, open_only=True)),
            ("Overdue complaints", partial(_list, actor, overdue_only=True)),
            ("Awaiting acknowledgement", partial(_list, actor, status="Received")),
            ("Every complaint", partial(_list, actor)),
            ("Open a complaint", partial(_open, actor)),
        ]
    else:
        entries += [
            ("My complaints", partial(_list, actor)),
            ("Open one of my complaints", partial(_open, actor)),
        ]
    if actor.can("complaint.raise"):
        entries.append(("Raise a complaint", partial(_raise, actor)))
    prompts.run_menu("Complaints", entries)


# ═════════════════════════════════════════════════════════════════════
# Listing and reading
# ═════════════════════════════════════════════════════════════════════

def _list(actor: Actor, **filters: object) -> None:
    prompts.title("Complaints")
    today = date.today()
    rows = complaint_service.list_complaints(actor, **filters)  # type: ignore[arg-type]
    prompts.table(
        _COLUMNS, rows,
        lambda c: (c.reference, c.received_at, c.raised_by, c.category, c.subject, c.status,
                   c.next_deadline(), "OVERDUE" if c.is_overdue(today) else ""),
        noun="complaint",
    )
    prompts.pause()


def _pick(actor: Actor) -> Complaint:
    rows = complaint_service.list_complaints(actor)
    if not rows:
        prompts.fail("There are no complaints to show.")
        raise prompts.Abort
    return prompts.choose(
        "Complaint", rows, render=lambda c: f"{c.reference}  {c.subject} — {c.status}"
    )


def _show(actor: Actor, complaint: Complaint) -> None:
    today = date.today()
    prompts.title(f"{complaint.reference} — {complaint.subject}")
    prompts.details([
        ("Status", complaint.status + (f"  ({complaint.overdue_label(today)})"
                                       if complaint.is_overdue(today) else "")),
        ("Category", complaint.category),
        ("Raised by", f"{complaint.raised_by} ({complaint.raised_role_label})"),
        ("Apprentice", complaint.apprentice_name),
        ("Employer", complaint.employer_name),
        ("Received", complaint.received_at),
        ("Acknowledge by", complaint.ack_due_on),
        ("Acknowledged", complaint.acknowledged_at),
        ("Respond by", complaint.response_due_on),
        ("Handled by", complaint.handler),
        ("Outcome", complaint.outcome),
        ("Escalated to", complaint.escalated_to),
        ("Closed", complaint.closed_at),
        ("Satisfied", complaint.satisfied),
    ])
    prompts.note("\nThe complaint:")
    prompts.note(complaint.description)
    manager = actor.can("complaint.manage")
    prompts.note("\nRecord:" if manager else "\nUpdates:")
    prompts.table(
        _UPDATE_COLUMNS if manager else tuple(c for c in _UPDATE_COLUMNS if c[0] != "Shared"),
        complaint_service.list_updates(actor, complaint.complaint_id),
        lambda u: ((u.created_at, u.author_label, u.visible_to_complainant, u.note)
                   if manager else (u.created_at, u.author_label, u.note)),
        noun="entry",
    )


def _open(actor: Actor) -> None:
    complaint = _pick(actor)
    while True:
        complaint = complaint_service.get_complaint(actor, complaint.complaint_id)
        _show(actor, complaint)
        actions = _actions(actor, complaint)
        if not actions:
            prompts.pause()
            return
        chosen = prompts.choose("Do what?", list(actions), allow_blank=True)
        if chosen is None:
            return
        prompts.run_action(actions[chosen])


def _actions(actor: Actor, complaint: Complaint) -> dict[str, Callable[[], None]]:
    actions: dict[str, Callable[[], None]] = {}
    cid = complaint.complaint_id
    if actor.can("complaint.manage"):
        if complaint.status == "Received":
            actions["Acknowledge"] = lambda: _done(complaint_service.acknowledge(actor, cid))
        if complaint.allowed_next():
            actions["Change status"] = lambda: _change_status(actor, complaint)
        actions["Assign handler"] = lambda: _done(complaint_service.assign_handler(
            actor, cid, prompts.ask("Handler (username)", default=complaint.handler
                                    or actor.username, required=True)))
        actions["Add a note"] = lambda: _note(actor, complaint, manager=True)
    elif complaint.status != "Closed":
        actions["Add a comment"] = lambda: _note(actor, complaint, manager=False)
    if (complaint.status in ("Resolved", "Escalated", "Closed") and complaint.satisfied is None
            and (actor.can("complaint.manage")
                 or complaint_service.is_complainant(actor, complaint))):
        actions["Record satisfaction"] = lambda: _done(complaint_service.record_satisfaction(
            actor, cid, prompts.ask_yes_no("Satisfied with the response?", default=True)))
    return actions


# ═════════════════════════════════════════════════════════════════════
# Writing
# ═════════════════════════════════════════════════════════════════════

def _raise(actor: Actor) -> None:
    prompts.title("Raise a complaint")
    prompts.note(f"We acknowledge every complaint within {config.COMPLAINT_ACK_DAYS} days "
                 f"and respond within {config.COMPLAINT_RESPONSE_DAYS}.")
    payload: dict[str, object] = {
        "category": prompts.choose_value("What is it about?", config.COMPLAINT_CATEGORIES),
        "subject": prompts.ask("Subject", required=True),
        "description": prompts.ask("What happened", required=True),
    }
    if actor.role != config.APPRENTICE and actor.can("apprentice.view"):
        people = apprentice_service.list_apprentices(actor)
        if people:
            chosen = prompts.choose("Apprentice concerned (blank for none)", people,
                                    render=lambda s: s.full_name, allow_blank=True)
            payload["apprentice_id"] = chosen.apprentice.apprentice_id if chosen else None
    if actor.can("complaint.manage"):
        payload["received_at"] = prompts.ask("Date received (YYYY-MM-DD)",
                                             default=date.today().isoformat())
    created = complaint_service.raise_complaint(actor, payload)
    prompts.ok(f"{created.reference} received. We will acknowledge it by {created.ack_due_on}.")
    prompts.pause()


def _change_status(actor: Actor, complaint: Complaint) -> None:
    target = prompts.choose_value("Move to", complaint.allowed_next())
    outcome = escalated_to = None
    if target == "Resolved":
        outcome = prompts.ask("Outcome", default=complaint.outcome or "", required=True)
    if target == "Escalated":
        escalated_to = prompts.choose_value("Escalated to", config.COMPLAINT_ESCALATION_BODIES)
        if escalated_to == "Other":
            escalated_to = prompts.ask("Which body?", required=True)
    note = prompts.ask("Note to the complainant (optional)")
    _done(complaint_service.change_status(
        actor, complaint.complaint_id, target,
        note=note, outcome=outcome, escalated_to=escalated_to,
    ))


def _note(actor: Actor, complaint: Complaint, *, manager: bool) -> None:
    text = prompts.ask("Note" if manager else "Comment", required=True)
    visible = prompts.ask_yes_no("Share with the complainant?") if manager else True
    complaint_service.add_update(actor, complaint.complaint_id, text, visible=visible)
    prompts.ok("Added.")


def _done(complaint: Complaint) -> None:
    prompts.ok(f"{complaint.reference} is now {complaint.status}.")
