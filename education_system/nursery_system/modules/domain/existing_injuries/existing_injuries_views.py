"""Tkinter views for the Existing Injuries Log (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists existing-injury records with a tree + toolbar and an add/edit
form dialog — the GUI counterpart of ``existing_injuries_cli.py``.
"""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.nursery_system.modules.domain.existing_injuries import (
    existing_injuries as data,
)
from education_system.nursery_system.modules.domain.existing_injuries.existing_injuries import (
    FEATURE_NAME,
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
    logger.debug("GUI: existing_injuries open_manager")
    root = _clear(host)
    _header(root, FEATURE_NAME)

    date_var = tk.StringVar()

    filt = ttk.Frame(root)
    filt.pack(fill="x", pady=(0, 6))
    ttk.Label(filt, text="Observed date (YYYY-MM-DD):").pack(side="left", padx=(0, 4))
    ttk.Entry(filt, textvariable=date_var, width=14).pack(side="left", padx=2)
    ttk.Button(filt, text="Load",
               command=lambda: _refresh(tree, date_var.get())).pack(side="left", padx=2)
    ttk.Button(filt, text="Clear",
               command=lambda: (date_var.set(""), _refresh(tree, ""))).pack(
        side="left", padx=2)

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

    cols = ("date", "child", "body", "description", "informed", "signed")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=17)
    for c, label, w in [
        ("date", "Date", 100), ("child", "Child", 180), ("body", "Body part", 130),
        ("description", "Description", 230), ("informed", "Parent informed", 110),
        ("signed", "Signed", 80),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("unsigned", background="#fde9c8")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, date_var.get())
    host.status_var.set("Existing injuries loaded")


def _refresh(tree: ttk.Treeview, observed_date: str) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_records(observed_date=(observed_date or "").strip() or None)
    except Exception:
        logger.exception("Could not refresh existing injuries")
        try:
            messagebox.showerror("Existing injuries", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        tags = () if r.parent_signed else ("unsigned",)
        tree.insert("", "end", iid=r.record_id, tags=tags, values=(
            r.observed_date, r.child_name or "-", r.body_part or "-",
            r.description or "-",
            "Yes" if r.parent_informed else "No",
            "Yes" if r.parent_signed else "No"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Existing injuries", f"Select a record to {verb}.",
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
            f"Delete existing-injury record {sel} for {r.child_name}?",
            parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete existing-injury %s", sel)
        messagebox.showerror("Delete record", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted existing-injury record {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None,
                 staff_choices: list[tuple[str, str]] | None = None
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
    vars_: dict[str, tk.Variable] = {}
    text_widgets: dict[str, tk.Text] = {}
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
                     state="readonly" if choices else "normal", width=36).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    def _entry(key: str, label: str, default: str = "") -> None:
        nonlocal row
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        v = tk.StringVar(value=default if cur is None else str(cur))
        ttk.Entry(frm, textvariable=v, width=36).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1

    def _text(key: str, label: str) -> None:
        nonlocal row
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        txt = tk.Text(frm, width=36, height=3, wrap="word")
        cur = initial.get(key)
        if cur:
            txt.insert("1.0", str(cur))
        txt.grid(row=row, column=1, sticky="ew", pady=2)
        text_widgets[key] = txt
        row += 1

    today = _dt.date.today().isoformat()
    _entry("observed_date", "Observed date (YYYY-MM-DD)",
           default=today if not is_edit else "")
    _entry("observed_time", "Observed time (HH:MM)")
    _entry("body_part", "Body part")
    _text("description", "Description")
    _text("explanation", "Parent's explanation")

    # Staff picker.
    ttk.Label(frm, text="Observed by:").grid(row=row, column=0, sticky="nw", pady=2)
    schoices = staff_choices or []
    sid_by_label = {lbl: sid for sid, lbl in schoices}
    label_by_sid = {sid: lbl for sid, lbl in schoices}
    svar = tk.StringVar(value=label_by_sid.get(initial.get("observed_by") or "", ""))
    ttk.Combobox(frm, textvariable=svar, values=[""] + [lbl for _i, lbl in schoices],
                 state="readonly" if schoices else "normal", width=36).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["__staff_label"] = svar
    row += 1

    informed = tk.BooleanVar(
        value=bool(initial.get("parent_informed", 1)) if is_edit else True)
    ttk.Checkbutton(frm, text="Parent informed", variable=informed).grid(
        row=row, column=0, columnspan=2, sticky="w", pady=2)
    vars_["parent_informed"] = informed
    row += 1

    signed = tk.BooleanVar(value=bool(initial.get("parent_signed", 0)))
    ttk.Checkbutton(frm, text="Parent signed", variable=signed).grid(
        row=row, column=0, columnspan=2, sticky="w", pady=2)
    vars_["parent_signed"] = signed
    row += 1

    _entry("notes", "Notes")
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
            elif k == "__staff_label":
                out["observed_by"] = sid_by_label.get((v.get() or "").strip(), "")
            elif isinstance(v, tk.BooleanVar):
                out[k] = 1 if v.get() else 0
            else:
                out[k] = (v.get() or "").strip()
        for k, txt in text_widgets.items():
            out[k] = txt.get("1.0", "end").strip()
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
    logger.debug("GUI: existing_injuries open_add")
    fields = _form_dialog(host, "Add Existing-Injury Record",
                          pupil_choices=_pupil_choices(),
                          staff_choices=_staff_choices())
    if not fields:
        host.status_var.set("Add existing-injury cancelled")
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
        f"{r.child_name} — {r.body_part or 'injury'} ({r.observed_date})",
        parent=host.root)
    host.status_var.set(f"Added existing-injury {r.record_id}")
    open_manager(host)


@_safe_view
def open_edit(host, record_id: str) -> None:
    logger.debug("GUI: existing_injuries open_edit(%s)", record_id)
    r = data.get_record(record_id)
    if r is None:
        messagebox.showerror("Edit record", f"No record with id {record_id}",
                             parent=host.root)
        return
    initial = {
        "observed_date": r.observed_date, "observed_time": r.observed_time,
        "body_part": r.body_part, "description": r.description,
        "explanation": r.explanation, "observed_by": r.observed_by,
        "parent_informed": r.parent_informed, "parent_signed": r.parent_signed,
        "notes": r.notes,
    }
    fields = _form_dialog(host, f"Edit {r.child_name} — existing injury",
                          initial=initial, is_edit=True,
                          staff_choices=_staff_choices())
    if not fields:
        return
    try:
        data.update_record(record_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit record", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated existing-injury {record_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text=FEATURE_NAME,
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open the Existing Injuries Log from the navigation menu."
              ).pack(anchor="w")
    return frame
