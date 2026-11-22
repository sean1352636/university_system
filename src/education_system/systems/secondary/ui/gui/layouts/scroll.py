"""A form window whose fields scroll while its buttons stay put.

Forms taller than the screen (1366x768 laptops) were cut off at the bottom,
hiding the Save button. :func:`scrolled_form` gives a vertically scrolling
body and a footer pinned to the bottom of the window for the error text and
buttons, so they are always visible.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def scrolled_form(win: tk.Toplevel, padding: int = 12) -> tuple[ttk.Frame, ttk.Frame]:
    """Return ``(body, footer)`` packed into *win*. Put fields in *body* (it
    scrolls) and buttons/messages in *footer* (always visible)."""
    footer = ttk.Frame(win, padding=(padding, 6, padding, padding))
    footer.pack(side="bottom", fill="x")
    ttk.Separator(win, orient="horizontal").pack(side="bottom", fill="x")

    holder = ttk.Frame(win)
    holder.pack(side="top", fill="both", expand=True)
    canvas = tk.Canvas(holder, highlightthickness=0, borderwidth=0)
    bar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    body = ttk.Frame(canvas, padding=padding)
    item = canvas.create_window(0, 0, window=body, anchor="nw")

    def fit_region(_e=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def fit_width(e) -> None:
        # Fill the width so grid weights still stretch the columns.
        canvas.itemconfigure(item, width=max(e.width, body.winfo_reqwidth()))

    body.bind("<Configure>", fit_region)
    canvas.bind("<Configure>", fit_width)

    def wheel(e) -> str | None:
        if isinstance(e.widget, (tk.Text, tk.Listbox)):
            return None  # these scroll themselves
        if body.winfo_reqheight() <= canvas.winfo_height():
            return None  # everything fits
        if getattr(e, "num", None) == 4 or getattr(e, "delta", 0) > 0:
            canvas.yview_scroll(-1, "units")
        else:
            canvas.yview_scroll(1, "units")
        return "break"

    # Every widget in the window carries the toplevel's bind tag, so this covers
    # the whole form without reaching other windows (combobox drop-downs are
    # their own toplevels and keep their own scrolling).
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        win.bind(seq, wheel, add="+")
    return body, footer
