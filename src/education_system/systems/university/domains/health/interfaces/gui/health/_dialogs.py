"""Dialogs for the health GUIs, parented to the window you are looking at.

The Health Portal, Medical Accommodations, the Dentist and the First Aid
portal all open their own ``Toplevel`` windows (record editors, report and
export windows, the appointment dialogs), and the message boxes, prompts and
file pickers inside them were raised without ``parent=``. Tk then parents
to the application root, so the dialog was stacked against the **main GUI**
and appeared behind the health window that raised it — which, the dialog
being modal, then looked frozen.

Call sites use ``from ..._dialogs import messagebox, simpledialog,
filedialog`` so the existing ``messagebox.showerror(...)`` /
``simpledialog.askstring(...)`` / ``filedialog.asksaveasfilename(...)`` calls
read unchanged; the wrappers fill in ``parent`` when the caller did not. An
explicit ``parent=`` is still honoured.

The mechanism lives in ``platform.delivery.gui.parented_dialogs`` (Grade
Tracking and the Academic Calendar use the same one).
"""

from education_system.platform.delivery.gui.parented_dialogs import (  # noqa: F401
    active_window,
    filedialog,
    make_toplevel,
    messagebox,
    simpledialog,
)

__all__ = ["messagebox", "simpledialog", "filedialog", "active_window", "make_toplevel"]
