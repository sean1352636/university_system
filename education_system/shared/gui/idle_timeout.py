"""Idle / inactivity timeout helper for tkinter main GUIs.

Use :func:`attach_idle_timeout` to install an auto-logout watchdog on a
``tk.Tk`` root window.  Any keyboard, mouse-motion or mouse-button event
counts as activity and resets the idle timer.  When ``timeout_minutes``
elapse without activity, the supplied ``on_timeout`` callback is invoked
(typically the application's logout method).

Mirrors the spirit of the university system's session expiry but tracks
real user activity rather than relying on a hard session age.
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable

DEFAULT_TIMEOUT_MINUTES = 30
CHECK_INTERVAL_MS = 30_000  # how often the watchdog wakes up


def attach_idle_timeout(
    root: tk.Tk,
    on_timeout: Callable[[], None],
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
    *,
    title: str = "Session Expired",
    message: str = "You have been logged out due to inactivity.",
) -> Callable[[], None]:
    """Install an idle-timeout watchdog on *root*.

    Parameters
    ----------
    root:
        The application's main ``tk.Tk`` window.
    on_timeout:
        Callable invoked once when the idle timeout fires.  Typically the
        GUI's existing logout method (e.g. ``self._do_logout``).
    timeout_minutes:
        Minutes of inactivity before logout.  Defaults to 30.
    title, message:
        Text shown in the warning dialog before logout fires.

    Returns
    -------
    cancel:
        A zero-arg function that cancels the watchdog (call from
        ``WM_DELETE_WINDOW`` or other shutdown paths).
    """
    state = {"last_activity": time.monotonic(), "after_id": None, "fired": False}
    timeout_seconds = max(1, timeout_minutes) * 60

    def _on_activity(_event=None):
        state["last_activity"] = time.monotonic()

    # bind_all so the events fire regardless of which child widget has focus
    for seq in ("<Motion>", "<KeyPress>", "<ButtonPress>", "<MouseWheel>"):
        root.bind_all(seq, _on_activity, add="+")

    def _tick():
        state["after_id"] = None
        if state["fired"]:
            return
        try:
            if not root.winfo_exists():
                return
        except tk.TclError:
            return

        idle = time.monotonic() - state["last_activity"]
        if idle >= timeout_seconds:
            state["fired"] = True
            try:
                messagebox.showwarning(title, message, parent=root)
            except tk.TclError:
                pass
            try:
                on_timeout()
            except Exception:
                # Never let a logout-handler error escape into the tk loop
                import logging
                logging.getLogger(__name__).exception(
                    "Idle-timeout handler raised an exception"
                )
            return

        # Schedule next check
        try:
            state["after_id"] = root.after(CHECK_INTERVAL_MS, _tick)
        except tk.TclError:
            pass

    state["after_id"] = root.after(CHECK_INTERVAL_MS, _tick)

    def cancel():
        state["fired"] = True  # stop any in-flight tick from doing anything
        aid = state.get("after_id")
        if aid is not None:
            try:
                root.after_cancel(aid)
            except tk.TclError:
                pass
            state["after_id"] = None

    return cancel
