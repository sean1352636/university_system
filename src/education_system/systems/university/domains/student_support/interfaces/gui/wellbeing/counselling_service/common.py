"""Small helpers shared by the Counselling Service screens."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

TITLE = "Counselling Service"


def title() -> str:
    return _t("gui.student_support.counselling_service.title", default=TITLE)


def show_error(parent, exc) -> None:
    if isinstance(exc, (PermissionError, ValueError)):
        messagebox.showerror(title(), str(exc), parent=parent)
    else:
        logger.exception("Counselling service action failed")
        messagebox.showerror(title(), f"That didn't work: {exc}", parent=parent)


def run(parent, fn, *args, **kwargs):
    """``fn(*args, **kwargs)``, showing any error; ``None`` on failure."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # shown to the user as it is
        show_error(parent, exc)
        return None


def dialog(parent, text, size="560x460") -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title(text)
    win.geometry(size)
    win.transient(parent.winfo_toplevel())
    return win


def tree(master, columns, height=14) -> ttk.Treeview:
    """A Treeview with a scrollbar packed into ``master``. ``columns`` is
    ``((key, heading, width), ...)``."""
    frame = ttk.Frame(master)
    frame.pack(fill=tk.BOTH, expand=True)
    view = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height, selectmode="browse")
    for key, heading, width in columns:
        view.heading(key, text=heading)
        view.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
    view.configure(yscrollcommand=bar.set)
    view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    bar.pack(side=tk.LEFT, fill=tk.Y)
    return view


def fill(view: ttk.Treeview, rows, columns, empty_text="") -> dict:
    """Replace the rows; returns ``{iid: row}``. An empty list shows one
    greyed line saying so."""
    view.delete(*view.get_children())
    found = {}
    for row in rows:
        iid = view.insert("", tk.END, values=[_cell(row.get(c[0])) for c in columns])
        found[iid] = row
    if not found and empty_text:
        view.insert("", tk.END, values=[empty_text] + [""] * (len(columns) - 1),
                    tags=("empty",))
        view.tag_configure("empty", foreground="#777777")
    return found


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else ""
    return value


def selected(view: ttk.Treeview, rows: dict, parent, what="a row"):
    sel = view.selection()
    if not sel or sel[0] not in rows:
        messagebox.showinfo(title(), f"Select {what} first.", parent=parent)
        return None
    return rows[sel[0]]


def text_box(master, height=6, width=60) -> tk.Text:
    box = tk.Text(master, height=height, width=width, wrap="word")
    return box


def read_text(box: tk.Text) -> str:
    return box.get("1.0", tk.END).strip()


def readonly_text(master, content, height=20) -> tk.Text:
    box = tk.Text(master, height=height, wrap="word")
    box.insert("1.0", content)
    box.configure(state="disabled")
    return box
