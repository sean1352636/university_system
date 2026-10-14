"""Employer contacts: contacts and roles, the conversation log, commitments.

Exposes: menu, employer_menu.

An admin sees every employer; a tutor the employers of their caseload.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.employers.models import EmployerSummary
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    employer_contact_service,
)
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

_CONTACT_COLUMNS = (("Name", 22), ("Role", 22), ("Job title", 18), ("Email", 24),
                    ("Phone", 13), ("Signs", 6))
_LOG_COLUMNS = (("Date", 11), ("How", 10), ("With", 16), ("About", 16), ("Summary", 34),
                ("Follow up", 11))
_COMMITMENT_COLUMNS = (("Commitment", 30), ("Category", 22), ("Apprentice", 16), ("Due", 11),
                       ("Status", 10), ("Level", -5))


def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Choose an employer", partial(_choose, actor)),
        ("Follow-ups due", partial(_follow_ups, actor)),
        ("Overdue commitments", partial(_overdue, actor)),
    ]
    prompts.run_menu("Employer Contacts", entries)


def employer_menu(actor: Actor, employer_id: int, name: str) -> None:
    """Everything this actor may do for one employer."""
    entries: list[tuple[str, Callable[[], None]]] = [
        ("View contacts, history and commitments", partial(_show, actor, employer_id, name)),
    ]
    if actor.can("employer.contact"):
        entries += [
            ("Log a contact", partial(_log, actor, employer_id)),
            ("Mark a follow-up done", partial(_follow_up_done, actor, employer_id)),
            ("Add a contact", partial(_add_contact, actor, employer_id)),
            ("Edit a contact", partial(_edit_contact, actor, employer_id)),
            ("Add a commitment", partial(_add_commitment, actor, employer_id)),
            ("Edit a commitment", partial(_edit_commitment, actor, employer_id)),
            ("Escalate a commitment", partial(_escalate, actor, employer_id)),
            ("Mark a commitment met", partial(_close, actor, employer_id, "Met")),
            ("Withdraw a commitment", partial(_close, actor, employer_id, "Withdrawn")),
        ]
    prompts.run_menu(f"Employer Contacts — {name}", entries)


def _choose(actor: Actor) -> None:
    summary = pick(actor)
    employer_menu(actor, summary.employer.employer_id, summary.name)


def pick(actor: Actor) -> EmployerSummary:
    employers = employer_contact_service.list_employers(actor)
    if not employers:
        prompts.fail("There are no employers for you to keep in touch with.")
        prompts.note("A tutor sees the employers of the apprentices on their caseload.")
        raise prompts.Abort
    return prompts.choose(
        "Employer", employers,
        render=lambda e: f"{e.name} — {e.employer.status}, {e.active_apprentices} active",
    )


# ═════════════════════════════════════════════════════════════════════
# Showing
# ═════════════════════════════════════════════════════════════════════

def _show(actor: Actor, employer_id: int, name: str) -> None:
    contacts = employer_contact_service.list_contacts(actor, employer_id)
    log = employer_contact_service.list_contact_log(actor, employer_id)
    commitments = employer_contact_service.list_commitments(actor, employer_id)
    today = date.today()

    prompts.title(f"{name} — contacts and commitments")
    prompts.details([
        ("Active contacts", sum(1 for c in contacts if c.active)),
        ("Conversations", len(log)),
        ("Open follow-ups", sum(1 for e in log if e.follow_up_open)),
        ("Outstanding commitments", sum(1 for c in commitments if c.is_outstanding)),
        ("Overdue commitments", sum(1 for c in commitments if c.is_overdue(today))),
    ])
    prompts.note("\nContacts:")
    _contact_table(contacts)
    prompts.note("\nContact history, newest first:")
    _log_table(log[:15], today)
    prompts.note("\nCommitments:")
    _commitment_table(commitments, today)
    prompts.pause()


def _follow_ups(actor: Actor) -> None:
    prompts.title("Follow-ups due")
    entries = employer_contact_service.follow_ups(actor)
    today = date.today()
    prompts.table(
        (("Due", 11), ("Employer", 22), ("With", 16), ("About", 16), ("Summary", 36)),
        entries,
        lambda e: ((e.follow_up_date or "") + (" !" if e.follow_up_overdue(today) else ""),
                   e.employer_name, e.contact_name, e.apprentice_name, e.summary),
        noun="follow-up",
        empty="no follow-ups are open",
    )
    prompts.pause()


def _overdue(actor: Actor) -> None:
    prompts.title("Overdue commitments")
    commitments = employer_contact_service.list_commitments(actor, overdue_only=True)
    prompts.table(
        (("Employer", 22), ("Commitment", 30), ("Due", 11), ("Status", 10), ("Level", -5)),
        commitments,
        lambda c: (c.employer_name, c.commitment, c.due_date, c.status, c.escalation_level),
        noun="commitment",
        empty="no commitments are overdue",
    )
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Contacts and the log
# ═════════════════════════════════════════════════════════════════════

def _add_contact(actor: Actor, employer_id: int) -> None:
    prompts.title("Add a contact")
    created = employer_contact_service.add_contact(actor, employer_id, _contact_payload(None))
    prompts.ok(f"Added {created.full_name}"
               + (f" as {created.contact_role}." if created.contact_role else "."))
    prompts.pause()


def _edit_contact(actor: Actor, employer_id: int) -> None:
    contacts = employer_contact_service.list_contacts(actor, employer_id)
    contact = prompts.choose(
        "Contact", contacts,
        render=lambda c: f"{c.full_name} — {c.contact_role or c.job_title or 'contact'}",
    )
    updated = employer_contact_service.update_contact(
        actor, contact.manager_id, _contact_payload(contact)
    )
    prompts.ok(f"Updated {updated.full_name}.")
    prompts.pause()


def _contact_payload(contact) -> dict[str, object]:
    def current(attr: str) -> str:
        value = getattr(contact, attr, None) if contact is not None else None
        return "" if value is None else str(value)

    role = prompts.choose("Role (blank for none)", config.EMPLOYER_CONTACT_ROLES,
                          allow_blank=True)
    return {
        "full_name": prompts.ask("Name", default=current("full_name"), required=True),
        "contact_role": role or (current("contact_role") if contact is not None else ""),
        "job_title": prompts.ask("Job title", default=current("job_title")),
        "email": prompts.ask("Email", default=current("email")),
        "phone": prompts.ask("Phone", default=current("phone")),
    }


def _log(actor: Actor, employer_id: int) -> None:
    prompts.title("Log a contact")
    contacts = [c for c in employer_contact_service.list_contacts(actor, employer_id) if c.active]
    contact = prompts.choose(
        "With (blank for nobody in particular)", contacts,
        render=lambda c: f"{c.full_name} — {c.contact_role or c.job_title or 'contact'}",
        allow_blank=True,
    )
    apprentice = _pick_apprentice(actor, employer_id)
    payload = {
        "contacted_on": prompts.ask("Date (YYYY-MM-DD)", default=date.today().isoformat()),
        "channel": prompts.choose_value("How", config.CONTACT_CHANNELS,
                                        default=config.CONTACT_CHANNELS[0]),
        "contact_id": contact.manager_id if contact else None,
        "apprentice_id": apprentice.apprentice.apprentice_id if apprentice else None,
        "summary": prompts.ask("What was said", required=True),
        "follow_up_date": prompts.ask("Follow up by (YYYY-MM-DD, blank for none)"),
    }
    entry = employer_contact_service.log_contact(actor, employer_id, payload)
    prompts.ok(f"Logged a {entry.channel.lower()} contact on {entry.contacted_on}.")
    prompts.pause()


def _follow_up_done(actor: Actor, employer_id: int) -> None:
    open_entries = [
        e for e in employer_contact_service.list_contact_log(actor, employer_id)
        if e.follow_up_open
    ]
    entry = prompts.choose(
        "Follow-up", open_entries,
        render=lambda e: f"due {e.follow_up_date} — {e.summary[:50]}",
    )
    employer_contact_service.complete_follow_up(actor, entry.log_id)
    prompts.ok("Follow-up marked done.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Commitments
# ═════════════════════════════════════════════════════════════════════

def _add_commitment(actor: Actor, employer_id: int) -> None:
    prompts.title("Add a commitment")
    created = employer_contact_service.add_commitment(
        actor, employer_id, _commitment_payload(actor, employer_id, None)
    )
    prompts.ok(f"Recorded “{created.commitment}”.")
    prompts.pause()


def _edit_commitment(actor: Actor, employer_id: int) -> None:
    commitment = _pick_commitment(actor, employer_id, outstanding=True)
    updated = employer_contact_service.update_commitment(
        actor, commitment.commitment_id, _commitment_payload(actor, employer_id, commitment)
    )
    prompts.ok(f"Updated “{updated.commitment}”.")
    prompts.pause()


def _escalate(actor: Actor, employer_id: int) -> None:
    commitment = _pick_commitment(actor, employer_id, outstanding=True)
    level = min(commitment.escalation_level + 1, config.COMMITMENT_MAX_ESCALATION)
    prompts.note(f"Escalating to level {level}: {config.COMMITMENT_ESCALATION_LEVELS[level]}.")
    reason = prompts.ask("Why", required=True)
    updated = employer_contact_service.escalate_commitment(
        actor, commitment.commitment_id, reason=reason
    )
    prompts.ok(f"“{updated.commitment}” is escalated to {updated.escalation_label}.")
    prompts.pause()


def _close(actor: Actor, employer_id: int, status: str) -> None:
    commitment = _pick_commitment(actor, employer_id, outstanding=True)
    note = prompts.ask("Why" if status == "Withdrawn" else "Note (optional)",
                       required=status == "Withdrawn")
    updated = employer_contact_service.close_commitment(
        actor, commitment.commitment_id, status=status, note=note
    )
    prompts.ok(f"“{updated.commitment}” is {updated.status}.")
    prompts.pause()


def _commitment_payload(actor: Actor, employer_id: int, commitment) -> dict[str, object]:
    def current(attr: str) -> str:
        value = getattr(commitment, attr, None) if commitment is not None else None
        return "" if value is None else str(value)

    apprentice = _pick_apprentice(actor, employer_id)
    return {
        "commitment": prompts.ask("Commitment", default=current("commitment"), required=True),
        "category": prompts.choose_value(
            "Category", config.COMMITMENT_CATEGORIES, default=current("category") or "Other"
        ),
        "apprentice_id": apprentice.apprentice.apprentice_id if apprentice else None,
        "due_date": prompts.ask("Due (YYYY-MM-DD)", default=current("due_date")),
        "notes": prompts.ask("Notes", default=current("notes")),
    }


def _pick_commitment(actor: Actor, employer_id: int, *, outstanding: bool):
    commitments = employer_contact_service.list_commitments(
        actor, employer_id, outstanding_only=outstanding
    )
    if not commitments:
        prompts.fail("There are no outstanding commitments for this employer.")
        raise prompts.Abort
    return prompts.choose(
        "Commitment", commitments,
        render=lambda c: f"{c.commitment[:40]} — {c.status}, due {c.due_date or '—'}",
    )


def _pick_apprentice(actor: Actor, employer_id: int):
    people = apprentice_service.list_apprentices(actor, employer_id=employer_id)
    return prompts.choose(
        "About apprentice (blank for the employer as a whole)", people,
        render=lambda s: f"{s.full_name} — {s.apprentice.status}", allow_blank=True,
    )


# ═════════════════════════════════════════════════════════════════════
# Tables
# ═════════════════════════════════════════════════════════════════════

def _contact_table(contacts: list) -> None:
    prompts.table(
        _CONTACT_COLUMNS, contacts,
        lambda c: (c.full_name, c.contact_role, c.job_title, c.email, c.phone, c.is_primary),
        noun="contact", empty="no contacts recorded",
    )


def _log_table(entries: list, today: date) -> None:
    prompts.table(
        _LOG_COLUMNS, entries,
        lambda e: (e.contacted_on, e.channel, e.contact_name, e.apprentice_name, e.summary,
                   (e.follow_up_date or "")
                   + (" done" if e.follow_up_done_at else
                      " !" if e.follow_up_overdue(today) else "")),
        noun="conversation", empty="nothing logged yet",
    )


def _commitment_table(commitments: list, today: date) -> None:
    prompts.table(
        _COMMITMENT_COLUMNS, commitments,
        lambda c: (c.commitment, c.category, c.apprentice_name,
                   (c.due_date or "") + (" !" if c.is_overdue(today) else ""),
                   c.status, c.escalation_level),
        noun="commitment", empty="no commitments recorded",
    )
