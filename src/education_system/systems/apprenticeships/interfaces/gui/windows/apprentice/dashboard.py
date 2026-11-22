"""The apprentice's own dashboard.

One question, answered honestly: am I on track? Off-the-job hours are the
number an apprenticeship is judged on, so they lead — with the target,
the hours actually approved, and the weekly pace needed from here rather
than a percentage that flatters.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.workspace import reporting_service

logger = logging.getLogger(__name__)

UNLINKED = (
    "Your sign-in is not linked to an apprentice record yet, so there is nothing to "
    "show here. Ask your training provider's administrator to link your account."
)

# Where the "Open" buttons go: the module tail under the windows package,
# and the label the navigation sidebar uses for the same screen.
_SHORTCUTS: tuple[tuple[str, str, str], ...] = (
    ("Log off-the-job hours", "apprentice.off_the_job_hours", "Off-the-Job Hours"),
    ("My portfolio", "apprentice.portfolio", "Portfolio"),
    ("My reviews", "apprentice.reviews", "Progress Reviews"),
    ("Learning plan", "shared.learning_plan", "Learning Plan"),
    ("Gateway", "apprentice.gateway", "Gateway"),
    ("End-point assessment", "apprentice.epa", "End-Point Assessment"),
)


def render(gui: Any) -> None:
    """The apprentice's own progress, in the terms they are judged on."""
    frame = gui.clear()
    widgets.heading(
        frame,
        "My Apprenticeship",
        subtitle="Where you have got to, and what is waiting on you.",
    )
    ok, data = widgets.guard(lambda: reporting_service.apprentice_dashboard(gui.actor))
    if not ok:
        return
    if data.get("unlinked"):
        widgets.empty_state(frame, UNLINKED)
        return

    body = widgets.scrollable(frame)
    widgets.kpi_row(body, data.get("kpis") or [])
    _degree(body, data.get("academic_progress"), data.get("degree_link"),
            data.get("reconciliation_warning"))
    _off_the_job(body, data["hours"])
    _attendance(body, data.get("attendance"))
    _portfolio(body, data.get("portfolio"))
    _functional_skills(body, data.get("functional_skills") or [])
    _reviews(body, data.get("next_review"), data.get("open_targets") or [])
    _recent_hours(body, data.get("recent_hours") or [])
    _assessment(body, data.get("bookings") or [], data.get("results") or [])
    widgets.button_bar(
        body,
        [(f"{label} →", _opener(gui, module, nav_label))
         for label, module, nav_label in _SHORTCUTS],
    )


def _opener(gui: Any, module: str, label: str) -> Any:
    return lambda: gui.show(module, label)


def _degree(parent: Any, academic: dict[str, Any] | None, link: Any,
            warning: str | None) -> None:
    if link is None:
        return
    box = widgets.section(parent, "My degree apprenticeship")
    if warning:
        widgets.empty_state(box, f"Your provider is checking this record: {warning}.")
    if academic is None:
        widgets.empty_state(
            box, "Your university registration is linked. Academic progress is waiting "
                 "for the next university update.",
        )
        return
    widgets.field_grid(box, [
        ("Registered degree", academic.get("degree_program_name") or
         academic.get("degree_program_code") or "Linked degree"),
        ("Credits", f"{academic.get('credits_earned', 0):g} / "
         f"{academic.get('credits_required', 0):g}"),
        ("Modules completed", academic.get("modules_completed", 0)),
        ("Academic standing", academic.get("academic_standing") or "Not reported"),
        ("Degree outcome", academic.get("degree_outcome") or "Not awarded"),
        ("Registration", academic.get("registration_status") or "Not reported"),
    ], columns=3)


# ═════════════════════════════════════════════════════════════════════
# Panels
# ═════════════════════════════════════════════════════════════════════

def _off_the_job(parent: Any, hours: Any) -> None:
    box = widgets.section(parent, "Off-the-job training")
    if hours.target_hours <= 0:
        widgets.empty_state(
            box,
            "Your off-the-job target is worked out from your programme dates, and "
            "those are not set yet. Your tutor can put them right.",
        )
        return
    widgets.progress_row(
        box, "Approved hours", hours.percent_complete,
        detail=_pace(hours), rag=hours.rag_rating,
    )
    widgets.field_grid(box, [
        ("Approved so far", f"{hours.approved_hours:,.1f} hrs"),
        ("Your target", f"{hours.target_hours:,.1f} hrs"),
        ("Waiting for approval", f"{hours.pending_hours:,.1f} hrs"),
        ("Still to log", f"{hours.remaining_hours:,.1f} hrs"),
    ], columns=4)


def _pace(hours: Any) -> str:
    """The one honest line: where you are, and what it takes from here."""
    logged = f"{hours.approved_hours:,.0f} of {hours.target_hours:,.0f} hours"
    if hours.target_met:
        return f"{logged} — target met"
    weekly = f"{hours.weekly_hours_needed:,.1f} hrs/week needed"
    if hours.is_on_track:
        return f"{logged} — {weekly}, on track"
    return f"{logged} — {weekly}, {hours.hours_behind:,.1f} hrs behind today's pace"


def _attendance(parent: Any, attendance: Any) -> None:
    box = widgets.section(parent, "Attendance at training")
    if attendance is None or attendance.total == 0:
        widgets.empty_state(box, "No training session registers have been marked for you yet.")
        return
    attended = attendance.present + attendance.late
    countable = attended + attendance.absent
    widgets.progress_row(
        box, "Sessions attended", attendance.attendance_rate,
        detail=attendance.concern_reason
        or f"{attended} of {countable} sessions — excused absences are not counted",
        rag=attendance.rag or "Amber",
    )
    widgets.field_grid(box, [
        ("Present", attendance.present),
        ("Late", attendance.late),
        ("Punctuality", widgets.percent(attendance.punctuality_rate)),
        ("Unauthorised absences", attendance.unauthorised),
        ("Excused absences", attendance.authorised),
        ("Sickness", attendance.sickness),
    ], columns=3)


def _portfolio(parent: Any, portfolio: Any) -> None:
    box = widgets.section(parent, "Portfolio")
    if portfolio is None or not portfolio.total_ksbs:
        widgets.empty_state(
            box,
            "There are no knowledge, skills and behaviours to evidence yet — that "
            "starts once you are on a programme.",
        )
        return
    widgets.progress_row(
        box, "KSBs signed off as competent", portfolio.percent_competent,
        detail=f"{portfolio.competent_ksbs} of {portfolio.total_ksbs} — "
               f"{len(portfolio.gaps)} still to evidence",
        rag="Green" if portfolio.is_complete else "Amber",
    )


def _functional_skills(parent: Any, skills: list[Any]) -> None:
    box = widgets.section(parent, "English and maths")
    if not skills:
        widgets.empty_state(box, "Nothing has been recorded for English or maths yet.")
        return
    widgets.field_grid(box, [(skill.subject, _skill_line(skill)) for skill in skills])


def _skill_line(skill: Any) -> str:
    if skill.status == "Exempt":
        return f"Exempt — {skill.exemption_reason or 'reason not recorded'}"
    if skill.status == "Achieved":
        return f"Achieved {skill.level or ''}".strip()
    return skill.status


def _reviews(parent: Any, next_review: Any, targets: list[Any]) -> None:
    box = widgets.section(parent, "Your next review and open targets")
    if next_review is None:
        widgets.empty_state(box, "You have no review in the diary at the moment.")
    else:
        widgets.field_grid(box, [
            ("Next review", next_review.scheduled_date),
            ("Status", next_review.status),
            ("With", next_review.conductor_name or "your tutor"),
            ("Overdue", next_review.is_overdue),
        ], columns=4)

    if not targets:
        widgets.empty_state(box, "Nothing outstanding from your last review.")
        return
    table = widgets.DataTable(box, (
        ("description", "Target", 440),
        ("due", "Due", 110),
        ("ksbs", "KSBs", 140),
        ("status", "Status", 110),
    ), height=5)
    table.populate(
        targets,
        lambda t: (t.description, t.due_date, t.ksb_codes, t.status),
        identity=lambda t: t.target_id,
        tag=lambda t: "Red" if t.is_overdue else None,
        noun="open target",
    )


def _recent_hours(parent: Any, entries: list[Any]) -> None:
    box = widgets.section(parent, "Hours you logged recently")
    if not entries:
        widgets.empty_state(
            box, "You haven't logged any hours yet — start from the Off-the-Job Hours screen."
        )
        return
    table = widgets.DataTable(box, (
        ("date", "Date", 110),
        ("hours", "Hours", 80, "e"),
        ("activity", "Activity", 200),
        ("description", "What you did", 360),
        ("status", "Status", 110),
    ), height=6)
    table.populate(
        entries,
        lambda e: (e.activity_date, e.hours, e.activity_type, e.description, e.status),
        identity=lambda e: e.entry_id,
        tag=lambda e: _HOUR_TAGS.get(e.status),
        noun="entry",
    )


# Only approved hours count, so the log is coloured by whether an entry
# has actually landed rather than by how recent it is.
_HOUR_TAGS: dict[str, str] = {"Approved": "Green", "Submitted": "Amber", "Rejected": "Red"}


def _assessment(parent: Any, bookings: list[Any], results: list[Any]) -> None:
    box = widgets.section(parent, "End-point assessment")
    if not bookings and not results:
        widgets.empty_state(
            box,
            "Nothing booked yet. Your end-point assessment is arranged once you have "
            "passed through gateway.",
        )
        return

    if bookings:
        booked = widgets.DataTable(box, (
            ("method", "Method", 220),
            ("when", "When", 180),
            ("location", "Where", 200),
            ("assessor", "Assessor", 180),
            ("status", "Status", 120),
        ), height=4)
        booked.populate(
            bookings,
            lambda b: (
                b.get("method"),
                " ".join(filter(None, [b.get("scheduled_date"), b.get("scheduled_time")])),
                b.get("location"),
                b.get("assessor_name"),
                b.get("status"),
            ),
            identity=lambda b: b["booking_id"],
            noun="booking",
        )
    if results:
        graded = widgets.DataTable(box, (
            ("method", "Method", 220),
            ("grade", "Grade", 120),
            ("assessed", "Assessed", 120),
            ("attempt", "Attempt", 90, "e"),
        ), height=4)
        graded.populate(
            results,
            lambda r: (r.method, r.grade, r.assessed_date, r.attempt),
            identity=lambda r: r.result_id,
            tag=lambda r: "Green" if r.is_pass else "Red",
            noun="result",
        )
