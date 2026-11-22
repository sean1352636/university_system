"""Qualifications and achievements, for everyone with a stake in them.

Prior qualifications decide eligibility and recognised prior learning;
those taken and achieved during the programme are what the apprentice
leaves with. Provider staff record them; the apprentice and their
employer read them. The service scopes what each sees, and the buttons
follow the permissions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.learner_support.qualifications import (
    Qualification,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.assessments import qualification_service

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

QUALIFICATION_COLUMNS = (
    ("title", "Qualification", 260),
    ("level", "Level", 80),
    ("body", "Awarding body", 140),
    ("ref", "QAN / ref", 100),
    ("status", "Status", 100),
    ("grade", "Grade", 70),
    ("start", "Started", 100),
    ("achieved", "Achieved", 100),
    ("cert", "Certificate", 110),
    ("rpl", "Prior learning", 100),
)

_STATUS_TAGS = {"Achieved": "Green", "Held (prior)": "muted"}


def render(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(
        frame,
        "Qualifications",
        subtitle="What the apprentice held before the programme, is working towards, "
                 "and has achieved.",
    )
    if gui.actor.role == config.APPRENTICE:
        if gui.actor.apprentice_id is None:
            widgets.empty_state(frame, UNLINKED)
            return
        _record(gui, frame, gui.actor.apprentice_id, reload=lambda: render(gui))
        return

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
        apprentice_id = table.require_selection_int("open their qualifications")
        if apprentice_id is not None:
            _open(gui, apprentice_id)

    widgets.button_bar(frame, [("Open qualifications →", open_selected)])
    table.populate(
        people,
        lambda s: (s.full_name, s.programme_title, s.employer_name, s.apprentice.status),
        identity=lambda s: s.apprentice.apprentice_id,
        noun="apprentice",
    )


def _open(gui: Any, apprentice_id: int) -> None:
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    name = summary.full_name if ok and summary else f"Apprentice {apprentice_id}"
    widgets.heading(frame, f"Qualifications — {name}")
    widgets.button_bar(frame, [("← All apprentices", lambda: render(gui))])
    if ok:
        _record(gui, frame, apprentice_id, reload=lambda: _open(gui, apprentice_id))


def _record(gui: Any, frame: Any, apprentice_id: int, *, reload: Callable[[], None]) -> None:
    ok, rows = widgets.guard(lambda: qualification_service.list_qualifications(
        gui.actor, apprentice_id=apprentice_id
    ))
    if not ok:
        return
    by_id = {q.qualification_id: q for q in rows}

    widgets.kpi_row(frame, [
        ("Held before the programme", sum(1 for q in rows if q.is_prior)),
        ("In progress", sum(1 for q in rows if q.status == "In progress")),
        ("Achieved", sum(1 for q in rows if q.status == "Achieved")),
        ("Recognised prior learning", sum(1 for q in rows if q.relevant_prior_learning)),
        ("Awaiting certificate", sum(1 for q in rows if q.awaiting_certificate)),
    ])

    table: widgets.DataTable | None = None

    def selected(action: str) -> Qualification | None:
        if table is None:
            widgets.warn("There are no qualifications yet.", title="Nothing to choose")
            return None
        ident = table.require_selection_int(action)
        return by_id.get(ident) if ident is not None else None

    def add() -> None:
        _form(gui, apprentice_id, None, reload)

    def edit() -> None:
        qualification = selected("edit a qualification")
        if qualification is not None:
            _form(gui, apprentice_id, qualification, reload)

    def delete() -> None:
        qualification = selected("delete a qualification")
        if qualification is None:
            return
        reason = widgets.ask_reason(f"Why is “{qualification.title}” being deleted?")
        if not reason:
            return
        ok, _ = widgets.guard(lambda: qualification_service.delete_qualification(
            gui.actor, qualification.qualification_id, reason=reason
        ))
        if ok:
            reload()

    if gui.actor.can("qualification.manage"):
        widgets.button_bar(frame, [("Add…", add), ("Edit…", edit), ("Delete…", delete)])

    if not rows:
        widgets.empty_state(frame, "No qualifications have been recorded yet.")
        return
    table = widgets.DataTable(frame, QUALIFICATION_COLUMNS)
    table.populate(
        rows,
        lambda q: (
            q.title, q.level, q.awarding_body, q.reference, q.status, q.grade,
            q.start_date, q.achieved_date, q.certificate_ref,
            "Yes" if q.relevant_prior_learning else "",
        ),
        identity=lambda q: q.qualification_id,
        tag=lambda q: _STATUS_TAGS.get(q.status),
        noun="qualification",
    )


def _form(gui: Any, apprentice_id: int, qualification: Qualification | None,
          reload: Callable[[], None]) -> None:
    def current(attr: str, default: Any = "") -> Any:
        value = getattr(qualification, attr, None) if qualification is not None else None
        return default if value is None else value

    fields = [
        {"key": "title", "label": "Qualification", "required": True, "value": current("title")},
        {"key": "level", "label": "Level", "kind": "combo",
         "options": ["", *config.QUALIFICATION_LEVELS], "value": current("level")},
        {"key": "awarding_body", "label": "Awarding body", "value": current("awarding_body")},
        {"key": "reference", "label": "QAN / reference", "value": current("reference"),
         "help": "The Qualification Accreditation Number, e.g. 603/1234/5."},
        {"key": "status", "label": "Status", "kind": "combo",
         "options": config.QUALIFICATION_STATUSES, "value": current("status", "In progress")},
        {"key": "grade", "label": "Grade", "value": current("grade")},
        {"key": "start_date", "label": "Started", "value": current("start_date"),
         "help": "YYYY-MM-DD."},
        {"key": "achieved_date", "label": "Achieved", "value": current("achieved_date"),
         "help": "YYYY-MM-DD. Defaults to today when Achieved."},
        {"key": "certificate_ref", "label": "Certificate ref",
         "value": current("certificate_ref")},
        {"key": "relevant_prior_learning", "label": "Recognised prior learning",
         "kind": "check", "value": current("relevant_prior_learning", False),
         "help": "Only for a qualification held before the programme."},
        {"key": "notes", "label": "Notes", "kind": "text", "value": current("notes")},
    ]

    def save(values: dict[str, Any]) -> object:
        if qualification is None:
            return qualification_service.add_qualification(gui.actor, apprentice_id, values)
        return qualification_service.update_qualification(
            gui.actor, qualification.qualification_id, values
        )

    dialog = widgets.FormDialog(
        gui.root, "Edit qualification" if qualification else "Add a qualification",
        fields, save,
    )
    if dialog.saved:
        reload()
