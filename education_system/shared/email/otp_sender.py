"""Shared email OTP sender for all Education System subsystems.

Sends a 6-digit verification code via SMTP using the shared email config.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict

from education_system.shared.email.config import load_email_config

logger = logging.getLogger(__name__)


def send_otp(
    to_email: str,
    code: str,
    username: str | None = None,
    system_name: str = "Education System",
) -> Dict:
    """Send a verification code email.

    Returns ``{"success": True}`` on success, or
    ``{"success": False, "error": "..."}`` on failure.
    """
    cfg = load_email_config()

    smtp_server = cfg.get("smtp_server", "")
    smtp_port = cfg.get("smtp_port", 587)
    smtp_user = cfg.get("smtp_username", "")
    smtp_pass = cfg.get("smtp_password", "")
    from_email = cfg.get("sender_email", "") or smtp_user
    from_name = cfg.get("sender_name", system_name)
    use_tls = cfg.get("use_tls", True)

    if not all([smtp_server, smtp_user, smtp_pass]):
        return {"success": False, "error": "SMTP not configured"}

    display_name = username or "User"

    # Build message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your Verification Code - {system_name}"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    text_body = (
        f"Hello {display_name},\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code expires in 10 minutes.\n\n"
        f"If you did not request this code, please ignore this email.\n\n"
        f"— {system_name}"
    )
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
<div style="max-width:480px;margin:auto;background:#fff;border-radius:8px;
            box-shadow:0 2px 8px rgba(0,0,0,.1);padding:30px">
  <h2 style="color:#2c3e50;margin-top:0">Verification Code</h2>
  <p>Hello <strong>{display_name}</strong>,</p>
  <p>Your verification code is:</p>
  <div style="text-align:center;margin:25px 0">
    <span style="font-size:32px;font-weight:bold;letter-spacing:6px;
                 color:#2c3e50;background:#f0f0f0;padding:12px 24px;
                 border-radius:8px;display:inline-block">{code}</span>
  </div>
  <p style="color:#666">This code expires in <strong>10 minutes</strong>.</p>
  <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
  <p style="color:#999;font-size:12px">
    If you did not request this code, please ignore this email.
  </p>
</div>
</body></html>"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)

        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        logger.info("OTP email sent to %s", to_email)  # lgtm[py/clear-text-logging-sensitive-data]
        return {"success": True}
    except Exception as exc:
        logger.warning("Failed to send OTP email to %s: %s", to_email, exc)  # lgtm[py/clear-text-logging-sensitive-data]
        return {"success": False, "error": str(exc)}
