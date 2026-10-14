"""Welfare and risk: who to worry about, the concerns, and the case notes.

For provider staff only — an administrator across the provider, a tutor
for their own caseload. The screen opens on the risk list, highest
first, with the reasons spelled out; below it the concerns still open.
An apprentice's page adds their risk profile and every concern about
them; a concern's page holds its case notes, which are never edited,
only added to.

Formal safeguarding referrals are not made here: they go to the
designated safeguarding lead through the platform's safeguarding process.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.learner_support.welfare import (
    WelfareConcern,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    welfare_service,
)

logger = logging.getLogger(__name__)

RISK_COLUMNS = (
    ("name", "Apprentice", 200),
    ("tutor", "Tutor", 160),
    ("level", "Risk", 80),
    ("score", "Score", 60, "e"),
    ("reasons", "Why", 560),
)

CONCERN_COLUMNS = (
    ("raised", "Raised", 150),
    ("apprentice", "Apprentice", 180),
    ("category", "Category", 130),
    ("severity", "Severity", 90),
    ("status", "Status", 100),
    ("assigned", "Assigned to", 160),
)

NOTE_COLUMNS = (
    ("when", "When", 150),
    ("who", "From", 200),
    ("note", "Note", 620),
)

_NOBODY = ""


def render(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(
        frame,
        "Welfare & Risk",
        subtitle="Apprentices showing warning signs, and the welfare concerns being held. "
                 "Restricted to provider staff.",
    )
    if not gui.actor.can("welfare.view"):
        widgets.empty_state(frame, "Welfare records are for provider staff only.")
        return

    body = widgets.scrollable(frame)
    _risk_list(gui, body)
    _open_concerns(gui, body)


def _risk_list(gui: Any, parent: Any) -> None:
    box = widgets.section(parent, "Risk across the caseload, highest first")
    ok, profiles = widgets.guard(lambda: welfare_service.at_risk(gui.actor, include_low=True))
    if not ok:
        return
    if not profiles:
        widgets.empty_state(box, "There are no active apprentices on your caseload.")
        return
    at_risk = sum(1 for p in profiles if p.is_at_risk)
    widgets.kpi_row(box, [
        ("High", sum(1 for p in profiles if p.level == "High")),
        ("Medium", sum(1 for p in profiles if p.level == "Medium")),
        ("No warning signs", len(profiles) - at_risk),
    ])
    table = widgets.DataTable(
        box, RISK_COLUMNS, height=min(10, len(profiles)),
        on_activate=lambda ident: _apprentice(gui, int(ident)),
    )

    def open_selected() -> None:
        apprentice_id = table.require_selection_int("open an apprentice")
        if apprentice_id is not None:
            _apprentice(gui, apprentice_id)

    widgets.button_bar(box, [("Open apprentice →", open_selected)])
    table.populate(
        profiles,
        lambda p: (p.apprentice_name, p.tutor_name, p.level, p.score,
                   "; ".join(p.reasons) or "—"),
        identity=lambda p: p.apprentice_id,
        tag=lambda p: p.rag,
        noun="apprentice",
    )


def _open_concerns(gui: Any, parent: Any) -> None:
    box = widgets.section(parent, "Open concerns")
    ok, concerns = widgets.guard(lambda: welfare_service.list_concerns(gui.actor, open_only=True))
    if not ok:
        return
    reload = lambda: render(gui)  # noqa: E731
    buttons: list[tuple[str, Callable[[], None]]] = []
    table: widgets.DataTable | None = None

    def open_selected() -> None:
        if table is None:
            return
        concern_id = table.require_selection_int("open a concern")
        if concern_id is not None:
            _concern(gui, concern_id, back=reload)

    if concerns:
        buttons.append(("Open concern →", open_selected))
    if gui.actor.can("welfare.manage"):
        buttons.append(("Raise a concern…", lambda: _raise_form(gui, None, reload)))
    if buttons:
        widgets.button_bar(box, buttons)
    if not concerns:
        widgets.empty_state(box, "No concerns are open.")
        return
    table = widgets.DataTable(
        box, CONCERN_COLUMNS, height=min(8, len(concerns)),
        on_activate=lambda ident: _concern(gui, int(ident), back=reload),
    )
    _populate_concerns(table, concerns)


def _populate_concerns(table: widgets.DataTable, concerns: list[WelfareConcern]) -> None:
    table.populate(
        concerns,
        lambda c: (c.raised_at, c.apprentice_name, c.category, c.severity, c.status,
                   c.assigned_name),
        identity=lambda c: c.concern_id,
        tag=lambda c: c.rag or "muted",
        noun="concern",
    )


# ═════════════════════════════════════════════════════════════════════
# One apprentice
# ═════════════════════════════════════════════════════════════════════

def _apprentice(gui: Any, apprentice_id: int) -> None:
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    name = summary.full_name if ok and summary else f"Apprentice {apprentice_id}"
    widgets.heading(frame, f"Welfare — {name}")
    widgets.button_bar(frame, [("← Welfare & Risk", lambda: render(gui))])
    if not ok:
        return
    reload = lambda: _apprentice(gui, apprentice_id)  # noqa: E731
    body = widgets.scrollable(frame)

    ok, profile = widgets.guard(lambda: welfare_service.risk_profile(gui.actor, apprentice_id))
    if ok:
        box = widgets.section(body, "Risk profile")
        widgets.kpi_row(box, [("Risk", profile.level), ("Score", profile.score)])
        if profile.reasons:
            for reason in profile.reasons:
                widgets.empty_state(box, f"• {reason}")
        else:
            widgets.empty_state(box, "No warning signs at the moment.")

    box = widgets.section(body, "Concerns")
    ok, concerns = widgets.guard(
        lambda: welfare_service.list_concerns(gui.actor, apprentice_id=apprentice_id)
    )
    if not ok:
        return
    table: widgets.DataTable | None = None

    def open_selected() -> None:
        if table is None:
            return
        concern_id = table.require_selection_int("open a concern")
        if concern_id is not None:
            _concern(gui, concern_id, back=reload)

    buttons: list[tuple[str, Callable[[], None]]] = []
    if concerns:
        buttons.append(("Open concern →", open_selected))
    if gui.actor.can("welfare.manage"):
        buttons.append(("Raise a concern…", lambda: _raise_form(gui, apprentice_id, reload)))
    if buttons:
        widgets.button_bar(box, buttons)
    if not concerns:
        widgets.empty_state(box, "No welfare concerns have been raised.")
        return
    table = widgets.DataTable(
        box, CONCERN_COLUMNS, height=min(8, len(concerns)),
        on_activate=lambda ident: _concern(gui, int(ident), back=reload),
    )
    _populate_concerns(table, concerns)


# ═════════════════════════════════════════════════════════════════════
# One concern
# ═════════════════════════════════════════════════════════════════════

def _concern(gui: Any, concern_id: int, *, back: Callable[[], None]) -> None:
    frame = gui.clear()
    ok, concern = widgets.guard(lambda: welfare_service.get_concern(gui.actor, concern_id))
    if not ok:
        back()
        return
    widgets.heading(
        frame, f"{concern.category} concern — {concern.apprentice_name}",
        subtitle=f"{concern.severity} severity, {concern.status}",
    )
    reload = lambda: _concern(gui, concern_id, back=back)  # noqa: E731
    buttons: list[tuple[str, Callable[[], None]]] = [("← Back", back)]
    if gui.actor.can("welfare.manage"):
        buttons += [
            ("Add case note…", lambda: _note_form(gui, concern, reload)),
            ("Edit…", lambda: _edit_form(gui, concern, reload)),
        ]
        for status in config.WELFARE_STATUSES:
            if status != concern.status:
                label = {"Open": "Reopen…" if concern.status == "Closed" else "Mark open…",
                         "Monitoring": "Monitor…", "Escalated": "Escalate…",
                         "Closed": "Close…"}[status]
                buttons.append((label, lambda s=status: _status_form(gui, concern, s, reload)))
    widgets.button_bar(frame, buttons)

    body = widgets.scrollable(frame)
    widgets.field_grid(body, [
        ("Apprentice", concern.apprentice_name),
        ("Assigned to", concern.assigned_name),
        ("Raised", f"{concern.raised_at} by {concern.raised_by}"),
        ("Status", concern.status),
        ("Escalated to", concern.escalated_to),
        ("Escalated", concern.escalated_at),
        ("Closed", concern.closed_at),
        ("Outcome", concern.outcome),
    ])
    box = widgets.section(body, "What was noticed")
    # empty_state's label, un-muted: this is the substance of the case.
    description = widgets.empty_state(box, concern.description)
    description.configure(foreground="", wraplength=900)

    box = widgets.section(body, "Case notes, oldest first")
    if not concern.notes:
        widgets.empty_state(box, "No case notes yet.")
        return
    table = widgets.DataTable(box, NOTE_COLUMNS, height=min(12, len(concern.notes)))
    table.populate(
        concern.notes,
        lambda n: (n.created_at, n.author_label, n.note),
        identity=lambda n: n.note_id,
        noun="note",
    )


# ═════════════════════════════════════════════════════════════════════
# Forms
# ═════════════════════════════════════════════════════════════════════

def _staff_options() -> dict[str, int]:
    ok, staff = widgets.guard(lambda: staff_repository.list_all(active_only=True))
    return {f"{m.full_name} ({m.staff_role})": m.staff_id for m in (staff or [])} if ok else {}


def _raise_form(gui: Any, apprentice_id: int | None, reload: Callable[[], None]) -> None:
    staff = _staff_options()
    people: dict[str, int] = {}
    fields: list[dict[str, Any]] = []
    if apprentice_id is None:
        ok, cohort = widgets.guard(
            lambda: apprentice_service.list_apprentices(gui.actor, active_only=True)
        )
        if not ok:
            return
        people = {f"{s.full_name} ({s.apprentice.apprentice_id})": s.apprentice.apprentice_id
                  for s in cohort}
        if not people:
            widgets.warn("There is nobody on your caseload to raise a concern about.",
                         title="Nobody to choose")
            return
        fields.append({"key": "apprentice", "label": "Apprentice", "kind": "combo",
                       "options": list(people), "required": True})
    fields += [
        {"key": "category", "label": "Category", "kind": "combo",
         "options": config.WELFARE_CATEGORIES, "value": config.WELFARE_CATEGORIES[0]},
        {"key": "severity", "label": "Severity", "kind": "combo",
         "options": config.WELFARE_SEVERITIES, "value": "Medium"},
        {"key": "description", "label": "What was noticed", "kind": "text", "required": True},
        {"key": "owner", "label": "Assigned to", "kind": "combo",
         "options": [_NOBODY, *staff], "value": _NOBODY,
         "help": "Left blank, it is whoever raises it."},
    ]

    def save(values: dict[str, Any]) -> object:
        target = apprentice_id if apprentice_id is not None else people.get(
            values.get("apprentice") or ""
        )
        if target is None:
            raise ValidationError("Choose the apprentice the concern is about")
        return welfare_service.raise_concern(gui.actor, target, {
            "category": values.get("category"),
            "severity": values.get("severity"),
            "description": values.get("description"),
            "assigned_to": staff.get(values.get("owner") or ""),
        })

    dialog = widgets.FormDialog(
        gui.root, "Raise a welfare concern", fields, save,
        intro="A safeguarding or Prevent concern must also be reported to the designated "
              "safeguarding lead straight away. This record does not do that for you.",
    )
    if dialog.saved:
        reload()


def _edit_form(gui: Any, concern: WelfareConcern, reload: Callable[[], None]) -> None:
    staff = _staff_options()
    current_owner = next(
        (label for label, sid in staff.items() if sid == concern.assigned_to), _NOBODY
    )
    fields = [
        {"key": "category", "label": "Category", "kind": "combo",
         "options": config.WELFARE_CATEGORIES, "value": concern.category},
        {"key": "severity", "label": "Severity", "kind": "combo",
         "options": config.WELFARE_SEVERITIES, "value": concern.severity},
        {"key": "description", "label": "What was noticed", "kind": "text",
         "value": concern.description},
        {"key": "owner", "label": "Assigned to", "kind": "combo",
         "options": [_NOBODY, *staff], "value": current_owner},
        {"key": "note", "label": "Note for the case", "kind": "text"},
    ]

    def save(values: dict[str, Any]) -> object:
        payload = {k: v for k, v in values.items() if k != "owner"}
        payload["assigned_to"] = staff.get(values.get("owner") or "")
        return welfare_service.update_concern(gui.actor, concern.concern_id, payload)

    dialog = widgets.FormDialog(
        gui.root, "Edit concern", fields, save,
        intro="Every change is written into the case notes as well.",
    )
    if dialog.saved:
        reload()


def _status_form(gui: Any, concern: WelfareConcern, status: str,
                 reload: Callable[[], None]) -> None:
    fields: list[dict[str, Any]] = []
    if status == "Escalated":
        fields.append({"key": "escalated_to", "label": "Escalated to", "required": True,
                       "help": "A person or agency, e.g. the DSL or the local authority."})
    if status == "Closed":
        fields.append({"key": "outcome", "label": "Outcome", "kind": "text", "required": True})
    fields.append({"key": "note", "label": "Case note", "kind": "text"})

    def save(values: dict[str, Any]) -> object:
        return welfare_service.change_status(
            gui.actor, concern.concern_id, status,
            note=values.get("note") or None,
            escalated_to=values.get("escalated_to") or None,
            outcome=values.get("outcome") or None,
        )

    dialog = widgets.FormDialog(
        gui.root, f"Move to {status}", fields, save,
        intro=f"The concern is {concern.status}. The change is recorded in the case notes.",
    )
    if dialog.saved:
        reload()


def _note_form(gui: Any, concern: WelfareConcern, reload: Callable[[], None]) -> None:
    fields = [{"key": "note", "label": "Case note", "kind": "text", "required": True}]
    dialog = widgets.FormDialog(
        gui.root, "Add a case note", fields,
        lambda v: welfare_service.add_note(gui.actor, concern.concern_id, v.get("note", "")),
        intro="Case notes cannot be edited or deleted afterwards.",
    )
    if dialog.saved:
        reload()
