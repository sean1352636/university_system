"""JSON email templates for the FE College system.

Templates live at ``assets/templates/email/<name>.json`` inside the
package — shipped with the code, not editable runtime state. Each file
describes one outbound message::

    {
      "subject": "Welcome to {{college_name}}, {{first_name}}",
      "body":    "Hi {{first_name}}, ...",
      "from_name": "FE College Admissions",
      "from_address": "admissions@fecollege.ac.uk",
      "channel": "Email",           # optional, default Email
      "category": "Admissions",     # optional, default General
      "priority": "Normal"          # optional, default Normal
    }

``{{placeholder}}`` tokens in the subject/body/from_* fields are
substituted from the ``context`` dict the caller supplies. An unknown
token is left in place rather than raising, so a missing field shows up
in the drafted message — visibly wrong, and fixable before sending —
instead of failing at the call site, which is often somewhere that must
not break (learner creation, an enrolment).

Mirrors ``sixth_form`` and ``nursery``'s equivalents, over this system's
own message log.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from education_system import paths
from education_system.systems.fe_college.services import email_service

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class TemplateError(Exception):
    """Raised when a template cannot be found or parsed."""


def list_templates() -> list[str]:
    """Available template names (filename stems), sorted."""
    directory = paths.FE_COLLEGE_EMAIL_TEMPLATES_DIR
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


def load_template(name: str) -> dict[str, Any]:
    """Load and parse one template by filename stem."""
    path = paths.FE_COLLEGE_EMAIL_TEMPLATES_DIR / f"{name}.json"
    if not path.is_file():
        raise TemplateError(f"Email template not found: {name}")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise TemplateError(
            f"Email template {name} is not valid JSON: {exc}") from exc


def render(text: str, context: dict[str, Any]) -> str:
    """Substitute ``{{key}}`` tokens in ``text`` from ``context``."""
    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context and context[key] is not None:
            return str(context[key])
        return match.group(0)
    return _PLACEHOLDER_RE.sub(_sub, text)


def placeholders(name: str) -> list[str]:
    """Every token a template expects, so a screen can prompt for them."""
    tpl = load_template(name)
    found: set[str] = set()
    for field in ("subject", "body", "from_name", "from_address"):
        found.update(_PLACEHOLDER_RE.findall(tpl.get(field, "") or ""))
    return sorted(found)


def preview(name: str, context: dict[str, Any]) -> tuple[str, str]:
    """Render a template without writing anything. Returns (subject, body)."""
    tpl = load_template(name)
    return (render(tpl.get("subject", ""), context).strip(),
            render(tpl.get("body", ""), context))


def compose_from_template(
    name: str,
    context: dict[str, Any],
    *,
    to_name: str = "",
    to_address: str = "",
    student_id: str = "",
    staff_id: str = "",
    send_now: bool = False,
) -> email_service.SendResult:
    """Render a template into the message log.

    Saved as a draft unless ``send_now``, matching ``compose`` — a
    templated message is still read back before it goes out.
    """
    tpl = load_template(name)
    subject, body = preview(name, context)
    result = email_service.compose(
        subject=subject,
        body=body,
        to_name=to_name,
        to_address=to_address,
        category=tpl.get("category", "General"),
        priority=tpl.get("priority", "Normal"),
        channel=tpl.get("channel", "Email"),
        student_id=student_id,
        staff_id=staff_id,
        from_name=render(tpl.get("from_name", "") or "", context),
        from_address=render(tpl.get("from_address", "") or "", context),
        tags=f"template:{name}",
        send_now=send_now,
    )
    logger.info("Composed template '%s' as %s to %s",
                name, result.message.message_id, to_address or "-")
    return result


__all__ = [
    "TemplateError",
    "list_templates",
    "load_template",
    "render",
    "placeholders",
    "preview",
    "compose_from_template",
]
