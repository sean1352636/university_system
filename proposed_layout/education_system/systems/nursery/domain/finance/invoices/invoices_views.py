"""Tkinter views for Invoices & Fees (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists invoices with a tree + toolbar (paid/balance columns) and an
add/edit form dialog — the GUI counterpart of ``invoices_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.finance.invoices import invoices as data
from education_system.systems.nursery.domain.finance.invoices.invoices import (
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
    ("period",           "Period (e.g. June 2025)",      "entry"),
    ("issue_date",       "Issue date (YYYY-MM-DD)",      "entry"),
    ("due_date",         "Due date (YYYY-MM-DD)",        "entry"),
    ("hours_billed",     "Hours billed",                 "entry"),
    ("hourly_rate",      "Hourly rate (£)",              "entry"),
    ("gross_amount",     "Gross amount (£)",             "entry"),
    ("funded_deduction", "Funded-hours deduction (£)",   "entry"),
    ("discount_amount",  "Discount (£)",                 "entry"),
    ("status",           "Status",                       "status"),
    ("notes",            "Notes",                        "entry"),
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
    logger.debug("GUI: invoices open_manager")
    root = _clear(host)
    _header(root, "Invoices & Fees")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Invoice",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ("id", "child", "period", "total", "paid", "balance", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w, anc in [
        ("id", "ID", 80, "w"), ("child", "Child", 170, "w"),
        ("period", "Period", 110, "w"), ("total", "Total £", 90, "e"),
        ("paid", "Paid £", 90, "e"), ("balance", "Balance £", 90, "e"),
        ("status", "Status", 90, "w"),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor=anc)
    tree.tag_configure("owing", foreground="#b9770e")
    tree.tag_configure("paid", foreground="#1e7e34")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary)
    host.status_var.set("Invoices loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_invoices()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh invoices")
        try:
            messagebox.showerror("Invoices", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for inv in rows:
        tag = "paid" if inv.balance <= 0 and inv.status != "void" else (
            "owing" if inv.balance > 0 else "")
        tree.insert("", "end", iid=inv.invoice_id, tags=(tag,) if tag else (),
                    values=(inv.invoice_id, inv.child_name or "-",
                            inv.period or "-", f"{inv.total_amount:.2f}",
                            f"{inv.paid:.2f}", f"{inv.balance:.2f}", inv.status))
    summary.config(
        text=f"Invoices: {int(s['count'])}    Billed: £{s['billed']:.2f}    "
             f"Collected: £{s['collected']:.2f}    "
             f"Outstanding: £{s['outstanding']:.2f}",
        foreground="#a00" if s["outstanding"] > 0 else "#555")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Invoices", f"Select an invoice to {verb}.",
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
    if not messagebox.askyesno("Delete invoice", f"Delete invoice {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_invoice(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete invoice %s", sel)
        messagebox.showerror("Delete invoice", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted invoice {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("470x500")
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
        if kind == "status":
            v = tk.StringVar(value=str(cur or "draft"))
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
    fields = _form_dialog(host, "Add Invoice", pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add invoice cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add invoice", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        inv = data.create_invoice(fields)
    except ValidationError as e:
        messagebox.showerror("Add invoice", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo(
        "Invoice created",
        f"{inv.child_name} — {inv.period or '-'}\nTotal due: £{inv.total_amount:.2f}",
        parent=host.root)
    host.status_var.set(f"Created invoice {inv.invoice_id}")
    open_manager(host)


@_safe_view
def open_edit(host, invoice_id: str) -> None:
    inv = data.get_invoice(invoice_id)
    if inv is None:
        messagebox.showerror("Edit invoice", f"No invoice with id {invoice_id}",
                             parent=host.root)
        return
    initial = {key: getattr(inv, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit invoice — {inv.child_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_invoice(invoice_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit invoice", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated invoice {invoice_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Invoices & Fees", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Invoices & Fees from the navigation menu.").pack(
        anchor="w")
    return frame
