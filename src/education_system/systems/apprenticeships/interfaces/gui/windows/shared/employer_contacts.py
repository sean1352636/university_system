"""Employer contacts: who to talk to, what was said, and what they owe.

For admins and provider staff. An admin sees every employer; a tutor
sees the employers of the apprentices on their own caseload — the ones
they actually deal with. One employer's screen shows its contacts and
what each does, the history of conversations with them (with follow-ups
that fall due), and the commitments the employer has made, overdue ones
flagged. The buttons follow ``employer.contact``, the same permission
the service checks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.employers.contacts import (
    ContactLogEntry,
    EmployerCommitment,
)
from education_system.systems.apprenticeships.domain.employers.models import EmployerManager
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.employers import employer_contact_service

logger = logging.getLogger(__name__)

PICK_COLUMNS = (
    ("name", "Employer", 240),
    ("sector", "Sector", 160),
    ("status", "Status", 100),
    ("active", "Active apprentices", 130, "e"),
    ("total", "All apprentices", 110, "e"),
)

CONTACT_COLUMNS = (
    ("name", "Contact", 180),
    ("role", "Role", 170),
    ("title", "Job title", 160),
    ("email", "Email", 200),
    ("phone", "Phone", 120),
    ("signatory", "Signatory", 80),
    ("active", "Active", 70),
)

LOG_COLUMNS = (
    ("when", "Date", 100),
    ("channel", "How", 90),
    ("contact", "With", 150),
    ("apprentice", "About", 150),
    ("summary", "Summary", 360),
    ("follow", "Follow up by", 110),
    ("by", "Logged by", 110),
)

COMMITMENT_COLUMNS = (
    ("commitment", "Commitment", 280),
    ("category", "Category", 200),
    ("apprentice", "Apprentice", 140),
    ("due", "Due", 100),
    ("status", "Status", 90),
    ("level", "Escalation", 170),
)

_NOBODY = ""


def render(gui: Any) -> None:
    """The employers this actor keeps in touch with."""
    frame = gui.clear()
    widgets.heading(
        frame, "Employer Contacts",
        subtitle="Who to talk to at each employer, every conversation with them, and what "
                 "they have committed to. Tutors see the employers of their own caseload.",
    )
    ok, employers = widgets.guard(lambda: employer_contact_service.list_employers(gui.actor))
    if not ok:
        return
    if not employers:
        widgets.empty_state(
            frame,
            "No employers to show. A tutor sees the employers of the apprentices on their "
            "caseload, so this fills up once apprentices are assigned to you.",
        )
        return

    table = widgets.DataTable(
        frame, PICK_COLUMNS, on_activate=lambda ident: open_employer(gui, int(ident))
    )

    def open_selected() -> None:
        employer_id = table.require_selection_int("open an employer")
        if employer_id is not None:
            open_employer(gui, employer_id)

    # Packed before the table fills, so a short screen keeps the action bar.
    widgets.button_bar(frame, [("Open employer →", open_selected)])
    table.populate(
        employers,
        lambda e: (e.name, e.employer.sector, e.employer.status, e.active_apprentices,
                   e.apprentice_count),
        identity=lambda e: e.employer.employer_id,
        noun="employer",
    )


def open_employer(gui: Any, employer_id: int) -> None:
    """One employer's contacts, conversation history and commitments."""
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: employer_contact_service.get_employer(gui.actor, employer_id)
    )
    name = summary.name if ok and summary else f"Employer {employer_id}"
    widgets.heading(frame, f"{name} — contacts and commitments")
    widgets.button_bar(frame, [("← All employers", lambda: render(gui))])
    if not ok:
        return

    def reload() -> None:
        open_employer(gui, employer_id)

    ok_c, contacts = widgets.guard(
        lambda: employer_contact_service.list_contacts(gui.actor, employer_id)
    )
    ok_l, log = widgets.guard(
        lambda: employer_contact_service.list_contact_log(gui.actor, employer_id)
    )
    ok_m, commitments = widgets.guard(
        lambda: employer_contact_service.list_commitments(gui.actor, employer_id)
    )
    if not (ok_c and ok_l and ok_m):
        return
    today = date.today()

    body = widgets.scrollable(frame)
    widgets.kpi_row(body, [
        ("Active contacts", sum(1 for c in contacts if c.active)),
        ("Conversations logged", len(log)),
        ("Open follow-ups", sum(1 for e in log if e.follow_up_open)),
        ("Outstanding commitments", sum(1 for c in commitments if c.is_outstanding)),
        ("Overdue commitments", sum(1 for c in commitments if c.is_overdue(today))),
    ])
    _contacts(gui, body, employer_id, contacts, reload)
    _history(gui, body, employer_id, contacts, log, today, reload)
    _commitments(gui, body, employer_id, commitments, today, reload)


# ═════════════════════════════════════════════════════════════════════
# Contacts
# ═════════════════════════════════════════════════════════════════════

def _contacts(gui: Any, parent: Any, employer_id: int, contacts: list[EmployerManager],
              reload: Callable[[], None]) -> None:
    box = widgets.section(parent, "Contacts")
    by_id = {c.manager_id: c for c in contacts}
    table: widgets.DataTable | None = None

    def add() -> None:
        _contact_form(gui, employer_id, None, reload)

    def edit() -> None:
        if table is None:
            widgets.warn("There are no contacts yet.", title="Nothing to choose")
            return
        ident = table.require_selection_int("edit a contact")
        if ident is not None and ident in by_id:
            _contact_form(gui, employer_id, by_id[ident], reload)

    if gui.actor.can("employer.contact"):
        widgets.button_bar(box, [("Add contact…", add), ("Edit…", edit)])
    if not contacts:
        widgets.empty_state(box, "No contacts are recorded for this employer yet.")
        return
    table = widgets.DataTable(box, CONTACT_COLUMNS, height=min(6, len(contacts)))
    table.populate(
        contacts,
        lambda c: (c.full_name, c.contact_role, c.job_title, c.email, c.phone,
                   c.is_primary, c.active),
        identity=lambda c: c.manager_id,
        noun="contact",
    )


def _contact_form(gui: Any, employer_id: int, contact: EmployerManager | None,
                  reload: Callable[[], None]) -> None:
    def current(attr: str) -> Any:
        value = getattr(contact, attr, None) if contact is not None else None
        return "" if value is None else value

    fields = [
        {"key": "full_name", "label": "Name", "required": True, "value": current("full_name")},
        {"key": "contact_role", "label": "Role", "kind": "combo",
         "options": ("", *config.EMPLOYER_CONTACT_ROLES), "value": current("contact_role")},
        {"key": "job_title", "label": "Job title", "value": current("job_title")},
        {"key": "email", "label": "Email", "value": current("email")},
        {"key": "phone", "label": "Phone", "value": current("phone")},
    ]

    def save(values: dict[str, Any]) -> object:
        if contact is None:
            return employer_contact_service.add_contact(gui.actor, employer_id, values)
        return employer_contact_service.update_contact(gui.actor, contact.manager_id, values)

    dialog = widgets.FormDialog(
        gui.root, "Edit contact" if contact else "Add contact", fields, save,
        intro="Linking a contact to an employer portal login, or making them the "
              "signatory, is done on the Employers screen.",
    )
    if dialog.saved:
        reload()


# ═════════════════════════════════════════════════════════════════════
# Contact history
# ═════════════════════════════════════════════════════════════════════

def _history(gui: Any, parent: Any, employer_id: int, contacts: list[EmployerManager],
             log: list[ContactLogEntry], today: date, reload: Callable[[], None]) -> None:
    box = widgets.section(parent, "Contact history")
    by_id = {e.log_id: e for e in log}
    table: widgets.DataTable | None = None

    def add() -> None:
        _log_form(gui, employer_id, contacts, reload)

    def done() -> None:
        if table is None:
            widgets.warn("Nothing has been logged yet.", title="Nothing to choose")
            return
        ident = table.require_selection_int("mark a follow-up done")
        entry = by_id.get(ident) if ident is not None else None
        if entry is None:
            return
        if not entry.follow_up_open:
            widgets.inform("That conversation has no open follow-up.", title="Nothing to do")
            return
        ok, _ = widgets.guard(
            lambda: employer_contact_service.complete_follow_up(gui.actor, entry.log_id)
        )
        if ok:
            reload()

    if gui.actor.can("employer.contact"):
        widgets.button_bar(box, [("Log a contact…", add), ("Follow-up done", done)])
    if not log:
        widgets.empty_state(box, "No conversations have been logged with this employer yet.")
        return
    table = widgets.DataTable(box, LOG_COLUMNS, height=min(8, len(log)))
    table.populate(
        log,
        lambda e: (e.contacted_on, e.channel, e.contact_name, e.apprentice_name, e.summary,
                   (e.follow_up_date or "") + (" ✓" if e.follow_up_done_at else ""),
                   e.logged_by),
        identity=lambda e: e.log_id,
        tag=lambda e: e.follow_up_rag(today),
        noun="conversation",
    )


def _log_form(gui: Any, employer_id: int, contacts: list[EmployerManager],
              reload: Callable[[], None]) -> None:
    people = {
        f"{c.full_name} — {c.contact_role or c.job_title or 'contact'}": c.manager_id
        for c in contacts if c.active
    }
    apprentices = _apprentice_choices(gui, employer_id)
    fields = [
        {"key": "contacted_on", "label": "Date", "value": date.today().isoformat(),
         "help": "YYYY-MM-DD."},
        {"key": "channel", "label": "How", "kind": "combo", "required": True,
         "options": config.CONTACT_CHANNELS, "value": config.CONTACT_CHANNELS[0]},
        {"key": "contact", "label": "With", "kind": "combo",
         "options": (_NOBODY, *people), "value": _NOBODY},
        {"key": "apprentice", "label": "About apprentice", "kind": "combo",
         "options": (_NOBODY, *apprentices), "value": _NOBODY},
        {"key": "summary", "label": "What was said", "kind": "text", "required": True},
        {"key": "follow_up_date", "label": "Follow up by",
         "help": "YYYY-MM-DD. Leave blank if nothing needs to happen next."},
    ]

    def save(values: dict[str, Any]) -> object:
        return employer_contact_service.log_contact(gui.actor, employer_id, {
            "contacted_on": values.get("contacted_on"),
            "channel": values.get("channel"),
            "contact_id": people.get(values.get("contact") or ""),
            "apprentice_id": apprentices.get(values.get("apprentice") or ""),
            "summary": values.get("summary"),
            "follow_up_date": values.get("follow_up_date"),
        })

    if widgets.FormDialog(gui.root, "Log a contact", fields, save).saved:
        reload()


# ═════════════════════════════════════════════════════════════════════
# Commitments
# ═════════════════════════════════════════════════════════════════════

def _commitments(gui: Any, parent: Any, employer_id: int,
                 commitments: list[EmployerCommitment], today: date,
                 reload: Callable[[], None]) -> None:
    box = widgets.section(parent, "Commitments")
    by_id = {c.commitment_id: c for c in commitments}
    table: widgets.DataTable | None = None

    def selected(action: str) -> EmployerCommitment | None:
        if table is None:
            widgets.warn("There are no commitments yet.", title="Nothing to choose")
            return None
        ident = table.require_selection_int(action)
        return by_id.get(ident) if ident is not None else None

    def add() -> None:
        _commitment_form(gui, employer_id, None, reload)

    def edit() -> None:
        commitment = selected("edit a commitment")
        if commitment is not None:
            _commitment_form(gui, employer_id, commitment, reload)

    def escalate() -> None:
        commitment = selected("escalate a commitment")
        if commitment is None:
            return
        level = min(commitment.escalation_level + 1, config.COMMITMENT_MAX_ESCALATION)
        reason = widgets.ask_reason(
            f"Why is “{commitment.commitment}” being escalated to level {level} "
            f"({config.COMMITMENT_ESCALATION_LEVELS[level]})?"
        )
        if not reason:
            return
        ok, _ = widgets.guard(lambda: employer_contact_service.escalate_commitment(
            gui.actor, commitment.commitment_id, reason=reason
        ))
        if ok:
            reload()

    def met() -> None:
        commitment = selected("mark a commitment met")
        if commitment is None or not widgets.confirm(
            f"Mark “{commitment.commitment}” as met?"
        ):
            return
        ok, _ = widgets.guard(lambda: employer_contact_service.close_commitment(
            gui.actor, commitment.commitment_id, status="Met"
        ))
        if ok:
            reload()

    def withdraw() -> None:
        commitment = selected("withdraw a commitment")
        if commitment is None:
            return
        reason = widgets.ask_reason(f"Why is “{commitment.commitment}” being withdrawn?")
        if not reason:
            return
        ok, _ = widgets.guard(lambda: employer_contact_service.close_commitment(
            gui.actor, commitment.commitment_id, status="Withdrawn", note=reason
        ))
        if ok:
            reload()

    if gui.actor.can("employer.contact"):
        widgets.button_bar(box, [
            ("Add commitment…", add), ("Edit…", edit), ("Escalate…", escalate),
            ("Mark met", met), ("Withdraw…", withdraw),
        ])
    if not commitments:
        widgets.empty_state(
            box,
            "No commitments recorded. Note what the employer has undertaken — release for "
            "training, a mentor, attending reviews — so it can be followed up.",
        )
        return
    table = widgets.DataTable(box, COMMITMENT_COLUMNS, height=min(8, len(commitments)))
    table.populate(
        commitments,
        lambda c: (
            c.commitment, c.category, c.apprentice_name,
            (c.due_date or "") + (" (overdue)" if c.is_overdue(today) else ""),
            c.status, c.escalation_label,
        ),
        identity=lambda c: c.commitment_id,
        tag=lambda c: c.rag(today),
        noun="commitment",
    )


def _commitment_form(gui: Any, employer_id: int, commitment: EmployerCommitment | None,
                     reload: Callable[[], None]) -> None:
    apprentices = _apprentice_choices(gui, employer_id)
    current_apprentice = next(
        (label for label, key in apprentices.items()
         if commitment is not None and key == commitment.apprentice_id), _NOBODY,
    )

    def current(attr: str, default: Any = "") -> Any:
        value = getattr(commitment, attr, None) if commitment is not None else None
        return default if value is None else value

    fields = [
        {"key": "commitment", "label": "Commitment", "required": True,
         "value": current("commitment")},
        {"key": "category", "label": "Category", "kind": "combo",
         "options": config.COMMITMENT_CATEGORIES, "value": current("category", "Other")},
        {"key": "apprentice", "label": "Apprentice", "kind": "combo",
         "options": (_NOBODY, *apprentices), "value": current_apprentice,
         "help": "Leave blank for a commitment about the employer as a whole."},
        {"key": "due_date", "label": "Due", "value": current("due_date"),
         "help": "YYYY-MM-DD. An open commitment past this date is flagged."},
        {"key": "notes", "label": "Notes", "kind": "text", "value": current("notes")},
    ]

    def save(values: dict[str, Any]) -> object:
        payload = {k: v for k, v in values.items() if k != "apprentice"}
        payload["apprentice_id"] = apprentices.get(values.get("apprentice") or "")
        if commitment is None:
            return employer_contact_service.add_commitment(gui.actor, employer_id, payload)
        return employer_contact_service.update_commitment(
            gui.actor, commitment.commitment_id, payload
        )

    dialog = widgets.FormDialog(
        gui.root, "Edit commitment" if commitment else "Add commitment", fields, save,
    )
    if dialog.saved:
        reload()


def _apprentice_choices(gui: Any, employer_id: int) -> dict[str, int]:
    """This employer's apprentices that the actor may see, label -> id."""
    ok, people = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor, employer_id=employer_id)
    )
    return {
        f"{s.full_name} ({s.apprentice.status})": s.apprentice.apprentice_id
        for s in (people or [])
    } if ok else {}
