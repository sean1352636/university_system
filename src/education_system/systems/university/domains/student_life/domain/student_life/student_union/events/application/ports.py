from __future__ import annotations
import os
import random
import string
from datetime import datetime
from typing import Optional, Protocol, Any
from education_system.systems.university.infrastructure.database.db import (
    DatabaseManager, get_connection, sqlite3,
)

try:
    from education_system.systems.university.infrastructure.email import send_confirmation_email
except Exception:
    def send_confirmation_email(*_args, **_kwargs):
        return False

try:
    from education_system.systems.university.domains.teaching.domain.academic_calendar.calendar_core import AcademicCalendarManager
except Exception:
    AcademicCalendarManager = None

from education_system.systems.university.infrastructure.institution_settings import get_events_support_phone

try:
    from education_system.systems.university.infrastructure.auth import (
        UserAuth, get_current_user, set_auth_instance,
    )
    HAS_AUTH = True
except ImportError:
    class UserAuth:
        pass
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

class EventRepository(Protocol):
    def get(self, event_id: int) -> Any: ...

class EmailGateway(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> bool: ...

class CalendarGateway(Protocol):
    def add_event(self, event: Any) -> Any: ...

class QRCodeGateway(Protocol):
    def generate(self, payload: str) -> str: ...
