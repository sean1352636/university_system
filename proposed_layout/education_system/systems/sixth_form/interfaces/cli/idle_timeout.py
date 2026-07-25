"""Idle-timeout helpers for the Sixth Form CLI.

Companion to ``modules.shared.gui.idle_timeout`` — does the same job
(log the user out after a stretch of inactivity) but for the
terminal-based interface, where the natural pattern is "wait on
stdin, but no longer than N minutes".

Public surface
--------------
``SessionTimeoutError``
    Raised by ``timed_input`` when the user goes silent for too long.
    Callers in the main CLI loop catch this and exit back to the
    universal login screen.

``timeout_minutes()``
    Resolves the configured timeout (env var → default 30).

``stamp_activity()``
    Records "the user just did something" — call this whenever a
    domain CLI completes an action so the *next* main-loop prompt
    correctly measures idle time across the whole session, not just
    the most recent prompt.

``timed_input(prompt, *, timeout=None)``
    Drop-in replacement for ``input()`` that raises
    ``SessionTimeoutError`` if no character arrives within
    ``timeout`` seconds.

Configuration: ``EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES`` (default 30,
matching the GUI). ``0`` disables the timeout entirely.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import select
import sys

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MINUTES: int = 30


class SessionTimeoutError(Exception):
    """Raised when the user has been idle past the configured threshold."""


def timeout_minutes() -> int:
    """Return the configured idle timeout in minutes (0 == disabled)."""
    raw = os.environ.get("EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES")
    if raw is None:
        return DEFAULT_TIMEOUT_MINUTES
    try:
        v = int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Ignoring invalid EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES=%r; "
            "using default %d", raw, DEFAULT_TIMEOUT_MINUTES)
        return DEFAULT_TIMEOUT_MINUTES
    return max(v, 0)


# Module-level last-activity timestamp so a long stretch inside a
# domain submenu is still counted against the user's idle budget.
_last_activity: _dt.datetime = _dt.datetime.now()


def stamp_activity() -> None:
    """Mark the user as having interacted with the CLI just now."""
    global _last_activity
    _last_activity = _dt.datetime.now()


def idle_seconds() -> float:
    return (_dt.datetime.now() - _last_activity).total_seconds()


def _can_use_select() -> bool:
    """True when stdin is a real, selectable file (tty or pipe).

    Falls back to plain ``input()`` for unusual stdins (e.g. some
    Windows shells, IDE-embedded terminals) so the CLI still works,
    just without the timeout feature.
    """
    try:
        fileno = sys.stdin.fileno()
    except (AttributeError, OSError, ValueError):
        return False
    # ``select`` on a closed/non-selectable fd raises immediately on
    # call; we only need to know the fd is real.
    return fileno is not None and fileno >= 0


def timed_input(prompt: str = "", *, timeout: float | None = None) -> str:
    """Read a line from stdin or raise ``SessionTimeoutError``.

    ``timeout`` is in *seconds*. When ``None`` (the default) the
    module-level configured value is used (minutes × 60). A timeout
    of ``0`` disables the wait entirely and falls back to plain
    ``input()``.
    """
    if timeout is None:
        timeout = timeout_minutes() * 60.0
    if timeout <= 0 or not _can_use_select():
        line = input(prompt)
        stamp_activity()
        return line

    # Display the prompt now so the user sees it even though we're
    # the ones blocked on stdin (not input()).
    if prompt:
        sys.stdout.write(prompt)
        sys.stdout.flush()

    # Account for time already idle in a domain submenu before this
    # call arrived back at the tracked prompt: clamp remaining
    # budget instead of giving them a fresh full window every time.
    remaining = max(0.0, timeout - idle_seconds())
    if remaining <= 0:
        sys.stdout.write("\n")
        sys.stdout.flush()
        raise SessionTimeoutError(
            f"Session idle for >= {timeout / 60:.0f} minute(s)")

    ready, _, _ = select.select([sys.stdin], [], [], remaining)
    if not ready:
        sys.stdout.write("\n")
        sys.stdout.flush()
        raise SessionTimeoutError(
            f"Session idle for >= {timeout / 60:.0f} minute(s)")
    line = sys.stdin.readline()
    if line == "":
        # EOF on the underlying stream — treat like a normal EOF so
        # callers' existing handling (return "0", quit, …) kicks in.
        raise EOFError
    stamp_activity()
    return line.rstrip("\n")
