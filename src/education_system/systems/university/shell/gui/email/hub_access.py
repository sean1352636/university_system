"""Who may use which part of the Communication Hub, and the one safe way
the hub saves SMTP settings.

* Bulk sending is checked by ``email_admin.send_bulk`` itself.
* Configuration, templates, the queue and the Delivery screen need an
  administrator or the ``email_admin`` e-mail role
  (``application/mail/outbox.holds``).
* :func:`save_smtp_settings` edits the shared config file in place, keeping
  every key it does not change, and never writes a password into it: a
  password typed in the hub goes to the keyring or the owner-only secrets
  file (``platform/integrations/email/config``).
"""

from __future__ import annotations

import json
import logging
from tkinter import messagebox

logger = logging.getLogger(__name__)

TITLE = "Communication Hub"

# Settings the hub may write to the shared config file.
SMTP_KEYS = ("smtp_server", "smtp_port", "smtp_username", "sender_email", "sender_name",
             "use_tls", "use_authentication")


def user_of(auth) -> tuple[str, str]:
    """``(username, role)`` of the signed-in user, or ``("", "")``."""
    who = getattr(auth, "current_user", None) or {}
    if not isinstance(who, dict):
        return "", ""
    return str(who.get("username") or ""), str(who.get("role") or "")


def is_email_admin(auth) -> bool:
    username, role = user_of(auth)
    if not username:
        return False
    from education_system.systems.university.application.mail import outbox as email_outbox
    from education_system.systems.university.infrastructure.database.db import get_connection
    if email_outbox.is_admin(role):
        return True
    conn = get_connection(row_factory=False)
    try:
        result = email_outbox.holds(conn, username, "email_admin", role)
        conn.commit()
        return result
    except Exception:
        logger.exception("e-mail role check failed")
        return False
    finally:
        conn.close()


def require_email_admin(auth, parent=None) -> bool:
    """True when allowed; otherwise explains the refusal and returns False."""
    if is_email_admin(auth):
        return True
    messagebox.showerror(TITLE, "Only an e-mail administrator can use this. Ask an "
                                "administrator to give you the email_admin role.",
                         parent=parent)
    return False


def save_smtp_settings(values: dict, password: str = "") -> None:
    """Update the SMTP settings in the shared config file, keeping every
    other key (the delivery mode is changed only through
    ``outbox_delivery.set_mode``). A ``password`` goes to secure storage."""
    from education_system import paths
    from education_system.platform.integrations.email import config as platform_config
    path = paths.PLATFORM_EMAIL_CONFIG_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    for key in SMTP_KEYS:
        if key in values:
            raw[key] = values[key]
    if password:
        username = str(raw.get("smtp_username") or "")
        stored = False
        try:
            stored = bool(username) and platform_config.set_smtp_password(username, password)
        except RuntimeError:
            stored = False
        if not stored:
            platform_config.write_secret_file(password)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    tmp.replace(path)


def smtp_settings() -> dict:
    """The current SMTP settings from the shared config file, no password."""
    from education_system.systems.university.infrastructure.email import outbox_delivery
    return outbox_delivery.file_config()
