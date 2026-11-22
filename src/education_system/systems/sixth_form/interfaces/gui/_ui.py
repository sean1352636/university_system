"""Small shared Tk helpers for the sixth-form views.

Deliberately dependency-free: every view module imports this, so it must
not pull in anything that could make an import cycle.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

__all__ = ["grab_when_viewable", "fit_to_width", "fit_when_shown"]

# Poll interval and attempt budget for grab_when_viewable. 20 x 25ms is
# half a second, comfortably longer than a Toplevel takes to map, while
# still giving up rather than polling a window that will never appear.
_GRAB_RETRY_MS = 25
_GRAB_TRIES = 20


def grab_when_viewable(win: tk.Misc, _tries: int = _GRAB_TRIES) -> None:
    """Take a modal grab on *win* as soon as it is actually viewable.

    ``win.after_idle(win.grab_set)`` looks like it waits long enough, but
    idle callbacks can run before the window manager has mapped the
    window, and ``grab set`` on an unmapped window raises::

        _tkinter.TclError: grab failed: window not viewable

    Tk offers no event for "now viewable", so this re-schedules itself
    until ``winfo_viewable()`` is true, then grabs. A window that is
    destroyed, or never maps within the retry budget, is left alone -
    the dialog stays usable, just not modal, which is a better outcome
    than an unhandled callback exception.
    """
    try:
        if not win.winfo_exists():
            return
        if win.winfo_viewable():
            win.grab_set()
            return
    except tk.TclError:
        # Window went away between the checks and the grab.
        return

    if _tries > 0:
        try:
            win.after(_GRAB_RETRY_MS, grab_when_viewable, win, _tries - 1)
        except tk.TclError:
            return
    else:
        logger.debug(
            "Window never became viewable; left without a modal grab (%r)",
            win)


# ── Fitting a built page into the space it actually has ─────────────

_MIN_COLUMN = 40


def fit_to_width(page: tk.Misc) -> None:
    """Make an already-built page fit the space it was given.

    Tab classes written for a wide window lay a toolbar out as one long
    row of buttons, size table columns in pixels, and pack their action
    bar *after* the table. In a smaller window the right-hand end of the
    toolbar and table is cut off, and the table pushes the action bar off
    the bottom. Call this once the page is on screen; it:

    * moves every frame packed after an expanding table to the bottom,
      so action bars and counts keep their height;
    * wraps any button row wider than its frame onto further rows;
    * shrinks table columns, in proportion, to the table's real width.
    """
    try:
        page.update_idletasks()
    except tk.TclError:
        return
    _walk(page)
    # Columns are fitted last, to the widths the layout pass left them.
    try:
        page.update_idletasks()
    except tk.TclError:
        return
    _walk_trees(page)


def fit_when_shown(page: tk.Misc) -> None:
    """:func:`fit_to_width` once *page* has been given its real size.

    A page built into a window that is not mapped yet still reports a
    width of 1, so fitting it then does nothing.
    """
    try:
        page.update_idletasks()
        if page.winfo_width() > 1:
            fit_to_width(page)
            return
    except tk.TclError:
        return

    def _once(_event=None) -> None:
        if page.winfo_width() > 1:
            page.unbind("<Configure>", bind_id)
            fit_to_width(page)

    bind_id = page.bind("<Configure>", _once, add="+")


# Rows holding one of these are a table or text area with its scrollbar,
# not a row of buttons, and must never be wrapped.
_NO_WRAP = {"Treeview", "Text", "Canvas", "Listbox", "TScrollbar",
            "Scrollbar"}


def _walk(widget: tk.Misc) -> None:
    for child in list(widget.winfo_children()):
        if isinstance(child, tk.Toplevel):
            continue
        _walk(child)
    _scrollbar_first(widget)
    _bottom_after_expander(widget)
    _wrap_row(widget)


def _walk_trees(widget: tk.Misc) -> None:
    for child in widget.winfo_children():
        if isinstance(child, tk.Toplevel):
            continue
        if child.winfo_class() == "Treeview":
            _shrink_columns(child)
        _walk_trees(child)


def _scrollbar_first(widget: tk.Misc) -> None:
    """Pack a side scrollbar ahead of its table so it keeps its width.

    Packed after a table that asks for more width than there is, the
    scrollbar is squeezed to nothing.
    """
    packed = _packed(widget)
    for i, (child, info) in enumerate(packed):
        if child.winfo_class() not in ("TScrollbar", "Scrollbar"):
            continue
        earlier = [c for c, _info in packed[:i]
                   if c.winfo_class() in _NO_WRAP]
        if earlier and info.get("side") in ("right", "bottom"):
            child.pack_configure(before=earlier[0])


def _packed(widget: tk.Misc) -> list[tuple[tk.Misc, dict]]:
    out = []
    for child in widget.pack_slaves():
        try:
            out.append((child, child.pack_info()))
        except tk.TclError:
            pass
    return out


def _bottom_after_expander(widget: tk.Misc) -> None:
    packed = _packed(widget)
    if not packed or any(info.get("side") not in ("top", None)
                         for _c, info in packed):
        return
    for i, (child, info) in enumerate(packed):
        if str(info.get("expand")) in ("1", "true", "True"):
            later = [c for c, _info in packed[i + 1:]]
            for c in reversed(later):
                c.pack_configure(side="bottom", before=child)
            return


def _pad_x(info: dict) -> int:
    pad = info.get("padx", 0)
    if isinstance(pad, (tuple, list)):
        return sum(int(p) for p in pad)
    try:
        return int(pad) * 2
    except (TypeError, ValueError):
        return 0


def _wrap_row(widget: tk.Misc) -> None:
    """Re-lay a left-to-right row of widgets onto several rows if needed."""
    packed = _packed(widget)
    if len(packed) < 2 or any(info.get("side") not in ("left", "right")
                              for _c, info in packed):
        return
    if any(c.winfo_class() in _NO_WRAP for c, _info in packed):
        return
    avail = widget.winfo_width()
    if avail <= 1 or widget.winfo_reqwidth() <= avail:
        return
    # Left-hand items in order, then the right-hand ones (packed right to
    # left, so reversed back into reading order).
    lefts = [(c, i) for c, i in packed if i.get("side") == "left"]
    rights = [(c, i) for c, i in packed if i.get("side") == "right"][::-1]
    items = lefts + rights
    for child, _info in items:
        child.pack_forget()
    # Each row is a frame inside *widget*; the items stay *widget*'s
    # children and are packed into the row with ``in_``. They are raised
    # above the row frame, which was created after them.
    row_frame = None
    used = 0
    for child, info in items:
        need = child.winfo_reqwidth() + _pad_x(info)
        if row_frame is None or (used and used + need > avail):
            row_frame = ttk.Frame(widget)
            row_frame.pack(side="top", fill="x", pady=(0, 2))
            used = 0
        child.pack(in_=row_frame, side="left", padx=info.get("padx", 0),
                   pady=info.get("pady", 0))
        child.lift(row_frame)
        used += need


def _shrink_columns(tree: tk.Misc) -> None:
    try:
        avail = tree.winfo_width()
        columns = list(tree["displaycolumns"])
        if columns in (["#all"], ("#all",)) or columns == ["#all"]:
            columns = list(tree["columns"])
        if "tree" in str(tree["show"]):
            columns = ["#0"] + columns
        widths = {c: int(tree.column(c, "width")) for c in columns}
    except (tk.TclError, ValueError):
        return
    total = sum(widths.values())
    if avail <= 1 or total <= avail - 4:
        return
    scale = (avail - 4) / total
    for c, w in widths.items():
        tree.column(c, width=max(_MIN_COLUMN, int(w * scale)))
