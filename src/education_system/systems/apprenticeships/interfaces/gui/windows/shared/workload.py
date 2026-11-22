"""Workload: each tutor's caseload and the open work behind it.

An administrator sees everyone, heaviest first, and can rebalance
before a review slips; a tutor sees their own position against the same
thresholds.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.workspace import workload_service

logger = logging.getLogger(__name__)

COLUMNS = (
    ("name", "Staff member", 190),
    ("role", "Role", 130),
    ("active", "Apprentices", 90, "e"),
    ("overdue", "Reviews overdue", 110, "e"),
    ("due", "Reviews due", 90, "e"),
    ("evidence", "Evidence", 80, "e"),
    ("hours", "Hours", 70, "e"),
    ("attendance", "Attendance", 90, "e"),
    ("objectives", "Objectives late", 110, "e"),
    ("other", "Other", 160),
    ("open", "Open items", 90, "e"),
)


def render(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(
        frame, "Workload",
        subtitle=f"Amber from {config.CASELOAD_WARNING_THRESHOLD} apprentices or "
                 f"{config.WORKLOAD_ITEMS_WARNING} open items; red from "
                 f"{config.CASELOAD_MAXIMUM} or {config.WORKLOAD_ITEMS_MAXIMUM}.",
    )
    ok, loads = widgets.guard(lambda: workload_service.list_workloads(gui.actor))
    if not ok:
        return
    if not loads:
        widgets.empty_state(
            frame,
            "There is no workload to show. A tutor's login has to be linked to their "
            "staff record before their work can be counted.",
        )
        return

    widgets.kpi_row(frame, [
        ("Staff", len(loads)),
        ("Apprentices", sum(w.active for w in loads)),
        ("Open items", sum(w.open_items for w in loads)),
        ("At or over threshold", sum(1 for w in loads if w.rag != "Green")),
    ])
    table = widgets.DataTable(frame, COLUMNS)
    table.populate(
        loads,
        lambda w: (
            w.name, w.staff_role, w.active, w.reviews_overdue, w.reviews_due_soon,
            w.evidence_to_assess, w.hours_to_approve, w.attendance_concerns,
            w.objectives_overdue,
            ", ".join(f"{label} {n}" for label, n in w.other.items()),
            w.open_items,
        ),
        identity=lambda w: w.staff_id,
        tag=lambda w: w.rag,
        noun="member of staff",
    )
