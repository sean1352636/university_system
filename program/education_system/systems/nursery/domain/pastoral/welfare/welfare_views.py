"""Tkinter views for Welfare Requirements (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``); the GUI counterpart of ``welfare_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.pastoral.welfare import welfare as data
from education_system.systems.nursery.domain.pastoral.welfare.welfare import ValidationError

logger = logging.getLogger(__name__)


def _cell(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return str(v)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            try:
                messagebox.showerror(func.__name__, str(e), parent=parent)
            except Exception:
                logger.debug("dialog", exc_info=True)
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror("Error", f"An unexpected error occurred:\n\n{e}\n\nSee logs.", parent=parent)
            except Exception:
                logger.debug("dialog", exc_info=True)
    return wrapper


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


@_safe_view
def open_manager(host) -> None:
    root = _clear(host)
    ttk.Label(root, text="Welfare Requirements", font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))
    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add", command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit", command=lambda: _edit_sel(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete", command=lambda: _del_sel(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh", command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ('record_id', 'area', 'status', 'responsible_name', 'next_review',)
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("record_id", "ID", 70),
        ("area", "Area", 200),
        ("status", "Status", 100),
        ("responsible_name", "Responsible", 160),
        ("next_review", "Next review", 120),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_sel(tree, host))

    _refresh(tree, summary)
    host.status_var.set("Welfare Requirements loaded")


def _refresh(tree, summary) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_records()
        s = data.summary()
    except Exception:
        logger.exception("refresh failed")
        return
    for rec in rows:
        tree.insert("", "end", iid=rec.record_id, values=(_cell(getattr(rec, 'record_id', None)), _cell(getattr(rec, 'area', None)), _cell(getattr(rec, 'status', None)), _cell(getattr(rec, 'responsible_name', None)), _cell(getattr(rec, 'next_review', None)),))
    summary.config(text=f"Records: {s['total']}    Open: {s['open']}")


def _sel(tree, host, verb):
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Welfare Requirements", f"Select a record to {verb}.", parent=host.root)
        return None
    return sel


def _edit_sel(tree, host) -> None:
    sel = _sel(tree, host, "edit")
    if sel:
        open_edit(host, sel)


def _del_sel(tree, host) -> None:
    sel = _sel(tree, host, "delete")
    if not sel:
        return
    if not messagebox.askyesno("Delete", f"Delete {sel}?", parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Delete", f"Could not delete:\n\n{e}", parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted {sel}")


def _form_dialog(host, title, *, initial=None):
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("480x560")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab", exc_info=True)
    outer = ttk.Frame(dlg, padding=12)
    outer.pack(fill="both", expand=True)
    frm = ttk.Frame(outer)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    children = []
    child_label_by_id = {}
    child_id_by_label = {}
    staff_ch = data.list_staff_choices()
    staff_label_by_id = {sid: l for sid, l in staff_ch}
    staff_id_by_label = {l: sid for sid, l in staff_ch}
    vars_: dict = {}
    row = 0

    ttk.Label(frm, text="Area:").grid(row=row, column=0, sticky="nw", pady=2)
    cur = initial.get("area")
    v = tk.StringVar(value=str(cur or ""))
    ttk.Combobox(frm, textvariable=v, values=[""] + list(data.AREAS), state="readonly", width=32).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["area"] = v
    row += 1
    ttk.Label(frm, text="Requirement:").grid(row=row, column=0, sticky="nw", pady=2)
    cur = initial.get("requirement")
    v = tk.StringVar(value="" if cur is None else str(cur))
    ttk.Entry(frm, textvariable=v, width=34).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["requirement"] = v
    row += 1
    ttk.Label(frm, text="Status:").grid(row=row, column=0, sticky="nw", pady=2)
    cur = initial.get("status")
    v = tk.StringVar(value=str(cur or "review"))
    ttk.Combobox(frm, textvariable=v, values=list(data.STATUSES), state="readonly", width=32).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["status"] = v
    row += 1
    ttk.Label(frm, text="Responsible:").grid(row=row, column=0, sticky="nw", pady=2)
    cur = initial.get("responsible")
    v = tk.StringVar(value=staff_label_by_id.get(str(cur or ""), ""))
    ttk.Combobox(frm, textvariable=v, values=[""] + [l for _i, l in staff_ch], width=32).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["responsible"] = v
    row += 1
    ttk.Label(frm, text="Last reviewed (YYYY-MM-DD):").grid(row=row, column=0, sticky="nw", pady=2)
    cur = initial.get("last_reviewed")
    v = tk.StringVar(value="" if cur is None else str(cur))
    ttk.Entry(frm, textvariable=v, width=34).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["last_reviewed"] = v
    row += 1
    ttk.Label(frm, text="Next review (YYYY-MM-DD):").grid(row=row, column=0, sticky="nw", pady=2)
    cur = initial.get("next_review")
    v = tk.StringVar(value="" if cur is None else str(cur))
    ttk.Entry(frm, textvariable=v, width=34).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["next_review"] = v
    row += 1
    ttk.Label(frm, text="Evidence:").grid(row=row, column=0, sticky="nw", pady=2)
    cur = initial.get("evidence")
    v = tk.StringVar(value="" if cur is None else str(cur))
    ttk.Entry(frm, textvariable=v, width=34).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["evidence"] = v
    row += 1
    ttk.Label(frm, text="Notes:").grid(row=row, column=0, sticky="nw", pady=2)
    cur = initial.get("notes")
    v = tk.StringVar(value="" if cur is None else str(cur))
    ttk.Entry(frm, textvariable=v, width=34).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["notes"] = v
    row += 1
    frm.columnconfigure(1, weight=1)

    result = None

    def _save():
        nonlocal result
        out: dict = {}
        for k, v in vars_.items():
            if isinstance(v, tk.BooleanVar):
                out[k] = 1 if v.get() else 0
                continue
            val = (v.get() or "").strip()
            if k == "responsible":
                out[k] = staff_id_by_label.get(val, val)
                continue
            out[k] = val
        result = out
        dlg.destroy()

    btns = ttk.Frame(outer)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_add(host) -> None:
    fields = _form_dialog(host, "Add requirement")
    if not fields:
        open_manager(host)
        return
    try:
        rec = data.create_record(fields)
    except ValidationError as e:
        messagebox.showerror("Add", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added {rec.record_id}")
    open_manager(host)


@_safe_view
def open_edit(host, record_id) -> None:
    rec = data.get_record(record_id)
    if rec is None:
        messagebox.showerror("Edit", f"No record with id {record_id}", parent=host.root)
        return
    initial = {f: getattr(rec, f) for f in rec.__dataclass_fields__}
    fields = _form_dialog(host, f"Edit {record_id}", initial=initial)
    if not fields:
        return
    try:
        data.update_record(record_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated {record_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Welfare Requirements", font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Welfare Requirements from the navigation menu.").pack(anchor="w")
    return frame
