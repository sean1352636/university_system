"""The one idle-logout setting shared by the school systems.

``EDU_IDLE_TIMEOUT_MINUTES`` applies to the Primary, Secondary, Nursery and
FE College GUIs and CLIs: default 30 minutes, ``0`` turns idle logout off.
A value that is not a whole number, or is negative, falls back to the default
rather than disabling logout by accident.

This module imports neither tkinter nor the CLI helpers, so both sides can
read it.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

ENV_VAR = "EDU_IDLE_TIMEOUT_MINUTES"
DEFAULT_TIMEOUT_MINUTES = 30


def idle_timeout_minutes() -> int:
    """Minutes of inactivity before logout; ``0`` means disabled."""
    raw = os.environ.get(ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_TIMEOUT_MINUTES
    try:
        minutes = int(raw)
    except ValueError:
        logger.warning("Ignoring invalid %s=%r; using %d minutes",
                       ENV_VAR, raw, DEFAULT_TIMEOUT_MINUTES)
        return DEFAULT_TIMEOUT_MINUTES
    if minutes < 0:
        logger.warning("Ignoring negative %s=%r; using %d minutes",
                       ENV_VAR, raw, DEFAULT_TIMEOUT_MINUTES)
        return DEFAULT_TIMEOUT_MINUTES
    return minutes
