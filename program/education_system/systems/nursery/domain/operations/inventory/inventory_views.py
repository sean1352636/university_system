"""Tkinter views for Consumables & Stock (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Three tabs — the stock list with low/out-of-stock rows in red, the
alert board, and the movement ledger — plus use / receive / stocktake actions
that move stock and its level together. The GUI counterpart of
``inventory_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.operations.inventory import (
    inventory as data,
)
from education_system.systems.nursery.domain.operations.inventory.inventory import (
    CATEGORIES,
    ITEM_STATUSES,
    UNITS,
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
          height: int = 14) -> ttk.Treeview:
    cols = tuple(c for c, _l, _w in spec)
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=height)
    for c, label, w in spec:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("alert", foreground="#c0392b")
    tree.tag_configure("warn", foreground="#b9770e")
    tree.tag_configure("muted", foreground="#7f8c8d")
    tree.pack(fill="both", expand=True)
    return tree


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Stock", f"Select an item to {verb}.",
                            parent=host.root)
        return None
    return sel


def _form_dialog(host, title: str, fields: list[tuple[str, str, str, Any]], *,
                 initial: dict[str, Any] | None = None,
                 geometry: str = "480x560") -> dict[str, Any] | None:
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
                         width=32).grid(row=row, column=1, sticky="ew", pady=2)
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
        result = {k: (str(v.get()) or "").strip() for k, v in vars_.items()}
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _supplier_choices() -> list[str]:
    try:
        return [""] + [sid for sid, _label in data.list_supplier_choices()]
    except Exception:
        logger.exception("Could not load supplier choices")
        return [""]


# ── Manager ──────────────────────────────────────────────────────────────────

@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: inventory open_manager")
    root = _clear(host)
    ttk.Label(root, text="Consumables & Stock", font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 2))
    warn = ttk.Label(root, foreground="#a00", wraplength=900)
    warn.pack(anchor="w", pady=(0, 6))
    _refresh_summary(summary, warn)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    item_tab = ttk.Frame(nb, padding=8)
    alert_tab = ttk.Frame(nb, padding=8)
    movement_tab = ttk.Frame(nb, padding=8)
    nb.add(item_tab, text="Stock List")
    nb.add(alert_tab, text="Reorder Alerts")
    nb.add(movement_tab, text="Movements")

    _build_item_tab(host, item_tab)
    _build_alert_tab(host, alert_tab)
    _build_movement_tab(host, movement_tab)

    host.status_var.set("Stock loaded")


def _refresh_summary(summary: ttk.Label, warn: ttk.Label) -> None:
    try:
        s = data.summary()
    except Exception:
        logger.exception("Could not load stock summary")
        summary.config(text="Could not load — see logs.", foreground="#a00")
        return
    summary.config(
        text=f"Items: {s['active_items']} active across {s['categories']} "
             f"categories   Stock value: £{s['stock_value']:.2f}   "
             f"Suggested reorder: £{s['reorder_cost']:.2f}")
    problems = []
    if s["out_of_stock"]:
        problems.append(f"{s['out_of_stock']} out of stock")
    if s["needs_reorder"]:
        problems.append(f"{s['needs_reorder']} at reorder level")
    if s["expired"]:
        problems.append(f"{s['expired']} expired")
    if s["expiring_soon"]:
        problems.append(f"{s['expiring_soon']} expiring soon")
    warn.config(text=("⚠ " + ", ".join(problems)) if problems else "")


# ── Stock list tab ───────────────────────────────────────────────────────────

_ITEM_FIELDS: list[tuple[str, str, str, Any]] = [
    ("name",             "Name",              "entry",  None),
    ("category",         "Category",          "choice", CATEGORIES),
    ("unit",             "Unit",              "choice", UNITS),
    ("reorder_level",    "Reorder level",     "entry",  None),
    ("reorder_quantity", "Reorder quantity",  "entry",  None),
    ("unit_cost",        "Unit cost (£)",     "entry",  None),
    ("supplier_id",      "Supplier ID",       "choice", None),
    ("location",         "Storage location",  "entry",  None),
    ("room",             "Room",              "entry",  None),
    ("expiry_date",      "Expiry (YYYY-MM-DD)", "entry", None),
    ("status",           "Status",            "choice", ITEM_STATUSES),
    ("notes",            "Notes",             "entry",  None),
]


def _item_fields(*, with_quantity: bool) -> list[tuple[str, str, str, Any]]:
    fields = [(k, lb, kd, _supplier_choices() if k == "supplier_id" else ch)
              for k, lb, kd, ch in _ITEM_FIELDS]
    if with_quantity:
        fields.insert(3, ("quantity", "Opening quantity", "entry", None))
    return fields


def _build_item_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Item",
               command=lambda: _add_item(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_item(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Use Stock",
               command=lambda: _movement(host, tree, "usage")).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Receive",
               command=lambda: _movement(host, tree, "receipt")).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Stocktake",
               command=lambda: _movement(host, tree, "stocktake")).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_item(host, tree)).pack(side="left",
                                                              padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_items(tree)).pack(side="left", padx=2)

    tree = _tree(parent, [
        ("id", "ID", 70), ("name", "Item", 220), ("category", "Category", 160),
        ("qty", "In stock", 90), ("unit", "Unit", 70),
        ("reorder", "Reorder at", 90), ("cost", "Unit cost", 90),
        ("value", "Value", 90), ("supplier", "Supplier", 150),
        ("expiry", "Expires", 100),
    ])
    tree.bind("<Double-1>", lambda _e: _edit_item(host, tree))
    _refresh_items(tree)


def _refresh_items(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_items()
    except Exception:
        logger.exception("Could not refresh stock items")
        return
    for i in rows:
        if i.status != "active":
            tag = "muted"
        elif i.out_of_stock:
            tag = "alert"
        elif i.needs_reorder:
            tag = "warn"
        else:
            tag = ""
        tree.insert("", "end", iid=i.item_id, tags=(tag,) if tag else (),
                    values=(i.item_id, i.name, i.category, f"{i.quantity:g}",
                            i.unit, f"{i.reorder_level:g}",
                            f"£{i.unit_cost:.2f}", f"£{i.value:.2f}",
                            i.supplier_name or "-", i.expiry_date or "-"))


@_safe_view
def _add_item(host) -> None:
    fields = _form_dialog(host, "Add Stock Item", _item_fields(with_quantity=True),
                          initial={"category": "Consumables", "unit": "each",
                                   "status": "active", "quantity": "0"})
    if not fields:
        return
    try:
        item = data.create_item(fields)
    except ValidationError as e:
        messagebox.showerror("Add item", str(e), parent=host.root)
        return
    host.status_var.set(f"Added {item.name} ({item.item_id})")
    open_manager(host)


@_safe_view
def _edit_item(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "edit")
    if not sel:
        return
    item = data.get_item(sel)
    if item is None:
        return
    initial = {k: getattr(item, k) for k, _l, _kd, _ch in _ITEM_FIELDS}
    fields = _form_dialog(host, f"Edit {item.name}",
                          _item_fields(with_quantity=False), initial=initial)
    if not fields:
        return
    try:
        data.update_item(sel, fields)
    except ValidationError as e:
        messagebox.showerror("Edit item", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated {sel}")
    open_manager(host)


@_safe_view
def _movement(host, tree: ttk.Treeview, movement_type: str) -> None:
    titles = {"usage": "Use Stock", "receipt": "Receive Delivery",
              "stocktake": "Stocktake"}
    sel = _selected(tree, host, titles[movement_type].lower())
    if not sel:
        return
    item = data.get_item(sel)
    if item is None:
        return
    label = ("Counted quantity" if movement_type == "stocktake"
             else f"Quantity ({item.unit})")
    fields = _form_dialog(host, f"{titles[movement_type]} — {item.name}", [
        ("quantity", label, "entry", None),
        ("room", "Room", "entry", None),
        ("staff_id", "Your staff ID", "entry", None),
        ("reference", "Reference (PO / delivery note)", "entry", None),
        ("notes", "Notes", "entry", None),
    ], initial={"quantity": f"{item.quantity:g}"
                if movement_type == "stocktake" else ""},
        geometry="440x300")
    if not fields:
        return
    try:
        data.record_movement({**fields, "item_id": sel,
                              "movement_type": movement_type})
    except ValidationError as e:
        messagebox.showerror(titles[movement_type], str(e), parent=host.root)
        return
    after = data.get_item(sel)
    assert after is not None
    host.status_var.set(
        f"{item.name} now at {after.quantity:g} {after.unit}")
    if after.needs_reorder:
        messagebox.showwarning(
            "Reorder", f"{after.name} is down to {after.quantity:g} "
                       f"{after.unit}.\n\nOrder {after.suggested_order:g} "
                       f"{after.unit}"
                       + (f" from {after.supplier_name}."
                          if after.supplier_name else "."),
            parent=host.root)
    open_manager(host)


@_safe_view
def _delete_item(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "delete")
    if not sel:
        return
    if not messagebox.askyesno(
            "Delete item",
            f"Delete {sel} and its movement history?", parent=host.root):
        return
    data.delete_item(sel)
    host.status_var.set(f"Deleted {sel}")
    open_manager(host)


# ── Alerts tab ───────────────────────────────────────────────────────────────

def _build_alert_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Reorder List",
               command=lambda: _reorder_list(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_alerts(tree)).pack(side="left", padx=2)

    tree = _tree(parent, [
        ("severity", "Severity", 90), ("item", "Item", 220),
        ("category", "Category", 160), ("reason", "Reason", 120),
        ("detail", "What to do", 480),
    ])
    _refresh_alerts(tree)


def _refresh_alerts(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.reorder_alerts()
    except Exception:
        logger.exception("Could not refresh stock alerts")
        return
    for i, a in enumerate(rows):
        tag = "alert" if a.severity == "urgent" else "warn"
        tree.insert("", "end", iid=f"alert-{i}", tags=(tag,), values=(
            a.severity.upper(), a.item.name, a.item.category, a.reason,
            a.detail))


@_safe_view
def _reorder_list(host) -> None:
    rows = data.reorder_list()
    if not rows:
        messagebox.showinfo("Reorder list", "Nothing needs ordering.",
                            parent=host.root)
        return
    lines = [f"{r['description'][:30]:<30} {r['quantity']:>6g} {r['unit']:<7} "
             f"£{r['line_total']:>8.2f}  {r['supplier_name'] or '-'}"
             for r in rows]
    total = sum(r["line_total"] for r in rows)
    messagebox.showinfo(
        "Reorder list",
        "\n".join(lines) + f"\n\nTotal: £{total:.2f}\n\n"
        "Raise this as a purchase order from Suppliers & Purchase Orders.",
        parent=host.root)


# ── Movements tab ────────────────────────────────────────────────────────────

def _build_movement_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_movements(tree)).pack(side="left",
                                                              padx=2)

    tree = _tree(parent, [
        ("id", "ID", 70), ("date", "Date", 100), ("item", "Item", 220),
        ("type", "Type", 110), ("qty", "Change", 90),
        ("room", "Room", 130), ("ref", "Reference", 150),
        ("by", "Recorded by", 160),
    ])
    _refresh_movements(tree)


def _refresh_movements(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_movements()
    except Exception:
        logger.exception("Could not refresh stock movements")
        return
    for m in rows[:200]:
        tag = "warn" if m.quantity < 0 else ""
        tree.insert("", "end", iid=m.movement_id, tags=(tag,) if tag else (),
                    values=(m.movement_id, m.movement_date,
                            m.item_name or m.item_id, m.movement_type,
                            f"{m.quantity:+g}", m.room or "-",
                            m.reference or "-",
                            m.staff_name or m.staff_id or "-"))


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Consumables & Stock", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Consumables & Stock from the navigation menu."
              ).pack(anchor="w")
    return frame
