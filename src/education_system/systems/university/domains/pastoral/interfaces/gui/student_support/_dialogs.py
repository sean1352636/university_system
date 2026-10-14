"""``messagebox`` for the Student Support portal, parented to the active window.

The portal opens plenty of its own ``Toplevel`` windows — ticket detail, the
create/edit forms, the export and report dialogs, the admin editors — and every
message box inside them was raised without ``parent=``. Tk then parents to the
application root, so the dialog was stacked against the **main GUI** and
appeared behind the window that raised it. Since the dialogs are modal, that
window then looks frozen for no visible reason.

Call sites use ``from ._dialogs import messagebox`` so the existing
``messagebox.showerror(...)`` calls read unchanged; the wrapper fills in
``parent`` when the caller did not. An explicit ``parent=`` is still honoured.
``make_toplevel`` does the same one level up, for the portal's own windows.

The mechanism lives in ``platform.delivery.gui.parented_dialogs`` — Grade
Tracking hit the same bug first and proved the approach.
"""

from education_system.platform.delivery.gui.parented_dialogs import (  # noqa: F401
    active_window,
    make_toplevel,
    messagebox,
)

__all__ = ["messagebox", "active_window", "make_toplevel"]
