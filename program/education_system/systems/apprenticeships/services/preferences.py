"""Per-user interface preferences.

Three settings, chosen because each one has a single place it can take
effect rather than needing every screen to cooperate:

* **date format** — every cell in both interfaces goes through one
  formatter (``widgets._display`` / ``prompts.cell``), so reformatting
  ISO dates there covers the whole system.
* **rows per page** — every GUI table is a ``widgets.DataTable`` and
  every CLI table is ``prompts.table``, so the row budget has two homes.
* **idle timeout** — the desktop shell owns the only session that can
  sit unattended, and signs it out.

Those formatters are called thousands of times per screen and have no
actor to hand, so the active user's values are cached in a module global
that the CLI and GUI entrypoints set at start-up. :func:`activate` is
the only way in; nothing reads the database per cell.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    preference_repository as repo,
)
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

# key -> (label, default, help)
DATE_FORMAT = "date_format"
ROWS_PER_PAGE = "rows_per_page"
IDLE_TIMEOUT_MINUTES = "idle_timeout_minutes"

# The stored value is the strftime pattern; the label is what the
# settings screen offers, because "%d/%m/%Y" is not a choice anyone
# wants to make out of a dropdown.
DATE_FORMATS: dict[str, str] = {
    "ISO — 2026-03-09": "%Y-%m-%d",
    "UK — 09/03/2026": "%d/%m/%Y",
    "Long — 9 March 2026": "%-d %B %Y",
    "Short — 09 Mar 26": "%d %b %y",
}

ROWS_PER_PAGE_CHOICES: tuple[int, ...] = (10, 15, 20, 30, 50, 100)

# Zero means "never sign me out", which is the right answer on a machine
# that is already locked and the wrong one on a shared workstation — so
# it is offered, not assumed.
IDLE_TIMEOUT_CHOICES: tuple[int, ...] = (0, 5, 10, 15, 30, 60)

DEFAULTS: dict[str, Any] = {
    DATE_FORMAT: "%Y-%m-%d",
    ROWS_PER_PAGE: 20,
    IDLE_TIMEOUT_MINUTES: 30,
}

# Cheap enough to test on every cell, and it only matches a full ISO
# date — a timestamp, a code or a note is left exactly as it was.
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_ACTIVE: dict[str, Any] = dict(DEFAULTS)
_ACTIVE_USER: str = ""


# ═════════════════════════════════════════════════════════════════════
# The active session's preferences
# ═════════════════════════════════════════════════════════════════════

def activate(username: str | None) -> dict[str, Any]:
    """Load *username*'s preferences and make them the active ones.

    Called once by each interface entrypoint. A failure to read them is
    not a reason to refuse a login, so it falls back to the defaults and
    logs — a wrong date format is a nuisance, a blocked sign-in is not.
    """
    global _ACTIVE_USER
    _ACTIVE_USER = (username or "").strip()
    if not _ACTIVE_USER:
        reset_active()
        return dict(_ACTIVE)
    try:
        _ACTIVE.update(_coerce(repo.load(_ACTIVE_USER)))
    except Exception:
        logger.warning("Could not load preferences for %s", _ACTIVE_USER, exc_info=True)
        reset_active()
    return dict(_ACTIVE)


def reset_active() -> None:
    """Forget the loaded preferences and fall back to the defaults."""
    _ACTIVE.clear()
    _ACTIVE.update(DEFAULTS)


def active() -> dict[str, Any]:
    """The preferences in force for this session."""
    return dict(_ACTIVE)


def date_format() -> str:
    return str(_ACTIVE.get(DATE_FORMAT) or DEFAULTS[DATE_FORMAT])


def rows_per_page() -> int:
    return int(_ACTIVE.get(ROWS_PER_PAGE) or DEFAULTS[ROWS_PER_PAGE])


def idle_timeout_minutes() -> int:
    return int(_ACTIVE.get(IDLE_TIMEOUT_MINUTES, DEFAULTS[IDLE_TIMEOUT_MINUTES]))


def format_date(value: Any) -> Any:
    """Render an ISO date in the active format, leaving anything else alone.

    Returned unchanged unless the value is exactly ``YYYY-MM-DD``: the
    formatters that call this hand it every cell in the system, most of
    which are not dates at all.
    """
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        return value
    pattern = date_format()
    if pattern == DEFAULTS[DATE_FORMAT]:
        return value
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    try:
        return parsed.strftime(pattern)
    except ValueError:
        # "%-d" is a glibc extension; on a platform without it, fall back
        # rather than let a preference break every table on the screen.
        return parsed.strftime(pattern.replace("%-d", "%d"))


# ═════════════════════════════════════════════════════════════════════
# Reading and writing one user's preferences
# ═════════════════════════════════════════════════════════════════════

def get(actor: Actor) -> dict[str, Any]:
    """*actor*'s stored preferences, with the defaults filled in.

    No permission check: these are the caller's own settings and nobody
    else's, which is enforced by keying on ``actor.username`` rather than
    by taking a username argument.
    """
    if not actor.username:
        return dict(DEFAULTS)
    values = dict(DEFAULTS)
    values.update(_coerce(repo.load(actor.username)))
    return values


def set_preferences(actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and store a batch of *actor*'s own preferences."""
    if not actor.username:
        raise ValidationError("Preferences are stored against a login, and yours is anonymous")

    values: dict[str, Any] = {}
    if DATE_FORMAT in payload:
        values[DATE_FORMAT] = _validate_date_format(payload[DATE_FORMAT])
    if ROWS_PER_PAGE in payload:
        values[ROWS_PER_PAGE] = _validate_choice(
            payload[ROWS_PER_PAGE], ROWS_PER_PAGE_CHOICES, "Rows per page"
        )
    if IDLE_TIMEOUT_MINUTES in payload:
        values[IDLE_TIMEOUT_MINUTES] = _validate_choice(
            payload[IDLE_TIMEOUT_MINUTES], IDLE_TIMEOUT_CHOICES, "Idle timeout"
        )
    if not values:
        raise ValidationError("Nothing to save")

    repo.save(actor.username, values)
    logger.info("Preferences updated for %s: %s", actor.username, ", ".join(sorted(values)))
    if actor.username == _ACTIVE_USER:
        _ACTIVE.update(values)
    return get(actor)


def reset(actor: Actor) -> dict[str, Any]:
    """Drop *actor*'s stored preferences and go back to the defaults."""
    if not actor.username:
        raise ValidationError("Preferences are stored against a login, and yours is anonymous")
    repo.clear(actor.username)
    logger.info("Preferences reset to defaults for %s", actor.username)
    if actor.username == _ACTIVE_USER:
        reset_active()
    return dict(DEFAULTS)


# ═════════════════════════════════════════════════════════════════════
# Labels and validation
# ═════════════════════════════════════════════════════════════════════

def date_format_label(pattern: str) -> str:
    """The dropdown label for a stored strftime pattern."""
    for label, value in DATE_FORMATS.items():
        if value == pattern:
            return label
    return pattern


def date_format_from_label(label: str) -> str | None:
    return DATE_FORMATS.get((label or "").strip())


def idle_timeout_label(minutes: int) -> str:
    return "Never" if minutes <= 0 else f"{minutes} minutes"


def _validate_date_format(value: Any) -> str:
    """Accept either the dropdown label or the pattern behind it."""
    text = str(value or "").strip()
    resolved = date_format_from_label(text) or text
    if resolved not in DATE_FORMATS.values():
        allowed = ", ".join(DATE_FORMATS)
        raise ValidationError(f"Date format must be one of: {allowed}")
    return resolved


def _validate_choice(value: Any, choices: tuple[int, ...], label: str) -> int:
    try:
        chosen = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be a whole number") from exc
    if chosen not in choices:
        allowed = ", ".join(str(c) for c in choices)
        raise ValidationError(f"{label} must be one of: {allowed}")
    return chosen


def _coerce(stored: dict[str, str]) -> dict[str, Any]:
    """Turn stored strings back into the types the callers expect.

    A stored value that no longer validates — a format dropped from the
    list, say — is discarded rather than raising: the caller is usually
    a login, and one stale row must not lock anybody out.
    """
    values: dict[str, Any] = {}
    for key, raw in stored.items():
        try:
            if key == DATE_FORMAT:
                values[key] = _validate_date_format(raw)
            elif key == ROWS_PER_PAGE:
                values[key] = _validate_choice(raw, ROWS_PER_PAGE_CHOICES, "Rows per page")
            elif key == IDLE_TIMEOUT_MINUTES:
                values[key] = _validate_choice(raw, IDLE_TIMEOUT_CHOICES, "Idle timeout")
        except ValidationError:
            logger.debug("Discarding unusable stored preference %s=%r", key, raw)
    return values
