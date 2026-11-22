"""``messagebox`` that parents its dialogs to the window you are looking at.

Tk parents a message dialog to the application's root window unless told
otherwise. Grade Tracking opens plenty of its own ``Toplevel`` windows (the
report viewer, the grade and enrolment dialogs, the batch editors), and those
sit above the root. So a dialog raised *from* one of those windows — pressing
"Email to Admin" in a report window, for instance — was stacked relative to the
root and appeared **underneath** the window that raised it. It looks like
nothing happened, and the window that owns the dialog is unresponsive because
the dialog is modal.

Passing ``parent=`` fixes it, but there are ~400 message dialogs in this package
and only a couple passed it. Rather than annotate each one, this module wraps
``tkinter.messagebox`` and fills in ``parent`` when the caller did not: the
dialog is then stacked above, and centred on, the window it came from.

An explicit ``parent=`` is always honoured, so call sites that already pass one
keep their exact behaviour.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

import tkinter as tk
from tkinter import messagebox as _messagebox

# The dialog functions tkinter.messagebox exposes.
_DIALOGS = (
    "showinfo", "showwarning", "showerror",
    "askquestion", "askokcancel", "askyesno", "askyesnocancel", "askretrycancel",
)


def _usable(widget) -> bool:
    """True if *widget* still exists and can host a dialog."""
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


def active_window():
    """Best guess at the window the user is currently interacting with.

    Preference order: the toplevel holding keyboard focus, then the most
    recently created toplevel that is actually on screen, then the root.
    Returns ``None`` when there is no usable window, in which case the caller
    should let Tk pick (i.e. omit ``parent`` entirely).
    """
    root = getattr(tk, "_default_root", None)
    if root is None or not _usable(root):
        return None

    # 1. Whatever has keyboard focus. focus_get() raises KeyError when focus
    #    sits on a widget belonging to another interpreter, hence the guard.
    try:
        focused = root.focus_get()
    except Exception:
        focused = None
    if focused is not None:
        try:
            top = focused.winfo_toplevel()
            if _usable(top):
                return top
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    # 2. No focus information — fall back to the last mapped Toplevel. Tk lists
    #    children in creation order, so the last viewable one is the most
    #    recently opened, which is the one stacked on top.
    try:
        for child in reversed(root.winfo_children()):
            if isinstance(child, tk.Toplevel) and _usable(child) and child.winfo_viewable():
                return child
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)

    return root


def _wrap(name):
    def dialog(*args, **kwargs):
        # Resolved per call, not captured at import: tests routinely patch
        # tkinter.messagebox.showerror & friends to assert what was shown, and
        # a reference captured at import time would silently bypass the patch.
        original = getattr(_messagebox, name)
        if "parent" not in kwargs:
            parent = active_window()
            if parent is not None:
                kwargs["parent"] = parent
        try:
            return original(*args, **kwargs)
        except tk.TclError:
            # The chosen parent went away between picking it and showing the
            # dialog (a window closing under a background callback). Showing
            # the message unparented beats losing it.
            kwargs.pop("parent", None)
            return original(*args, **kwargs)

    dialog.__name__ = name
    dialog.__qualname__ = name
    dialog.__doc__ = "Parented to the active window by default; see module docstring."
    return dialog


for _name in _DIALOGS:
    globals()[_name] = _wrap(_name)


def make_toplevel(master=None, **kwargs):
    """``tk.Toplevel`` that opens above the window the user is working in.

    Same stacking bug as the message dialogs, one level up: 34 of this
    package's ~53 Toplevels were created as ``tk.Toplevel(self.root)``, so a
    dialog opened *from* a child window was stacked against the main window and
    appeared behind the window that opened it.

    The Tk master is left exactly as the caller passed it — that governs the
    widget hierarchy and destruction, and changing it would alter when these
    windows die. Only the stacking owner is set, via ``transient()``, which is
    what actually keeps a window above another. The owner is resolved *before*
    the new window exists, so the new window cannot pick itself.
    """
    owner = active_window()

    window = tk.Toplevel(**kwargs) if master is None else tk.Toplevel(master, **kwargs)

    try:
        if owner is not None and owner is not window and _usable(owner):
            window.transient(owner)
    except Exception:
        # transient() is a hint to the window manager, never worth failing over.
        logger.debug("Suppressed exception", exc_info=True)
    try:
        window.lift()
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return window


def __getattr__(name):
    # Anything else (constants like YES/NO/OK, showdialog, ...) passes through.
    return getattr(_messagebox, name)


# Call sites use ``from ._dialogs import messagebox`` so that the ~400 existing
# ``messagebox.showerror(...)`` calls read unchanged. This module *is* that
# namespace: attribute lookups hit the wrapped functions above, and anything
# else falls through __getattr__ to the real tkinter.messagebox.
import sys as _sys

messagebox = _sys.modules[__name__]

__all__ = list(_DIALOGS) + ["messagebox", "active_window", "make_toplevel"]
