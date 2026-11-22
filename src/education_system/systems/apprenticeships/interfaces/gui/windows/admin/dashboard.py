"""The provider's opening screen."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.workspace import reporting_service

logger = logging.getLogger(__name__)

_SUBTITLE = (
    "Where the provider stands today. Each section opens the screen that can "
    "do something about what it shows."
)

# Enough rows to see the shape of a problem; the linked screen has the rest.
_ROWS = 8


def render(gui) -> None:
    """Provider-wide health: cohort, delivery, money and compliance."""
    frame = gui.clear()
    widgets.heading(frame, "Provider Dashboard", subtitle=_SUBTITLE)

    ok, data = widgets.guard(lambda: reporting_service.admin_dashboard(gui.actor))
    if not ok or data is None:
        widgets.empty_state(
            frame,
            "The dashboard could not be built. Pick another screen from the "
            "navigation panel, or ask an administrator to check the message above.",
        )
        return

    body = widgets.scrollable(frame)
    widgets.kpi_row(body, data["kpis"])
    _status_breakdown(gui, body, data)
    _behind_on_otj(gui, body, data)
    _compliance_flags(gui, body, data)
    _gateway_queue(gui, body, data)
    _caseloads(gui, body, data)


# ═════════════════════════════════════════════════════════════════════
# Sections
# ═════════════════════════════════════════════════════════════════════

def _status_breakdown(gui, parent, data: dict[str, Any]) -> None:
    counts = data.get("by_status") or {}
    section = widgets.section(parent, "Where the cohort is")
    # Every status, present or not: a zero in a column that is normally
    # busy says as much as a large number.
    pairs = [(status, counts.get(status, 0)) for status in config.APPRENTICE_STATUSES]
    widgets.field_grid(section, pairs, columns=4)
    _open(gui, section, "admin.apprentices", "Apprentices", "apprentice.view")


def _behind_on_otj(gui, parent, data: dict[str, Any]) -> None:
    rows = data.get("behind_on_otj") or []
    section = widgets.section(parent, "Behind on off-the-job hours")
    if not rows:
        widgets.empty_state(
            section,
            "Nobody on programme is behind their off-the-job target. "
            "This is the first thing an audit looks at, so it is worth keeping empty.",
        )
        return

    table = widgets.DataTable(
        section,
        (
            ("name", "Apprentice", 180),
            ("programme", "Programme", 200),
            ("employer", "Employer", 160),
            ("tutor", "Tutor", 140),
            ("elapsed", "Elapsed", 80, "e"),
            ("otj", "Off-the-job", 90, "e"),
        ),
        height=_ROWS,
    )
    table.populate(
        rows,
        lambda s: (
            s.full_name, s.programme_title, s.employer_name, s.tutor_name,
            widgets.percent(s.progress_percent), widgets.percent(s.otj_percent),
        ),
        identity=lambda s: s.apprentice.apprentice_id,
        tag=lambda s: s.apprentice.status,
        noun="apprentice",
    )
    _open(gui, section, "admin.apprentices", "Apprentices", "apprentice.view")


def _compliance_flags(gui, parent, data: dict[str, Any]) -> None:
    rows = data.get("compliance_flags") or []
    section = widgets.section(parent, "Compliance flags")
    if not rows:
        widgets.empty_state(
            section,
            "Every apprentice on the books is eligible with their paperwork signed. "
            "Nothing here is at risk of clawback.",
        )
        return

    table = widgets.DataTable(
        section,
        (
            ("name", "Apprentice", 180),
            ("employer", "Employer", 160),
            ("rag", "RAG", 70),
            ("missing", "Missing documents", 260),
            ("failed", "Failed checks", 220),
        ),
        height=_ROWS,
    )
    table.populate(
        rows,
        lambda r: (
            r.get("apprentice_name"), r.get("employer_name"), r.get("rag"),
            ", ".join(r.get("missing") or []), ", ".join(r.get("failed_checks") or []),
        ),
        identity=lambda r: r["apprentice_id"],
        tag=lambda r: r.get("rag"),
        noun="apprentice",
    )
    _open(gui, section, "admin.compliance", "Compliance", "compliance.view")


def _gateway_queue(gui, parent, data: dict[str, Any]) -> None:
    rows = data.get("gateway_queue") or []
    section = widgets.section(parent, "Gateway requests awaiting a decision")
    if not rows:
        widgets.empty_state(
            section,
            "No gateway requests are with the end-point assessment organisation. "
            "Requests appear here once a tutor submits one.",
        )
        return

    table = widgets.DataTable(
        section,
        (
            ("name", "Apprentice", 180),
            ("programme", "Programme", 200),
            ("employer", "Employer", 160),
            ("tutor", "Tutor", 140),
            ("gateway", "Gateway", 100),
            ("requested", "Requested", 110),
        ),
        height=_ROWS,
    )
    table.populate(
        rows,
        lambda r: (
            r.get("apprentice_name"), r.get("programme_title"), r.get("employer_name"),
            r.get("tutor_name"), r.get("gateway_status"), r.get("requested_at"),
        ),
        identity=lambda r: r["apprentice_id"],
        noun="request",
    )
    _open(gui, section, "admin.apprentices", "Apprentices", "apprentice.view")


def _caseloads(gui, parent, data: dict[str, Any]) -> None:
    rows = data.get("overloaded_caseloads") or []
    section = widgets.section(parent, "Caseloads over the warning threshold")
    if not rows:
        widgets.empty_state(
            section,
            f"No tutor is carrying {config.CASELOAD_WARNING_THRESHOLD} or more active "
            "apprentices. Caseload size is the best early warning of missed reviews.",
        )
        return

    table = widgets.DataTable(
        section,
        (
            ("name", "Tutor", 200),
            ("role", "Role", 140),
            ("active", "Active", 80, "e"),
            ("gateway", "At gateway", 90, "e"),
            ("overdue", "Reviews overdue", 120, "e"),
            ("behind", "Behind on OTJ", 110, "e"),
            ("rag", "RAG", 70),
        ),
        height=_ROWS,
    )
    table.populate(
        rows,
        lambda c: (
            c.name, c.staff.staff_role, c.active, c.at_gateway,
            c.reviews_overdue, c.otj_behind, c.rag_rating,
        ),
        identity=lambda c: c.staff.staff_id,
        tag=lambda c: c.rag_rating,
        noun="caseload",
    )
    _open(gui, section, "admin.staff", "Staff & Caseloads", "staff.view")


def _open(gui, parent, module: str, label: str, permission: str) -> None:
    """A way into the screen that can act on what the section shows."""
    if not gui.actor.can(permission):
        return
    widgets.button_bar(parent, [("Open →", lambda: gui.show(module, label))])
