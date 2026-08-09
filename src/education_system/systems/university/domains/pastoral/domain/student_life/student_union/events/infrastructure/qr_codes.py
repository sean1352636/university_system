"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.context import auth

def generate_qr_code():
    """Generate a simple QR code string for event attendance"""
    # Generate a random string for QR code
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
