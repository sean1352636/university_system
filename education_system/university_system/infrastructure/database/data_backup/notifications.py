"""Backup notification services (email, Slack, Discord)."""

import datetime
import smtplib

import requests

from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.database.data_backup.config import config

logger = configure_logging(name=__name__)


def send_email_notification(subject: str, message: str, recipients: list):
    """Send email notification"""
    try:
        if not config["email_notifications"] or not recipients:
            return

        from education_system.university_system.infrastructure.email.smtp import send_email_via_smtp
        from datetime import datetime as dt

        # Send to first recipient with others as CC
        recipient_email = recipients[0]
        cc = recipients[1:] if len(recipients) > 1 else None

        current_time = dt.now().isoformat()
        success = send_email_via_smtp(
            recipient_email=recipient_email,
            subject=subject,
            body=message,
            cc=cc,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        if success:
            logger.info(f"Email notification sent to {recipients}")
        else:
            logger.error(f"Failed to send email notification to {recipients}")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email notification: {e}")
    except (OSError, IOError) as e:
        logger.error(f"Network error sending email notification: {e}")


def send_slack_notification(message: str):
    """Send Slack notification"""
    try:
        if not config["slack_webhook"]:
            return

        payload = {"text": message}
        response = requests.post(config["slack_webhook"], json=payload, timeout=30)

        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
        else:
            logger.error(f"Error sending Slack notification: {response.status_code}")
    except requests.exceptions.Timeout as e:
        logger.error(f"Slack notification timed out: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error sending Slack notification: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error sending Slack notification: {e}")


def send_discord_notification(message: str):
    """Send Discord notification"""
    try:
        if not config["discord_webhook"]:
            return

        payload = {"content": message}
        response = requests.post(config["discord_webhook"], json=payload, timeout=30)

        if response.status_code == 204:
            logger.info("Discord notification sent successfully")
        else:
            logger.error(f"Error sending Discord notification: {response.status_code}")
    except requests.exceptions.Timeout as e:
        logger.error(f"Discord notification timed out: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error sending Discord notification: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error sending Discord notification: {e}")


def notify_backup_result(success: bool, backup_path: str, operation: str):
    """Send notifications about backup results"""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if success:
        subject, message = render_template('backup_success', {
            'operation': operation,
            'backup_path': backup_path,
            'timestamp': timestamp
        })
        slack_msg = f"✅ Backup Success: {operation}\nFile: {backup_path}"
    else:
        subject, message = render_template('backup_failed', {
            'operation': operation,
            'timestamp': timestamp
        })
        slack_msg = f"❌ Backup Failed: {operation}\nCheck logs for details."

    send_email_notification(subject, message, config["notification_recipients"])
    send_slack_notification(slack_msg)
    send_discord_notification(slack_msg)
