"""JSON e-mail templates (``resources/email_templates/<name>.json``,
:data:`paths.SECONDARY_EMAIL_TEMPLATES_DIR`).

A template file holds::

    {
      "name": "welcome_pupil",
      "subject": "Welcome, {pupil_first_name}",
      "body": ["line 1", "line 2"],          # a string or a list of lines
      "placeholders": {"pupil_first_name": "what it is", ...},
      "defaults": {"school_name": "..."}     # optional values used when not supplied
    }

Loading checks the file thoroughly and raises :class:`TemplateError` with the
reason - a missing or broken template never silently sends nothing. Every
``{placeholder}`` used must be declared, and rendering fails if a value is
missing, so a half-filled e-mail can't go out.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from education_system.paths import SECONDARY_EMAIL_TEMPLATES_DIR

TEMPLATE_DIR = SECONDARY_EMAIL_TEMPLATES_DIR

_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_]+)\}")


class TemplateError(ValueError):
    pass


@dataclass(frozen=True)
class EmailTemplate:
    name: str
    subject: str
    body: str
    placeholders: dict[str, str]
    defaults: dict[str, str] = field(default_factory=dict)
    description: str = ""

    def render(self, values: dict[str, object]) -> tuple[str, str]:
        """Return ``(subject, body)`` with every placeholder filled in."""
        merged = {**self.defaults, **_school_values(),
                  **{k: "" if v is None else str(v) for k, v in values.items()}}
        missing = sorted({m for m in _PLACEHOLDER_RE.findall(self.subject + self.body)
                          if m not in merged})
        if missing:
            raise TemplateError(f"Template '{self.name}' needs a value for: "
                                + ", ".join(missing))

        def fill(text: str) -> str:
            return _PLACEHOLDER_RE.sub(lambda m: merged[m.group(1)], text)

        subject = " ".join(fill(self.subject).split())  # one line: no header injection
        return subject, fill(self.body)


def _school_values() -> dict[str, str]:
    """The school's details from School Settings (name, address, phone,
    e-mail, headteacher, signature...) - only the ones actually filled in, so
    a template's own default stays when a setting is blank or untouched."""
    try:
        from education_system.systems.secondary.modules.administration.domain import settings as ST
        stored = ST.school_values()
        default_name = ST.get_spec("school_name").default
    except Exception:  # noqa: BLE001 - no settings (yet): the template defaults apply
        return {}
    return {k: str(v) for k, v in stored.items()
            if v and not (k == "school_name" and v == default_name)}


def load_template(name: str, directory: Path | None = None) -> EmailTemplate:
    if not _NAME_RE.match(name or ""):
        raise TemplateError(f"Bad template name '{name}'")
    path = (directory or TEMPLATE_DIR) / f"{name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise TemplateError(f"E-mail template '{name}' not found at {path}") from None
    except (OSError, ValueError) as e:
        raise TemplateError(f"E-mail template '{name}' can't be read: {e}") from e
    if not isinstance(data, dict):
        raise TemplateError(f"E-mail template '{name}' must be a JSON object")
    subject = data.get("subject")
    body = data.get("body")
    if isinstance(body, list) and all(isinstance(line, str) for line in body):
        body = "\n".join(body)
    if not isinstance(subject, str) or not subject.strip():
        raise TemplateError(f"E-mail template '{name}' has no subject")
    if not isinstance(body, str) or not body.strip():
        raise TemplateError(f"E-mail template '{name}' has no body")
    placeholders = data.get("placeholders") or {}
    defaults = data.get("defaults") or {}
    if not isinstance(placeholders, dict) or not isinstance(defaults, dict):
        raise TemplateError(f"E-mail template '{name}': placeholders/defaults must be objects")
    undeclared = sorted({m for m in _PLACEHOLDER_RE.findall(subject + body)
                         if m not in placeholders})
    if undeclared:
        raise TemplateError(f"E-mail template '{name}' uses undeclared placeholder(s): "
                            + ", ".join(undeclared))
    return EmailTemplate(name=name, subject=subject, body=body,
                         placeholders={str(k): str(v) for k, v in placeholders.items()},
                         defaults={str(k): str(v) for k, v in defaults.items()},
                         description=str(data.get("description") or ""))
