"""Gateway Requests — end point assessor screen.

Apprentices the provider says are ready. Yours alone to approve.

The decision is the whole reason this role exists as a separate one:
``gateway.approve`` is withheld from the provider admin, so this is the
only screen in the system where it can be taken. It therefore shows the
evidence behind the request in full rather than a summary — an assessor
approving on a green tick they cannot interrogate is not independence,
it is a rubber stamp.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import gateway_service

logger = logging.getLogger(__name__)

TITLE = "Gateway Requests"
SUBTITLE = "Apprentices the provider says are ready. Yours alone to approve."

_QUEUE_COLUMNS = (
    ("apprentice", "Apprentice", 200),
    ("uln", "ULN", 120),
    ("programme", "Programme", 220),
    ("standard", "Standard", 100),
    ("employer", "Employer", 180),
    ("gateway", "Gateway", 110),
    ("requested", "Requested", 110),
)

_CHECK_COLUMNS = (
    ("requirement", "Requirement", 380),
    ("met", "Met", 70),
    ("how", "Decided", 110),
    ("detail", "Evidence", 520),
)

_GATEWAY_TAGS = {"Approved": "Green", "Requested": "Amber", "Rejected": "Red"}


def render(gui) -> None:
    """Draw the gateway requests screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.can("gateway.view"):
        widgets.empty_state(frame, "Your role may not see gateway requests.")
        return

    filters = widgets.FilterBar(
        frame, (("status", "Gateway", "combo", config.GATEWAY_STATUSES),),
        lambda: reload(),
    )
    table = widgets.DataTable(
        frame, _QUEUE_COLUMNS,
        on_activate=lambda ident: _detail(gui, int(ident)),
    )
    hint = widgets.empty_state(frame, "")

    def reload() -> None:
        chosen = filters.values()
        # The queue defaults to what is actually waiting on a decision;
        # the filter widens it to the whole gateway population.
        chosen.setdefault("status", "Requested")
        _, rows = widgets.guard(
            lambda: gateway_service.gateway_queue(gui.actor, **chosen)
        )
        rows = rows or []
        table.populate(
            rows,
            lambda r: (r.get("apprentice_name"), r.get("uln"), r.get("programme_title"),
                       r.get("programme_reference"), r.get("employer_name"),
                       r.get("gateway_status"), r.get("requested_at")),
            identity=lambda r: r["apprentice_id"],
            tag=lambda r: _GATEWAY_TAGS.get(r.get("gateway_status")),
            noun="request",
        )
        hint.config(text="" if rows else (
            "Nothing is waiting on a decision. Set the Gateway filter to see "
            "apprentices at other stages."
        ))

    def open_detail() -> None:
        apprentice_id = table.require_selection_int("open a request")
        if apprentice_id is not None:
            _detail(gui, apprentice_id)

    widgets.button_bar(frame, [("Open", open_detail), ("Refresh", reload)])
    reload()


# ═════════════════════════════════════════════════════════════════════
# One request
# ═════════════════════════════════════════════════════════════════════

def _detail(gui, apprentice_id: int) -> None:
    """The evidence behind one request, and the decision on it."""
    frame = gui.clear()
    ok, record = widgets.guard(
        lambda: gateway_service.evaluate_gateway(gui.actor, apprentice_id)
    )
    back = ("← Back to requests", lambda: render(gui))
    if not ok or record is None:
        widgets.button_bar(frame, [back])
        return

    name = _name(gui, apprentice_id)
    widgets.heading(frame, f"Gateway — {name}", subtitle=record.summary_line())
    widgets.progress_row(
        frame, "Requirements met", record.percent_complete,
        detail=f"{record.met_count} of {record.total_count}",
        rag="Green" if record.is_ready else "Red",
    )
    widgets.field_grid(frame, [
        ("Status", record.status),
        ("Put forward", record.requested_at),
        ("By", record.requested_by),
        ("Decided", record.decided_at),
        ("By", record.decided_by),
        ("Decision notes", record.decision_notes),
    ], columns=3)

    table = widgets.DataTable(frame, _CHECK_COLUMNS, height=len(record.checks) or 3)
    table.populate(
        record.checks,
        lambda c: (c.label, "Yes" if c.met else "No",
                   "Automatic" if c.automatic else "Recorded", c.detail),
        identity=lambda c: c.requirement_key,
        tag=lambda c: "Green" if c.met else "Red",
        noun="requirement",
    )
    ttk.Label(
        frame,
        text="Automatic requirements are recomputed from the provider's own records "
             "every time this screen opens, so a figure that has moved since the "
             "request was made shows here as it stands now, not as it stood then.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(6, 0))

    if not record.is_ready:
        ttk.Label(
            frame,
            text="Not everything is met. Approving anyway is possible — the check is "
                 "on the provider's request, not on your decision — but the shortfall "
                 "above is what you would be approving over.",
            foreground=config.ERROR_FG, wraplength=900, justify="left",
        ).pack(anchor="w", pady=(6, 0))

    buttons: list[tuple[str, Any]] = []
    if gui.actor.can("gateway.approve"):
        buttons += [
            ("Approve", lambda: _approve(gui, apprentice_id, name)),
            ("Reject…", lambda: _reject(gui, apprentice_id, name)),
        ]
    buttons.append(back)
    widgets.button_bar(frame, buttons)


def _approve(gui, apprentice_id: int, name: str) -> None:
    fields = [
        {"key": "note", "label": "Decision note", "kind": "text",
         "help": "Recorded against the gateway decision and readable by the provider."},
    ]

    def save(values: dict[str, Any]) -> Any:
        return gateway_service.approve_gateway(
            gui.actor, apprentice_id, note=values["note"]
        )

    dialog = widgets.FormDialog(
        gui.root, f"Approve gateway — {name}", fields, save,
        intro="The apprentice passes through gateway and assessment methods can be "
              "booked against them.",
        save_label="Approve",
    )
    if dialog.saved:
        widgets.inform(f"Gateway approved for {name}.")
        _detail(gui, apprentice_id)


def _reject(gui, apprentice_id: int, name: str) -> None:
    fields = [
        {"key": "reason", "label": "Reason", "kind": "text", "required": True,
         "help": "The apprentice goes back to training, so say what the provider has "
                 "to put right before re-requesting."},
    ]

    def save(values: dict[str, Any]) -> Any:
        return gateway_service.reject_gateway(
            gui.actor, apprentice_id, reason=values["reason"]
        )

    dialog = widgets.FormDialog(
        gui.root, f"Reject gateway — {name}", fields, save,
        intro="Sends the request back and returns the apprentice to On Programme, "
              "rather than leaving them in limbo at Gateway.",
        save_label="Reject",
    )
    if dialog.saved:
        widgets.inform(f"Sent back. {name} is on programme again.")
        _detail(gui, apprentice_id)


def _name(gui, apprentice_id: int) -> str:
    """The apprentice's name for the heading, or a bare id."""
    from education_system.systems.apprenticeships.services import apprentice_service

    try:
        return apprentice_service.get_apprentice(gui.actor, apprentice_id).full_name
    except Exception:
        logger.debug("Could not name apprentice %s", apprentice_id, exc_info=True)
        return f"Apprentice {apprentice_id}"
