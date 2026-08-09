"""JSON email templates for the apprenticeships system.

Templates live at ``assets/templates/email/<name>.json`` inside the
package — shipped with the code, not editable runtime state. Each file
describes one outbound message::

    {
      "subject": "Progress review booked — {{apprentice_name}}",
      "body":    "Dear {{recipient_name}}, ...",
      "from_name": "Apprenticeships",
      "from_address": "training@provider.ac.uk",
      "channel": "Email",          # optional, default Email
      "category": "Review",        # optional, default General
      "priority": "Normal"         # optional, default Normal
    }

``{{placeholder}}`` tokens are substituted from the ``context`` the
caller supplies. An unknown token is left in place rather than raising,
so a missing field shows up in the drafted message — visible and fixable
before it goes out — instead of failing at a call site that must not
break.

Mirrors the equivalents in ``fe_college``, ``sixth_form`` and
``nursery``, over this system's own scoped message log.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from education_system import paths
from education_system.systems.apprenticeships.services import email_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class TemplateError(Exception):
    """Raised when a template cannot be found or parsed."""


def list_templates() -> list[str]:
    """Available template names (filename stems), sorted."""
    directory = paths.APPRENTICESHIPS_EMAIL_TEMPLATES_DIR
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


def load_template(name: str) -> dict[str, Any]:
    """Load and parse one template by filename stem."""
    path = paths.APPRENTICESHIPS_EMAIL_TEMPLATES_DIR / f"{name}.json"
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
    """Render without writing anything. Returns ``(subject, body)``."""
    tpl = load_template(name)
    return (render(tpl.get("subject", ""), context).strip(),
            render(tpl.get("body", ""), context))


def compose_from_template(
    actor: Actor,
    name: str,
    context: dict[str, Any],
    *,
    to_name: str = "",
    to_address: str = "",
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    send_now: bool = False,
) -> email_service.SendResult:
    """Render a template into the message log.

    Permission and scoping are enforced by ``email_service.compose``, so
    a template cannot be used to write to somebody the actor could not
    otherwise address.
    """
    tpl = load_template(name)
    subject, body = preview(name, context)
    result = email_service.compose(
        actor,
        subject=subject,
        body=body,
        to_name=to_name,
        to_address=to_address,
        category=tpl.get("category", "General"),
        priority=tpl.get("priority", "Normal"),
        channel=tpl.get("channel", "Email"),
        apprentice_id=apprentice_id,
        employer_id=employer_id,
        tags=f"template:{name}",
        send_now=send_now,
    )
    logger.info("%s composed template '%s' as %s to %s",
                actor.username, name, result.message_id, to_address or "-")
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
