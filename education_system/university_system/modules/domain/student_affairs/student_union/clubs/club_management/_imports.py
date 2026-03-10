# Standard library imports
import os
import random
import string
from datetime import datetime
from typing import Optional

# Third-party/database imports
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.infrastructure.database.db import DatabaseManager, get_connection

# Service imports
from education_system.university_system.infrastructure.email import send_confirmation_email
from education_system.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager

# Authentication import with fallback
try:
    from education_system.university_system.infrastructure.auth import UserAuth, get_current_user, set_auth_instance
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
