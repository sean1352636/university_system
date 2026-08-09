"""Dashboards and reports, one shape per role.

Each role opens onto a different question. An admin asks "where is the
portfolio drifting?"; a tutor asks "who on my caseload needs me this
week?"; an apprentice asks "am I on track?"; an employer asks "what am I
being asked to sign?"; an assessor asks "what am I grading, and when?".

Building those here rather than in the windows means the GUI dashboard
and the CLI dashboard show the same numbers, and the scoping rules are
applied once. Every builder returns a plain dict of primitives and
domain objects, so an interface can render it without knowing anything
about the database.
"""

from __future__ import annotations

import csv
import logging
from datetime import date, timedelta
from typing import Any

from education_system import paths
from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.training import off_the_job_hours as otj
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    employer_repository,
    epa_repository,
    funding_repository,
    portfolio_repository,
    programme_repository,
    review_repository,
    staff_repository,
    training_repository,
)
from education_system.systems.apprenticeships.services.access import Actor, require

logger = logging.getLogger(__name__)

# How far ahead "upcoming" reaches on every dashboard. A fortnight is
# the planning horizon a tutor or assessor actually works to.
UPCOMING_DAYS = 14


def dashboard(actor: Actor) -> dict[str, Any]:
    """The dashboard for whoever is signed in."""
    builders = {
        config.ADMIN: admin_dashboard,
        config.STAFF: staff_dashboard,
        config.APPRENTICE: apprentice_dashboard,
        config.EMPLOYER: employer_dashboard,
        config.END_POINT_ASSESSOR: assessor_dashboard,
    }
    builder = builders.get(actor.role)
    if builder is None:
        return {"role": actor.role, "title": "Apprenticeships", "unavailable": True}
    return builder(actor)


# ═════════════════════════════════════════════════════════════════════
# Admin
# ═════════════════════════════════════════════════════════════════════

def admin_dashboard(actor: Actor) -> dict[str, Any]:
    """Provider-wide health: cohort, delivery, money, compliance."""
    require(actor, "report.view")
    summaries = apprentice_repository.list_summaries()
    active = [s for s in summaries if s.apprentice.is_active]
    behind = [s for s in active if s.is_behind]

    money = funding_repository.totals()
    caseloads = staff_repository.list_caseloads()
    overloaded = [c for c in caseloads if c.is_over_threshold]
    flagged = compliance_repository.flagged_apprentices()

    return {
        "role": config.ADMIN,
        "title": "Provider Dashboard",
        "kpis": [
            ("Active apprentices", len(active)),
            ("At gateway", sum(1 for s in active if s.apprentice.status == "Gateway")),
            ("In EPA", sum(1 for s in active if s.apprentice.status == "EPA")),
            ("Behind on off-the-job", len(behind)),
            ("Compliance flags", len(flagged)),
            ("Overdue payments",
             f"{config.CURRENCY_SYMBOL}{money['overdue']:,.0f}"),
        ],
        "by_status": apprentice_repository.count_by_status(),
        "by_programme": apprentice_repository.count_by_programme(),
        "by_employer": apprentice_repository.count_by_employer(),
        "behind_on_otj": behind[:15],
        "compliance_flags": flagged[:15],
        "overloaded_caseloads": overloaded,
        "money": money,
        "contracted_value": funding_repository.contracted_value(),
        "gateway_queue": epa_repository.list_gateway_queue(status="Requested"),
        "reviews_overdue": review_repository.count_overdue(),
        "reviews_awaiting_signature": review_repository.count_awaiting_signature(),
        "otj_pending": training_repository.pending_count(),
        "evidence_pending": portfolio_repository.pending_assessment_count(),
        "completion_rate": _completion_rate(summaries),
        "satisfaction": review_repository.average_satisfaction(),
    }


def programme_report(actor: Actor) -> list[dict[str, Any]]:
    """Per-programme delivery figures, for the admin reports screen."""
    require(actor, "report.view")
    rows = []
    for programme in programme_repository.list_all():
        summaries = apprentice_repository.list_summaries(programme_id=programme.programme_id)
        active = [s for s in summaries if s.apprentice.is_active]
        completed = [s for s in summaries if s.apprentice.status == "Completed"]
        withdrawn = [s for s in summaries if s.apprentice.status == "Withdrawn"]
        finished = len(completed) + len(withdrawn)
        rows.append({
            "programme": programme,
            "total": len(summaries),
            "active": len(active),
            "completed": len(completed),
            "withdrawn": len(withdrawn),
            "behind": sum(1 for s in active if s.is_behind),
            "ksb_count": programme_repository.count_ksbs(programme.programme_id),
            # None rather than 0% while nobody has finished — a new
            # programme showing zero achievement would be read as failure.
            "achievement_rate": (
                round(len(completed) / finished * 100, 1) if finished else None
            ),
        })
    rows.sort(key=lambda r: r["active"], reverse=True)
    return rows


def employer_report(actor: Actor) -> list[dict[str, Any]]:
    """Per-employer figures, for the admin reports screen."""
    require(actor, "report.view")
    rows = []
    for summary in employer_repository.list_summaries():
        rows.append({
            "employer": summary.employer,
            "active": summary.active_apprentices,
            "total": summary.apprentice_count,
            "completed": summary.completed_apprentices,
            "withdrawn": summary.withdrawn_apprentices,
            "retention": summary.retention_rate,
            "pending_approvals": summary.pending_otj_approvals,
            "satisfaction": review_repository.average_satisfaction(
                employer_id=summary.employer.employer_id
            ),
        })
    rows.sort(key=lambda r: r["active"], reverse=True)
    return rows


# ═════════════════════════════════════════════════════════════════════
# Export
# ═════════════════════════════════════════════════════════════════════

# What each export contains: a header row and a function turning the
# report rows into cells. Keyed rather than branched so the CLI and the
# GUI can both offer the list without restating it.
EXPORTS: dict[str, str] = {
    "cohort": "Every apprentice in scope, with progress and status",
    "programmes": "Per-programme delivery and achievement",
    "employers": "Per-employer retention, approvals and satisfaction",
    "funding": "Agreed prices, contribution splits and what has been paid",
}


def export_csv(actor: Actor, kind: str, *, as_of: str | None = None) -> Any:
    """Write one report to a CSV under the exports directory.

    Returns the path written. The file is named for the report and the
    day rather than being overwritten, because these get emailed to a
    funding auditor and "which run was this?" has to be answerable from
    the filename alone.
    """
    require(actor, "report.view")
    if kind not in EXPORTS:
        from education_system.systems.apprenticeships.domain.apprentices.models import (
            ValidationError,
        )

        raise ValidationError(f"Export must be one of: {', '.join(EXPORTS)}")

    header, rows = _export_rows(actor, kind)
    stamp = as_of or date.today().isoformat()
    paths.ensure_apprenticeships_directories()
    target = paths.APPRENTICESHIPS_EXPORTS_DIR / f"{kind}-{stamp}.csv"

    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)

    compliance_repository.record(
        action="export", entity="report", entity_id=kind,
        actor=actor.username, actor_role=actor.role,
        detail=f"{len(rows)} row(s) to {target.name}",
    )
    logger.info(
        "Exported %s report (%s rows) to %s for %s", kind, len(rows), target, actor.username
    )
    return target


def _export_rows(actor: Actor, kind: str) -> tuple[list[str], list[list[Any]]]:
    """The header and body for one export.

    Reads through the same services the screens do, so an employer
    exporting the funding report gets their own apprentices and nobody
    else's — the scope is not re-derived here.
    """
    if kind == "cohort":
        from education_system.systems.apprenticeships.services import apprentice_service

        header = [
            "Apprentice", "ULN", "Programme", "Level", "Employer", "Tutor", "Status",
            "Started", "Planned end", "Off-the-job %", "KSB %", "Elapsed %",
            "Behind", "Gateway",
        ]
        return header, [
            [s.full_name, s.apprentice.uln, s.programme_title, s.programme_level,
             s.employer_name, s.tutor_name, s.apprentice.status, s.apprentice.start_date,
             s.apprentice.planned_end_date, s.otj_percent, s.ksb_percent,
             s.progress_percent, s.is_behind, s.gateway_status]
            for s in apprentice_service.list_apprentices(actor)
        ]

    if kind == "programmes":
        header = [
            "Reference", "Title", "Level", "Total", "Active", "Completed",
            "Withdrawn", "Behind", "KSBs", "Achievement %",
        ]
        return header, [
            [r["programme"].reference, r["programme"].title, r["programme"].level,
             r["total"], r["active"], r["completed"], r["withdrawn"], r["behind"],
             r["ksb_count"], r["achievement_rate"]]
            for r in programme_report(actor)
        ]

    if kind == "employers":
        header = [
            "Employer", "Active", "Total", "Completed", "Withdrawn",
            "Retention %", "Approvals waiting", "Satisfaction",
        ]
        return header, [
            [r["employer"].name, r["active"], r["total"], r["completed"],
             r["withdrawn"], r["retention"], r["pending_approvals"], r["satisfaction"]]
            for r in employer_report(actor)
        ]

    from education_system.systems.apprenticeships.services import funding_service

    header = [
        "Apprentice", "Status", "Employer", "Programme", "Model", "Band",
        "Negotiated price", "Employer contribution", "Government contribution",
        "Additional payments", "Paid to date",
    ]
    return header, [
        [r["apprentice_name"], r["apprentice_status"], r["employer_name"],
         r["programme_title"], r["funding_model"], r["band"], r["negotiated_price"],
         r["employer_contribution"], r["government_contribution"],
         r["additional_payments"], r["paid_to_date"]]
        for r in funding_service.list_funding(actor)
    ]


# ═════════════════════════════════════════════════════════════════════
# Staff
# ═════════════════════════════════════════════════════════════════════

def staff_dashboard(actor: Actor) -> dict[str, Any]:
    """A tutor's caseload and the work waiting on them."""
    require(actor, "apprentice.view")
    caseload = (
        staff_repository.build_caseload(actor.staff_id, with_members=True)
        if actor.staff_id is not None
        else None
    )
    scope = {"tutor_id": actor.staff_id} if actor.staff_id is not None else {"tutor_id": -1}
    summaries = apprentice_repository.list_summaries(**scope, active_only=True)
    behind = [s for s in summaries if s.is_behind]

    return {
        "role": config.STAFF,
        "title": "My Caseload",
        "unlinked": actor.staff_id is None,
        "caseload": caseload,
        "kpis": [
            ("Caseload", len(summaries)),
            ("Behind on off-the-job", len(behind)),
            ("Reviews overdue", review_repository.count_overdue(**scope)),
            ("Evidence to assess",
             portfolio_repository.pending_assessment_count(tutor_id=actor.staff_id)),
            ("Hours to approve", training_repository.pending_count(tutor_id=actor.staff_id)),
            ("At gateway",
             sum(1 for s in summaries if s.apprentice.status == "Gateway")),
        ],
        "apprentices": summaries,
        "behind_on_otj": behind,
        "reviews_overdue": review_repository.list_reviews(**scope, overdue_only=True),
        "reviews_upcoming": _upcoming_reviews(**scope),
        "evidence_queue": portfolio_repository.list_evidence(
            status="Submitted", tutor_id=actor.staff_id, limit=20
        ),
        "otj_queue": training_repository.list_entries(
            status="Submitted", tutor_id=actor.staff_id, limit=20
        ),
        "gateway_queue": epa_repository.list_gateway_queue(tutor_id=actor.staff_id),
        "sessions_upcoming": training_repository.list_sessions(
            trainer_id=actor.staff_id, upcoming_only=True
        ),
    }


# ═════════════════════════════════════════════════════════════════════
# Apprentice
# ═════════════════════════════════════════════════════════════════════

def apprentice_dashboard(actor: Actor) -> dict[str, Any]:
    """The apprentice's own progress, in the terms they are judged on."""
    if actor.apprentice_id is None:
        return {
            "role": config.APPRENTICE,
            "title": "My Apprenticeship",
            "unlinked": True,
            "kpis": [],
        }

    apprentice_id = actor.apprentice_id
    summary = apprentice_repository.get_summary(apprentice_id)
    if summary is None:
        return {
            "role": config.APPRENTICE,
            "title": "My Apprenticeship",
            "unlinked": True,
            "kpis": [],
        }

    record = summary.apprentice
    totals = training_repository.hour_totals(apprentice_id)
    hours = otj.build_summary(
        apprentice_id,
        start_iso=record.start_date,
        end_iso=record.planned_end_date,
        weekly_hours=record.weekly_hours,
        approved=totals.get("approved", 0.0),
        pending=totals.get("pending", 0.0),
        draft=totals.get("draft", 0.0),
        entry_count=int(totals.get("count", 0)),
    )
    portfolio = (
        portfolio_repository.build_summary(apprentice_id, record.programme_id)
        if record.programme_id
        else None
    )
    compliance = compliance_repository.build_status(apprentice_id)
    reviews = review_repository.list_reviews(
        apprentice_id=apprentice_id, with_children=True, limit=10
    )

    return {
        "role": config.APPRENTICE,
        "title": "My Apprenticeship",
        "unlinked": False,
        "summary": summary,
        "kpis": [
            ("Off-the-job", f"{hours.approved_hours:.0f} / {hours.target_hours:.0f} hrs"),
            ("On track", "Yes" if hours.is_on_track else "No"),
            ("KSBs competent",
             f"{portfolio.competent_ksbs}/{portfolio.total_ksbs}" if portfolio else "—"),
            ("Programme elapsed", f"{summary.progress_percent:.0f}%"),
            ("Status", record.status),
            ("Gateway", summary.gateway_status),
        ],
        "hours": hours,
        "portfolio": portfolio,
        "gaps": portfolio.gaps[:10] if portfolio else [],
        "compliance": compliance,
        "functional_skills": compliance.functional_skills,
        "reviews": reviews,
        "next_review": _next_review(reviews),
        "open_targets": review_repository.list_targets(
            apprentice_id=apprentice_id, open_only=True
        ),
        "recent_hours": training_repository.list_entries(
            apprentice_id=apprentice_id, limit=10
        ),
        "bookings": epa_repository.list_bookings(apprentice_id=apprentice_id),
        "results": epa_repository.list_results(apprentice_id=apprentice_id),
        "sessions_upcoming": training_repository.list_sessions(
            programme_id=record.programme_id, upcoming_only=True
        ),
    }


# ═════════════════════════════════════════════════════════════════════
# Employer
# ═════════════════════════════════════════════════════════════════════

def employer_dashboard(actor: Actor) -> dict[str, Any]:
    """The employer's apprentices and what is waiting on their signature."""
    if actor.employer_id is None:
        return {
            "role": config.EMPLOYER,
            "title": "My Apprentices",
            "unlinked": True,
            "kpis": [],
        }

    employer_id = actor.employer_id
    employer = employer_repository.get_summary(employer_id)
    summaries = apprentice_repository.list_summaries(employer_id=employer_id)
    active = [s for s in summaries if s.apprentice.is_active]
    behind = [s for s in active if s.is_behind]

    return {
        "role": config.EMPLOYER,
        "title": employer.name if employer else "My Apprentices",
        "unlinked": False,
        "employer": employer,
        "kpis": [
            ("Active apprentices", len(active)),
            ("Hours to approve",
             training_repository.pending_count(employer_id=employer_id)),
            ("Reviews to sign",
             review_repository.count_awaiting_signature(employer_id=employer_id)),
            ("Behind on off-the-job", len(behind)),
            ("At gateway",
             sum(1 for s in active if s.apprentice.status == "Gateway")),
            ("Completed",
             sum(1 for s in summaries if s.apprentice.status == "Completed")),
        ],
        "apprentices": summaries,
        "behind_on_otj": behind,
        "otj_queue": training_repository.list_entries(
            status="Submitted", employer_id=employer_id, limit=25
        ),
        "reviews_to_sign": review_repository.list_reviews(
            employer_id=employer_id, status="Awaiting Signatures", with_children=True
        ),
        "reviews_upcoming": _upcoming_reviews(employer_id=employer_id),
        "workplaces": employer_repository.list_workplaces(employer_id),
        "funding": funding_repository.totals(employer_id=employer_id),
        "levy": _levy_for(employer),
    }


# ═════════════════════════════════════════════════════════════════════
# End-point assessor
# ═════════════════════════════════════════════════════════════════════

def assessor_dashboard(actor: Actor) -> dict[str, Any]:
    """The assessor's diary and the gateway requests awaiting a decision.

    Deliberately narrow. An end-point assessor is independent of the
    provider, so this shows the assessment side only — no caseload
    notes, no formative judgements, nothing that could prejudice a
    grading decision.
    """
    require(actor, "epa.view")
    today = date.today().isoformat()
    horizon = (date.today() + timedelta(days=UPCOMING_DAYS)).isoformat()

    mine = epa_repository.list_bookings(
        assessor_username=actor.username, open_only=True
    )
    return {
        "role": config.END_POINT_ASSESSOR,
        "title": "End-Point Assessment",
        "kpis": [
            ("My open bookings", len(mine)),
            ("Scheduled this fortnight",
             sum(1 for b in mine if b.get("scheduled_date")
                 and today <= b["scheduled_date"] <= horizon)),
            ("Awaiting scheduling",
             sum(1 for b in mine if b.get("status") == "Requested")),
            ("Gateway requests",
             len(epa_repository.list_gateway_queue(status="Requested"))),
            ("Resits requested",
             len(epa_repository.list_resits(status="Requested"))),
            ("Graded this month", _graded_this_month()),
        ],
        "my_bookings": mine,
        "diary": epa_repository.list_bookings(
            assessor_username=actor.username,
            date_from=today, date_to=horizon, open_only=True,
        ),
        "unassigned": epa_repository.list_bookings(status="Requested"),
        "gateway_requests": epa_repository.list_gateway_queue(status="Requested"),
        "resits": epa_repository.list_resits(status="Requested"),
        "recent_results": epa_repository.list_results(limit=15),
    }


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _upcoming_reviews(**scope: Any) -> list[Any]:
    today = date.today().isoformat()
    horizon = (date.today() + timedelta(days=UPCOMING_DAYS)).isoformat()
    return review_repository.list_reviews(
        **scope, statuses=["Scheduled", "In Progress"],
        date_from=today, date_to=horizon,
    )


def _next_review(reviews: list[Any]) -> Any | None:
    """The soonest review still to happen."""
    pending = [r for r in reviews if r.status in ("Scheduled", "In Progress")]
    if not pending:
        return None
    return min(pending, key=lambda r: r.scheduled_date)


def _completion_rate(summaries: list[Any]) -> float | None:
    """Share of finished apprentices who completed.

    None while nobody has finished, so a young provider is not shown a
    0% achievement rate that means nothing.
    """
    completed = sum(1 for s in summaries if s.apprentice.status == "Completed")
    withdrawn = sum(1 for s in summaries if s.apprentice.status == "Withdrawn")
    finished = completed + withdrawn
    if finished == 0:
        return None
    return round(completed / finished * 100, 1)


def _levy_for(employer_summary: Any) -> Any | None:
    if employer_summary is None:
        return None
    from education_system.systems.apprenticeships.domain.funding.funding_rules import (
        levy_position,
    )

    try:
        return levy_position(employer_summary.employer.paybill)
    except Exception:
        logger.debug("Could not compute levy position", exc_info=True)
        return None


def _graded_this_month() -> int:
    month = date.today().isoformat()[:7]
    return sum(1 for r in epa_repository.list_results(limit=500)
               if r.assessed_date.startswith(month))
