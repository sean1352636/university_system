"""Shared Tk building blocks for the small operations windows
(lockers, parking, catering, ID cards).

Each window is a notebook of :class:`TableTab` pages — a filter bar, an
action bar and a table — plus a :class:`SummaryTab`. Add/edit dialogs
are built from :class:`Field` lists by :func:`form_dialog`. Domain
``ValidationError`` / ``PermissionError`` raised by an action are shown
as an error box instead of escaping into Tk's callback handler.
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable, Sequence

from education_system.platform import branding
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


@dataclass
class Field:
    key: str
    label: str
    kind: str = "entry"          # entry | combo | check | text | multi
    values: Sequence[Any] = ()   # combo options, or multi checkboxes
    required: bool = False
    width: int = 36
    readonly: bool = True        # combo: restrict to the list


def make_window(parent: Any, title: str) -> tuple[tk.Misc, ttk.Notebook]:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"{title} — {branding.SYSTEM_NAME}")
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    return win, nb


def show_error(parent: tk.Misc, exc: BaseException) -> None:
    messagebox.showerror("Not saved", str(exc), parent=parent)


def guarded(parent: tk.Misc, fn: Callable[[], Any]) -> Any:
    """Run ``fn``; show expected domain errors, log unexpected ones."""
    try:
        return fn()
    except (ValueError, PermissionError) as e:
        show_error(parent, e)
    except Exception as e:  # noqa: BLE001 - surface, don't crash Tk
        logger.exception("Operations window action failed")
        messagebox.showerror("Error", f"Unexpected error: {e}",
                             parent=parent)
    return None


def form_dialog(parent: tk.Misc, title: str, fields: list[Field],
                initial: dict[str, Any] | None = None
                ) -> dict[str, Any] | None:
    """Modal form. Returns ``{key: value}`` (str / bool / list[str]) or
    ``None`` on cancel. Required fields are checked before closing."""
    initial = initial or {}
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent.winfo_toplevel())
    body = ttk.Frame(dlg, padding=12)
    body.pack(fill="both", expand=True)
    getters: dict[str, Callable[[], Any]] = {}
    for row, f in enumerate(fields):
        ttk.Label(body, text=f.label + (" *" if f.required else "")
                  ).grid(row=row, column=0, sticky="nw", padx=(0, 8),
                         pady=3)
        init = initial.get(f.key)
        if f.kind == "check":
            var = tk.BooleanVar(value=bool(init))
            ttk.Checkbutton(body, variable=var).grid(
                row=row, column=1, sticky="w", pady=3)
            getters[f.key] = var.get
        elif f.kind == "combo":
            labels = [str(v) for v in f.values]
            cb = ttk.Combobox(body, values=labels, width=f.width,
                              state="readonly" if f.readonly else "normal")
            if init not in (None, ""):
                cb.set(str(init))
            elif labels and f.required:
                cb.current(0)
            cb.grid(row=row, column=1, sticky="w", pady=3)
            getters[f.key] = cb.get
        elif f.kind == "text":
            txt = tk.Text(body, width=f.width + 10, height=4, wrap="word")
            if init:
                txt.insert("1.0", str(init))
            txt.grid(row=row, column=1, sticky="w", pady=3)
            getters[f.key] = (lambda t=txt: t.get("1.0", "end").strip())
        elif f.kind == "multi":
            box = ttk.Frame(body)
            box.grid(row=row, column=1, sticky="w", pady=3)
            chosen = set(init or [])
            vars_: list[tuple[str, tk.BooleanVar]] = []
            for i, v in enumerate(f.values):
                var = tk.BooleanVar(value=v in chosen)
                ttk.Checkbutton(box, text=str(v), variable=var).grid(
                    row=i // 3, column=i % 3, sticky="w", padx=(0, 10))
                vars_.append((str(v), var))
            getters[f.key] = (lambda vs=vars_: [n for n, b in vs if b.get()])
        else:
            ent = ttk.Entry(body, width=f.width)
            if init not in (None, ""):
                ent.insert(0, str(init))
            ent.grid(row=row, column=1, sticky="w", pady=3)
            getters[f.key] = ent.get
    result: dict[str, Any] = {}
    ok = {"value": False}

    def _save() -> None:
        values = {k: g() for k, g in getters.items()}
        for f in fields:
            v = values.get(f.key)
            if f.required and (v is None or (isinstance(v, str)
                                             and not v.strip())):
                messagebox.showwarning("Missing", f"{f.label} is required",
                                       parent=dlg)
                return
        result.update(values)
        ok["value"] = True
        dlg.destroy()

    btns = ttk.Frame(dlg, padding=(12, 0, 12, 12))
    btns.pack(fill="x")
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(
        side="right", padx=6)
    dlg.bind("<Escape>", lambda _e: dlg.destroy())
    grab_when_viewable(dlg)
    dlg.wait_window()
    return result if ok["value"] else None


def option_label(key: Any, text: str) -> str:
    return f"{key} — {text}"


def option_key(label: str | None) -> str | None:
    """Inverse of :func:`option_label`: the part before " — "."""
    if not label:
        return None
    return label.split(" — ", 1)[0].strip() or None


class TableTab:
    """Filter bar + action bar + table, refreshed from ``loader``.

    ``loader(filters)`` returns ``[(iid, values, tags), ...]``;
    ``actions`` are ``(label, callback)`` where the callback receives
    this tab. The action bar is packed before the table so it stays
    visible when the window is short.
    """

    def __init__(self, nb: ttk.Notebook, label: str,
                 columns: list[tuple[str, str, int]],
                 loader: Callable[[dict[str, Any]], list[tuple]],
                 *, actions: list[tuple[str, Callable[["TableTab"], None]]],
                 filters: list[Field] | None = None,
                 on_double: Callable[["TableTab"], None] | None = None,
                 tag_colours: dict[str, tuple[str, str]] | None = None,
                 selectmode: str = "browse") -> None:
        self.loader = loader
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._filter_getters: dict[str, Callable[[], Any]] = {}

        if filters:
            bar = ttk.Frame(self.frame)
            bar.pack(fill="x", padx=8, pady=(8, 4))
            for f in filters:
                if f.kind == "check":
                    var = tk.BooleanVar(value=False)
                    ttk.Checkbutton(bar, text=f.label, variable=var).pack(
                        side="left", padx=(0, 8))
                    self._filter_getters[f.key] = var.get
                    continue
                ttk.Label(bar, text=f"{f.label}:").pack(side="left")
                if f.kind == "combo":
                    cb = ttk.Combobox(bar, values=[""] + [str(v)
                                                          for v in f.values],
                                      state="readonly", width=f.width)
                    cb.current(0)
                    cb.pack(side="left", padx=(2, 8))
                    self._filter_getters[f.key] = cb.get
                else:
                    ent = ttk.Entry(bar, width=f.width)
                    ent.pack(side="left", padx=(2, 8))
                    ent.bind("<Return>", lambda _e: self.refresh())
                    self._filter_getters[f.key] = ent.get
            ttk.Button(bar, text="Apply", command=self.refresh).pack(
                side="left", padx=4)

        actions_bar = ttk.Frame(self.frame)
        actions_bar.pack(side="bottom", fill="x", padx=8, pady=(4, 8))
        for text, cb in actions:
            ttk.Button(actions_bar, text=text,
                       command=lambda c=cb: guarded(self.frame,
                                                    lambda: c(self))
                       ).pack(side="left", padx=4)
        ttk.Button(actions_bar, text="Refresh",
                   command=self.refresh).pack(side="left", padx=4)
        self.count = ttk.Label(actions_bar, text="")
        self.count.pack(side="right")

        table = ttk.Frame(self.frame)
        table.pack(fill="both", expand=True, padx=8, pady=4)
        keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(table, columns=keys, show="headings",
                                 selectmode=selectmode)
        for key, heading, width in columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w")
        vsb = ttk.Scrollbar(table, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for tag, (bg, fg) in (tag_colours or {}).items():
            self.tree.tag_configure(tag, background=bg, foreground=fg)
        if on_double is not None:
            self.tree.bind("<Double-Button-1>",
                           lambda _e: guarded(self.frame,
                                              lambda: on_double(self)))
        self.refresh()

    def filters(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, g in self._filter_getters.items():
            v = g()
            if isinstance(v, str):
                v = v.strip()
            if v not in ("", None, False):
                out[k] = v
        return out

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = guarded(self.frame, lambda: self.loader(self.filters())) or []
        for iid, values, tags in rows:
            self.tree.insert("", "end", iid=str(iid),
                             values=[("" if v is None else v)
                                     for v in values],
                             tags=tuple(tags))
        self.count.configure(text=f"{len(rows)} row(s)")

    def selected(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Select a row first.",
                                parent=self.frame)
            return None
        return sel[0]

    def selected_all(self) -> list[str]:
        return list(self.tree.selection())


class SummaryTab:
    """Read-only text page rebuilt from ``render()`` (list of lines)."""

    def __init__(self, nb: ttk.Notebook, render: Callable[[], list[str]],
                 label: str = "Summary") -> None:
        self.render = render
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        bar = ttk.Frame(self.frame)
        bar.pack(side="bottom", fill="x", padx=8, pady=(4, 8))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="left")
        self.text = tk.Text(self.frame, wrap="word", font=("TkFixedFont",))
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        lines = guarded(self.frame, self.render) or []
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


def student_options() -> list[str]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return [option_label(s.student_id, s.full_name)
            for s in sorted(_students.list_students(),
                            key=lambda s: (s.last_name, s.first_name))]


def staff_options() -> list[str]:
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    return [option_label(s.staff_id, s.full_name)
            for s in sorted(_staff.list_staff(), key=lambda s: s.staff_id)]


def money(v: float | None) -> str:
    return "" if v is None else f"£{v:,.2f}"
