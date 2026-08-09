"""The off-the-job hours approval queue, and the whole log behind it."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    training_service,
)

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your login is not linked to a staff record, so no apprentice's hours are routed "
    "to you for approval. Ask an administrator to link your account to your staff "
    "profile — an unlinked login is not the same as an empty queue."
)

COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("date", "Activity date", 110),
    ("hours", "Hours", 70, "e"),
    ("type", "Activity type", 170),
    ("description", "Description", 340),
    ("status", "Status", 100),
)


def render(gui) -> None:
    """Hours submitted by this tutor's apprentices, waiting on sign-off."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "Off-the-Job Approvals",
        subtitle="Only approved hours count towards the target a funding audit checks.",
    )
    if gui.actor.staff_id is None:
        widgets.empty_state(frame, UNLINKED)
        return

    entries = training_service.pending_approvals(gui.actor)
    names = _names(gui)
    if not entries:
        widgets.empty_state(
            frame,
            "Nothing is waiting for your sign-off. Hours reach this queue when an "
            "apprentice submits them.",
        )
        widgets.button_bar(frame, [("View All Hours", lambda: _all_hours(gui))])
        return

    table = widgets.DataTable(frame, COLUMNS, multiselect=True)
    table.populate(
        entries,
        lambda e: (
            names.get(e.apprentice_id, f"Apprentice {e.apprentice_id}"),
            e.activity_date, e.hours, e.activity_type, e.description, e.status,
        ),
        identity=lambda e: e.entry_id,
        noun="entry",
    )
    ttk.Label(
        frame,
        text="Select several rows with Ctrl or Shift to approve them in one go.",
        foreground=config.MUTED_FG,
    ).pack(anchor="w", pady=(4, 0))

    def approve() -> None:
        chosen = table.require_selection_int("approve hours")
        if chosen is None:
            return
        ok, _ = widgets.guard(lambda: training_service.approve_hours(gui.actor, chosen))
        if ok:
            gui.refresh()

    def reject() -> None:
        chosen = table.require_selection_int("reject hours")
        if chosen is None:
            return
        reason = widgets.ask_reason(
            "Why are these hours being sent back? The apprentice can edit and "
            "resubmit them, so say what needs to change.",
            title="Reject hours",
        )
        if reason is None:
            return
        ok, _ = widgets.guard(
            lambda: training_service.reject_hours(gui.actor, chosen, reason=reason)
        )
        if ok:
            gui.refresh()

    def bulk_approve() -> None:
        chosen = [int(i) for i in table.selected_many()]
        if not chosen:
            widgets.warn("Select the entries to approve first.", title="Nothing selected")
            return
        if not widgets.confirm(
            f"Approve {len(chosen)} entries? Approved hours are locked and count "
            "towards the off-the-job target.",
            title="Bulk approve",
        ):
            return
        ok, approved = widgets.guard(lambda: training_service.bulk_approve(gui.actor, chosen))
        if not ok:
            return
        # The service skips entries somebody else already dealt with, so
        # the count it returns is the honest one to report.
        skipped = len(chosen) - int(approved or 0)
        message = f"{approved} of {len(chosen)} entries approved."
        if skipped:
            message += f" {skipped} were no longer awaiting approval."
        widgets.inform(message)
        gui.refresh()

    widgets.button_bar(frame, [
        ("Approve", approve),
        ("Reject…", reject),
        ("Bulk Approve", bulk_approve),
        ("View All Hours", lambda: _all_hours(gui)),
    ])


def _all_hours(gui) -> None:
    """The whole log in scope, not just what is awaiting a decision."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "Off-the-Job Hours",
        subtitle="Every entry logged by your caseload, whatever its status.",
    )
    names = _names(gui)
    body = ttk.Frame(frame)

    def reload() -> None:
        for child in body.winfo_children():
            child.destroy()
        rows = training_service.list_otj_entries(gui.actor, **bar.values())
        if not rows:
            widgets.empty_state(body, "No hours match these filters.")
            return
        table = widgets.DataTable(body, (*COLUMNS, ("approved", "Decided by", 140)), height=16)
        table.populate(
            rows,
            lambda e: (
                names.get(e.apprentice_id, f"Apprentice {e.apprentice_id}"),
                e.activity_date, e.hours, e.activity_type, e.description, e.status,
                e.approved_by,
            ),
            identity=lambda e: e.entry_id,
            noun="entry",
        )

    bar = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.OTJ_STATUSES),
            ("date_from", "From (YYYY-MM-DD)", "entry"),
            ("date_to", "To (YYYY-MM-DD)", "entry"),
        ),
        reload,
    )
    body.pack(fill="both", expand=True)
    reload()
    widgets.button_bar(frame, [("← Back to queue", lambda: render(gui))])


def _names(gui) -> dict[int, str]:
    """Apprentice ids to names: the hour log carries only the id."""
    return {
        s.apprentice.apprentice_id: s.full_name
        for s in apprentice_service.list_apprentices(gui.actor)
    }
