"""Handing work back from a batch worker thread to the Tk main loop.

Batch operations run on worker threads so the window keeps painting while an
import, export or report is in flight. Tk is single-threaded: a worker must
not configure widgets, open a messagebox or destroy a window itself —
that is undefined behaviour, showing up as stray TclErrors, a garbled
display, or an interpreter that wedges.

Two ways back onto the main loop:

* ``post()`` for fire-and-forget widget work.
* ``ask_yes_no()`` when the worker needs an answer before it can continue.

For end-of-operation success/failure dialogs prefer the GUI's own
``message_queue`` (drained by ``main_gui.process_queue``), which also resets
the progress bar.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox


def on_main_thread() -> bool:
    """True when the caller is the thread running the Tk main loop."""
    return threading.current_thread() is threading.main_thread()


def post(widget, callback) -> bool:
    """Schedule *callback* on the Tk main loop. Safe to call from any thread.

    Returns True if it was scheduled, False if the widget is already gone —
    in which case there is nothing left to update and the call is dropped.

    Both failure modes are caught: a destroyed widget raises TclError, while
    a worker still running after the main loop has exited gets
    RuntimeError("main thread is not in main loop"). Neither should take the
    worker down.
    """
    try:
        if widget.winfo_exists():
            widget.after(0, callback)
            return True
    except (tk.TclError, RuntimeError):
        pass
    return False


def call_and_wait(widget, func, default=None):
    """Run *func* on the main loop and block the caller until it returns.

    For the cases a worker cannot simply fire and forget: a modal question, or
    a dialog whose choice decides what the worker does next. Running such a
    dialog on the worker itself drives Tk from the wrong thread — and
    ``wait_window()`` there spins a nested event loop on that thread, which is
    worse.

    *default* is returned without running anything if the window has already
    closed. The wait is unbounded because a human is answering; these workers
    are daemon threads, so a shutdown mid-question does not hold up exit.
    """
    if on_main_thread():
        # Posting and then waiting here would block the very loop that has to
        # run the callback — just call it.
        return func()

    box = {"value": default}
    done = threading.Event()

    def run():
        try:
            box["value"] = func()
        finally:
            done.set()

    if not post(widget, run):
        return default

    done.wait()
    return box["value"]


def ask_yes_no(widget, title, message, default=False):
    """Ask a yes/no question on the main loop; block the worker for the answer."""
    return call_and_wait(
        widget,
        lambda: messagebox.askyesno(title, message, parent=widget),
        default=default,
    )
