"""Shared email template rendering for all Education System subsystems.

Uses ``string.Template`` from the standard library (no Jinja2 dependency).
Templates use ``$variable`` or ``${variable}`` placeholder syntax.

Usage::

    from education_system.platform.integrations.email.email_templates import render_template

    subject, body, html = render_template(
        "welcome",
        user_name="Alice",
        system_name="College System",
        login_url="https://college.example.com/login",
    )
"""

from __future__ import annotations

import logging
from string import Template
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------
# Each template is a dict with keys: subject, body, html_body.
# All three values are ``string.Template`` compatible strings.

BUILTIN_TEMPLATES: Dict[str, Dict[str, str]] = {
    "welcome": {
        "subject": "Welcome to $system_name",
        "body": (
            "Hello $user_name,\n\n"
            "Welcome to $system_name! Your account has been created.\n\n"
            "You can log in at: $login_url\n\n"
            "If you have any questions, please contact your administrator.\n\n"
            "Best regards,\n"
            "$system_name"
        ),
        "html_body": (
            '<html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">'
            '<div style="max-width:520px;margin:auto;background:#fff;border-radius:8px;'
            'box-shadow:0 2px 8px rgba(0,0,0,.1);padding:30px">'
            '<h2 style="color:#2c3e50;margin-top:0">Welcome to $system_name</h2>'
            "<p>Hello <strong>$user_name</strong>,</p>"
            "<p>Your account has been created successfully.</p>"
            '<p>You can log in here: <a href="$login_url">$login_url</a></p>'
            '<p style="color:#666">If you have any questions, please contact '
            "your administrator.</p>"
            '<hr style="border:none;border-top:1px solid #eee;margin:20px 0">'
            '<p style="color:#999;font-size:12px">$system_name</p>'
            "</div></body></html>"
        ),
    },
    "password_reset": {
        "subject": "Password Reset - $system_name",
        "body": (
            "Hello $user_name,\n\n"
            "A password reset was requested for your account.\n\n"
            "Your reset code is: $reset_code\n\n"
            "This code expires in $expiry_minutes minutes.\n\n"
            "If you did not request this, please ignore this email.\n\n"
            "Best regards,\n"
            "$system_name"
        ),
        "html_body": (
            '<html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">'
            '<div style="max-width:520px;margin:auto;background:#fff;border-radius:8px;'
            'box-shadow:0 2px 8px rgba(0,0,0,.1);padding:30px">'
            '<h2 style="color:#2c3e50;margin-top:0">Password Reset</h2>'
            "<p>Hello <strong>$user_name</strong>,</p>"
            "<p>A password reset was requested for your account.</p>"
            '<div style="text-align:center;margin:25px 0">'
            '<span style="font-size:28px;font-weight:bold;letter-spacing:4px;'
            "color:#2c3e50;background:#f0f0f0;padding:12px 24px;"
            'border-radius:8px;display:inline-block">$reset_code</span>'
            "</div>"
            '<p style="color:#666">This code expires in '
            "<strong>$expiry_minutes minutes</strong>.</p>"
            '<hr style="border:none;border-top:1px solid #eee;margin:20px 0">'
            '<p style="color:#999;font-size:12px">'
            "If you did not request this, please ignore this email.</p>"
            "</div></body></html>"
        ),
    },
    "notification": {
        "subject": "$notification_title - $system_name",
        "body": (
            "Hello $user_name,\n\n"
            "$notification_body\n\n"
            "Best regards,\n"
            "$system_name"
        ),
        "html_body": (
            '<html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">'
            '<div style="max-width:520px;margin:auto;background:#fff;border-radius:8px;'
            'box-shadow:0 2px 8px rgba(0,0,0,.1);padding:30px">'
            '<h2 style="color:#2c3e50;margin-top:0">$notification_title</h2>'
            "<p>Hello <strong>$user_name</strong>,</p>"
            "<p>$notification_body</p>"
            '<hr style="border:none;border-top:1px solid #eee;margin:20px 0">'
            '<p style="color:#999;font-size:12px">$system_name</p>'
            "</div></body></html>"
        ),
    },
    "announcement": {
        "subject": "Announcement: $announcement_title - $system_name",
        "body": (
            "Hello $user_name,\n\n"
            "--- Announcement ---\n\n"
            "$announcement_title\n\n"
            "$announcement_body\n\n"
            "Posted by: $posted_by\n"
            "Date: $posted_date\n\n"
            "Best regards,\n"
            "$system_name"
        ),
        "html_body": (
            '<html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">'
            '<div style="max-width:520px;margin:auto;background:#fff;border-radius:8px;'
            'box-shadow:0 2px 8px rgba(0,0,0,.1);padding:30px">'
            '<div style="background:#3498db;color:#fff;padding:10px 20px;'
            'border-radius:6px 6px 0 0;margin:-30px -30px 20px -30px">'
            '<h2 style="margin:0">Announcement</h2></div>'
            "<h3>$announcement_title</h3>"
            "<p>Hello <strong>$user_name</strong>,</p>"
            "<p>$announcement_body</p>"
            '<p style="color:#888;font-size:13px">'
            "Posted by <strong>$posted_by</strong> on $posted_date</p>"
            '<hr style="border:none;border-top:1px solid #eee;margin:20px 0">'
            '<p style="color:#999;font-size:12px">$system_name</p>'
            "</div></body></html>"
        ),
    },
    "attendance_alert": {
        "subject": "Attendance Alert: $student_name - $system_name",
        "body": (
            "Hello $recipient_name,\n\n"
            "This is an attendance alert for $student_name.\n\n"
            "Date: $alert_date\n"
            "Status: $attendance_status\n"
            "Session: $session_info\n\n"
            "$additional_notes\n\n"
            "Please contact the school if you have any questions.\n\n"
            "Best regards,\n"
            "$system_name"
        ),
        "html_body": (
            '<html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">'
            '<div style="max-width:520px;margin:auto;background:#fff;border-radius:8px;'
            'box-shadow:0 2px 8px rgba(0,0,0,.1);padding:30px">'
            '<div style="background:#e74c3c;color:#fff;padding:10px 20px;'
            'border-radius:6px 6px 0 0;margin:-30px -30px 20px -30px">'
            '<h2 style="margin:0">Attendance Alert</h2></div>'
            "<p>Hello <strong>$recipient_name</strong>,</p>"
            "<p>This is an attendance alert for "
            "<strong>$student_name</strong>.</p>"
            '<table style="width:100%;border-collapse:collapse;margin:15px 0">'
            '<tr><td style="padding:8px;border-bottom:1px solid #eee;'
            'font-weight:bold;width:120px">Date</td>'
            '<td style="padding:8px;border-bottom:1px solid #eee">'
            "$alert_date</td></tr>"
            '<tr><td style="padding:8px;border-bottom:1px solid #eee;'
            'font-weight:bold">Status</td>'
            '<td style="padding:8px;border-bottom:1px solid #eee">'
            "$attendance_status</td></tr>"
            '<tr><td style="padding:8px;border-bottom:1px solid #eee;'
            'font-weight:bold">Session</td>'
            '<td style="padding:8px;border-bottom:1px solid #eee">'
            "$session_info</td></tr></table>"
            "<p>$additional_notes</p>"
            '<p style="color:#666">Please contact the school if you have '
            "any questions.</p>"
            '<hr style="border:none;border-top:1px solid #eee;margin:20px 0">'
            '<p style="color:#999;font-size:12px">$system_name</p>'
            "</div></body></html>"
        ),
    },
}

# Registry of custom templates added at runtime
_custom_templates: Dict[str, Dict[str, str]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_template(
    template_name: str, **context
) -> Tuple[str, str, Optional[str]]:
    """Render a named email template with the given context variables.

    Args:
        template_name: Name of a built-in or registered custom template.
        **context: Keyword arguments substituted into the template using
            ``string.Template.safe_substitute`` (unknown placeholders are
            left as-is rather than raising an error).

    Returns:
        A 3-tuple of ``(subject, body, html_body)``.  ``html_body`` may be
        ``None`` if the template has no HTML variant.

    Raises:
        KeyError: If *template_name* is not found.
    """
    tpl = get_template(template_name)

    subject = Template(tpl["subject"]).safe_substitute(context)
    body = Template(tpl["body"]).safe_substitute(context)

    html_body = None
    if tpl.get("html_body"):
        html_body = Template(tpl["html_body"]).safe_substitute(context)

    return subject, body, html_body


def get_template(name: str) -> Dict[str, str]:
    """Return the raw template dict for *name*.

    Checks custom templates first, then built-ins.

    Raises:
        KeyError: If the template is not found.
    """
    if name in _custom_templates:
        return _custom_templates[name]
    if name in BUILTIN_TEMPLATES:
        return BUILTIN_TEMPLATES[name]
    raise KeyError(f"Email template not found: {name}")


def register_template(
    name: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
) -> None:
    """Register (or overwrite) a custom email template at runtime.

    This does **not** modify the built-in templates; it adds to a separate
    custom registry that is checked first by ``get_template``.
    """
    _custom_templates[name] = {
        "subject": subject,
        "body": body,
        "html_body": html_body or "",
    }
    logger.debug("Registered custom email template: %s", name)


def list_templates() -> List[str]:
    """Return sorted list of all available template names."""
    names = set(BUILTIN_TEMPLATES.keys()) | set(_custom_templates.keys())
    return sorted(names)


def template_exists(name: str) -> bool:
    """Return True if a template with *name* exists."""
    return name in _custom_templates or name in BUILTIN_TEMPLATES
