"""My tasks: everything waiting on the signed-in person, most urgent first.

Exposes: menu.
"""

from __future__ import annotations

import logging
from datetime import date

from education_system.systems.apprenticeships.domain.workspace.items import count_by_urgency
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services import task_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (("Due", 11), ("When", 9), ("Area", 18), ("Task", 38), ("Apprentice", 20),
            ("Detail", 30))


def menu(actor: Actor) -> None:
    tasks = task_service.my_tasks(actor)
    today = date.today()
    counts = count_by_urgency(tasks, today)
    prompts.title("My Tasks")
    prompts.details([
        ("Overdue", counts["Overdue"]),
        ("Due soon", counts["Due soon"]),
        ("Upcoming", counts["Upcoming"]),
        ("Undated", counts["No date"]),
    ])
    prompts.table(
        _COLUMNS,
        tasks,
        lambda t: (t.due or "—", t.urgency(today), t.category, t.title,
                   t.apprentice_name or "", t.detail),
        noun="task",
        empty="nothing is waiting on you",
    )
    if any(t.opens for t in tasks):
        prompts.note("\n  Each area has its own entry in the menu — that is where to act on it.")
    prompts.pause()
