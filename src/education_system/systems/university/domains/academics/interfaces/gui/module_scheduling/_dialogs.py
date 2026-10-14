"""``messagebox`` for Module Scheduling, safe against a closed parent.

These dialogs pass ``parent=self.dialog`` explicitly, and several of them
close that dialog as part of finishing. Tk then rejects the message box with
``TclError: bad window path name``, and because the failure happens inside a
``try`` whose ``except`` *also* parents to the dead window, one problem
surfaced as two tracebacks — with the second wrongly reporting that the save
had failed when the record had already been written.

The wrapper in ``platform.delivery.gui.parented_dialogs`` retries without the
parent when the named window has gone, so a stale parent degrades to a
correctly-shown dialog instead of an exception. It also fills in ``parent``
for the call sites that pass none, which keeps a message over the window that
raised it rather than behind it.

The ordering bug is fixed at each site as well — confirm, then close. This is
the safety net, not the fix.
"""

from education_system.platform.delivery.gui.parented_dialogs import (  # noqa: F401
    active_window,
    make_toplevel,
    messagebox,
)

__all__ = ["messagebox", "active_window", "make_toplevel"]
