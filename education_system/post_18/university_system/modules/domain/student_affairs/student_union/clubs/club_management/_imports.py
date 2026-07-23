# Standard library imports
import os
import random
import string
from datetime import datetime
from typing import Optional

# Third-party/database imports
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.infrastructure.database.db import DatabaseManager, get_connection

# Service imports
try:
    from education_system.post_18.university_system.infrastructure.email import send_confirmation_email
except Exception:  # pragma: no cover - optional dependency
    def send_confirmation_email(*_args, **_kwargs):
        return False

try:
    from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
except Exception:  # pragma: no cover - optional dependency
    AcademicCalendarManager = None

# Authentication import with fallback
try:
    from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    # Fallback class for type hints when import fails
    class UserAuth:  # type: ignore
        pass
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Global auth instance
auth: Optional[UserAuth] = None

def set_auth(auth_obj: UserAuth) -> None:
    """Inject the shared authentication instance for this module."""
    global auth
    auth = auth_obj
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_obj)
    # Keep package-level auth in sync for tests that assign on the package.
    try:
        import sys
        pkg = sys.modules.get(
            "education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management"
        )
        if pkg is not None:
            setattr(pkg, "auth", auth_obj)
    except Exception:
        pass

def get_auth() -> Optional[UserAuth]:
    """Return the current auth instance, syncing with package attribute if set."""
    global auth
    try:
        import sys
        pkg = sys.modules.get(
            "education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management"
        )
        if pkg is not None:
            pkg_auth = getattr(pkg, "auth", None)
            if pkg_auth is not auth:
                auth = pkg_auth
    except Exception:
        pass
    return auth

def resolve_get_connection():
    """Return the get_connection callable, honoring package-level overrides."""
    try:
        import sys
        pkg = sys.modules.get(
            "education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management"
        )
        if pkg is not None:
            pkg_conn = getattr(pkg, "get_connection", None)
            if pkg_conn is not None and pkg_conn is not get_connection:
                return pkg_conn
    except Exception:
        pass
    return get_connection

def resolve_send_confirmation_email():
    """Return the send_confirmation_email callable, honoring package-level overrides."""
    try:
        import sys
        pkg = sys.modules.get(
            "education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management"
        )
        if pkg is not None:
            pkg_sender = getattr(pkg, "send_confirmation_email", None)
            if pkg_sender is not None and pkg_sender is not send_confirmation_email:
                return pkg_sender
    except Exception:
        pass
    return send_confirmation_email
