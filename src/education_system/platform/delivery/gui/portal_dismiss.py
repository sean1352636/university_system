"""Return-to-homepage / close-window handling for embeddable portals.

A portal that supports ``host=`` embedding can be running in one of three
shapes, and "close this and go back" means something different in each:

* **a workspace notebook tab** — the main GUI hosted it via
  ``open_in_workspace``. Closing means forgetting the tab, which drops the
  user back on the dashboard. Until now the only way to do that was a
  *right-click* on the tab strip, which nobody discovers.
* **a Toplevel** — e.g. Safeguarding, or the ``open_in_workspace`` fallback
  when there is no dashboard yet. Closing means destroying that window,
  leaving the main window behind it.
* **its own root** — launched standalone from ``main()``. Closing means
  quitting, so it is confirmed first.

This lives in ``platform.delivery.gui`` rather than the university shell on
purpose: a domain must never import the shell, and every system's portals
need the same behaviour. It works by walking up the widget tree, so it
needs no reference to the hosting GUI object.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

__all__ = ["dismiss_target", "dismiss", "add_dismiss_button", "forget_tab"]


def _enclosing_notebook_tab(widget):
    """Return ``(notebook, tab_frame)`` if ``widget`` sits inside a notebook tab.

    Walks up from ``widget`` looking for a parent that is a direct tab of a
    ``ttk.Notebook``. Returns ``(None, None)`` when it is not in one.
    """
    node = widget
    while node is not None:
        parent = getattr(node, "master", None)
        if isinstance(parent, ttk.Notebook):
            try:
                if str(node) in parent.tabs():
                    return parent, node
            except tk.TclError:
                pass
        node = parent
    return None, None


def dismiss_target(host):
    """Classify how ``host`` is being displayed.

    Returns one of ``("tab", notebook, frame)``, ``("window", toplevel, None)``
    or ``("root", root, None)``. Returns ``("none", None, None)`` if the
    widget is already gone.
    """
    try:
        if not host.winfo_exists():
            return ("none", None, None)
    except (tk.TclError, AttributeError):
        return ("none", None, None)

    notebook, frame = _enclosing_notebook_tab(host)
    if notebook is not None:
        return ("tab", notebook, frame)

    try:
        top = host.winfo_toplevel()
    except tk.TclError:
        return ("none", None, None)

    if isinstance(top, tk.Tk):
        return ("root", top, None)
    return ("window", top, None)


def dismiss(host, *, on_before=None, confirm_quit=True):
    """Close ``host``'s portal and hand the user back where they came from.

    ``on_before`` runs first (close DB handles, cancel ``after`` timers).
    Its failure is logged, never raised — a cleanup bug must not leave the
    user trapped in a window with a dead close button.
    """
    if on_before is not None:
        try:
            on_before()
        except Exception:
            logger.warning("portal dismiss cleanup failed", exc_info=True)

    kind, widget, frame = dismiss_target(host)

    if kind == "tab":
        try:
            widget.forget(frame)
        except tk.TclError:
            logger.debug("notebook tab already gone", exc_info=True)
        # Destroy as well as forget. ``open_in_workspace`` caches the frame
        # in ``workspace_tabs[title]`` and re-raises it when the same title
        # is launched again; ``forget`` alone leaves ``winfo_exists()`` True,
        # so that cached entry would look live and block a rebuild. Once the
        # frame is destroyed the launcher's own staleness check fails and it
        # builds a fresh tab.
        try:
            frame.destroy()
        except tk.TclError:
            logger.debug("tab frame already destroyed", exc_info=True)
        return kind

    if kind == "window":
        try:
            widget.destroy()
        except tk.TclError:
            logger.debug("toplevel already destroyed", exc_info=True)
        return kind

    if kind == "root":
        if confirm_quit:
            from tkinter import messagebox

            if not messagebox.askyesno(
                "Close",
                "Close the portal? It is running on its own, so this quits "
                "the application.",
                parent=widget,
            ):
                return "cancelled"
        try:
            widget.destroy()
        except tk.TclError:
            logger.debug("root already destroyed", exc_info=True)
        return kind

    return kind


def add_dismiss_button(
    parent,
    host,
    *,
    on_before=None,
    side="right",
    padx=4,
    pady=10,
    style="flat",
    bg="#1f3a5f",
    fg="white",
    activebackground="#274875",
):
    """Pack a close button whose label matches what it will actually do.

    Returns the button. The label is decided at build time from how the
    portal is hosted, so an embedded tab never says "Close window".
    """
    kind, _widget, _frame = dismiss_target(host)
    text = {
        "tab": "◀  Back to dashboard",
        "window": "✕  Close",
        "root": "✕  Close",
    }.get(kind, "✕  Close")

    if style == "ttk":
        button = ttk.Button(
            parent, text=text, command=lambda: dismiss(host, on_before=on_before)
        )
        button.pack(side=side, padx=padx, pady=pady)
        return button

    button = tk.Button(
        parent,
        text=text,
        bg=bg,
        fg=fg,
        relief="flat",
        font=("Segoe UI", 9, "bold"),
        padx=10,
        pady=4,
        activebackground=activebackground,
        activeforeground=fg,
        command=lambda: dismiss(host, on_before=on_before),
    )
    button.pack(side=side, padx=padx, pady=pady)
    return button


def forget_tab(notebook, tab) -> None:
    """Remove *tab* from *notebook* and destroy the widgets behind it.

    ``Notebook.forget()`` only detaches a tab: its frame, and every widget
    inside it, stay alive as children of the notebook. Screens that rebuild
    their tabs, or that offer a close button, therefore accumulated a whole
    screen's worth of widgets per click for the life of the session — which
    ends as "BadAlloc ... X_CreatePixmap" once the X server runs out of
    pixmaps.

    Accepts either the tab's widget or its Tcl path name. Never raises: a tab
    that has already gone is not an error worth failing a close over.

    Do **not** use this for a pane you intend to re-add — see the members
    sidebar in the chat window, which toggles with ``forget``/``add`` on
    purpose and must keep its widget.
    """
    widget = tab
    try:
        if isinstance(tab, str):
            widget = notebook.nametowidget(tab)
    except (KeyError, tk.TclError):
        widget = None
    try:
        notebook.forget(tab)
    except tk.TclError:
        logger.debug("tab already detached", exc_info=True)
    if widget is not None:
        try:
            widget.destroy()
        except tk.TclError:
            logger.debug("tab widget already destroyed", exc_info=True)
