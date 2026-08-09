"""About — what this system is, and what your role may do.

The permission table is the useful part. Roles here differ sharply in
what they can reach, and "why is that button missing?" is otherwise a
question only answerable by reading ``config.ROLE_PERMISSIONS`` in the
source. This screen answers it.
"""

from __future__ import annotations

import logging

from education_system.systems.apprenticeships import SYSTEM_NAME, VERSION, config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.interfaces.gui.controllers import (
    apprenticeship_controller as controller,
)

logger = logging.getLogger(__name__)


def render(gui) -> None:
    """Draw the about screen into the content pane."""
    frame = gui.clear()
    widgets.heading(
        frame, f"About {SYSTEM_NAME}",
        subtitle="Work-based learning: employed apprentices, off-the-job "
                 "training, and independent End-Point Assessment.",
    )

    actor = gui.actor
    widgets.field_grid(frame, [
        ("Version", VERSION),
        ("Signed in as", actor.username or widgets.EMPTY),
        ("Name", actor.name),
        ("Role", actor.role_label),
        ("Linked apprentice record", actor.apprentice_id or "—"),
        ("Linked employer record", actor.employer_id or "—"),
        ("Linked staff record", actor.staff_id or "—"),
    ], columns=2)

    if not actor.is_admin and not _is_linked(actor):
        box = widgets.section(frame, "This account is not linked")
        widgets.empty_state(
            box,
            f"Your login has the {actor.role_label} role but is not yet linked "
            "to a record in this system, so most screens will be empty.\n"
            "An administrator needs to set your username on the matching "
            "apprentice, employer contact or staff record.",
        )

    box = widgets.section(frame, "What your role may do")
    held = [(name, ok) for name, ok in controller.capability_summary(actor)]
    granted = sum(1 for _n, ok in held if ok)
    table = widgets.DataTable(box, [
        ("permission", "Capability", 260),
        ("held", "Your role", 120),
    ], height=12)
    table.populate(
        held,
        lambda row: (row[0], "Yes" if row[1] else "No"),
        identity=lambda row: row[0],
        tag=lambda row: "Green" if row[1] else None,
        noun="capability",
    )
    table.count_var.set(f"{granted} of {len(held)} capabilities held")

    if not actor.can("epa.grade"):
        # The one absence worth explaining, because it looks like an
        # oversight on an admin account and is in fact the point.
        widgets.empty_state(
            frame,
            "Note: nobody at the training provider — including "
            "administrators — may approve gateway or grade an End-Point "
            "Assessment. Those belong solely to the independent assessor.",
        )


def _is_linked(actor) -> bool:
    if actor.role == config.APPRENTICE:
        return actor.apprentice_id is not None
    if actor.role == config.EMPLOYER:
        return actor.employer_id is not None
    if actor.role == config.STAFF:
        return actor.staff_id is not None
    return True
