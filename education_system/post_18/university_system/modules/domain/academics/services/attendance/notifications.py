"""Enhanced notification system for attendance alerts."""

import datetime
import uuid
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.academics.services.attendance.settings import get_setting

try:
    from education_system.post_18.university_system.infrastructure.email import queue_template_email
    EMAIL_SUPPORT = True
except ImportError:
    EMAIL_SUPPORT = False


class EnhancedNotificationSystem:
    def __init__(self):
        self.notification_queue = []
        self.sms_api_key = get_setting('sms_api_key')

    def send_email_notification(self, recipient, subject, message, template_name=None):
        """Send email notification"""
        try:
            if EMAIL_SUPPORT and template_name:
                template_vars = {
                    'recipient': recipient,
                    'subject': subject,
                    'message': message,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                return queue_template_email(template_name, recipient, template_vars)
            else:
                # Basic email sending
                print(f"EMAIL TO {recipient}: {subject}\n{message}")
                return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def send_sms_notification(self, phone_number, message):
        """Send SMS notification"""
        try:
            if get_setting('enable_sms_notifications') != 'True':
                return False

            if not self.sms_api_key:
                print(f"SMS to {phone_number}: {message}")
                return True

            # Integration with SMS service (example using a generic REST API)
            payload = {
                'to': phone_number,
                'message': message,
                'api_key': self.sms_api_key
            }

            # This would be replaced with actual SMS service API call
            print(f"SMS to {phone_number}: {message}")
            return True

        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False

    def create_attendance_alert(self, student_id, module_code, alert_type, severity, message):
        """Create and queue attendance alert"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student contact info
            cursor.execute('''
            SELECT email_address, phone_number FROM students WHERE student_id = ?
            ''', (student_id,))

            student_info = cursor.fetchone()

            if not student_info:
                return False

            email, phone = student_info

            alert_id = str(uuid.uuid4())

            # Insert alert
            cursor.execute('''
            INSERT INTO attendance_alerts
            (alert_id, student_id, module_code, alert_type, severity, message,
             recipient_email, recipient_phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (alert_id, student_id, module_code, alert_type, severity, message, email, phone))

            conn.commit()
            conn.close()

            # Send notifications based on severity
            if severity in ['high', 'critical']:
                if email:
                    self.send_email_notification(email, f"Attendance Alert - {alert_type}", message, 'attendance_alert')
                if phone and get_setting('enable_sms_notifications') == 'True':
                    self.send_sms_notification(phone, f"Attendance Alert: {message}")

            return True

        except Exception as e:
            print(f"Error creating attendance alert: {e}")
            return False

    def send_parent_notifications(self, student_id, message):
        """Send notifications to parents"""
        try:
            if get_setting('enable_parent_portal') != 'True':
                return False

            conn = get_connection()
            cursor = conn.cursor()

            # Get parent contact info (assuming it's stored in students table)
            cursor.execute('''
            SELECT parent_email, parent_phone FROM students WHERE student_id = ?
            ''', (student_id,))

            parent_info = cursor.fetchone()
            conn.close()

            if parent_info and parent_info[0]:  # Parent email exists
                self.send_email_notification(parent_info[0], "Student Attendance Update", message, 'parent_notification')

            if parent_info and parent_info[1]:  # Parent phone exists
                self.send_sms_notification(parent_info[1], f"Student attendance update: {message}")

            return True

        except Exception as e:
            print(f"Error sending parent notifications: {e}")
            return False
