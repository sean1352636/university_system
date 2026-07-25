"""
University Bakery Shop — interactive text CLI.

The Bakery Shop is otherwise a large GUI-only app (``app.py`` plus the
``tabs_main`` / ``tabs_advanced`` tab packages). This CLI does **not** try to
mirror all of the GUI's buttons; instead it drives the module's highest-value
*persisted* entities through the Tkinter-free service layer in
``bakery_shop.services.bakery_service`` — which reads/writes the same central
``student_records.db`` and the same ``bakery_*`` tables the GUI uses, so
records created here are visible in the GUI and vice-versa.

Covered areas: Menu / Catering Trays, Sales Orders (POS), Pre-orders,
Inventory (suppliers / reorder rules / purchase orders / batches),
Production Plans, and Subscriptions. Loyalty, promos, gift cards, refunds
workflow, HACCP/QA, staffing, KDS/labels and the many other GUI-only
features are intentionally left to the GUI.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from education_system.systems.university.domain.operations.commerce.bakery_shop.services.bakery_service import (
    MenuManager,
    OrderManager,
    PreorderManager,
    InventoryManager,
    ProductionManager,
    SubscriptionManager,
)


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _prompt_float(text: str, *, allow_blank: bool = True) -> Optional[float]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return float(raw)
        except ValueError:
            print("Please enter a number.")


def _prompt_bool(text: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    raw = input(f"{text} ({d}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "true", "1")


def _pause() -> None:
    input("\nPress Enter to continue...")


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _current_username(auth) -> str:
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return user.get("username") or user.get("name") or "cli-user"
    except Exception:
        pass
    return "cli-user"


def _prompt_items() -> dict:
    """Collect a ``{item_name: qty}`` map interactively (blank name ends)."""
    items: dict[str, int] = {}
    print("Add items (blank item name to finish):")
    while True:
        name = _prompt("  Item name")
        if not name:
            break
        qty = _prompt_int("  Quantity", allow_blank=False) or 0
        if qty > 0:
            items[name] = items.get(name, 0) + qty
    return items


# --------------------------------------------------------------------------- #
# 1. Menu / Catering Trays
# --------------------------------------------------------------------------- #
def _list_trays() -> None:
    active_only = _prompt_bool("Only active trays?", default=False)
    trays = MenuManager.list_trays(active_only=active_only)
    if not trays:
        print("\nNo catering trays defined yet.")
        return
    print(f"\n{'ID':<5}{'Name':<30}{'Serves':<8}{'Price':<10}Active")
    print("-" * 62)
    for t in trays:
        print(f"{t['id']:<5}{(t.get('name') or '')[:29]:<30}"
              f"{t.get('serves') if t.get('serves') is not None else '-':<8}"
              f"£{(t.get('price') or 0):<9.2f}"
              f"{'yes' if t.get('active') else 'no'}")


def _add_tray() -> None:
    name = _prompt("Tray name")
    if not name:
        print("Name is required.")
        return
    price = _prompt_float("Price (£)", allow_blank=False)
    serves = _prompt_int("Serves (optional)") or 0
    items = _prompt_items()
    if not items:
        print("A tray needs at least one item.")
        return
    try:
        tid = MenuManager.add_tray(name, price, items, serves=serves)
        print(f"\n✓ Added catering tray '{name}' (id={tid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_tray() -> None:
    tid = _prompt_int("Tray id", allow_blank=False)
    price = _prompt_float("New price (blank = unchanged)")
    serves = _prompt_int("New serves (blank = unchanged)")
    active_raw = _prompt("Active? (y/n, blank = unchanged)")
    active = None
    if active_raw:
        active = active_raw.lower() in ("y", "yes", "true", "1")
    if price is None and serves is None and active is None:
        print("Nothing to update.")
        return
    try:
        if MenuManager.update_tray(tid, price=price, serves=serves, active=active):
            print(f"\n✓ Updated tray {tid}.")
        else:
            print(f"\nNo tray with id {tid} (or nothing changed).")
    except Exception as e:
        print(f"\n✗ {e}")


def _menu_menu(auth) -> None:
    while True:
        _header("Menu / Catering Trays")
        print("[1] List trays")
        print("[2] Add tray")
        print("[3] Update tray (price / serves / active)")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_trays()
        elif choice == "2":
            _add_tray()
        elif choice == "3":
            _update_tray()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Sales Orders (POS)
# --------------------------------------------------------------------------- #
def _list_orders() -> None:
    orders = OrderManager.list_orders(limit=30)
    if not orders:
        print("\nNo orders recorded yet.")
        return
    print(f"\n{'ID':<5}{'Order':<12}{'When':<18}{'User':<14}{'Total':<10}Refunded")
    print("-" * 68)
    for o in orders:
        print(f"{o['id']:<5}{(o.get('order_id') or '')[:11]:<12}"
              f"{(o.get('timestamp') or '')[:17]:<18}"
              f"{(o.get('username') or '')[:13]:<14}"
              f"£{(o.get('total') or 0):<9.2f}"
              f"{'yes' if o.get('refunded') else 'no'}")


def _view_order() -> None:
    pk = _prompt_int("Order id (numeric)", allow_blank=False)
    order = OrderManager.get_order(pk)
    if not order:
        print(f"\nNo order with id {pk}.")
        return
    print(f"\n--- Order {order.get('order_id')} (id={pk}) ---")
    for key in ("timestamp", "username", "user_type", "subtotal", "discount",
                "total", "payment_method", "refunded", "refund_ref"):
        print(f"  {key:<16}: {order.get(key) if order.get(key) is not None else '-'}")
    try:
        items = json.loads(order.get("items_json") or "{}")
    except (TypeError, ValueError):
        items = {}
    print("  items           :")
    for name, qty in items.items():
        print(f"      {name} × {qty}")


def _create_order(auth) -> None:
    username = _prompt("Customer username", default=_current_username(auth))
    user_type = _prompt("User type (Student/Staff/Admin/Guest)", default="Guest")
    line_items = []
    print("Add line items (blank item name to finish):")
    while True:
        name = _prompt("  Item name")
        if not name:
            break
        qty = _prompt_int("  Quantity", allow_blank=False) or 0
        price = _prompt_float("  Unit price (£)", allow_blank=False)
        line_items.append({"name": name, "qty": qty, "unit_price": price})
    if not line_items:
        print("An order needs at least one line item.")
        return
    discount = _prompt_float("Discount (£, optional)") or 0.0
    payment = _prompt("Payment method (cash/card)", default="cash")
    try:
        res = OrderManager.create_order(
            username, user_type, line_items,
            discount=discount, payment_method=payment)
        print(f"\n✓ Recorded order {res['order_id']} "
              f"(id={res['id']}, total £{res['total']:.2f}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _refund_order() -> None:
    pk = _prompt_int("Order id to refund", allow_blank=False)
    ref = _prompt("Refund reference (optional)")
    try:
        if OrderManager.refund_order(pk, ref or None):
            print(f"\n✓ Refunded order {pk}.")
        else:
            print(f"\nNo un-refunded order with id {pk}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _orders_menu(auth) -> None:
    while True:
        _header("Sales Orders (POS)")
        print("[1] List recent orders")
        print("[2] Create order (sale)")
        print("[3] View order (+ items)")
        print("[4] Refund order")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_orders()
        elif choice == "2":
            _create_order(auth)
        elif choice == "3":
            _view_order()
        elif choice == "4":
            _refund_order()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Pre-orders
# --------------------------------------------------------------------------- #
def _list_preorders() -> None:
    include = _prompt_bool("Include collected/cancelled?", default=False)
    preorders = PreorderManager.list_preorders(include_completed=include)
    if not preorders:
        print("\nNo pre-orders found.")
        return
    print(f"\n{'ID':<5}{'Order':<12}{'User':<14}{'Collect':<18}{'Status':<11}Paid")
    print("-" * 66)
    for p in preorders:
        print(f"{p['id']:<5}{(p.get('order_id') or '')[:11]:<12}"
              f"{(p.get('user') or '')[:13]:<14}"
              f"{(p.get('collection_time') or '')[:17]:<18}"
              f"{(p.get('status') or '')[:10]:<11}"
              f"{'yes' if p.get('paid') else 'no'}")


def _create_preorder(auth) -> None:
    user = _prompt("Customer username", default=_current_username(auth))
    user_type = _prompt("User type (Student/Staff/Admin/Guest)", default="Guest")
    items = _prompt_items()
    if not items:
        print("A pre-order needs at least one item.")
        return
    collection = _prompt("Collection time (YYYY-MM-DD HH:MM)")
    if not collection:
        print("Collection time is required.")
        return
    total = _prompt_float("Total (£, optional)") or 0.0
    notes = _prompt("Notes (optional)")
    payment = _prompt("Payment method (cash/card)", default="card")
    try:
        oid = PreorderManager.create_preorder(
            user, user_type, items, collection,
            total=total, notes=notes, payment_method=payment)
        print(f"\n✓ Created pre-order {oid} for {user}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_preorder_status() -> None:
    pk = _prompt_int("Pre-order id", allow_blank=False)
    status = _prompt("New status (pending/ready/collected/cancelled)")
    if not status:
        print("Status is required.")
        return
    try:
        if PreorderManager.update_status(pk, status):
            print(f"\n✓ Updated pre-order {pk} → {status}.")
        else:
            print(f"\nNo pre-order with id {pk}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _preorders_menu(auth) -> None:
    while True:
        _header("Pre-orders")
        print("[1] List pre-orders")
        print("[2] Create pre-order")
        print("[3] Update pre-order status")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_preorders()
        elif choice == "2":
            _create_preorder(auth)
        elif choice == "3":
            _update_preorder_status()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 4. Inventory
# --------------------------------------------------------------------------- #
def _list_suppliers() -> None:
    suppliers = InventoryManager.list_suppliers()
    if not suppliers:
        print("\nNo suppliers registered yet.")
        return
    print(f"\n{'ID':<5}{'Name':<26}{'Contact':<18}{'Lead(d)':<9}Active")
    print("-" * 62)
    for s in suppliers:
        print(f"{s['id']:<5}{(s.get('name') or '')[:25]:<26}"
              f"{(s.get('contact') or '-')[:17]:<18}"
              f"{s.get('lead_time_days') if s.get('lead_time_days') is not None else '-':<9}"
              f"{'yes' if s.get('active') else 'no'}")


def _add_supplier() -> None:
    name = _prompt("Supplier name")
    if not name:
        print("Name is required.")
        return
    contact = _prompt("Contact name (optional)")
    email = _prompt("Email (optional)")
    phone = _prompt("Phone (optional)")
    lead = _prompt_int("Lead time days (default 3)") or 3
    try:
        sid = InventoryManager.add_supplier(
            name, contact=contact, email=email, phone=phone, lead_time_days=lead)
        print(f"\n✓ Added supplier '{name}' (id={sid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_reorder_rules() -> None:
    rules = InventoryManager.list_reorder_rules()
    if not rules:
        print("\nNo reorder rules set.")
        return
    print(f"\n{'Item':<26}{'Min':<7}{'Reorder':<9}{'Supplier':<10}Auto")
    print("-" * 58)
    for r in rules:
        print(f"{(r.get('item_name') or '')[:25]:<26}"
              f"{r.get('min_stock'):<7}{r.get('reorder_qty'):<9}"
              f"{r.get('supplier_id') if r.get('supplier_id') is not None else '-':<10}"
              f"{'yes' if r.get('auto') else 'no'}")


def _set_reorder_rule() -> None:
    item = _prompt("Item name")
    if not item:
        print("Item name is required.")
        return
    min_stock = _prompt_int("Minimum stock threshold", allow_blank=False)
    reorder_qty = _prompt_int("Reorder quantity", allow_blank=False)
    supplier_id = _prompt_int("Supplier id (optional)")
    unit_cost = _prompt_float("Unit cost (optional)") or 0.0
    auto = _prompt_bool("Auto-generate PO when low?", default=False)
    try:
        InventoryManager.set_reorder_rule(
            item, min_stock=min_stock, reorder_qty=reorder_qty,
            supplier_id=supplier_id, unit_cost=unit_cost, auto=auto)
        print(f"\n✓ Reorder rule set for '{item}'.")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_purchase_orders() -> None:
    status = _prompt("Status filter (draft/sent/received/cancelled, blank = all)")
    pos = InventoryManager.list_purchase_orders(status=status or None)
    if not pos:
        print("\nNo purchase orders found.")
        return
    print(f"\n{'ID':<5}{'PO Number':<22}{'Supplier':<10}{'Status':<12}Total")
    print("-" * 60)
    for p in pos:
        print(f"{p['id']:<5}{(p.get('po_number') or '')[:21]:<22}"
              f"{p.get('supplier_id') if p.get('supplier_id') is not None else '-':<10}"
              f"{(p.get('status') or '')[:11]:<12}"
              f"£{(p.get('total_cost') or 0):.2f}")


def _create_purchase_order(auth) -> None:
    supplier_id = _prompt_int("Supplier id (optional)")
    items = []
    print("Add PO line items (blank item name to finish):")
    while True:
        name = _prompt("  Item name")
        if not name:
            break
        qty = _prompt_int("  Quantity", allow_blank=False) or 0
        cost = _prompt_float("  Unit cost (£)") or 0.0
        items.append({"item": name, "qty": qty, "unit_cost": cost})
    if not items:
        print("A purchase order needs at least one line item.")
        return
    status = _prompt("Status (draft/sent)", default="draft")
    notes = _prompt("Notes (optional)")
    try:
        po_number = InventoryManager.create_purchase_order(
            items, supplier_id=supplier_id, status=status, notes=notes,
            created_by=_current_username(auth))
        print(f"\n✓ Created purchase order {po_number}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _receive_purchase_order() -> None:
    po_id = _prompt_int("Purchase order id to receive", allow_blank=False)
    shelf = _prompt_int("Shelf life days (default 7)") or 7
    try:
        if InventoryManager.receive_purchase_order(po_id, shelf_days=shelf):
            print(f"\n✓ Received PO {po_id}; stock batches created.")
        else:
            print(f"\nNo pending PO with id {po_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_batches() -> None:
    include = _prompt_bool("Include depleted/expired?", default=False)
    batches = InventoryManager.list_batches(include_depleted=include)
    if not batches:
        print("\nNo stock batches found.")
        return
    print(f"\n{'ID':<5}{'Item':<24}{'Qty':<7}{'Expiry':<12}{'Status':<10}Lot")
    print("-" * 70)
    for b in batches:
        print(f"{b['id']:<5}{(b.get('item_name') or '')[:23]:<24}"
              f"{b.get('quantity'):<7}{(b.get('expiry_date') or '')[:11]:<12}"
              f"{(b.get('status') or '')[:9]:<10}"
              f"{(b.get('lot_number') or '-')}")


def _inventory_menu(auth) -> None:
    while True:
        _header("Inventory")
        print("[1] List suppliers")
        print("[2] Add supplier")
        print("[3] List reorder rules")
        print("[4] Set reorder rule")
        print("[5] List purchase orders")
        print("[6] Create purchase order")
        print("[7] Receive purchase order")
        print("[8] List stock batches")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_suppliers()
        elif choice == "2":
            _add_supplier()
        elif choice == "3":
            _list_reorder_rules()
        elif choice == "4":
            _set_reorder_rule()
        elif choice == "5":
            _list_purchase_orders()
        elif choice == "6":
            _create_purchase_order(auth)
        elif choice == "7":
            _receive_purchase_order()
        elif choice == "8":
            _list_batches()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 5. Production Plans
# --------------------------------------------------------------------------- #
def _list_plans() -> None:
    plan_date = _prompt("Filter by plan date (YYYY-MM-DD, blank = all)")
    plans = ProductionManager.list_plans(plan_date=plan_date or None)
    if not plans:
        print("\nNo production plans found.")
        return
    print(f"\n{'ID':<5}{'Date':<12}{'Item':<22}{'Forecast':<10}{'Batch':<8}"
          f"{'Batches':<9}Planned")
    print("-" * 74)
    for p in plans:
        print(f"{p['id']:<5}{(p.get('plan_date') or '')[:11]:<12}"
              f"{(p.get('item_name') or '')[:21]:<22}"
              f"{p.get('forecast_qty'):<10}{p.get('batch_size'):<8}"
              f"{p.get('planned_batches'):<9}{p.get('planned_qty')}")


def _save_plan(auth) -> None:
    plan_date = _prompt("Plan date (YYYY-MM-DD)",
                        default=datetime.now().strftime("%Y-%m-%d"))
    item = _prompt("Item name")
    if not item:
        print("Item name is required.")
        return
    forecast = _prompt_int("Forecast quantity", allow_blank=False)
    batch_size = _prompt_int("Batch size", allow_blank=False)
    try:
        res = ProductionManager.save_plan(
            plan_date, item, forecast, batch_size,
            created_by=_current_username(auth))
        print(f"\n✓ Saved plan for {item} on {plan_date}: "
              f"{res['planned_batches']} batch(es), {res['planned_qty']} units.")
    except Exception as e:
        print(f"\n✗ {e}")


def _production_menu(auth) -> None:
    while True:
        _header("Production Plans")
        print("[1] List plans")
        print("[2] Save / update plan")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_plans()
        elif choice == "2":
            _save_plan(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 6. Subscriptions
# --------------------------------------------------------------------------- #
def _list_subscriptions() -> None:
    active_only = _prompt_bool("Only active subscriptions?", default=False)
    subs = SubscriptionManager.list_subscriptions(active_only=active_only)
    if not subs:
        print("\nNo subscriptions found.")
        return
    print(f"\n{'ID':<5}{'User':<14}{'Plan':<22}{'Freq':<10}{'Next':<12}Active")
    print("-" * 68)
    for s in subs:
        print(f"{s['id']:<5}{(s.get('user') or '')[:13]:<14}"
              f"{(s.get('plan_name') or '')[:21]:<22}"
              f"{(s.get('frequency') or '')[:9]:<10}"
              f"{(s.get('next_delivery') or '')[:11]:<12}"
              f"{'yes' if s.get('active') else 'no'}")


def _create_subscription(auth) -> None:
    user = _prompt("Customer username", default=_current_username(auth))
    plan = _prompt("Plan name")
    if not plan:
        print("Plan name is required.")
        return
    items = _prompt_items()
    if not items:
        print("A subscription needs at least one item.")
        return
    freq = _prompt("Frequency (weekly/biweekly/monthly)", default="weekly")
    price = _prompt_float("Price per delivery (£, optional)") or 0.0
    try:
        sid = SubscriptionManager.create_subscription(
            user, plan, items, freq, price=price)
        print(f"\n✓ Created subscription {sid} for {user}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _cancel_subscription() -> None:
    sid = _prompt_int("Subscription id to cancel", allow_blank=False)
    try:
        if SubscriptionManager.cancel_subscription(sid):
            print(f"\n✓ Cancelled subscription {sid}.")
        else:
            print(f"\nNo active subscription with id {sid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _subscriptions_menu(auth) -> None:
    while True:
        _header("Subscriptions")
        print("[1] List subscriptions")
        print("[2] Create subscription")
        print("[3] Cancel subscription")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_subscriptions()
        elif choice == "2":
            _create_subscription(auth)
        elif choice == "3":
            _cancel_subscription()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_bakery_menu(auth) -> None:
    """Run the Bakery Shop CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("       UNIVERSITY BAKERY SHOP")
        print("=" * 50)
        print("1. Menu / Catering Trays")
        print("2. Sales Orders (POS)")
        print("3. Pre-orders")
        print("4. Inventory")
        print("5. Production Plans")
        print("6. Subscriptions")
        print("7. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-7): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _menu_menu(auth)
            elif choice == "2":
                _orders_menu(auth)
            elif choice == "3":
                _preorders_menu(auth)
            elif choice == "4":
                _inventory_menu(auth)
            elif choice == "5":
                _production_menu(auth)
            elif choice == "6":
                _subscriptions_menu(auth)
            elif choice == "7":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
