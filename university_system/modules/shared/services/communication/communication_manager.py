"""
Unified Communication Manager
Handles all communication channels: email, SMS, push notifications, announcements
"""

from university_system.infrastructure.database.db import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.modules.shared.utils.i18n import get_text, _

class CommunicationManager:
    """Comprehensive manager for all communication operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

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
        """Queue an email for sending"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cc_json = json.dumps(cc_addresses) if cc_addresses else None
                bcc_json = json.dumps(bcc_addresses) if bcc_addresses else None

                cursor.execute("""
                    INSERT INTO email_queue (
                        to_address, cc_addresses, bcc_addresses, subject,
                        body, html_body, scheduled_time, priority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (to_address, cc_json, bcc_json, subject, body,
                      html_body, scheduled_time, priority))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error queuing email: {e}")
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
        """Queue an SMS for sending"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sms_queue (phone_number, message_text, scheduled_time)
                    VALUES (?, ?, ?)
                """, (phone_number, message_text, scheduled_time))
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
        """Send a push notification"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                data_json = json.dumps(data) if data else None

                cursor.execute("""
                    INSERT INTO push_notifications (
                        user_id, title, body, data, click_action
                    ) VALUES (?, ?, ?, ?, ?)
                """, (user_id, title, body, data_json, click_action))
                conn.commit()
                return cursor.lastrowid
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

                audience_json = json.dumps(target_audience) if target_audience else None

                cursor.execute("""
                    INSERT INTO announcements (
                        title, content, target_audience, priority,
                        start_date, end_date, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (title, content, audience_json, priority,
                      start_date, end_date, created_by))
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
                    ORDER BY priority DESC, created_at DESC
                """)

                columns = [d[0] for d in cursor.description]
                results = []

                for row in cursor.fetchall():
                    announcement = dict(zip(columns, row))
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

                variables_json = json.dumps(variables) if variables else None

                cursor.execute("""
                    INSERT INTO message_templates (
                        name, subject, body, variables, template_type, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (name, subject, body, variables_json, template_type, created_by))
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
                    SELECT subject, body FROM message_templates
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

                # Check if preferences exist
                cursor.execute("""
                    SELECT pref_id FROM communication_preferences
                    WHERE user_id = ?
                """, (user_id,))

                exists = cursor.fetchone() is not None

                if exists:
                    updates = []
                    values = []

                    if email_enabled is not None:
                        updates.append("email_enabled = ?")
                        values.append(1 if email_enabled else 0)

                    if sms_enabled is not None:
                        updates.append("sms_enabled = ?")
                        values.append(1 if sms_enabled else 0)

                    if push_enabled is not None:
                        updates.append("push_enabled = ?")
                        values.append(1 if push_enabled else 0)

                    if preferred_method:
                        updates.append("preferred_method = ?")
                        values.append(preferred_method)

                    if updates:
                        values.append(user_id)
                        query = f"""
                            UPDATE communication_preferences
                            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = ?
                        """
                        cursor.execute(query, values)
                else:
                    cursor.execute("""
                        INSERT INTO communication_preferences (
                            user_id, email_enabled, sms_enabled, push_enabled, preferred_method
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (user_id,
                          1 if email_enabled else 0,
                          1 if sms_enabled else 0,
                          1 if push_enabled else 0,
                          preferred_method or 'email'))

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
                    SELECT * FROM communication_preferences
                    WHERE user_id = ?
                """, (user_id,))

                row = cursor.fetchone()
                if row:
                    columns = [d[0] for d in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting preferences: {e}")
            return None
