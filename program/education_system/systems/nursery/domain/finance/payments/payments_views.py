"""Tkinter views for Payments (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists payments with a tree + toolbar and an add/edit form dialog with
a child picker, invoice allocation and method list — the GUI counterpart of
``payments_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.finance.payments import payments as data
from education_system.systems.nursery.domain.finance.payments.payments import (
    METHODS,
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


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: payments open_manager")
    root = _clear(host)
    _header(root, "Payments")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Record Payment",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ("id", "date", "child", "amount", "method", "invoice")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w, anc in [
        ("id", "ID", 80, "w"), ("date", "Date", 100, "w"),
        ("child", "Child", 180, "w"), ("amount", "Amount £", 90, "e"),
        ("method", "Method", 190, "w"), ("invoice", "Invoice", 90, "w"),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor=anc)
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary)
    host.status_var.set("Payments loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_payments()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh payments")
        try:
            messagebox.showerror("Payments", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for p in rows:
        tree.insert("", "end", iid=p.payment_id, values=(
            p.payment_id, p.payment_date or "-", p.child_name or "-",
            f"{p.amount:.2f}", p.method or "-", p.invoice_id or "-"))
    summary.config(text=f"Payments: {int(s['count'])}    "
                        f"Total received: £{s['received']:.2f}")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Payments", f"Select a payment to {verb}.",
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
    if not messagebox.askyesno("Delete payment", f"Delete payment {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_payment(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete payment %s", sel)
        messagebox.showerror("Delete payment", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted payment {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("470x420")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    # Invoice picker is populated from the chosen child (add) or current child.
    inv_combo: dict[str, Any] = {}
    inv_id_by_label: dict[str, str] = {}

    pid_id_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        pcb = ttk.Combobox(frm, textvariable=pvar,
                           values=[lbl for _i, lbl in choices],
                           state="readonly" if choices else "normal", width=34)
        pcb.grid(row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

        def _on_child(*_a) -> None:
            sid = pid_id_by_label.get((pvar.get() or "").strip(), "")
            open_inv = data.list_open_invoice_choices(sid) if sid else []
            inv_id_by_label.clear()
            inv_id_by_label.update({lbl: iid for iid, lbl in open_inv})
            inv_combo["widget"]["values"] = [""] + [lbl for _i, lbl in open_inv]
        pvar.trace_add("write", _on_child)

    ttk.Label(frm, text="Invoice:").grid(row=row, column=0, sticky="nw", pady=2)
    ivar = tk.StringVar(value=str(initial.get("invoice_id") or ""))
    icb = ttk.Combobox(frm, textvariable=ivar, width=34)
    icb.grid(row=row, column=1, sticky="ew", pady=2)
    inv_combo["widget"] = icb
    vars_["__invoice_label"] = ivar
    row += 1

    money_fields = [
        ("amount", "Amount (£)", "entry"),
        ("method", "Method", "method"),
        ("payment_date", "Payment date (YYYY-MM-DD)", "entry"),
        ("reference", "Reference", "entry"),
        ("notes", "Notes", "entry"),
    ]
    for key, label, kind in money_fields:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "method":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(METHODS),
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
            val = (v.get() or "").strip()
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get(val, "")
            elif k == "__invoice_label":
                # Accept either a picked "id — period" label or a raw id.
                out["invoice_id"] = inv_id_by_label.get(val, val)
            else:
                out[k] = val
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
    fields = _form_dialog(host, "Record Payment", pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Record payment cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Record payment", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        p = data.create_payment(fields)
    except ValidationError as e:
        messagebox.showerror("Record payment", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Recorded payment {p.payment_id}")
    open_manager(host)


@_safe_view
def open_edit(host, payment_id: str) -> None:
    p = data.get_payment(payment_id)
    if p is None:
        messagebox.showerror("Edit payment", f"No payment with id {payment_id}",
                             parent=host.root)
        return
    initial = {"invoice_id": p.invoice_id, "amount": p.amount, "method": p.method,
               "payment_date": p.payment_date, "reference": p.reference,
               "notes": p.notes}
    fields = _form_dialog(host, f"Edit payment — {p.child_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_payment(payment_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit payment", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated payment {payment_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Payments", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Payments from the navigation menu.").pack(
        anchor="w")
    return frame
