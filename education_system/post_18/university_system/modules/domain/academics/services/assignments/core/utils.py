from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import json
import os
import smtplib


class UtilsMixin:
    """Mixin providing utility helpers: file hashing, validation, logging, notifications, email."""

    def _calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _validate_file(self, file_path, allowed_types, max_size_mb):
        """Validate file type and size"""
        if not os.path.exists(file_path):
            return False, "File does not exist."

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > max_size_mb * 1024 * 1024:
            return False, f"File size exceeds {max_size_mb}MB limit."

        # Check file type
        if allowed_types:
            file_ext = os.path.splitext(file_path)[1].lower()
            if isinstance(allowed_types, list):
                allowed_list = [ext.strip().lower() for ext in allowed_types]
            else:
                allowed_list = [ext.strip().lower() for ext in allowed_types.split(',')]
            # Normalise: ensure both sides have a leading dot for comparison
            allowed_list = [e if e.startswith('.') else f'.{e}' for e in allowed_list]
            if file_ext not in allowed_list:
                return False, f"File type not allowed. Allowed types: {allowed_types}"

        return True, "Valid"

    def _log_action(self, action, table_name=None, record_id=None, old_values=None, new_values=None):
        """Log user actions for audit trail"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.auth.current_user['id'] if self.auth and self.auth.current_user else None,
                action, table_name, record_id,
                json.dumps(old_values) if old_values else None,
                json.dumps(new_values) if new_values else None,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning: Could not log action: {e}")

    def _send_notification(self, user_id, title, message, notification_type, assignment_id=None):
        """Send notification to user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO notifications (user_id, title, message, type, created_at, assignment_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, title, message, notification_type,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), assignment_id))

            conn.commit()
            conn.close()

            # Check if user wants email notifications
            self._check_and_send_email(user_id, title, message, notification_type)

        except Exception as e:
            print(f"Error sending notification: {e}")

    def _check_and_send_email(self, user_id, title, message, notification_type):
        """Check preferences and send email if enabled"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get user email and preferences
            cursor.execute('''
            SELECT u.email, np.email_enabled
            FROM users u
            LEFT JOIN notification_preferences np ON u.id = np.user_id AND np.notification_type = ?
            WHERE u.id = ?
            ''', (notification_type, user_id))

            result = cursor.fetchone()
            if result and result[0] and (result[1] is None or result[1] == 1):
                # Send email (implement with your email settings)
                self._send_email(result[0], title, message)

            conn.close()
        except Exception as e:
            print(f"Error checking email preferences: {e}")

    def _send_email(self, email, subject, message):
        """Send email notification (configure with your SMTP settings)"""
        try:
            # SMTP settings are read from the environment; no credentials
            # are hardcoded here.
            smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_username = os.getenv("SMTP_USERNAME", "")
            smtp_password = os.getenv("SMTP_PASSWORD", "")
            if not smtp_username or not smtp_password:
                print("Email not sent: SMTP_USERNAME/SMTP_PASSWORD not configured")
                return

            msg = MIMEMultipart()
            msg['From'] = smtp_username
            msg['To'] = email
            msg['Subject'] = subject

            msg.attach(MIMEText(message, 'plain'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            text = msg.as_string()
            server.sendmail(smtp_username, email, text)
            server.quit()

        except Exception as e:
            print(f"Error sending email: {e}")
