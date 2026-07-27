"""Tkinter views for Photos & Evidence (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Shows the evidence library with a tree + toolbar and an add/edit
form dialog — the GUI counterpart of ``evidence_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.assessment.evidence import (
    evidence as data,
)
from education_system.systems.nursery.domain.assessment.evidence.evidence import (
    AREAS,
    EVIDENCE_TYPES,
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


# (key, label, kind) — kind one of entry/type/area/bool/staff
_FIELDS: list[tuple[str, str, str]] = [
    ("title",               "Title",                    "entry"),
    ("capture_date",        "Capture date (YYYY-MM-DD)", "entry"),
    ("file_ref",            "File ref",                 "entry"),
    ("description",         "Description",              "entry"),
    ("evidence_type",       "Evidence type",            "type"),
    ("area",                "EYFS area",                "area"),
    ("shared_with_parent",  "Shared with parent",       "bool"),
    ("staff_id",            "Staff",                    "staff"),
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
    logger.debug("GUI: evidence open_manager")
    root = _clear(host)
    _header(root, "Photos & Evidence")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Evidence",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: open_manager(host)).pack(side="left", padx=2)

    cols = ("id", "child", "date", "type", "area", "title", "shared")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=16)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 160), ("date", "Date", 100),
        ("type", "Type", 110), ("area", "EYFS Area", 210),
        ("title", "Title", 180), ("shared", "Shared", 60),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("Photos & Evidence loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_evidence()
    except Exception:
        logger.exception("Could not refresh evidence")
        return
    for ev in rows:
        tree.insert("", "end", iid=ev.evidence_id, values=(
            ev.evidence_id, ev.child_name or "-", ev.capture_date or "-",
            ev.evidence_type or "-", ev.area or "-", ev.title,
            "Yes" if ev.shared_with_parent else ""))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Photos & Evidence", f"Select an evidence record to {verb}.",
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
    if not messagebox.askyesno("Delete evidence", f"Delete evidence record {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_evidence(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete evidence %s", sel)
        messagebox.showerror("Delete evidence", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted evidence {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("480x480")
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
                     state="readonly" if choices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    for key, label, kind in _FIELDS:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "type":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(EVIDENCE_TYPES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "area":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(AREAS),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "bool":
            v = tk.BooleanVar(value=bool(cur))
            ttk.Checkbutton(frm, variable=v).grid(
                row=row, column=1, sticky="w", pady=2)
        elif kind == "staff":
            v = tk.StringVar(value=staff_label_by_id.get(str(cur or ""), ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _i, lbl in staff],
                         state="readonly" if staff else "normal", width=32).grid(
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
    fields = _form_dialog(host, "Add Evidence", pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add evidence cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add evidence", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        ev = data.create_evidence(fields)
    except ValidationError as e:
        messagebox.showerror("Add evidence", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added evidence {ev.evidence_id}")
    open_manager(host)


@_safe_view
def open_edit(host, evidence_id: str) -> None:
    ev = data.get_evidence(evidence_id)
    if ev is None:
        messagebox.showerror("Edit evidence", f"No evidence with id {evidence_id}",
                             parent=host.root)
        return
    initial = {key: getattr(ev, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit evidence — {ev.title}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_evidence(evidence_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit evidence", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated evidence {evidence_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Photos & Evidence", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Photos & Evidence from the navigation menu.").pack(
        anchor="w")
    return frame
