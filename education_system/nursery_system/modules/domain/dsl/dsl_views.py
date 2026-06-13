"""Tkinter views for Designated Safeguarding Lead (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists the DSL register with a tree + toolbar and an add/edit form
dialog — the GUI counterpart of ``dsl_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.nursery_system.modules.domain.dsl import dsl as data
from education_system.nursery_system.modules.domain.dsl.dsl import (
    DSL_ROLES,
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


_TAG_COLOURS = {"expired": "#c0392b", "expiring": "#b9770e", "valid": "#1e7e34",
                "unknown": "#555555"}


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _staff_choices() -> list[tuple[str, str]]:
    try:
        return data.list_staff_choices()
    except Exception:
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: dsl open_manager")
    root = _clear(host)
    ttk.Label(root, text="Designated Safeguarding Lead",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add DSL",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ("id", "staff", "role", "lead", "expiry", "state", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 70), ("staff", "Staff", 200), ("role", "Role", 120),
        ("lead", "Lead", 60), ("expiry", "Training expiry", 130),
        ("state", "Training", 90), ("status", "Status", 80),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    for st, colour in _TAG_COLOURS.items():
        tree.tag_configure(st, foreground=colour)
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary)
    host.status_var.set("DSL register loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_records()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh DSL register")
        return
    for d in rows:
        tree.insert("", "end", iid=d.record_id, tags=(d.training_status,), values=(
            d.record_id, d.staff_name or "-", d.dsl_role or "-",
            "Yes" if d.is_lead else "-", d.training_expiry or "-",
            d.training_status, d.status))
    summary.config(text=f"Active DSLs: {s['total']}    Leads: {s['leads']}    "
                        f"Deputies: {s['deputies']}    Training due: {s['training_due']}",
                   foreground="#a00" if s["training_due"] else "#555")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("DSL", f"Select a record to {verb}.", parent=host.root)
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
    if not messagebox.askyesno("Delete DSL", f"Delete DSL record {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete DSL %s", sel)
        messagebox.showerror("Delete DSL", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted DSL record {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("440x340")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    staff = _staff_choices()
    sid_by_label = {lbl: sid for sid, lbl in staff}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    if not is_edit:
        ttk.Label(frm, text="Staff:").grid(row=row, column=0, sticky="nw", pady=2)
        svar = tk.StringVar()
        ttk.Combobox(frm, textvariable=svar, values=[lbl for _i, lbl in staff],
                     state="readonly" if staff else "normal", width=32).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__staff_label"] = svar
        row += 1

    spec = [
        ("dsl_role", "Role", "role"),
        ("is_lead", "Lead DSL", "check"),
        ("training_date", "Training date (YYYY-MM-DD)", "entry"),
        ("training_expiry", "Training expiry (YYYY-MM-DD)", "entry"),
        ("contact_number", "Contact number", "entry"),
        ("status", "Status", "status"),
        ("notes", "Notes", "entry"),
    ]
    for key, label, kind in spec:
        if kind == "check":
            v = tk.BooleanVar(value=bool(initial.get(key)))
            ttk.Checkbutton(frm, text=label, variable=v).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=2)
            vars_[key] = v
            row += 1
            continue
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "role":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(DSL_ROLES),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "active"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if isinstance(v, tk.BooleanVar):
                out[k] = 1 if v.get() else 0
            elif k == "__staff_label":
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
    fields = _form_dialog(host, "Add DSL")
    if not fields:
        host.status_var.set("Add DSL cancelled")
        open_manager(host)
        return
    if not fields.get("staff_id"):
        messagebox.showerror("Add DSL", "Please choose a staff member.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        d = data.create_record(fields)
    except ValidationError as e:
        messagebox.showerror("Add DSL", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Registered DSL {d.record_id}")
    open_manager(host)


@_safe_view
def open_edit(host, record_id: str) -> None:
    d = data.get_record(record_id)
    if d is None:
        messagebox.showerror("Edit DSL", f"No record with id {record_id}",
                             parent=host.root)
        return
    initial = {"dsl_role": d.dsl_role, "is_lead": d.is_lead,
               "training_date": d.training_date, "training_expiry": d.training_expiry,
               "contact_number": d.contact_number, "status": d.status,
               "notes": d.notes}
    fields = _form_dialog(host, f"Edit DSL — {d.staff_name}", initial=initial,
                          is_edit=True)
    if not fields:
        return
    try:
        data.update_record(record_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit DSL", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated DSL record {record_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Designated Safeguarding Lead",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Designated Safeguarding Lead from the navigation menu."
              ).pack(anchor="w")
    return frame
