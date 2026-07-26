"""Tkinter views for Cohort Tracking (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Shows the cohort list with a tree + toolbar and an add/edit
form dialog — the GUI counterpart of ``cohort_tracking_cli.py``.

Cohort Tracking records are group-level attainment snapshots and are NOT
attached to any individual child.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.assessment.cohort_tracking import (
    cohort_tracking as data,
)
from education_system.systems.nursery.domain.assessment.cohort_tracking.cohort_tracking import (
    AREAS,
    ROOMS,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e), parent=parent)
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent)
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


# (key, label, kind) — kind: entry | room | area | staff
_FIELDS: list[tuple[str, str, str]] = [
    ("cohort_name",     "Cohort name",                      "entry"),
    ("term",            "Term",                             "entry"),
    ("total_children",  "Total children",                   "entry"),
    ("below_count",     "Below expected count",             "entry"),
    ("on_track_count",  "On-track count",                   "entry"),
    ("above_count",     "Above expected count",             "entry"),
    ("assessment_date", "Assessment date (YYYY-MM-DD)",     "entry"),
    ("notes",           "Notes",                            "entry"),
    ("room",            "Room",                             "room"),
    ("area",            "Area",                             "area"),
    ("staff_id",        "Staff",                            "staff"),
]


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _staff_choices() -> list[tuple[str, str]]:
    try:
        return data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: cohort_tracking open_manager")
    root = _clear(host)
    _header(root, "Cohort Tracking")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Cohort Record",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: open_manager(host)).pack(side="left", padx=2)

    cols = ("id", "cohort_name", "room", "area", "total", "on_track")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id",          "ID",          80),
        ("cohort_name", "Cohort",      200),
        ("room",        "Room",        120),
        ("area",        "Area",        220),
        ("total",       "Total",       70),
        ("on_track",    "On Track",    80),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("Cohort Tracking loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_cohorts()
    except Exception:
        logger.exception("Could not refresh cohort tracking")
        return
    for c in rows:
        tree.insert("", "end", iid=c.cohort_id, values=(
            c.cohort_id,
            c.cohort_name,
            c.room or "-",
            c.area or "-",
            c.total_children if c.total_children is not None else "-",
            c.on_track_count if c.on_track_count is not None else "-",
        ))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Cohort Tracking",
                            f"Select a cohort record to {verb}.",
                            parent=host.root)
        return None
    return sel


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "edit")
    if sel:
        open_edit(host, sel)


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "delete")
    if not sel:
        return
    if not messagebox.askyesno("Delete cohort record",
                               f"Delete cohort record {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_cohort(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete cohort record %s", sel)
        messagebox.showerror("Delete cohort record", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted cohort record {sel}")


def _form_dialog(host, title: str, *,
                 initial: dict[str, Any] | None = None,
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("520x460")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    staff = _staff_choices()
    staff_label_by_id = {sid: lbl for sid, lbl in staff}
    staff_id_by_label = {lbl: sid for sid, lbl in staff}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    for key, label, kind in _FIELDS:
        ttk.Label(frm, text=f"{label}:").grid(
            row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "room":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + list(ROOMS),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "area":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + list(AREAS),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "staff":
            v = tk.StringVar(value=staff_label_by_id.get(str(cur or ""), ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _i, lbl in staff],
                         state="readonly" if staff else "normal",
                         width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            val = (v.get() or "").strip()
            if k == "staff_id":
                out[k] = staff_id_by_label.get(val, val)
            else:
                out[k] = val
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(
        side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_add(host) -> None:
    fields = _form_dialog(host, "Add Cohort Record")
    if not fields:
        host.status_var.set("Add cohort record cancelled")
        open_manager(host)
        return
    try:
        c = data.create_cohort(fields)
    except ValidationError as e:
        messagebox.showerror("Add cohort record", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added cohort record {c.cohort_id}")
    open_manager(host)


@_safe_view
def open_edit(host, cohort_id: str) -> None:
    c = data.get_cohort(cohort_id)
    if c is None:
        messagebox.showerror("Edit cohort record",
                             f"No cohort record with id {cohort_id}",
                             parent=host.root)
        return
    initial = {key: getattr(c, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit cohort record — {c.cohort_name}",
                          initial=initial)
    if not fields:
        return
    try:
        data.update_cohort(cohort_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit cohort record", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated cohort record {cohort_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Cohort Tracking", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Cohort Tracking from the navigation menu.").pack(
        anchor="w")
    return frame
