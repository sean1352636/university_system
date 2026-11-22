"""Shared authentication context for event-management workflows."""
from __future__ import annotations
from typing import Optional

from education_system.systems.university.domains.student_life.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)

auth: Optional[UserAuth] = None

def set_auth(auth_obj: UserAuth) -> None:
    """Inject the shared authentication instance for this module."""
    global auth
    auth = auth_obj
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_obj)
    # Keep extracted workflow modules synchronized with the shared session.
    import sys
    package_prefix = "education_system.systems.university.domains.student_life.interfaces.cli.student_union_events."
    for module_name in (
        "menu", "catalogue", "registrations", "attendance", "ticketing",
        "finances", "recurring", "virtual", "sustainability",
        "knowledge_sharing", "analytics",
    ):
        module = sys.modules.get(package_prefix + module_name)
        if module is not None:
            module.auth = auth_obj
