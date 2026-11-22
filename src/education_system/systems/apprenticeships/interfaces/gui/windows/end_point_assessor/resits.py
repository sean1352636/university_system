"""Resits — end point assessor screen.

Resit and retake requests after a failed method.

The distinction the screen exists to enforce: a *resit* goes straight
back to assessment, a *retake* requires further training first — which
is why a retake cannot be requested without a plan for that training.
Booking one produces an ordinary booking carrying ``resit_of``, so the
result chain can be followed back to the sitting it replaces.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.assessments import epa_service

logger = logging.getLogger(__name__)

TITLE = "Resits"
SUBTITLE = "Resit and retake requests after a failed method."

_COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("requested", "Requested", 150),
    ("type", "Type", 90),
    ("status", "Status", 110),
    ("reason", "Reason", 300),
    ("plan", "Training plan", 300),
    ("booking", "Booking", 90, "e"),
)

_FAIL_COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("method", "Method", 230),
    ("grade", "Grade", 100),
    ("assessed", "Assessed", 120),
    ("attempt", "Attempt", 90, "e"),
    ("remaining", "Attempts left", 110, "e"),
)


def render(gui) -> None:
    """Draw the resits screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.can("epa.view"):
        widgets.empty_state(frame, "Your role may not see resit requests.")
        return

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True)

    requested = ttk.Frame(notebook, padding=8)
    notebook.add(requested, text="Requests")
    _requests(gui, requested)

    failures = ttk.Frame(notebook, padding=8)
    notebook.add(failures, text="Failed sittings")
    _failures(gui, failures)


# ═════════════════════════════════════════════════════════════════════
# Requests
# ═════════════════════════════════════════════════════════════════════

def _requests(gui, parent: Any) -> None:
    names = _names(gui)
    filters = widgets.FilterBar(
        parent, (("status", "Status", "combo", ("Requested", "Booked")),),
        lambda: reload(),
    )
    table = widgets.DataTable(parent, _COLUMNS)
    rows_by_id: dict[int, Any] = {}

    def reload() -> None:
        _, rows = widgets.guard(
            lambda: epa_service.list_resits(gui.actor, **filters.values())
        )
        rows = rows or []
        rows_by_id.clear()
        rows_by_id.update({r.resit_id: r for r in rows})
        table.populate(
            rows,
            lambda r: (names.get(r.apprentice_id, f"Apprentice {r.apprentice_id}"),
                       r.requested_at, r.resit_type, r.status, r.reason,
                       r.training_plan, r.booking_id),
            identity=lambda r: r.resit_id,
            tag=lambda r: "Green" if r.booking_id else "Amber",
            noun="resit",
        )
        if not rows:
            table.count_var.set(
                "Nothing requested. A resit is asked for against a failed sitting — "
                "see the Failed sittings tab."
            )

    def book() -> None:
        resit_id = table.require_selection_int("book a resit")
        if resit_id is None:
            return
        resit = rows_by_id.get(resit_id)
        if resit is None:
            return
        if resit.booking_id:
            widgets.warn(
                f"That resit is already booked (booking {resit.booking_id}).",
                title="Already booked",
            )
            return
        _book(gui, resit, names, reload)

    if gui.actor.can("epa.book"):
        widgets.button_bar(parent, [("Book Resit…", book)])
    reload()


def _book(gui, resit: Any, names: dict[int, str], reload: Any) -> None:
    """Turn an approved resit request into a booking."""
    who = names.get(resit.apprentice_id, f"Apprentice {resit.apprentice_id}")
    fields: list[dict[str, Any]] = [
        {"key": "method", "label": "Method", "kind": "combo",
         "options": ("", *config.EPA_METHODS),
         "help": "Blank re-books the same method as the sitting being replaced."},
        {"key": "scheduled_date", "label": "Date", "help": "YYYY-MM-DD, or blank."},
        {"key": "scheduled_time", "label": "Time", "help": "HH:MM"},
        {"key": "location", "label": "Location"},
        {"key": "assessor_name", "label": "Assessor", "value": gui.actor.name},
        {"key": "assessor_username", "label": "Assessor login",
         "value": gui.actor.username},
        {"key": "notes", "label": "Notes", "kind": "text",
         "value": resit.training_plan or ""},
    ]

    def save(values: dict[str, Any]) -> Any:
        payload = {k: v for k, v in values.items() if str(v or "").strip()}
        return epa_service.book_resit(gui.actor, resit.resit_id, payload)

    dialog = widgets.FormDialog(
        gui.root, f"Book {resit.resit_type.lower()} — {who}", fields, save,
        intro="The new booking carries a link back to the sitting it replaces, so the "
              "result chain stays followable. Gateway has to still be approved.",
        save_label="Book",
    )
    if dialog.saved:
        widgets.inform(f"Booked as booking {dialog.result['booking_id']}.")
        reload()


# ═════════════════════════════════════════════════════════════════════
# Failed sittings
# ═════════════════════════════════════════════════════════════════════

def _failures(gui, parent: Any) -> None:
    """Every failed method in scope, and whether a resit is left."""
    ttk.Label(
        parent,
        text=f"A method may normally be sat {config.MAX_RESITS} more times after a "
             "fail. A resit goes straight back to assessment; a retake needs further "
             "training first, so it cannot be requested without a plan for it.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    ok, summaries = widgets.guard(lambda: apprentice_service.list_apprentices(gui.actor))
    if not ok:
        return

    rows: list[dict[str, Any]] = []
    for summary in summaries or []:
        apprentice_id = summary.apprentice.apprentice_id
        loaded, progress = widgets.guard(_progress_for(gui, apprentice_id))
        if not loaded or progress is None:
            continue
        for result in progress.results:
            if result.is_pass:
                continue
            rows.append({
                "apprentice_id": apprentice_id,
                "name": summary.full_name,
                "result": result,
                "remaining": progress.resits_remaining(result.method),
            })

    table = widgets.DataTable(parent, _FAIL_COLUMNS)
    table.populate(
        rows,
        lambda r: (r["name"], r["result"].method, r["result"].grade,
                   r["result"].assessed_date, r["result"].attempt, r["remaining"]),
        identity=lambda r: r["result"].result_id,
        tag=lambda r: "Red" if r["remaining"] <= 0 else "Amber",
        noun="failed sitting",
    )
    if not rows:
        widgets.empty_state(parent, "Nothing has been failed.")
        return

    by_result = {r["result"].result_id: r for r in rows}

    def request() -> None:
        result_id = table.require_selection_int("request a resit")
        if result_id is None:
            return
        row = by_result[result_id]
        if row["remaining"] <= 0:
            widgets.warn(
                f"No further attempts at {row['result'].method} are permitted — "
                f"{row['result'].attempt} of {config.MAX_RESITS + 1} sittings used.",
                title="No attempts left",
            )
            return
        _request(gui, row)

    if gui.actor.can("epa.resit"):
        widgets.button_bar(parent, [("Request Resit…", request)])


def _request(gui, row: dict[str, Any]) -> None:
    result = row["result"]
    fields: list[dict[str, Any]] = [
        {"key": "resit_type", "label": "Type", "kind": "combo", "required": True,
         "options": config.RESIT_TYPES, "value": "Resit",
         "help": "Resit goes straight back to assessment; Retake means further "
                 "training first."},
        {"key": "reason", "label": "Reason", "kind": "text"},
        {"key": "training_plan", "label": "Training plan", "kind": "text",
         "help": "Required for a retake — that is what makes it a retake rather than "
                 "a resit."},
    ]

    def save(values: dict[str, Any]) -> Any:
        return epa_service.request_resit(
            gui.actor, row["apprentice_id"], result.result_id,
            resit_type=values["resit_type"], reason=values["reason"],
            training_plan=values["training_plan"],
        )

    dialog = widgets.FormDialog(
        gui.root, f"Resit {result.method} — {row['name']}", fields, save,
        intro=f"{result.method} was graded {result.grade} on {result.assessed_date} "
              f"(attempt {result.attempt}). {row['remaining']} further attempt(s) "
              "are permitted.",
        save_label="Request",
    )
    if dialog.saved:
        widgets.inform(
            f"{dialog.result.resit_type} requested. Book it from the Requests tab."
        )
        gui.refresh()


def _progress_for(gui, apprentice_id: int) -> Callable[[], Any]:
    """A no-argument reader for one apprentice's EPA position.

    A named factory rather than a lambda with a default argument: the
    loop below builds one per apprentice, and the default-argument trick
    that stops them all closing over the last id reads as a bug to
    anyone who has not met it before.
    """
    return lambda: epa_service.epa_progress(gui.actor, apprentice_id)


def _names(gui) -> dict[int, str]:
    """Apprentice ids to names: a resit row carries only the id."""
    ok, summaries = widgets.guard(lambda: apprentice_service.list_apprentices(gui.actor))
    if not ok:
        return {}
    return {s.apprentice.apprentice_id: s.full_name for s in summaries or []}
