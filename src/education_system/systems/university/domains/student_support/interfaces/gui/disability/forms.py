"""Small shared form dialog and table helpers for the DSA and PEEP panels."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

logger = logging.getLogger(__name__)


def show_error(parent, title, exc) -> None:
    if isinstance(exc, (PermissionError, ValueError)):
        messagebox.showerror(title, str(exc), parent=parent)
    else:
        logger.exception("%s action failed", title)
        messagebox.showerror(title, f"That didn't work: {exc}", parent=parent)


def ask_form(parent, title, fields, *, width=48):
    """A modal form parented to ``parent``'s window. ``fields`` is a list of
    ``(key, label, kind, extra)`` with kind ``entry`` / ``combo`` (extra =
    values) / ``check`` / ``text`` and an optional default in ``extra`` for
    entry/check/text (``(values, default)`` for combo). Returns the values
    as a dict, or ``None`` when cancelled."""
    top = parent.winfo_toplevel()
    win = tk.Toplevel(top)
    win.title(title)
    win.transient(top)
    body = ttk.Frame(win, padding=12)
    body.pack(fill=tk.BOTH, expand=True)
    getters = {}
    for row, (key, label, kind, extra) in enumerate(fields):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="nw", pady=3, padx=(0, 8))
        if kind == "combo":
            values, default = extra
            var = tk.StringVar(value=default or "")
            ttk.Combobox(body, textvariable=var, values=list(values), width=width - 2).grid(
                row=row, column=1, sticky="we", pady=3)
            getters[key] = var.get
        elif kind == "check":
            var = tk.BooleanVar(value=bool(extra))
            ttk.Checkbutton(body, variable=var).grid(row=row, column=1, sticky="w", pady=3)
            getters[key] = var.get
        elif kind == "text":
            box = scrolledtext.ScrolledText(body, width=width, height=5, wrap=tk.WORD)
            box.insert("1.0", extra or "")
            box.grid(row=row, column=1, sticky="we", pady=3)
            getters[key] = (lambda b=box: b.get("1.0", tk.END).strip())
        else:
            var = tk.StringVar(value="" if extra is None else str(extra))
            ttk.Entry(body, textvariable=var, width=width).grid(row=row, column=1, sticky="we",
                                                               pady=3)
            getters[key] = var.get
    result = {}

    def ok():
        result.update({k: g() for k, g in getters.items()})
        win.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side=tk.RIGHT)
    ttk.Button(bar, text="Save", command=ok).pack(side=tk.RIGHT, padx=6)
    win.grab_set()
    win.wait_window()
    return result or None


def make_tree(parent, columns, height=8):
    """A treeview with a scrollbar; ``columns`` is ``[(key, label, width)]``."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height,
                        selectmode="browse")
    for key, label, width in columns:
        tree.heading(key, text=label)
        tree.column(key, width=width, anchor=tk.W)
    sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    return frame, tree


def fill_tree(tree, rows, columns, key="id"):
    tree.delete(*tree.get_children())
    for row in rows:
        tree.insert("", tk.END, iid=str(row[key]),
                    values=[("" if row.get(c[0]) is None else row.get(c[0])) for c in columns])


def selected_id(tree, parent, title, what="a row"):
    sel = tree.selection()
    if not sel:
        messagebox.showinfo(title, f"Select {what} first.", parent=parent)
        return None
    return int(sel[0])


def button_bar(parent, buttons, enabled=True):
    bar = ttk.Frame(parent)
    bar.pack(fill=tk.X, pady=(4, 4))
    for text, command in buttons:
        btn = ttk.Button(bar, text=text, command=command)
        btn.pack(side=tk.LEFT, padx=(0, 4))
        if not enabled:
            btn.config(state="disabled")
    return bar
