"""Domain-specific email notification functions."""

from education_system.post_18.university_system.infrastructure.email.email_service.notifications.academic import (
    send_registration_confirmation,
    send_update_confirmation,
    send_grade_notification,
    send_password_reset,
    send_assignment_notification,
    send_extension_notification,
    send_confirmation_email,
)
from education_system.post_18.university_system.infrastructure.email.email_service.notifications.helpdesk import (
    send_ticket_notification,
    send_reply_notification,
    send_sla_alert,
    send_satisfaction_survey,
    send_bulk_satisfaction_surveys,
)
from education_system.post_18.university_system.infrastructure.email.email_service.notifications.health import (
    send_appointment_confirmation,
    send_health_notification,
)
from education_system.post_18.university_system.infrastructure.email.email_service.notifications.internship import (
    send_internship_notification,
    send_application_confirmation,
)
from education_system.post_18.university_system.infrastructure.email.email_service.notifications.alumni import (
    send_alumni_welcome_email,
    send_mentorship_notification,
    send_event_invitation,
    send_donation_receipt,
)
from education_system.post_18.university_system.infrastructure.email.email_service.notifications.parking import (
    send_permit_confirmation,
    send_permit_update_confirmation,
)
from education_system.post_18.university_system.infrastructure.email.email_service.notifications.library import (
    send_book_checkout_confirmation,
    send_book_return_reminder,
    send_overdue_notification,
)
from education_system.post_18.university_system.infrastructure.email.email_service.notifications.schedule_change import (
    send_schedule_change_notification,
)
