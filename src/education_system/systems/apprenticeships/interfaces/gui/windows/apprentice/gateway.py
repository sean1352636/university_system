"""Gateway — apprentice screen.

What stands between you and your End-Point Assessment.

Read-only by design. Every requirement here is either computed from
evidence the apprentice has already generated or recorded by somebody
else — the employer's confirmation — and none of it is theirs to tick.
So the screen's whole job is to say, in order, what is left and what
each shortfall actually is: "38.5 of 240 approved hours", not
"off-the-job hours: not met".
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import gateway_service

logger = logging.getLogger(__name__)

TITLE = "Gateway"
SUBTITLE = "What stands between you and your End-Point Assessment."

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is no gateway "
    "position to show. Ask your training provider's administrator to link your account."
)

_CHECK_COLUMNS = (
    ("requirement", "Requirement", 380),
    ("met", "Met", 70),
    ("how", "Decided", 110),
    ("detail", "Where you are", 520),
)

# What each status means for the apprentice, rather than for the record.
_EXPLANATION = {
    "Not Ready": (
        "You have not been put forward yet. Once everything below is met, your tutor "
        "sends you to the assessment organisation."
    ),
    "Requested": (
        "Your provider has put you forward. The assessment organisation decides from "
        "here — they are independent of your provider, which is the point."
    ),
    "Approved": (
        "You are through gateway. Your assessment methods can be booked now."
    ),
    "Rejected": (
        "The assessment organisation sent it back, so you are on programme again. "
        "The reason is below — your tutor will work through it with you."
    ),
}


def render(gui) -> None:
    """Draw the gateway screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    apprentice_id = gui.actor.apprentice_id
    if apprentice_id is None:
        widgets.empty_state(frame, UNLINKED)
        return

    ok, record = widgets.guard(
        lambda: gateway_service.evaluate_gateway(gui.actor, apprentice_id)
    )
    if not ok or record is None:
        return

    widgets.kpi_row(frame, [
        ("Status", record.status),
        ("Requirements met", f"{record.met_count} of {record.total_count}"),
        ("Still to do", len(record.outstanding)),
    ], per_row=3)
    widgets.progress_row(
        frame, "Gateway readiness", record.percent_complete,
        detail=record.summary_line(),
        rag="Green" if record.is_ready else "Amber",
    )

    ttk.Label(
        frame,
        text=_EXPLANATION.get(record.status, ""),
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(8, 0))

    if record.decision_notes:
        box = widgets.section(frame, "What the assessment organisation said")
        ttk.Label(
            box, text=record.decision_notes, wraplength=900, justify="left",
        ).pack(anchor="w")

    if record.requested_at or record.decided_at:
        widgets.field_grid(frame, [
            ("Put forward", record.requested_at),
            ("By", record.requested_by),
            ("Decided", record.decided_at),
            ("By", record.decided_by),
        ], columns=4)

    box = widgets.section(frame, "Every requirement")
    table = widgets.DataTable(box, _CHECK_COLUMNS, height=len(record.checks) or 3)
    table.populate(
        record.checks,
        lambda c: (c.label, "Yes" if c.met else "No",
                   "Automatic" if c.automatic else "Recorded", c.detail),
        identity=lambda c: c.requirement_key,
        tag=lambda c: "Green" if c.met else "Red",
        noun="requirement",
    )
    ttk.Label(
        box,
        text="Automatic requirements are worked out from your record every time this "
             "screen opens, so they cannot be ticked by hand — and they go back down "
             "if the evidence behind them changes.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(6, 0))

    _next_steps(frame, record)
    widgets.button_bar(frame, [("Refresh", lambda: render(gui))])


def _next_steps(parent: Any, record: Any) -> None:
    """What to actually do about each thing that is not met."""
    box = widgets.section(parent, "What is left")
    if record.is_ready and record.status == "Not Ready":
        ttk.Label(
            box,
            text="Everything is met. Ask your tutor to put you forward — you cannot "
                 "request gateway yourself, and neither can your provider approve it.",
            wraplength=900, justify="left",
        ).pack(anchor="w")
        return
    if not record.outstanding:
        ttk.Label(
            box, text="Nothing — every requirement is met.", wraplength=900,
        ).pack(anchor="w")
        return

    for check in record.outstanding:
        line = ttk.Frame(box)
        line.pack(fill="x", pady=2)
        ttk.Label(line, text="·", foreground=config.ERROR_FG).pack(side="left", padx=(0, 6))
        ttk.Label(line, text=check.label, font=("", 10, "bold")).pack(side="left")
        ttk.Label(
            line, text=f"— {_advice(check)}", foreground=config.MUTED_FG,
            wraplength=700, justify="left",
        ).pack(side="left", padx=(6, 0))


def _advice(check: Any) -> str:
    """The shortfall, plus who fixes it."""
    detail = check.detail or "not met"
    who = {
        "otj_hours": "log and get the hours approved",
        "english": "your provider records this once you have passed or are exempt",
        "maths": "your provider records this once you have passed or are exempt",
        "portfolio": "add evidence for the KSBs that are not competent yet",
        "reviews": "attend the review and sign it afterwards",
        "employer_sign_off": "your employer confirms you are ready",
        "minimum_duration": "time on programme — there is nothing to do but continue",
    }.get(check.requirement_key)
    return f"{detail} ({who})" if who else detail
