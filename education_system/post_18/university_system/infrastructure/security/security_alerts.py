"""
Real-Time Security Alerting System

Provides multi-channel security alerting via email, Slack, and SMS.
Integrates with the immutable audit log for compliance tracking.
"""

import os
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

# Optional requests for Slack integration
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class SecurityAlertManager:
    """Real-time security alert system with multi-channel notification."""

    ALERT_LEVELS = {
        'LOW': 1,
        'MEDIUM': 2,
        'HIGH': 3,
        'CRITICAL': 4
    }

    def __init__(self):
        """Initialize alert manager with configuration from environment."""
        self.alert_recipients = self._parse_recipients(
            os.getenv('SECURITY_ALERT_EMAILS', '')
        )
        self.slack_webhook = os.getenv('SECURITY_SLACK_WEBHOOK')
        self.sms_enabled = os.getenv('SECURITY_SMS_ENABLED', 'false').lower() == 'true'
        self.min_email_level = os.getenv('SECURITY_MIN_EMAIL_LEVEL', 'MEDIUM')
        self.min_slack_level = os.getenv('SECURITY_MIN_SLACK_LEVEL', 'LOW')

    def _parse_recipients(self, recipients_str: str) -> List[str]:
        """Parse comma-separated email recipients."""
        if not recipients_str:
            return []
        return [r.strip() for r in recipients_str.split(',') if r.strip()]

    def send_alert(
        self,
        level: str,
        title: str,
        details: Dict,
        notify_sms: bool = False,
        source_module: Optional[str] = None
    ) -> bool:
        """
        Send security alert via multiple channels.

        Args:
            level: Alert level (LOW, MEDIUM, HIGH, CRITICAL)
            title: Alert title
            details: Alert details dictionary
            notify_sms: Send SMS for critical alerts
            source_module: Module that triggered the alert

        Returns:
            bool: True if at least one notification was sent successfully
        """
        if level not in self.ALERT_LEVELS:
            level = 'MEDIUM'

        # Add metadata to details
        details['timestamp'] = datetime.now().isoformat()
        if source_module:
            details['source_module'] = source_module

        # Format alert message
        message = self._format_alert_message(level, title, details)

        success = False

        # Send via email for MEDIUM and above
        if (self.alert_recipients and
            self.ALERT_LEVELS[level] >= self.ALERT_LEVELS.get(self.min_email_level, 2)):
            if self._send_email_alert(level, title, message):
                success = True

        # Send via Slack
        if (self.slack_webhook and REQUESTS_AVAILABLE and
            self.ALERT_LEVELS[level] >= self.ALERT_LEVELS.get(self.min_slack_level, 1)):
            if self._send_slack_alert(level, title, message):
                success = True

        # Send SMS for critical alerts
        if notify_sms and level == 'CRITICAL' and self.sms_enabled:
            if self._send_sms_alert(title, details):
                success = True

        # Log alert to activity logger
        self._log_alert(level, title, details)

        # Log to immutable audit log for compliance
        self._log_to_immutable_audit(level, title, details)

        return success

    def _format_alert_message(self, level: str, title: str, details: Dict) -> str:
        """Format alert message for display."""
        emoji_map = {
            'LOW': 'ℹ️',
            'MEDIUM': '⚠️',
            'HIGH': '🔴',
            'CRITICAL': '🚨'
        }
        emoji = emoji_map.get(level, '⚠️')

        message = f"""
{emoji} SECURITY ALERT - {level}

{title}

Details:
"""
        for key, value in details.items():
            if key != 'timestamp':  # Timestamp added at end
                message += f"  {key}: {value}\n"

        message += f"\nTimestamp: {details.get('timestamp', datetime.now().isoformat())}\n"
        message += "\n---\nUniversity Management System Security Monitoring"
        return message

    def _send_email_alert(self, level: str, title: str, message: str) -> bool:
        """Send email alert to configured recipients."""
        try:
            msg = MIMEMultipart()
            msg['From'] = os.getenv('SECURITY_ALERT_FROM', 'security@university.edu')
            msg['To'] = ', '.join(self.alert_recipients)
            msg['Subject'] = f"[{level}] Security Alert: {title}"

            # Add priority header for high/critical
            if level in ('HIGH', 'CRITICAL'):
                msg['X-Priority'] = '1'
                msg['Importance'] = 'high'

            msg.attach(MIMEText(message, 'plain'))

            # Send email
            smtp_server = os.getenv('SMTP_HOST', 'localhost')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_user = os.getenv('SMTP_USER')
            smtp_password = os.getenv('SMTP_PASSWORD')

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)

            logger.info(f"Security alert email sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    def _send_slack_alert(self, level: str, title: str, message: str) -> bool:
        """Send Slack alert via webhook."""
        if not REQUESTS_AVAILABLE:
            logger.warning("requests library not available for Slack alerts")
            return False

        try:
            color_map = {
                'LOW': '#36a64f',      # Green
                'MEDIUM': '#ff9900',   # Orange
                'HIGH': '#ff0000',     # Red
                'CRITICAL': '#8b0000'  # Dark Red
            }

            payload = {
                'attachments': [{
                    'color': color_map.get(level, '#808080'),
                    'title': f'Security Alert: {title}',
                    'text': message,
                    'footer': 'University Security System',
                    'ts': int(datetime.now().timestamp())
                }]
            }

            response = requests.post(
                self.slack_webhook,
                json=payload,
                timeout=5
            )
            response.raise_for_status()

            logger.info(f"Security alert sent to Slack: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _send_sms_alert(self, title: str, details: Dict) -> bool:
        """
        Send SMS alert for critical issues.

        Implement using Twilio or similar service.
        Configure with TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER.
        """
        try:
            # Check for Twilio configuration
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            from_number = os.getenv('TWILIO_FROM_NUMBER')
            to_numbers = os.getenv('SECURITY_SMS_NUMBERS', '').split(',')

            if not all([account_sid, auth_token, from_number, to_numbers]):
                logger.warning("SMS alerting not configured (missing Twilio credentials)")
                return False

            try:
                from twilio.rest import Client
            except ImportError:
                logger.warning("twilio library not installed for SMS alerts")
                return False

            client = Client(account_sid, auth_token)
            sms_body = f"CRITICAL SECURITY ALERT: {title}"

            for number in to_numbers:
                number = number.strip()
                if number:
                    client.messages.create(
                        body=sms_body,
                        from_=from_number,
                        to=number
                    )

            logger.info(f"Security SMS alert sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")
            return False

    def _log_alert(self, level: str, title: str, details: Dict):
        """Log alert to activity logger."""
        try:
            from education_system.post_18.university_system.core.activity_logger import log_activity
            log_activity('security_alert', 'alert', details={
                'level': level,
                'title': title,
                **details
            })
        except ImportError:
            logger.debug("Activity logger not available")

    def _log_to_immutable_audit(self, level: str, title: str, details: Dict):
        """Log alert to immutable audit log for compliance."""
        try:
            from education_system.post_18.university_system.infrastructure.security.audit_helpers import (
                safe_log_security_event,
            )
            from education_system.post_18.university_system.infrastructure.security.immutable_audit_log import AuditAction

            safe_log_security_event(
                action=AuditAction.SECURITY_ALERT,
                resource_type='security_alert',
                resource_id=level,
                details={
                    'title': title,
                    'level': level,
                    **details
                }
            )
        except ImportError:
            logger.debug("Immutable audit log not available")


# Global instance (lazy initialization)
_alert_manager: Optional[SecurityAlertManager] = None


def get_alert_manager() -> SecurityAlertManager:
    """Get or create the global SecurityAlertManager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = SecurityAlertManager()
    return _alert_manager


def send_security_alert(
    level: str,
    title: str,
    details: Dict,
    notify_sms: bool = False,
    source_module: Optional[str] = None
) -> bool:
    """
    Send security alert via configured channels.

    Args:
        level: Alert level (LOW, MEDIUM, HIGH, CRITICAL)
        title: Short alert title
        details: Dictionary of alert details
        notify_sms: Also send SMS for critical alerts
        source_module: Module that triggered the alert

    Returns:
        bool: True if at least one notification sent successfully

    Example:
        send_security_alert(
            level='HIGH',
            title='Multiple Failed Login Attempts',
            details={
                'user_id': 'admin',
                'ip_address': '192.168.1.100',
                'attempts': 5,
                'reason': 'Possible brute force attack'
            }
        )
    """
    return get_alert_manager().send_alert(
        level=level,
        title=title,
        details=details,
        notify_sms=notify_sms,
        source_module=source_module
    )


# Convenience functions for common alert scenarios

def alert_suspicious_login(
    user_id: str,
    ip_address: str,
    reason: str,
    country: Optional[str] = None,
    additional_details: Optional[Dict] = None
):
    """Send alert for suspicious login activity."""
    details = {
        'user_id': user_id,
        'ip_address': ip_address,
        'reason': reason
    }
    if country:
        details['country'] = country
    if additional_details:
        details.update(additional_details)

    send_security_alert(
        level='HIGH',
        title='Suspicious Login Detected',
        details=details,
        source_module='authentication'
    )


def alert_brute_force_attempt(
    identifier: str,
    ip_address: str,
    attempts: int,
    window_minutes: int = 5
):
    """Send alert for potential brute force attack."""
    send_security_alert(
        level='CRITICAL' if attempts > 10 else 'HIGH',
        title='Potential Brute Force Attack',
        details={
            'identifier': identifier,
            'ip_address': ip_address,
            'attempts': attempts,
            'window': f'{window_minutes} minutes',
            'reason': 'Multiple failed authentication attempts'
        },
        notify_sms=attempts > 10,
        source_module='rate_limiter'
    )


def alert_unauthorized_access(
    user_id: str,
    resource_type: str,
    resource_id: str,
    required_permission: str
):
    """Send alert for unauthorized access attempt."""
    send_security_alert(
        level='MEDIUM',
        title='Unauthorized Access Attempt',
        details={
            'user_id': user_id,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'required_permission': required_permission,
            'reason': 'User attempted to access resource without permission'
        },
        source_module='authorization'
    )


def alert_data_exfiltration(
    user_id: str,
    data_type: str,
    record_count: int,
    export_format: str
):
    """Send alert for potential data exfiltration."""
    level = 'CRITICAL' if record_count > 1000 else 'HIGH'
    send_security_alert(
        level=level,
        title='Large Data Export Detected',
        details={
            'user_id': user_id,
            'data_type': data_type,
            'record_count': record_count,
            'export_format': export_format,
            'reason': 'Unusually large data export'
        },
        notify_sms=record_count > 1000,
        source_module='data_export'
    )


def alert_account_lockout(
    user_id: str,
    ip_address: str,
    failed_attempts: int,
    lockout_duration_minutes: int
):
    """Send alert when account is locked out."""
    send_security_alert(
        level='MEDIUM',
        title='Account Locked Out',
        details={
            'user_id': user_id,
            'ip_address': ip_address,
            'failed_attempts': failed_attempts,
            'lockout_duration': f'{lockout_duration_minutes} minutes',
            'reason': 'Too many failed login attempts'
        },
        source_module='authentication'
    )


def alert_privilege_escalation(
    user_id: str,
    old_role: str,
    new_role: str,
    changed_by: str
):
    """Send alert for role/privilege changes."""
    send_security_alert(
        level='HIGH',
        title='Privilege Escalation Detected',
        details={
            'user_id': user_id,
            'old_role': old_role,
            'new_role': new_role,
            'changed_by': changed_by,
            'reason': 'User role was elevated'
        },
        source_module='user_management'
    )


def alert_configuration_change(
    setting_name: str,
    old_value: str,
    new_value: str,
    changed_by: str
):
    """Send alert for security-relevant configuration changes."""
    send_security_alert(
        level='MEDIUM',
        title='Security Configuration Changed',
        details={
            'setting': setting_name,
            'old_value': old_value,
            'new_value': new_value,
            'changed_by': changed_by
        },
        source_module='configuration'
    )
