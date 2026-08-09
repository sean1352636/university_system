"""Shared email template rendering for all Education System subsystems.

Templates are JSON files in ``platform/assets/templates/email/``, one per
message, alongside the ones the auth and security-training flows already
kept there::

    {
      "subject": "Welcome to $system_name",
      "body": "Hello $user_name, ...",
      "html_body": "<html>..."       # optional
    }

They use ``string.Template`` syntax (``$variable`` / ``${variable}``) and
are rendered with ``safe_substitute``, so an unknown placeholder is left
in place rather than raising — a missing field shows up in the message
instead of breaking the send.

Why files rather than a Python dict: an email template is content, not
code. Keeping it in a ``.py`` meant every wording fix was a code change,
the HTML was unreadable as a wall of concatenated string literals, and
half the platform's templates lived here while the other half were
already JSON on disk. One location, one format.

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

import json
import logging
from pathlib import Path
from string import Template
from typing import Dict, List, Optional, Tuple

from education_system.paths import PLATFORM_EMAIL_TEMPLATES_DIR

logger = logging.getLogger(__name__)

TEMPLATES_DIR: Path = PLATFORM_EMAIL_TEMPLATES_DIR

# Parsed templates, keyed by name. Populated on first use rather than at
# import: nothing should pay for disk reads just by importing the email
# package, and most processes never render a templated email at all.
_cache: Dict[str, Dict[str, str]] = {}

# Templates registered at runtime. Checked before the files on disk, so a
# caller can override a shipped template without editing the package.
_custom_templates: Dict[str, Dict[str, str]] = {}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_from_disk(name: str) -> Optional[Dict[str, str]]:
    """Read and parse one template file, or return None if unusable.

    A missing or malformed file is logged and treated as absent rather
    than raised, so one bad template cannot take down every send. The
    caller still gets a ``KeyError`` from :func:`get_template`, which is
    the same failure an unknown name has always produced.
    """
    path = TEMPLATES_DIR / f"{name}.json"
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Email template %s could not be read (%s)", path, exc)
        return None
    if not isinstance(loaded, dict) or "subject" not in loaded:
        logger.error(
            "Email template %s is not a template object — expected an "
            "object with at least a 'subject' key", path)
        return None
    return {
        "subject": str(loaded.get("subject", "")),
        "body": str(loaded.get("body", "")),
        "html_body": str(loaded.get("html_body", "") or ""),
    }


def reload_templates() -> None:
    """Drop the cache so edited template files are picked up.

    Templates ship with the package and rarely change at runtime, so they
    are cached indefinitely. This exists for tests and for an admin
    screen that edits a template file in place.
    """
    _cache.clear()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_template(
    template_name: str, **context
) -> Tuple[str, str, Optional[str]]:
    """Render a named email template with the given context variables.

    Args:
        template_name: Name of a template file (without ``.json``) or of a
            template registered at runtime.
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

    # Plain-text subject and body take the raw context.
    subject = Template(tpl["subject"]).safe_substitute(context)
    body = Template(tpl["body"]).safe_substitute(context)

    html_body = None
    if tpl.get("html_body"):
        # HTML output must escape context values, or a name/comment containing
        # markup (e.g. "<img src=x onerror=...>") is injected verbatim into the
        # email. string.Template has no autoescaping, so escape here. Values
        # explicitly marked safe HTML (URLs a template builds itself) can be
        # passed via a "<key>_html" convention which is left unescaped.
        import html as _html

        safe_context = {
            k: (v if k.endswith("_html") else _html.escape(str(v), quote=True))
            for k, v in context.items()
        }
        html_body = Template(tpl["html_body"]).safe_substitute(safe_context)

    return subject, body, html_body


def get_template(name: str) -> Dict[str, str]:
    """Return the raw template dict for *name*.

    Checks templates registered at runtime first, then the files on disk.

    Raises:
        KeyError: If the template is not found.
    """
    if name in _custom_templates:
        return _custom_templates[name]
    if name in _cache:
        return _cache[name]
    loaded = _load_from_disk(name)
    if loaded is not None:
        _cache[name] = loaded
        return loaded
    raise KeyError(f"Email template not found: {name}")


def register_template(
    name: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
) -> None:
    """Register (or overwrite) a custom email template at runtime.

    This does **not** write a file; it adds to a separate in-memory
    registry that ``get_template`` checks first, so a caller can override
    a shipped template for the life of the process.
    """
    _custom_templates[name] = {
        "subject": subject,
        "body": body,
        "html_body": html_body or "",
    }
    logger.debug("Registered custom email template: %s", name)


def list_templates() -> List[str]:
    """Return a sorted list of every available template name."""
    names = set(_custom_templates)
    if TEMPLATES_DIR.is_dir():
        names |= {path.stem for path in TEMPLATES_DIR.glob("*.json")}
    return sorted(names)


def template_exists(name: str) -> bool:
    """Return True if a template with *name* exists."""
    if name in _custom_templates or name in _cache:
        return True
    return (TEMPLATES_DIR / f"{name}.json").is_file()


def builtin_templates() -> Dict[str, Dict[str, str]]:
    """Every template shipped on disk, parsed. Reads the directory."""
    out: Dict[str, Dict[str, str]] = {}
    if not TEMPLATES_DIR.is_dir():
        return out
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        loaded = _load_from_disk(path.stem)
        if loaded is not None:
            out[path.stem] = loaded
    return out


def __getattr__(name: str):
    """Keep ``BUILTIN_TEMPLATES`` working, without reading disk on import.

    It used to be a module-level dict holding the template content. The
    content now lives in files, but the name is part of this module's
    published surface, so it resolves lazily to the same shape — see
    :func:`builtin_templates`.
    """
    if name == "BUILTIN_TEMPLATES":
        return builtin_templates()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "TEMPLATES_DIR",
    "render_template",
    "get_template",
    "register_template",
    "list_templates",
    "template_exists",
    "builtin_templates",
    "reload_templates",
]
