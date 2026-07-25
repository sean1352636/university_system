"""Tkinter views for Tax-Free Childcare / Vouchers (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists voucher / Tax-Free Childcare arrangements with a tree + toolbar
and an add/edit form dialog — the GUI counterpart of
``childcare_vouchers_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.finance.childcare_vouchers import (
    childcare_vouchers as data,
)
from education_system.systems.nursery.domain.finance.childcare_vouchers.childcare_vouchers import (
    SCHEMES,
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
    ("scheme",          "Scheme",                     "scheme"),
    ("provider",        "Provider (employer / NS&I)", "entry"),
    ("account_ref",     "Account reference",          "entry"),
    ("expected_amount", "Expected amount / month (£)", "entry"),
    ("status",          "Status",                     "status"),
    ("notes",           "Notes",                      "entry"),
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
    logger.debug("GUI: vouchers open_manager")
    root = _clear(host)
    _header(root, "Tax-Free Childcare / Vouchers")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Arrangement",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ("id", "child", "scheme", "provider", "monthly", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w, anc in [
        ("id", "ID", 80, "w"), ("child", "Child", 170, "w"),
        ("scheme", "Scheme", 200, "w"), ("provider", "Provider", 140, "w"),
        ("monthly", "Monthly £", 90, "e"), ("status", "Status", 80, "w"),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor=anc)
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary)
    host.status_var.set("Voucher arrangements loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_vouchers()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh vouchers")
        try:
            messagebox.showerror("Vouchers", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for v in rows:
        amt = f"{v.expected_amount:.2f}" if v.expected_amount is not None else "-"
        tree.insert("", "end", iid=v.voucher_id, values=(
            v.voucher_id, v.child_name or "-", v.scheme or "-", v.provider or "-",
            amt, v.status))
    by_scheme = "  ".join(f"{k}={v}" for k, v in sorted(s["by_scheme"].items()))
    summary.config(text=f"Arrangements: {s['count']}    Active: {s['active']}    "
                        f"Expected/month: £{s['expected_monthly']:.2f}"
                        + (f"    ·    {by_scheme}" if by_scheme else ""))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Vouchers", f"Select an arrangement to {verb}.",
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
    if not messagebox.askyesno("Delete arrangement",
                               f"Delete arrangement {sel}?", parent=host.root):
        return
    try:
        data.delete_voucher(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete voucher %s", sel)
        messagebox.showerror("Delete arrangement", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted arrangement {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x380")
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
        if kind == "scheme":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(SCHEMES),
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
    fields = _form_dialog(host, "Add Voucher Arrangement",
                          pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add arrangement cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add arrangement", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        v = data.create_voucher(fields)
    except ValidationError as e:
        messagebox.showerror("Add arrangement", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added arrangement {v.voucher_id}")
    open_manager(host)


@_safe_view
def open_edit(host, voucher_id: str) -> None:
    v = data.get_voucher(voucher_id)
    if v is None:
        messagebox.showerror("Edit arrangement", f"No arrangement with id {voucher_id}",
                             parent=host.root)
        return
    initial = {key: getattr(v, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit arrangement — {v.child_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_voucher(voucher_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit arrangement", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated arrangement {voucher_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Tax-Free Childcare / Vouchers",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Tax-Free Childcare / Vouchers from the navigation menu."
              ).pack(anchor="w")
    return frame
