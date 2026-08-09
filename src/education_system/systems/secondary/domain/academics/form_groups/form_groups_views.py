"""Tk views for form groups."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.academics.form_groups import (
    form_groups as data,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Form Groups", str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


_FIELDS = [
    ("name",       "Form name (e.g. 7A)"),
    ("year_group", "Year group"),
    ("form_tutor", "Form tutor"),
    ("room",       "Room"),
    ("notes",      "Notes"),
]


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None
                 ) -> dict[str, str] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("420x300")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}

    for i, (key, label) in enumerate(_FIELDS):
        ttk.Label(frm, text=f"{label}:").grid(row=i, column=0, sticky="w",
                                               pady=2)
        if key == "year_group":
            v = tk.StringVar(value=str(initial.get(key) or YEAR_GROUPS[0]))
            ttk.Combobox(frm, textvariable=v, values=list(YEAR_GROUPS),
                         state="readonly", width=8).grid(
                row=i, column=1, sticky="w", pady=2)
        else:
            v = tk.StringVar(value=str(initial.get(key) or ""))
            ttk.Entry(frm, textvariable=v, width=32).grid(
                row=i, column=1, sticky="ew", pady=2)
        vars_[key] = v
    frm.columnconfigure(1, weight=1)

    result: dict[str, str] | None = None

    def _save() -> None:
        nonlocal result
        result = {k: (v.get() or "").strip() for k, v in vars_.items()}
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(_FIELDS), column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                               padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_form_groups(host) -> None:
    logger.debug("GUI: open_form_groups")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Form Groups", font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Year filter:").pack(side="left", padx=(0, 6))
    year_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly", width=6).pack(
        side="left", padx=(0, 8))
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)).pack(side="left",
                                                                   padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "year", "name", "tutor", "room", "pupils", "notes")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=16)
    for c, label, w in [
        ("id", "ID", 60), ("year", "Year", 60), ("name", "Form", 90),
        ("tutor", "Form Tutor", 180), ("room", "Room", 90),
        ("pupils", "Pupils", 70), ("notes", "Notes", 260),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_all(year_group=year_var.get().strip() or None)
            counts = data.pupil_counts()
        except ValidationError as e:
            messagebox.showerror("Form Groups", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("form_groups refresh failed")
            messagebox.showerror("Form Groups",
                                 f"Could not load form groups:\n\n{e}",
                                 parent=host.root)
            return
        for f in rows:
            tree.insert("", "end", iid=str(f.form_id), values=(
                f.form_id, f.year_group, f.name,
                f.form_tutor or "-", f.room or "-",
                counts.get(f.form_id, 0), f.notes or "-",
            ))
        host.status_var.set(f"Form Groups: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit_selected(host, tree,
                                                       on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Form Groups", "Select a form group first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _form_dialog(host, "New form group")
    if not fields:
        return
    rec = data.create(fields)
    messagebox.showinfo("Form Groups",
                        f"Created {rec.name} (Year {rec.year_group})",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    form_id = _selected_id(tree, host)
    if form_id is None:
        return
    existing = data.get(form_id)
    if existing is None:
        messagebox.showerror("Form Groups",
                             f"No form group with id {form_id}",
                             parent=host.root)
        return
    initial = {k: getattr(existing, k) for k, _ in _FIELDS}
    fields = _form_dialog(host, f"Edit form #{form_id}", initial=initial)
    if not fields:
        return
    data.update(form_id, fields)
    if on_done:
        on_done()


@_safe_view
def _delete_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    form_id = _selected_id(tree, host)
    if form_id is None:
        return
    existing = data.get(form_id)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete form group",
            f"Delete form {existing.name} (Year {existing.year_group})?",
            parent=host.root):
        return
    data.delete(form_id)
    if on_done:
        on_done()
