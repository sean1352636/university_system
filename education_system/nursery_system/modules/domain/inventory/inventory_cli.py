"""CLI flow for Consumables & Stock (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.inventory import (
    inventory as data,
)
from education_system.nursery_system.modules.domain.inventory.inventory import (
    CATEGORIES,
    MOVEMENT_TYPES,
    UNITS,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _ask(label: str, current=None) -> str:
    cur = "" if current is None else str(current)
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label}{suffix}: ")
    return v if v else cur


def _print_items(rows: list[data.StockItem]) -> None:
    if not rows:
        print("  (no stock items)")
        return
    print(f"  {'ID':<8} {'Item':<28} {'Category':<20} {'Qty':>9} {'Unit':<8} "
          f"{'Reorder':>8} {'Value':>9}  Flag")
    print(f"  {'-'*8} {'-'*28} {'-'*20} {'-'*9} {'-'*8} {'-'*8} {'-'*9}  {'-'*12}")
    for i in rows:
        if i.out_of_stock:
            flag = "OUT OF STOCK"
        elif i.needs_reorder:
            flag = "reorder"
        else:
            flag = ""
        print(f"  {i.item_id:<8} {i.name[:28]:<28} {i.category[:20]:<20} "
              f"{i.quantity:>9g} {i.unit:<8} {i.reorder_level:>8g} "
              f"£{i.value:>8.2f}  {flag}")


@_safe
def open_manager() -> None:
    logger.debug("CLI: inventory open_manager")
    while True:
        s = data.summary()
        print("\n  ── Consumables & Stock ──")
        print(f"  Items: {s['active_items']} active across {s['categories']} "
              f"categories   Stock value: £{s['stock_value']:.2f}")
        if s["alerts"]:
            print(f"  ⚠ {s['out_of_stock']} out of stock, "
                  f"{s['needs_reorder']} at reorder level, "
                  f"{s['expiring_soon']} expiring soon, {s['expired']} expired")
            print(f"    Suggested reorder cost: £{s['reorder_cost']:.2f}")
        else:
            print("  No stock alerts.")
        _print_items(data.list_items())
        print("\n   A) Add item    E) Edit    D) Delete    U) Use stock")
        print("   R) Receive delivery    T) Stocktake    L) Reorder list")
        print("   ! ) Alerts    M) Movements    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_item()
        elif choice == "e":
            open_edit_item()
        elif choice == "d":
            open_delete_item()
        elif choice == "u":
            open_movement("usage")
        elif choice == "r":
            open_movement("receipt")
        elif choice == "t":
            open_movement("stocktake")
        elif choice == "l":
            open_reorder_list()
        elif choice == "!":
            open_alerts()
        elif choice == "m":
            open_movements()
        else:
            print("  Invalid selection.")


def _collect_item(existing: data.StockItem | None = None) -> dict[str, str]:
    fields: dict[str, str] = {}
    fields["name"] = _ask("Name", existing.name if existing else None)
    print(f"  Categories: {', '.join(CATEGORIES)}")
    fields["category"] = _ask("Category",
                              existing.category if existing else "Consumables")
    fields["unit"] = _ask(f"Unit ({'/'.join(UNITS)})",
                          existing.unit if existing else "each")
    if existing is None:
        fields["quantity"] = _ask("Opening quantity", 0)
    fields["reorder_level"] = _ask("Reorder level",
                                   existing.reorder_level if existing else 0)
    fields["reorder_quantity"] = _ask(
        "Reorder quantity", existing.reorder_quantity if existing else 0)
    fields["unit_cost"] = _ask("Unit cost (£)",
                               existing.unit_cost if existing else 0)
    fields["supplier_id"] = _ask("Supplier ID (optional)",
                                 existing.supplier_id if existing else None)
    fields["location"] = _ask("Storage location",
                              existing.location if existing else None)
    fields["room"] = _ask("Room (optional)", existing.room if existing else None)
    fields["expiry_date"] = _ask("Expiry date (optional)",
                                 existing.expiry_date if existing else None)
    fields["notes"] = _ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_add_item() -> None:
    print("\n  ── Add Stock Item ──")
    try:
        suppliers = data.list_supplier_choices()
    except Exception:
        suppliers = []
    if suppliers:
        print("  Suppliers: " + ", ".join(label for _s, label in suppliers))
    item = data.create_item(_collect_item())
    print(f"\n  Added {item.name} ({item.item_id}) — "
          f"{item.quantity:g} {item.unit} in stock.")


@_safe
def open_edit_item() -> None:
    iid = _prompt("  Item ID: ")
    if not iid:
        print("  Cancelled.")
        return
    existing = data.get_item(iid)
    if existing is None:
        print("  No item with that ID.")
        return
    print("  Press Enter to keep the existing value. "
          "(Use a movement to change the quantity.)")
    item = data.update_item(iid, _collect_item(existing))
    print(f"\n  Updated {item.name}.")


@_safe
def open_delete_item() -> None:
    iid = _prompt("  Item ID to delete: ")
    if not iid:
        print("  Cancelled.")
        return
    existing = data.get_item(iid)
    if existing is None:
        print("  No item with that ID.")
        return
    if _prompt(f"  Delete {existing.name} and its movement history? (y/N): "
               ).lower() != "y":
        print("  Cancelled.")
        return
    print(f"  Deleted {iid}." if data.delete_item(iid)
          else "  Could not delete (already removed?).")


@_safe
def open_movement(movement_type: str = "usage") -> None:
    titles = {"usage": "Use Stock", "receipt": "Receive Delivery",
              "stocktake": "Stocktake"}
    print(f"\n  ── {titles.get(movement_type, 'Stock Movement')} ──")
    choices = data.list_item_choices()
    if not choices:
        print("  No stock items yet.")
        return
    for iid, label in choices:
        print(f"    {iid}  {label}")
    iid = _prompt("  Item ID: ")
    if not iid:
        print("  Cancelled.")
        return
    if movement_type not in MOVEMENT_TYPES:
        movement_type = "usage"
    label = ("Counted quantity" if movement_type == "stocktake"
             else "Quantity")
    quantity = _prompt(f"  {label}: ")
    m = data.record_movement({
        "item_id": iid, "quantity": quantity, "movement_type": movement_type,
        "room": _prompt("  Room (optional): "),
        "staff_id": _prompt("  Your staff ID (optional): "),
        "reference": _prompt("  Reference (PO / delivery note, optional): "),
        "notes": _prompt("  Notes: "),
    })
    item = data.get_item(iid)
    assert item is not None
    print(f"\n  {m.movement_type} of {m.quantity:+g} {item.unit} — "
          f"{item.name} now at {item.quantity:g} {item.unit}.")
    if item.needs_reorder:
        print(f"  ⚠ At or below the reorder level — order "
              f"{item.suggested_order:g} {item.unit}.")


@_safe
def open_movements() -> None:
    iid = _prompt("  Item ID (blank = all): ")
    rows = data.list_movements(item_id=iid or None)
    if not rows:
        print("  (no movements)")
        return
    print(f"\n  {'ID':<8} {'Date':<12} {'Item':<26} {'Type':<11} {'Qty':>9} "
          f"{'Reference':<16} {'By'}")
    print(f"  {'-'*8} {'-'*12} {'-'*26} {'-'*11} {'-'*9} {'-'*16} {'-'*16}")
    for m in rows[:60]:
        print(f"  {m.movement_id:<8} {m.movement_date:<12} "
              f"{(m.item_name or m.item_id)[:26]:<26} {m.movement_type:<11} "
              f"{m.quantity:>+9g} {(m.reference or '-')[:16]:<16} "
              f"{m.staff_name or m.staff_id or '-'}")
    _prompt("  Press Enter to continue...")


@_safe
def open_alerts() -> None:
    alerts = data.reorder_alerts()
    print("\n  ── Stock Alerts ──")
    if not alerts:
        print("  Nothing needs ordering and nothing is near its expiry date.")
    for a in alerts:
        mark = "!!" if a.severity == "urgent" else " !"
        print(f"  {mark} {a.item.name[:30]:<30} {a.reason:<14} {a.detail}")
    _prompt("  Press Enter to continue...")


@_safe
def open_reorder_list() -> None:
    supplier = _prompt("  Supplier ID (blank = all): ")
    rows = data.reorder_list(supplier_id=supplier or None)
    print("\n  ── Reorder List ──")
    if not rows:
        print("  Nothing needs ordering.")
        _prompt("  Press Enter to continue...")
        return
    print(f"  {'Item':<30} {'Qty':>9} {'Unit':<8} {'Price':>9} {'Total':>10}  "
          f"Supplier")
    print(f"  {'-'*30} {'-'*9} {'-'*8} {'-'*9} {'-'*10}  {'-'*20}")
    for r in rows:
        print(f"  {r['description'][:30]:<30} {r['quantity']:>9g} "
              f"{r['unit']:<8} £{r['unit_price']:>8.2f} "
              f"£{r['line_total']:>9.2f}  {r['supplier_name'] or '-'}")
    print(f"\n  Total: £{sum(r['line_total'] for r in rows):.2f}")
    print("  Raise this as a purchase order from Suppliers & Purchase Orders.")
    _prompt("  Press Enter to continue...")


_DISPATCH = {"Consumables & Stock": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching inventory CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
