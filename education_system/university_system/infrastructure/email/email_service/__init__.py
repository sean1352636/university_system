"""Core email processing services.

This package was split from a single email_service.py module.
All public names are re-exported here for backward compatibility.
"""

from __future__ import annotations

# === Core sending engine ===
from education_system.university_system.infrastructure.email.email_service.core import (
    _get_current_auth,
    auth,
    safe_log_email,
    send_email,
    send_email_db_only,
    send_email_as_user,
    send_email_as_system,
    send_template_email,
    get_appropriate_sender_id,
    generate_system_username,
    # Re-export imported names that callers access via this module
    IMMUTABLE_AUDIT_AVAILABLE,
    mask_sensitive_data,
)

# === Stored email CRUD ===
from education_system.university_system.infrastructure.email.email_service.storage import (
    get_stored_emails,
    delete_stored_email,
    clear_stored_emails,
)

# === Queue and worker management ===
from education_system.university_system.infrastructure.email.email_service.queue import (
    email_queue,
    worker_threads,
    worker_threads_lock,
    stop_workers_event,
    email_worker,
    start_email_workers,
    stop_email_workers,
    queue_email,
    queue_template_email,
    wait_for_email_queue,
)

# === Bulk send and scheduling ===
from education_system.university_system.infrastructure.email.email_service.scheduling import (
    scheduled_jobs,
    scheduled_jobs_lock,
    send_bulk,
    schedule_send,
    process_scheduled_emails,
    ensure_scheduler_running,
    run_scheduler,
    update_scheduled_email_status,
)

# === Interactive CLI forms ===
from education_system.university_system.infrastructure.email.email_service.cli import (
    send_batch_email_form,
    schedule_email_form,
    display_stored_emails_menu,
)

# === Maintenance and diagnostics ===
from education_system.university_system.infrastructure.email.email_service.maintenance import (
    fix_inbox_display_issue,
    fix_existing_email_senders,
    test_sender_attribution,
)

# === Domain-specific notifications ===
from education_system.university_system.infrastructure.email.email_service.notifications import (
    # Academic
    send_registration_confirmation,
    send_update_confirmation,
    send_grade_notification,
    send_password_reset,
    send_assignment_notification,
    send_extension_notification,
    send_confirmation_email,
    # Helpdesk
    send_ticket_notification,
    send_reply_notification,
    send_sla_alert,
    send_satisfaction_survey,
    send_bulk_satisfaction_surveys,
    # Health
    send_appointment_confirmation,
    send_health_notification,
    # Internship
    send_internship_notification,
    send_application_confirmation,
    # Alumni
    send_alumni_welcome_email,
    send_mentorship_notification,
    send_event_invitation,
    send_donation_receipt,
    # Parking
    send_permit_confirmation,
    send_permit_update_confirmation,
    # Library
    send_book_checkout_confirmation,
    send_book_return_reminder,
    send_overdue_notification,
    # Schedule changes
    send_schedule_change_notification,
)

# === Re-export dependencies that external code accesses via this module ===
# (e.g. email/__init__.py accesses _email_service_module.config, .execute_db_operation, etc.)
from education_system.university_system.infrastructure.email.config import config
from education_system.university_system.infrastructure.email.email_db_utilities import _ensure_db_ready, execute_db_operation
from education_system.university_system.core.logs import handle_exception, log_event
from education_system.university_system.infrastructure.email.templates import (
    ensure_templates_directory,
    list_templates,
    load_template,
    render_template,
    template_management_menu,
)
from education_system.university_system.infrastructure.exceptions import (
    EmailError,
    EmailDeliveryError,
    TemplateError,
    AttachmentError,
    ValidationError,
    InvalidInputError,
)
