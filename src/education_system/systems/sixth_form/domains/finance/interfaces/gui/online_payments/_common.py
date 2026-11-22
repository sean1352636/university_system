"""Small Tk helpers shared by the online-payment screens."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
import webbrowser
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable

logger = logging.getLogger(__name__)


def warn_errors(parent: tk.Misc, fn: Callable[[], Any], *,
                title: str = "Online payments") -> Any:
    """Run *fn*; user errors (ValueError) as a warning, permission
    problems and provider failures as an error, anything else logged."""
    try:
        return fn()
    except ValueError as e:
        messagebox.showwarning(title, str(e), parent=parent)
    except PermissionError as e:
        messagebox.showerror(title, str(e), parent=parent)
    except RuntimeError as e:          # ProviderError
        messagebox.showerror(title, str(e), parent=parent)
    except Exception as e:  # noqa: BLE001 - surface, don't crash Tk
        logger.exception("Online payment action failed")
        messagebox.showerror(title, f"Unexpected error: {e}", parent=parent)
    return None


def run_in_background(win: tk.Misc, fn: Callable[[], Any],
                      done: Callable[[Any], None], *,
                      busy: Callable[[bool], None] | None = None,
                      title: str = "Online payments") -> None:
    """Run *fn* (which may call the card provider over the network) off
    the Tk thread, then call ``done(result)`` back on it. Errors are
    shown like :func:`warn_errors`."""
    q: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            q.put(("ok", fn()))
        except BaseException as e:  # noqa: BLE001 - handed to the Tk thread
            q.put(("err", e))

    if busy:
        busy(True)
    threading.Thread(target=work, daemon=True,
                     name="sixthform-online-payment").start()

    def poll() -> None:
        try:
            kind, value = q.get_nowait()
        except queue.Empty:
            try:
                win.after(150, poll)
            except tk.TclError:
                pass
            return
        if busy:
            try:
                busy(False)
            except tk.TclError:
                return
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return
        if kind == "ok":
            done(value)
        else:
            def _raise() -> None:
                raise value
            warn_errors(win, _raise, title=title)

    win.after(150, poll)


def open_link(parent: tk.Misc, url: str) -> None:
    """Open the checkout page and put the link on the clipboard too."""
    try:
        parent.clipboard_clear()
        parent.clipboard_append(url)
    except tk.TclError:
        pass
    try:
        opened = webbrowser.open(url, new=2)
    except webbrowser.Error:
        opened = False
    if not opened:
        messagebox.showinfo(
            "Payment page",
            "Your browser could not be opened automatically. The payment "
            "link has been copied — paste it into a web browser:\n\n" + url,
            parent=parent)
