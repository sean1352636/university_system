"""Employer risk: every employer rated Low, Medium or High, worst first.

The rating is worked out from attendance, off-the-job progress, reviews,
commitments and satisfaction (see ``domain/employers/risk.py``); each
point it scores comes with a reason, shown for the selected employer.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import employer_risk_service

logger = logging.getLogger(__name__)

_COLUMNS = (
    ("name", "Employer", 220),
    ("level", "Risk", 80),
    ("points", "Points", 60, "e"),
    ("apprentices", "Active / all", 90, "e"),
    ("attendance", "Attendance", 90, "e"),
    ("otj", "OTJ on track", 100, "e"),
    ("reviews", "Reviews done / overdue", 150, "e"),
    ("commitments", "Commitments overdue / open", 170, "e"),
    ("satisfaction", "Satisfaction", 100, "e"),
)

_PROMPT = "Select an employer to see why it is rated as it is."


def render(gui: Any) -> None:
    """The risk table, highest risk first, with the reasons for the selection."""
    frame = gui.clear()
    widgets.heading(
        frame, "Employer Risk",
        subtitle="Each employer rated from attendance, off-the-job progress, reviews, "
                 "commitments and satisfaction. Every point carries a reason.",
    )
    ok, results = widgets.guard(lambda: employer_risk_service.assess_employers(gui.actor))
    if not ok:
        return
    if not results:
        widgets.empty_state(frame, "There are no employers to rate yet.")
        return

    widgets.kpi_row(frame, [
        ("High risk", sum(1 for r in results if r.level == "High")),
        ("Medium risk", sum(1 for r in results if r.level == "Medium")),
        ("Low risk", sum(1 for r in results if r.level == "Low")),
    ])
    reasons = widgets.empty_state(widgets.section(frame, "Why"), _PROMPT)
    reasons.config(wraplength=1100, justify="left")
    by_id = {r.employer_id: r for r in results}

    table = widgets.DataTable(frame, _COLUMNS, on_activate=lambda _ident: show())

    def show() -> None:
        ident = table.selected_int()
        result = by_id.get(ident) if ident is not None else None
        if result is None:
            reasons.config(text=_PROMPT)
            return
        reasons.config(
            text=f"{result.employer_name}: {result.level} risk, {result.points} point(s).\n"
                 + "\n".join(f"• {reason}" for reason in result.reasons)
        )

    def contacts() -> None:
        employer_id = table.require_selection_int("open an employer")
        if employer_id is None:
            return
        from education_system.systems.apprenticeships.interfaces.gui.windows.shared import (
            employer_contacts,
        )
        employer_contacts.open_employer(gui, employer_id)

    buttons: list[tuple[str, Any]] = [("Show reasons", show), ("Refresh", lambda: render(gui))]
    if gui.actor.can("employer.contact"):
        buttons.append(("Contacts & commitments →", contacts))
    widgets.button_bar(frame, buttons)

    table.tree.bind("<<TreeviewSelect>>", lambda _e: show())
    table.populate(
        results,
        lambda r: (
            r.employer_name, r.level, r.points,
            f"{r.metrics.active_apprentices} / {r.metrics.apprentices}",
            widgets.percent(r.metrics.attendance_percent),
            widgets.percent(r.metrics.otj_compliance_percent),
            f"{r.metrics.reviews_completed} / {r.metrics.reviews_overdue}",
            f"{r.metrics.commitments_overdue} / {r.metrics.commitments_outstanding}",
            "—" if r.metrics.satisfaction is None else f"{r.metrics.satisfaction:.1f} / 5",
        ),
        identity=lambda r: r.employer_id,
        tag=lambda r: r.rag,
        noun="employer",
    )
