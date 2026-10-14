"""Complaints, for whoever raised one and for the provider handling them.

Everyone may raise a complaint here and follow their own. Provider
administrators see every complaint, with the late ones flagged, and
move each one along: acknowledge, investigate, resolve, escalate,
close. One screen serves both — the service decides what each actor may
see, and the buttons follow the same permissions, so a complainant is
never offered an action that would only be refused.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.quality.complaints import Complaint
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    complaint_service,
)

logger = logging.getLogger(__name__)

COLUMNS = (
    ("ref", "Ref", 90),
    ("received", "Received", 100),
    ("from", "From", 190),
    ("about", "About", 170),
    ("category", "Category", 150),
    ("subject", "Subject", 240),
    ("status", "Status", 110),
    ("due", "Next deadline", 110),
    ("flag", "", 170),
)

OWN_COLUMNS = (
    ("ref", "Ref", 90),
    ("received", "Received", 100),
    ("category", "Category", 150),
    ("subject", "Subject", 300),
    ("status", "Status", 110),
    ("due", "Response due", 110),
)

UPDATE_COLUMNS = (
    ("when", "When", 150),
    ("who", "From", 220),
    ("shared", "Shared", 70),
    ("note", "Note", 600),
)

_NOBODY = "(not about a particular apprentice)"


def render(gui: Any) -> None:
    """Every complaint for a handler; your own for anyone else."""
    frame = gui.clear()
    manager = gui.actor.can("complaint.manage")
    widgets.heading(
        frame,
        "Complaints",
        subtitle=(
            f"Every complaint must be acknowledged within {config.COMPLAINT_ACK_DAYS} days "
            f"and answered within {config.COMPLAINT_RESPONSE_DAYS}. Late ones are shown red."
            if manager else
            f"Tell us what has gone wrong. We acknowledge every complaint within "
            f"{config.COMPLAINT_ACK_DAYS} days and respond within "
            f"{config.COMPLAINT_RESPONSE_DAYS}."
        ),
    )
    today = date.today()

    if manager:
        ok, totals = widgets.guard(lambda: complaint_service.counts(gui.actor))
        if ok:
            widgets.kpi_row(frame, [
                ("Open", totals["open"]),
                ("Awaiting acknowledgement", totals["awaiting_ack"]),
                ("Overdue", totals["overdue"]),
                ("All complaints", totals["total"]),
            ])
        filters = widgets.FilterBar(
            frame,
            (
                ("status", "Status", "combo", config.COMPLAINT_STATUSES),
                ("category", "Category", "combo", config.COMPLAINT_CATEGORIES),
                ("open_only", "Open only", "check"),
                ("overdue_only", "Overdue only", "check"),
            ),
            lambda: reload(),
        )

    table = widgets.DataTable(
        frame, COLUMNS if manager else OWN_COLUMNS,
        on_activate=lambda ident: _open(gui, int(ident)),
    )

    def reload() -> None:
        values = filters.values() if manager else {}
        ok, rows = widgets.guard(lambda: complaint_service.list_complaints(gui.actor, **values))
        rows = rows or []
        if manager:
            table.populate(
                rows,
                lambda c: (
                    c.reference, c.received_at, f"{c.raised_by} ({c.raised_role_label})",
                    _about(c), c.category, c.subject, c.status, c.next_deadline(),
                    c.overdue_label(today),
                ),
                identity=lambda c: c.complaint_id,
                tag=lambda c: c.rag(today),
                noun="complaint",
            )
        else:
            table.populate(
                rows,
                lambda c: (
                    c.reference, c.received_at, c.category, c.subject, c.status,
                    c.response_due_on if c.is_open else "",
                ),
                identity=lambda c: c.complaint_id,
                noun="complaint",
            )

    def open_selected() -> None:
        complaint_id = table.require_selection_int("open a complaint")
        if complaint_id is not None:
            _open(gui, complaint_id)

    buttons: list[tuple[str, Callable[[], None]]] = [("Open →", open_selected)]
    if gui.actor.can("complaint.raise"):
        buttons.append(("Raise a complaint…", lambda: _raise(gui, lambda: render(gui))))
    widgets.button_bar(frame, buttons)
    reload()


def _about(complaint: Complaint) -> str:
    return complaint.apprentice_name or complaint.employer_name or ""


# ═════════════════════════════════════════════════════════════════════
# One complaint
# ═════════════════════════════════════════════════════════════════════

def _open(gui: Any, complaint_id: int) -> None:
    frame = gui.clear()
    ok, complaint = widgets.guard(
        lambda: complaint_service.get_complaint(gui.actor, complaint_id)
    )
    if not ok:
        widgets.heading(frame, "Complaint")
        widgets.button_bar(frame, [("← All complaints", lambda: render(gui))])
        return
    today = date.today()
    manager = gui.actor.can("complaint.manage")
    reload = lambda: _open(gui, complaint_id)  # noqa: E731

    widgets.heading(
        frame, f"{complaint.reference} — {complaint.subject}",
        subtitle=complaint.overdue_label(today) or complaint.status,
    )

    buttons: list[tuple[str, Callable[[], None]]] = [("← All complaints", lambda: render(gui))]
    if manager:
        if complaint.status == "Received":
            buttons.append(("Acknowledge", lambda: _acknowledge(gui, complaint, reload)))
        if complaint.allowed_next():
            buttons.append(("Change status…", lambda: _status_form(gui, complaint, reload)))
        buttons += [
            ("Assign handler…", lambda: _assign(gui, complaint, reload)),
            ("Add note…", lambda: _note_form(gui, complaint, reload, manager=True)),
        ]
    else:
        if complaint.status != "Closed":
            buttons.append(("Add a comment…",
                            lambda: _note_form(gui, complaint, reload, manager=False)))
    if (complaint.status in ("Resolved", "Escalated", "Closed")
            and complaint.satisfied is None
            and (manager or complaint_service.is_complainant(gui.actor, complaint))):
        buttons.append(("Were you satisfied?…" if not manager else "Record satisfaction…",
                        lambda: _satisfaction(gui, complaint, reload)))
    widgets.button_bar(frame, buttons)

    body = widgets.scrollable(frame)
    pairs: list[tuple[str, Any]] = [
        ("Status", complaint.status),
        ("Category", complaint.category),
        ("Received", complaint.received_at),
        ("Acknowledge by", complaint.ack_due_on),
        ("Acknowledged", complaint.acknowledged_at),
        ("Respond by", complaint.response_due_on),
        ("Raised by", f"{complaint.raised_by} ({complaint.raised_role_label})"),
        ("Handled by", complaint.handler),
        ("Apprentice", complaint.apprentice_name),
        ("Employer", complaint.employer_name),
        ("Escalated to", complaint.escalated_to),
        ("Closed", complaint.closed_at),
        ("Satisfied with the response",
         None if complaint.satisfied is None else complaint.satisfied),
    ]
    widgets.field_grid(body, pairs, columns=3)

    widgets.field_grid(widgets.section(body, "The complaint"),
                       [("", complaint.description)], columns=1)
    if complaint.outcome:
        widgets.field_grid(widgets.section(body, "Outcome"),
                           [("", complaint.outcome)], columns=1)

    box = widgets.section(body, "Record" if manager else "Updates")
    ok, updates = widgets.guard(lambda: complaint_service.list_updates(gui.actor, complaint_id))
    if not ok:
        return
    if not updates:
        widgets.empty_state(box, "Nothing has been added yet.")
        return
    columns = UPDATE_COLUMNS if manager else tuple(c for c in UPDATE_COLUMNS if c[0] != "shared")
    table = widgets.DataTable(box, columns, height=min(10, len(updates)))
    table.populate(
        updates,
        lambda u: (
            (u.created_at, u.author_label, u.visible_to_complainant, u.note)
            if manager else (u.created_at, u.author_label, u.note)
        ),
        identity=lambda u: u.update_id,
        tag=lambda u: None if u.visible_to_complainant or not manager else "muted",
        noun="entry",
    )


# ═════════════════════════════════════════════════════════════════════
# Forms
# ═════════════════════════════════════════════════════════════════════

def _raise(gui: Any, reload: Callable[[], None]) -> None:
    people: dict[str, int] = {}
    if gui.actor.role != config.APPRENTICE and gui.actor.can("apprentice.view"):
        ok, summaries = widgets.guard(lambda: apprentice_service.list_apprentices(gui.actor))
        for s in summaries or []:
            people[f"{s.apprentice.apprentice_id} — {s.full_name}"] = s.apprentice.apprentice_id

    fields: list[dict[str, Any]] = [
        {"key": "category", "label": "What it is about", "kind": "combo",
         "options": config.COMPLAINT_CATEGORIES, "value": config.COMPLAINT_CATEGORIES[0],
         "required": True},
        {"key": "subject", "label": "Subject", "required": True},
        {"key": "description", "label": "What happened", "kind": "text", "required": True,
         "help": "Dates, names and what you would like to happen all help."},
    ]
    if people:
        fields.append({"key": "apprentice", "label": "Apprentice concerned", "kind": "combo",
                       "options": [_NOBODY, *people], "value": _NOBODY})
    if gui.actor.can("complaint.manage"):
        fields.append({"key": "received_at", "label": "Date received",
                       "value": date.today().isoformat(),
                       "help": "For a complaint that arrived by letter or phone. "
                               "The deadlines run from this date."})

    def save(values: dict[str, Any]) -> object:
        payload = {k: v for k, v in values.items() if k != "apprentice"}
        payload["apprentice_id"] = people.get(values.get("apprentice") or "")
        return complaint_service.raise_complaint(gui.actor, payload)

    dialog = widgets.FormDialog(gui.root, "Raise a complaint", fields, save,
                                save_label="Submit")
    if dialog.saved:
        widgets.inform(
            f"{dialog.result.reference} has been received. We will acknowledge it by "
            f"{dialog.result.ack_due_on}.",
            title="Complaint received",
        )
        reload()


def _acknowledge(gui: Any, complaint: Complaint, reload: Callable[[], None]) -> None:
    ok, _ = widgets.guard(
        lambda: complaint_service.acknowledge(gui.actor, complaint.complaint_id)
    )
    if ok:
        reload()


def _status_form(gui: Any, complaint: Complaint, reload: Callable[[], None]) -> None:
    options = complaint.allowed_next()
    fields = [
        {"key": "status", "label": "Move to", "kind": "combo", "options": options,
         "value": options[0], "required": True},
        {"key": "outcome", "label": "Outcome", "kind": "text",
         "value": complaint.outcome or "",
         "help": "Required to resolve: what was found and what will be done."},
        {"key": "escalated_to", "label": "Escalated to", "kind": "combo", "editable": True,
         "options": config.COMPLAINT_ESCALATION_BODIES, "value": complaint.escalated_to or "",
         "help": "Required to escalate."},
        {"key": "note", "label": "Note to the complainant", "kind": "text"},
    ]

    def save(values: dict[str, Any]) -> object:
        return complaint_service.change_status(
            gui.actor, complaint.complaint_id, values.get("status", ""),
            note=values.get("note"), outcome=values.get("outcome"),
            escalated_to=values.get("escalated_to"),
        )

    dialog = widgets.FormDialog(
        gui.root, f"Change status — {complaint.reference}", fields, save,
        intro=f"{complaint.reference} is {complaint.status}. The change is added to the "
              "record the complainant can see.",
    )
    if dialog.saved:
        reload()


def _assign(gui: Any, complaint: Complaint, reload: Callable[[], None]) -> None:
    fields = [{"key": "handler", "label": "Handler (username)", "required": True,
               "value": complaint.handler or gui.actor.username}]
    dialog = widgets.FormDialog(
        gui.root, "Assign handler", fields,
        lambda values: complaint_service.assign_handler(
            gui.actor, complaint.complaint_id, values.get("handler", "")
        ),
    )
    if dialog.saved:
        reload()


def _note_form(gui: Any, complaint: Complaint, reload: Callable[[], None], *,
               manager: bool) -> None:
    fields: list[dict[str, Any]] = [
        {"key": "note", "label": "Note" if manager else "Comment", "kind": "text",
         "required": True},
    ]
    if manager:
        fields.append({"key": "visible", "label": "Share with the complainant",
                       "kind": "check", "value": False})

    def save(values: dict[str, Any]) -> object:
        return complaint_service.add_update(
            gui.actor, complaint.complaint_id, values.get("note", ""),
            visible=bool(values.get("visible")),
        )

    dialog = widgets.FormDialog(
        gui.root, "Add a note" if manager else "Add a comment", fields, save,
        intro=("Unticked, the note stays internal to the provider." if manager else
               "Your comment is added to the complaint for the provider to read."),
    )
    if dialog.saved:
        reload()


def _satisfaction(gui: Any, complaint: Complaint, reload: Callable[[], None]) -> None:
    fields = [{"key": "satisfied", "label": "Satisfied with the response?", "kind": "combo",
               "options": ("Yes", "No"), "value": "Yes", "required": True}]
    dialog = widgets.FormDialog(
        gui.root, "How did we do?", fields,
        lambda values: complaint_service.record_satisfaction(
            gui.actor, complaint.complaint_id, values.get("satisfied") == "Yes"
        ),
    )
    if dialog.saved:
        reload()
