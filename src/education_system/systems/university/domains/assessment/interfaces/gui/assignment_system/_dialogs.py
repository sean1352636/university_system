"""``messagebox`` for the Assignment System, parented to the active window.

The Assignment System opens ~90 of its own ``Toplevel`` windows — Messages,
the grading and rubric editors, extension requests, the file viewer, the
auto-grading and peer-review screens — and almost every message box inside
them was raised without ``parent=``. Tk then parents to the application root,
so the dialog was stacked against the **main GUI** and appeared behind the
assignment window that raised it. Since the dialogs are modal, that window
then looks frozen for no visible reason.

Call sites use ``from ..._dialogs import messagebox`` so the existing
``messagebox.showerror(...)`` calls read unchanged; the wrapper fills in
``parent`` when the caller did not. An explicit ``parent=`` is still honoured,
so the 62 call sites that already pass one keep their exact behaviour.

The mechanism lives in ``platform.delivery.gui.parented_dialogs`` — Grade
Tracking hit the same bug first and proved the approach.
"""

from education_system.platform.delivery.gui.parented_dialogs import (  # noqa: F401
    active_window,
    make_toplevel,
    messagebox,
)

__all__ = ["messagebox", "active_window", "make_toplevel"]
