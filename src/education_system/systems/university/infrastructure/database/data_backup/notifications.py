"""Backup notification services (email, Slack, Discord)."""

import datetime
import smtplib

import requests

from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.database.data_backup.config import config

logger = configure_logging(name=__name__)


def send_email_notification(subject: str, message: str, recipients: list):
    """Send email notification"""
    try:
        if not config["email_notifications"] or not recipients:
            return

        from education_system.systems.university.infrastructure.email import outbox_delivery

        # One message each, through the outbox (retries; nobody sees the
        # other recipients' addresses).
        accepted = 0
        for address in recipients:
            try:
                result = outbox_delivery.enqueue(address, subject, message,
                                                 category="backup_alert", created_by="backup")
                accepted += result["status"] in ("queued", "stored")
            except ValueError as exc:
                logger.error(f"Backup notification not sent to {address}: {exc}")
        if accepted:
            logger.info(f"Backup notification sent to {accepted} of {len(recipients)} recipients")
        else:
            logger.error(f"Failed to send backup notification to {recipients}")
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
