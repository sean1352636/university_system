"""GUI-neutral in-process university event broker.

This is a fast notification path only. Business-critical producers must also
write to the platform durable outbox in the transaction that records the source
decision.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

EVENT_EXAM_CHANGED = "exam.changed"
EVENT_GRADE_CHANGED = "grade.changed"
EVENT_MODULE_SCHEDULE_CHANGED = "module.schedule.changed"
EVENT_COURSE_CHANGED = "course.changed"
EVENT_ENROLMENT_CHANGED = "enrolment.changed"
EVENT_ASSESSMENT_CHANGED = "assessment.changed"
EVENT_ASSIGNMENT_CHANGED = "assignment.changed"
EVENT_CALENDAR_CHANGED = "calendar.changed"
EVENT_CHARGE_RAISED = "finance.charge.raised"
EVENT_HOLD_CHANGED = "finance.hold.changed"
EVENT_READING_LIST_CHANGED = "library.reading_list.changed"
EVENT_LOAN_CHANGED = "library.loan.changed"
EVENT_TERM_CHANGED = "academic.term.changed"
EVENT_SELECTION_CHANGED = "academic.selection.changed"
EVENT_STAFF_AVAILABILITY_CHANGED = "hr.staff_availability.changed"
EVENT_DOCUMENT_CHANGED = "dm.document.changed"
EVENT_INCIDENT_LOGGED = "hs.incident.logged"
EVENT_CERT_CHANGED = "hr.certification.changed"
EVENT_CASE_OPENED = "case.opened"
EVENT_CASE_CLOSED = "case.closed"
EVENT_SANCTION_APPLIED = "case.sanction.applied"
EVENT_SU_ADVOCACY_REQUESTED = "su.advocacy.requested"
EVENT_MEMBERSHIP_CHANGED = "su.membership.changed"
EVENT_ENGAGEMENT_STARTED = "careers.engagement.started"
EVENT_ENGAGEMENT_ENDED = "careers.engagement.ended"
EVENT_HOURS_LOGGED = "careers.hours.logged"
EVENT_JOB_POSTED = "careers.job.posted"
EVENT_TRIP_CREATED = "trip.created"
EVENT_TRIP_REGISTRATION_CHANGED = "trip.registration.changed"
EVENT_PARKING_VIOLATION = "parking.violation"
EVENT_MEAL_PLAN_CHANGED = "restaurant.meal_plan.changed"
EVENT_EMAIL_SENT = "email.sent"

ALL_EVENTS = (
    EVENT_EXAM_CHANGED,
    EVENT_GRADE_CHANGED,
    EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_COURSE_CHANGED,
    EVENT_ENROLMENT_CHANGED,
    EVENT_ASSESSMENT_CHANGED,
    EVENT_ASSIGNMENT_CHANGED,
    EVENT_CALENDAR_CHANGED,
    EVENT_CHARGE_RAISED,
    EVENT_HOLD_CHANGED,
    EVENT_READING_LIST_CHANGED,
    EVENT_LOAN_CHANGED,
    EVENT_TERM_CHANGED,
    EVENT_SELECTION_CHANGED,
    EVENT_STAFF_AVAILABILITY_CHANGED,
    EVENT_DOCUMENT_CHANGED,
    EVENT_INCIDENT_LOGGED,
    EVENT_CERT_CHANGED,
    EVENT_CASE_OPENED,
    EVENT_CASE_CLOSED,
    EVENT_SANCTION_APPLIED,
    EVENT_SU_ADVOCACY_REQUESTED,
    EVENT_MEMBERSHIP_CHANGED,
    EVENT_ENGAGEMENT_STARTED,
    EVENT_ENGAGEMENT_ENDED,
    EVENT_HOURS_LOGGED,
    EVENT_JOB_POSTED,
    EVENT_TRIP_CREATED,
    EVENT_TRIP_REGISTRATION_CHANGED,
    EVENT_PARKING_VIOLATION,
    EVENT_MEAL_PLAN_CHANGED,
    EVENT_EMAIL_SENT,
)

_lock = threading.RLock()
_subscribers: dict[str, list[Callable[..., None]]] = {}


def subscribe(event: str, callback: Callable[..., None]) -> Callable[[], None]:
    """Subscribe a callback and return an idempotent unsubscribe function."""
    if event not in ALL_EVENTS:
        raise ValueError(f"Unknown university event contract: {event}")
    with _lock:
        _subscribers.setdefault(event, []).append(callback)

    def unsubscribe() -> None:
        with _lock:
            listeners = _subscribers.get(event)
            if listeners and callback in listeners:
                listeners.remove(callback)

    return unsubscribe


def publish(event: str, **payload: Any) -> None:
    """Notify every current in-process listener."""
    if event not in ALL_EVENTS:
        raise ValueError(f"Unknown university event contract: {event}")
    with _lock:
        listeners = tuple(_subscribers.get(event, ()))
    for callback in listeners:
        try:
            callback(**payload)
        except Exception:
            logger.exception("University event subscriber failed: %s", event)


def reset_for_tests() -> None:
    with _lock:
        _subscribers.clear()


__all__ = [
    name
    for name in globals()
    if name.startswith("EVENT_")
] + ["ALL_EVENTS", "publish", "reset_for_tests", "subscribe"]
