"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
import secrets

from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.context import auth

def generate_qr_code():
    """Generate a QR code string that admits one attendee to one event.

    ``secrets``, not ``random``: this value is the whole proof of admission,
    stored on the registration row and presented at the door. ``random`` is a
    Mersenne Twister — observing a run of issued codes recovers its internal
    state and yields every subsequent code, so a batch printed for one event
    would expose the codes for the next.
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))
