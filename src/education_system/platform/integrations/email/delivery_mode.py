"""How e-mail leaves the system: ``inbox_only`` / ``sandbox`` / ``live``.

The setting lives in the shared e-mail config file (``delivery_mode``; when
unset, ``database_only_mode`` true means ``inbox_only`` and false means
``live``) — the same rule the university outbox uses
(``systems/university/infrastructure/email/outbox_delivery``). Code that
sends outside an outbox (the account-security e-mails in
``platform/identity/auth/core``) asks :func:`deliver` instead of opening an
SMTP connection itself, so nothing goes out while the system is not live.
Sign-in one-time codes are not routed here: they must arrive for the
person to sign in at all.
"""

from __future__ import annotations

import json
import logging
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

logger = logging.getLogger(__name__)

MODES = ("inbox_only", "sandbox", "live")


def delivery_mode() -> str:
    from education_system import paths
    try:
        cfg = json.loads(paths.PLATFORM_EMAIL_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    mode = str(cfg.get("delivery_mode") or "").strip().lower()
    if mode in MODES:
        return mode
    return "inbox_only" if cfg.get("database_only_mode", True) else "live"


def _write_sandbox(recipient, subject, body) -> str:
    from education_system import paths
    message = EmailMessage()
    message["To"] = recipient
    message["From"] = "noreply@localhost"
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()
    message.set_content(body)
    folder = paths.PLATFORM_EMAIL_SANDBOX_DIR
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{message['Message-ID'].strip('<>').replace('@', '_')}.eml"
    target.write_text(message.as_string(), encoding="utf-8")
    return str(target)


def deliver(recipient, subject, body, send_live) -> bool:
    """Send ``(recipient, subject, body)`` according to the delivery mode:
    ``live`` calls ``send_live()``; ``sandbox`` writes an .eml file;
    ``inbox_only`` sends nothing. Returns whether it was delivered (sent or
    written)."""
    mode = delivery_mode()
    if mode == "live":
        return bool(send_live())
    if mode == "sandbox":
        path = _write_sandbox(recipient, subject, body)
        logger.info("E-mail to %s written to the sandbox (%s)", recipient, path)
        return True
    logger.info("E-mail to %s not sent: delivery mode is inbox_only", recipient)
    return False
