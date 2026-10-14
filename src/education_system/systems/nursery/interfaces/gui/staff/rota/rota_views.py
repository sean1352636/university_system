"""Tkinter views for Staff Rota (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Lists shifts with a tree + toolbar and a date filter, plus an
add/edit form dialog — the GUI counterpart of ``rota_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.staff.rota import rota as data
from education_system.systems.nursery.domain.staff.rota.rota import (
    STATUSES,
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


_FIELDS: list[tuple[str, str, str]] = [
    ("shift_date", "Shift date (YYYY-MM-DD)", "entry"),
    ("start_time", "Start time (HH:MM)",      "entry"),
    ("end_time",   "End time (HH:MM)",        "entry"),
    ("room",       "Room",                    "room"),
    ("role",       "Role on shift",           "entry"),
    ("status",     "Status",                  "status"),
    ("notes",      "Notes",                   "entry"),
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


def _room_choices() -> list[str]:
    return data.list_room_choices()


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: rota open_manager")
    root = _clear(host)
    _header(root, "Staff Rota")

    date_var = tk.StringVar()

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Shift",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Label(bar, text="Date:").pack(side="left", padx=(12, 2))
    date_cb = ttk.Combobox(bar, textvariable=date_var, width=14,
                           values=[""] + _safe_dates())
    date_cb.pack(side="left")
    ttk.Button(bar, text="Filter",
               command=lambda: _refresh(tree, date_var.get())).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Clear",
               command=lambda: (date_var.set(""), _refresh(tree, ""))).pack(
        side="left", padx=2)

    cols = ("id", "date", "time", "staff", "room", "role", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 70), ("date", "Date", 100), ("time", "Time", 110),
        ("staff", "Staff", 180), ("room", "Room", 120), ("role", "Role", 130),
        ("status", "Status", 90),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, "")
    host.status_var.set("Staff rota loaded")


def _safe_dates() -> list[str]:
    try:
        return data.list_dates()
    except Exception:
        logger.exception("Could not load rota dates")
        return []


def _refresh(tree: ttk.Treeview, shift_date: str) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_shifts(shift_date=shift_date or None)
    except Exception:
        logger.exception("Could not refresh rota")
        try:
            messagebox.showerror("Rota", "Could not load shifts — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for s in rows:
        tree.insert("", "end", iid=s.shift_id, values=(
            s.shift_id, s.shift_date or "-", s.time_span, s.staff_name or "-",
            s.room or "-", s.role or "-", s.status))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Rota", f"Select a shift to {verb}.", parent=host.root)
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
    if not messagebox.askyesno("Delete shift", f"Delete shift {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_shift(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete shift %s", sel)
        messagebox.showerror("Delete shift", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted shift {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 staff_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("450x410")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    rooms = _room_choices()
    vars_: dict[str, tk.Variable] = {}
    row = 0

    sid_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Staff:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = staff_choices or []
        sid_by_label = {lbl: sid for sid, lbl in choices}
        svar = tk.StringVar()
        ttk.Combobox(frm, textvariable=svar, values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__staff_label"] = svar
        row += 1

    for key, label, kind in _FIELDS:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "room":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + rooms, width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "scheduled"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=32).grid(
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
            if k == "__staff_label":
                out["staff_id"] = sid_by_label.get((v.get() or "").strip(), "")
            else:
                out[k] = (v.get() or "").strip()
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_add(host) -> None:
    fields = _form_dialog(host, "Add Shift", staff_choices=_staff_choices())
    if not fields:
        host.status_var.set("Add shift cancelled")
        open_manager(host)
        return
    if not fields.get("staff_id"):
        messagebox.showerror("Add shift", "Please choose a staff member.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        s = data.create_shift(fields)
    except ValidationError as e:
        messagebox.showerror("Add shift", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added shift {s.shift_id}")
    open_manager(host)


@_safe_view
def open_edit(host, shift_id: str) -> None:
    s = data.get_shift(shift_id)
    if s is None:
        messagebox.showerror("Edit shift", f"No shift with id {shift_id}",
                             parent=host.root)
        return
    initial = {key: getattr(s, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit shift — {s.staff_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_shift(shift_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit shift", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated shift {shift_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Staff Rota", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Staff Rota from the navigation menu.").pack(
        anchor="w")
    return frame
