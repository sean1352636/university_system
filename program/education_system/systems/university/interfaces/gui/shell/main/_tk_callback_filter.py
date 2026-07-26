"""Quiet the upstream Tk destroy-race noise.

When a Toplevel (or its inner Notebook tabs) is destroyed, Tk
destroys its child widgets in dependency order — but any deferred
callback already in the event queue still gets to fire. Common
patterns:

* A ``Treeview`` with ``yscrollcommand=scrollbar.set`` flushes one
  more update during destroy. The scrollbar has already been
  destroyed, so ``scrollbar.set`` raises
  ``_tkinter.TclError: invalid command name ".!toplevel.!…!scrollbar"``.
* A periodic ``after(N, _tick)`` callback fires once after the
  widget that owns the timer is gone, surfacing as
  ``invalid command name "1234567_tick"``.

These come through **two** different paths and need two separate
filters:

1. **Python callback path** — Tk runs the registered Python callable
   for an event, the callable raises, and Tk routes it through
   ``Tk.report_callback_exception``. This is what
   ``install_destroy_race_filter`` overrides.
2. **Tcl background error (``bgerror``) path** — the failure happens
   inside an ``after`` script or a Tcl-level handler that has no
   Python frame on the stack, so it bypasses
   ``report_callback_exception`` entirely. Tcl's default ``bgerror``
   proc dumps the multi-line message to stderr in a format like::

       invalid command name "546947040448_tick"
           while executing
       "546947040448_tick"
           ("after" script)

   ``install_bgerror_filter`` registers a replacement ``bgerror``
   command that swallows the destroy-race patterns and lets
   everything else through.

Wire both from every creator of a ``tk.Tk()``:

    from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import (
        install_destroy_race_filter,
    )
    self.root = tk.Tk()
    install_destroy_race_filter(self.root)
"""
from __future__ import annotations

import logging
import sys
import tkinter as tk
import traceback

logger = logging.getLogger(__name__)


def _is_destroy_race_error(exc_val) -> bool:
    """Return True if *exc_val* matches the destroy-race patterns
    we want to swallow. Conservative — only the two known shapes."""
    if not isinstance(exc_val, tk.TclError):
        return False
    msg = str(exc_val)
    if "invalid command name" not in msg:
        return False
    # Two known shapes:
    #   .!toplevel.!notebook.!frame.!scrollbar  (widget path)
    #   1234567_tick                            (after-timer handle)
    if msg.endswith('"') or msg.endswith("'"):
        # Strip quotes to inspect the tail.
        tail = msg.rstrip('"').rstrip("'")
        if tail.endswith("_tick"):
            return True
        # Widget paths end with a Tcl element name, never plain alphanumeric.
        # The dotted-path pattern is distinctive enough on its own.
        if '"."' in msg or '".!' in msg:
            return True
    return False


def install_destroy_race_filter(root) -> None:
    """Attach the destroy-race filters on *root*.

    Installs **both** the Python-callback filter
    (``report_callback_exception``) and the Tcl ``bgerror`` filter so
    the two distinct paths the destroy-race noise arrives through are
    both quieted. Genuine exceptions still log to stderr in the same
    format Tk's default handler uses, so real bugs aren't silenced."""
    _install_python_callback_filter(root)
    _install_bgerror_filter(root)


def _install_python_callback_filter(root) -> None:
    """Override ``Tk.report_callback_exception`` to swallow destroy-
    race ``TclError``s that surface through Python callback frames."""
    def _handler(exc_type, exc_val, exc_tb):
        if _is_destroy_race_error(exc_val):
            logger.debug("destroy-race TclError swallowed: %s", exc_val)
            return
        sys.stderr.write("Exception in Tkinter callback\n")
        traceback.print_exception(exc_type, exc_val, exc_tb)
    try:
        root.report_callback_exception = _handler
    except Exception:
        logger.debug("could not install Python callback filter", exc_info=True)


def _install_bgerror_filter(root) -> None:
    """Replace Tcl's default ``bgerror`` proc with one that drops the
    destroy-race messages and forwards anything else to stderr.

    ``bgerror`` is invoked by Tcl when a background error happens
    inside an ``after`` script or other Tcl-level handler that has no
    Python frame on the stack. Without this override, the multi-line
    Tcl error message goes straight to stderr and bypasses
    ``report_callback_exception`` entirely — which is what the user
    sees in patterns like::

        invalid command name "546947040448_tick"
            while executing
        "546947040448_tick"
            ("after" script)
    """
    def _bgerror(msg):
        # ``msg`` is the first line of the Tcl error (the human
        # message). The "while executing" / "(after script)" trailer
        # is in the ``errorInfo`` global on the Tcl side; Python
        # doesn't see it here, but the head line is enough to
        # classify the destroy races we want to drop.
        try:
            text = str(msg) if msg is not None else ""
        except Exception:
            text = ""
        if _matches_bgerror_destroy_race(text):
            logger.debug("destroy-race bgerror swallowed: %s", text)
            return
        # Pass-through: dump the head line to stderr in a format
        # close to what Tcl's default bgerror produces. We can't
        # easily fetch errorInfo back through Tk's Python binding
        # without risking another exception in the handler, so the
        # detailed "while executing" trailer is intentionally
        # dropped — the head line is enough to triage real bugs.
        sys.stderr.write(f"Tk background error: {text}\n")
    try:
        # Re-create the command — replaces any existing bgerror.
        root.tk.createcommand("bgerror", _bgerror)
    except Exception:
        logger.debug("could not install Tcl bgerror filter", exc_info=True)


def _matches_bgerror_destroy_race(text: str) -> bool:
    """Same semantic as ``_is_destroy_race_error`` but operating on
    the raw Tcl error message string (since ``bgerror`` doesn't get
    a ``TclError`` instance — Tcl's exception system isn't routed
    through Python's)."""
    if "invalid command name" not in text:
        return False
    # ``invalid command name "<id>_tick"`` — after-timer race
    if '_tick"' in text or text.rstrip().endswith('_tick'):
        return True
    # ``invalid command name ".!toplevel.!…!scrollbar"`` — widget
    # destroy race; the dotted-path prefix is distinctive.
    if '".' in text or '".!' in text:
        return True
    return False


def install_clean_close(window) -> None:
    """Make a Toplevel close visually instant: ``withdraw`` first,
    then ``destroy``.

    Without this, Tk's default close path destroys children one at a
    time on the user-visible window — the user *watches* the
    Toplevel dismantle section by section before it disappears.
    Withdraw yanks the window off-screen immediately,
    ``update_idletasks`` flushes that to the display, then
    ``destroy`` does the slow teardown in private.

    Hooks ``WM_DELETE_WINDOW`` (the protocol the window manager fires
    when the user clicks the close button). Idempotent — safe to
    call repeatedly on the same window. Silently no-ops on widgets
    that have no ``protocol`` method (Frames, LabelFrames, etc.).

    Wire after creating any ``tk.Toplevel`` you want to close
    cleanly::

        win = tk.Toplevel(self.root)
        install_clean_close(win)
    """
    import tkinter as _tk
    try:
        if not hasattr(window, "protocol"):
            return  # Frame/LabelFrame — not a Toplevel
        def _close():
            try:
                window.withdraw()
                window.update_idletasks()
            except _tk.TclError:
                pass
            try:
                window.destroy()
            except _tk.TclError:
                pass
        window.protocol("WM_DELETE_WINDOW", _close)
    except Exception:
        logger.debug("install_clean_close failed", exc_info=True)


__all__ = [
    "install_destroy_race_filter",
    "install_clean_close",
    "_is_destroy_race_error",
    "_matches_bgerror_destroy_race",
]
