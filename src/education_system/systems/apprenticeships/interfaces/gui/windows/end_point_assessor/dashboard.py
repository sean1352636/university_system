"""End-Point Assessment — end point assessor screen.

Your diary, gateway requests awaiting decision, and recent grading.

The assessor is an outsider to the provider, and the dashboard reflects
that: it holds the work in front of them and nothing about how the
training went. The provider's formative judgements — portfolio
assessment, review ratings, caseload notes — are deliberately absent,
because seeing them is precisely what would compromise the
independence the role exists for.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.workspace import reporting_service

logger = logging.getLogger(__name__)

TITLE = "End-Point Assessment"
SUBTITLE = "Your diary, gateway requests awaiting decision, and recent grading."

_BOOKING_COLUMNS = (
    ("apprentice", "Apprentice", 190),
    ("method", "Method", 220),
    ("when", "When", 160),
    ("location", "Where", 180),
    ("standard", "Standard", 110),
    ("status", "Status", 120),
)

_GATEWAY_COLUMNS = (
    ("apprentice", "Apprentice", 200),
    ("programme", "Programme", 220),
    ("employer", "Employer", 180),
    ("gateway", "Gateway", 110),
    ("requested", "Requested", 120),
)

_RESIT_COLUMNS = (
    ("requested", "Requested", 160),
    ("type", "Type", 100),
    ("status", "Status", 120),
    ("reason", "Reason", 420),
)

_RESULT_COLUMNS = (
    ("assessed", "Assessed", 120),
    ("method", "Method", 230),
    ("grade", "Grade", 110),
    ("attempt", "Attempt", 90, "e"),
)


def render(gui) -> None:
    """Draw the assessor dashboard into the content pane."""
    frame = gui.clear()
    ok, data = widgets.guard(lambda: reporting_service.dashboard(gui.actor))
    if not ok or data is None:
        widgets.heading(frame, TITLE, subtitle=SUBTITLE)
        return

    widgets.heading(frame, str(data.get("title") or TITLE), subtitle=SUBTITLE)
    if data.get("unavailable"):
        widgets.empty_state(frame, "No dashboard is defined for your role.")
        return

    widgets.kpi_row(frame, data.get("kpis") or [])

    scroll = widgets.scrollable(frame)

    _bookings(
        scroll, "My diary — the next fortnight", data.get("diary") or [],
        "Nothing is booked in the next fortnight.",
    )
    _bookings(
        scroll, "My open bookings", data.get("my_bookings") or [],
        "Nothing is assigned to you.",
    )
    _bookings(
        scroll, "Requested — no date yet", data.get("unassigned") or [],
        "Every booking the provider has placed has a date against it.",
    )

    box = widgets.section(scroll, "Gateway requests awaiting a decision")
    requests = data.get("gateway_requests") or []
    if requests:
        ttk.Label(
            box,
            text="Yours alone to decide. Nobody at the training provider — "
                 "administrators included — may approve a gateway request.",
            foreground=config.MUTED_FG, wraplength=900, justify="left",
        ).pack(anchor="w", pady=(0, 6))
        table = widgets.DataTable(box, _GATEWAY_COLUMNS, height=min(8, len(requests)))
        table.populate(
            requests,
            lambda r: (r.get("apprentice_name"), r.get("programme_title"),
                       r.get("employer_name"), r.get("gateway_status"),
                       r.get("requested_at")),
            identity=lambda r: r["apprentice_id"],
            tag=lambda _r: "Amber",
            noun="request",
        )
    else:
        widgets.empty_state(box, "Nothing is waiting on you.")

    box = widgets.section(scroll, "Resits requested")
    resits = data.get("resits") or []
    if resits:
        table = widgets.DataTable(box, _RESIT_COLUMNS, height=min(6, len(resits)))
        table.populate(
            resits,
            lambda r: (r.requested_at, r.resit_type, r.status, r.reason),
            identity=lambda r: r.resit_id,
            tag=lambda r: "Green" if r.booking_id else "Amber",
            noun="resit",
        )
    else:
        widgets.empty_state(box, "None requested.")

    box = widgets.section(scroll, "Recently graded")
    results = data.get("recent_results") or []
    if results:
        table = widgets.DataTable(box, _RESULT_COLUMNS, height=min(8, len(results)))
        table.populate(
            results,
            lambda r: (r.assessed_date, r.method, r.grade, r.attempt),
            identity=lambda r: r.result_id,
            tag=lambda r: "Green" if r.is_pass else "Red",
            noun="result",
        )
    else:
        widgets.empty_state(box, "You have not graded anything yet.")

    widgets.button_bar(frame, [("Refresh", lambda: render(gui))])


def _bookings(parent: Any, heading: str, rows: list, empty: str) -> None:
    box = widgets.section(parent, heading)
    if not rows:
        widgets.empty_state(box, empty)
        return
    table = widgets.DataTable(box, _BOOKING_COLUMNS, height=min(8, len(rows)))
    table.populate(
        rows,
        lambda r: (
            r.get("apprentice_name"), r.get("method"),
            f"{r.get('scheduled_date') or widgets.EMPTY} "
            f"{r.get('scheduled_time') or ''}".strip(),
            r.get("location"), r.get("programme_reference"), r.get("status"),
        ),
        identity=lambda r: r["booking_id"],
        tag=lambda r: "Amber" if not r.get("scheduled_date") else None,
        noun="booking",
    )
