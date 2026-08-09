"""The employer's own cohort, read-only."""

from __future__ import annotations

import logging

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.interfaces.gui.windows.employer.dashboard import (
    UNLINKED_MESSAGE,
)
from education_system.systems.apprenticeships.services import apprentice_service, training_service

logger = logging.getLogger(__name__)

SUBTITLE = (
    "Everyone you employ on an apprenticeship, and how far through they are. "
    "The records themselves belong to the training provider — programme, tutor and "
    "enrolment changes are theirs to make, so there is nothing to edit here. Raise "
    "anything that looks wrong with the tutor."
)

_COLUMNS = (
    ("name", "Apprentice", 190),
    ("programme", "Programme", 210),
    ("workplace", "Workplace", 150),
    ("tutor", "Tutor", 150),
    ("status", "Status", 130),
    ("otj", "Off-the-job", 100, "e"),
    ("ksb", "KSBs", 80, "e"),
    ("gateway", "Gateway", 110),
)


def render(gui) -> None:
    """The apprentices this employer employs, with an in-pane detail view."""
    frame = gui.clear()
    widgets.heading(frame, "My Apprentices", subtitle=SUBTITLE)
    if gui.actor.employer_id is None:
        widgets.empty_state(frame, UNLINKED_MESSAGE)
        return

    ok, initial = widgets.guard(lambda: apprentice_service.list_apprentices(gui.actor))
    if not ok:
        return
    if not initial:
        widgets.empty_state(
            frame,
            "No apprentices are recorded against your organisation yet. They appear "
            "here once the training provider enrols them against your name.",
        )
        return

    def fill(rows) -> None:
        table.populate(
            rows,
            lambda s: (
                s.full_name, s.programme_title, s.workplace_name, s.tutor_name,
                s.apprentice.status, widgets.percent(s.otj_percent),
                widgets.percent(s.ksb_percent), s.gateway_status,
            ),
            identity=lambda s: s.apprentice.apprentice_id,
            tag=lambda s: s.apprentice.status,
            noun="apprentice",
        )

    def reload() -> None:
        found, rows = widgets.guard(
            lambda: apprentice_service.list_apprentices(gui.actor, **filters.values())
        )
        if found:
            fill(rows)

    # Built before the table so the filters sit above it; ``reload`` closes
    # over both and is not called until they exist.
    filters = widgets.FilterBar(
        frame,
        [("status", "Status", "combo", config.APPRENTICE_STATUSES),
         ("search", "Search", "entry")],
        reload,
    )
    table = widgets.DataTable(
        frame, _COLUMNS, on_activate=lambda chosen: _detail(gui, int(chosen))
    )
    widgets.button_bar(frame, [("View Detail", lambda: _open_selected(gui, table))])
    fill(initial)


def _open_selected(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("view an apprentice")
    if apprentice_id is not None:
        _detail(gui, apprentice_id)


def _detail(gui, apprentice_id: int) -> None:
    """One apprentice's record and off-the-job position, in the same pane."""
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    if not ok:
        render(gui)
        return

    record = summary.apprentice
    widgets.heading(
        frame, summary.full_name,
        subtitle=f"{summary.programme_title or 'No programme'} · {record.status}",
    )
    widgets.button_bar(frame, [("← Back to list", lambda: render(gui))])

    body = widgets.scrollable(frame)
    widgets.field_grid(widgets.section(body, "Record"), [
        ("ULN", record.uln),
        ("Status", record.status),
        ("Programme", summary.programme_title),
        ("Level", summary.programme_level),
        ("Workplace", summary.workplace_name),
        ("Tutor", summary.tutor_name),
        ("Started", record.start_date),
        ("Planned end", record.planned_end_date),
        ("Contracted hours a week", record.weekly_hours),
        ("Funding model", record.funding_model),
        ("Gateway", summary.gateway_status),
        ("KSBs competent", f"{summary.ksbs_competent} of {summary.ksbs_total}"),
    ], columns=3)

    hours_box = widgets.section(body, "Off-the-job training")
    ok, hours = widgets.guard(lambda: training_service.otj_summary(gui.actor, apprentice_id))
    if not ok:
        return
    widgets.progress_row(
        hours_box, "Approved hours against target", hours.percent_complete,
        detail=f"{hours.approved_hours:,.0f} of {hours.target_hours:,.0f} hours",
        rag=hours.rag_rating,
    )
    widgets.progress_row(
        hours_box, "Where the programme dates say they should be", hours.expected_percent,
        detail=f"{hours.expected_to_date:,.0f} hours expected by today",
    )
    widgets.field_grid(hours_box, [
        ("Approved", f"{hours.approved_hours:,.1f} hrs"),
        ("Awaiting approval", f"{hours.pending_hours:,.1f} hrs"),
        ("Still in draft", f"{hours.draft_hours:,.1f} hrs"),
        ("Remaining to target", f"{hours.remaining_hours:,.1f} hrs"),
        ("Needed each week from here", f"{hours.weekly_hours_needed:,.1f} hrs"),
        ("On track", "Yes" if hours.is_on_track else "No"),
    ], columns=3)
