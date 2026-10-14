"""Presentable report surfaces for the Academics GUIs.

Used by the Degree Audit screens, the Course Evaluation results, Module
Scheduling analytics and the Academic Calendar reports.

Reports used to be written as plain text into a fixed-height
``ScrolledText``. Three problems came with that: the output was a wall of
monospace prose, long results ran past the bottom of a panel that could not
grow, and the big analyses buried themselves in a tab rather than opening
where you were looking.

This gives them a common vocabulary — a banner, a strip of headline numbers,
titled cards, label/value grids and tables — either inside an existing frame
or in a window of its own. Everything sits on a scrolling canvas, so a long
report scrolls instead of being clipped.

It lives at the ``academics.interfaces.gui`` level, and imports nothing but
tkinter, so any Academics GUI can use it without loading another GUI's
package. It used to sit inside ``course_management_gui``, whose ``__init__``
imports the whole Course Management application; that path still works.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

BG = "#eef1f4"          # page behind the cards
CARD = "#ffffff"
HEADER = "#2c3e50"
ACCENT = "#3498db"
LABEL = "#6b7280"
VALUE = "#1f2933"
MUTED = "#95a5a6"
OK = "#16a34a"
WARN = "#d97706"
BAD = "#dc2626"
FONT = "Segoe UI"       # Tk substitutes a sane default where absent


def scrollable(parent, bg=BG):
    """Return an inner frame on a vertically scrolling canvas filling *parent*.

    The wheel is bound while the pointer is over the area and unbound on
    leave, so it doesn't fight a notebook or a second scroller elsewhere.
    """
    outer = tk.Frame(parent, bg=bg)
    outer.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0, bg=bg)
    bar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    inner = tk.Frame(canvas, bg=bg)
    window = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    def _wheel(event):
        delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
        canvas.yview_scroll(delta, "units")

    canvas.bind("<Enter>", lambda e: (canvas.bind_all("<MouseWheel>", _wheel),
                                      canvas.bind_all("<Button-4>", _wheel),
                                      canvas.bind_all("<Button-5>", _wheel)))
    canvas.bind("<Leave>", lambda e: (canvas.unbind_all("<MouseWheel>"),
                                      canvas.unbind_all("<Button-4>"),
                                      canvas.unbind_all("<Button-5>")))
    return inner


def clear(frame):
    for child in frame.winfo_children():
        child.destroy()


def banner(parent, title, subtitle="", tone=HEADER):
    bar = tk.Frame(parent, bg=tone)
    bar.pack(fill=tk.X, padx=6, pady=(6, 0))
    tk.Label(bar, text=title, font=(FONT, 13, "bold"), bg=tone, fg="white",
             anchor="w").pack(anchor="w", padx=16, pady=(12, 0))
    if subtitle:
        tk.Label(bar, text=subtitle, font=(FONT, 9), bg=tone, fg="#bdc3c7",
                 anchor="w").pack(anchor="w", padx=16, pady=(2, 12))
    else:
        tk.Frame(bar, bg=tone, height=12).pack()
    return bar


def stat_strip(parent, items):
    """A row of headline figures: ``[(value, label), ...]``."""
    strip = tk.Frame(parent, bg=BG)
    strip.pack(fill=tk.X, padx=2, pady=(2, 0))
    for column in range(len(items)):
        strip.columnconfigure(column, weight=1, uniform="stat")
    for column, item in enumerate(items):
        value, label = item[0], item[1]
        colour = item[2] if len(item) > 2 else ACCENT
        cell = tk.Frame(strip, bg=CARD, highlightbackground="#e5e7eb",
                        highlightthickness=1)
        cell.grid(row=0, column=column, sticky="ew", padx=4, pady=6)
        tk.Label(cell, text=str(value), font=(FONT, 13, "bold"),
                 bg=CARD, fg=colour).pack(pady=(8, 0))
        tk.Label(cell, text=label, font=(FONT, 8), bg=CARD,
                 fg=LABEL).pack(pady=(0, 8))
    return strip


def card(parent, title=None, accent=ACCENT):
    """A white card; returns the body frame to fill."""
    shell = tk.Frame(parent, bg=CARD, highlightbackground="#e5e7eb",
                     highlightthickness=1)
    shell.pack(fill=tk.X, padx=6, pady=6)
    if title:
        head = tk.Frame(shell, bg=CARD)
        head.pack(fill=tk.X, padx=12, pady=(10, 0))
        tk.Frame(head, bg=accent, width=4, height=15).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(head, text=title, font=(FONT, 10, "bold"), bg=CARD,
                 fg=HEADER).pack(side=tk.LEFT)
    body = tk.Frame(shell, bg=CARD)
    body.pack(fill=tk.X, padx=12, pady=8)
    return body


def kv_grid(body, pairs, cols=2):
    """Label/value pairs laid out in *cols* columns."""
    grid = tk.Frame(body, bg=CARD)
    grid.pack(fill=tk.X)
    for c in range(cols):
        grid.columnconfigure(c * 2 + 1, weight=1, uniform="val")
    for index, (label, value) in enumerate(pairs):
        row, base = divmod(index, cols)
        base *= 2
        tk.Label(grid, text=label, font=(FONT, 8), bg=CARD, fg=LABEL,
                 anchor="w").grid(row=row, column=base, sticky="w",
                                  padx=(0, 8), pady=3)
        tk.Label(grid, text=str(value), font=(FONT, 9, "bold"), bg=CARD,
                 fg=VALUE, anchor="w", justify="left", wraplength=320
                 ).grid(row=row, column=base + 1, sticky="w", padx=(0, 20), pady=3)
    return grid


def status_list(body, items):
    """Pass/fail lines: ``[(ok_bool_or_None, text, detail), ...]``.

    ``None`` means "not assessed" — shown in grey rather than as a failure,
    because an unchecked requirement is not the same as an unmet one.
    """
    for item in items:
        ok, text = item[0], item[1]
        detail = item[2] if len(item) > 2 else ""
        mark, colour = ("✓", OK) if ok else (("—", MUTED) if ok is None else ("✗", BAD))
        row = tk.Frame(body, bg=CARD)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=mark, font=(FONT, 11, "bold"), bg=CARD, fg=colour,
                 width=2).pack(side=tk.LEFT)
        tk.Label(row, text=text, font=(FONT, 9), bg=CARD, fg=VALUE,
                 anchor="w").pack(side=tk.LEFT)
        if detail:
            tk.Label(row, text=f"  {detail}", font=(FONT, 8), bg=CARD,
                     fg=LABEL, anchor="w").pack(side=tk.LEFT)


def verdict(parent, ok, headline, detail="", neutral=False):
    """A prominent outcome banner."""
    tone = MUTED if neutral else (OK if ok else BAD)
    body = card(parent, accent=tone)
    tk.Label(body, text=headline, font=(FONT, 11, "bold"), bg=CARD,
             fg=tone, anchor="w").pack(anchor="w")
    if detail:
        tk.Label(body, text=detail, font=(FONT, 9), bg=CARD, fg=VALUE,
                 anchor="w", justify="left", wraplength=620).pack(anchor="w", pady=(4, 0))
    return body


def table(parent, columns, rows, widths=None, height=10):
    """A tidy Treeview inside a card."""
    body = card(parent)
    style = ttk.Style()
    style.configure("DegreeAudit.Treeview", rowheight=24, font=(FONT, 9))
    style.configure("DegreeAudit.Treeview.Heading", font=(FONT, 9, "bold"))
    holder = tk.Frame(body, bg=CARD)
    holder.pack(fill=tk.BOTH, expand=True)
    tree = ttk.Treeview(holder, columns=list(columns), show="headings",
                        style="DegreeAudit.Treeview",
                        height=min(height, max(3, len(rows))))
    widths = widths or {}
    for column in columns:
        tree.heading(column, text=column)
        tree.column(column, width=widths.get(column, 120), anchor=tk.W)
    tree.tag_configure("_odd", background="#f7f9fb")
    for index, values in enumerate(rows):
        tree.insert("", tk.END, values=list(values),
                    tags=("_odd",) if index % 2 else ())
    bar = ttk.Scrollbar(holder, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    bar.pack(side=tk.RIGHT, fill=tk.Y)
    return tree


def report_window(parent, title, size="900x680"):
    """A scrollable report window. Returns ``(window, inner_frame)``.

    The close button is packed before the body so a long report can never
    push it off the bottom.
    """
    window = tk.Toplevel(parent)
    window.title(title)
    window.geometry(size)
    window.minsize(720, 480)
    window.configure(bg=BG)
    try:
        window.transient(parent)
    except tk.TclError:
        logger.debug("could not set transient parent", exc_info=True)

    actions = ttk.Frame(window, padding=8)
    actions.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Button(actions, text="Close", command=window.destroy).pack(side=tk.RIGHT)

    body = tk.Frame(window, bg=BG)
    body.pack(fill=tk.BOTH, expand=True)
    return window, scrollable(body)


__all__ = [
    "scrollable", "clear", "banner", "stat_strip", "card", "kv_grid",
    "status_list", "verdict", "table", "report_window",
    "BG", "CARD", "HEADER", "ACCENT", "LABEL", "VALUE", "MUTED",
    "OK", "WARN", "BAD", "FONT",
]
