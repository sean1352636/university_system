"""Degree-apprenticeship links and reconciliation for provider administrators."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    degree_apprenticeship_service as service,
)


def render(gui) -> None:
    frame = gui.clear()
    widgets.heading(
        frame, "Degree Apprenticeships",
        subtitle=(
            "One learner journey, with apprenticeship and university records "
            "active together. Academic data shown here remains university-owned."
        ),
    )
    table = widgets.DataTable(
        frame,
        (("name", "Apprentice", 190), ("university", "University ID", 120),
         ("link", "Link", 90), ("state", "Reconciliation", 210),
         ("sync", "Last academic sync", 160), ("issues", "Issues", 340)),
    )

    def reload() -> None:
        ok, rows = widgets.guard(
            lambda: service.reconciliation_dashboard(gui.actor)
        )
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

    widgets.button_bar(frame, [
        ("Map programme", lambda: _map(gui)),
        ("Link apprentice", lambda: _link(gui)),
        ("Refresh", reload),
    ])
    reload()


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
