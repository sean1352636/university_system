"""In-process pub/sub for the academic GUIs.

When one of the four management windows (Exam, Grade, Module, Course)
writes data, it ``publish``-es a typed event. Other open windows that
have ``subscribe_tk``-d to that event get a callback dispatched onto
their own Tk loop via ``widget.after_idle``, so they can refresh
without the writer caring who's listening.

Design constraints:
- Pure Python module-level state. No external dependencies, no
  threading primitives beyond a single Lock for the registry.
- Callbacks for Tk widgets are marshaled onto the widget's loop —
  publishers may run from any thread, subscribers always run on the
  widget's main thread.
- Subscriptions tied to a Tk widget are auto-revoked when the widget
  is destroyed (``<Destroy>`` binding) so closed windows don't keep
  receiving events or leak.
- Failures inside subscriber callbacks are swallowed and logged — one
  broken listener must not stop the others.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event names — keep these as module-level constants so typos surface as
# import errors instead of silently mis-routing.
# ---------------------------------------------------------------------------

EVENT_EXAM_CHANGED = "exam.changed"
EVENT_GRADE_CHANGED = "grade.changed"
EVENT_MODULE_SCHEDULE_CHANGED = "module.schedule.changed"
EVENT_COURSE_CHANGED = "course.changed"
EVENT_ENROLMENT_CHANGED = "enrolment.changed"
EVENT_ASSESSMENT_CHANGED = "assessment.changed"
EVENT_ASSIGNMENT_CHANGED = "assignment.changed"
EVENT_CALENDAR_CHANGED = "calendar.changed"

# Cross-domain events (Finance / Library / Research). The bus is the
# de-facto in-process channel for all GUIs, not just academics, so the
# new events live here too.
EVENT_CHARGE_RAISED = "finance.charge.raised"
EVENT_HOLD_CHANGED = "finance.hold.changed"
EVENT_READING_LIST_CHANGED = "library.reading_list.changed"
EVENT_LOAN_CHANGED = "library.loan.changed"

# Shared academic state. ``term.changed`` carries year/semester so all
# four scheduling GUIs re-filter together. ``selection.changed`` is a
# soft pointer ("we're now looking at module X") so sibling windows can
# highlight the same row without forcing a context switch.
EVENT_TERM_CHANGED = "academic.term.changed"
EVENT_SELECTION_CHANGED = "academic.selection.changed"

# HR publishes this when a staff member's availability changes (leave
# approved, sickness recorded, sabbatical starts). Module Scheduling,
# Exam, Timetable, and Grade subscribe so they can grey-out / flag
# affected slots without the operator having to refresh manually.
EVENT_STAFF_AVAILABILITY_CHANGED = "hr.staff_availability.changed"

# Document Manager / Health & Safety / Certifications events. The DM
# event lets the chatbot re-index and any GUI displaying an evidence
# pack auto-refresh. Incident logged is the HS/First Aid bridge into
# Finance and the chatbot. Cert changed feeds the expiry tracker.
EVENT_DOCUMENT_CHANGED = "dm.document.changed"
EVENT_INCIDENT_LOGGED = "hs.incident.logged"
EVENT_CERT_CHANGED = "hr.certification.changed"

# Academic Misconduct + Disciplinary Portal share one lifecycle. Single
# event family lets HR profiles, Grade Tracking, the chatbot, and the
# evidence panel all subscribe without caring which subsystem opened
# the case.
EVENT_CASE_OPENED = "case.opened"
EVENT_CASE_CLOSED = "case.closed"
EVENT_SANCTION_APPLIED = "case.sanction.applied"

# Student Union events. Advocacy is opt-in: the chatbot prompts the
# subject after a case is opened, and only on user reply does this
# fire — SU never receives a feed of every disciplinary case.
EVENT_SU_ADVOCACY_REQUESTED = "su.advocacy.requested"
EVENT_MEMBERSHIP_CHANGED = "su.membership.changed"

# Careers / employer / engagement lifecycle. One event family covers
# job/internship/placement/apprenticeship/mentorship since they share
# the engagement model in careers_bus.
EVENT_ENGAGEMENT_STARTED = "careers.engagement.started"
EVENT_ENGAGEMENT_ENDED = "careers.engagement.ended"
EVENT_HOURS_LOGGED = "careers.hours.logged"
EVENT_JOB_POSTED = "careers.job.posted"

# Trips + Parking. Trip events feed Calendar / Finance / Cases / DM
# subscribers; parking violations feed Finance and (on repeat) Cases.
EVENT_TRIP_CREATED = "trip.created"
EVENT_TRIP_REGISTRATION_CHANGED = "trip.registration.changed"
EVENT_PARKING_VIOLATION = "parking.violation"

# Restaurant + Email. Meal-plan and POS spend ride on
# EVENT_CHARGE_RAISED already; this event fires *additionally* on
# meal-plan top-ups so RestaurantPanel and the chatbot menu tool can
# refresh distinctly. EVENT_EMAIL_SENT is the audit-trail signal for
# the email_bus subscriber.
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

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_subscribers: dict[str, list[Callable[..., None]]] = {}


def subscribe(event: str, callback: Callable[..., None]) -> Callable[[], None]:
    """Subscribe a raw callback. Returns an ``unsubscribe()`` function."""
    with _lock:
        _subscribers.setdefault(event, []).append(callback)

    def _unsubscribe() -> None:
        with _lock:
            try:
                _subscribers.get(event, []).remove(callback)
            except ValueError:
                pass

    return _unsubscribe


def subscribe_tk(
    event: str,
    widget: tk.Misc,
    callback: Callable[..., None],
) -> Callable[[], None]:
    """Subscribe a Tk-bound callback.

    ``callback`` will run on the widget's main loop via
    ``widget.after_idle``. Auto-unsubscribed when the widget is
    destroyed (we bind <Destroy> with add="+", filtered to the widget
    itself so child destructions don't fire it).
    """
    def _wrapped(**payload: Any) -> None:
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            widget.after_idle(_safe_call, callback, payload)
        except tk.TclError:
            # Widget disappeared between winfo_exists and after_idle
            pass

    unsub = subscribe(event, _wrapped)

    def _on_destroy(_event: "tk.Event") -> None:
        if _event.widget is widget:
            unsub()

    try:
        widget.bind("<Destroy>", _on_destroy, add="+")
    except tk.TclError:
        # Widget already gone — drop the subscription immediately
        unsub()

    return unsub


def publish(event: str, **payload: Any) -> None:
    """Fire ``event`` to every current subscriber.

    Returns immediately. Each subscriber is called inside its own
    try/except so a broken listener can't stop the others.
    """
    with _lock:
        listeners = list(_subscribers.get(event, ()))
    if not listeners:
        return
    for cb in listeners:
        try:
            cb(**payload)
        except Exception as exc:  # noqa: BLE001 — log + continue intentional
            logger.warning(
                "event-bus subscriber for %s raised: %s", event, exc,
            )


def _safe_call(callback: Callable[..., None], payload: dict[str, Any]) -> None:
    """after_idle landing target — runs on the Tk thread."""
    try:
        callback(**payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tk subscriber raised on idle: %s", exc)


def reset_for_tests() -> None:
    """Clear all subscriptions. Test-only helper."""
    with _lock:
        _subscribers.clear()


__all__ = [
    "EVENT_EXAM_CHANGED",
    "EVENT_GRADE_CHANGED",
    "EVENT_MODULE_SCHEDULE_CHANGED",
    "EVENT_COURSE_CHANGED",
    "EVENT_ENROLMENT_CHANGED",
    "EVENT_ASSESSMENT_CHANGED",
    "EVENT_ASSIGNMENT_CHANGED",
    "EVENT_CALENDAR_CHANGED",
    "EVENT_CHARGE_RAISED",
    "EVENT_HOLD_CHANGED",
    "EVENT_READING_LIST_CHANGED",
    "EVENT_LOAN_CHANGED",
    "EVENT_TERM_CHANGED",
    "EVENT_SELECTION_CHANGED",
    "EVENT_STAFF_AVAILABILITY_CHANGED",
    "EVENT_DOCUMENT_CHANGED",
    "EVENT_INCIDENT_LOGGED",
    "EVENT_CERT_CHANGED",
    "EVENT_CASE_OPENED",
    "EVENT_CASE_CLOSED",
    "EVENT_SANCTION_APPLIED",
    "EVENT_SU_ADVOCACY_REQUESTED",
    "EVENT_MEMBERSHIP_CHANGED",
    "EVENT_ENGAGEMENT_STARTED",
    "EVENT_ENGAGEMENT_ENDED",
    "EVENT_HOURS_LOGGED",
    "EVENT_JOB_POSTED",
    "EVENT_TRIP_CREATED",
    "EVENT_TRIP_REGISTRATION_CHANGED",
    "EVENT_PARKING_VIOLATION",
    "EVENT_MEAL_PLAN_CHANGED",
    "EVENT_EMAIL_SENT",
    "ALL_EVENTS",
    "subscribe",
    "subscribe_tk",
    "publish",
    "reset_for_tests",
]
