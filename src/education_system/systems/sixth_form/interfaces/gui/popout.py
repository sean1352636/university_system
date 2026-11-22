"""Open a page or a chart in its own window.

Two ways in:

* :func:`open_page` re-runs a main-window page (a sidebar handler that
  draws into ``gui.content_frame``) inside a new window. The handler runs
  against a :class:`_WindowHost` — the main GUI with its own content
  frame, status line and root — so the page draws there instead of
  replacing what the main window shows. Each window is independent: it
  can be refreshed, kept open, and several can be open at once.
* :func:`add_button` puts an "Open in new window" button on a bar inside
  a tab or panel; ``build(frame)`` draws the chart/report again into the
  new window's frame.
"""

from __future__ import annotations

import logging
import tkinter as tk
import types
from collections.abc import Callable
from tkinter import ttk

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)

logger = logging.getLogger(__name__)

BUTTON_TEXT = "⧉ Open in new window"
_SIZE = "1400x900"
_MIN = (1200, 800)


def _new_window(master: tk.Misc, title: str) -> tuple[tk.Toplevel, ttk.Frame,
                                                       ttk.Frame, tk.StringVar]:
    """A sized window with a top bar, a scrolling body and a status line.
    Returns (window, bar, body, status)."""
    win = make_toplevel(master)
    try:
        # A pop-out is a window in its own right, not a dialog that must
        # sit on top of the main window: drop the stacking owner.
        win.wm_transient("")
    except tk.TclError:
        pass
    win.title(title)
    window_sizing.fit(win, _SIZE, _MIN)

    status = tk.StringVar(value="")
    bar = ttk.Frame(win, padding=(10, 8, 10, 0))
    bar.pack(side="top", fill="x")
    foot = ttk.Frame(win, padding=(10, 2))
    foot.pack(side="bottom", fill="x")
    ttk.Label(foot, textvariable=status, foreground="#555").pack(side="left")

    outer = ttk.Frame(win)
    outer.pack(side="top", fill="both", expand=True)
    canvas = tk.Canvas(outer, highlightthickness=0)
    vs = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    vs.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=vs.set)
    body = ttk.Frame(canvas, padding=10)
    item = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>",
              lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfigure(item, width=e.width))
    return win, bar, body, status


class _WindowHost:
    """Stands in for the main GUI while a page is drawn in a pop-out.

    ``content_frame``, ``status_var`` and ``root`` are the pop-out's own;
    everything else is the main GUI's. The GUI's own methods are re-bound
    to this host, so a page that calls ``self._clear_content()`` clears
    the pop-out, never the main window.
    """

    def __init__(self, gui, window: tk.Toplevel, body: ttk.Frame,
                 status: tk.StringVar) -> None:
        self.__dict__["_gui"] = gui
        self.__dict__["content_frame"] = body
        self.__dict__["status_var"] = status
        self.__dict__["root"] = window

    def __getattr__(self, name: str):
        gui = self.__dict__["_gui"]
        attr = getattr(type(gui), name, None)
        if isinstance(attr, types.FunctionType):
            return types.MethodType(attr, self)
        return getattr(gui, name)


def open_page(gui, label: str,
              draw: Callable[[object], None]) -> tk.Toplevel:
    """Open a main-window page in a new window: ``draw(host)`` is the
    page's own drawing function, run against a :class:`_WindowHost`."""
    win, bar, body, status = _new_window(gui.root, f"{label} — Sixth Form")
    host = _WindowHost(gui, win, body, status)

    def redraw() -> None:
        for w in body.winfo_children():
            w.destroy()
        try:
            draw(host)
            status.set(f"Showing: {label}")
        except Exception as exc:  # noqa: BLE001 — shown in the window
            logger.exception("%s could not be drawn in a new window", label)
            ttk.Label(body, text=f"{label} could not be shown:\n{exc}",
                      foreground="#a33").pack(anchor="w")

    ttk.Button(bar, text="↻ Refresh", command=redraw).pack(side="left")
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
    redraw()
    return win


def show_page(gui, label: str, draw: Callable[[object], None]) -> None:
    """Draw a page in the main window (``draw(gui)``) and make it the one
    the main window's "Open in new window" button opens. For pages
    reached from buttons inside another page rather than the sidebar."""
    draw(gui)
    remember = getattr(gui, "_set_current_page", None)
    if callable(remember):
        remember((label, draw))


def open_built(parent: tk.Misc, title: str,
               build: Callable[[ttk.Frame], None]) -> tk.Toplevel:
    """Open a new window and draw ``build(frame)`` into it."""
    win, bar, body, status = _new_window(parent.winfo_toplevel(), title)

    def draw() -> None:
        for w in body.winfo_children():
            w.destroy()
        try:
            build(body)
            status.set(f"Showing: {title}")
        except Exception as exc:  # noqa: BLE001 — shown in the window
            logger.exception("%s could not be drawn in a new window", title)
            ttk.Label(body, text=f"{title} could not be shown:\n{exc}",
                      foreground="#a33").pack(anchor="w")

    ttk.Button(bar, text="↻ Refresh", command=draw).pack(side="left")
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
    draw()
    return win


def add_button(bar: tk.Misc, title: str, build: Callable[[ttk.Frame], None],
               *, side: str = "right", **pack) -> ttk.Button:
    """Pack an "Open in new window" button on ``bar`` that opens
    :func:`open_built` with ``build``."""
    def go() -> None:
        try:
            open_built(bar, title, build)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Opening %s in a new window", title)
            messagebox.showerror(title, f"Could not open a new window:\n{exc}",
                                 parent=bar.winfo_toplevel())
    btn = ttk.Button(bar, text=BUTTON_TEXT, command=go)
    btn.pack(side=side, **pack)
    return btn


class FrameBook(ttk.Frame):
    """Stands in for a notebook/sidebar book so a page class that adds
    itself as a tab (``nb.add(frame, text=...)``) can be drawn on its own
    in a new window: the added page simply fills this frame."""

    def add(self, child: tk.Misc, **_options) -> None:
        child.pack(fill="both", expand=True)

    def select(self, *_args, **_kw):
        return ""

    def tab(self, *_args, **_kw):
        return {}


def open_book_page(parent: tk.Misc, title: str,
                   make_page: Callable[[FrameBook], object]) -> tk.Toplevel:
    """Open ``make_page(book)`` — a page that adds itself to a book — in a
    new window."""
    def build(frame: ttk.Frame) -> None:
        book = FrameBook(frame)
        book.pack(fill="both", expand=True)
        make_page(book)
    return open_built(parent, title, build)


def add_page_button(bar: tk.Misc, title: str,
                    make_page: Callable[[FrameBook], object], *,
                    side: str = "right", **pack) -> ttk.Button:
    """"Open in new window" button for a tab page (see
    :func:`open_book_page`)."""
    def build(frame: ttk.Frame) -> None:
        book = FrameBook(frame)
        book.pack(fill="both", expand=True)
        make_page(book)
    return add_button(bar, title, build, side=side, **pack)
