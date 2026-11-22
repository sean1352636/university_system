"""The apprentice's off-the-job hours: the log and the target above it.

The most consequential screen an apprentice has. Off-the-job hours are
what a funding audit turns on and what gateway checks first, so the
target sits above the log rather than beside it, and the figures are the
honest ones: only hours an approver has signed count, and the screen says
so instead of showing a total that will shrink later.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.learning import training_service

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is nothing to "
    "show here. Ask your training provider's administrator to link your account."
)

_COLUMNS: tuple[tuple, ...] = (
    ("date", "Date", 110),
    ("hours", "Hours", 80, "e"),
    ("activity", "Activity", 200),
    ("description", "What you did", 420),
    ("ksbs", "KSBs", 150),
    ("status", "Status", 110),
)

# Approved is the only status that moves the total, so the log is
# coloured by how close each entry is to counting.
_TAGS: dict[str, str] = {"Approved": "Green", "Submitted": "Amber", "Rejected": "Red"}


def render(gui: Any) -> None:
    """Log off-the-job hours, and see how far they take you."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "Off-the-Job Hours",
        subtitle="Training you do in paid working time but away from your day job. "
                 "Only hours your tutor or employer has approved count towards your "
                 "target — draft and submitted hours are shown so you can see your own "
                 "effort, but they do not move the total.",
    )
    apprentice_id = _require_record(gui, frame)
    if apprentice_id is None:
        return

    ok, summary = widgets.guard(lambda: training_service.otj_summary(gui.actor, apprentice_id))
    if not ok:
        return
    _progress(frame, summary)

    filters = widgets.FilterBar(
        frame, (("status", "Status", "combo", config.OTJ_STATUSES),), lambda: reload()
    )
    table = widgets.DataTable(frame, _COLUMNS)
    entries: dict[int, Any] = {}

    def reload() -> None:
        loaded, rows = widgets.guard(lambda: training_service.list_otj_entries(
            gui.actor, apprentice_id=apprentice_id, **filters.values()
        ))
        rows = rows or [] if loaded else []
        entries.clear()
        entries.update({entry.entry_id: entry for entry in rows})
        table.populate(
            rows,
            lambda e: (
                e.activity_date, e.hours, e.activity_type, e.description,
                e.ksb_codes, e.status,
            ),
            identity=lambda e: e.entry_id,
            tag=lambda e: _TAGS.get(e.status),
            noun="entry",
        )
        if not rows:
            table.count_var.set("You haven't logged any hours yet.")

    def chosen(action: str) -> Any | None:
        entry_id = table.require_selection_int(action)
        return entries.get(entry_id) if entry_id is not None else None

    def log_hours() -> None:
        dialog = widgets.FormDialog(
            frame, "Log off-the-job hours", _fields(None),
            lambda values: training_service.log_hours(gui.actor, values),
            intro="Saved as a draft. Submit it when you are ready and your approver "
                  "will sign it off.",
            save_label="Save draft",
        )
        if dialog.saved:
            gui.refresh()

    def edit_hours() -> None:
        entry = chosen("edit it")
        if entry is None:
            return
        if not entry.is_editable:
            widgets.warn(
                f"These hours are {entry.status.lower()} and cannot be changed. Ask your "
                "approver to send them back if they are wrong.",
                title="Locked",
            )
            return
        dialog = widgets.FormDialog(
            frame, "Edit these hours", _fields(entry),
            lambda values: training_service.update_entry(gui.actor, entry.entry_id, values),
        )
        if dialog.saved:
            gui.refresh()

    def submit_hours() -> None:
        entry = chosen("submit it")
        if entry is None:
            return
        ok, _ = widgets.guard(lambda: training_service.submit_hours(gui.actor, entry.entry_id))
        if ok:
            gui.refresh()

    def delete_entry() -> None:
        entry = chosen("delete it")
        if entry is None:
            return
        if not widgets.confirm(
            f"Delete the {entry.hours} hours you logged on {entry.activity_date}?",
            title="Delete hours",
        ):
            return
        ok, _ = widgets.guard(lambda: training_service.delete_entry(gui.actor, entry.entry_id))
        if ok:
            gui.refresh()

    if gui.actor.can("otj.log"):
        widgets.button_bar(frame, [
            ("Log hours", log_hours),
            ("Edit", edit_hours),
            ("Submit for approval", submit_hours),
            ("Delete", delete_entry),
        ])
    reload()


def _require_record(gui: Any, frame: Any) -> int | None:
    """The apprentice id this screen is scoped to, or None having said why not."""
    apprentice_id = gui.actor.apprentice_id
    if apprentice_id is None:
        widgets.empty_state(frame, UNLINKED)
    return apprentice_id


def _progress(parent: Any, summary: Any) -> None:
    box = widgets.section(parent, "Where you are against your target")
    if summary.target_hours <= 0:
        widgets.empty_state(
            box,
            "Your target is worked out from your programme dates, and those are not "
            "set yet — so nothing here has a total to count towards. Your tutor can "
            "put that right.",
        )
        return

    widgets.progress_row(
        box, "Approved hours", summary.percent_complete,
        detail=_pace(summary), rag=summary.rag_rating,
    )
    weeks_left = max(0.0, summary.weeks_total - summary.weeks_elapsed)
    widgets.field_grid(box, [
        ("Your target", f"{summary.target_hours:,.1f} hrs"),
        ("Approved", f"{summary.approved_hours:,.1f} hrs"),
        ("Waiting for approval", f"{summary.pending_hours:,.1f} hrs"),
        ("Still in draft", f"{summary.draft_hours:,.1f} hrs"),
        ("Left to do", f"{summary.remaining_hours:,.1f} hrs"),
        ("Weeks left", f"{weeks_left:,.1f}"),
        ("Hours a week needed", f"{summary.weekly_hours_needed:,.1f}"),
        ("On track", summary.target_met or summary.is_on_track),
    ], columns=4)


def _pace(summary: Any) -> str:
    """The one honest line: where you are, and what it takes from here."""
    logged = f"{summary.approved_hours:,.0f} of {summary.target_hours:,.0f} hours"
    if summary.target_met:
        return f"{logged} — target met"
    weekly = f"{summary.weekly_hours_needed:,.1f} hrs/week needed"
    if summary.is_on_track:
        return f"{logged} — {weekly}, on track"
    return f"{logged} — {weekly}, {summary.hours_behind:,.1f} hrs behind today's pace"


def _fields(entry: Any | None) -> list[dict[str, Any]]:
    """The log form, pre-filled when an existing entry is being corrected."""
    return [
        {
            "key": "activity_date", "label": "Date", "kind": "date", "required": True,
            "value": entry.activity_date if entry else date.today().isoformat(),
            "help": "YYYY-MM-DD. Hours cannot be logged for a day that has not happened.",
        },
        {
            "key": "hours", "label": "Hours", "required": True,
            "value": entry.hours if entry else "",
            "help": "How long it took — 1.5 for an hour and a half.",
        },
        {
            "key": "activity_type", "label": "Activity type", "kind": "combo",
            "options": config.OTJ_ACTIVITY_TYPES, "required": True,
            "value": entry.activity_type if entry else "",
        },
        {
            "key": "description", "label": "What you did", "kind": "text", "required": True,
            "value": entry.description if entry else "",
            "help": "Your approver reads this — say what you learned, not just where you were.",
        },
        {
            "key": "ksb_codes", "label": "KSBs covered",
            "value": entry.ksb_codes if entry else "",
            "help": "Comma-separated codes, e.g. K3, S1, B2. Leave blank if you are unsure.",
        },
    ]
