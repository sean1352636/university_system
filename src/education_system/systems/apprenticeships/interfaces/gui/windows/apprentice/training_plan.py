"""The apprentice's training plan and the sessions coming up.

The plan is the provider's commitment about what will be delivered and
when; the apprentice reads it rather than writes it. Sessions are shown
underneath because they are how the plan actually arrives.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import apprentice_service, training_service

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is nothing to "
    "show here. Ask your training provider's administrator to link your account."
)


def render(gui: Any) -> None:
    """The planned learning for this apprentice, and the sessions ahead."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "Training Plan",
        subtitle="What your provider and employer agreed would be delivered, and when. "
                 "Your tutor keeps this up to date — ask them if something here has "
                 "changed.",
    )
    apprentice_id = _require_record(gui, frame)
    if apprentice_id is None:
        return

    body = widgets.scrollable(frame)
    _plan(gui, body, apprentice_id)
    _sessions(gui, body)


def _require_record(gui: Any, frame: Any) -> int | None:
    """The apprentice id this screen is scoped to, or None having said why not."""
    apprentice_id = gui.actor.apprentice_id
    if apprentice_id is None:
        widgets.empty_state(frame, UNLINKED)
    return apprentice_id


def _plan(gui: Any, parent: Any, apprentice_id: int) -> None:
    box = widgets.section(parent, "Your planned learning")
    ok, items = widgets.guard(
        lambda: training_service.list_plan_items(gui.actor, apprentice_id)
    )
    if not ok:
        return
    if not items:
        widgets.empty_state(
            box,
            "There is nothing in your training plan yet. Your tutor writes it with you "
            "at the start of the apprenticeship.",
        )
        return

    table = widgets.DataTable(box, (
        ("title", "What you will cover", 320),
        ("start", "Planned start", 120),
        ("end", "Planned end", 120),
        ("hours", "Hours", 80, "e"),
        ("ksbs", "KSBs", 160),
        ("mode", "How", 140),
        ("status", "Status", 110),
    ), height=12)
    table.populate(
        items,
        lambda i: (
            i.title, i.planned_start, i.planned_end, i.planned_hours,
            i.ksb_codes, i.delivery_mode, i.status,
        ),
        identity=lambda i: i.item_id,
        tag=lambda i: "Green" if i.is_done else None,
        noun="planned item",
    )


def _sessions(gui: Any, parent: Any) -> None:
    box = widgets.section(parent, "Sessions coming up")
    ok, summary = widgets.guard(lambda: apprentice_service.get_own_record(gui.actor))
    if not ok:
        return

    programme_id = summary.apprentice.programme_id if summary else None
    if programme_id is None:
        # The timetable is not scoped per apprentice — an unfiltered call
        # would list every session the provider runs, which is not this
        # apprentice's timetable and not theirs to read.
        widgets.empty_state(
            box, "You are not on a programme yet, so there is no timetable to show."
        )
        return

    ok, sessions = widgets.guard(lambda: training_service.list_sessions(
        gui.actor, programme_id=programme_id, upcoming_only=True
    ))
    if not ok:
        return
    if not sessions:
        widgets.empty_state(box, "Nothing is scheduled for your programme at the moment.")
        return

    table = widgets.DataTable(box, (
        ("when", "When", 200),
        ("title", "Session", 300),
        ("mode", "How", 140),
        ("location", "Where", 200),
        ("trainer", "Trainer", 160),
        ("hours", "Off-the-job hours", 130, "e"),
    ), height=10)
    table.populate(
        sessions,
        lambda s: (
            s.when, s.title, s.delivery_mode, s.location, s.trainer_name, s.otj_hours,
        ),
        identity=lambda s: s.session_id,
        noun="session",
    )
