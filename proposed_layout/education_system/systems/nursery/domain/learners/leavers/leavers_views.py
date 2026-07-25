"""Tkinter views for Leavers (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists leavers with a tree + toolbar, an add/edit form dialog and a
reinstate action — the GUI counterpart of ``leavers_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.learners.leavers import leavers as data
from education_system.systems.nursery.domain.learners.leavers.leavers import (
    REASONS,
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
    ("leaving_date",        "Leaving date (YYYY-MM-DD)",     "entry"),
    ("last_day_attended",   "Last day attended (YYYY-MM-DD)", "entry"),
    ("reason",              "Reason",                        "reason"),
    ("destination",        "Destination (school / provider)", "entry"),
    ("records_transferred", "Records transferred",           "check"),
    ("notes",              "Notes",                         "entry"),
]


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _pupil_choices() -> list[tuple[str, str]]:
    try:
        return data.list_active_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: leavers open_manager")
    root = _clear(host)
    _header(root, "Leavers")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Record Leaver",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Reinstate",
               command=lambda: _reinstate_selected(tree, host)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Delete Record",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree)).pack(side="left", padx=2)

    cols = ("id", "child", "left", "reason", "destination", "records")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 180), ("left", "Left on", 100),
        ("reason", "Reason", 170), ("destination", "Destination", 180),
        ("records", "Records sent", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("Leavers loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_leavers()
    except Exception:
        logger.exception("Could not refresh leavers")
        try:
            messagebox.showerror("Leavers", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for lv in rows:
        tree.insert("", "end", iid=lv.leaver_id, values=(
            lv.leaver_id, lv.child_name or "-", lv.leaving_date or "-",
            lv.reason or "-", lv.destination or "-",
            "Yes" if lv.records_transferred else "No"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Leavers", f"Select a leaver to {verb}.",
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
    if not messagebox.askyesno(
            "Delete leaver record",
            f"Delete leaver record {sel}?\n\n"
            "This removes the record only; the child stays off roll.",
            parent=host.root):
        return
    try:
        data.delete_leaver(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete leaver %s", sel)
        messagebox.showerror("Delete leaver", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Deleted leaver record {sel}")


def _reinstate_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "reinstate")
    if not sel:
        return
    lv = data.get_leaver(sel)
    if lv is None:
        return
    if not messagebox.askyesno(
            "Reinstate child",
            f"Put {lv.child_name} back on the active roll and remove the "
            "leaver record?", parent=host.root):
        return
    try:
        data.reinstate(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to reinstate leaver %s", sel)
        messagebox.showerror("Reinstate", f"Could not reinstate:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Reinstated {lv.pupil_id}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("450x380")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    pid_id_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar, values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    for key, label, kind in _FIELDS:
        if kind == "check":
            v = tk.BooleanVar(value=bool(initial.get(key)))
            ttk.Checkbutton(frm, text=label, variable=v).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=2)
            vars_[key] = v
            row += 1
            continue
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "reason":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(REASONS),
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
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
            elif isinstance(v, tk.BooleanVar):
                out[k] = 1 if v.get() else 0
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
    fields = _form_dialog(host, "Record a Leaver", pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Record leaver cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Record leaver", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        lv = data.record_leaver(fields)
    except ValidationError as e:
        messagebox.showerror("Record leaver", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo(
        "Leaver recorded",
        f"{lv.child_name} recorded as a leaver and taken off the active roll.",
        parent=host.root)
    host.status_var.set(f"Recorded leaver {lv.leaver_id}")
    open_manager(host)


@_safe_view
def open_edit(host, leaver_id: str) -> None:
    lv = data.get_leaver(leaver_id)
    if lv is None:
        messagebox.showerror("Edit leaver", f"No leaver with id {leaver_id}",
                             parent=host.root)
        return
    initial = {key: getattr(lv, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit leaver — {lv.child_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_leaver(leaver_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit leaver", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated leaver {leaver_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Leavers", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Leavers from the navigation menu.").pack(anchor="w")
    return frame
