"""Small shared Tk helpers for the sixth-form views.

Deliberately dependency-free: every view module imports this, so it must
not pull in anything that could make an import cycle.
"""

from __future__ import annotations

import logging
import tkinter as tk

logger = logging.getLogger(__name__)

__all__ = ["grab_when_viewable"]

# Poll interval and attempt budget for grab_when_viewable. 20 x 25ms is
# half a second, comfortably longer than a Toplevel takes to map, while
# still giving up rather than polling a window that will never appear.
_GRAB_RETRY_MS = 25
_GRAB_TRIES = 20


def grab_when_viewable(win: tk.Misc, _tries: int = _GRAB_TRIES) -> None:
    """Take a modal grab on *win* as soon as it is actually viewable.

    ``win.after_idle(win.grab_set)`` looks like it waits long enough, but
    idle callbacks can run before the window manager has mapped the
    window, and ``grab set`` on an unmapped window raises::

        _tkinter.TclError: grab failed: window not viewable

    Tk offers no event for "now viewable", so this re-schedules itself
    until ``winfo_viewable()`` is true, then grabs. A window that is
    destroyed, or never maps within the retry budget, is left alone -
    the dialog stays usable, just not modal, which is a better outcome
    than an unhandled callback exception.
    """
    try:
        if not win.winfo_exists():
            return
        if win.winfo_viewable():
            win.grab_set()
            return
    except tk.TclError:
        # Window went away between the checks and the grab.
        return

    if _tries > 0:
        try:
            win.after(_GRAB_RETRY_MS, grab_when_viewable, win, _tries - 1)
        except tk.TclError:
            return
    else:
        logger.debug(
            "Window never became viewable; left without a modal grab (%r)",
            win)
