"""Workload: each tutor's caseload and the open work behind it.

Exposes: menu.
"""

from __future__ import annotations

import logging

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.workspace import workload_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (
    ("Staff member", 20), ("Appr", -5), ("Rev late", -8), ("Rev due", -7), ("Evid", -5),
    ("Hours", -5), ("Attend", -6), ("Obj late", -8), ("Other", 18), ("Open", -5), ("RAG", 6),
)


def menu(actor: Actor) -> None:
    loads = workload_service.list_workloads(actor)
    prompts.title("Workload")
    prompts.note(
        f"Amber from {config.CASELOAD_WARNING_THRESHOLD} apprentices or "
        f"{config.WORKLOAD_ITEMS_WARNING} open items; red from {config.CASELOAD_MAXIMUM} or "
        f"{config.WORKLOAD_ITEMS_MAXIMUM}."
    )
    prompts.table(
        _COLUMNS,
        loads,
        lambda w: (
            w.name, w.active, w.reviews_overdue, w.reviews_due_soon, w.evidence_to_assess,
            w.hours_to_approve, w.attendance_concerns, w.objectives_overdue,
            ", ".join(f"{label} {n}" for label, n in w.other.items()), w.open_items, w.rag,
        ),
        noun="member of staff",
        empty="no workload to show — a login must be linked to a staff record",
    )
    prompts.pause()
