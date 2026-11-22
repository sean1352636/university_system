"""
Unified Communication Manager
Handles all communication channels: email, SMS, push notifications, announcements
"""

from education_system.systems.university.infrastructure.database.db import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.i18n import get_text, _

class CommunicationManager:
    """Comprehensive manager for all communication operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or UNIVERSITY_DEFAULT_DB_PATH

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    # ==== Email Management ====
    def queue_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None,
        scheduled_time: Optional[datetime] = None,
        priority: int = 5
    ) -> Optional[int]:
        """Send an e-mail through the university outbox.

        Returns the outbox message id, or None if it was not accepted. The
        outbox delivers per the e-mail delivery mode, with retries;
        ``scheduled_time`` and ``priority`` are not supported by the outbox
        and are ignored (the old ``email_queue`` table never existed in the
        live database, so nothing was ever sent from here)."""
        try:
            from education_system.systems.university.infrastructure.email.email_service.core import (
                send_email,
            )
            ok = send_email(to_address, subject, html_body or body, cc=cc_addresses,
                            bcc=bcc_addresses)
            if not ok:
                return None
            from education_system.systems.university.infrastructure.database.db import (
                get_connection,
            )
            conn = get_connection(None, row_factory=False)
            try:
                row = conn.execute("SELECT MAX(message_id) FROM email_outbox WHERE to_address = ?",
                                   (to_address,)).fetchone()
            finally:
                conn.close()
            return row[0] if row else None
        except Exception as e:
            print(f"Error sending email: {e}")
            return None

    def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> int:
        """Send email to multiple recipients"""
        count = 0
        for recipient in recipients:
            if self.queue_email(recipient, subject, body, html_body):
                count += 1
        return count

    # ==== SMS Management ====
    def queue_sms(
        self,
        phone_number: str,
        message_text: str,
        scheduled_time: Optional[datetime] = None
    ) -> Optional[int]:
        """Queue an SMS for sending (a ``queued`` row in ``sms_messages``, the
        log the SMS screens read). ``scheduled_time`` is kept in no column of
        that table and is ignored."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sms_messages (phone_number, recipient_phone, message, status)
                    VALUES (?, ?, ?, 'queued')
                """, (phone_number, phone_number, message_text))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error queuing SMS: {e}")
            return None

    # ==== Push Notifications ====
    def send_push_notification(
        self,
        user_id: int,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        click_action: Optional[str] = None
    ) -> Optional[int]:
        """Send a push notification through the push service (which logs each
        delivery to ``push_delivery_log``). Returns how many devices it reached,
        or None if none."""
        try:
            from education_system.systems.university.infrastructure.communication.push_notifications import (
                get_push_notification_service,
            )
            result = get_push_notification_service().send_push_notification(
                str(user_id), title, body, data=data, action_url=click_action)
            return result.get('sent') or None
        except Exception as e:
            print(f"Error sending push notification: {e}")
            return None

    # ==== Announcements ====
    def create_announcement(
        self,
        title: str,
        content: str,
        created_by: int,
        target_audience: Optional[Dict] = None,
        priority: str = 'normal',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[int]:
        """Create an announcement"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                audience_json = json.dumps(target_audience) if target_audience else 'all'
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                urgent = 1 if str(priority).lower() in ('high', 'urgent') else 0

                cursor.execute("""
                    INSERT INTO announcements (
                        creator_id, title, content, target_audience, is_urgent,
                        start_date, end_date, created_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (created_by, title, content, audience_json, urgent,
                      start_date or now, end_date, created_by, now, now))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error creating announcement: {e}")
            return None

    def get_active_announcements(
        self,
        target_role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get active announcements"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM announcements
                    WHERE is_active = 1
                    AND (start_date IS NULL OR start_date <= CURRENT_DATE)
                    AND (end_date IS NULL OR end_date >= CURRENT_DATE)
                    ORDER BY is_urgent DESC, created_at DESC
                """)

                columns = [d[0] for d in cursor.description]
                results = []

                for row in cursor.fetchall():
                    announcement = dict(zip(columns, row))
                    announcement['priority'] = 'urgent' if announcement.get('is_urgent') else 'normal'
                    if announcement.get('target_audience'):
                        try:
                            announcement['target_audience'] = json.loads(
                                announcement['target_audience']
                            )
                        except (json.JSONDecodeError, TypeError):
                            pass
                    results.append(announcement)

                return results
        except Exception as e:
            print(f"Error getting announcements: {e}")
            return []

    # ==== Emergency Alerts ====
    def send_emergency_alert(
        self,
        alert_type: str,
        message: str,
        severity: str,
        sent_by: int,
        affected_locations: Optional[List[str]] = None
    ) -> Optional[int]:
        """Send an emergency alert to all users"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                locations_json = json.dumps(affected_locations) if affected_locations else None

                cursor.execute("""
                    INSERT INTO emergency_alerts (
                        alert_type, message, severity, affected_locations, sent_by
                    ) VALUES (?, ?, ?, ?, ?)
                """, (alert_type, message, severity, locations_json, sent_by))

                alert_id = cursor.lastrowid

                # Queue notifications to all users
                # In a real implementation, this would filter based on preferences
                # and affected locations
                conn.commit()
                return alert_id
        except Exception as e:
            print(f"Error sending emergency alert: {e}")
            return None

    # ==== Message Templates ====
    def create_template(
        self,
        name: str,
        body: str,
        template_type: str = 'email',
        subject: Optional[str] = None,
        variables: Optional[List[str]] = None,
        created_by: Optional[int] = None
    ) -> Optional[int]:
        """Create a message template"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # ``variables`` and ``created_by`` have no column on the shared
                # template table; placeholders are read from the text when rendering.
                send_method = template_type if template_type in ('email', 'sms', 'push') else 'email'
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    INSERT INTO notification_templates (
                        template_name, template_type, subject_template, body_template,
                        send_method, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name, template_type, subject or '', body, send_method, now, now))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error creating template: {e}")
            return None

    def render_template(
        self,
        template_id: int,
        variables: Dict[str, str]
    ) -> Optional[Dict[str, str]]:
        """Render a template with variables"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT subject_template, body_template FROM notification_templates
                    WHERE template_id = ?
                """, (template_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                subject, body = row

                # Simple variable replacement
                rendered_subject = subject
                rendered_body = body

                for key, value in variables.items():
                    placeholder = f"{{{key}}}"
                    if subject:
                        rendered_subject = rendered_subject.replace(placeholder, str(value))
                    rendered_body = rendered_body.replace(placeholder, str(value))

                return {
                    'subject': rendered_subject,
                    'body': rendered_body
                }
        except Exception as e:
            print(f"Error rendering template: {e}")
            return None

    # ==== Communication Preferences ====
    # Kept on ``user_preferences``: e-mail and push have their own columns; the
    # SMS switch and preferred method live in its ``preferences_json``.
    def update_preferences(
        self,
        user_id: int,
        email_enabled: Optional[bool] = None,
        sms_enabled: Optional[bool] = None,
        push_enabled: Optional[bool] = None,
        preferred_method: Optional[str] = None
    ) -> bool:
        """Update user communication preferences"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                key = str(user_id)
                cursor.execute("""
                    SELECT email_notifications, push_notifications, preferences_json
                    FROM user_preferences WHERE user_id = ?
                """, (key,))
                row = cursor.fetchone()
                extra = self._extra_preferences(row[2] if row else None)
                if sms_enabled is not None:
                    extra['sms_enabled'] = bool(sms_enabled)
                if preferred_method:
                    extra['preferred_method'] = preferred_method
                if row:
                    email = row[0] if email_enabled is None else int(bool(email_enabled))
                    push = row[1] if push_enabled is None else int(bool(push_enabled))
                    cursor.execute("""
                        UPDATE user_preferences
                        SET email_notifications = ?, push_notifications = ?, preferences_json = ?
                        WHERE user_id = ?
                    """, (email, push, json.dumps(extra), key))
                else:
                    cursor.execute("""
                        INSERT INTO user_preferences (
                            user_id, email_notifications, push_notifications, preferences_json
                        ) VALUES (?, ?, ?, ?)
                    """, (key,
                          1 if email_enabled else 0,
                          1 if push_enabled else 0,
                          json.dumps({'sms_enabled': bool(sms_enabled),
                                      'preferred_method': preferred_method or 'email'})))

                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating preferences: {e}")
            return False

    def get_preferences(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user communication preferences"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT email_notifications, push_notifications, preferences_json
                    FROM user_preferences WHERE user_id = ?
                """, (str(user_id),))

                row = cursor.fetchone()
                if row:
                    extra = self._extra_preferences(row[2])
                    return {
                        'user_id': user_id,
                        'email_enabled': int(bool(row[0])),
                        'sms_enabled': int(bool(extra.get('sms_enabled'))),
                        'push_enabled': int(bool(row[1])),
                        'preferred_method': extra.get('preferred_method', 'email'),
                    }
                return None
        except Exception as e:
            print(f"Error getting preferences: {e}")
            return None

    @staticmethod
    def _extra_preferences(raw: Optional[str]) -> Dict[str, Any]:
        try:
            extra = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            extra = {}
        return extra if isinstance(extra, dict) else {}
