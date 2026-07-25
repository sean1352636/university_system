"""Tkinter views for Suppliers & Purchase Orders (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Two tabs — the order board with the whole draft-to-paid workflow on
a toolbar, and the supplier list — the GUI counterpart of ``purchasing_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.finance.purchasing import (
    purchasing as data,
)
from education_system.systems.nursery.domain.finance.purchasing.purchasing import (
    APPROVAL_LIMITS,
    SUPPLIER_CATEGORIES,
    SUPPLIER_STATUSES,
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


def _tree(parent: ttk.Frame, spec: list[tuple[str, str, int]],
          height: int = 13) -> ttk.Treeview:
    cols = tuple(c for c, _l, _w in spec)
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=height)
    for c, label, w in spec:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("alert", foreground="#c0392b")
    tree.tag_configure("warn", foreground="#b9770e")
    tree.tag_configure("muted", foreground="#7f8c8d")
    tree.tag_configure("ok", foreground="#1e7e34")
    tree.pack(fill="both", expand=True)
    return tree


def _selected(tree: ttk.Treeview, host, what: str, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Purchasing", f"Select {what} to {verb}.",
                            parent=host.root)
        return None
    return sel


def _form_dialog(host, title: str, fields: list[tuple[str, str, str, Any]], *,
                 initial: dict[str, Any] | None = None,
                 geometry: str = "480x480") -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry(geometry)
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0
    for key, label, kind, choices in fields:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw",
                                              pady=2)
        cur = initial.get(key)
        if kind == "choice":
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Combobox(frm, textvariable=v, values=list(choices or []),
                         width=34).grid(row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=36).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {k: (str(v.get()) or "").strip() for k, v in vars_.items()}
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _supplier_ids() -> list[str]:
    try:
        return [sid for sid, _label in data.list_supplier_choices()]
    except Exception:
        logger.exception("Could not load supplier choices")
        return []


# ── Manager ──────────────────────────────────────────────────────────────────

@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: purchasing open_manager")
    root = _clear(host)
    ttk.Label(root, text="Suppliers & Purchase Orders",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 2))
    warn = ttk.Label(root, foreground="#a00")
    warn.pack(anchor="w", pady=(0, 6))
    _refresh_summary(summary, warn)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    order_tab = ttk.Frame(nb, padding=8)
    supplier_tab = ttk.Frame(nb, padding=8)
    nb.add(order_tab, text="Purchase Orders")
    nb.add(supplier_tab, text="Suppliers")

    _build_order_tab(host, order_tab)
    _build_supplier_tab(host, supplier_tab)

    host.status_var.set("Purchasing loaded")


def _refresh_summary(summary: ttk.Label, warn: ttk.Label) -> None:
    try:
        s = data.summary()
    except Exception:
        logger.exception("Could not load purchasing summary")
        summary.config(text="Could not load — see logs.", foreground="#a00")
        return
    summary.config(
        text=f"Suppliers: {s['active_suppliers']} active   Open orders: "
             f"{s['open_orders']}   Committed: £{s['committed_spend']:.2f}   "
             f"Unpaid: £{s['unpaid_value']:.2f}   Paid this year: "
             f"£{s['spend_this_year']:.2f}")
    problems = []
    if s["awaiting_approval"]:
        problems.append(f"{s['awaiting_approval']} awaiting approval")
    if s["overdue"]:
        problems.append(f"{s['overdue']} supplier invoice(s) overdue")
    warn.config(text=("⚠ " + ", ".join(problems)) if problems else "")


# ── Orders tab ───────────────────────────────────────────────────────────────

def _build_order_tab(host, parent: ttk.Frame) -> None:
    bar1 = ttk.Frame(parent)
    bar1.pack(fill="x", pady=(0, 4))
    ttk.Button(bar1, text="New Order",
               command=lambda: _new_order(host)).pack(side="left", padx=2)
    ttk.Button(bar1, text="Add Line",
               command=lambda: _add_line(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar1, text="View",
               command=lambda: _view_order(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar1, text="From Reorder List",
               command=lambda: _from_reorder(host)).pack(side="left", padx=2)
    ttk.Button(bar1, text="Approval Limits",
               command=lambda: _limits(host)).pack(side="left", padx=2)

    bar2 = ttk.Frame(parent)
    bar2.pack(fill="x", pady=(0, 8))
    for text, action in [
        ("Submit", _submit), ("Approve", _approve), ("Reject", _reject),
        ("Mark Ordered", _mark_ordered), ("Receive", _receive),
        ("Record Invoice", _invoice), ("Mark Paid", _pay),
        ("Cancel", _cancel),
    ]:
        ttk.Button(bar2, text=text,
                   command=(lambda a=action: a(host, tree))).pack(side="left",
                                                                  padx=2)

    tree = _tree(parent, [
        ("id", "PO", 70), ("supplier", "Supplier", 200),
        ("raised", "Raised", 100), ("required", "Required by", 100),
        ("lines", "Lines", 60), ("total", "Total", 100),
        ("status", "Status", 100), ("approver", "Needs", 130),
        ("invoice", "Invoice", 130),
    ])
    tree.bind("<Double-1>", lambda _e: _view_order(host, tree))
    _refresh_orders(tree)


def _refresh_orders(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_orders()
    except Exception:
        logger.exception("Could not refresh purchase orders")
        return
    for o in rows:
        if o.overdue:
            tag = "alert"
        elif o.status == "submitted":
            tag = "warn"
        elif o.status in ("paid", "cancelled", "rejected"):
            tag = "muted"
        elif o.status == "approved":
            tag = "ok"
        else:
            tag = ""
        invoice = o.invoice_ref or ""
        if o.overdue:
            invoice = f"{invoice} OVERDUE".strip()
        tree.insert("", "end", iid=o.po_id, tags=(tag,) if tag else (), values=(
            o.po_id, o.supplier_name or o.supplier_id, o.order_date,
            o.required_by or "-", len(o.lines), f"£{o.total:.2f}", o.status,
            data.required_role(o.total), invoice or "-"))


@_safe_view
def _limits(host) -> None:
    lines = [f"{role:<20} {'no limit' if limit is None else f'£{limit:,.2f}'}"
             for role, limit in APPROVAL_LIMITS.items()]
    messagebox.showinfo(
        "Approval limits",
        "\n".join(lines) + "\n\nAn order is approved by the most junior role "
        "whose limit covers the total.", parent=host.root)


@_safe_view
def _new_order(host) -> None:
    suppliers = _supplier_ids()
    if not suppliers:
        messagebox.showinfo("New order", "Add a supplier first.",
                            parent=host.root)
        return
    fields = _form_dialog(host, "Raise a Purchase Order", [
        ("supplier_id", "Supplier ID", "choice", suppliers),
        ("order_date", "Order date (blank = today)", "entry", None),
        ("required_by", "Required by", "entry", None),
        ("raised_by", "Your staff ID", "entry", None),
        ("notes", "Notes", "entry", None),
    ], geometry="460x280")
    if not fields:
        return
    try:
        o = data.create_order(fields)
    except ValidationError as e:
        messagebox.showerror("New order", str(e), parent=host.root)
        return
    host.status_var.set(f"Raised draft {o.po_id} — add lines, then submit")
    open_manager(host)


@_safe_view
def _add_line(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "an order", "add a line to")
    if not sel:
        return
    from education_system.systems.nursery.domain.operations.inventory import (
        inventory as _inventory,
    )
    try:
        items = [""] + [iid for iid, _label in _inventory.list_item_choices()]
    except Exception:
        items = [""]
    fields = _form_dialog(host, f"Add a line to {sel}", [
        ("item_id", "Stock item (optional)", "choice", items),
        ("description", "Description", "entry", None),
        ("quantity", "Quantity", "entry", None),
        ("unit", "Unit", "entry", None),
        ("unit_price", "Unit price (£)", "entry", None),
        ("notes", "Notes", "entry", None),
    ], initial={"unit": "each", "quantity": "1"}, geometry="460x320")
    if not fields:
        return
    try:
        data.add_line(sel, fields)
    except ValidationError as e:
        messagebox.showerror("Add line", str(e), parent=host.root)
        return
    o = data.get_order(sel)
    host.status_var.set(
        f"{sel} now has {len(o.lines)} line(s), £{o.total:.2f}" if o else "")
    open_manager(host)


@_safe_view
def _view_order(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "an order", "view")
    if not sel:
        return
    o = data.get_order(sel)
    if o is None:
        return
    lines = [
        f"Supplier:    {o.supplier_name or o.supplier_id}",
        f"Raised:      {o.order_date} by "
        f"{o.raised_by_name or o.raised_by or '-'}",
        f"Required by: {o.required_by or '-'}",
        f"Status:      {o.status}",
    ]
    if o.approved_at:
        lines.append(f"Approved by: {o.approved_by_name or o.approved_by} "
                     f"at {o.approved_at}")
        if o.approval_note:
            lines.append(f"Note:        {o.approval_note}")
    if o.invoice_ref:
        lines.append(f"Invoice:     {o.invoice_ref} dated {o.invoice_date}, "
                     f"due {o.invoice_due}")
    if o.paid_at:
        lines.append(f"Paid:        {o.paid_at}")
    lines.append("")
    for line in o.lines:
        lines.append(f"  {line.description[:30]:<30} {line.quantity:>6g} "
                     f"{line.unit:<7} £{line.unit_price:>7.2f} = "
                     f"£{line.line_total:>8.2f}"
                     + (f"  [stock {line.item_id}]" if line.item_id else ""))
    if not o.lines:
        lines.append("  (no lines)")
    lines += ["", f"Total: £{o.total:.2f}",
              f"Needs a {data.required_role(o.total)} to approve.",
              f"Can move to: {', '.join(o.next_statuses()) or 'nothing'}"]
    messagebox.showinfo(f"Purchase order {o.po_id}", "\n".join(lines),
                        parent=host.root)


def _step(host, tree: ttk.Treeview, verb: str, action, *,
          fields: list[tuple[str, str, str, Any]] | None = None,
          confirm: str | None = None, geometry: str = "440x220") -> None:
    """Shared plumbing for the one-button workflow transitions."""
    sel = _selected(tree, host, "an order", verb)
    if not sel:
        return
    o = data.get_order(sel)
    if o is None:
        return
    if confirm and not messagebox.askyesno(verb.title(),
                                           confirm.format(po=o.po_id,
                                                          total=o.total),
                                           parent=host.root):
        return
    values: dict[str, Any] = {}
    if fields:
        got = _form_dialog(host, f"{verb.title()} — {o.po_id}", fields,
                           geometry=geometry)
        if got is None:
            return
        values = got
    try:
        out = action(sel, values, o)
    except ValidationError as e:
        messagebox.showerror(verb.title(), str(e), parent=host.root)
        return
    host.status_var.set(f"{out.po_id} is now {out.status}")
    open_manager(host)


def _submit(host, tree):
    _step(host, tree, "submit", lambda po, v, o: data.submit_order(po),
          confirm="Submit {po} (£{total:.2f}) for approval?")


def _approve(host, tree):
    _step(host, tree, "approve",
          lambda po, v, o: data.approve_order(po, v.get("staff_id", ""),
                                              v.get("note") or None),
          fields=[("staff_id", "Your staff ID", "entry", None),
                  ("note", "Note (optional)", "entry", None)])


def _reject(host, tree):
    _step(host, tree, "reject",
          lambda po, v, o: data.reject_order(po, v.get("staff_id", ""),
                                             v.get("note") or None),
          fields=[("staff_id", "Your staff ID", "entry", None),
                  ("note", "Reason", "entry", None)])


def _mark_ordered(host, tree):
    _step(host, tree, "mark ordered", lambda po, v, o: data.mark_ordered(po),
          confirm="Mark {po} as placed with the supplier?")


def _receive(host, tree):
    def _do(po, v, o):
        out = data.receive_order(po, received_date=v.get("date") or None,
                                 staff_id=v.get("staff_id") or None)
        linked = sum(1 for line in out.lines if line.item_id)
        if linked:
            messagebox.showinfo(
                "Received",
                f"{linked} line(s) booked into stock — nothing to re-key.",
                parent=host.root)
        return out
    _step(host, tree, "receive", _do,
          fields=[("date", "Received date (blank = today)", "entry", None),
                  ("staff_id", "Your staff ID", "entry", None)])


def _invoice(host, tree):
    _step(host, tree, "record invoice",
          lambda po, v, o: data.record_invoice(
              po, v.get("ref", ""), invoice_date=v.get("date") or None,
              invoice_due=v.get("due") or None),
          fields=[("ref", "Supplier invoice reference", "entry", None),
                  ("date", "Invoice date (blank = today)", "entry", None),
                  ("due", "Due date (blank = payment terms)", "entry", None)],
          geometry="460x260")


def _pay(host, tree):
    _step(host, tree, "mark paid",
          lambda po, v, o: data.mark_paid(po, paid_date=v.get("date") or None),
          fields=[("date", "Paid date (blank = today)", "entry", None)],
          geometry="440x180")


def _cancel(host, tree):
    _step(host, tree, "cancel",
          lambda po, v, o: data.cancel_order(po, v.get("note") or None),
          fields=[("note", "Reason", "entry", None)],
          confirm="Cancel {po}?", geometry="440x180")


@_safe_view
def _from_reorder(host) -> None:
    suppliers = _supplier_ids()
    if not suppliers:
        messagebox.showinfo("Reorder", "Add a supplier first.",
                            parent=host.root)
        return
    fields = _form_dialog(host, "Raise From the Stock Reorder List", [
        ("supplier_id", "Supplier ID", "choice", suppliers),
        ("raised_by", "Your staff ID", "entry", None),
    ], geometry="440x190")
    if not fields:
        return
    try:
        o = data.create_order_from_reorder_list(
            fields.get("supplier_id", ""),
            raised_by=fields.get("raised_by") or None)
    except ValidationError as e:
        messagebox.showerror("Reorder", str(e), parent=host.root)
        return
    host.status_var.set(
        f"Raised {o.po_id} with {len(o.lines)} line(s), £{o.total:.2f}")
    open_manager(host)


# ── Suppliers tab ────────────────────────────────────────────────────────────

_SUPPLIER_FIELDS: list[tuple[str, str, str, Any]] = [
    ("name",               "Name",                 "entry",  None),
    ("category",           "Category",             "choice", SUPPLIER_CATEGORIES),
    ("contact_name",       "Contact name",         "entry",  None),
    ("email",              "Email",                "entry",  None),
    ("phone",              "Phone",                "entry",  None),
    ("account_number",     "Account number",       "entry",  None),
    ("payment_terms_days", "Payment terms (days)", "entry",  None),
    ("status",             "Status",               "choice", SUPPLIER_STATUSES),
    ("notes",              "Notes",                "entry",  None),
]


def _build_supplier_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Supplier",
               command=lambda: _add_supplier(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_supplier(host, tree)).pack(side="left",
                                                                padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_supplier(host, tree)).pack(side="left",
                                                                  padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_suppliers(tree)).pack(side="left",
                                                              padx=2)

    tree = _tree(parent, [
        ("id", "ID", 70), ("name", "Name", 220), ("category", "Category", 170),
        ("contact", "Contact", 160), ("email", "Email", 200),
        ("phone", "Phone", 130), ("terms", "Terms", 70),
        ("status", "Status", 90),
    ])
    tree.bind("<Double-1>", lambda _e: _edit_supplier(host, tree))
    _refresh_suppliers(tree)


def _refresh_suppliers(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_suppliers()
    except Exception:
        logger.exception("Could not refresh suppliers")
        return
    for s in rows:
        tag = "muted" if s.status != "active" else ""
        tree.insert("", "end", iid=s.supplier_id, tags=(tag,) if tag else (),
                    values=(s.supplier_id, s.name, s.category or "-",
                            s.contact_name or "-", s.email or "-",
                            s.phone or "-", f"{s.payment_terms_days}d",
                            s.status))


@_safe_view
def _add_supplier(host) -> None:
    fields = _form_dialog(host, "Add Supplier", _SUPPLIER_FIELDS,
                          initial={"payment_terms_days": "30",
                                   "status": "active"})
    if not fields:
        return
    try:
        s = data.create_supplier(fields)
    except ValidationError as e:
        messagebox.showerror("Add supplier", str(e), parent=host.root)
        return
    host.status_var.set(f"Added {s.name} ({s.supplier_id})")
    open_manager(host)


@_safe_view
def _edit_supplier(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a supplier", "edit")
    if not sel:
        return
    s = data.get_supplier(sel)
    if s is None:
        return
    initial = {k: getattr(s, k) for k, _l, _kd, _ch in _SUPPLIER_FIELDS}
    fields = _form_dialog(host, f"Edit {s.name}", _SUPPLIER_FIELDS,
                          initial=initial)
    if not fields:
        return
    try:
        data.update_supplier(sel, fields)
    except ValidationError as e:
        messagebox.showerror("Edit supplier", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated {sel}")
    open_manager(host)


@_safe_view
def _delete_supplier(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a supplier", "delete")
    if not sel:
        return
    if not messagebox.askyesno("Delete supplier", f"Delete {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_supplier(sel)
    except ValidationError as e:
        messagebox.showerror("Delete supplier", str(e), parent=host.root)
        return
    host.status_var.set(f"Deleted {sel}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Suppliers & Purchase Orders",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Suppliers & Purchase Orders from the "
              "navigation menu.").pack(anchor="w")
    return frame
