"""Off-the-job hour approvals — the employer's main job in this system."""

from __future__ import annotations

import logging
from collections.abc import Callable

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.interfaces.gui.windows.employer.dashboard import (
    UNLINKED_MESSAGE,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.learning import training_service

logger = logging.getLogger(__name__)

SUBTITLE = (
    "Approving an entry confirms the training happened, that it was off the job, and "
    "that it fell inside the apprentice's paid working hours. Approved hours are what "
    "a funding audit counts, so send anything you cannot vouch for back with a reason "
    "rather than approving it."
)

_QUEUE_COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("date", "Date", 110),
    ("hours", "Hours", 80, "e"),
    ("type", "Activity type", 200),
    ("description", "Description", 420),
)

_LOG_COLUMNS = (
    ("apprentice", "Apprentice", 180),
    ("date", "Date", 110),
    ("hours", "Hours", 70, "e"),
    ("type", "Activity type", 190),
    ("description", "Description", 300),
    ("status", "Status", 110),
    ("approver", "Decided by", 140),
)


def render(gui) -> None:
    """The queue of submitted hours waiting on this employer's sign-off."""
    frame = gui.clear()
    widgets.heading(frame, "Off-the-Job Hours", subtitle=SUBTITLE)
    if gui.actor.employer_id is None:
        widgets.empty_state(frame, UNLINKED_MESSAGE)
        return

    ok, entries = widgets.guard(lambda: training_service.pending_approvals(gui.actor))
    if not ok:
        return

    names = _names(gui)
    table = widgets.DataTable(frame, _QUEUE_COLUMNS, multiselect=True)
    if entries:
        table.populate(
            entries,
            lambda e: (
                names.get(e.apprentice_id, f"#{e.apprentice_id}"),
                e.activity_date, e.hours, e.activity_type, e.description,
            ),
            identity=lambda e: e.entry_id,
            noun="entry",
        )
    else:
        widgets.empty_state(
            frame,
            "Nothing is waiting on you. Hours appear here once an apprentice submits "
            "them; until then they are still drafting.",
        )

    buttons: list[tuple[str, Callable[[], None]]] = []
    if gui.actor.can("otj.approve"):
        buttons.extend([
            ("Approve", lambda: _approve(gui, table)),
            ("Reject", lambda: _reject(gui, table)),
            ("Bulk Approve", lambda: _bulk_approve(gui, table)),
        ])
    buttons.append(("View All Hours", lambda: _log(gui)))
    widgets.button_bar(frame, buttons)


# ── Decisions ───────────────────────────────────────────────────────

def _approve(gui, table: widgets.DataTable) -> None:
    entry_id = table.require_selection_int("approve hours")
    if entry_id is None:
        return
    ok, _ = widgets.guard(lambda: training_service.approve_hours(gui.actor, entry_id))
    if ok:
        gui.refresh()


def _reject(gui, table: widgets.DataTable) -> None:
    entry_id = table.require_selection_int("reject hours")
    if entry_id is None:
        return
    reason = widgets.ask_reason(
        "Why are these hours being sent back? The apprentice sees this, and cannot "
        "fix what they were not told about."
    )
    if reason is None:
        return
    ok, _ = widgets.guard(
        lambda: training_service.reject_hours(gui.actor, entry_id, reason=reason)
    )
    if ok:
        gui.refresh()


def _bulk_approve(gui, table: widgets.DataTable) -> None:
    """Approve everything selected, reporting how many actually moved.

    The service skips entries somebody else has already decided, so the
    count it returns is the honest one — not the number selected.
    """
    chosen = [int(raw) for raw in table.selected_many() if raw.isdigit()]
    if not chosen:
        widgets.inform(
            "Select the entries to approve first — hold Ctrl or Shift to pick several.",
            title="Nothing selected",
        )
        return
    if not widgets.confirm(
        f"Approve {len(chosen)} entr{'y' if len(chosen) == 1 else 'ies'}? This confirms "
        "the training happened in paid working hours."
    ):
        return
    ok, approved = widgets.guard(lambda: training_service.bulk_approve(gui.actor, chosen))
    if not ok:
        return
    widgets.inform(f"{approved} of {len(chosen)} entries approved.")
    gui.refresh()


# ── The whole log ───────────────────────────────────────────────────

def _log(gui) -> None:
    """Every entry for this employer's apprentices, not just the queue."""
    frame = gui.clear()
    widgets.heading(
        frame, "All Off-the-Job Hours",
        subtitle="The full log for your apprentices, whatever state each entry is in.",
    )
    widgets.button_bar(frame, [("← Back to approvals", lambda: render(gui))])

    ok, initial = widgets.guard(lambda: training_service.list_otj_entries(gui.actor))
    if not ok:
        return
    if not initial:
        widgets.empty_state(
            frame,
            "Your apprentices have not logged any off-the-job training yet. Entries "
            "appear here as soon as they record them, before you approve anything.",
        )
        return

    names = _names(gui)

    def fill(entries) -> None:
        table.populate(
            entries,
            lambda e: (
                names.get(e.apprentice_id, f"#{e.apprentice_id}"),
                e.activity_date, e.hours, e.activity_type, e.description,
                e.status, e.approved_by,
            ),
            identity=lambda e: e.entry_id,
            tag=lambda e: {"Approved": "Green", "Rejected": "Red"}.get(e.status),
            noun="entry",
        )

    def reload() -> None:
        found, entries = widgets.guard(
            lambda: training_service.list_otj_entries(gui.actor, **filters.values())
        )
        if found:
            fill(entries)

    filters = widgets.FilterBar(
        frame,
        [("status", "Status", "combo", config.OTJ_STATUSES),
         ("date_from", "From (YYYY-MM-DD)", "entry"),
         ("date_to", "To (YYYY-MM-DD)", "entry")],
        reload,
    )
    table = widgets.DataTable(frame, _LOG_COLUMNS)
    fill(initial)


def _names(gui) -> dict[int, str]:
    """Apprentice ids to names.

    Hour entries carry an id and no name, and a failure here should cost
    the labels rather than the screen.
    """
    try:
        return {
            s.apprentice.apprentice_id: s.full_name
            for s in apprentice_service.list_apprentices(gui.actor)
        }
    except Exception:
        logger.debug("Could not build the apprentice name lookup", exc_info=True)
        return {}
