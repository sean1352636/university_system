"""The skills matrix: every KSB and how far the apprentice has got with it.

Read-only. The levels come from the portfolio's own coverage rule — only
accepted evidence counts, and the best judgement wins — so this screen
and the gateway's portfolio check always agree. The apprentice sees
their own matrix; tutors, administrators and employers open on the
cohort, apprentices against % competent per KSB type, and drill into
one.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.progress.skills_matrix import (
    CohortRow,
    average_percent,
    level_bar,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.learning import skills_matrix_service

logger = logging.getLogger(__name__)

TITLE = "Skills Matrix"
SUBTITLE = (
    "Knowledge, skills and behaviours from the apprenticeship standard, each at the level "
    "the portfolio evidence has reached. Only evidence an assessor has accepted counts."
)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is no matrix to "
    "show. Ask your training provider's administrator to link your account."
)

COHORT_COLUMNS = (
    ("name", "Apprentice", 200),
    ("programme", "Programme", 220),
    ("employer", "Employer", 180),
    ("knowledge", "Knowledge %", 100, "e"),
    ("skill", "Skills %", 90, "e"),
    ("behaviour", "Behaviours %", 100, "e"),
    ("overall", "Overall %", 90, "e"),
    ("competent", "Competent", 90, "e"),
)

KSB_COLUMNS = (
    ("code", "KSB", 60),
    ("statement", "Statement", 460),
    ("level", "Level", 110),
    ("bar", "", 150),
    ("evidence", "Evidence", 80, "e"),
)

PICK_COLUMNS = (
    ("name", "Apprentice", 220),
    ("programme", "Programme", 240),
    ("employer", "Employer", 200),
    ("status", "Status", 130),
)

_LEVEL_TAGS = {"Competent": "Green", "Developing": "Amber"}

# Roles with a cohort to compare; mirrors skills_matrix_service, which
# refuses the cohort view to everyone else.
_COHORT_ROLES = (config.ADMIN, config.STAFF, config.EMPLOYER)


def render(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)
    if not gui.actor.can("portfolio.view"):
        widgets.empty_state(frame, "Your role does not see portfolio progress.")
        return
    if gui.actor.role == config.APPRENTICE:
        if gui.actor.apprentice_id is None:
            widgets.empty_state(frame, UNLINKED)
            return
        _matrix(gui, frame, gui.actor.apprentice_id)
        return
    if gui.actor.role not in _COHORT_ROLES:
        _picker(gui, frame)
        return
    _cohort(gui, frame)


def _picker(gui: Any, frame: Any) -> None:
    """For a role that may open one apprentice's matrix but has no cohort view."""
    ok, people = widgets.guard(
        lambda: apprentice_service.list_apprentices(gui.actor, active_only=True)
    )
    if not ok:
        return
    if not people:
        widgets.empty_state(frame, "There are no active apprentices in your view.")
        return

    def open_selected() -> None:
        ident = table.require_selection_int("open a skills matrix")
        if ident is not None:
            _open(gui, ident)

    widgets.button_bar(frame, [("Open matrix →", open_selected)])
    table = widgets.DataTable(frame, PICK_COLUMNS, on_activate=lambda i: _open(gui, int(i)))
    table.populate(
        people,
        lambda s: (s.full_name, s.programme_title, s.employer_name, s.apprentice.status),
        identity=lambda s: s.apprentice.apprentice_id,
        noun="apprentice",
    )


def _cohort(gui: Any, frame: Any) -> None:
    ok, rows = widgets.guard(lambda: skills_matrix_service.cohort_matrix(gui.actor))
    if not ok:
        return
    rows = rows or []
    if not rows:
        widgets.empty_state(frame, "There are no active apprentices on a programme in your view.")
        return

    widgets.kpi_row(frame, [
        ("Apprentices", len(rows)),
        ("Knowledge", widgets.percent(average_percent(rows, "Knowledge"))),
        ("Skills", widgets.percent(average_percent(rows, "Skill"))),
        ("Behaviours", widgets.percent(average_percent(rows, "Behaviour"))),
        ("Overall competent", widgets.percent(average_percent(rows))),
    ])
    programmes = sorted({r.programme_title for r in rows if r.programme_title})
    filters = widgets.FilterBar(
        frame,
        (
            ("programme", "Programme", "combo", programmes),
            ("search", "Name", "entry"),
        ),
        lambda: fill(),
    )

    def open_selected() -> None:
        ident = table.require_selection_int("open a skills matrix")
        if ident is not None:
            _open(gui, ident)

    widgets.button_bar(frame, [("Open matrix →", open_selected)])
    table = widgets.DataTable(frame, COHORT_COLUMNS, on_activate=lambda i: _open(gui, int(i)))

    def fill() -> None:
        values = filters.values()
        wanted = values.get("programme")
        term = str(values.get("search") or "").strip().casefold()
        shown = [
            r for r in rows
            if (not wanted or r.programme_title == wanted)
            and (not term or term in r.apprentice_name.casefold())
        ]
        table.populate(
            shown,
            _cohort_values,
            identity=lambda r: r.apprentice_id,
            noun="apprentice",
        )

    fill()


def _cohort_values(row: CohortRow) -> tuple[Any, ...]:
    competent = sum(1 for c in row.coverage if c.is_competent)
    return (
        row.apprentice_name, row.programme_title, row.employer_name,
        widgets.percent(row.percent("Knowledge")), widgets.percent(row.percent("Skill")),
        widgets.percent(row.percent("Behaviour")), widgets.percent(row.percent_overall),
        f"{competent} / {len(row.coverage)}",
    )


def _open(gui: Any, apprentice_id: int) -> None:
    frame = gui.clear()
    widgets.heading(frame, TITLE)
    widgets.button_bar(frame, [("← Cohort", lambda: render(gui))])
    _matrix(gui, frame, apprentice_id)


def _matrix(gui: Any, frame: Any, apprentice_id: int) -> None:
    ok, matrix = widgets.guard(
        lambda: skills_matrix_service.apprentice_matrix(gui.actor, apprentice_id)
    )
    if not ok or matrix is None:
        return
    widgets.heading(
        frame, f"{matrix.apprentice_name} — {matrix.programme_title or 'no programme'}"
    )
    developing = sum(1 for c in matrix.coverage if c.coverage == "Developing")
    widgets.kpi_row(frame, [
        ("KSBs", matrix.total),
        ("Competent", matrix.competent),
        ("Developing", developing),
        ("Not started", matrix.total - matrix.competent - developing),
        ("Competent overall", widgets.percent(matrix.percent_competent)),
    ])
    if not matrix.coverage:
        widgets.empty_state(frame, "The standard has no KSBs recorded yet.")
        return

    body = widgets.scrollable(frame)
    grouped = matrix.by_type()
    for summary in matrix.summaries():
        items = grouped.get(summary.ksb_type, [])
        if not items:
            continue
        box = widgets.section(
            body,
            f"{summary.ksb_type} — {summary.competent} of {summary.total} competent "
            f"({widgets.percent(summary.percent_competent)})",
        )
        table = widgets.DataTable(box, KSB_COLUMNS, height=min(10, len(items)))
        table.populate(
            items,
            lambda c: (c.ksb.code, c.ksb.description, c.coverage, level_bar(c.coverage),
                       c.evidence_count),
            identity=lambda c: c.ksb.ksb_id,
            tag=lambda c: _LEVEL_TAGS.get(c.coverage),
            noun="KSB",
        )
