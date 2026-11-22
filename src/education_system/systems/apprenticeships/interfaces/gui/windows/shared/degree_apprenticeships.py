"""Degree apprenticeships: the university half of one learner journey.

Providers (admin and tutors) see the reconciliation list for the links
in their scope, and admin can map programmes and link learners. An
apprentice sees their own academic progress. The academic data is
owned by the university and only read here.
"""

from __future__ import annotations

from typing import Any

from tkinter import ttk

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.programmes import (
    degree_apprenticeship_service as service,
)
from education_system.systems.apprenticeships.application.security.access import PermissionDenied

TITLE = "Degree Apprenticeships"
SUBTITLE = (
    "One learner journey, with apprenticeship and university records "
    "active together. Academic data shown here remains university-owned."
)


def render(gui) -> None:
    if gui.actor.role == config.APPRENTICE:
        _render_own(gui)
        return
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)
    table = widgets.DataTable(
        frame,
        (("name", "Apprentice", 190), ("university", "University ID", 120),
         ("link", "Link", 90), ("state", "Reconciliation", 210),
         ("sync", "Last academic sync", 160), ("issues", "Issues", 340)),
        on_activate=lambda ident: _show_progress(gui, int(ident)),
    )
    names: dict[int, str] = {}

    def reload() -> None:
        ok, rows = widgets.guard(
            lambda: service.reconciliation_dashboard(gui.actor)
        )
        names.clear()
        names.update({int(r["apprentice_id"]): r["apprentice_name"] for r in rows or []})
        table.populate(
            rows or [],
            lambda row: (
                row["apprentice_name"], row["university_student_id"],
                row["link_status"], row["reconciliation_state"],
                row["last_academic_sync_at"], "; ".join(row["issues"]),
            ),
            identity=lambda row: row["apprentice_id"],
            noun="degree-apprenticeship link",
        )

    def progress() -> None:
        apprentice_id = table.require_selection_int("see academic progress")
        if apprentice_id is not None:
            _show_progress(gui, apprentice_id, names.get(apprentice_id))

    buttons = []
    if gui.actor.can("programme.manage"):
        buttons.append(("Map programme", lambda: _map(gui)))
    if gui.actor.can("apprentice.manage"):
        buttons.append(("Link apprentice", lambda: _link(gui)))
    buttons += [("Academic Progress…", progress), ("Refresh", reload)]
    widgets.button_bar(frame, buttons)
    reload()


def _render_own(gui) -> None:
    """The apprentice's own view: where they are on the degree."""
    frame = gui.clear()
    widgets.heading(frame, "University Degree", subtitle=SUBTITLE)
    if gui.actor.apprentice_id is None:
        widgets.empty_state(
            frame,
            "Your login is not linked to an apprentice record yet. "
            "Ask your provider to link it, then sign in again.",
        )
        return
    try:
        progress = service.academic_progress(gui.actor, gui.actor.apprentice_id)
    except (ValidationError, PermissionDenied) as exc:  # no link, or nothing received yet
        widgets.empty_state(frame, str(exc))
        return
    widgets.field_grid(frame, _progress_pairs(progress))


def _show_progress(gui, apprentice_id: int, name: str | None = None) -> None:
    ok, progress = widgets.guard(
        lambda: service.academic_progress(gui.actor, apprentice_id),
        title="Academic progress",
    )
    if not ok:
        return
    win = widgets.open_window(gui.root, f"Academic progress — {name or apprentice_id}")
    body = ttk.Frame(win, padding=14)
    body.pack(fill="both", expand=True)
    widgets.heading(body, name or f"Apprentice {apprentice_id}",
                    subtitle="As last received from the university.")
    widgets.field_grid(body, _progress_pairs(progress))
    widgets.button_bar(body, [("Close", win.destroy)])


def _progress_pairs(progress: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        ("University student", progress.get("university_student_id")),
        ("Degree", progress.get("degree_program_name")),
        ("Registration", progress.get("registration_status")),
        ("Credits", f"{progress.get('credits_earned', 0)} / "
                    f"{progress.get('credits_required', 0)}"),
        ("Modules completed", progress.get("modules_completed")),
        ("Academic standing", progress.get("academic_standing")),
        ("University gateway confirmed",
         "Yes" if progress.get("university_gateway_confirmed") else "No"),
        ("Degree outcome", progress.get("degree_outcome")),
    ]


def _map(gui) -> None:
    def save(values: dict[str, Any]) -> None:
        service.map_programme(
            gui.actor, int(values["apprenticeship_programme_id"]),
            int(values["university_degree_program_id"]),
            credits_required=(float(values["credits_required"])
                              if values.get("credits_required") else None),
            integration_type=str(values["integration_type"]),
        )

    dialog = widgets.FormDialog(
        gui.root, "Map degree programme",
        [
            {"key": "apprenticeship_programme_id", "label": "Apprenticeship programme ID", "required": True},
            {"key": "university_degree_program_id", "label": "University degree programme ID", "required": True},
            {"key": "credits_required", "label": "Credits required"},
            {"key": "integration_type", "label": "Integration type", "kind": "combo",
             "options": tuple(sorted(service.INTEGRATION_TYPES)), "value": "Integrated"},
        ], save,
    )
    if dialog.saved:
        gui.refresh()


def _link(gui) -> None:
    def save(values: dict[str, Any]) -> None:
        service.link_learner(
            gui.actor, int(values["apprentice_id"]),
            journey_id=str(values["journey_id"]),
            university_student_id=str(values["university_student_id"]),
            institution_id=str(values.get("institution_id") or "") or None,
            start_date=str(values.get("start_date") or "") or None,
        )

    dialog = widgets.FormDialog(
        gui.root, "Link degree apprentice",
        [
            {"key": "apprentice_id", "label": "Apprentice ID", "required": True},
            {"key": "journey_id", "label": "Shared journey ID", "required": True},
            {"key": "university_student_id", "label": "Requested/existing university student ID", "required": True},
            {"key": "institution_id", "label": "Institution ID"},
            {"key": "start_date", "label": "University start date"},
        ], save,
    )
    if dialog.saved:
        gui.refresh()
