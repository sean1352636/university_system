import uuid
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.modules.domain.academics.services.academic_calendar.exceptions import CalendarError, ValidationError
from education_system.university_system.modules.domain.academics.services.academic_calendar.config import ValidationUtils
from education_system.university_system.modules.domain.academics.services.academic_calendar.database import DatabaseManager
from education_system.university_system.modules.domain.academics.services.academic_calendar.auth import AuthenticationManager

logger = configure_logging(name=__name__)

try:
    import twilio
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False


class SMSNotificationManager:
    """SMS notification service using Twilio or similar services"""

    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager,
                 sms_config: Dict = None):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self.sms_config = sms_config or {}
        self.client = None

        if TWILIO_AVAILABLE and self.sms_config:
            try:
                self.client = TwilioClient(
                    self.sms_config.get('account_sid'),
                    self.sms_config.get('auth_token')
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Twilio client: {e}")

    def send_sms_notification(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """Send SMS notification"""
        if not self.client:
            return False, "SMS service not configured"

        try:
            # Validate phone number format
            if not self._validate_phone_number(phone_number):
                return False, "Invalid phone number format"

            message_obj = self.client.messages.create(
                body=message,
                from_=self.sms_config.get('from_number'),
                to=phone_number
            )

            logger.info(f"SMS sent successfully: {message_obj.sid}")
            return True, f"SMS sent successfully: {message_obj.sid}"

        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False, f"Failed to send SMS: {str(e)}"

    def _validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format"""
        import re
        # Basic international phone number validation
        pattern = r'^\+?1?[2-9]\d{2}[2-9]\d{2}\d{4}$'
        return bool(re.match(pattern, phone_number.replace('-', '').replace(' ', '')))

    def send_event_reminder_sms(self, user_id: str, event_id: str) -> Tuple[bool, str]:
        """Send SMS reminder for an event"""
        try:
            # Get user phone number
            user_rows = self.db_manager.execute_query(
                "SELECT phone_number FROM users WHERE id = ?", (user_id,)
            )
            if not user_rows or not user_rows[0]['phone_number']:
                return False, "User phone number not found"

            # Get event details
            event_rows = self.db_manager.execute_query(
                "SELECT * FROM academic_calendar_events WHERE id = ?", (event_id,)
            )
            if not event_rows:
                return False, "Event not found"

            event = dict(event_rows[0])
            phone_number = user_rows[0]['phone_number']

            message = f"Reminder: {event['name']} on {event['date'] or event['date_start']}"
            if event['description']:
                message += f" - {event['description'][:100]}"

            return self.send_sms_notification(phone_number, message)

        except Exception as e:
            logger.error(f"Failed to send event reminder SMS: {e}")
            return False, f"Error sending reminder: {str(e)}"


class NotificationManager:
    """Manages notifications and reminders"""

    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager, smtp_config: Dict = None):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self.smtp_config = smtp_config or {}

    def set_notification_preference(self, user_id, notification_type: str,
                                  enabled: bool = True, advance_time: int = 60,
                                  method: str = 'email') -> Tuple[bool, str]:
        """Set notification preferences for a user"""
        try:
            if user_id is None or str(user_id).strip() == '':
                raise ValidationError("Invalid user ID")

            notification_type = ValidationUtils.sanitize_string(notification_type, 50)
            method = ValidationUtils.sanitize_string(method, 20)

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT OR REPLACE INTO notification_preferences
                       (user_id, notification_type, enabled, advance_time, method, date_added)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, notification_type, enabled, advance_time, method,
                     datetime.now().isoformat())
                )

            return True, "Notification preference updated successfully"

        except Exception as e:
            logger.error(f"Failed to set notification preference: {e}")
            raise CalendarError(f"Failed to set notification preference: {str(e)}")

    def schedule_notification(self, user_id, event_id: str, notification_type: str,
                            scheduled_time: str) -> Tuple[bool, str]:
        """Schedule a notification for an event"""
        try:
            if user_id is None or str(user_id).strip() == '':
                raise ValidationError("Invalid user ID")
            if not event_id or not str(event_id).strip():
                raise ValidationError("Invalid event ID")

            if not ValidationUtils.validate_datetime(scheduled_time):
                raise ValidationError("Invalid scheduled time format")

            notification_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO notification_queue (id, user_id, event_id, notification_type,
                       scheduled_time, status, date_added) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (notification_id, user_id, event_id,
                     ValidationUtils.sanitize_string(notification_type, 50),
                     scheduled_time, 'pending', datetime.now().isoformat())
                )

            return True, f"Notification scheduled with ID: {notification_id}"

        except Exception as e:
            logger.error(f"Failed to schedule notification: {e}")
            raise CalendarError(f"Failed to schedule notification: {str(e)}")

    def send_email_notification(self, recipient_email: str, subject: str, body: str) -> Tuple[bool, str]:
        """Send email notification"""
        if not EMAIL_AVAILABLE:
            return False, "Email functionality not available"

        try:
            from education_system.university_system.infrastructure.email.smtp import send_email_via_smtp

            if not ValidationUtils.validate_email(recipient_email):
                raise ValidationError("Invalid recipient email")

            subject = ValidationUtils.sanitize_string(subject, 200)
            body = ValidationUtils.sanitize_string(body, 5000)

            current_time = datetime.now().isoformat()
            success = send_email_via_smtp(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                cc=None,
                bcc=None,
                attachments=None,
                current_time=current_time
            )

            if success:
                logger.info(f"Email sent to {recipient_email}")
                return True, "Email sent successfully"
            else:
                logger.error(f"Failed to send email to {recipient_email}")
                return False, "Failed to send email"

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False, f"Failed to send email: {str(e)}"
