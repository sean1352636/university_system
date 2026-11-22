"""Small shared pieces for the Wellbeing Casework screens: error display,
a table, and a parented form dialog."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

logger = logging.getLogger(__name__)

TITLE = "Wellbeing Casework"


def show_error(parent, exc, title=TITLE) -> None:
    if isinstance(exc, (PermissionError, ValueError)):
        messagebox.showerror(title, str(exc), parent=parent)
    else:
        logger.exception("Wellbeing casework action failed")
        messagebox.showerror(title, f"That didn't work: {exc}", parent=parent)


def info(parent, text, title=TITLE) -> None:
    messagebox.showinfo(title, text, parent=parent)


def ask(parent, text, title=TITLE) -> bool:
    return bool(messagebox.askyesno(title, text, parent=parent))


class Table(ttk.Frame):
    """A Treeview with a scrollbar; rows are dicts keyed by column name."""

    def __init__(self, master, columns, height=12):
        super().__init__(master)
        self.columns = columns
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show="headings",
                                 selectmode="browse", height=height)
        for key, label, width in columns:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        bar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.LEFT, fill=tk.Y)
        self.rows: dict[str, dict] = {}

    def load(self, rows, empty_text=None):
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for row in rows:
            iid = self.tree.insert("", tk.END, values=[
                "" if row.get(k) is None else row.get(k) for k, _l, _w in self.columns])
            self.rows[iid] = row
        if not rows and empty_text:
            self.tree.insert("", tk.END, values=[empty_text] + [""] * (len(self.columns) - 1))

    def selected(self):
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def bind_open(self, callback):
        self.tree.bind("<Double-1>", lambda _e: callback())


def form_dialog(parent, title, fields, on_save, *, size="560x460"):
    """A modal form. ``fields`` is a list of ``(key, label, kind, default)``
    where kind is ``entry``, ``text``, ``check`` or a tuple of choices.
    ``on_save(values)`` raises to keep the dialog open."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(size)
    win.transient(parent.winfo_toplevel())
    body = ttk.Frame(win, padding=10)
    body.pack(fill=tk.BOTH, expand=True)
    getters = {}
    for row, (key, label, kind, default) in enumerate(fields):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="nw", pady=3, padx=(0, 6))
        if kind == "text":
            box = scrolledtext.ScrolledText(body, height=5, width=48, wrap="word")
            box.insert("1.0", default or "")
            box.grid(row=row, column=1, sticky="nsew", pady=3)
            getters[key] = lambda b=box: b.get("1.0", "end").strip()
        elif kind == "check":
            var = tk.BooleanVar(value=bool(default))
            ttk.Checkbutton(body, variable=var).grid(row=row, column=1, sticky="w", pady=3)
            getters[key] = var.get
        elif isinstance(kind, tuple):
            var = tk.StringVar(value=default if default is not None else (kind[0] if kind else ""))
            ttk.Combobox(body, textvariable=var, values=kind, state="readonly",
                         width=44).grid(row=row, column=1, sticky="w", pady=3)
            getters[key] = var.get
        else:
            var = tk.StringVar(value="" if default is None else str(default))
            ttk.Entry(body, textvariable=var, width=48).grid(row=row, column=1, sticky="we",
                                                             pady=3)
            getters[key] = lambda v=var: v.get().strip()
    body.columnconfigure(1, weight=1)

    def save():
        try:
            on_save({k: g() for k, g in getters.items()})
        except Exception as exc:
            show_error(win, exc)
            return
        win.destroy()

    bar = ttk.Frame(win, padding=(10, 0, 10, 10))
    bar.pack(fill=tk.X, side=tk.BOTTOM)
    ttk.Button(bar, text="Save", command=save).pack(side=tk.RIGHT)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side=tk.RIGHT, padx=6)
    try:
        win.grab_set()
    except tk.TclError:
        pass
    return win


def open_file(path) -> None:
    import webbrowser
    from pathlib import Path
    webbrowser.open(Path(path).resolve().as_uri())
