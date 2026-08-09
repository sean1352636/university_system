"""Small, intentional public API for integration features."""
from .bootstrap import reset_for_tests, wire_subscribers
from .publishing import log_and_publish
from .persistence.event_log import recent_events
from .persistence.student_lookup import resolve_student_id

__all__ = [
    "log_and_publish", "recent_events", "resolve_student_id",
    "wire_subscribers", "reset_for_tests",
]
