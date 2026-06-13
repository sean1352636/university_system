"""Idle-timeout watcher for the Sixth Form GUI.

Mirrors the university system's session-timeout behaviour: if the
signed-in user does nothing for ``timeout_minutes`` the GUI logs them
out and returns to the universal login screen.

The university implementation works by stamping a ``last_activity``
timestamp on every operation that flows through the auth manager and
then comparing it to ``session_timeout`` whenever a permission check
runs. The sixth-form GUI is a Tk app, so instead we:

* listen for user-interaction events on the root window (keypress,
  mouse click, mouse motion, scroll-wheel) and stamp ``last_activity``
  on each one;
* poll once a minute via ``root.after(...)`` to compare the idle
  delta to the configured threshold;
* when the threshold is exceeded, call back into the GUI's logout
  routine so the same teardown path used by the manual Logout button
  is followed.

Timeout is configurable via the ``EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES``
environment variable (default: 30, matching the university default).
Setting it to ``0`` disables the watcher.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import tkinter as tk
from tkinter import messagebox
from typing import Callable

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MINUTES: int = 30
DEFAULT_WARNING_LEAD_SECONDS: int = 60
_POLL_INTERVAL_MS: int = 30_000  # check twice a minute


def _read_env_timeout() -> int:
    """Return the configured timeout in minutes, falling back to default."""
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
    if v < 0:
        return DEFAULT_TIMEOUT_MINUTES
    return v


class IdleTimeoutWatcher:
    """Watches user-interaction events on a Tk root and fires a
    callback when the user has been idle for too long.

    Parameters
    ----------
    root:
        The Tk root or Toplevel whose events drive activity tracking.
    on_timeout:
        Called (in the Tk main thread) when the idle threshold is
        crossed. Expected to perform a logout — the watcher stops
        polling itself once this fires.
    timeout_minutes:
        Idle threshold. ``0`` disables the watcher entirely.
    warning_lead_seconds:
        How long before the hard cut-off to show the warning
        dialogue. ``0`` to disable the warning step.
    """

    _EVENTS: tuple[str, ...] = (
        "<Key>", "<Button>", "<ButtonRelease>", "<Motion>",
        "<MouseWheel>", "<KeyRelease>",
    )

    def __init__(
        self,
        root: tk.Misc,
        *,
        on_timeout: Callable[[], None],
        timeout_minutes: int | None = None,
        warning_lead_seconds: int | None = None,
    ) -> None:
        self.root = root
        self.on_timeout = on_timeout
        self.timeout_minutes = (
            _read_env_timeout() if timeout_minutes is None
            else int(timeout_minutes))
        self.warning_lead_seconds = (
            DEFAULT_WARNING_LEAD_SECONDS if warning_lead_seconds is None
            else int(warning_lead_seconds))

        self._last_activity: _dt.datetime = _dt.datetime.now()
        self._scheduled_after: str | None = None
        self._warning_shown: bool = False
        self._stopped: bool = False
        self._fired: bool = False

    # ── Public API ──────────────────────────────────────────────────

    def start(self) -> None:
        """Begin tracking activity and scheduling timeout checks."""
        if self.timeout_minutes <= 0:
            logger.info(
                "Idle timeout disabled (timeout_minutes=%d)",
                self.timeout_minutes)
            return
        for ev in self._EVENTS:
            try:
                self.root.bind_all(ev, self._on_activity, add="+")
            except tk.TclError:
                logger.debug("Could not bind %s for idle tracking", ev)
        self._schedule_next_check()
        logger.info(
            "Idle timeout watcher started: %d-minute threshold "
            "(warning %d seconds before)",
            self.timeout_minutes, self.warning_lead_seconds)

    def stop(self) -> None:
        """Stop polling. Safe to call multiple times."""
        self._stopped = True
        if self._scheduled_after is not None:
            try:
                self.root.after_cancel(self._scheduled_after)
            except tk.TclError:
                pass
            self._scheduled_after = None

    def reset(self) -> None:
        """Manually mark the user as active right now."""
        self._last_activity = _dt.datetime.now()
        self._warning_shown = False

    def idle_seconds(self) -> float:
        return (_dt.datetime.now() - self._last_activity).total_seconds()

    # ── Internals ───────────────────────────────────────────────────

    def _on_activity(self, _event=None) -> None:
        # Don't reset after we've already fired — the warning dialog
        # itself can synthesise events as the user closes it.
        if self._fired:
            return
        self._last_activity = _dt.datetime.now()
        # Closing the warning dialog counts as activity, so reset the
        # flag so the dialog can show again next cycle.
        self._warning_shown = False

    def _schedule_next_check(self) -> None:
        if self._stopped:
            return
        try:
            self._scheduled_after = self.root.after(
                _POLL_INTERVAL_MS, self._tick)
        except tk.TclError:
            # Root has been destroyed underneath us.
            self._stopped = True

    def _tick(self) -> None:
        self._scheduled_after = None
        if self._stopped:
            return
        idle = self.idle_seconds()
        threshold = self.timeout_minutes * 60
        remaining = threshold - idle

        if remaining <= 0:
            self._fire_timeout()
            return

        if (self.warning_lead_seconds > 0
                and remaining <= self.warning_lead_seconds
                and not self._warning_shown):
            self._show_warning(int(remaining))

        self._schedule_next_check()

    def _show_warning(self, seconds_left: int) -> None:
        self._warning_shown = True
        # Non-blocking-feeling warning. If the user dismisses it, the
        # close event itself counts as activity (we bind <Button>),
        # which extends the session by another full timeout window.
        try:
            messagebox.showwarning(
                "Session inactive",
                f"You've been inactive for a while.\n\n"
                f"You will be signed out in about "
                f"{max(seconds_left, 1)} seconds unless you interact "
                f"with the application.",
                parent=self.root,
            )
        except tk.TclError:
            pass

    def _fire_timeout(self) -> None:
        if self._fired:
            return
        self._fired = True
        self._stopped = True
        logger.info(
            "Session timed out after %d minute(s) of inactivity",
            self.timeout_minutes)
        try:
            self.on_timeout()
        except Exception:
            logger.exception("Idle-timeout callback raised")
