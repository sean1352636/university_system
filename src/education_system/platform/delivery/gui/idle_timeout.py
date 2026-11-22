"""Idle / inactivity timeout helper for tkinter main GUIs.

Use :func:`attach_idle_timeout` to install an auto-logout watchdog on a
``tk.Tk`` root window.  Any keyboard, mouse-motion or mouse-button event
counts as activity and resets the idle timer.  When ``timeout_minutes``
elapse without activity, the supplied ``on_timeout`` callback is invoked
(typically the application's logout method).  School systems should call
:func:`install_idle_logout`, which applies the shared timeout setting and
cancels the watchdog however the window is closed.

Mirrors the spirit of the university system's session expiry but tracks
real user activity rather than relying on a hard session age.
"""

from __future__ import annotations

import logging
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable

from education_system.platform.delivery.idle_settings import idle_timeout_minutes

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MINUTES = 30
CHECK_INTERVAL_MS = 30_000  # how often the watchdog wakes up


def notify_signed_out(root: tk.Misc, title: str, message: str) -> None:
    """Tell the user why they were signed out.

    Normally the logout has already destroyed *root*, so this uses a hidden
    throwaway root of its own, which shows no school data while it waits.
    """
    try:
        alive = bool(root.winfo_exists())
    except tk.TclError:
        alive = False
    if alive:
        messagebox.showwarning(title, message, parent=root)
        return
    holder = tk.Tk()
    try:
        holder.withdraw()
        messagebox.showwarning(title, message, parent=holder)
    finally:
        holder.destroy()


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
        Text of the dialog shown after logout. It must come after: the dialog
        is modal, and shown first it would keep an unattended session signed
        in, with its window on screen, until somebody clicked OK.

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
                on_timeout()
            except Exception:
                # Never let a logout-handler error escape into the tk loop
                logger.exception("Idle-timeout handler raised an exception")
            try:
                notify_signed_out(root, title, message)
            except tk.TclError:
                logger.debug("Could not show the signed-out notice", exc_info=True)
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


def install_idle_logout(root: tk.Tk, logout: Callable[[], None]) -> Callable[[], None]:
    """Run *logout* after ``EDU_IDLE_TIMEOUT_MINUTES`` of inactivity.

    Pass the window's manual Logout method, so an idle logout tears down the
    same way. Returns the cancel function; it also runs on ``<Destroy>``, so
    every path that closes the window cancels the pending ``after`` without each
    having to remember. Otherwise Tk would later report ``invalid command name``.
    With a setting of 0 nothing is installed. A failure here is logged rather
    than stopping the window opening.
    """
    minutes = idle_timeout_minutes()
    if minutes <= 0:
        logger.info("Idle logout disabled by %s=0", "EDU_IDLE_TIMEOUT_MINUTES")
        return lambda: None
    try:
        cancel = attach_idle_timeout(root, logout, minutes)

        def _cancel_on_destroy(event=None) -> None:
            # <Destroy> on a toplevel also fires for each of its children.
            if event is None or event.widget is root:
                cancel()

        root.bind("<Destroy>", _cancel_on_destroy, add="+")
    except (tk.TclError, RuntimeError):
        logger.exception("Could not start the idle-logout watchdog")
        return lambda: None
    return cancel
