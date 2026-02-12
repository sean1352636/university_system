"""SMTP utilities used by the email infrastructure.

This module provides SMTP functionality with dependency injection to avoid
circular imports. The SMTPClient class handles pure SMTP operations, while
database logging is handled through injected callbacks.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Optional, Protocol

from university_system.infrastructure.email.config import config
from university_system.infrastructure.email.email_db_utilities import execute_db_operation
from university_system.core.logs import log_event

logger = logging.getLogger(__name__)


@dataclass
class SMTPConfig:
    """Configuration for SMTP connection."""
    smtp_server: str
    smtp_port: int
    sender_email: str
    sender_name: str
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = True
    use_authentication: bool = False


class EmailLoggerProtocol(Protocol):
    """Protocol for email logging operations."""

    def log_email(
        self,
        cursor,
        recipient_email: str,
        subject: str,
        sent_time: str,
        status: str,
        **kwargs
    ) -> None:
        """Log email to database."""
        ...

    def log_metrics(self, status: str) -> None:
        """Log email metrics."""
        ...

    def get_sender_id(
        self,
        cursor,
        sender_email: str,
        sender_name: str,
        current_time: str
    ) -> int:
        """Get or create sender ID."""
        ...


class SMTPClient:
    """Pure SMTP client for sending emails.

    This class handles only SMTP operations without any database dependencies.
    Database logging is handled through dependency injection.
    """

    def __init__(self, smtp_config: Optional[SMTPConfig] = None):
        """Initialize SMTP client with configuration.

        Args:
            smtp_config: SMTP configuration. If None, uses global config.
        """
        if smtp_config:
            self.config = smtp_config
        else:
            # Use global config for backward compatibility
            self.config = SMTPConfig(
                smtp_server=config.get('smtp_server', ''),
                smtp_port=config.get('smtp_port', 587),
                sender_email=config.get('sender_email', ''),
                sender_name=config.get('sender_name', ''),
                username=config.get('username'),
                password=config.get('password'),
                use_tls=config.get('use_tls', True),
                use_authentication=config.get('use_authentication', False),
            )

    def send(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        attachments: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP.

        Args:
            recipient_email: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Comma-separated CC recipients
            bcc: Comma-separated BCC recipients
            attachments: Comma-separated attachment file paths

        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{self.config.sender_name} <{self.config.sender_email}>"
            msg['To'] = recipient_email
            msg['Subject'] = subject
            if cc:
                msg['Cc'] = cc
            if bcc:
                msg['Bcc'] = bcc
            msg.attach(MIMEText(body, 'plain'))

            if attachments:
                for file_path in attachments.split(','):
                    file_path = file_path.strip()
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as file:
                            part = MIMEApplication(file.read(), Name=os.path.basename(file_path))
                            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                            msg.attach(part)

            all_recipients = [recipient_email]
            if cc:
                all_recipients.extend(cc.split(','))
            if bcc:
                all_recipients.extend(bcc.split(','))

            context = ssl.create_default_context()
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                # Always use TLS when available (STARTTLS on port 587)
                if self.config.use_tls or self.config.smtp_port in (587, 465):
                    server.starttls(context=context)
                if self.config.use_authentication and self.config.username and self.config.password:
                    server.login(self.config.username, self.config.password)
                server.sendmail(self.config.sender_email, all_recipients, msg.as_string())

            logger.info("Email sent successfully to %s", recipient_email)
            return True

        except Exception as e:
            logger.error("SMTP send failed: %s", e)
            return False


class EmailService:
    """Email service that orchestrates SMTP sending and database logging.

    Uses dependency injection to avoid circular imports between smtp.py
    and email_service.py.
    """

    def __init__(
        self,
        smtp_client: SMTPClient,
        log_email_func: Optional[Callable] = None,
        log_metrics_func: Optional[Callable] = None,
        get_sender_id_func: Optional[Callable] = None,
    ):
        """Initialize email service with dependencies.

        Args:
            smtp_client: SMTP client for sending emails
            log_email_func: Function to log email to database
            log_metrics_func: Function to log email metrics
            get_sender_id_func: Function to get/create sender ID
        """
        self.smtp = smtp_client
        self._log_email = log_email_func
        self._log_metrics = log_metrics_func
        self._get_sender_id = get_sender_id_func

    def send_and_log(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        attachments: Optional[str] = None,
        current_time: Optional[str] = None,
    ) -> bool:
        """Send email and log to database.

        Args:
            recipient_email: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Comma-separated CC recipients
            bcc: Comma-separated BCC recipients
            attachments: Comma-separated attachment file paths
            current_time: Timestamp for logging

        Returns:
            True if email was sent and logged successfully
        """
        result = self.smtp.send(recipient_email, subject, body, cc, bcc, attachments)

        if result and self._log_email:
            try:
                self._log_email(
                    recipient_email=recipient_email,
                    subject=subject,
                    sent_time=current_time,
                    status='sent',
                    cc=cc,
                    bcc=bcc,
                    attachments=attachments,
                )
            except Exception as e:
                logger.warning("Failed to log email: %s", e)

        if self._log_metrics:
            try:
                self._log_metrics('sent' if result else 'failed')
            except Exception as e:
                logger.warning("Failed to log metrics: %s", e)

        return result


# Backward compatibility function that uses deferred imports
def send_email_via_smtp(recipient_email, subject, body, cc, bcc, attachments, current_time):
    """Send via SMTP and log result.

    This function maintains backward compatibility with existing code while
    using the new SMTPClient class internally. Database logging functions
    are imported at call time to avoid circular dependencies.
    """
    # Deferred imports to avoid circular dependencies
    from .email_service import get_appropriate_sender_id, safe_log_email
    from .reports import log_email_metrics

    # Use the new SMTPClient
    client = SMTPClient()
    result = client.send(recipient_email, subject, body, cc, bcc, attachments)

    if result:
        try:
            def _log_and_inbox(cursor):
                cursor.execute("SELECT id FROM users WHERE email = ?", (recipient_email,))
                recipient_user = cursor.fetchone()
                if recipient_user:
                    recipient_id = recipient_user[0]
                    sender_id = get_appropriate_sender_id(
                        cursor,
                        config['sender_email'],
                        config['sender_name'],
                        current_time,
                    )

                    cursor.execute('''
                    INSERT INTO messages (
                        sender_id, recipient_id, subject, message, content,
                        attachment_path, is_read, sent_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    ''', (sender_id, recipient_id, subject, body, body, attachments, current_time))

                safe_log_email(cursor, recipient_email, subject, current_time, 'sent',
                               sender_email=config['sender_email'], sender_name=config['sender_name'],
                               cc_recipients=cc, bcc_recipients=bcc, attachment_info=attachments)

            execute_db_operation(_log_and_inbox)
            log_email_metrics('sent')
        except Exception as e:
            logger.warning("Failed to log email after successful send: %s", e)

        return True
    else:
        log_email_metrics('failed')
        log_event('error', f"SMTP send failed for {recipient_email}")
        return False
