"""Tkinter views for Sibling Discounts (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists discount arrangements with a tree + toolbar and an add/edit
form dialog — the GUI counterpart of ``discounts_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.nursery_system.modules.domain.discounts import discounts as data
from education_system.nursery_system.modules.domain.discounts.discounts import (
    DISCOUNT_TYPES,
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
    ("discount_type", "Type",                          "type"),
    ("percentage",    "Percentage (blank if fixed)",   "entry"),
    ("fixed_amount",  "Fixed amount £ (blank if %)",   "entry"),
    ("reason",        "Reason",                        "entry"),
    ("start_date",    "Start date (YYYY-MM-DD)",       "entry"),
    ("end_date",      "End date (blank = ongoing)",    "entry"),
    ("status",        "Status",                        "status"),
    ("notes",         "Notes",                         "entry"),
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


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: discounts open_manager")
    root = _clear(host)
    _header(root, "Sibling Discounts")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Discount",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ("id", "child", "type", "value", "reason", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w, anc in [
        ("id", "ID", 80, "w"), ("child", "Child", 170, "w"),
        ("type", "Type", 130, "w"), ("value", "Value", 90, "w"),
        ("reason", "Reason", 200, "w"), ("status", "Status", 80, "w"),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor=anc)
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary)
    host.status_var.set("Discounts loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_discounts()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh discounts")
        try:
            messagebox.showerror("Discounts", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for d in rows:
        tree.insert("", "end", iid=d.discount_id, values=(
            d.discount_id, d.child_name or "-", d.discount_type or "-",
            d.value_label, d.reason or "-", d.status))
    by_type = "  ".join(f"{k}={v}" for k, v in sorted(s["by_type"].items()))
    summary.config(text=f"Discounts: {s['count']}    Active: {s['active']}"
                        + (f"    ·    {by_type}" if by_type else ""))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Discounts", f"Select a discount to {verb}.",
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
    if not messagebox.askyesno("Delete discount", f"Delete discount {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_discount(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete discount %s", sel)
        messagebox.showerror("Delete discount", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted discount {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x420")
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
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "type":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(DISCOUNT_TYPES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "active"))
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
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
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
    fields = _form_dialog(host, "Add Discount", pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add discount cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add discount", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        d = data.create_discount(fields)
    except ValidationError as e:
        messagebox.showerror("Add discount", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added discount {d.discount_id}")
    open_manager(host)


@_safe_view
def open_edit(host, discount_id: str) -> None:
    d = data.get_discount(discount_id)
    if d is None:
        messagebox.showerror("Edit discount", f"No discount with id {discount_id}",
                             parent=host.root)
        return
    initial = {key: getattr(d, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit discount — {d.child_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_discount(discount_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit discount", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated discount {discount_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Sibling Discounts", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Sibling Discounts from the navigation menu.").pack(
        anchor="w")
    return frame
