"""Shared pieces for the admissions ``pages_*`` sections.

Each page is a ``ttk.Frame`` added to the Admissions window's sidebar
book. They all need the same few things: a scrolling table, a modal
form that keeps itself open on a validation error, a guarded call that
shows AccessDenied / ValidationError messages, a read-only text viewer
and a cycle picker. Dialogs are parented with ``make_toplevel`` so they
open above the Admissions window, never behind it.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Iterable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.gui._sidebar import (
    page_header,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)

logger = logging.getLogger(__name__)

MUTED = "#7f8c8d"

#: (key, label, kind, options) — kind is entry / combo / readonly /
#: check / text; options is the value list for combos.
Field = tuple[str, str, str, "Iterable[str] | None"]

#: Errors a domain call is expected to raise; shown, never logged as bugs.
EXPECTED = (access.AccessDenied, ValueError)


def can(capability: str) -> bool:
    try:
        return access.current().can(capability)
    except Exception:  # noqa: BLE001 — no principal means no access
        return False


def username() -> str:
    try:
        return access.current().username or ""
    except Exception:  # noqa: BLE001
        return ""


def today() -> str:
    return _dt.date.today().isoformat()


def new_page(nb: Any, text: str, title: str, blurb: str = "", *,
             on_show: Callable[[], None] | None = None) -> ttk.Frame:
    """A frame added to the sidebar book with the standard page header.

    *on_show* runs each time the page is shown (SidebarBook only)."""
    frame = ttk.Frame(nb, padding=(4, 4))
    if on_show is not None:
        nb.add(frame, text=text, on_show=on_show)
    else:
        nb.add(frame, text=text)
    page_header(frame, title, blurb)
    return frame


def error_page(nb: Any, text: str, error: BaseException) -> ttk.Frame:
    """Stand-in page for a section that failed to build, so the gap is
    visible and says why."""
    frame = ttk.Frame(nb, padding=(4, 4))
    nb.add(frame, text=text)
    page_header(frame, text, "This section could not be opened.")
    ttk.Label(frame, text=f"{type(error).__name__}: {error}",
              foreground="#b03a2e", wraplength=900, justify="left").pack(
        anchor="w", pady=(4, 4))
    ttk.Label(frame, text="The rest of the Admissions window still works. "
              "The full error is in the application log.",
              foreground=MUTED).pack(anchor="w")
    return frame


def denied(parent: tk.Misc, what: str) -> None:
    """A note in place of a page's content for someone without access."""
    ttk.Label(parent, text=f"You do not have access to {what}.",
              foreground="#b03a2e").pack(anchor="w", pady=8)


def make_tree(parent: tk.Misc, columns: list[tuple[str, str, int]], *,
              height: int = 14, selectmode: str = "browse") -> ttk.Treeview:
    """A Treeview with scrollbars, packed to fill *parent*."""
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=[c[0] for c in columns],
                        show="headings", height=height, selectmode=selectmode)
    for key, heading, width in columns:
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor="w", stretch=True)
    vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    hs = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
    hs.pack(side="bottom", fill="x")
    vs.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return tree


def clear(tree: ttk.Treeview) -> None:
    tree.delete(*tree.get_children())


def selected(tree: ttk.Treeview, title: str, *, quiet: bool = False
             ) -> str | None:
    sel = tree.selection()
    if sel:
        return sel[0]
    if not quiet:
        messagebox.showinfo(title, "Select a row first.",
                            parent=tree.winfo_toplevel())
    return None


def selected_all(tree: ttk.Treeview, title: str) -> list[str]:
    sel = list(tree.selection())
    if not sel:
        messagebox.showinfo(title, "Select one or more rows first.",
                            parent=tree.winfo_toplevel())
    return sel


def run(parent: tk.Misc, title: str, fn: Callable[..., Any], /, *a: Any,
        **kw: Any) -> tuple[bool, Any]:
    """Call *fn*; show any error. Returns (ok, result)."""
    try:
        return True, fn(*a, **kw)
    except EXPECTED as e:
        messagebox.showerror(title, str(e), parent=parent.winfo_toplevel())
    except Exception as e:  # noqa: BLE001 — shown, and logged as a fault
        logger.exception("%s failed", title)
        messagebox.showerror(title, f"Unexpected error: {e}",
                             parent=parent.winfo_toplevel())
    return False, None


def load(status: tk.StringVar, title: str, fn: Callable[..., Any], /,
         *a: Any, **kw: Any) -> tuple[bool, Any]:
    """Call a read for a refresh: errors go to the page's status line
    (no popup each time the page is shown)."""
    try:
        return True, fn(*a, **kw)
    except EXPECTED as e:
        status.set(str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("%s failed to load", title)
        status.set(f"{title} could not be loaded: {e}")
    return False, None


def status_line(parent: tk.Misc) -> tk.StringVar:
    var = tk.StringVar()
    ttk.Label(parent, textvariable=var, foreground="#555", wraplength=1000,
              justify="left").pack(fill="x", pady=(2, 2))
    return var


def ask_form(parent: tk.Misc, title: str, fields: list[Field],
             initial: dict[str, Any] | None = None, *,
             on_submit: Callable[[dict[str, Any]], Any] | None = None,
             intro: str | None = None) -> dict[str, Any] | None:
    """Modal form; returns the values or None if cancelled. With
    *on_submit*, an error keeps the form open and shows the message."""
    initial = initial or {}
    win = make_toplevel(parent.winfo_toplevel())
    win.title(title)
    grab_when_viewable(win)
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    row0 = 0
    if intro:
        ttk.Label(body, text=intro, wraplength=520, justify="left",
                  foreground=MUTED).grid(row=0, column=0, columnspan=2,
                                         sticky="w", pady=(0, 8))
        row0 = 1
    widgets: dict[str, tuple[str, Any]] = {}
    for i, (key, label, kind, options) in enumerate(fields):
        row = row0 + i
        ttk.Label(body, text=label + ":").grid(row=row, column=0, sticky="ne",
                                               padx=4, pady=3)
        value = initial.get(key)
        if kind in ("combo", "readonly"):
            w: Any = ttk.Combobox(body, values=tuple(options or ()), width=40,
                                  state="readonly" if kind == "readonly"
                                  else "normal")
            w.set("" if value is None else str(value))
        elif kind == "check":
            var = tk.BooleanVar(value=bool(value))
            w = ttk.Checkbutton(body, variable=var)
            w.var = var
        elif kind == "text":
            w = tk.Text(body, width=52, height=6, wrap="word")
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
            except EXPECTED as e:
                messagebox.showerror(title, str(e), parent=win)
                return
            except Exception as e:  # noqa: BLE001 — shown, form stays open
                logger.exception("%s failed", title)
                messagebox.showerror(title, f"Unexpected error: {e}",
                                     parent=win)
                return
        result.update(vals)
        result["__ok__"] = True
        win.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=row0 + len(fields), column=0, columnspan=2, pady=(10, 0))
    ttk.Button(bar, text="OK", command=ok).pack(side="left", padx=4)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")
    win.wait_window()
    if not result.pop("__ok__", False):
        return None
    return result


def ask_text(parent: tk.Misc, title: str, label: str, *,
             required: bool = False, initial: str = "") -> str | None:
    """One free-text answer (a reason or a note). None if cancelled."""
    def check(v: dict[str, Any]) -> None:
        if required and not v["text"]:
            raise ValueError(f"{label} is required.")
    out = ask_form(parent, title, [("text", label, "text", None)],
                   {"text": initial}, on_submit=check)
    return None if out is None else out["text"]


def show_text(parent: tk.Misc, title: str, text: str, *,
              save_name: str | None = None) -> None:
    """Read-only text with Copy / Save / Close."""
    win = make_toplevel(parent.winfo_toplevel())
    win.title(title)
    win.geometry("900x600")
    bar = ttk.Frame(win, padding=(8, 8, 8, 0))
    bar.pack(side="top", fill="x")

    def copy() -> None:
        win.clipboard_clear()
        win.clipboard_append(text)

    ttk.Button(bar, text="Copy", command=copy).pack(side="left")
    if save_name:
        ttk.Button(bar, text="Save…", command=lambda: save_file(
            win, text, save_name)).pack(side="left", padx=6)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="left",
                                                            padx=6)
    t = tk.Text(win, wrap="word")
    t.pack(fill="both", expand=True, padx=8, pady=8)
    t.insert("1.0", text)
    t.configure(state="disabled")


def save_file(parent: tk.Misc, text: str, initialfile: str) -> str | None:
    ext = initialfile.rsplit(".", 1)[-1] if "." in initialfile else "txt"
    path = filedialog.asksaveasfilename(
        parent=parent.winfo_toplevel(), initialfile=initialfile,
        defaultextension=f".{ext}",
        filetypes=[(ext.upper(), f"*.{ext}"), ("All files", "*.*")])
    if not path:
        return None
    try:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    except OSError as e:
        messagebox.showerror("Save", f"Could not save the file:\n{e}",
                             parent=parent.winfo_toplevel())
        return None
    messagebox.showinfo("Save", f"Saved to {path}",
                        parent=parent.winfo_toplevel())
    return path


def cycle_names() -> list[str]:
    from education_system.systems.sixth_form.domain.admissions import cycles
    try:
        return [c.cycle for c in cycles.list_cycles()]
    except Exception:  # noqa: BLE001 — an empty picker is shown instead
        logger.warning("Admissions cycles not read", exc_info=True)
        return []


def default_cycle() -> str:
    from education_system.systems.sixth_form.domain.admissions import (
        admissions as adm,
        cycles,
    )
    try:
        return cycles.current_cycle() or adm.default_intake_year()
    except Exception:  # noqa: BLE001
        return adm.default_intake_year()


class CyclePicker(ttk.Frame):
    """Label + editable combobox of cycles (a cycle not yet set up can
    still be typed, e.g. to rank applications already given that intake)."""

    def __init__(self, parent: tk.Misc, on_change: Callable[[], None], *,
                 label: str = "Cycle:", allow_all: bool = False) -> None:
        super().__init__(parent)
        self._on_change = on_change
        self._allow_all = allow_all
        ttk.Label(self, text=label).pack(side="left")
        self.box = ttk.Combobox(self, width=12)
        self.box.pack(side="left", padx=(4, 0))
        self.box.bind("<<ComboboxSelected>>", lambda _e: on_change())
        self.box.bind("<Return>", lambda _e: on_change())
        self.reload()
        self.box.set("" if allow_all else default_cycle())

    def reload(self) -> None:
        names = cycle_names()
        self.box.configure(values=(["(all)"] if self._allow_all else [])
                           + names)

    def get(self) -> str | None:
        v = self.box.get().strip()
        return None if v in ("", "(all)") else v


def pick_row(parent: tk.Misc, title: str,
             columns: list[tuple[str, str, int]],
             rows: list[tuple[str, tuple[Any, ...]]], *,
             prompt: str = "", search: bool = True) -> str | None:
    """Choose one row (iid, values) from a searchable table."""
    win = make_toplevel(parent.winfo_toplevel())
    win.title(title)
    win.geometry("760x520")
    grab_when_viewable(win)
    top = ttk.Frame(win, padding=8)
    top.pack(side="top", fill="x")
    if prompt:
        ttk.Label(top, text=prompt, wraplength=700, justify="left").pack(
            anchor="w", pady=(0, 4))
    q = ttk.Entry(top, width=30)
    if search:
        ttk.Label(top, text="Search:").pack(side="left")
        q.pack(side="left", padx=4)
    bar = ttk.Frame(win, padding=8)
    bar.pack(side="bottom", fill="x")
    holder = ttk.Frame(win, padding=(8, 0, 8, 0))
    holder.pack(fill="both", expand=True)
    tree = make_tree(holder, columns, height=16)
    chosen: dict[str, str] = {}

    def fill(*_a: Any) -> None:
        clear(tree)
        needle = q.get().strip().lower()
        for iid, values in rows:
            if needle and needle not in " ".join(map(str, values)).lower():
                continue
            tree.insert("", "end", iid=iid, values=values)

    def ok(*_a: Any) -> None:
        sel = tree.selection()
        if sel:
            chosen["id"] = sel[0]
            win.destroy()

    q.bind("<KeyRelease>", fill)
    tree.bind("<Double-1>", ok)
    ttk.Button(bar, text="Choose", command=ok).pack(side="left")
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left",
                                                             padx=6)
    fill()
    win.wait_window()
    return chosen.get("id")


def yes(v: Any) -> str:
    return "Yes" if v else ""


def fmt(v: Any) -> str:
    return "" if v is None else str(v)
