"""Quiet the upstream Tk destroy-race ``TclError`` noise.

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

Both are upstream Tk quirks — many large Tk apps install an exception
filter to swallow them rather than retro-fitting destroy protocols
on every Treeview / scheduler in the app. This module gives every
Tk root creator a one-call ``install`` that does exactly that, while
still letting genuine exceptions surface to stderr unchanged.

Wire from every creator of a ``tk.Tk()``:

    from education_system.university_system.modules.shared.gui.main._tk_callback_filter import (
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
    """Attach ``report_callback_exception`` on *root* that quietly
    swallows the destroy-race patterns documented at the top of this
    module. Real exceptions are still logged to stderr in the same
    format Tk's default handler uses, so genuine bugs aren't
    silenced."""
    def _handler(exc_type, exc_val, exc_tb):
        if _is_destroy_race_error(exc_val):
            # Log at debug for diagnostic forensics — visible if
            # someone bumps log level, but invisible by default.
            logger.debug("destroy-race TclError swallowed: %s", exc_val)
            return
        # Default behaviour: print to stderr exactly the way Tk does.
        sys.stderr.write("Exception in Tkinter callback\n")
        traceback.print_exception(exc_type, exc_val, exc_tb)

    try:
        root.report_callback_exception = _handler
    except Exception:
        logger.debug("could not install Tk destroy-race filter", exc_info=True)


__all__ = ["install_destroy_race_filter", "_is_destroy_race_error"]
