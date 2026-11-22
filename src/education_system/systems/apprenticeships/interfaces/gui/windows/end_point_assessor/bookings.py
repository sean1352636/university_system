"""Bookings — end point assessor screen.

Assessment methods booked, scheduled and awaiting a date.

Booking and scheduling are the same permission (``epa.book``) and are
held by both the provider and the assessor, because in practice either
side may place the date — the provider knows when the apprentice is
free, the assessor knows when they are. Grading is not here; it is the
one thing only this role may do, and it has its own screen.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.assessments import epa_service

logger = logging.getLogger(__name__)

TITLE = "Bookings"
SUBTITLE = "Assessment methods booked, scheduled and awaiting a date."

_COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("method", "Method", 210),
    ("when", "When", 160),
    ("location", "Where", 170),
    ("assessor", "Assessor", 170),
    ("epao", "EPAO", 160),
    ("status", "Status", 120),
    ("resit", "Resit", 70),
)

_TAGS = {
    "Assessed": "Green", "Scheduled": "Green", "In Progress": "Amber",
    "Requested": "Amber", "Cancelled": "Red",
}


def render(gui) -> None:
    """Draw the bookings screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.can("epa.view"):
        widgets.empty_state(frame, "Your role may not see assessment bookings.")
        return

    filters = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.EPA_BOOKING_STATUSES),
            ("method", "Method", "combo", config.EPA_METHODS),
            ("open_only", "Still to grade", "check"),
            ("mine_only", "Mine only", "check"),
        ),
        lambda: reload(),
    )
    table = widgets.DataTable(
        frame, _COLUMNS,
        on_activate=lambda ident: _detail(gui, int(ident)),
    )
    rows_by_id: dict[int, dict] = {}

    def reload() -> None:
        _, rows = widgets.guard(
            lambda: epa_service.list_bookings(gui.actor, **filters.values())
        )
        rows = rows or []
        rows_by_id.clear()
        rows_by_id.update({int(r["booking_id"]): r for r in rows})
        table.populate(
            rows,
            lambda r: (
                r.get("apprentice_name"), r.get("method"),
                f"{r.get('scheduled_date') or widgets.EMPTY} "
                f"{r.get('scheduled_time') or ''}".strip(),
                r.get("location"), r.get("assessor_name"), r.get("epao_name"),
                r.get("status"), bool(r.get("resit_of")),
            ),
            identity=lambda r: r["booking_id"],
            tag=lambda r: _TAGS.get(r.get("status")),
            noun="booking",
        )
        if not rows:
            table.count_var.set(
                "Nothing matches. A booking appears once the provider places one — "
                "which they can only do after gateway is approved."
            )

    def chosen(action: str) -> dict | None:
        booking_id = table.require_selection_int(action)
        return rows_by_id.get(booking_id) if booking_id is not None else None

    buttons: list[tuple[str, Any]] = [
        ("Open", lambda: _open(gui, chosen("open a booking"))),
    ]
    if gui.actor.can("epa.book"):
        buttons += [
            ("Book…", lambda: _book(gui)),
            ("Schedule…", lambda: _schedule(gui, chosen("schedule a booking"))),
            ("Edit…", lambda: _edit(gui, chosen("edit a booking"))),
            ("Cancel…", lambda: _cancel(gui, chosen("cancel a booking"))),
        ]
    widgets.button_bar(frame, buttons)
    reload()


def _open(gui, row: dict | None) -> None:
    if row is not None:
        _detail(gui, int(row["booking_id"]))


# ═════════════════════════════════════════════════════════════════════
# One booking
# ═════════════════════════════════════════════════════════════════════

def _detail(gui, booking_id: int) -> None:
    frame = gui.clear()
    ok, row = widgets.guard(lambda: epa_service.get_booking(gui.actor, booking_id))
    back = ("← Back to bookings", lambda: render(gui))
    if not ok or row is None:
        widgets.button_bar(frame, [back])
        return

    widgets.heading(
        frame, f"{row.get('apprentice_name')} — {row.get('method')}",
        subtitle=f"{row.get('status')} · "
                 f"{row.get('scheduled_date') or 'no date yet'}",
    )
    widgets.field_grid(frame, [
        ("Apprentice", row.get("apprentice_name")),
        ("ULN", row.get("apprentice_uln")),
        ("Programme", row.get("programme_title")),
        ("Standard", row.get("programme_reference")),
        ("Method", row.get("method")),
        ("EPAO", row.get("epao_name")),
        ("Date", row.get("scheduled_date")),
        ("Time", row.get("scheduled_time")),
        ("Location", row.get("location")),
        ("Assessor", row.get("assessor_name")),
        ("Assessor login", row.get("assessor_username")),
        ("Status", row.get("status")),
        ("Resit of result", row.get("resit_of")),
    ], columns=4)

    box = widgets.section(frame, "Notes")
    widgets.empty_state(box, row.get("notes") or "None.")

    buttons: list[tuple[str, Any]] = []
    if gui.actor.can("epa.book"):
        buttons += [
            ("Schedule…", lambda: _schedule(gui, row, on_done=lambda: _detail(
                gui, booking_id
            ))),
            ("Edit…", lambda: _edit(gui, row, on_done=lambda: _detail(gui, booking_id))),
            ("Cancel…", lambda: _cancel(gui, row, on_done=lambda: _detail(
                gui, booking_id
            ))),
        ]
    buttons.append(back)
    widgets.button_bar(frame, buttons)


# ═════════════════════════════════════════════════════════════════════
# Actions
# ═════════════════════════════════════════════════════════════════════

def _book(gui) -> None:
    """Place a booking. Refused until gateway is approved."""
    ok, summaries = widgets.guard(lambda: apprentice_service.list_apprentices(gui.actor))
    if not ok or not summaries:
        widgets.warn("There are no apprentices in scope to book.")
        return

    people = {s.full_name: s.apprentice.apprentice_id for s in summaries}
    epao_fields, epao_ids = _epao_field(gui)
    fields = [
        {"key": "apprentice", "label": "Apprentice", "kind": "combo", "required": True,
         "options": list(people)},
        {"key": "method", "label": "Method", "kind": "combo", "required": True,
         "options": config.EPA_METHODS,
         "help": "Has to be one the standard's assessment plan lists — a grade for a "
                 "method the plan does not name is one nobody can use."},
        *epao_fields,
        {"key": "scheduled_date", "label": "Date", "help": "YYYY-MM-DD, or leave blank."},
        {"key": "scheduled_time", "label": "Time", "help": "HH:MM"},
        {"key": "location", "label": "Location"},
        {"key": "assessor_name", "label": "Assessor", "value": gui.actor.name},
        {"key": "assessor_username", "label": "Assessor login",
         "value": gui.actor.username,
         "help": "Puts the sitting in that assessor's diary."},
        {"key": "notes", "label": "Notes", "kind": "text"},
    ]

    def save(values: dict[str, Any]) -> Any:
        return epa_service.book_assessment(
            gui.actor, people[values["apprentice"]], _payload(values, epao_ids)
        )

    dialog = widgets.FormDialog(
        gui.root, "Book an assessment", fields, save,
        intro="Only after the assessment organisation has approved gateway. Booking "
              "the first method moves the apprentice to the EPA status.",
        save_label="Book",
    )
    if dialog.saved:
        gui.refresh()


def _schedule(gui, row: dict | None, *, on_done: Any = None) -> None:
    if row is None:
        return
    fields = [
        {"key": "scheduled_date", "label": "Date", "required": True,
         "value": row.get("scheduled_date") or date.today().isoformat(),
         "help": "YYYY-MM-DD"},
        {"key": "scheduled_time", "label": "Time",
         "value": row.get("scheduled_time") or "", "help": "HH:MM"},
        {"key": "location", "label": "Location", "value": row.get("location") or ""},
        {"key": "assessor_name", "label": "Assessor",
         "value": row.get("assessor_name") or gui.actor.name},
        {"key": "assessor_username", "label": "Assessor login",
         "value": row.get("assessor_username") or gui.actor.username,
         "help": "Puts the sitting in that assessor's diary."},
    ]

    def save(values: dict[str, Any]) -> Any:
        return epa_service.schedule_assessment(
            gui.actor, int(row["booking_id"]),
            scheduled_date=values["scheduled_date"],
            scheduled_time=values["scheduled_time"],
            location=values["location"],
            assessor_name=values["assessor_name"],
            assessor_username=values["assessor_username"],
        )

    title = f"Schedule — {row.get('apprentice_name')}, {row.get('method')}"
    if widgets.FormDialog(gui.root, title, fields, save).saved:
        (on_done or gui.refresh)()


def _edit(gui, row: dict | None, *, on_done: Any = None) -> None:
    if row is None:
        return
    if row.get("status") == "Assessed":
        widgets.warn(
            "A graded booking cannot be edited. Grading is final — a correction is a "
            "resit, not an edit.",
            title="Graded",
        )
        return

    epao_fields, epao_ids = _epao_field(gui, current=row.get("epao_name"))
    fields = [
        {"key": "method", "label": "Method", "kind": "combo", "required": True,
         "options": config.EPA_METHODS, "value": row.get("method")},
        *epao_fields,
        {"key": "scheduled_date", "label": "Date",
         "value": row.get("scheduled_date") or "", "help": "YYYY-MM-DD"},
        {"key": "scheduled_time", "label": "Time",
         "value": row.get("scheduled_time") or "", "help": "HH:MM"},
        {"key": "location", "label": "Location", "value": row.get("location") or ""},
        {"key": "assessor_name", "label": "Assessor",
         "value": row.get("assessor_name") or ""},
        {"key": "assessor_username", "label": "Assessor login",
         "value": row.get("assessor_username") or ""},
        {"key": "notes", "label": "Notes", "kind": "text", "value": row.get("notes") or ""},
    ]

    def save(values: dict[str, Any]) -> Any:
        return epa_service.update_booking(
            gui.actor, int(row["booking_id"]), _payload(values, epao_ids)
        )

    title = f"Edit — {row.get('apprentice_name')}, {row.get('method')}"
    if widgets.FormDialog(
        gui.root, title, fields, save,
        intro="Status moves through scheduling, cancelling and grading — not here.",
    ).saved:
        (on_done or gui.refresh)()


def _cancel(gui, row: dict | None, *, on_done: Any = None) -> None:
    if row is None:
        return
    reason = widgets.ask_reason(
        f"Why is the {row.get('method')} sitting for {row.get('apprentice_name')} "
        "being cancelled?",
        title="Cancel booking",
    )
    if not reason:
        return
    ok, _ = widgets.guard(lambda: epa_service.cancel_booking(
        gui.actor, int(row["booking_id"]), reason=reason
    ))
    if ok:
        (on_done or gui.refresh)()


# ═════════════════════════════════════════════════════════════════════
# Shared
# ═════════════════════════════════════════════════════════════════════

def _epao_field(
    gui, *, current: str | None = None
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The EPAO picker and a name-to-id map, or nothing at all.

    An empty combobox reads as a bug, and the service treats a missing
    EPAO as acceptable, so the field is simply left out of the form
    until somebody has added one to the directory.
    """
    ok, epaos = widgets.guard(
        lambda: epa_service.list_epaos(gui.actor, active_only=True)
    )
    if not ok or not epaos:
        return [], {}
    field = {
        "key": "epao", "label": "EPAO", "kind": "combo",
        "options": ("", *[e.name for e in epaos]), "value": current or "",
    }
    return [field], {e.name: e.epao_id for e in epaos}


def _payload(values: dict[str, Any], epao_ids: dict[str, int]) -> dict[str, Any]:
    """Turn the form's EPAO name back into its id, and drop the label field."""
    payload = dict(values)
    payload.pop("apprentice", None)
    name = payload.pop("epao", "")
    if name:
        payload["epao_id"] = epao_ids.get(name)
    return payload
