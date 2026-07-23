"""Utility functions for the Campus Public Safety Management System."""

import logging

logger = logging.getLogger(__name__)


def get_current_user():
    """Get the current authenticated user from the system."""
    try:
        from education_system.post_18.university_system.infrastructure.shared_context import get_current_user as get_user
        user = get_user()
        if user:
            return user
    except ImportError:
        pass
    return None


def send_notification_email(recipient_email, subject, body):
    """Send notification email."""
    # Validate email address before attempting to send
    if not recipient_email or not isinstance(recipient_email, str):
        logger.debug("No recipient email provided, skipping notification")
        return False

    recipient_email = recipient_email.strip()
    if not recipient_email or '@' not in recipient_email:
        logger.debug(f"Invalid email address: {recipient_email}, skipping notification")
        return False

    try:
        from education_system.post_18.university_system.infrastructure.email.email_service import send_email
        result = send_email(recipient_email, subject, body)
        if result:
            logger.info(f"Email sent to {recipient_email}: {subject}")
            return True
        return False
    except Exception as e:
        logger.warning(f"Failed to send email: {e}")
        return False


def get_admin_emails():
    """Get list of admin user emails for notifications."""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT email FROM users WHERE role IN ('admin', 'security_admin', 'police_chief') AND email IS NOT NULL"
            )
            return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []


def get_officer_email(officer_badge):
    """Get officer email by badge number."""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT email FROM users WHERE badge_number = ? OR username = ?",
                (officer_badge, officer_badge)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception:
        return None
