"""Dashboards and reports.

The dashboard is one command for five very different screens. The
service already branches on role and hands back a plain dict, so all
this module does is decide which tables are worth printing for each —
the numbers themselves are identical to the ones the GUI shows.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    compliance_service,
    reporting_service,
)
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

# What an unresolved login means, per role. Each one is a
# half-provisioned account rather than an error, so it is explained
# rather than raised.
_UNLINKED: dict[str, str] = {
    config.APPRENTICE: "Your login is not linked to an apprentice record yet.",
    config.EMPLOYER: "Your login is not linked to an employer yet.",
    config.STAFF: "Your login is not linked to a staff record, so you have no caseload.",
}


def dashboard(actor: Actor) -> None:
    data = reporting_service.dashboard(actor)
    prompts.title(str(data.get("title") or "Apprenticeships"))

    if data.get("unavailable"):
        prompts.note("No dashboard is defined for your role.")
        prompts.pause()
        return
    if data.get("unlinked"):
        prompts.note(_UNLINKED.get(actor.role, "Your login is not linked to a record yet."))
        prompts.note("Ask your provider to link it, then sign in again.")
        prompts.pause()
        return

    prompts.details(data.get("kpis") or [])
    renderer = _RENDERERS.get(str(data.get("role")))
    if renderer is not None:
        renderer(data)
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Per-role detail
# ═════════════════════════════════════════════════════════════════════

def _admin_dashboard(data: dict[str, Any]) -> None:
    money = data.get("money") or {}
    prompts.details([
        ("Contracted value", prompts.money(data.get("contracted_value"))),
        ("Claimed", prompts.money(money.get("claimed"))),
        ("Paid", prompts.money(money.get("paid"))),
        ("Withheld", prompts.money(money.get("withheld"))),
        ("Completion rate", _percent(data.get("completion_rate"))),
        ("Employer satisfaction", _score(data.get("satisfaction"))),
        ("Reviews overdue", data.get("reviews_overdue")),
        ("Reviews awaiting signature", data.get("reviews_awaiting_signature")),
        ("Hours awaiting approval", data.get("otj_pending")),
        ("Evidence awaiting assessment", data.get("evidence_pending")),
    ])

    _counts_table("By status", (data.get("by_status") or {}).items())
    _counts_table("By programme", data.get("by_programme") or [])
    _counts_table("By employer", data.get("by_employer") or [])

    prompts.note("\nBehind on off-the-job hours:")
    apprentices.table(data.get("behind_on_otj") or [])

    prompts.note("\nCompliance flags:")
    prompts.table(
        (("Apprentice", 24), ("Status", 16), ("RAG", 6), ("Outstanding", 40)),
        data.get("compliance_flags") or [],
        lambda r: (
            r.get("apprentice_name"), r.get("status"), r.get("rag"),
            "; ".join([*r.get("failed_checks", []), *r.get("missing", [])]),
        ),
        noun="flag",
        empty="nothing flagged",
    )

    prompts.note("\nCaseloads over the warning threshold:")
    prompts.table(
        (("Tutor", 24), ("Active", -7), ("Total", -7), ("Overdue reviews", -15), ("RAG", 6)),
        data.get("overloaded_caseloads") or [],
        lambda c: (c.name, c.active, c.total, c.reviews_overdue, c.rag_rating),
        noun="caseload",
        empty="every caseload is within the threshold",
    )

    prompts.note("\nGateway requests awaiting a decision:")
    _gateway_table(data.get("gateway_queue") or [])


def _staff_dashboard(data: dict[str, Any]) -> None:
    prompts.note("\nMy caseload:")
    apprentices.table(data.get("apprentices") or [])

    prompts.note("\nReviews overdue:")
    _review_table(data.get("reviews_overdue") or [])

    prompts.note("\nReviews in the next fortnight:")
    _review_table(data.get("reviews_upcoming") or [])

    prompts.note("\nEvidence to assess:")
    prompts.table(
        (("Title", 34), ("Type", 22), ("Submitted", 20)),
        data.get("evidence_queue") or [],
        lambda e: (e.title, e.evidence_type, e.submitted_at),
        noun="item",
        empty="nothing waiting",
    )

    prompts.note("\nHours to approve:")
    prompts.table(
        (("Date", 12), ("Hours", -7), ("Activity", 26), ("Description", 32)),
        data.get("otj_queue") or [],
        lambda o: (o.activity_date, o.hours, o.activity_type, o.description),
        noun="entry",
        empty="nothing waiting",
    )

    prompts.note("\nUpcoming sessions:")
    _session_table(data.get("sessions_upcoming") or [])


def _apprentice_dashboard(data: dict[str, Any]) -> None:
    hours = data.get("hours")
    if hours is not None:
        prompts.note("")
        prompts.note(f"Off-the-job  {prompts.bar(hours.percent_complete)}  "
                     f"{hours.approved_hours:,.1f} / {hours.target_hours:,.1f} hrs")
        prompts.note(f"Expected     {prompts.bar(hours.expected_percent)}  "
                     f"pace to date ({hours.rag_rating})")
        prompts.details([
            ("Awaiting approval", f"{hours.pending_hours:,.1f} hrs"),
            ("Still in draft", f"{hours.draft_hours:,.1f} hrs"),
            ("Remaining", f"{hours.remaining_hours:,.1f} hrs"),
            ("Needed per week", f"{hours.weekly_hours_needed:,.1f} hrs"),
        ])

    portfolio = data.get("portfolio")
    if portfolio is not None:
        prompts.note("")
        prompts.note(f"Portfolio    {prompts.bar(portfolio.percent_competent)}  "
                     f"{portfolio.competent_ksbs} / {portfolio.total_ksbs} KSBs competent")

    prompts.note("\nKSBs still to evidence:")
    prompts.table(
        (("KSB", 6), ("Type", 12), ("Coverage", 12), ("Evidence", -9), ("Statement", 38)),
        data.get("gaps") or [],
        lambda c: (c.ksb.code, c.ksb.ksb_type, c.coverage, c.evidence_count, c.ksb.description),
        noun="gap",
        empty="every KSB is covered",
    )

    prompts.note("\nEnglish and Maths:")
    prompts.table(
        (("Subject", 12), ("Status", 14), ("Level", 12), ("Achieved", 12)),
        data.get("functional_skills") or [],
        lambda s: (s.subject, s.status, s.level, s.achieved_date),
        noun="subject",
    )

    next_review = data.get("next_review")
    if next_review is not None:
        prompts.note(f"\nNext review: {next_review.scheduled_date} ({next_review.status})")

    prompts.note("\nOpen targets:")
    prompts.table(
        (("Due", 12), ("Target", 52), ("KSBs", 16)),
        data.get("open_targets") or [],
        lambda t: (t.due_date, t.description, t.ksb_codes),
        noun="target",
        empty="no open targets",
    )

    prompts.note("\nMy recent hours:")
    prompts.table(
        (("Date", 12), ("Hours", -7), ("Activity", 26), ("Status", 12)),
        data.get("recent_hours") or [],
        lambda o: (o.activity_date, o.hours, o.activity_type, o.status),
        noun="entry",
    )

    prompts.note("\nUpcoming sessions:")
    _session_table(data.get("sessions_upcoming") or [])


def _employer_dashboard(data: dict[str, Any]) -> None:
    funding = data.get("funding") or {}
    levy = data.get("levy")
    prompts.details([
        ("Scheduled", prompts.money(funding.get("scheduled"))),
        ("Paid", prompts.money(funding.get("paid"))),
        ("Overdue", prompts.money(funding.get("overdue"))),
        ("Levy payer", levy.is_levy_payer if levy else prompts.EMPTY),
        ("Annual levy", prompts.money(levy.levy_due) if levy else prompts.EMPTY),
    ])

    prompts.note("\nMy apprentices:")
    apprentices.table(data.get("apprentices") or [])

    prompts.note("\nHours to approve:")
    prompts.table(
        (("Date", 12), ("Hours", -7), ("Activity", 26), ("Description", 32)),
        data.get("otj_queue") or [],
        lambda o: (o.activity_date, o.hours, o.activity_type, o.description),
        noun="entry",
        empty="nothing waiting",
    )

    prompts.note("\nReviews to sign:")
    _review_table(data.get("reviews_to_sign") or [])

    prompts.note("\nWorkplaces:")
    prompts.table(
        (("Site", 28), ("Postcode", 10), ("H&S checked", 13), ("H&S expires", 13), ("Usable", 8)),
        data.get("workplaces") or [],
        lambda w: (w.name, w.postcode, w.hs_checked_date, w.hs_expiry_date,
                   w.can_host_apprentices),
        noun="workplace",
    )


def _assessor_dashboard(data: dict[str, Any]) -> None:
    prompts.note("\nMy diary (next fortnight):")
    _booking_table(data.get("diary") or [])

    prompts.note("\nMy open bookings:")
    _booking_table(data.get("my_bookings") or [])

    prompts.note("\nUnassigned bookings:")
    _booking_table(data.get("unassigned") or [])

    prompts.note("\nGateway requests awaiting a decision:")
    _gateway_table(data.get("gateway_requests") or [])

    prompts.note("\nResits requested:")
    prompts.table(
        (("Requested", 20), ("Type", 10), ("Reason", 40), ("Status", 12)),
        data.get("resits") or [],
        lambda r: (r.requested_at, r.resit_type, r.reason, r.status),
        noun="resit",
    )

    prompts.note("\nRecent results:")
    prompts.table(
        (("Assessed", 12), ("Method", 26), ("Grade", 12), ("Attempt", -8)),
        data.get("recent_results") or [],
        lambda r: (r.assessed_date, r.method, r.grade, r.attempt),
        noun="result",
    )


_RENDERERS: dict[str, Callable[[dict[str, Any]], None]] = {
    config.ADMIN: _admin_dashboard,
    config.STAFF: _staff_dashboard,
    config.APPRENTICE: _apprentice_dashboard,
    config.EMPLOYER: _employer_dashboard,
    config.END_POINT_ASSESSOR: _assessor_dashboard,
}


# ═════════════════════════════════════════════════════════════════════
# Reports
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = []
    if actor.can("report.view"):
        entries += [
            ("Cohort statistics", partial(_cohort, actor)),
            ("Programme report", partial(_programmes, actor)),
            ("Employer report", partial(_employers, actor)),
        ]
    if actor.is_provider and actor.can("compliance.view"):
        entries.append(("Funding evidence pack", partial(_evidence_pack, actor)))
    prompts.run_menu("Reports", entries)


def _cohort(actor: Actor) -> None:
    stats = apprentice_service.cohort_statistics(actor)
    prompts.title("Cohort statistics")
    prompts.details([
        ("Total", stats["total"]),
        ("Active", stats["active"]),
        ("At gateway", stats["at_gateway"]),
        ("Completed", stats["completed"]),
        ("Withdrawn", stats["withdrawn"]),
        ("Behind on off-the-job", stats["behind_on_otj"]),
    ])
    _counts_table("By status", stats["by_status"].items())
    _counts_table("By programme", stats["by_programme"])
    _counts_table("By employer", stats["by_employer"])

    prompts.note("\nBehind on off-the-job hours:")
    apprentices.table(stats["behind_list"])
    prompts.pause()


def _programmes(actor: Actor) -> None:
    rows = reporting_service.programme_report(actor)
    prompts.title("Programme report")
    prompts.table(
        (("Reference", 10), ("Title", 28), ("Lvl", -4), ("Active", -7), ("Total", -6),
         ("Done", -5), ("Left", -5), ("Behind", -7), ("KSBs", -5), ("Achieved %", -11)),
        rows,
        lambda r: (
            r["programme"].reference, r["programme"].title, r["programme"].level,
            r["active"], r["total"], r["completed"], r["withdrawn"], r["behind"],
            r["ksb_count"], _percent(r["achievement_rate"]),
        ),
        noun="programme",
    )
    prompts.pause()


def _employers(actor: Actor) -> None:
    rows = reporting_service.employer_report(actor)
    prompts.title("Employer report")
    prompts.table(
        (("Employer", 30), ("Active", -7), ("Total", -6), ("Done", -5), ("Left", -5),
         ("Retention %", -12), ("To approve", -11), ("Satisfaction", -13)),
        rows,
        lambda r: (
            r["employer"].name, r["active"], r["total"], r["completed"], r["withdrawn"],
            _percent(r["retention"]), r["pending_approvals"], _score(r["satisfaction"]),
        ),
        noun="employer",
    )
    prompts.pause()


def _evidence_pack(actor: Actor) -> None:
    summary = apprentices.pick(actor, heading="Apprentice for the evidence pack")
    pack = compliance_service.evidence_pack(actor, summary.apprentice.apprentice_id)

    person = pack["apprentice"]
    prompts.title(f"Funding evidence pack — {person['name']}")
    prompts.note(f"Generated {pack['generated_at']} by {pack['generated_by']}")
    prompts.details([
        ("ULN", person["uln"]),
        ("Date of birth", person["date_of_birth"]),
        ("Status", person["status"]),
        ("Programme", f"{person['programme_reference'] or ''} {person['programme'] or ''}".strip()),
        ("Level", person["level"]),
        ("Employer", person["employer"]),
        ("Tutor", person["tutor"]),
        ("Funding model", person["funding_model"]),
        ("Weekly hours", person["weekly_hours"]),
        ("Started", person["start_date"]),
        ("Planned end", person["planned_end_date"]),
        ("Actual end", person["actual_end_date"]),
        ("Retention expiry", pack["retention_expiry"]),
    ])

    compliance = pack["compliance"]
    prompts.details([
        ("Compliance RAG", compliance["rag"]),
        ("Eligible", compliance["is_eligible"]),
        ("Audit ready", compliance["is_audit_ready"]),
        ("Eligibility passed", f"{compliance['eligibility_passed']}/"
                               f"{compliance['eligibility_total']}"),
        ("Failed checks", "; ".join(compliance["failed_checks"]) or prompts.EMPTY),
        ("Documents signed", f"{compliance['documents_signed']}/{compliance['documents_total']}"),
        ("Missing documents", "; ".join(compliance["missing_documents"]) or prompts.EMPTY),
        ("Missing pre-start", "; ".join(compliance["missing_pre_start"]) or prompts.EMPTY),
        ("Expired documents", "; ".join(compliance["expired_documents"]) or prompts.EMPTY),
    ])

    hours = pack["off_the_job"]
    prompts.details([
        ("Target hours", hours["target_hours"]),
        ("Approved hours", hours["approved_hours"]),
        ("Pending hours", hours["pending_hours"]),
        ("Shortfall", hours["shortfall_hours"]),
        ("Target met", hours["target_met"]),
        ("Entries", hours["entry_count"]),
        ("Reviews signed", pack["reviews"]["signed"]),
        ("Reviews outstanding", pack["reviews"]["outstanding"]),
        ("Gateway", pack["gateway"]["status"]),
        ("Gateway decided", pack["gateway"]["decided_at"]),
        ("Gateway decided by", pack["gateway"]["decided_by"]),
    ])

    prompts.note("\nFunctional skills:")
    prompts.table(
        (("Subject", 12), ("Status", 14), ("Level", 12), ("Achieved", 12), ("Satisfied", 10)),
        pack["functional_skills"],
        lambda s: (s["subject"], s["status"], s["level"], s["achieved_date"], s["is_satisfied"]),
        noun="subject",
    )

    prompts.note("\nEnd-point assessment:")
    prompts.table(
        (("Method", 28), ("Grade", 12), ("Assessed", 12), ("Attempt", -8), ("Pass", 6)),
        pack["epa"]["results"],
        lambda r: (r["method"], r["grade"], r["assessed_date"], r["attempt"], r["is_pass"]),
        noun="result",
        empty="no results recorded",
    )
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Shared tables
# ═════════════════════════════════════════════════════════════════════

def _counts_table(heading: str, pairs: Any) -> None:
    rows = list(pairs)
    prompts.note(f"\n{heading}:")
    prompts.table(
        (("", 34), ("Count", -7)),
        rows,
        lambda pair: (pair[0], pair[1]),
        noun="row",
    )


def _gateway_table(rows: list[dict[str, Any]]) -> None:
    prompts.table(
        (("Apprentice", 24), ("Programme", 24), ("Employer", 20),
         ("Gateway", 12), ("Requested", 12)),
        rows,
        lambda r: (r.get("apprentice_name"), r.get("programme_title"),
                   r.get("employer_name"), r.get("gateway_status"), r.get("requested_at")),
        noun="request",
        empty="nothing waiting",
    )


def _booking_table(rows: list[dict[str, Any]]) -> None:
    prompts.table(
        (("Apprentice", 22), ("Method", 24), ("When", 18), ("Location", 16), ("Status", 12)),
        rows,
        lambda r: (
            r.get("apprentice_name"), r.get("method"),
            f"{r.get('scheduled_date') or prompts.EMPTY} {r.get('scheduled_time') or ''}".strip(),
            r.get("location"), r.get("status"),
        ),
        noun="booking",
    )


def _review_table(rows: list[Any]) -> None:
    prompts.table(
        (("Apprentice", 22), ("Scheduled", 12), ("Held", 12), ("Status", 20),
         ("Rating", 8), ("Unsigned", 26)),
        rows,
        lambda r: (r.apprentice_name, r.scheduled_date, r.held_date, r.status,
                   r.progress_rating, ", ".join(r.missing_signatures)),
        noun="review",
        empty="nothing waiting",
    )


def _session_table(rows: list[Any]) -> None:
    prompts.table(
        (("When", 20), ("Title", 28), ("Mode", 16), ("Location", 16),
         ("OTJ hrs", -8), ("Booked", -7)),
        rows,
        lambda s: (s.when, s.title, s.delivery_mode, s.location, s.otj_hours,
                   s.attendee_count),
        noun="session",
    )


def _percent(value: float | None) -> str:
    return prompts.EMPTY if value is None else f"{value:.1f}%"


def _score(value: float | None) -> str:
    return prompts.EMPTY if value is None else f"{value:.2f} / 5"
