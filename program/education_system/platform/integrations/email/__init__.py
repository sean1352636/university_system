"""Shared email infrastructure for the Education System.

Modules
-------
- ``config``          -- SMTP configuration loading (JSON + env vars + keyring)
- ``otp_sender``      -- One-time-password email delivery
- ``email_service``   -- Core ``EmailService`` class wrapping smtplib
- ``email_templates`` -- JSON email templates with ``string.Template`` rendering.
  The templates themselves live in ``platform/assets/templates/email/``,
  one JSON file per message.
- ``email_queue``     -- Threaded background queue with retry logic

Quick-start::

    from education_system.platform.integrations.email import EmailService, EmailQueue, render_template

    svc = EmailService()                    # reads shared config automatically
    svc.send_email("user@example.com", "Hi", "Hello there")

    # Templated email
    subject, body, html = render_template("welcome", user_name="Alice",
                                          system_name="College System",
                                          login_url="https://college.example.com")
    svc.send_email("alice@example.com", subject, body, html_body=html)

    # Async queue
    q = EmailQueue(svc)
    q.start()
    q.enqueue("bob@example.com", "News", "Latest updates...")
    q.stop()
"""

from education_system.platform.integrations.email.email_service import (
    EmailService,
    EmailMessage,
    EmailError,
)
from education_system.platform.integrations.email.email_templates import (
    render_template,
    get_template,
    register_template,
    list_templates,
    template_exists,
    builtin_templates,
    reload_templates,
)
from education_system.platform.integrations.email.email_queue import EmailQueue
from education_system.platform.integrations.email.config import load_email_config, save_email_config


def __getattr__(name: str):
    """Resolve ``BUILTIN_TEMPLATES`` without reading disk at import.

    It was a dict of template content; the content is now JSON on disk.
    Importing this package should not read every template file for a name
    most callers never touch, so it is resolved on access instead.
    """
    if name == "BUILTIN_TEMPLATES":
        return builtin_templates()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Core service
    "EmailService",
    "EmailMessage",
    "EmailError",
    # Templates
    "render_template",
    "get_template",
    "register_template",
    "list_templates",
    "template_exists",
    "builtin_templates",
    "reload_templates",
    "BUILTIN_TEMPLATES",
    # Queue
    "EmailQueue",
    # Config
    "load_email_config",
    "save_email_config",
]
