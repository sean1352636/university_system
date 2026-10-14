"""Tkinter views for 2-Year-Old Progress Check (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Shows the progress check list with a tree + toolbar and an add/edit
form dialog — the GUI counterpart of ``progress_check_2yr_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.assessment.progress_check_2yr import (
    progress_check_2yr as data,
)
from education_system.systems.nursery.domain.assessment.progress_check_2yr.progress_check_2yr import (
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


# (key, label, kind) — kind one of entry/status/bool/staff
_FIELDS: list[tuple[str, str, str]] = [
    ("check_date",           "Check date (YYYY-MM-DD)",              "entry"),
    ("age_months",           "Age (months)",                         "entry"),
    ("comm_language",        "Communication & language",             "entry"),
    ("physical_development", "Physical development",                 "entry"),
    ("pse_development",      "Personal-social-emotional development", "entry"),
    ("summary",              "Summary",                              "entry"),
    ("strengths",            "Strengths",                            "entry"),
    ("areas_of_concern",     "Areas of concern",                     "entry"),
    ("status",               "Status",                               "status"),
    ("shared_with_parents",  "Shared with parents",                  "bool"),
    ("shared_with_hv",       "Shared with health visitor",           "bool"),
    ("staff_id",             "Staff",                                "staff"),
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
        return data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return []


def _staff_choices() -> list[tuple[str, str]]:
    try:
        return data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: progress_check_2yr open_manager")
    root = _clear(host)
    _header(root, "2-Year-Old Progress Check")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Check",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: open_manager(host)).pack(side="left", padx=2)

    cols = ("id", "child", "date", "age_months", "status", "shared")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=16)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 180), ("date", "Date", 100),
        ("age_months", "Age (mo)", 80), ("status", "Status", 100),
        ("shared", "Shared (P/HV)", 110),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("2-Year-Old Progress Checks loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_checks()
    except Exception:
        logger.exception("Could not refresh progress checks")
        return
    for c in rows:
        p_flag = "Y" if c.shared_with_parents else "N"
        hv_flag = "Y" if c.shared_with_hv else "N"
        tree.insert("", "end", iid=c.check_id, values=(
            c.check_id, c.child_name or "-", c.check_date or "-",
            c.age_months if c.age_months is not None else "-",
            c.status or "-",
            f"{p_flag}/{hv_flag}"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("2-Year-Old Progress Check",
                            f"Select a check to {verb}.", parent=host.root)
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
    if not messagebox.askyesno("Delete check", f"Delete progress check {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_check(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete progress check %s", sel)
        messagebox.showerror("Delete check", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted progress check {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("500x560")
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

    pid_id_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar, values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=36).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    for key, label, kind in _FIELDS:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "status":
            v = tk.StringVar(value=str(cur or "draft"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "bool":
            v = tk.BooleanVar(value=bool(cur))
            ttk.Checkbutton(frm, variable=v).grid(
                row=row, column=1, sticky="w", pady=2)
        elif kind == "staff":
            v = tk.StringVar(value=staff_label_by_id.get(str(cur or ""), ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _i, lbl in staff],
                         state="readonly" if staff else "normal", width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=36).grid(
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
                out[k] = bool(v.get())
            elif k == "staff_id":
                val = (v.get() or "").strip()
                out[k] = staff_id_by_label.get(val, val)
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
    fields = _form_dialog(host, "Add 2-Year-Old Progress Check",
                          pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add progress check cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add progress check", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        c = data.create_check(fields)
    except ValidationError as e:
        messagebox.showerror("Add progress check", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added progress check {c.check_id}")
    open_manager(host)


@_safe_view
def open_edit(host, check_id: str) -> None:
    c = data.get_check(check_id)
    if c is None:
        messagebox.showerror("Edit progress check", f"No check with id {check_id}",
                             parent=host.root)
        return
    initial = {key: getattr(c, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit progress check — {c.child_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_check(check_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit progress check", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated progress check {check_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="2-Year-Old Progress Check", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open 2-Year-Old Progress Check from the navigation menu.").pack(
        anchor="w")
    return frame
