"""The tutor's caseload list, with a detail pane for one apprentice."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    portfolio_service,
    training_service,
)

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your login is not linked to a staff record, so no apprentices are assigned to it. "
    "Ask an administrator to link your account to your staff profile — an unlinked "
    "login is not the same as an empty caseload."
)

COLUMNS = (
    ("name", "Apprentice", 190),
    ("uln", "ULN", 110),
    ("programme", "Programme", 200),
    ("employer", "Employer", 170),
    ("status", "Status", 130),
    ("otj", "Off-the-job", 90, "e"),
    ("ksb", "KSBs", 80, "e"),
    ("reviews", "Reviews open", 100, "e"),
    ("gateway", "Gateway", 110),
)


def render(gui) -> None:
    """Every apprentice assigned to this tutor, filtered and drillable."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "My Caseload",
        subtitle="The apprentices you are the named tutor for.",
    )
    if gui.actor.staff_id is None:
        widgets.empty_state(frame, UNLINKED)
        return

    caseload = staff_repository.build_caseload(gui.actor.staff_id)
    if caseload is not None:
        ttk.Label(
            frame, text=_pressure_line(caseload), foreground=config.MUTED_FG,
        ).pack(anchor="w", pady=(0, 8))

    body = ttk.Frame(frame)

    def reload() -> None:
        for child in body.winfo_children():
            child.destroy()
        rows = apprentice_service.list_apprentices(gui.actor, **bar.values())
        if not rows:
            widgets.empty_state(
                body,
                "No apprentices match these filters. Clear them to see the whole "
                "caseload; if it is still empty, an administrator assigns apprentices "
                "to a tutor.",
            )
            return

        table = widgets.DataTable(
            body, COLUMNS,
            on_activate=lambda ident: _detail(gui, int(ident)),
        )
        table.populate(
            rows,
            lambda s: (
                s.full_name, s.apprentice.uln, s.programme_title, s.employer_name,
                s.apprentice.status, widgets.percent(s.otj_percent),
                widgets.percent(s.ksb_percent), s.open_reviews, s.gateway_status,
            ),
            identity=lambda s: s.apprentice.apprentice_id,
            tag=lambda s: s.apprentice.status,
            noun="apprentice",
        )
        _actions(gui, body, table, {s.apprentice.apprentice_id: s.full_name for s in rows})

    bar = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.APPRENTICE_STATUSES),
            ("search", "Search", "entry"),
            ("active_only", "Active only", "check"),
        ),
        reload,
    )
    body.pack(fill="both", expand=True)
    reload()


def _actions(gui, parent, table: widgets.DataTable, names: dict[int, str]) -> None:
    """The buttons under the list, all of them selection-driven."""

    def detail() -> None:
        chosen = table.require_selection_int("see the full record")
        if chosen is not None:
            _detail(gui, chosen)

    def elsewhere(module: str, label: str, action: str) -> None:
        chosen = table.require_selection_int(action)
        if chosen is None:
            return
        # The render contract takes no arguments, so the target screen
        # opens on its own queue rather than pre-filtered. Naming the
        # apprentice in the status bar keeps the trail visible.
        gui.show(module, label)
        gui.status_var.set(f"{label} — looking for {names.get(chosen, chosen)}")

    widgets.button_bar(parent, [
        ("View Detail", detail),
        ("Open Portfolio", lambda: elsewhere("staff.portfolios", "Portfolios", "open a portfolio")),
        ("Open Reviews", lambda: elsewhere("staff.reviews", "Progress Reviews", "open reviews")),
        ("Gateway Check", lambda: elsewhere(
            "staff.gateway_checks", "Gateway Checks", "run a gateway check"
        )),
    ])


def _detail(gui, apprentice_id: int) -> None:
    """One apprentice's record, in place of the list."""
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    if not ok or summary is None:
        widgets.button_bar(frame, [("← Back to caseload", lambda: render(gui))])
        return

    record = summary.apprentice
    widgets.heading(
        frame, summary.full_name,
        subtitle=f"{summary.programme_title or 'No programme'} · {record.status}",
    )
    widgets.field_grid(frame, [
        ("ULN", record.uln),
        ("Date of birth", record.date_of_birth),
        ("Email", record.email),
        ("Phone", record.phone),
        ("Employer", summary.employer_name),
        ("Workplace", summary.workplace_name),
        ("Programme", summary.programme_title),
        ("Level", summary.programme_level),
        ("Started", record.start_date),
        ("Planned end", record.planned_end_date),
        ("Weekly hours", record.weekly_hours),
        ("Funding model", record.funding_model),
        ("Support needs", record.support_needs),
        ("Prior learning", record.prior_learning),
    ], columns=3)

    progress = widgets.section(frame, "Progress")
    widgets.progress_row(
        progress, "Programme elapsed", summary.progress_percent,
        detail=widgets.percent(summary.progress_percent),
    )

    ok, hours = widgets.guard(lambda: training_service.otj_summary(gui.actor, apprentice_id))
    if ok and hours is not None:
        widgets.progress_row(
            progress, "Off-the-job hours", hours.percent_complete,
            detail=(
                f"{hours.approved_hours:,.1f} of {hours.target_hours:,.1f} approved · "
                f"{hours.pending_hours:,.1f} awaiting approval · "
                f"{hours.weekly_hours_needed:,.1f}h/week to finish"
            ),
            rag=hours.rag_rating,
        )

    ok, portfolio = widgets.guard(lambda: portfolio_service.get_portfolio(gui.actor, apprentice_id))
    if ok and portfolio is not None:
        widgets.progress_row(
            progress, "Portfolio", portfolio.percent_competent,
            detail=(
                f"{portfolio.competent_ksbs} of {portfolio.total_ksbs} KSBs competent · "
                f"{len(portfolio.awaiting_assessment)} awaiting assessment"
            ),
            rag="Green" if portfolio.is_complete else "Amber",
        )

    widgets.field_grid(frame, [
        ("Reviews open", summary.open_reviews),
        ("Gateway", summary.gateway_status),
        ("Tutor", summary.tutor_name),
    ], columns=3)
    widgets.button_bar(frame, [("← Back to caseload", lambda: render(gui))])


def _pressure_line(caseload) -> str:
    """The one-line caseload health summary above the list."""
    return (
        f"Caseload {caseload.rag_rating}: {caseload.active} active of {caseload.total} "
        f"· {caseload.at_gateway} at gateway · {caseload.reviews_overdue} reviews overdue "
        f"· {caseload.otj_behind} behind on off-the-job "
        f"· {caseload.evidence_awaiting_assessment} evidence items to assess "
        f"· room for {caseload.headroom} more"
    )
