"""My Tasks: everything waiting on the signed-in person, most urgent first.

Gathered from every screen's own queue — reviews, approvals, evidence,
signatures, deadlines — so the day starts in one place. Each row opens
the screen where the work is actually done.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships.domain.workspace.items import count_by_urgency
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import task_service

logger = logging.getLogger(__name__)

COLUMNS = (
    ("due", "Due", 100),
    ("urgency", "When", 90),
    ("category", "Area", 150),
    ("task", "Task", 320),
    ("apprentice", "Apprentice", 180),
    ("detail", "Detail", 320),
)


def render(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(
        frame, "My Tasks",
        subtitle="Everything waiting on you, gathered from every screen — overdue first.",
    )
    ok, tasks = widgets.guard(lambda: task_service.my_tasks(gui.actor))
    if not ok:
        return
    today = date.today()
    counts = count_by_urgency(tasks, today)
    widgets.kpi_row(frame, [
        ("Overdue", counts["Overdue"]),
        ("Due soon", counts["Due soon"]),
        ("Upcoming", counts["Upcoming"]),
        ("Undated", counts["No date"]),
        ("Total", len(tasks)),
    ])
    if not tasks:
        widgets.empty_state(frame, "Nothing is waiting on you. New work appears here as it arrives.")
        widgets.button_bar(frame, [("Refresh", lambda: render(gui))])
        return

    by_index = dict(enumerate(tasks))

    def open_task(ident: Any) -> None:
        task = by_index.get(int(ident))
        if task is not None and task.opens:
            gui.show(*task.opens)
        else:
            widgets.inform(
                "This task does not have a screen of its own for your role — it is here "
                "so you know about it.",
                title="Nothing to open",
            )

    table = widgets.DataTable(frame, COLUMNS, on_activate=open_task)

    def open_selected() -> None:
        ident = table.require_selection_int("open a task")
        if ident is not None:
            open_task(ident)

    widgets.button_bar(frame, [("Open →", open_selected), ("Refresh", lambda: render(gui))])
    table.populate(
        list(by_index.items()),
        lambda pair: (
            pair[1].due or "—", pair[1].urgency(today), pair[1].category, pair[1].title,
            pair[1].apprentice_name, pair[1].detail,
        ),
        identity=lambda pair: pair[0],
        tag=lambda pair: pair[1].rag(today),
        noun="task",
    )
