"""The calendar: every dated thing in the actor's scope, in one diary.

Reviews, training sessions, end-point assessments and learning-plan
target dates each live on their own screen. The calendar lays them out
by day so a tutor can see a clash, an apprentice can see their week, and
an employer can plan who is out of the building for training.

Like the task list, it is built from small providers, and a provider
that fails is logged and skipped rather than blanking the diary.

``export_ics`` writes the same events as an iCalendar file, which is how
the diary gets into Outlook, Google Calendar or Apple Calendar without
this system having to integrate with any of them.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from education_system import paths
from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.workspace.items import (
    CalendarEvent,
    to_ics,
    within,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    epa_repository,
    learning_plan_repository,
    review_repository,
    support_repository,
    training_repository,
)
from education_system.systems.apprenticeships.services import (
    action_plan_service,
    appeal_service,
    assignment_service,
    complaint_service,
    document_service,
    employer_contact_service,
    survey_service,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
)

logger = logging.getLogger(__name__)

Provider = Callable[[Actor, date, date], list[CalendarEvent]]

_REVIEW_SCREENS: dict[str, tuple[str, str]] = {
    config.STAFF: ("staff.reviews", "Progress Reviews"),
    config.APPRENTICE: ("apprentice.reviews", "Progress Reviews"),
    config.EMPLOYER: ("employer.reviews", "Progress Reviews"),
}
_SESSION_SCREENS: dict[str, tuple[str, str]] = {
    config.STAFF: ("staff.training", "Training Sessions"),
    config.APPRENTICE: ("shared.learning_plan", "Learning Plan"),
}
_EPA_SCREENS: dict[str, tuple[str, str]] = {
    config.END_POINT_ASSESSOR: ("end_point_assessor.bookings", "Bookings"),
    config.APPRENTICE: ("apprentice.epa", "End-Point Assessment"),
}
_PLAN_SCREENS: dict[str, tuple[str, str]] = {
    config.STAFF: ("shared.learning_plan", "Learning Plans"),
    config.APPRENTICE: ("shared.learning_plan", "Learning Plan"),
    config.EMPLOYER: ("shared.learning_plan", "Learning Plans"),
    config.ADMIN: ("shared.learning_plan", "Learning Plans"),
}


def events(actor: Actor, *, date_from: date, date_to: date) -> list[CalendarEvent]:
    """Everything in *actor*'s scope from *date_from* to *date_to* inclusive."""
    require(actor, "calendar.view")
    if date_to < date_from:
        raise ValidationError("The end of the range must not be before the start")
    if (date_to - date_from).days > config.CALENDAR_MAX_DAYS:
        raise ValidationError(f"Choose a range of {config.CALENDAR_MAX_DAYS} days or fewer")
    found: list[CalendarEvent] = []
    for provider in _PROVIDERS:
        try:
            found.extend(provider(actor, date_from, date_to))
        except PermissionDenied:
            continue
        except Exception:
            logger.exception("Calendar source %s failed for %s", provider.__name__,
                             actor.username)
    return within(found, date_from, date_to)


def export_ics(actor: Actor, *, date_from: date, date_to: date) -> Path:
    """Write the diary for the range as an .ics file and return its path.

    Written under the exports directory rather than handed back as text,
    for the same reason the CSV reports are: the filename says whose
    diary it is and for when, which matters once it has been emailed.
    """
    diary = events(actor, date_from=date_from, date_to=date_to)
    name = f"Apprenticeships — {getattr(actor, 'display_name', None) or actor.username}"
    text = to_ics(diary, name=name, stamp=datetime.now(UTC))

    who = re.sub(r"[^A-Za-z0-9_-]", "", actor.username) or "user"
    target = paths.APPRENTICESHIPS_EXPORTS_DIR / f"calendar-{who}-{date_from}-{date_to}.ics"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="")

    compliance_repository.record(
        action="export", entity="calendar", entity_id=actor.username,
        actor=actor.username, actor_role=actor.role,
        detail=f"{len(diary)} event(s) {date_from} to {date_to} → {target.name}",
    )
    return target


# ═════════════════════════════════════════════════════════════════════
# Providers
# ═════════════════════════════════════════════════════════════════════

def _reviews(actor: Actor, start: date, end: date) -> list[CalendarEvent]:
    if not actor.can("review.view") or actor.role == config.END_POINT_ASSESSOR:
        return []
    own = actor.role == config.APPRENTICE
    return [
        CalendarEvent(
            day=r.scheduled_date,
            title="Progress review" if own else f"Progress review — {r.apprentice_name}",
            kind="Review", detail=r.status, apprentice_id=r.apprentice_id,
            opens=_REVIEW_SCREENS.get(actor.role), uid=f"review-{r.review_id}",
        )
        for r in review_repository.list_reviews(
            **apprentice_filters(actor), date_from=start.isoformat(), date_to=end.isoformat(),
        )
    ]


def _sessions(actor: Actor, start: date, end: date) -> list[CalendarEvent]:
    """Training sessions: those a tutor delivers, those an apprentice's
    programme runs, and — for an employer — those their apprentices will
    be out of the workplace for."""
    if not actor.can("training.view"):
        return []
    window = {"date_from": start.isoformat(), "date_to": end.isoformat()}
    if actor.role == config.STAFF:
        if actor.staff_id is None:
            return []
        sessions = training_repository.list_sessions(trainer_id=actor.staff_id, **window)
    elif actor.role == config.ADMIN:
        sessions = training_repository.list_sessions(**window)
    else:
        programmes = {
            s.apprentice.programme_id
            for s in apprentice_repository.list_summaries(
                **apprentice_filters(actor), active_only=True,
            )
            if s.apprentice.programme_id
        }
        sessions = [
            session
            for programme_id in programmes
            for session in training_repository.list_sessions(programme_id=programme_id, **window)
        ]
    return [
        CalendarEvent(
            day=s.session_date, time=s.start_time, title=s.title, kind="Training",
            detail=" · ".join(filter(None, [s.delivery_mode, s.location, s.programme_title])),
            opens=_SESSION_SCREENS.get(actor.role), uid=f"session-{s.session_id}",
        )
        for s in sessions
        if s.status != "Cancelled"
    ]


def _epa(actor: Actor, start: date, end: date) -> list[CalendarEvent]:
    if not actor.can("epa.view"):
        return []
    window = {"date_from": start.isoformat(), "date_to": end.isoformat()}
    if actor.role == config.END_POINT_ASSESSOR:
        bookings = epa_repository.list_bookings(assessor_username=actor.username, **window)
    elif actor.role == config.APPRENTICE:
        if actor.apprentice_id is None:
            return []
        bookings = epa_repository.list_bookings(apprentice_id=actor.apprentice_id, **window)
    else:
        bookings = epa_repository.list_bookings(**window)
        filters = apprentice_filters(actor)
        if filters:
            visible = {
                s.apprentice.apprentice_id
                for s in apprentice_repository.list_summaries(**filters)
            }
            bookings = [b for b in bookings if b.get("apprentice_id") in visible]
    own = actor.role == config.APPRENTICE
    return [
        CalendarEvent(
            day=b["scheduled_date"], time=b.get("scheduled_time"),
            title=f"EPA: {b.get('method')}" if own
            else f"EPA: {b.get('method')} — {b.get('apprentice_name')}",
            kind="EPA", detail=b.get("location") or "", apprentice_id=b.get("apprentice_id"),
            opens=_EPA_SCREENS.get(actor.role), uid=f"epa-{b.get('booking_id')}",
        )
        for b in bookings
        if b.get("scheduled_date") and b.get("status") != "Cancelled"
    ]


def _targets(actor: Actor, start: date, end: date) -> list[CalendarEvent]:
    """Learning-plan objective target dates, for open objectives."""
    if not actor.can("training.view") or actor.role == config.ADMIN:
        return []
    own = actor.role == config.APPRENTICE
    found = []
    for summary in apprentice_repository.list_summaries(
        **apprentice_filters(actor), active_only=True,
    ):
        for objective in learning_plan_repository.list_objectives(summary.apprentice.apprentice_id):
            if objective.is_open and objective.target_date:
                found.append(CalendarEvent(
                    day=objective.target_date,
                    title=f"Target: {objective.title}" if own
                    else f"Target: {objective.title} — {summary.full_name}",
                    kind="Target", detail=f"{objective.progress}% complete",
                    apprentice_id=summary.apprentice.apprentice_id,
                    opens=_PLAN_SCREENS.get(actor.role),
                    uid=f"objective-{objective.objective_id}",
                ))
    return found


def _support_reviews(actor: Actor, start: date, end: date) -> list[CalendarEvent]:
    """Review dates for support arrangements — the provider's diary only."""
    if not actor.can("support.manage"):
        return []
    opens = ("shared.support", "Support & Adjustments")
    return [
        CalendarEvent(
            day=a.review_date, title=f"Support review — {a.apprentice_name}", kind="Support",
            detail=a.need_category, apprentice_id=a.apprentice_id, opens=opens,
            uid=f"support-{a.arrangement_id}",
        )
        for a in support_repository.list_arrangements(
            **apprentice_filters(actor), in_force_only=True,
        )
        if a.review_date and start.isoformat() <= a.review_date <= end.isoformat()
    ]


def _progress_dates(actor: Actor, start: date, end: date) -> list[CalendarEvent]:
    """Due dates of open review actions and assignments in scope.

    Not for the provider admin: across the whole provider these would
    bury everything else in the diary.
    """
    if actor.role == config.ADMIN:
        return []
    own = actor.role == config.APPRENTICE
    found: list[CalendarEvent] = []
    if actor.can("action.update"):
        for a in action_plan_service.list_actions(actor, open_only=True):
            if a.due_date:
                who = getattr(a, "apprentice_name", None)
                found.append(CalendarEvent(
                    day=a.due_date, kind="Action",
                    title=f"Action due: {a.description[:60]}"
                    + ("" if own or not who else f" — {who}"),
                    detail=f"{a.owner} · {a.priority}", apprentice_id=a.apprentice_id,
                    opens=("shared.actions", "Action Plans"), uid=f"action-{a.target_id}",
                ))
    if actor.can("assignment.view"):
        for a in assignment_service.list_assignments(actor, open_only=True):
            if a.due_date:
                found.append(CalendarEvent(
                    day=a.due_date, kind="Assignment",
                    title=f"Assignment due: {a.title}"
                    + ("" if own or not a.apprentice_name else f" — {a.apprentice_name}"),
                    detail=a.assignment_type, apprentice_id=a.apprentice_id,
                    opens=("shared.assignments", "Assignments"),
                    uid=f"assignment-{a.assignment_id}",
                ))
    return [e for e in found if start.isoformat() <= e.day[:10] <= end.isoformat()]


def _document_expiry(actor: Actor, start: date, end: date) -> list[CalendarEvent]:
    """When documents in scope expire — the day a right-to-work check or
    an agreement stops being valid is worth seeing in advance."""
    if not actor.can("document.view") or actor.role == config.ADMIN:
        return []
    return [
        CalendarEvent(
            day=d.expiry_date, kind="Document",
            title=f"Expires: {d.title}"
            + (f" — {d.apprentice_name}" if d.apprentice_name
               and actor.role != config.APPRENTICE else ""),
            detail=d.category, apprentice_id=d.apprentice_id,
            opens=("shared.documents", "Documents"), uid=f"document-{d.document_id}",
        )
        for d in document_service.list_documents(actor)
        if d.expiry_date and start.isoformat() <= d.expiry_date[:10] <= end.isoformat()
    ]


def _employer_dates(actor: Actor, start: date, end: date) -> list[CalendarEvent]:
    """Employer follow-ups and commitment due dates, for the provider."""
    if not actor.can("employer.contact"):
        return []
    window_from, window_to = start.isoformat(), end.isoformat()
    opens = ("shared.employer_contacts", "Employer Contacts")
    found = [
        CalendarEvent(
            day=e.follow_up_date, kind="Employer",
            title=f"Follow up: {e.employer_name or 'employer'}", detail=e.summary[:80],
            apprentice_id=e.apprentice_id, opens=opens, uid=f"follow-up-{e.log_id}",
        )
        for e in employer_contact_service.follow_ups(actor, due_from=window_from, due_by=window_to)
        if e.follow_up_date
    ]
    found += [
        CalendarEvent(
            day=c.due_date, kind="Employer",
            title=f"Commitment due: {c.commitment[:50]} — {c.employer_name or 'employer'}",
            detail=c.category, apprentice_id=c.apprentice_id, opens=opens,
            uid=f"commitment-{c.commitment_id}",
        )
        for c in employer_contact_service.list_commitments(
            actor, outstanding_only=True, due_from=window_from, due_to=window_to,
        )
        if c.due_date
    ]
    return found


def _quality_deadlines(actor: Actor, start: date, end: date) -> list[CalendarEvent]:
    """Complaint and appeal deadlines for whoever must meet them, and the
    closing date of any survey still waiting for this person's answer."""
    found: list[CalendarEvent] = []
    if actor.can("complaint.manage"):
        for c in complaint_service.list_complaints(actor, open_only=True):
            acknowledging = c.status == "Received"
            found.append(CalendarEvent(
                day=c.ack_due_on if acknowledging else c.response_due_on,
                title=f"{'Acknowledge' if acknowledging else 'Respond to'} {c.reference}",
                kind="Complaint", detail=c.subject, apprentice_id=c.apprentice_id,
                opens=("shared.complaints", "Complaints"), uid=f"complaint-{c.complaint_id}",
            ))
    if actor.can("appeal.decide"):
        for a in appeal_service.list_appeals(actor, open_only=True):
            if appeal_service.may_decide(actor, a):
                found.append(CalendarEvent(
                    day=a.deadline, title=f"Decide appeal {a.reference}", kind="Appeal",
                    detail=a.appeal_type, apprentice_id=a.apprentice_id,
                    opens=("shared.appeals", "Appeals"), uid=f"appeal-{a.appeal_id}",
                ))
    if actor.can("survey.respond"):
        for survey, responded in survey_service.available_surveys(actor):
            if not responded and survey.closes_on:
                found.append(CalendarEvent(
                    day=survey.closes_on, title=f"Survey closes: {survey.title}",
                    kind="Survey", opens=("shared.surveys", "Surveys"),
                    uid=f"survey-{survey.survey_id}",
                ))
    return [e for e in found if e.day and start.isoformat() <= e.day[:10] <= end.isoformat()]


_PROVIDERS: tuple[Provider, ...] = (
    _reviews, _sessions, _epa, _targets, _support_reviews, _progress_dates,
    _document_expiry, _employer_dates, _quality_deadlines,
)
