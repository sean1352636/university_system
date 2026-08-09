"""Portfolio evidence for the employer's apprentices, read-only."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.interfaces.gui.windows.employer.dashboard import (
    UNLINKED_MESSAGE,
)
from education_system.systems.apprenticeships.services import apprentice_service, portfolio_service

logger = logging.getLogger(__name__)

SUBTITLE = (
    "What your apprentices have put in their portfolios. You can read it — seeing the "
    "work is part of employing an apprentice — but judging it is the provider assessor's "
    "job, not yours, so there is nothing to accept or refer here."
)

_STATUS_TAGS = {"Accepted": "Green", "Rejected": "Red", "Referred": "Amber"}

_COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("title", "Title", 300),
    ("type", "Type", 180),
    ("status", "Status", 120),
    ("submitted", "Submitted", 160),
)


def render(gui) -> None:
    """Their apprentices' evidence, with a detail pane under the list."""
    frame = gui.clear()
    widgets.heading(frame, "Portfolio Evidence", subtitle=SUBTITLE)
    if gui.actor.employer_id is None:
        widgets.empty_state(frame, UNLINKED_MESSAGE)
        return

    ok, initial = widgets.guard(lambda: portfolio_service.list_evidence(gui.actor))
    if not ok:
        return
    if not initial:
        widgets.empty_state(
            frame,
            "Your apprentices have not added any portfolio evidence yet. It appears "
            "here as they upload it, and again once their assessor has judged it.",
        )
        return

    names = _names(gui)

    def fill(rows: Sequence[Any]) -> None:
        table.populate(
            rows,
            lambda e: (
                names.get(e.apprentice_id, f"#{e.apprentice_id}"),
                e.title, e.evidence_type, e.status, e.submitted_at,
            ),
            identity=lambda e: e.evidence_id,
            tag=lambda e: _STATUS_TAGS.get(e.status),
            noun="item",
        )

    def reload() -> None:
        ok, rows = widgets.guard(
            lambda: portfolio_service.list_evidence(gui.actor, **filters.values())
        )
        if ok:
            fill(rows)

    def show_detail(chosen: str) -> None:
        for child in detail.winfo_children():
            child.destroy()
        found, item = widgets.guard(
            lambda: portfolio_service.get_evidence(gui.actor, int(chosen))
        )
        if not found:
            return
        widgets.field_grid(detail, [
            ("Apprentice", names.get(item.apprentice_id, f"#{item.apprentice_id}")),
            ("Title", item.title),
            ("Type", item.evidence_type),
            ("Status", item.status),
            ("Submitted", item.submitted_at),
            ("Assessed", item.assessed_at),
            ("File", item.file_name),
            ("KSBs claimed", ", ".join(item.ksb_codes)),
            ("Description", item.description),
            ("Assessor feedback", item.feedback),
        ], columns=2)

    filters = widgets.FilterBar(
        frame,
        [("status", "Status", "combo", config.EVIDENCE_STATUSES),
         ("evidence_type", "Type", "combo", config.EVIDENCE_TYPES)],
        reload,
    )
    table = widgets.DataTable(frame, _COLUMNS, on_activate=show_detail)
    widgets.button_bar(frame, [("View Detail", lambda: _open_selected(table, show_detail))])
    detail = widgets.section(frame, "Selected item")
    widgets.empty_state(detail, "Pick an item above to read it.")
    fill(initial)


def _open_selected(table: widgets.DataTable, show_detail) -> None:
    evidence_id = table.require_selection_int("read an item")
    if evidence_id is not None:
        show_detail(str(evidence_id))


def _names(gui) -> dict[int, str]:
    """Apprentice ids to names — evidence rows carry the id only."""
    try:
        return {
            s.apprentice.apprentice_id: s.full_name
            for s in apprentice_service.list_apprentices(gui.actor)
        }
    except Exception:
        logger.debug("Could not build the apprentice name lookup", exc_info=True)
        return {}
