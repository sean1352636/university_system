"""What the provider holds about the signed-in apprentice.

Read-only by design: an apprentice does not hold ``apprentice.manage``,
and these fields — the ULN, the planned end date, the contracted hours —
drive funding and the off-the-job target. So the screen says who to ask
rather than offering buttons that would only ever be refused.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import apprentice_service

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is nothing to "
    "show here. Ask your training provider's administrator to link your account."
)


def render(gui: Any) -> None:
    """The apprentice's own record, and how their status has moved."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "My Details",
        subtitle="Everything your provider holds about you. Contact your tutor to "
                 "correct any of these details — they cannot be edited here.",
    )
    apprentice_id = _require_record(gui, frame)
    if apprentice_id is None:
        return

    ok, summary = widgets.guard(lambda: apprentice_service.get_own_record(gui.actor))
    if not ok:
        return
    if summary is None:
        widgets.empty_state(frame, UNLINKED)
        return

    body = widgets.scrollable(frame)
    record = summary.apprentice

    about = widgets.section(body, "About you")
    widgets.field_grid(about, [
        ("Name", record.full_name),
        ("Unique learner number", record.uln),
        ("Date of birth", record.date_of_birth),
        ("Email", record.email),
        ("Phone", record.phone),
        ("Sign-in", record.username),
    ], columns=3)

    programme = widgets.section(body, "Your apprenticeship")
    widgets.field_grid(programme, [
        ("Programme", summary.programme_title),
        ("Standard", summary.programme_reference),
        ("Level", summary.programme_level),
        ("Employer", summary.employer_name),
        ("Workplace", summary.workplace_name),
        ("Your tutor", summary.tutor_name),
        ("Status", record.status),
        ("Started", record.start_date),
        ("Planned to finish", record.planned_end_date),
        ("Contracted hours", f"{record.weekly_hours:,.1f} hours a week"),
        ("How it is funded", record.funding_model),
        ("Finished", record.actual_end_date),
    ], columns=3)

    _history(gui, body, apprentice_id)


def _require_record(gui: Any, frame: Any) -> int | None:
    """The apprentice id this screen is scoped to, or None having said why not."""
    apprentice_id = gui.actor.apprentice_id
    if apprentice_id is None:
        widgets.empty_state(frame, UNLINKED)
    return apprentice_id


def _history(gui: Any, parent: Any, apprentice_id: int) -> None:
    box = widgets.section(parent, "How your status has changed")
    ok, changes = widgets.guard(
        lambda: apprentice_service.status_history(gui.actor, apprentice_id)
    )
    if not ok:
        return
    if not changes:
        widgets.empty_state(box, "Nothing has changed since you were enrolled.")
        return

    table = widgets.DataTable(box, (
        ("effective", "Date", 120),
        ("from_status", "From", 150),
        ("to_status", "To", 150),
        ("reason", "Reason", 400),
        ("actor", "Recorded by", 150),
    ), height=8)
    table.populate(
        changes,
        lambda c: (c.effective_date, c.from_status, c.to_status, c.reason, c.actor),
        identity=lambda c: c.history_id,
        tag=lambda c: c.to_status,
        noun="change",
    )
