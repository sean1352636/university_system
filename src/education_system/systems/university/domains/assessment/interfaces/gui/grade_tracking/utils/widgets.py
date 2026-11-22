"""Widget lifetime helpers for the grade-tracking GUI."""

import tkinter as tk


def widget_alive(widget):
    """Return True when ``widget`` exists and has not been destroyed.

    Navigating between views runs ``LayoutManager._clear_content()``, which
    destroys everything under the content frame. The managers' Python
    references (``student_tree``, ``module_tree``, ...) survive that and keep
    pointing at dead widgets, so a ``hasattr`` check is not enough: a later
    refresh — a Refresh click, or an event-bus broadcast reaching
    ``refresh_all_data`` — would raise ``TclError: invalid command name``.
    """
    if widget is None:
        return False
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False
    except Exception:
        return False


def attr_alive(owner, name):
    """Return True when ``owner.<name>`` is a live, undestroyed widget."""
    return widget_alive(getattr(owner, name, None))
