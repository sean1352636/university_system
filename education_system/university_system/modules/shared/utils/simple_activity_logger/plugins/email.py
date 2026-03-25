import time
from datetime import datetime
from typing import Dict, Any

from education_system.university_system.modules.shared.utils.simple_activity_logger.models import LogEntry, SecurityLevel
from education_system.university_system.modules.shared.utils.simple_activity_logger.plugins.base import LoggerPlugin


class EmailNotificationPlugin(LoggerPlugin):
    """Plugin to send email notifications for critical events"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_server = config.get('smtp_server')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.from_email = config.get('from_email')
        self.to_emails = config.get('to_emails', [])
        self.last_notification = {}
        self.rate_limit_seconds = config.get('rate_limit_seconds', 600)  # 10 minutes

    def after_log(self, log_entry: LogEntry, success: bool):
        if not success or not self._is_configured():
            return

        if log_entry.security_level == SecurityLevel.CRITICAL.name:
            self._send_email_notification(log_entry)

    def _is_configured(self) -> bool:
        """Check if email plugin is properly configured"""
        return all([
            self.smtp_server,
            self.smtp_username,
            self.smtp_password,
            self.from_email,
            self.to_emails
        ])

    def _send_email_notification(self, log_entry: LogEntry):
        """Send email notification with rate limiting"""
        # Rate limiting
        key = f"{log_entry.username}:{log_entry.action}"
        now = time.time()

        if key in self.last_notification:
            if now - self.last_notification[key] < self.rate_limit_seconds:
                return

        self.last_notification[key] = now

        try:
            from education_system.university_system.infrastructure.email.smtp import send_email_via_smtp

            # Prepare template variables
            template_vars = {
                'timestamp': log_entry.timestamp,
                'username': log_entry.username,
                'role': log_entry.role,
                'action': log_entry.action,
                'module': log_entry.module,
                'status': log_entry.status,
                'ip_address': log_entry.ip_address,
                'security_level': log_entry.security_level,
                'details': log_entry.details,
                'trace_id': log_entry.trace_id
            }

            # Try to use template
            try:
                from education_system.university_system.infrastructure.email.template_utils import render_template
                subject, body = render_template('security_alert', template_vars)
            except Exception as e:
                # Fallback to hardcoded message
                subject = f"CRITICAL: Security Alert - {log_entry.action}"
                body = f"""
CRITICAL SECURITY ALERT

Timestamp: {log_entry.timestamp}
User: {log_entry.username} ({log_entry.role})
Action: {log_entry.action}
Module: {log_entry.module}
Status: {log_entry.status}
IP Address: {log_entry.ip_address}
Security Level: {log_entry.security_level}

Details: {log_entry.details}

Trace ID: {log_entry.trace_id}

This is an automated alert from the Enhanced Activity Logger.
Please investigate this activity immediately.
            """

            # Send to first recipient with others as CC
            recipient_email = self.to_emails[0]
            cc = self.to_emails[1:] if len(self.to_emails) > 1 else None

            current_time = datetime.now().isoformat()
            success = send_email_via_smtp(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                cc=cc,
                bcc=None,
                attachments=None,
                current_time=current_time
            )

            if success:
                print(f"Critical alert email sent for {log_entry.username}:{log_entry.action}")
            else:
                print(f"Failed to send email notification for {log_entry.username}:{log_entry.action}")

        except Exception as e:
            print(f"Failed to send email notification: {e}")
