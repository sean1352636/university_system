"""Tkinter views for the Nappy / Toileting Log (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists toileting records with a tree + toolbar and an add/edit form
dialog — the GUI counterpart of ``toileting_log_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.nursery_system.modules.domain.toileting_log import (
    toileting_log as data,
)
from education_system.nursery_system.modules.domain.toileting_log.toileting_log import (
    TYPES,
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
    logger.debug("GUI: toileting_log open_manager")
    root = _clear(host)
    _header(root, "Nappy / Toileting Log")

    date_var = tk.StringVar()

    filt = ttk.Frame(root)
    filt.pack(fill="x", pady=(0, 6))
    ttk.Label(filt, text="Date (YYYY-MM-DD):").pack(side="left", padx=(0, 4))
    ttk.Entry(filt, textvariable=date_var, width=14).pack(side="left")
    ttk.Button(filt, text="Load",
               command=lambda: _refresh(tree, date_var.get())).pack(
        side="left", padx=4)
    ttk.Button(filt, text="Clear",
               command=lambda: (date_var.set(""), _refresh(tree, ""))).pack(
        side="left")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Record",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, date_var.get())).pack(
        side="left", padx=2)

    cols = ("id", "date", "time", "child", "type", "cream", "staff")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=17)
    for c, label, w in [
        ("id", "ID", 70), ("date", "Date", 95), ("time", "Time", 60),
        ("child", "Child", 180), ("type", "Type", 130),
        ("cream", "Cream", 60), ("staff", "Staff", 150),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, "")
    host.status_var.set("Toileting log loaded")


def _refresh(tree: ttk.Treeview, log_date: str) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_records(log_date=(log_date or "").strip() or None)
    except Exception:
        logger.exception("Could not refresh toileting log")
        try:
            messagebox.showerror("Toileting log", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        cream = "Yes" if r.cream_applied else "No"
        tree.insert("", "end", iid=r.record_id, values=(
            r.record_id, r.log_date, r.log_time or "-", r.child_name or "-",
            r.type, cream, r.staff_name or "-"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Toileting log", f"Select a record to {verb}.",
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
    r = data.get_record(sel)
    if r is None:
        return
    if not messagebox.askyesno(
            "Delete record",
            f"Delete toileting-log record {sel} for {r.child_name}?",
            parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete toileting-log %s", sel)
        messagebox.showerror("Delete record", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted toileting-log record {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None,
                 staff_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("470x430")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    # Child picker only when adding a new record.
    pid_id_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar,
                     values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    ttk.Label(frm, text="Date (YYYY-MM-DD):").grid(
        row=row, column=0, sticky="nw", pady=2)
    dvar = tk.StringVar(value=str(initial.get("log_date") or ""))
    ttk.Entry(frm, textvariable=dvar, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["log_date"] = dvar
    row += 1

    ttk.Label(frm, text="Time (HH:MM):").grid(
        row=row, column=0, sticky="nw", pady=2)
    tvar = tk.StringVar(value=str(initial.get("log_time") or ""))
    ttk.Entry(frm, textvariable=tvar, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["log_time"] = tvar
    row += 1

    ttk.Label(frm, text="Type:").grid(row=row, column=0, sticky="nw", pady=2)
    typevar = tk.StringVar(value=str(initial.get("type") or TYPES[0]))
    ttk.Combobox(frm, textvariable=typevar, values=list(TYPES),
                 state="readonly", width=32).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["type"] = typevar
    row += 1

    creamvar = tk.BooleanVar(value=bool(initial.get("cream_applied")))
    ttk.Checkbutton(frm, text="Barrier cream applied", variable=creamvar).grid(
        row=row, column=0, columnspan=2, sticky="w", pady=2)
    vars_["cream_applied"] = creamvar
    row += 1

    ttk.Label(frm, text="Staff:").grid(row=row, column=0, sticky="nw", pady=2)
    schoices = staff_choices or []
    sid_by_label = {lbl: sid for sid, lbl in schoices}
    label_by_sid = {sid: lbl for sid, lbl in schoices}
    svar = tk.StringVar(value=label_by_sid.get(initial.get("staff_id"), ""))
    ttk.Combobox(frm, textvariable=svar,
                 values=[""] + [lbl for _i, lbl in schoices],
                 state="readonly" if schoices else "normal", width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["__staff_label"] = svar
    row += 1

    ttk.Label(frm, text="Notes:").grid(row=row, column=0, sticky="nw", pady=2)
    nvar = tk.StringVar(value=str(initial.get("notes") or ""))
    ttk.Entry(frm, textvariable=nvar, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["notes"] = nvar
    row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
            elif k == "__staff_label":
                out["staff_id"] = sid_by_label.get((v.get() or "").strip(), "")
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
    logger.debug("GUI: toileting_log open_add")
    fields = _form_dialog(host, "Add Toileting-Log Record",
                          pupil_choices=_pupil_choices(),
                          staff_choices=_staff_choices())
    if not fields:
        host.status_var.set("Add toileting-log cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add record", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        r = data.create_record(fields)
    except ValidationError as e:
        messagebox.showerror("Add record", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo(
        "Record added",
        f"{r.child_name} — {r.type}\n{r.log_date} {r.log_time or ''}".strip(),
        parent=host.root)
    host.status_var.set(f"Added toileting-log {r.record_id}")
    open_manager(host)


@_safe_view
def open_edit(host, record_id: str) -> None:
    logger.debug("GUI: toileting_log open_edit(%s)", record_id)
    r = data.get_record(record_id)
    if r is None:
        messagebox.showerror("Edit record", f"No record with id {record_id}",
                             parent=host.root)
        return
    initial = {
        "log_date": r.log_date, "log_time": r.log_time, "type": r.type,
        "cream_applied": r.cream_applied, "staff_id": r.staff_id, "notes": r.notes,
    }
    fields = _form_dialog(host, f"Edit {r.child_name} — toileting log",
                          initial=initial, is_edit=True,
                          staff_choices=_staff_choices())
    if not fields:
        return
    try:
        data.update_record(record_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit record", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated toileting-log {record_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Nappy / Toileting Log",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open the Nappy / Toileting Log from the navigation menu."
              ).pack(anchor="w")
    return frame
