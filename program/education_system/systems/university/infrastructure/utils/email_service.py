"""Stub implementation of the email service.

This module provides simplified placeholders for the functions and
variables exposed by the real email service in the university system.
The primary purpose is to satisfy imports in unit tests without
performing any actual email sending or scheduling.

For production use, import from:
    university_system.infrastructure.email.email_service

This stub module will attempt to delegate to the real implementation
when available, falling back to mock behavior for testing.
"""

from __future__ import annotations

import warnings
from enum import Enum
from threading import Thread
from typing import Any, Dict, List, Optional, Tuple

# Try to import the real email service implementation
_REAL_EMAIL_SERVICE_AVAILABLE = False
_real_email_service = None

try:
    from education_system.systems.university.infrastructure.email import email_service as _real_email_service
    _REAL_EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    pass


def _delegate_or_stub(func_name: str, *args: Any, **kwargs: Any) -> Any:
    """Delegate to real email service if available, otherwise use stub."""
    if _REAL_EMAIL_SERVICE_AVAILABLE and hasattr(_real_email_service, func_name):
        return getattr(_real_email_service, func_name)(*args, **kwargs)
    return None


class EmailTemplate(Enum):
    """Enum for all email template types used in the system."""
    REGISTRATION_CONFIRMATION = "user_management/registration_confirmation"
    UPDATE_CONFIRMATION = "update_confirmation"
    GRADE_NOTIFICATION = "grade_notification"
    PASSWORD_RESET = "password_reset"
    ASSIGNMENT_NOTIFICATION = "assignment_notification"
    EXTENSION_NOTIFICATION = "extension_notification"
    CONFIRMATION_EMAIL = "confirmation_email"
    BATCH_EMAIL_FORM = "batch_email_form"
    TICKET_NOTIFICATION = "ticket_notification"
    REPLY_NOTIFICATION = "reply_notification"
    APPOINTMENT_CONFIRMATION = "appointment_confirmation"
    HEALTH_NOTIFICATION = "health_notification"
    INTERNSHIP_NOTIFICATION = "internship_notification"
    APPLICATION_CONFIRMATION = "application_confirmation"
    ALUMNI_WELCOME_EMAIL = "alumni_welcome_email"
    MENTORSHIP_NOTIFICATION = "mentorship_notification"
    EVENT_INVITATION = "event_invitation"
    DONATION_RECEIPT = "donation_receipt"
    PERMIT_CONFIRMATION = "permit_confirmation"
    PERMIT_UPDATE_CONFIRMATION = "permit_update_confirmation"
    BOOK_CHECKOUT_CONFIRMATION = "book_checkout_confirmation"
    BOOK_RETURN_REMINDER = "book_return_reminder"
    OVERDUE_NOTIFICATION = "overdue_notification"
    SLA_ALERT = "sla_alert"
    SATISFACTION_SURVEY = "satisfaction_survey"

__all__ = [
    # Enums
    'EmailTemplate',
    # Core email functionality
    'email_queue', 'worker_threads', 'stop_workers', 'scheduled_jobs',
    'safe_log_email', 'send_email', 'send_email_db_only',
    'fix_inbox_display_issue', 'generate_system_username',
    'send_email_as_user', 'send_email_as_system', 'get_appropriate_sender_id',
    'send_template_email', 'get_stored_emails', 'delete_stored_email',
    'clear_stored_emails', 'email_worker', 'start_email_workers',
    'stop_email_workers', 'queue_email', 'queue_template_email',
    'wait_for_email_queue', 'send_bulk', 'schedule_send',
    'process_scheduled_emails', 'ensure_scheduler_running', 'run_scheduler',
    'update_scheduled_email_status',
    # Legacy stub functions (DEPRECATED - use send_template_email with EmailTemplate enum)
    'send_registration_confirmation',
    'send_update_confirmation', 'send_grade_notification', 'send_password_reset',
    'send_assignment_notification', 'send_extension_notification',
    'send_confirmation_email', 'send_batch_email_form', 'schedule_email_form',
    'send_ticket_notification', 'send_reply_notification',
    'send_appointment_confirmation', 'send_health_notification',
    'send_internship_notification', 'send_application_confirmation',
    'send_alumni_welcome_email', 'send_mentorship_notification',
    'send_event_invitation', 'send_donation_receipt', 'send_permit_confirmation',
    'send_permit_update_confirmation', 'send_book_checkout_confirmation',
    'send_book_return_reminder', 'send_overdue_notification',
    'display_stored_emails_menu', 'send_sla_alert', 'send_satisfaction_survey',
    'send_bulk_satisfaction_surveys', 'fix_existing_email_senders',
    'test_sender_attribution'
]

# Simple in‑memory email queue and worker tracking
email_queue: List[Dict[str, Any]] = []
worker_threads: List[Thread] = []
scheduled_jobs: List[Tuple[Dict[str, Any], float]] = []


def safe_log_email(*args: Any, **kwargs: Any) -> None:
    """Log email details safely (no‑op)."""
    return None


def send_email(*args: Any, **kwargs: Any) -> Any:
    """Send an email immediately (delegates to real service if available)."""
    if _REAL_EMAIL_SERVICE_AVAILABLE:
        return _delegate_or_stub('send_email', *args, **kwargs)
    # In the stub, just append to email_queue for visibility
    email_queue.append({'type': 'immediate', 'args': args, 'kwargs': kwargs})
    return None


def send_email_db_only(*args: Any, **kwargs: Any) -> None:
    """Store an email in the database only (stub)."""
    email_queue.append({'type': 'db_only', 'args': args, 'kwargs': kwargs})


def fix_inbox_display_issue(*args: Any, **kwargs: Any) -> None:
    return None


def generate_system_username(*args: Any, **kwargs: Any) -> str:
    return 'system'


def send_email_as_user(*args: Any, **kwargs: Any) -> None:
    return send_email(*args, **kwargs)


def send_email_as_system(*args: Any, **kwargs: Any) -> None:
    return send_email(*args, **kwargs)


def get_appropriate_sender_id(*args: Any, **kwargs: Any) -> str:
    return 'system'


def send_template_email(*args: Any, **kwargs: Any) -> Any:
    """Send a templated email (delegates to real service if available)."""
    if _REAL_EMAIL_SERVICE_AVAILABLE:
        return _delegate_or_stub('send_template_email', *args, **kwargs)
    return send_email(*args, **kwargs)


def get_stored_emails(*args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    return email_queue.copy()


def delete_stored_email(*args: Any, **kwargs: Any) -> None:
    return None


def clear_stored_emails(*args: Any, **kwargs: Any) -> None:
    email_queue.clear()


def email_worker(*args: Any, **kwargs: Any) -> None:
    return None


def start_email_workers(*args: Any, **kwargs: Any) -> None:
    return None

def start_workers(*args: Any, **kwargs: Any) -> None:
    """Alias for start_email_workers to maintain backwards compatibility."""
    return start_email_workers(*args, **kwargs)


def stop_email_workers(*args: Any, **kwargs: Any) -> None:
    worker_threads.clear()
    return None


# ---------------------------------------------------------------------------
# Backwards‑compatibility aliases
#
# Some parts of the system refer to ``stop_workers`` on the email_service.
# Define it here as an alias to ``stop_email_workers`` to prevent
# AttributeError.
def stop_workers(*args: Any, **kwargs: Any) -> None:
    """Alias for stop_email_workers to maintain backwards compatibility."""
    return stop_email_workers(*args, **kwargs)


def queue_email(*args: Any, **kwargs: Any) -> Any:
    """Queue an email for sending (delegates to real service if available)."""
    if _REAL_EMAIL_SERVICE_AVAILABLE:
        return _delegate_or_stub('queue_email', *args, **kwargs)
    email_queue.append({'type': 'queued', 'args': args, 'kwargs': kwargs})
    return None


def queue_template_email(*args: Any, **kwargs: Any) -> None:
    return queue_email(*args, **kwargs)


def wait_for_email_queue(*args: Any, **kwargs: Any) -> None:
    return None


def send_bulk(*args: Any, **kwargs: Any) -> None:
    return None


def schedule_send(*args: Any, **kwargs: Any) -> None:
    # schedule job at current time in stub
    scheduled_jobs.append(({'args': args, 'kwargs': kwargs}, 0.0))
    return None


def process_scheduled_emails(*args: Any, **kwargs: Any) -> None:
    return None


def ensure_scheduler_running(*args: Any, **kwargs: Any) -> None:
    return None


def run_scheduler(*args: Any, **kwargs: Any) -> None:
    return None


def update_scheduled_email_status(*args: Any, **kwargs: Any) -> None:
    return None


# =============================================================================
# BACKWARDS COMPATIBILITY WRAPPERS (DEPRECATED)
# =============================================================================
# These functions are provided for backwards compatibility and testing.
# In production, they delegate to the real email service implementation.
# For new code, use send_template_email(EmailTemplate.XXX, recipient, vars) instead.
# =============================================================================


def _deprecated_email_function(func_name: str, template: EmailTemplate, *args: Any, **kwargs: Any) -> Any:
    """Helper to handle deprecated email function calls."""
    # Delegate to real service if available
    if _REAL_EMAIL_SERVICE_AVAILABLE and hasattr(_real_email_service, func_name):
        return getattr(_real_email_service, func_name)(*args, **kwargs)
    # Fall back to stub behavior
    return send_email(*args, **kwargs)


def send_registration_confirmation(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.REGISTRATION_CONFIRMATION, ...) instead."""
    return _deprecated_email_function('send_registration_confirmation', EmailTemplate.REGISTRATION_CONFIRMATION, *args, **kwargs)


def send_update_confirmation(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.UPDATE_CONFIRMATION, ...) instead."""
    return _deprecated_email_function('send_update_confirmation', EmailTemplate.UPDATE_CONFIRMATION, *args, **kwargs)


def send_grade_notification(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.GRADE_NOTIFICATION, ...) instead."""
    return _deprecated_email_function('send_grade_notification', EmailTemplate.GRADE_NOTIFICATION, *args, **kwargs)


def send_password_reset(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.PASSWORD_RESET, ...) instead."""
    return _deprecated_email_function('send_password_reset', EmailTemplate.PASSWORD_RESET, *args, **kwargs)


def send_assignment_notification(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.ASSIGNMENT_NOTIFICATION, ...) instead."""
    return _deprecated_email_function('send_assignment_notification', EmailTemplate.ASSIGNMENT_NOTIFICATION, *args, **kwargs)


def send_extension_notification(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.EXTENSION_NOTIFICATION, ...) instead."""
    return _deprecated_email_function('send_extension_notification', EmailTemplate.EXTENSION_NOTIFICATION, *args, **kwargs)


def send_confirmation_email(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.CONFIRMATION_EMAIL, ...) instead."""
    return _deprecated_email_function('send_confirmation_email', EmailTemplate.CONFIRMATION_EMAIL, *args, **kwargs)


def send_batch_email_form(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.BATCH_EMAIL_FORM, ...) instead."""
    return _deprecated_email_function('send_batch_email_form', EmailTemplate.BATCH_EMAIL_FORM, *args, **kwargs)


def schedule_email_form(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use schedule_send with EmailTemplate enum instead."""
    if _REAL_EMAIL_SERVICE_AVAILABLE and hasattr(_real_email_service, 'schedule_email_form'):
        return _real_email_service.schedule_email_form(*args, **kwargs)
    return schedule_send(*args, **kwargs)


def send_ticket_notification(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.TICKET_NOTIFICATION, ...) instead."""
    return _deprecated_email_function('send_ticket_notification', EmailTemplate.TICKET_NOTIFICATION, *args, **kwargs)


def send_reply_notification(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.REPLY_NOTIFICATION, ...) instead."""
    return _deprecated_email_function('send_reply_notification', EmailTemplate.REPLY_NOTIFICATION, *args, **kwargs)


def send_appointment_confirmation(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.APPOINTMENT_CONFIRMATION, ...) instead."""
    return _deprecated_email_function('send_appointment_confirmation', EmailTemplate.APPOINTMENT_CONFIRMATION, *args, **kwargs)


def send_health_notification(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.HEALTH_NOTIFICATION, ...) instead."""
    return _deprecated_email_function('send_health_notification', EmailTemplate.HEALTH_NOTIFICATION, *args, **kwargs)


def send_internship_notification(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.INTERNSHIP_NOTIFICATION, ...) instead."""
    return _deprecated_email_function('send_internship_notification', EmailTemplate.INTERNSHIP_NOTIFICATION, *args, **kwargs)


def send_application_confirmation(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.APPLICATION_CONFIRMATION, ...) instead."""
    return _deprecated_email_function('send_application_confirmation', EmailTemplate.APPLICATION_CONFIRMATION, *args, **kwargs)


def send_alumni_welcome_email(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.ALUMNI_WELCOME_EMAIL, ...) instead."""
    return _deprecated_email_function('send_alumni_welcome_email', EmailTemplate.ALUMNI_WELCOME_EMAIL, *args, **kwargs)


def send_mentorship_notification(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.MENTORSHIP_NOTIFICATION, ...) instead."""
    return _deprecated_email_function('send_mentorship_notification', EmailTemplate.MENTORSHIP_NOTIFICATION, *args, **kwargs)


def send_event_invitation(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.EVENT_INVITATION, ...) instead."""
    return _deprecated_email_function('send_event_invitation', EmailTemplate.EVENT_INVITATION, *args, **kwargs)


def send_donation_receipt(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.DONATION_RECEIPT, ...) instead."""
    return _deprecated_email_function('send_donation_receipt', EmailTemplate.DONATION_RECEIPT, *args, **kwargs)


def send_permit_confirmation(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.PERMIT_CONFIRMATION, ...) instead."""
    return _deprecated_email_function('send_permit_confirmation', EmailTemplate.PERMIT_CONFIRMATION, *args, **kwargs)


def send_permit_update_confirmation(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.PERMIT_UPDATE_CONFIRMATION, ...) instead."""
    return _deprecated_email_function('send_permit_update_confirmation', EmailTemplate.PERMIT_UPDATE_CONFIRMATION, *args, **kwargs)


def send_book_checkout_confirmation(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.BOOK_CHECKOUT_CONFIRMATION, ...) instead."""
    return _deprecated_email_function('send_book_checkout_confirmation', EmailTemplate.BOOK_CHECKOUT_CONFIRMATION, *args, **kwargs)


def send_book_return_reminder(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.BOOK_RETURN_REMINDER, ...) instead."""
    return _deprecated_email_function('send_book_return_reminder', EmailTemplate.BOOK_RETURN_REMINDER, *args, **kwargs)


def send_overdue_notification(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.OVERDUE_NOTIFICATION, ...) instead."""
    return _deprecated_email_function('send_overdue_notification', EmailTemplate.OVERDUE_NOTIFICATION, *args, **kwargs)


def send_sla_alert(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.SLA_ALERT, ...) instead."""
    return _deprecated_email_function('send_sla_alert', EmailTemplate.SLA_ALERT, *args, **kwargs)


def send_satisfaction_survey(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_template_email(EmailTemplate.SATISFACTION_SURVEY, ...) instead."""
    return _deprecated_email_function('send_satisfaction_survey', EmailTemplate.SATISFACTION_SURVEY, *args, **kwargs)


def send_bulk_satisfaction_surveys(*args: Any, **kwargs: Any) -> Any:
    """DEPRECATED: Use send_bulk with EmailTemplate.SATISFACTION_SURVEY instead."""
    if _REAL_EMAIL_SERVICE_AVAILABLE and hasattr(_real_email_service, 'send_bulk_satisfaction_surveys'):
        return _real_email_service.send_bulk_satisfaction_surveys(*args, **kwargs)
    return send_email(*args, **kwargs)

# Placeholder functions - no-ops for testing
def display_stored_emails_menu(*args: Any, **kwargs: Any) -> None:
    """No-op placeholder for testing."""
    return None

def fix_existing_email_senders(*args: Any, **kwargs: Any) -> None:
    """No-op placeholder for testing."""
    return None

def test_sender_attribution(*args: Any, **kwargs: Any) -> None:
    """No-op placeholder for testing."""
    return None
