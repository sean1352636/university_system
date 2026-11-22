"""SMTP utilities used by the email infrastructure.

This module provides SMTP functionality with dependency injection to avoid
circular imports. The SMTPClient class handles pure SMTP operations, while
database logging is handled through injected callbacks.
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from html import unescape
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Optional, Protocol

from education_system.systems.university.infrastructure.email.config import config
from education_system.systems.university.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.systems.university.infrastructure.logs import log_event
from education_system.systems.university.infrastructure.exceptions import AttachmentError

logger = logging.getLogger(__name__)

# A body is treated as HTML when it opens with a doctype/<html> or clearly
# carries block markup. Deliberately conservative: a plain-text body that
# merely mentions "<3" or "a < b" must not be misclassified, because sending
# text as text/html would swallow it as an unknown tag.
_HTML_BODY_RE = re.compile(
    r'^\s*(?:<!doctype\s+html|<html\b)|<(?:div|table|p|br\s*/?|h[1-6]|body)\b[^>]*>',
    re.IGNORECASE,
)

_FULL_DOCUMENT_RE = re.compile(r'^\s*(?:<!doctype\s+html|<html\b)', re.IGNORECASE)

_BLOCK_BREAK_RE = re.compile(
    r'</(?:p|div|tr|h[1-6]|li|ul|ol|table|thead|tbody)\s*>|<br\s*/?>', re.IGNORECASE)
_CELL_BREAK_RE = re.compile(r'</(?:td|th)\s*>', re.IGNORECASE)
_DROP_BLOCK_RE = re.compile(r'<(head|style|script)\b.*?</\1\s*>', re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r'<[^>]+>')


def body_is_html(body: str) -> bool:
    """Whether *body* should be delivered as text/html."""
    return bool(body) and bool(_HTML_BODY_RE.search(body))


def html_to_plain_text(html_body: str) -> str:
    """Best-effort plain-text alternative for an HTML body.

    Used for the text/plain part of a multipart/alternative message so
    text-only clients get something readable rather than raw markup. This is
    not a full renderer — it keeps block structure and drops the rest.
    """
    text = _DROP_BLOCK_RE.sub('', html_body)
    text = _CELL_BREAK_RE.sub('\t', text)
    text = _BLOCK_BREAK_RE.sub('\n', text)
    text = _TAG_RE.sub('', text)
    text = unescape(text)
    # Collapse the runs of blank lines the tag stripping leaves behind, and
    # trim trailing whitespace each line picked up from the source indentation.
    lines = [line.strip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return '\n'.join(out).strip()


def _text_part(text: str, subtype: str) -> MIMEText:
    """A MIMEText part that stays human-readable on the wire when it can.

    Declaring utf-8 makes Python base64-encode the payload, which is correct
    but turns an ASCII body into an opaque blob for anything reading the raw
    message. Only reach for utf-8 when the content actually needs it.
    """
    if text.isascii():
        return MIMEText(text, subtype)
    return MIMEText(text, subtype, 'utf-8')


def _branded(make, styled):
    """``make(html_layout)``, or ``None`` when the design is off or fails.
    A problem in the design must never stop an e-mail going out."""
    try:
        from education_system.systems.university.infrastructure.email import html_layout
        if styled is None and not html_layout.enabled():
            return None
        return make(html_layout)
    except Exception:
        logger.warning("Branded e-mail layout failed; sending plain text", exc_info=True)
        return None


def build_message(
    subject: str,
    body: str,
    from_header: str,
    to_header: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    html_body: Optional[str] = None,
    reply_to: Optional[str] = None,
    styled: Optional[bool] = None,
) -> MIMEMultipart:
    """Assemble the outgoing message, using multipart/alternative for HTML.

    A plain-text body is sent with a branded HTML version beside it (see
    ``html_layout``), and an HTML fragment is framed the same way; a full HTML
    document is sent as written. ``styled`` forces the choice; ``None`` follows
    the ``html_layout`` e-mail setting.

    ``html_body`` may be passed explicitly; otherwise an HTML-looking ``body``
    is detected and paired with a generated plain-text alternative. Callers
    that already have both (a template's body_text plus body_html) should pass
    ``body`` as the text and ``html_body`` as the markup.
    """
    logo = None
    if html_body is None and body_is_html(body):
        html_body = body
        body = html_to_plain_text(body)
        if styled is not False and not _FULL_DOCUMENT_RE.match(html_body):
            fragment = html_body
            branded = _branded(lambda layout: layout.email_html(subject, fragment, True, body),
                               styled)
            if branded:
                html_body, logo = branded
    elif html_body is None and body and styled is not False:
        # Plain text gets the branded HTML version beside it; the text part
        # below is the original, unchanged.
        branded = _branded(lambda layout: layout.email_html(subject, body), styled)
        if branded:
            html_body, logo = branded

    if html_body is not None:
        msg = MIMEMultipart('alternative')
        # Order matters: least-preferred part first, so clients that can
        # render HTML pick the last one.
        msg.attach(_text_part(body or '', 'plain'))
        if logo:
            # The header logo travels with the page (multipart/related) and is
            # shown by Content-ID, so mail clients that block remote images
            # still show it.
            from email.mime.image import MIMEImage
            from education_system.systems.university.infrastructure.email.html_layout import (
                LOGO_CID,
            )
            related = MIMEMultipart('related')
            related.attach(_text_part(html_body, 'html'))
            image = MIMEImage(logo['data'], logo['subtype'])
            image.add_header('Content-ID', f'<{LOGO_CID}>')
            image.add_header('Content-Disposition', 'inline',
                             filename=f"logo.{'jpg' if logo['subtype'] == 'jpeg' else logo['subtype']}")
            related.attach(image)
            msg.attach(related)
        else:
            msg.attach(_text_part(html_body, 'html'))
    else:
        msg = MIMEMultipart()
        msg.attach(_text_part(body or '', 'plain'))

    msg['From'] = from_header
    msg['To'] = to_header
    msg['Subject'] = subject
    if cc:
        msg['Cc'] = cc
    if bcc:
        msg['Bcc'] = bcc
    if reply_to:
        msg['Reply-To'] = reply_to
    return msg


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

    @staticmethod
    def _validate_email_header(value: str) -> str:
        """Reject email header values containing CRLF characters to prevent header injection."""
        if '\r' in value or '\n' in value:
            raise ValueError(f"Email header value contains illegal newline characters: {value!r}")
        return value

    def send(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        attachments: Optional[str] = None,
        html_body: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP.

        Args:
            recipient_email: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Comma-separated CC recipients
            bcc: Comma-separated BCC recipients
            attachments: Comma-separated attachment file paths
            html_body: HTML alternative. Omit and an HTML-looking ``body`` is
                detected automatically, which is how the JSON templates with a
                ``body_html`` are delivered.

        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            self.send_or_raise(recipient_email, subject, body, cc, bcc, attachments, html_body)
            return True
        except Exception as e:
            logger.error("SMTP send failed: %s", e)
            return False

    def send_or_raise(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        attachments: Optional[str] = None,
        html_body: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> None:
        """:meth:`send`, raising the SMTP error instead of returning False, so
        the outbox can tell a refused address from a temporary failure."""
        # Validate all header fields against CRLF injection
        self._validate_email_header(recipient_email)
        self._validate_email_header(subject)
        if cc:
            self._validate_email_header(cc)
        if bcc:
            self._validate_email_header(bcc)
        if reply_to:
            self._validate_email_header(reply_to)

        msg = build_message(
            subject=subject,
            body=body,
            from_header=f"{self.config.sender_name} <{self.config.sender_email}>",
            to_header=recipient_email,
            cc=cc,
            html_body=html_body,
            reply_to=reply_to,
        )

        if attachments:
            # Attachments are siblings of the *whole* body, so a
            # multipart/alternative body has to be nested inside a
            # multipart/mixed wrapper rather than gaining a file part —
            # otherwise clients treat the attachment as another
            # representation of the message and show only one of them.
            if msg.get_content_subtype() == 'alternative':
                wrapper = MIMEMultipart('mixed')
                for header in ('From', 'To', 'Subject', 'Cc', 'Bcc', 'Reply-To'):
                    if msg[header]:
                        wrapper[header] = msg[header]
                        del msg[header]
                wrapper.attach(msg)
                msg = wrapper

            for file_path in attachments.split(','):
                file_path = file_path.strip()
                if not file_path or not os.path.isfile(file_path):
                    raise AttachmentError(
                        f"Attachment does not exist or is not a file: {file_path}",
                        code="EMAIL_ATTACHMENT_NOT_FOUND",
                        details={"path": file_path},
                    )
                if os.path.getsize(file_path) > config.get('attachment_size_limit', 10 * 1024 * 1024):
                    raise AttachmentError(
                        f"Attachment exceeds the configured size limit: {file_path}",
                        code="EMAIL_ATTACHMENT_TOO_LARGE",
                        details={"path": file_path},
                    )
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
    """Kept for old callers: the message goes to the university outbox,
    which sends it according to the delivery mode, with retries."""
    from education_system.systems.university.infrastructure.email import outbox_delivery
    try:
        result = outbox_delivery.enqueue(recipient_email, subject, body, cc=cc, bcc=bcc,
                                         attachments=attachments)
    except Exception as exc:
        log_event('error', f"E-mail to {recipient_email} not added to the outbox: {exc}")
        return False
    return result["status"] in ("queued", "stored")
