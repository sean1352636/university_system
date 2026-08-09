"""Gateway Checks — staff screen.

Where each apprentice stands against every gateway requirement.

The screen a tutor runs before a monthly EPA planning meeting: who could
go now, and what is holding the rest up. Requesting gateway is here;
approving it is not, and never will be — ``gateway.approve`` belongs to
the independent assessment organisation and is withheld from the
provider by design.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import gateway_service

logger = logging.getLogger(__name__)

TITLE = "Gateway Checks"
SUBTITLE = "Where each apprentice stands against every gateway requirement."

_READINESS_COLUMNS = (
    ("apprentice", "Apprentice", 200),
    ("programme", "Programme", 200),
    ("employer", "Employer", 170),
    ("met", "Met", 70, "e"),
    ("of", "Of", 60, "e"),
    ("ready", "Ready", 70),
    ("outstanding", "Outstanding", 520),
)

_QUEUE_COLUMNS = (
    ("apprentice", "Apprentice", 200),
    ("programme", "Programme", 200),
    ("employer", "Employer", 170),
    ("tutor", "Tutor", 160),
    ("gateway", "Gateway", 110),
    ("requested", "Requested", 110),
    ("decided", "Decided", 110),
)

_CHECK_COLUMNS = (
    ("requirement", "Requirement", 380),
    ("met", "Met", 70),
    ("how", "Decided", 110),
    ("detail", "Where they are", 520),
)

_GATEWAY_TAGS = {
    "Approved": "Green", "Requested": "Amber", "Rejected": "Red",
}


def render(gui) -> None:
    """Draw the gateway checks screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.can("gateway.view"):
        widgets.empty_state(frame, "Your role may not see the gateway position.")
        return

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True)

    readiness = ttk.Frame(notebook, padding=8)
    notebook.add(readiness, text="Readiness")
    _readiness(gui, readiness)

    queue = ttk.Frame(notebook, padding=8)
    notebook.add(queue, text="Queue")
    _queue(gui, queue)


# ═════════════════════════════════════════════════════════════════════
# Readiness
# ═════════════════════════════════════════════════════════════════════

def _readiness(gui, parent: Any) -> None:
    ok, rows = widgets.guard(lambda: gateway_service.readiness_report(gui.actor))
    if not ok:
        return
    rows = rows or []
    rows.sort(key=lambda r: (not r["is_ready"], -r["met"]))
    ready = [r for r in rows if r["is_ready"]]

    widgets.kpi_row(parent, [
        ("Active apprentices", len(rows)),
        ("Could go now", len(ready)),
        ("Still short", len(rows) - len(ready)),
    ], per_row=3)

    if not rows:
        widgets.empty_state(
            parent, "Nobody in scope is on programme, so there is nothing to check."
        )
        return

    table = widgets.DataTable(
        parent, _READINESS_COLUMNS,
        on_activate=lambda ident: _detail(gui, int(ident)),
    )
    table.populate(
        rows,
        lambda r: (r["apprentice"].full_name, r["apprentice"].programme_title,
                   r["apprentice"].employer_name, r["met"], r["total"], r["is_ready"],
                   "; ".join(r["outstanding_labels"])),
        identity=lambda r: r["apprentice"].apprentice.apprentice_id,
        tag=lambda r: "Green" if r["is_ready"] else "Amber",
        noun="apprentice",
    )

    def open_detail() -> None:
        apprentice_id = table.require_selection_int("open an apprentice's checks")
        if apprentice_id is not None:
            _detail(gui, apprentice_id)

    def request() -> None:
        apprentice_id = table.require_selection_int("request gateway")
        if apprentice_id is not None:
            _request(gui, apprentice_id, on_done=gui.refresh)

    buttons: list[tuple[str, Any]] = [("Open", open_detail)]
    if gui.actor.can("gateway.request"):
        buttons.append(("Request Gateway…", request))
    buttons.append(("Refresh", lambda: gui.refresh()))
    widgets.button_bar(parent, buttons)


# ═════════════════════════════════════════════════════════════════════
# Queue
# ═════════════════════════════════════════════════════════════════════

def _queue(gui, parent: Any) -> None:
    ttk.Label(
        parent,
        text="Where each request has got to with the assessment organisation. The "
             "decision is theirs alone — nobody at the provider, administrators "
             "included, may approve a gateway request.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    filters = widgets.FilterBar(
        parent, (("status", "Gateway", "combo", config.GATEWAY_STATUSES),),
        lambda: reload(),
    )
    table = widgets.DataTable(
        parent, _QUEUE_COLUMNS,
        on_activate=lambda ident: _detail(gui, int(ident)),
    )

    def reload() -> None:
        _, rows = widgets.guard(
            lambda: gateway_service.gateway_queue(gui.actor, **filters.values())
        )
        rows = rows or []
        table.populate(
            rows,
            lambda r: (r.get("apprentice_name"), r.get("programme_title"),
                       r.get("employer_name"), r.get("tutor_name"),
                       r.get("gateway_status"), r.get("requested_at"),
                       r.get("decided_at")),
            identity=lambda r: r["apprentice_id"],
            tag=lambda r: _GATEWAY_TAGS.get(r.get("gateway_status")),
            noun="apprentice",
        )
        if not rows:
            table.count_var.set("Nobody is at or approaching gateway.")

    def open_detail() -> None:
        apprentice_id = table.require_selection_int("open an apprentice's checks")
        if apprentice_id is not None:
            _detail(gui, apprentice_id)

    widgets.button_bar(parent, [("Open", open_detail)])
    reload()


# ═════════════════════════════════════════════════════════════════════
# One apprentice
# ═════════════════════════════════════════════════════════════════════

def _detail(gui, apprentice_id: int) -> None:
    """One apprentice against every requirement, and the sign-off action."""
    frame = gui.clear()
    ok, record = widgets.guard(
        lambda: gateway_service.evaluate_gateway(gui.actor, apprentice_id)
    )
    back = ("← Back to gateway checks", lambda: render(gui))
    if not ok or record is None:
        widgets.button_bar(frame, [back])
        return

    name = _name(gui, apprentice_id)
    widgets.heading(frame, f"Gateway — {name}", subtitle=record.summary_line())
    widgets.progress_row(
        frame, "Requirements met", record.percent_complete,
        detail=f"{record.met_count} of {record.total_count}",
        rag="Green" if record.is_ready else "Amber",
    )
    widgets.field_grid(frame, [
        ("Status", record.status),
        ("Requested", record.requested_at),
        ("Requested by", record.requested_by),
        ("Decided", record.decided_at),
        ("Decided by", record.decided_by),
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
        text="Automatic requirements are recomputed on every read and cannot be "
             "ticked by hand: a hand-back of approved hours or a KSB reopened for "
             "more evidence takes the requirement with it, which is what gateway is "
             "for. Only the employer's confirmation is recorded by a person.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(6, 0))

    buttons: list[tuple[str, Any]] = []
    if gui.actor.can("gateway.request"):
        buttons.append(("Record Employer Sign-Off…", lambda: _sign_off(
            gui, apprentice_id, record, name
        )))
        buttons.append(("Request Gateway…", lambda: _request(
            gui, apprentice_id, on_done=lambda: _detail(gui, apprentice_id)
        )))
    buttons.append(back)
    widgets.button_bar(frame, buttons)


def _sign_off(gui, apprentice_id: int, record: Any, name: str) -> None:
    """Record the one requirement no system can derive."""
    current = next(
        (c for c in record.checks if c.requirement_key == "employer_sign_off"), None
    )
    fields = [
        {"key": "confirmed", "label": "Employer confirms readiness", "kind": "check",
         "value": bool(current and current.met)},
        {"key": "note", "label": "Evidence", "kind": "text",
         "value": (current.evidence_note if current else "") or "",
         "help": "Who said so, and where — a sign-off given verbally in a review "
                 "still has to be attributable. Your username and today's date are "
                 "stamped on it automatically.",
         },
    ]

    def save(values: dict[str, Any]) -> Any:
        return gateway_service.set_employer_sign_off(
            gui.actor, apprentice_id,
            confirmed=bool(values["confirmed"]), note=values["note"],
        )

    if widgets.FormDialog(gui.root, f"Employer sign-off — {name}", fields, save).saved:
        _detail(gui, apprentice_id)


def _request(gui, apprentice_id: int, *, on_done: Any) -> None:
    """Put an apprentice forward, once everything is actually met."""
    ok, record = widgets.guard(
        lambda: gateway_service.evaluate_gateway(gui.actor, apprentice_id)
    )
    if not ok or record is None:
        return
    if not record.is_ready:
        widgets.warn(
            "Not everything is met yet, so the request would be refused:\n\n"
            + "\n".join(
                f"·  {c.label} — {c.detail or 'not met'}" for c in record.outstanding
            ),
            title="Not ready for gateway",
        )
        return

    fields = [
        {"key": "note", "label": "Note", "kind": "text",
         "help": "Goes to the audit trail. The assessment organisation's own decision "
                 "notes are separate and theirs to write."},
    ]

    def save(values: dict[str, Any]) -> Any:
        return gateway_service.request_gateway(
            gui.actor, apprentice_id, note=values["note"]
        )

    dialog = widgets.FormDialog(
        gui.root, "Request gateway", fields, save,
        intro="Puts this apprentice forward to the assessment organisation and moves "
              "them to the Gateway status. The decision is theirs from here.",
        save_label="Request",
    )
    if dialog.saved:
        widgets.inform(
            "Put forward. The assessment organisation decides from here — the "
            "provider cannot approve its own gateway."
        )
        on_done()


def _name(gui, apprentice_id: int) -> str:
    """The apprentice's name for the heading, or a bare id."""
    from education_system.systems.apprenticeships.services import apprentice_service

    try:
        return apprentice_service.get_apprentice(gui.actor, apprentice_id).full_name
    except Exception:
        logger.debug("Could not name apprentice %s", apprentice_id, exc_info=True)
        return f"Apprentice {apprentice_id}"
