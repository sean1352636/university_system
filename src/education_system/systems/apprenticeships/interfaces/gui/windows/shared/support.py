"""Reasonable adjustments and support, for everyone with a stake in them.

Provider staff agree arrangements, own them and review them; the
apprentice sees all of their own; an employer sees only the ones the
apprentice has agreed to share, without the history underneath. The
service does that narrowing — this screen only shows what comes back —
and flags any arrangement whose review date has passed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.learner_support.support_arrangements import (
    SupportArrangement,
    SupportRecord,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    support_service,
)

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is nothing to "
    "show. Ask your training provider's administrator to link your account."
)

PICK_COLUMNS = (
    ("name", "Apprentice", 220),
    ("programme", "Programme", 240),
    ("employer", "Employer", 200),
    ("status", "Status", 130),
)

DUE_COLUMNS = (
    ("apprentice", "Apprentice", 200),
    ("category", "Need", 160),
    ("adjustment", "Adjustment", 300),
    ("review", "Review due", 110),
    ("owner", "Responsible", 170),
)

ARRANGEMENT_COLUMNS = (
    ("category", "Need", 150),
    ("adjustment", "Adjustment", 280),
    ("owner", "Responsible", 160),
    ("review", "Review due", 110),
    ("status", "Status", 110),
    ("shared", "Shared with employer", 150),
)

HISTORY_COLUMNS = (
    ("when", "When", 150),
    ("about", "Arrangement", 240),
    ("who", "From", 200),
    ("note", "Note", 460),
)

_NOBODY = ""


def render(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(
        frame,
        "Support & Adjustments",
        subtitle="Reasonable adjustments and the support around them — who owns each "
                 "one, and when it is next reviewed.",
    )
    if gui.actor.role == config.APPRENTICE:
        if gui.actor.apprentice_id is None:
            widgets.empty_state(frame, UNLINKED)
            return
        _record(gui, frame, gui.actor.apprentice_id, reload=lambda: render(gui))
        return

    if gui.actor.can("support.manage"):
        _due(gui, frame)

    ok, people = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor, active_only=True)
    )
    if not ok:
        return
    if not people:
        widgets.empty_state(frame, "There are no active apprentices whose records you can see.")
        return

    table = widgets.DataTable(
        frame, PICK_COLUMNS, on_activate=lambda ident: _open(gui, int(ident))
    )

    def open_selected() -> None:
        apprentice_id = table.require_selection_int("open their support")
        if apprentice_id is not None:
            _open(gui, apprentice_id)

    widgets.button_bar(frame, [("Open support record →", open_selected)])
    table.populate(
        people,
        lambda s: (s.full_name, s.programme_title, s.employer_name, s.apprentice.status),
        identity=lambda s: s.apprentice.apprentice_id,
        noun="apprentice",
    )


def _due(gui: Any, frame: Any) -> None:
    """Arrangements whose review is overdue or coming up, across the caseload."""
    ok, due = widgets.guard(lambda: support_service.due_for_review(gui.actor))
    if not ok:
        return
    box = widgets.section(
        frame, f"Reviews overdue or due within {config.SUPPORT_REVIEW_DUE_SOON_DAYS} days"
    )
    if not due:
        widgets.empty_state(box, "Nothing is due for review.")
        return
    by_id = {a.arrangement_id: a for a in due}
    today = date.today()
    table = widgets.DataTable(
        box, DUE_COLUMNS, height=min(5, len(due)),
        on_activate=lambda ident: _open(gui, by_id[int(ident)].apprentice_id),
    )

    def open_selected() -> None:
        ident = table.require_selection_int("open that apprentice's support")
        if ident is not None:
            _open(gui, by_id[ident].apprentice_id)

    widgets.button_bar(box, [("Open apprentice →", open_selected)])
    table.populate(
        due,
        lambda a: (a.apprentice_name, a.need_category, a.adjustment, a.review_date,
                   a.responsible_staff_name),
        identity=lambda a: a.arrangement_id,
        tag=lambda a: a.rag(today),
        noun="arrangement",
    )


def _open(gui: Any, apprentice_id: int) -> None:
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    name = summary.full_name if ok and summary else f"Apprentice {apprentice_id}"
    widgets.heading(frame, f"Support & Adjustments — {name}")
    widgets.button_bar(frame, [("← All apprentices", lambda: render(gui))])
    if ok:
        _record(gui, frame, apprentice_id, reload=lambda: _open(gui, apprentice_id))


def _record(gui: Any, frame: Any, apprentice_id: int, *, reload: Callable[[], None]) -> None:
    ok, record = widgets.guard(lambda: support_service.get_record(gui.actor, apprentice_id))
    if not ok:
        return
    today = date.today()
    body = widgets.scrollable(frame)
    widgets.kpi_row(body, [
        ("In force", len(record.in_force)),
        ("Review overdue", len(record.overdue(today))),
        ("Shared with employer", sum(1 for a in record.in_force if a.share_with_employer)),
    ])
    if gui.actor.role != config.EMPLOYER:
        # Context only: the free text from enrolment predates the structured
        # arrangements and is not migrated into them.
        box = widgets.section(body, "Support needs recorded at enrolment")
        widgets.empty_state(box, record.support_needs or "None recorded.")
    _arrangements(gui, body, record, today, reload)
    if gui.actor.role != config.EMPLOYER:
        _history(body, record)


def _arrangements(gui: Any, parent: Any, record: SupportRecord, today: date,
                  reload: Callable[[], None]) -> None:
    box = widgets.section(parent, "Arrangements")
    by_id = {a.arrangement_id: a for a in record.arrangements}
    table: widgets.DataTable | None = None

    def selected(action: str) -> SupportArrangement | None:
        if table is None:
            widgets.warn("There are no arrangements yet.", title="Nothing to choose")
            return None
        ident = table.require_selection_int(action)
        return by_id.get(ident) if ident is not None else None

    def add() -> None:
        _form(gui, record.apprentice_id, None, reload)

    def edit() -> None:
        arrangement = selected("edit an arrangement")
        if arrangement is not None:
            _form(gui, record.apprentice_id, arrangement, reload)

    def review() -> None:
        arrangement = selected("record a review")
        if arrangement is not None:
            _review_form(gui, arrangement, reload)

    def note() -> None:
        arrangement = selected("add a note")
        if arrangement is None:
            return
        fields = [{"key": "body", "label": "Note", "kind": "text", "required": True}]
        dialog = widgets.FormDialog(
            gui.root, "Add a note", fields,
            lambda v: support_service.add_note(
                gui.actor, arrangement.arrangement_id, v.get("body", "")
            ),
        )
        if dialog.saved:
            reload()

    def delete() -> None:
        arrangement = selected("delete an arrangement")
        if arrangement is None:
            return
        reason = widgets.ask_reason(
            "Why is this arrangement being deleted? For one that no longer applies, set "
            "it to Ended instead, which keeps its history."
        )
        if not reason:
            return
        ok, _ = widgets.guard(lambda: support_service.delete_arrangement(
            gui.actor, arrangement.arrangement_id, reason=reason
        ))
        if ok:
            reload()

    if gui.actor.can("support.manage"):
        widgets.button_bar(box, [
            ("Add…", add), ("Edit…", edit), ("Record review…", review),
            ("Add note…", note), ("Delete…", delete),
        ])

    if not record.arrangements:
        widgets.empty_state(
            box,
            "No arrangements are shared with you." if gui.actor.role == config.EMPLOYER
            else "No support arrangements have been recorded.",
        )
        return
    table = widgets.DataTable(box, ARRANGEMENT_COLUMNS, height=min(8, len(record.arrangements)))
    table.populate(
        record.arrangements,
        lambda a: (
            a.need_category, a.adjustment, a.responsible_staff_name,
            a.review_date + (" (overdue)" if a.is_review_overdue(today) else "")
            if a.review_date else None,
            a.status, a.share_with_employer,
        ),
        identity=lambda a: a.arrangement_id,
        tag=lambda a: a.rag(today),
        noun="arrangement",
    )
    details = [a for a in record.arrangements if a.arrangements]
    for arrangement in details:
        widgets.field_grid(box, [
            (f"{arrangement.need_category} — how it is delivered", arrangement.arrangements),
        ], columns=1)


def _history(parent: Any, record: SupportRecord) -> None:
    box = widgets.section(parent, "History")
    entries = [
        (n, a) for a in record.arrangements for n in a.notes
    ]
    entries.sort(key=lambda pair: (pair[0].created_at, pair[0].note_id), reverse=True)
    if not entries:
        widgets.empty_state(box, "Nothing has been noted yet.")
        return
    table = widgets.DataTable(box, HISTORY_COLUMNS, height=min(8, len(entries)))
    table.populate(
        entries,
        lambda pair: (pair[0].created_at, f"{pair[1].need_category}: {pair[1].adjustment}",
                      pair[0].author_label, pair[0].body),
        identity=lambda pair: pair[0].note_id,
        noun="note",
    )


def _staff_options() -> dict[str, int]:
    ok, staff = widgets.guard(lambda: staff_repository.list_all(active_only=True))
    return {f"{m.full_name} ({m.staff_role})": m.staff_id for m in (staff or [])} if ok else {}


def _form(gui: Any, apprentice_id: int, arrangement: SupportArrangement | None,
          reload: Callable[[], None]) -> None:
    staff = _staff_options()
    current_owner = next(
        (label for label, sid in staff.items()
         if arrangement is not None and sid == arrangement.responsible_staff_id), _NOBODY,
    )

    def current(attr: str, default: Any = "") -> Any:
        value = getattr(arrangement, attr, None) if arrangement is not None else None
        return default if value is None else value

    fields = [
        {"key": "need_category", "label": "Need", "kind": "combo",
         "options": config.SUPPORT_NEED_CATEGORIES,
         "value": current("need_category", config.SUPPORT_NEED_CATEGORIES[0])},
        {"key": "adjustment", "label": "Adjustment", "required": True,
         "value": current("adjustment"),
         "help": "What is being done differently, e.g. 25% extra time in assessments."},
        {"key": "arrangements", "label": "How it is delivered", "kind": "text",
         "value": current("arrangements")},
        {"key": "owner", "label": "Responsible", "kind": "combo",
         "options": [_NOBODY, *staff], "value": current_owner,
         "help": "Left blank, it is whoever records it."},
        {"key": "review_date", "label": "Review by", "required": True,
         "value": current("review_date"), "help": "YYYY-MM-DD."},
        {"key": "status", "label": "Status", "kind": "combo",
         "options": config.SUPPORT_STATUSES, "value": current("status", "Active")},
        {"key": "share_with_employer", "label": "Share with employer", "kind": "check",
         "value": current("share_with_employer", False),
         "help": "Only with the apprentice's agreement."},
    ]
    if arrangement is not None:
        fields.append({"key": "note", "label": "Note for the history", "kind": "text"})

    def save(values: dict[str, Any]) -> object:
        payload = {k: v for k, v in values.items() if k != "owner"}
        payload["responsible_staff_id"] = staff.get(values.get("owner") or "")
        if arrangement is None:
            return support_service.add_arrangement(gui.actor, apprentice_id, payload)
        return support_service.update_arrangement(gui.actor, arrangement.arrangement_id, payload)

    dialog = widgets.FormDialog(
        gui.root, "Edit arrangement" if arrangement else "Add an arrangement", fields, save,
    )
    if dialog.saved:
        reload()


def _review_form(gui: Any, arrangement: SupportArrangement, reload: Callable[[], None]) -> None:
    fields = [
        {"key": "outcome", "label": "What the review found", "kind": "text", "required": True},
        {"key": "next_review_date", "label": "Next review by", "help": "YYYY-MM-DD. Not "
         "needed if the arrangement is ending."},
        {"key": "status", "label": "Status", "kind": "combo",
         "options": config.SUPPORT_STATUSES, "value": arrangement.status},
    ]

    def save(values: dict[str, Any]) -> object:
        return support_service.record_review(
            gui.actor, arrangement.arrangement_id,
            outcome=values.get("outcome", ""),
            next_review_date=values.get("next_review_date") or None,
            status=values.get("status") or None,
        )

    dialog = widgets.FormDialog(
        gui.root, "Record a review", fields, save,
        intro=f"{arrangement.need_category}: {arrangement.adjustment}",
    )
    if dialog.saved:
        reload()
