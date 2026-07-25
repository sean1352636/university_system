"""Tkinter views for Paediatric First Aid (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists PFA certificates with a validity-coloured tree + toolbar and an
add/edit form dialog — the GUI counterpart of ``first_aid_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.pastoral.health.first_aid import first_aid as data
from education_system.systems.nursery.domain.pastoral.health.first_aid.first_aid import (
    CERTIFICATE_TYPES,
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
    ("certificate_type", "Certificate type",         "type"),
    ("awarding_body",    "Awarding body",            "entry"),
    ("issue_date",       "Issue date (YYYY-MM-DD)",  "entry"),
    ("expiry_date",      "Expiry date (YYYY-MM-DD)", "entry"),
    ("certificate_ref",  "Certificate reference",    "entry"),
    ("notes",            "Notes",                    "entry"),
]

_TAG_COLOURS = {
    "expired": "#c0392b",
    "expiring": "#b9770e",
    "valid": "#1e7e34",
    "unknown": "#555555",
}


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
    logger.debug("GUI: first_aid open_manager")
    root = _clear(host)
    _header(root, "Paediatric First Aid")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Certificate",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ("id", "staff", "type", "issued", "expiry", "validity")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 70), ("staff", "Staff", 190), ("type", "Type", 180),
        ("issued", "Issued", 100), ("expiry", "Expiry", 100),
        ("validity", "Validity", 90),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    for state, colour in _TAG_COLOURS.items():
        tree.tag_configure(state, foreground=colour)
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary)
    host.status_var.set("Paediatric first aid loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_certificates()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh PFA certificates")
        try:
            messagebox.showerror("Paediatric first aid", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for c in rows:
        tree.insert("", "end", iid=c.record_id, tags=(c.validity,), values=(
            c.record_id, c.staff_name or "-", c.certificate_type or "-",
            c.issue_date or "-", c.expiry_date or "-", c.validity))
    summary.config(
        text=f"Certificates: {s['total']}   Valid: {s['valid']}   "
             f"Expiring: {s['expiring']}   Expired: {s['expired']}   "
             f"Staff covered: {s['staff_covered']}",
        foreground="#a00" if s["expired"] else "#555")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Paediatric first aid",
                            f"Select a certificate to {verb}.", parent=host.root)
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
    if not messagebox.askyesno("Delete certificate", f"Delete certificate {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_certificate(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete PFA %s", sel)
        messagebox.showerror("Delete certificate", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted certificate {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 staff_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x400")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
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
        if kind == "type":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(CERTIFICATE_TYPES),
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
    fields = _form_dialog(host, "Add PFA Certificate",
                          staff_choices=_staff_choices())
    if not fields:
        host.status_var.set("Add certificate cancelled")
        open_manager(host)
        return
    if not fields.get("staff_id"):
        messagebox.showerror("Add certificate", "Please choose a staff member.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        c = data.create_certificate(fields)
    except ValidationError as e:
        messagebox.showerror("Add certificate", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added PFA certificate {c.record_id}")
    open_manager(host)


@_safe_view
def open_edit(host, record_id: str) -> None:
    c = data.get_certificate(record_id)
    if c is None:
        messagebox.showerror("Edit certificate", f"No certificate with id {record_id}",
                             parent=host.root)
        return
    initial = {key: getattr(c, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit PFA — {c.staff_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_certificate(record_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit certificate", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated PFA certificate {record_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Paediatric First Aid",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Paediatric First Aid from the navigation menu."
              ).pack(anchor="w")
    return frame
