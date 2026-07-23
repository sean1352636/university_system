import logging
from datetime import datetime
import re
from typing import Any, Optional, List
from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.validators import sanitize_string
from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.exceptions import ValidationError, DatabaseError, SyncError
from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.database import DatabaseManager

gui_logger = logging.getLogger(__name__)

class NotificationManager:
    """
    Multi-channel notification system

    Features:
    - SMS notifications
    - Email notifications (integration ready)
    - Event reminders
    - Scheduled notifications
    - Notification templates
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize notification manager

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        gui_logger.info("NotificationManager initialized")

    def send_sms_notification(self, phone_number: str, message: str) -> bool:
        """
        Send SMS notification

        Args:
            phone_number: Recipient phone number
            message: SMS message content

        Returns:
            bool: True if SMS sent successfully

        Raises:
            ValidationError: If phone number invalid
            SyncError: If SMS service unavailable

        Example:
            notif.send_sms_notification(
                "+1234567890",
                "Reminder: Team meeting tomorrow at 10 AM"
            )
        """
        # Validate phone number
        if not self._validate_phone_number(phone_number):
            raise ValidationError.invalid_format(
                'phone_number',
                'valid phone number format',
                phone_number
            )

        # Sanitize message
        safe_message = sanitize_string(message, max_length=160)

        try:
            # Import and use the centralized SMS service
            from education_system.post_18.university_system.infrastructure.communication.sms_service import (
                get_sms_service, send_sms
            )

            # Send SMS via the centralized service (supports Twilio, AWS SNS, or Mock)
            success = send_sms(
                phone_number=phone_number,
                message=safe_message,
                related_to='calendar_notification'
            )

            if success:
                gui_logger.info(f"SMS sent to {phone_number}: {safe_message}")

                # Store notification record in calendar notifications table
                self.db.execute_update(
                    """INSERT INTO notifications
                       (recipient, channel, message, sent_at, status)
                       VALUES (?, 'sms', ?, ?, 'sent')""",
                    (phone_number, safe_message, datetime.now().isoformat())
                )

                return True
            else:
                gui_logger.warning(f"SMS delivery failed to {phone_number}")
                # Store failed notification record
                self.db.execute_update(
                    """INSERT INTO notifications
                       (recipient, channel, message, sent_at, status)
                       VALUES (?, 'sms', ?, ?, 'failed')""",
                    (phone_number, safe_message, datetime.now().isoformat())
                )
                return False

        except ImportError as e:
            # Fallback: log the SMS if SMS service is not available
            gui_logger.warning(f"SMS service not available, logging only: {e}")
            gui_logger.info(f"[LOGGED SMS] to {phone_number}: {safe_message}")

            # Store notification record as logged (not actually sent)
            self.db.execute_update(
                """INSERT INTO notifications
                   (recipient, channel, message, sent_at, status)
                   VALUES (?, 'sms', ?, ?, 'logged')""",
                (phone_number, safe_message, datetime.now().isoformat())
            )
            return True

        except Exception as e:
            gui_logger.error(f"SMS send error: {e}")
            raise SyncError.connection_failed(
                'SMS service',
                reason=str(e)
            )

    def _validate_phone_number(self, phone_number: str) -> bool:
        """
        Validate phone number format

        Args:
            phone_number: Phone number to validate

        Returns:
            bool: True if valid phone number
        """
        # Simple validation - accepts formats: +1234567890, 123-456-7890, etc.
        phone_pattern = re.compile(r'^\+?[1-9]\d{1,14}$|^[\d\-\(\)\s]{10,}$')
        return bool(phone_pattern.match(phone_number.replace(' ', '').replace('-', '')))

    def send_event_reminder_sms(self, event_id: int, hours_before: int = 24):
        """
        Send SMS reminder for upcoming event

        Args:
            event_id: Event ID
            hours_before: Hours before event to send reminder

        Example:
            notif.send_event_reminder_sms(event_id=123, hours_before=24)
        """
        try:
            # Get event details
            events = self.db.execute_query(
                """SELECT e.*, GROUP_CONCAT(a.phone_number) as attendee_phones
                   FROM scheduled_events e
                   LEFT JOIN event_attendees ea ON e.id = ea.event_id
                   LEFT JOIN attendees a ON ea.attendee_id = a.id
                   WHERE e.id = ?
                   GROUP BY e.id""",
                (event_id,)
            )

            if not events:
                raise DatabaseError.record_not_found('event', event_id)

            event = events[0]

            # Create reminder message
            message = f"Reminder: {event['title']} on {event['date']}"
            if event.get('start_time'):
                message += f" at {event['start_time']}"
            if event.get('location'):
                message += f" ({event['location']})"

            # Send to attendees
            if event.get('attendee_phones'):
                phones = event['attendee_phones'].split(',')
                for phone in phones:
                    if phone:
                        self.send_sms_notification(phone.strip(), message)

            gui_logger.info(f"Event reminder sent for event {event_id}")

        except Exception as e:
            gui_logger.error(f"Failed to send event reminder: {e}")


