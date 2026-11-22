"""Small Tkinter helpers shared by the admissions add-on screens.

Entry requirements, results day, open events, references, online
verification, Year 11 transition, identity checks and consents all need
the same three things: a sized Toplevel, a scrolling table, and a
modal form. They live here so each screen stays about its workflow.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from typing import Any, Callable, Iterable

from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)

#: (key, label, kind, options) — kind is entry / combo / readonly /
#: check / text; options is the value list for combos.
Field = tuple[str, str, str, Iterable[str] | None]


def new_window(parent: tk.Misc | None, title: str, *,
               geometry: str = "1400x900",
               minsize: tuple[int, int] = (1200, 800)) -> tk.Toplevel | tk.Tk:
    master = getattr(parent, "root", parent)
    win = make_toplevel(master) if master is not None else tk.Tk()
    win.title(title)
    try:
        from education_system.platform.delivery.gui import window_sizing
        window_sizing.fit(win, geometry, minsize)
    except Exception:
        win.geometry(geometry)
        win.minsize(*minsize)
    return win


def make_tree(parent: tk.Misc, columns: list[tuple[str, str, int]], *,
              height: int = 14, selectmode: str = "browse") -> ttk.Treeview:
    """A Treeview with a vertical scrollbar, packed to fill ``parent``."""
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=[c[0] for c in columns],
                        show="headings", height=height,
                        selectmode=selectmode)
    for key, heading, width in columns:
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor="w")
    vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    return tree


def clear(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)


def selected_iid(tree: ttk.Treeview) -> str | None:
    sel = tree.selection()
    return sel[0] if sel else None


def require_iid(tree: ttk.Treeview, title: str) -> str | None:
    iid = selected_iid(tree)
    if iid is None:
        messagebox.showinfo(title, "Select a row first.",
                            parent=tree.winfo_toplevel())
    return iid


def ask_form(parent: tk.Misc, title: str, fields: list[Field],
             initial: dict[str, Any] | None = None, *,
             on_submit: Callable[[dict[str, Any]], Any] | None = None,
             ) -> dict[str, Any] | None:
    """Modal form. Returns the values, or None if cancelled.

    When ``on_submit`` is given it is called with the values; an
    exception keeps the dialog open and shows the message, so a
    validation error can be fixed in place.
    """
    initial = initial or {}
    win = make_toplevel(parent)
    win.title(title)
    grab_when_viewable(win)
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    widgets: dict[str, Any] = {}
    for row, (key, label, kind, options) in enumerate(fields):
        ttk.Label(body, text=label + ":").grid(row=row, column=0,
                                               sticky="ne", padx=4, pady=3)
        value = initial.get(key)
        if kind in ("combo", "readonly"):
            w = ttk.Combobox(body, values=tuple(options or ()), width=40,
                             state="readonly" if kind == "readonly"
                             else "normal")
            w.set("" if value is None else str(value))
        elif kind == "check":
            var = tk.BooleanVar(value=bool(value))
            w = ttk.Checkbutton(body, variable=var)
            w.var = var  # type: ignore[attr-defined]
        elif kind == "text":
            w = tk.Text(body, width=52, height=5, wrap="word")
            if value:
                w.insert("1.0", str(value))
        else:
            w = ttk.Entry(body, width=42)
            if value not in (None, ""):
                w.insert(0, str(value))
        w.grid(row=row, column=1, sticky="w", padx=4, pady=3)
        widgets[key] = (kind, w)
    result: dict[str, Any] = {}

    def values() -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, (kind, w) in widgets.items():
            if kind == "check":
                out[key] = bool(w.var.get())
            elif kind == "text":
                out[key] = w.get("1.0", "end").strip()
            else:
                out[key] = w.get().strip()
        return out

    def ok() -> None:
        vals = values()
        if on_submit is not None:
            try:
                on_submit(vals)
            except Exception as e:  # noqa: BLE001 — shown, dialog stays open
                messagebox.showerror(title, str(e), parent=win)
                return
        result.update(vals)
        result["__ok__"] = True
        win.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=len(fields), column=0, columnspan=2, pady=(10, 0))
    ttk.Button(bar, text="OK", command=ok).pack(side="left", padx=4)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")
    win.bind("<Escape>", lambda _e: win.destroy())
    win.wait_window()
    if not result.pop("__ok__", False):
        return None
    return result


def show_text(parent: tk.Misc, title: str, text: str) -> None:
    """Read-only text with Copy / Close (letters, emails, reports)."""
    win = make_toplevel(parent)
    win.title(title)
    bar = ttk.Frame(win, padding=(8, 8, 8, 0))
    bar.pack(fill="x")

    def copy() -> None:
        win.clipboard_clear()
        win.clipboard_append(text)

    ttk.Button(bar, text="Copy", command=copy).pack(side="left")
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="left",
                                                            padx=6)
    t = tk.Text(win, width=90, height=28, wrap="word")
    t.pack(fill="both", expand=True, padx=8, pady=8)
    t.insert("1.0", text)
    t.configure(state="disabled")


def current_username() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def pick_applicant(parent: tk.Misc, title: str = "Choose applicant"
                   ) -> str | None:
    """Pick an applicant id from a searchable list."""
    from education_system.systems.sixth_form.domain.admissions import (
        admissions as data,
    )
    win = make_toplevel(parent)
    win.title(title)
    grab_when_viewable(win)
    top = ttk.Frame(win, padding=8)
    top.pack(fill="x")
    ttk.Label(top, text="Search:").pack(side="left")
    q = ttk.Entry(top, width=30)
    q.pack(side="left", padx=4)
    bar = ttk.Frame(win, padding=8)
    bar.pack(side="bottom", fill="x")
    tree_holder = ttk.Frame(win, padding=(8, 0, 8, 0))
    tree_holder.pack(fill="both", expand=True)
    tree = make_tree(tree_holder, [("id", "ID", 90), ("name", "Name", 220),
                                   ("status", "Status", 140)], height=16)
    chosen: dict[str, str] = {}

    def load(*_a: Any) -> None:
        clear(tree)
        for a in data.list_applicants(search=q.get().strip() or None):
            tree.insert("", "end", iid=a.applicant_id,
                        values=(a.applicant_id, a.full_name, a.status))

    def ok(*_a: Any) -> None:
        iid = selected_iid(tree)
        if iid:
            chosen["id"] = iid
            win.destroy()

    q.bind("<KeyRelease>", load)
    tree.bind("<Double-1>", ok)
    ttk.Button(bar, text="Choose", command=ok).pack(side="left")
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left",
                                                             padx=6)
    load()
    win.wait_window()
    return chosen.get("id")
