"""Deprecated compatibility façade for student-union event management."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application import (
    ports,
)
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.infrastructure import (
    qr_codes,
)
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.reporting import (
    financial_report,
)
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events import (
    analytics,
    attendance,
    catalogue,
    context,
    finances,
    knowledge_sharing,
    menu,
    recurring,
    registrations,
    sustainability,
    ticketing,
    virtual,
)

auth = None
get_connection = ports.get_connection
send_confirmation_email = ports.send_confirmation_email

_WORKFLOW_MODULES = (
    analytics,
    attendance,
    catalogue,
    finances,
    knowledge_sharing,
    menu,
    recurring,
    registrations,
    sustainability,
    ticketing,
    virtual,
    financial_report,
    qr_codes,
)


def _sync_legacy_overrides() -> None:
    """Propagate patched façade dependencies during the deprecation window."""
    context.set_auth(auth)
    for module in _WORKFLOW_MODULES:
        if hasattr(module, "get_connection"):
            module.get_connection = get_connection
        if hasattr(module, "send_confirmation_email"):
            module.send_confirmation_email = send_confirmation_email
    registrations.view_events = view_events


def set_auth(auth_obj) -> None:
    global auth
    auth = auth_obj
    context.set_auth(auth_obj)


def _delegate(module, name: str) -> Callable[..., Any]:
    target = getattr(module, name)

    @wraps(target)
    def compatible(*args, **kwargs):
        _sync_legacy_overrides()
        return target(*args, **kwargs)

    return compatible


view_events = _delegate(catalogue, "view_events")
create_event = _delegate(catalogue, "create_event")
register_for_event = _delegate(registrations, "register_for_event")
view_my_events = _delegate(registrations, "view_my_events")
_manage_event_attendance_simple = _delegate(
    attendance, "_manage_event_attendance_simple"
)
manage_event_attendance = _delegate(attendance, "manage_event_attendance")
_track_event_finances_simple = _delegate(finances, "_track_event_finances_simple")
track_event_finances = _delegate(finances, "track_event_finances")
_create_recurring_event_simple = _delegate(
    recurring, "_create_recurring_event_simple"
)
create_recurring_event = _delegate(recurring, "create_recurring_event")
manage_recurring_events = _delegate(recurring, "manage_recurring_events")
manage_event_tickets = _delegate(ticketing, "manage_event_tickets")
generate_event_financial_report = _delegate(
    financial_report, "generate_event_financial_report"
)
generate_qr_code = _delegate(qr_codes, "generate_qr_code")
manage_sustainable_events = _delegate(
    sustainability, "manage_sustainable_events"
)
event_popularity_predictions = _delegate(
    analytics, "event_popularity_predictions"
)
view_event_analytics = _delegate(analytics, "view_event_analytics")
manage_virtual_events = _delegate(virtual, "manage_virtual_events")
create_virtual_event = _delegate(virtual, "create_virtual_event")
setup_hybrid_event = _delegate(virtual, "setup_hybrid_event")
virtual_attendance_tracking = _delegate(
    virtual, "virtual_attendance_tracking"
)
virtual_event_tech_support = _delegate(virtual, "virtual_event_tech_support")
knowledge_sharing_sessions = _delegate(
    knowledge_sharing, "knowledge_sharing_sessions"
)
display_event_menu = _delegate(menu, "display_event_menu")

__all__ = [
    "set_auth",
    "view_events",
    "register_for_event",
    "view_my_events",
    "_manage_event_attendance_simple",
    "_track_event_finances_simple",
    "_create_recurring_event_simple",
    "track_event_finances",
    "manage_event_tickets",
    "generate_event_financial_report",
    "generate_qr_code",
    "manage_event_attendance",
    "create_recurring_event",
    "manage_recurring_events",
    "manage_sustainable_events",
    "event_popularity_predictions",
    "manage_virtual_events",
    "create_virtual_event",
    "setup_hybrid_event",
    "virtual_attendance_tracking",
    "virtual_event_tech_support",
    "knowledge_sharing_sessions",
    "create_event",
    "view_event_analytics",
    "display_event_menu",
]
