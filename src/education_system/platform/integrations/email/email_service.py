"""Shared email sending service for all Education System subsystems.

Wraps smtplib to provide a simple, consistent email API.  Configuration is
loaded from the shared email config (JSON file / env vars) via ``config.py``.

Usage::

    from education_system.platform.integrations.email.email_service import EmailService

    svc = EmailService()
    svc.send_email("user@example.com", "Hello", "Body text")
    svc.send_bulk_email(["a@b.com", "c@d.com"], "News", "Content")

Environment variable overrides (take precedence over JSON config):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_FROM_NAME
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional, Sequence

from education_system.platform.integrations.email.config import load_email_config

logger = logging.getLogger(__name__)

# Simple email regex for basic validation
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


@dataclass
class EmailMessage:
    """Value object representing a single email message."""

    to: str
    subject: str
    body: str
    html_body: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    attachments: Optional[List[str]] = None
    from_address: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)

    def all_recipients(self) -> List[str]:
        """Return a flat list of all recipient addresses."""
        recipients = [self.to]
        if self.cc:
            recipients.extend(self.cc)
        if self.bcc:
            recipients.extend(self.bcc)
        return recipients


class EmailError(Exception):
    """Raised when an email operation fails."""


class EmailService:
    """Core email sending service.

    Reads SMTP settings from the shared email config on construction.
    Environment variables override JSON config values.
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_address: Optional[str] = None,
        from_name: Optional[str] = None,
        use_tls: Optional[bool] = None,
        timeout: int = 30,
    ):
        cfg = load_email_config()

        # Resolution: env vars > explicit args > JSON config
        self.smtp_host = (
            os.environ.get("SMTP_HOST")
            or smtp_host
            or cfg.get("smtp_server", "")
        )
        self.smtp_port = int(
            os.environ.get("SMTP_PORT")
            or (smtp_port if smtp_port is not None else 0)
            or cfg.get("smtp_port", 587)
        )
        self.smtp_user = (
            os.environ.get("SMTP_USER")
            or smtp_user
            or cfg.get("smtp_username", "")
        )
        self.smtp_password = (
            os.environ.get("SMTP_PASSWORD")
            or smtp_password
            or cfg.get("smtp_password", "")
        )
        self.from_address = (
            os.environ.get("SMTP_FROM")
            or from_address
            or cfg.get("sender_email", "")
            or self.smtp_user
        )
        self.from_name = (
            os.environ.get("SMTP_FROM_NAME")
            or from_name
            or cfg.get("sender_name", "Education System")
        )
        if use_tls is not None:
            self.use_tls = use_tls
        else:
            self.use_tls = cfg.get("use_tls", True)

        self.timeout = timeout

        # Track whether SMTP is properly configured
        self._configured = bool(
            self.smtp_host and self.smtp_user and self.smtp_password
        )

    @property
    def is_configured(self) -> bool:
        """Return True if SMTP settings are present enough to attempt sending."""
        return self._configured

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
    ) -> Dict:
        """Send a single email.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Plain-text body.
            html_body: Optional HTML body (sent as alternative part).
            cc: Optional list of CC addresses.
            bcc: Optional list of BCC addresses.
            attachments: Optional list of file paths to attach.
            reply_to: Optional Reply-To address.

        Returns:
            ``{"success": True}`` on success, or
            ``{"success": False, "error": "..."}`` on failure.
        """
        msg = EmailMessage(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            from_address=self.from_address,
            from_name=self.from_name,
            reply_to=reply_to,
        )
        return self._send(msg)

    def send_bulk_email(
        self,
        recipients: Sequence[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[str]] = None,
    ) -> Dict:
        """Send the same email to multiple recipients.

        Uses BCC so recipients don't see each other's addresses.
        Sends in batches of 50 to respect typical SMTP limits.

        Returns:
            ``{"success": True/False, "sent": N, "failed": N}``
        """
        if not recipients:
            return {
                "success": False,
                "error": "No recipients provided",
                "sent": 0,
                "failed": 0,
            }

        sent = 0
        failed = 0
        errors: List[str] = []

        batch_size = 50
        for i in range(0, len(recipients), batch_size):
            batch = list(recipients[i : i + batch_size])
            to_addr = batch[0]
            bcc_addrs = batch[1:] if len(batch) > 1 else None

            result = self.send_email(
                to=to_addr,
                subject=subject,
                body=body,
                html_body=html_body,
                bcc=bcc_addrs,
                attachments=attachments,
            )
            if result.get("success"):
                sent += len(batch)
            else:
                failed += len(batch)
                errors.append(result.get("error", "Unknown error"))

        return {
            "success": failed == 0,
            "sent": sent,
            "failed": failed,
            "errors": errors if errors else None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_header(value: str) -> str:
        """Reject header values containing CRLF to prevent header injection."""
        if "\r" in value or "\n" in value:
            raise EmailError(
                f"Header value contains illegal newline characters: {value!r}"
            )
        return value

    @staticmethod
    def validate_email(address: str) -> bool:
        """Basic email format validation."""
        return bool(_EMAIL_RE.match(address))

    def _build_mime(self, msg: EmailMessage) -> MIMEMultipart:
        """Build a MIMEMultipart message from an EmailMessage."""
        from_addr = msg.from_address or self.from_address
        from_name = msg.from_name or self.from_name

        mime = MIMEMultipart("alternative")
        mime["From"] = self._validate_header(f"{from_name} <{from_addr}>")
        mime["To"] = self._validate_header(msg.to)
        mime["Subject"] = self._validate_header(msg.subject)

        if msg.cc:
            mime["Cc"] = self._validate_header(", ".join(msg.cc))
        if msg.reply_to:
            mime["Reply-To"] = self._validate_header(msg.reply_to)

        for key, value in msg.headers.items():
            mime[key] = self._validate_header(value)

        # Plain-text part (always present)
        mime.attach(MIMEText(msg.body, "plain", "utf-8"))

        # HTML part (optional)
        if msg.html_body:
            mime.attach(MIMEText(msg.html_body, "html", "utf-8"))

        # File attachments
        if msg.attachments:
            for file_path in msg.attachments:
                file_path = file_path.strip()
                try:
                    with open(file_path, "rb") as fh:
                        part = MIMEApplication(
                            fh.read(), Name=os.path.basename(file_path)
                        )
                        part["Content-Disposition"] = (
                            f'attachment; filename="{os.path.basename(file_path)}"'
                        )
                        mime.attach(part)
                except FileNotFoundError:
                    logger.warning("Attachment not found, skipping: %s", file_path)
                except OSError as exc:
                    logger.warning("Cannot read attachment %s: %s", file_path, exc)

        return mime

    def _send(self, msg: EmailMessage) -> Dict:
        """Send a single EmailMessage via SMTP."""
        if not self._configured:
            logger.warning("SMTP not configured - email to %s not sent", msg.to)
            return {"success": False, "error": "SMTP not configured"}

        if not self.validate_email(msg.to):
            return {"success": False, "error": f"Invalid recipient email: {msg.to}"}

        try:
            mime = self._build_mime(msg)
            recipients = msg.all_recipients()

            context = ssl.create_default_context()

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(
                    self.smtp_host,
                    self.smtp_port,
                    timeout=self.timeout,
                    context=context,
                )
            else:
                server = smtplib.SMTP(
                    self.smtp_host, self.smtp_port, timeout=self.timeout
                )
                if self.use_tls:
                    server.starttls(context=context)

            try:
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_address, recipients, mime.as_string())
                logger.info("Email sent to %s: %s", msg.to, msg.subject[:60])
                return {"success": True}
            finally:
                try:
                    server.quit()
                except smtplib.SMTPException:
                    pass

        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP authentication failed: %s", exc)
            return {"success": False, "error": f"Authentication failed: {exc}"}
        except smtplib.SMTPException as exc:
            logger.error("SMTP error sending to %s: %s", msg.to, exc)
            return {"success": False, "error": str(exc)}
        except OSError as exc:
            logger.error("Network error sending to %s: %s", msg.to, exc)
            return {"success": False, "error": str(exc)}
