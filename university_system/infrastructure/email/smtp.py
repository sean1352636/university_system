"""SMTP utilities used by the email infrastructure."""

from __future__ import annotations

import os
import smtplib
import ssl

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from university_system.infrastructure.email.config import config
from university_system.infrastructure.email.email_db_utilities import execute_db_operation
from university_system.modules.shared.utils.logs import log_event


def send_email_via_smtp(recipient_email, subject, body, cc, bcc, attachments, current_time):
    """Send via SMTP and log result"""
    from .email_service import get_appropriate_sender_id, safe_log_email
    from .reports import log_email_metrics

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{config['sender_name']} <{config['sender_email']}>"
        msg['To'] = recipient_email
        msg['Subject'] = subject
        if cc:
            msg['Cc'] = cc
        if bcc:
            msg['Bcc'] = bcc
        msg.attach(MIMEText(body, 'plain'))

        if attachments:
            for file_path in attachments.split(','):
                with open(file_path.strip(), 'rb') as file:
                    part = MIMEApplication(file.read(), Name=os.path.basename(file_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    msg.attach(part)

        all_recipients = [recipient_email] + (cc.split(',') if cc else []) + (bcc.split(',') if bcc else [])

        context = ssl.create_default_context()
        with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
            if config.get('use_tls'):
                server.starttls(context=context)
            if config.get('use_authentication'):
                server.login(config['username'], config['password'])
            server.sendmail(config['sender_email'], all_recipients, msg.as_string())

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

        return True

    except Exception as e:
        log_email_metrics('failed')
        log_event('error', f"SMTP send failed: {e}")
        return False
