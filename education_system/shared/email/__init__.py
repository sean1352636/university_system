"""Shared email infrastructure for the Education System.

Modules
-------
- ``config``          -- SMTP configuration loading (JSON + env vars + keyring)
- ``otp_sender``      -- One-time-password email delivery
- ``email_service``   -- Core ``EmailService`` class wrapping smtplib
- ``email_templates`` -- Built-in email templates with ``string.Template`` rendering
- ``email_queue``     -- Threaded background queue with retry logic

Quick-start::

    from education_system.shared.email import EmailService, EmailQueue, render_template

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

from education_system.shared.email.email_service import (
    EmailService,
    EmailMessage,
    EmailError,
)
from education_system.shared.email.email_templates import (
    render_template,
    get_template,
    register_template,
    list_templates,
    template_exists,
    BUILTIN_TEMPLATES,
)
from education_system.shared.email.email_queue import EmailQueue
from education_system.shared.email.config import load_email_config, save_email_config

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
    "BUILTIN_TEMPLATES",
    # Queue
    "EmailQueue",
    # Config
    "load_email_config",
    "save_email_config",
]
