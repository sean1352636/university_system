"""What is waiting on the signed-in person, gathered from everywhere.

Every screen already has its own queue — hours to approve, evidence to
assess, reviews to sign. The task list gathers them in one place, most
urgent first, so nobody has to visit eight screens to find out what
needs them today.

Each source is a small provider. A provider that fails is logged and
skipped rather than emptying the list: one broken query should not hide
everything else someone has to do. Providers that have nothing to say
to a role return an empty list.

For the provider admin, queues across the whole provider would be
hundreds of rows, so their tasks are rolled up into counts.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ApprenticeSummary
from education_system.systems.apprenticeships.domain.training import attendance as attendance_rules
from education_system.systems.apprenticeships.domain.workspace.items import (
    Task,
    count_by_urgency,
    sort_tasks,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    epa_repository,
    learning_plan_repository,
    portfolio_repository,
    review_repository,
    support_repository,
    training_repository,
    welfare_repository,
)
from education_system.systems.apprenticeships.application.apprentices import admissions_service
from education_system.systems.apprenticeships.application.employers import employer_contact_service
from education_system.systems.apprenticeships.application.learning import (
    action_plan_service,
    assignment_service,
)
from education_system.systems.apprenticeships.application.quality import (
    appeal_service,
    complaint_service,
    survey_service,
)
from education_system.systems.apprenticeships.application.records import (
    document_service,
    signature_service,
)
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
)

logger = logging.getLogger(__name__)

Provider = Callable[[Actor, date], list[Task]]

# (window module, navigation label) for each kind of work, per role. A
# role missing here has no screen for it: the task still shows, it just
# cannot open anything.
_SCREENS: dict[str, dict[str, tuple[str, str]]] = {
    "reviews": {
        config.STAFF: ("staff.reviews", "Progress Reviews"),
        config.APPRENTICE: ("apprentice.reviews", "Progress Reviews"),
        config.EMPLOYER: ("employer.reviews", "Progress Reviews"),
    },
    "otj_approve": {
        config.STAFF: ("staff.assessments", "Off-the-Job Approvals"),
        config.EMPLOYER: ("employer.training", "Off-the-Job Hours"),
    },
    "otj_log": {config.APPRENTICE: ("apprentice.off_the_job_hours", "Off-the-Job Hours")},
    "evidence": {config.STAFF: ("staff.portfolios", "Portfolios")},
    "caseload": {
        config.STAFF: ("staff.caseload", "My Caseload"),
        config.EMPLOYER: ("employer.apprentices", "My Apprentices"),
        config.APPRENTICE: ("apprentice.dashboard", "Dashboard"),
    },
    "attendance": {
        config.STAFF: ("staff.training", "Training Sessions"),
        config.EMPLOYER: ("employer.dashboard", "Dashboard"),
        config.APPRENTICE: ("apprentice.dashboard", "Dashboard"),
    },
    "plan": {
        config.STAFF: ("shared.learning_plan", "Learning Plans"),
        config.APPRENTICE: ("shared.learning_plan", "Learning Plan"),
        config.EMPLOYER: ("shared.learning_plan", "Learning Plans"),
    },
    "support": {
        config.STAFF: ("shared.support", "Support & Adjustments"),
        config.ADMIN: ("shared.support", "Support & Adjustments"),
    },
    "welfare": {
        config.STAFF: ("shared.welfare", "Welfare & Risk"),
        config.ADMIN: ("shared.welfare", "Welfare & Risk"),
    },
    "gateway": {config.END_POINT_ASSESSOR: ("end_point_assessor.gateway", "Gateway Requests")},
    "epa": {
        config.END_POINT_ASSESSOR: ("end_point_assessor.bookings", "Bookings"),
        config.APPRENTICE: ("apprentice.epa", "End-Point Assessment"),
    },
}

# Reviews are signed as one of config.REVIEW_SIGNATORIES.
_SIGNS_AS: dict[str, str] = {
    config.ADMIN: "provider",
    config.STAFF: "provider",
    config.APPRENTICE: "apprentice",
    config.EMPLOYER: "employer",
}


def my_tasks(actor: Actor, *, today: date | None = None) -> list[Task]:
    """Everything waiting on *actor*, most urgent first."""
    require(actor, "task.view")
    today = today or date.today()
    tasks: list[Task] = []
    for provider in _PROVIDERS:
        try:
            tasks.extend(provider(actor, today))
        except PermissionDenied:
            continue
        except Exception:
            logger.exception("Task source %s failed for %s", provider.__name__, actor.username)
    return sort_tasks(tasks, today)


def counts(actor: Actor, *, today: date | None = None) -> dict[str, int]:
    """Tasks by urgency, plus ``Total`` — for dashboard headlines."""
    today = today or date.today()
    tasks = my_tasks(actor, today=today)
    result = count_by_urgency(tasks, today)
    result["Total"] = len(tasks)
    return result


# ═════════════════════════════════════════════════════════════════════
# Providers
# ═════════════════════════════════════════════════════════════════════

def _reviews(actor: Actor, today: date) -> list[Task]:
    """Reviews to hold (staff) or attend (apprentice, employer)."""
    if not actor.can("review.view") or actor.role == config.END_POINT_ASSESSOR:
        return []
    horizon = today + timedelta(days=config.TASK_HORIZON_DAYS)
    reviews = review_repository.list_reviews(
        **apprentice_filters(actor), statuses=["Scheduled", "In Progress"],
        date_to=horizon.isoformat(),
    )
    if actor.role == config.ADMIN:
        overdue = [r for r in reviews if r.scheduled_date < today.isoformat()]
        if not overdue:
            return []
        oldest = min(r.scheduled_date for r in overdue)
        return [Task("Reviews", f"{len(overdue)} progress review(s) overdue across the provider",
                     detail=f"The oldest was due {oldest}", due=oldest)]
    verb = "Hold" if actor.can("review.conduct") else "Attend"
    return [
        Task("Reviews", f"{verb} progress review", detail=r.status, due=r.scheduled_date,
             apprentice_id=r.apprentice_id, apprentice_name=r.apprentice_name,
             opens=_opens("reviews", actor))
        for r in reviews
    ]


def _review_signatures(actor: Actor, today: date) -> list[Task]:
    """Held reviews still waiting for this role's signature."""
    signs_as = _SIGNS_AS.get(actor.role)
    if signs_as is None or not actor.can("review.sign"):
        return []
    reviews = [
        r for r in review_repository.list_reviews(
            **apprentice_filters(actor), status="Awaiting Signatures", with_children=True,
        )
        if signs_as in r.missing_signatures
    ]
    if actor.role == config.ADMIN:
        if not reviews:
            return []
        return [Task("Signatures", f"{len(reviews)} review(s) waiting for the provider's signature")]
    return [
        Task("Signatures", "Sign progress review",
             detail=f"Held {r.held_date or r.scheduled_date}",
             apprentice_id=r.apprentice_id, apprentice_name=r.apprentice_name,
             opens=_opens("reviews", actor))
        for r in reviews
    ]


def _hours_to_approve(actor: Actor, today: date) -> list[Task]:
    if not actor.can("otj.approve"):
        return []
    entries = training_repository.list_entries(status="Submitted", **apprentice_filters(actor))
    if not entries:
        return []
    if actor.role == config.ADMIN:
        return [Task("Off-the-job hours",
                     f"{len(entries)} off-the-job entries waiting for approval across the provider")]
    names = _names(actor)
    grouped: dict[int, list] = defaultdict(list)
    for entry in entries:
        grouped[entry.apprentice_id].append(entry)
    return [
        Task("Off-the-job hours",
             f"Approve {len(rows)} off-the-job entr{'y' if len(rows) == 1 else 'ies'}",
             detail=f"{sum(e.hours for e in rows):g} hours, the oldest from "
                    f"{min(e.activity_date for e in rows)}",
             apprentice_id=aid, apprentice_name=names.get(aid),
             opens=_opens("otj_approve", actor))
        for aid, rows in grouped.items()
    ]


def _evidence_to_assess(actor: Actor, today: date) -> list[Task]:
    if not actor.can("portfolio.assess"):
        return []
    if actor.role == config.ADMIN:
        waiting = portfolio_repository.pending_assessment_count()
        return [Task("Portfolio", f"{waiting} evidence item(s) waiting for assessment "
                     "across the provider")] if waiting else []
    if actor.staff_id is None:
        return []
    names = _names(actor)
    return [
        Task("Portfolio", f"Assess evidence: {e.title}",
             detail=f"Submitted {e.submitted_at or '—'}",
             apprentice_id=e.apprentice_id, apprentice_name=names.get(e.apprentice_id),
             opens=_opens("evidence", actor))
        for e in portfolio_repository.list_evidence(
            status="Submitted", tutor_id=actor.staff_id, limit=50,
        )
    ]


def _draft_hours(actor: Actor, today: date) -> list[Task]:
    """An apprentice's logged hours that were never sent for approval."""
    if actor.role != config.APPRENTICE or actor.apprentice_id is None:
        return []
    drafts = training_repository.list_entries(apprentice_id=actor.apprentice_id, status="Draft")
    if not drafts:
        return []
    return [Task("Off-the-job hours",
                 f"Submit {len(drafts)} draft entr{'y' if len(drafts) == 1 else 'ies'}",
                 detail=f"{sum(e.hours for e in drafts):g} hours not yet sent for approval",
                 opens=_opens("otj_log", actor))]


def _progress(actor: Actor, today: date) -> list[Task]:
    """Apprentices behind on off-the-job hours, and attendance concerns."""
    if actor.role not in (config.STAFF, config.EMPLOYER, config.APPRENTICE):
        return []
    cohort = _cohort(actor)
    own = actor.role == config.APPRENTICE
    tasks = [
        Task("Off-the-job hours",
             "You are behind on off-the-job hours" if own else "Behind on off-the-job hours",
             detail=f"{s.otj_percent:.0f}% logged against {s.progress_percent:.0f}% of the "
                    "programme elapsed",
             apprentice_id=s.apprentice.apprentice_id, apprentice_name=s.full_name,
             opens=_opens("otj_log" if own else "caseload", actor))
        for s in cohort if s.is_behind
    ]
    names = {s.apprentice.apprentice_id: s.full_name for s in cohort}
    marks = training_repository.attendance_by_apprentice(names)
    for apprentice_id, records in marks.items():
        record = attendance_rules.summarise(apprentice_id, records)
        if record.is_concern:
            tasks.append(Task(
                "Attendance",
                "Your attendance at training needs attention" if own
                else "Attendance needs following up",
                detail=record.concern_reason or "",
                apprentice_id=apprentice_id, apprentice_name=names.get(apprentice_id),
                opens=_opens("attendance", actor),
            ))
    return tasks


def _objectives(actor: Actor, today: date) -> list[Task]:
    """Learning-plan objectives overdue or due within the horizon."""
    if actor.role not in (config.STAFF, config.APPRENTICE) or not actor.can("training.view"):
        return []
    horizon = (today + timedelta(days=config.TASK_HORIZON_DAYS)).isoformat()
    tasks = []
    for summary in _cohort(actor):
        for objective in learning_plan_repository.list_objectives(summary.apprentice.apprentice_id):
            if objective.is_open and objective.target_date and objective.target_date <= horizon:
                tasks.append(Task(
                    "Learning plan", f"Objective due: {objective.title}",
                    detail=f"{objective.progress}% complete", due=objective.target_date,
                    apprentice_id=summary.apprentice.apprentice_id,
                    apprentice_name=summary.full_name, opens=_opens("plan", actor),
                ))
    return tasks


def _gateway(actor: Actor, today: date) -> list[Task]:
    """Gateway requests waiting on the end-point assessor's decision."""
    if actor.role != config.END_POINT_ASSESSOR or not actor.can("gateway.approve"):
        return []
    return [
        Task("Gateway", "Decide gateway request",
             detail=f"{row.get('programme_title') or ''} — requested {row.get('requested_at') or '—'}",
             apprentice_id=row.get("apprentice_id"), apprentice_name=row.get("apprentice_name"),
             opens=_opens("gateway", actor))
        for row in epa_repository.list_gateway_queue(status="Requested")
    ]


def _epa(actor: Actor, today: date) -> list[Task]:
    """Assessments to schedule or sit."""
    if actor.role == config.END_POINT_ASSESSOR:
        tasks = []
        for booking in epa_repository.list_bookings(
            assessor_username=actor.username, open_only=True,
        ):
            scheduled = booking.get("status") != "Requested" and booking.get("scheduled_date")
            tasks.append(Task(
                "End-point assessment",
                f"{'Assess' if scheduled else 'Schedule'}: {booking.get('method')}",
                detail=booking.get("location") or "",
                due=booking.get("scheduled_date") if scheduled else None,
                apprentice_id=booking.get("apprentice_id"),
                apprentice_name=booking.get("apprentice_name"),
                opens=_opens("epa", actor),
            ))
        unassigned = epa_repository.list_bookings(status="Requested")
        unassigned = [b for b in unassigned if not b.get("assessor_username")]
        if unassigned:
            tasks.append(Task("End-point assessment",
                              f"{len(unassigned)} booking(s) waiting for an assessor",
                              opens=_opens("epa", actor)))
        return tasks
    if actor.role == config.APPRENTICE and actor.apprentice_id is not None:
        return [
            Task("End-point assessment", f"End-point assessment: {b.get('method')}",
                 detail=" ".join(filter(None, [b.get("scheduled_time"), b.get("location")])),
                 due=b.get("scheduled_date"), opens=_opens("epa", actor))
            for b in epa_repository.list_bookings(
                apprentice_id=actor.apprentice_id, open_only=True,
            )
            if b.get("scheduled_date")
        ]
    return []


def _support_reviews(actor: Actor, today: date) -> list[Task]:
    """Support arrangements due for review — provider work, so staff and admin."""
    if not actor.can("support.manage"):
        return []
    horizon = (today + timedelta(days=config.TASK_HORIZON_DAYS)).isoformat()
    due = support_repository.list_arrangements(
        **apprentice_filters(actor), in_force_only=True, review_due_by=horizon,
    )
    if actor.role == config.ADMIN:
        if not due:
            return []
        soonest = min((a.review_date for a in due if a.review_date), default=None)
        return [Task("Support", f"{len(due)} support arrangement(s) due for review",
                     due=soonest, opens=_opens("support", actor))]
    return [
        Task("Support", f"Review support arrangement: {a.need_category}",
             detail=a.adjustment[:80], due=a.review_date,
             apprentice_id=a.apprentice_id, apprentice_name=a.apprentice_name,
             opens=_opens("support", actor))
        for a in due
    ]


def _welfare(actor: Actor, today: date) -> list[Task]:
    """Open welfare concerns. Never shown outside the provider.

    The detail is the status only — a concern's description does not
    belong in a list that might be read over someone's shoulder.
    """
    if actor.role not in (config.ADMIN, config.STAFF) or not actor.can("welfare.manage"):
        return []
    concerns = welfare_repository.list_concerns(**apprentice_filters(actor), open_only=True)
    if actor.role == config.ADMIN:
        if not concerns:
            return []
        serious = sum(1 for c in concerns if c.severity in ("High", "Critical"))
        return [Task("Welfare", f"{len(concerns)} open welfare concern(s), {serious} high or "
                     "critical", opens=_opens("welfare", actor))]
    return [
        Task("Welfare", f"{c.severity} {c.category.lower()} concern", detail=c.status,
             apprentice_id=c.apprentice_id, apprentice_name=c.apprentice_name,
             opens=_opens("welfare", actor))
        for c in concerns
    ]


def _actions(actor: Actor, today: date) -> list[Task]:
    """Review actions this person owns that are due or overdue."""
    if not actor.can("action.update"):
        return []
    opens = ("shared.actions", "Action Plans")
    if actor.role == config.ADMIN:
        overdue = action_plan_service.list_actions(actor, overdue_only=True)
        if not overdue:
            return []
        return [Task("Actions", f"{len(overdue)} review action(s) overdue across the provider",
                     due=min((a.due_date for a in overdue if a.due_date), default=None),
                     opens=opens)]
    horizon = (today + timedelta(days=config.TASK_HORIZON_DAYS)).isoformat()
    return [
        Task("Actions", f"Action: {a.description[:70]}",
             detail=f"{a.priority} priority" + (" · carried forward" if a.carry_count else ""),
             due=a.due_date, apprentice_id=a.apprentice_id,
             apprentice_name=getattr(a, "apprentice_name", None), opens=opens)
        for a in action_plan_service.list_actions(actor, open_only=True, mine_only=True)
        if a.due_date and a.due_date <= horizon
    ]


def _assignments(actor: Actor, today: date) -> list[Task]:
    """Work to hand in (apprentice), to mark and to moderate (provider)."""
    opens = ("shared.assignments", "Assignments")
    tasks: list[Task] = []
    if actor.role == config.APPRENTICE and actor.can("assignment.submit"):
        tasks += [
            Task("Assignments",
                 f"{'Resubmit' if a.status == 'Referred' else 'Submit'}: {a.title}",
                 detail=a.assignment_type, due=a.due_date, opens=opens)
            for a in assignment_service.list_assignments(actor, open_only=True)
            if a.is_with_apprentice
        ]
    for permission, queue, verb in (
        ("assignment.set", assignment_service.marking_queue, "Mark"),
        ("assignment.moderate", assignment_service.moderation_queue, "Moderate"),
    ):
        if actor.role == config.APPRENTICE or not actor.can(permission):
            continue
        items = queue(actor)
        if actor.role == config.ADMIN:
            if items:
                tasks.append(Task("Assignments", f"{verb}: {len(items)} assignment(s) across "
                                  "the provider", opens=opens))
            continue
        tasks += [
            Task("Assignments", f"{verb}: {a.title}", detail=f"Attempt {a.attempt}",
                 apprentice_id=a.apprentice_id, apprentice_name=a.apprentice_name, opens=opens)
            for a in items
        ]
    return tasks


def _signatures(actor: Actor, today: date) -> list[Task]:
    """Plans and agreements waiting for this person's signature, including
    ones whose earlier signature lapsed because the content changed."""
    if not actor.can("signature.sign"):
        return []
    pending = signature_service.awaiting_signature(actor)
    opens = ("shared.signatures", "Awaiting Signature")
    if actor.role == config.ADMIN:
        return [Task("Signatures", f"{len(pending)} plan(s) or agreement(s) waiting for the "
                     "provider's signature", opens=opens)] if pending else []
    return [
        Task("Signatures", f"Sign: {p.title}", detail=p.category or "",
             apprentice_id=p.signoff.apprentice_id, apprentice_name=p.apprentice_name,
             opens=opens)
        for p in pending
    ]


def _documents(actor: Actor, today: date) -> list[Task]:
    """Uploads waiting for approval, and documents about to expire."""
    if not actor.can("document.view"):
        return []
    opens = ("shared.documents", "Documents")
    pending = (document_service.list_documents(actor, approval_status="Pending")
               if actor.can("document.approve") else [])
    expiring = document_service.expiring_documents(actor)
    if actor.role == config.ADMIN:
        tasks = []
        if pending:
            tasks.append(Task("Documents", f"{len(pending)} document(s) waiting for approval",
                              opens=opens))
        if expiring:
            tasks.append(Task("Documents", f"{len(expiring)} document(s) expiring soon",
                              due=min((d.expiry_date for d in expiring if d.expiry_date),
                                      default=None),
                              opens=opens))
        return tasks
    return [
        Task("Documents", f"Approve document: {d.title}", detail=d.category,
             apprentice_id=d.apprentice_id, apprentice_name=d.apprentice_name, opens=opens)
        for d in pending
    ] + [
        Task("Documents", f"Document expiring: {d.title}", detail=d.category,
             due=d.expiry_date, apprentice_id=d.apprentice_id,
             apprentice_name=d.apprentice_name, opens=opens)
        for d in expiring
    ]


def _employer_follow_ups(actor: Actor, today: date) -> list[Task]:
    """Promised call-backs to employers that are due."""
    if not actor.can("employer.contact"):
        return []
    horizon = (today + timedelta(days=config.TASK_HORIZON_DAYS)).isoformat()
    opens = ("shared.employer_contacts", "Employer Contacts")
    items = employer_contact_service.follow_ups(actor, due_by=horizon)
    if actor.role == config.ADMIN:
        return [Task("Employers", f"{len(items)} employer follow-up(s) due",
                     due=min((e.follow_up_date for e in items if e.follow_up_date), default=None),
                     opens=opens)] if items else []
    return [
        Task("Employers", f"Follow up with {e.employer_name or 'the employer'}",
             detail=e.summary[:70], due=e.follow_up_date,
             apprentice_id=e.apprentice_id, apprentice_name=e.apprentice_name, opens=opens)
        for e in items
    ]


def _commitments(actor: Actor, today: date) -> list[Task]:
    """Employer commitments coming due — for the provider chasing them,
    and for the employer who made them."""
    if not (actor.can("employer.contact") or actor.role == config.EMPLOYER):
        return []
    horizon = (today + timedelta(days=config.TASK_HORIZON_DAYS)).isoformat()
    items = employer_contact_service.list_commitments(
        actor, outstanding_only=True, due_to=horizon,
    )
    opens = (("employer.dashboard", "Dashboard") if actor.role == config.EMPLOYER
             else ("shared.employer_contacts", "Employer Contacts"))
    if actor.role == config.ADMIN:
        overdue = [c for c in items if c.is_overdue(today)]
        return [Task("Employers", f"{len(items)} employer commitment(s) due, {len(overdue)} "
                     "overdue", opens=opens)] if items else []
    return [
        Task("Employers", f"Commitment: {c.commitment[:60]}",
             detail=" · ".join(filter(None, [
                 c.employer_name, c.category,
                 f"escalated to level {c.escalation_level}" if c.escalation_level else None,
             ])),
             due=c.due_date, apprentice_id=c.apprentice_id,
             apprentice_name=c.apprentice_name, opens=opens)
        for c in items
    ]


def _applications(actor: Actor, today: date) -> list[Task]:
    """Applicants waiting for an admissions decision."""
    if not actor.can("admission.decide"):
        return []
    waiting = admissions_service.pending_count(actor)
    return [Task("Admissions", f"{waiting} application(s) waiting for a decision",
                 opens=("shared.admissions", "Admissions"))] if waiting else []


def _complaints(actor: Actor, today: date) -> list[Task]:
    """Open complaints for whoever handles them: acknowledge, then respond."""
    if not actor.can("complaint.manage"):
        return []
    tasks = []
    for c in complaint_service.list_complaints(actor, open_only=True, today=today):
        acknowledging = c.status == "Received"
        tasks.append(Task(
            "Complaints",
            f"{'Acknowledge' if acknowledging else 'Respond to'} complaint {c.reference}",
            detail=c.subject, due=c.ack_due_on if acknowledging else c.response_due_on,
            apprentice_id=c.apprentice_id, apprentice_name=c.apprentice_name,
            opens=("shared.complaints", "Complaints"),
        ))
    return tasks


def _appeals(actor: Actor, today: date) -> list[Task]:
    """Appeals waiting on a decision. The service routes each type to the
    only role that may decide it, so the EPAO sees EPA-result appeals and
    the provider sees the rest."""
    if not actor.can("appeal.decide"):
        return []
    return [
        Task("Appeals", f"Decide appeal {a.reference}", detail=a.appeal_type, due=a.deadline,
             apprentice_id=a.apprentice_id, apprentice_name=a.apprentice_name,
             opens=("shared.appeals", "Appeals"))
        for a in appeal_service.list_appeals(actor, open_only=True, today=today)
        if appeal_service.may_decide(actor, a)
    ]


def _surveys(actor: Actor, today: date) -> list[Task]:
    """Open surveys this person has not answered yet."""
    if not actor.can("survey.respond"):
        return []
    return [
        Task("Surveys", f"Complete survey: {survey.title}", due=survey.closes_on,
             opens=("shared.surveys", "Surveys"))
        for survey, responded in survey_service.available_surveys(actor, today=today)
        if not responded
    ]


_PROVIDERS: tuple[Provider, ...] = (
    _reviews,
    _review_signatures,
    _hours_to_approve,
    _evidence_to_assess,
    _draft_hours,
    _progress,
    _objectives,
    _gateway,
    _epa,
    _support_reviews,
    _welfare,
    _actions,
    _assignments,
    _signatures,
    _documents,
    _employer_follow_ups,
    _commitments,
    _applications,
    _complaints,
    _appeals,
    _surveys,
)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _opens(kind: str, actor: Actor) -> tuple[str, str] | None:
    return _SCREENS.get(kind, {}).get(actor.role)


def _cohort(actor: Actor) -> list[ApprenticeSummary]:
    """Active apprentices inside *actor*'s scope."""
    return apprentice_repository.list_summaries(**apprentice_filters(actor), active_only=True)


def _names(actor: Actor) -> dict[int, str]:
    return {s.apprentice.apprentice_id: s.full_name for s in _cohort(actor)}
