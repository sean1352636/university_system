"""The tutor's dashboard: their caseload and every queue waiting on them."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.workspace import reporting_service

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your login is not linked to a staff record, so there is no caseload behind it. "
    "Ask an administrator to link your account to your staff profile — until then "
    "these queues would read as empty rather than as unknown."
)


def render(gui) -> None:
    """The work waiting on this tutor, grouped by what it is waiting for."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "My Caseload",
        subtitle="Your apprentices and everything sitting with you this fortnight.",
    )
    if gui.actor.staff_id is None:
        widgets.empty_state(frame, UNLINKED)
        return

    data = reporting_service.staff_dashboard(gui.actor)
    if data.get("unlinked"):
        widgets.empty_state(frame, UNLINKED)
        return

    widgets.kpi_row(frame, data["kpis"])
    body = widgets.scrollable(frame)

    # The queue rows carry an apprentice id but no name, so the caseload
    # this dashboard has already loaded doubles as the lookup table. An
    # id that is not on it belongs to someone no longer active, hence the
    # fallback rather than a second query per row.
    names = {s.apprentice.apprentice_id: s.full_name for s in data["apprentices"]}

    def named(apprentice_id: int) -> str:
        return names.get(apprentice_id, f"Apprentice {apprentice_id}")

    _section(
        gui, body, "Behind on off-the-job hours", data["behind_on_otj"],
        columns=(
            ("name", "Apprentice", 200),
            ("programme", "Programme", 200),
            ("employer", "Employer", 160),
            ("logged", "Hours logged", 100, "e"),
            ("otj", "Off-the-job", 90, "e"),
            ("elapsed", "Time elapsed", 90, "e"),
        ),
        to_values=lambda s: (
            s.full_name, s.programme_title, s.employer_name,
            s.otj_hours_logged, widgets.percent(s.otj_percent),
            widgets.percent(s.progress_percent),
        ),
        identity=lambda s: s.apprentice.apprentice_id,
        tag=lambda s: "Red",
        noun="apprentice",
        empty="Nobody on your caseload is behind on their off-the-job hours.",
        opens=("staff.caseload", "My Caseload"),
    )

    _section(
        gui, body, "Attendance concerns", data.get("attendance_concerns") or [],
        columns=(
            ("name", "Apprentice", 200),
            ("employer", "Employer", 160),
            ("rate", "Attendance", 90, "e"),
            ("unauthorised", "Unauthorised", 100, "e"),
            ("sickness", "Sickness", 80, "e"),
            ("why", "Why flagged", 260),
        ),
        to_values=lambda pair: (
            pair[0].full_name, pair[0].employer_name,
            widgets.percent(pair[1].attendance_rate), pair[1].unauthorised,
            pair[1].sickness, pair[1].concern_reason,
        ),
        identity=lambda pair: pair[0].apprentice.apprentice_id,
        tag=lambda pair: "Red" if pair[1].rag == "Red" else "Amber",
        noun="apprentice",
        empty="Nobody on your caseload has an attendance problem.",
        opens=("staff.training", "Training Sessions"),
    )

    _section(
        gui, body, "Reviews overdue", data["reviews_overdue"],
        columns=(
            ("name", "Apprentice", 200),
            ("scheduled", "Scheduled", 110),
            ("status", "Status", 140),
            ("targets", "Open targets", 100, "e"),
        ),
        to_values=lambda r: (
            r.apprentice_name, r.scheduled_date, r.status, len(r.open_targets),
        ),
        identity=lambda r: r.review_id,
        tag=lambda r: "Red",
        noun="review",
        empty="No reviews are past their scheduled date.",
        opens=("staff.reviews", "Progress Reviews"),
    )

    _section(
        gui, body, "Reviews in the next fortnight", data["reviews_upcoming"],
        columns=(
            ("name", "Apprentice", 200),
            ("scheduled", "Scheduled", 110),
            ("status", "Status", 140),
            ("conductor", "Conducted by", 160),
        ),
        to_values=lambda r: (
            r.apprentice_name, r.scheduled_date, r.status, r.conductor_name,
        ),
        identity=lambda r: r.review_id,
        noun="review",
        empty="Nothing in the review diary for the next fortnight.",
        opens=("staff.reviews", "Progress Reviews"),
    )

    _section(
        gui, body, "Evidence to assess", data["evidence_queue"],
        columns=(
            ("name", "Apprentice", 200),
            ("title", "Evidence", 240),
            ("type", "Type", 150),
            ("ksbs", "KSBs", 120),
            ("submitted", "Submitted", 150),
        ),
        to_values=lambda e: (
            named(e.apprentice_id), e.title, e.evidence_type,
            ", ".join(e.ksb_codes), e.submitted_at,
        ),
        identity=lambda e: e.evidence_id,
        noun="item",
        empty="No submitted evidence is waiting on your judgement.",
        opens=("staff.portfolios", "Portfolios"),
    )

    _section(
        gui, body, "Off-the-job hours to approve", data["otj_queue"],
        columns=(
            ("name", "Apprentice", 200),
            ("date", "Activity date", 110),
            ("hours", "Hours", 70, "e"),
            ("type", "Activity", 180),
            ("description", "Description", 260),
        ),
        to_values=lambda e: (
            named(e.apprentice_id), e.activity_date, e.hours,
            e.activity_type, e.description,
        ),
        identity=lambda e: e.entry_id,
        noun="entry",
        empty="No hours are waiting for your sign-off.",
        opens=("staff.assessments", "Off-the-Job Approvals"),
    )

    _section(
        gui, body, "Gateway", data["gateway_queue"],
        columns=(
            ("name", "Apprentice", 200),
            ("programme", "Programme", 220),
            ("gateway", "Gateway", 130),
            ("requested", "Requested", 110),
        ),
        to_values=lambda r: (
            r["apprentice_name"], r["programme_title"],
            r["gateway_status"], r["requested_at"],
        ),
        identity=lambda r: r["apprentice_id"],
        noun="apprentice",
        empty="Nobody on your caseload is at or approaching gateway.",
        opens=("staff.gateway_checks", "Gateway Checks"),
    )

    _section(
        gui, body, "Sessions you are delivering", data["sessions_upcoming"],
        columns=(
            ("when", "When", 190),
            ("title", "Session", 240),
            ("programme", "Programme", 200),
            ("location", "Location", 160),
            ("attendees", "Marked", 80, "e"),
        ),
        to_values=lambda s: (
            s.when, s.title, s.programme_title, s.location, s.attendee_count,
        ),
        identity=lambda s: s.session_id,
        noun="session",
        empty="Nothing in your delivery diary.",
        opens=("staff.training", "Training Sessions"),
    )


def _section(
    gui,
    parent,
    title: str,
    rows: Sequence[Any],
    *,
    columns: Sequence[tuple],
    to_values: Callable[[Any], Sequence[Any]],
    identity: Callable[[Any], Any],
    empty: str,
    opens: tuple[str, str],
    tag: Callable[[Any], str | None] | None = None,
    noun: str = "row",
) -> None:
    """One dashboard block: a short table and the screen that owns it."""
    box = widgets.section(parent, title)
    if rows:
        table = widgets.DataTable(box, columns, height=min(6, len(rows)))
        table.populate(rows, to_values, identity=identity, tag=tag, noun=noun)
    else:
        widgets.empty_state(box, empty)
    module, label = opens
    widgets.button_bar(box, [(f"Open {label} →", lambda: gui.show(module, label))])
