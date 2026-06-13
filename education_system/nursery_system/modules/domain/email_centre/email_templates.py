"""JSON email templates for the Nursery System Email / Messaging centre.

Templates live at ``data/templates/email/<name>.json``. Each file describes one
outbound message::

    {
      "subject": "Welcome to {{setting_name}}, {{first_name}}",
      "body":    "Hi {{parent_name}}, ...",
      "from_name": "Nursery Admissions",
      "from_address": "admissions@nursery.sch.uk",
      "channel": "Email",        # optional, default Email
      "category": "Admissions",  # optional, default General
      "priority": "Normal"       # optional, default Normal
    }

``{{placeholder}}`` tokens in the subject/body/from_* fields are substituted
from the ``context`` dict supplied by the caller. Unknown tokens are left in
place rather than raising, so a missing field is visually obvious instead of
crashing the call site.

Mirrors the other systems' ``email_templates`` module, adapted to the nursery's
self-contained message log.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from education_system.nursery_system.core import paths
from education_system.nursery_system.modules.domain.email_centre import (
    email_centre as _messages,
)

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class TemplateError(Exception):
    """Raised when a template cannot be loaded or parsed."""


def list_templates() -> list[str]:
    """Return the available template names (filename stems), sorted."""
    paths.ensure_directories()
    return sorted(p.stem for p in paths.EMAIL_TEMPLATES_DIR.glob("*.json"))


def load_template(name: str) -> dict[str, Any]:
    """Load and JSON-parse one template by filename stem."""
    paths.ensure_directories()
    path = paths.EMAIL_TEMPLATES_DIR / f"{name}.json"
    if not path.is_file():
        raise TemplateError(f"Email template not found: {name}")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise TemplateError(f"Email template {name} is not valid JSON: {e}") from e


def render(text: str, context: dict[str, Any]) -> str:
    """Substitute ``{{key}}`` tokens in ``text`` from ``context``."""
    def _sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in context and context[key] is not None:
            return str(context[key])
        return m.group(0)
    return _PLACEHOLDER_RE.sub(_sub, text)


def send_from_template(
    name: str,
    context: dict[str, Any],
    *,
    to_name: str | None = None,
    to_address: str | None = None,
    pupil_id: str | None = None,
    staff_id: str | None = None,
    status: str = "Sent",
) -> _messages.EmailMessage:
    """Render a template and write it to the message log.

    Returns the newly-created ``EmailMessage``. Raises ``TemplateError`` if the
    template can't be loaded, or ``email_centre.ValidationError`` if the
    rendered payload is invalid (e.g. a malformed ``to_address``).
    """
    tpl = load_template(name)
    subject = render(tpl.get("subject", ""), context).strip()
    body = render(tpl.get("body", ""), context)
    from_name = render(tpl.get("from_name", "") or "", context) or None
    from_address = render(tpl.get("from_address", "") or "", context) or None

    payload: dict[str, Any] = {
        "direction": "Outgoing",
        "channel": tpl.get("channel", "Email"),
        "category": tpl.get("category", "General"),
        "priority": tpl.get("priority", "Normal"),
        "status": status,
        "subject": subject,
        "body": body,
        "from_name": from_name,
        "from_address": from_address,
        "to_name": to_name,
        "to_address": to_address,
        "pupil_id": pupil_id,
        "staff_id": staff_id,
        "tags": f"template:{name}",
    }
    msg = _messages.create_message(payload)
    logger.info("Sent template '%s' as message %s to %s (pupil=%s)",
                name, msg.message_id, to_address, pupil_id)
    return msg
