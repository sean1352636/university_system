"""CLI flow for Suppliers & Purchase Orders (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

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


@_safe
def open_manager() -> None:
    logger.debug("CLI: purchasing open_manager")
    while True:
        s = data.summary()
        print("\n  ── Suppliers & Purchase Orders ──")
        print(f"  Suppliers: {s['active_suppliers']} active   "
              f"Open orders: {s['open_orders']}   "
              f"Committed spend: £{s['committed_spend']:.2f}")
        print(f"  Awaiting approval: {s['awaiting_approval']}   "
              f"Awaiting delivery: {s['awaiting_delivery']}   "
              f"Unpaid: {s['unpaid']} (£{s['unpaid_value']:.2f})   "
              f"Paid this year: £{s['spend_this_year']:.2f}")
        if s["overdue"]:
            print(f"  ⚠ {s['overdue']} supplier invoice(s) past their due date.")
        print("\n   O) Purchase orders    S) Suppliers    A) Approvals queue")
        print("   R) Raise from the stock reorder list    L) Limits    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "o":
            open_orders()
        elif choice == "s":
            open_suppliers()
        elif choice == "a":
            open_approvals()
        elif choice == "r":
            open_from_reorder()
        elif choice == "l":
            open_limits()
        else:
            print("  Invalid selection.")


@_safe
def open_limits() -> None:
    print("\n  ── Approval Limits ──")
    for role, limit in APPROVAL_LIMITS.items():
        shown = "no limit" if limit is None else f"£{limit:,.2f}"
        print(f"    {role:<20} {shown}")
    print("\n  An order is approved by the most junior role whose limit covers "
          "the total.")
    _prompt("  Press Enter to continue...")


# ── Suppliers ────────────────────────────────────────────────────────────────

def _print_suppliers(rows: list[data.Supplier]) -> None:
    if not rows:
        print("  (no suppliers)")
        return
    print(f"  {'ID':<8} {'Name':<28} {'Category':<22} {'Contact':<20} "
          f"{'Terms':<7} {'Status'}")
    print(f"  {'-'*8} {'-'*28} {'-'*22} {'-'*20} {'-'*7} {'-'*8}")
    for s in rows:
        print(f"  {s.supplier_id:<8} {s.name[:28]:<28} "
              f"{(s.category or '-')[:22]:<22} "
              f"{(s.contact_name or '-')[:20]:<20} "
              f"{str(s.payment_terms_days) + 'd':<7} {s.status}")


@_safe
def open_suppliers() -> None:
    while True:
        print("\n  ── Suppliers ──")
        _print_suppliers(data.list_suppliers())
        print("\n   A) Add    E) Edit    D) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_supplier()
        elif choice == "e":
            open_edit_supplier()
        elif choice == "d":
            sid = _prompt("  Supplier ID to delete: ")
            if sid and _prompt(f"  Delete {sid}? (y/N): ").lower() == "y":
                print(f"  Deleted {sid}." if data.delete_supplier(sid)
                      else "  No supplier with that ID.")
        else:
            print("  Invalid selection.")


def _collect_supplier(existing: data.Supplier | None = None) -> dict[str, str]:
    print(f"  Categories: {', '.join(SUPPLIER_CATEGORIES)}")
    return {
        "name": _ask("Name", existing.name if existing else None),
        "category": _ask("Category", existing.category if existing else None),
        "contact_name": _ask("Contact name",
                             existing.contact_name if existing else None),
        "email": _ask("Email", existing.email if existing else None),
        "phone": _ask("Phone", existing.phone if existing else None),
        "account_number": _ask("Account number",
                               existing.account_number if existing else None),
        "payment_terms_days": _ask(
            "Payment terms (days)",
            existing.payment_terms_days if existing else 30),
        "status": _ask(f"Status ({'/'.join(SUPPLIER_STATUSES)})",
                       existing.status if existing else "active"),
        "notes": _ask("Notes", existing.notes if existing else None),
    }


@_safe
def open_add_supplier() -> None:
    print("\n  ── Add Supplier ──")
    s = data.create_supplier(_collect_supplier())
    print(f"\n  Added {s.name} ({s.supplier_id}).")


@_safe
def open_edit_supplier() -> None:
    sid = _prompt("  Supplier ID: ")
    existing = data.get_supplier(sid)
    if existing is None:
        print("  No supplier with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    s = data.update_supplier(sid, _collect_supplier(existing))
    print(f"\n  Updated {s.name}.")


# ── Orders ───────────────────────────────────────────────────────────────────

def _print_orders(rows: list[data.PurchaseOrder]) -> None:
    if not rows:
        print("  (no purchase orders)")
        return
    print(f"  {'PO':<8} {'Supplier':<26} {'Raised':<12} {'Lines':>6} "
          f"{'Total':>11} {'Status':<11} {'Note'}")
    print(f"  {'-'*8} {'-'*26} {'-'*12} {'-'*6} {'-'*11} {'-'*11} {'-'*20}")
    for o in rows:
        note = "OVERDUE" if o.overdue else (o.invoice_ref or "")
        print(f"  {o.po_id:<8} {(o.supplier_name or o.supplier_id)[:26]:<26} "
              f"{o.order_date:<12} {len(o.lines):>6} £{o.total:>10.2f} "
              f"{o.status:<11} {note}")


def _print_order_detail(o: data.PurchaseOrder) -> None:
    print(f"\n  ── Purchase order {o.po_id} ──")
    print(f"  Supplier:    {o.supplier_name or o.supplier_id}")
    print(f"  Raised:      {o.order_date} by "
          f"{o.raised_by_name or o.raised_by or '-'}")
    print(f"  Required by: {o.required_by or '-'}")
    print(f"  Status:      {o.status}")
    if o.approved_at:
        print(f"  Approved by: {o.approved_by_name or o.approved_by} at "
              f"{o.approved_at}")
        if o.approval_note:
            print(f"  Note:        {o.approval_note}")
    if o.invoice_ref:
        print(f"  Invoice:     {o.invoice_ref} dated {o.invoice_date}, "
              f"due {o.invoice_due}")
    if o.paid_at:
        print(f"  Paid:        {o.paid_at}")
    print()
    if not o.lines:
        print("  (no lines)")
    else:
        print(f"  {'Line':<8} {'Description':<32} {'Qty':>8} {'Unit':<8} "
              f"{'Price':>9} {'Total':>10} {'Recd':>7}")
        for line in o.lines:
            print(f"  {line.line_id:<8} {line.description[:32]:<32} "
                  f"{line.quantity:>8g} {line.unit:<8} "
                  f"£{line.unit_price:>8.2f} £{line.line_total:>9.2f} "
                  f"{line.received_quantity:>7g}")
    print(f"\n  Total: £{o.total:.2f}   "
          f"Needs a {data.required_role(o.total)} to approve.")
    nxt = ", ".join(o.next_statuses()) or "nothing — it is closed"
    print(f"  Can move to: {nxt}")


@_safe
def open_orders() -> None:
    while True:
        print("\n  ── Purchase Orders ──")
        _print_orders(data.list_orders())
        print("\n   V) View    N) New order    L) Add a line    S) Submit")
        print("   A) Approve    J) Reject    O) Mark ordered    R) Receive")
        print("   I) Record invoice    P) Mark paid    C) Cancel    X) Delete")
        print("   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        handlers = {
            "v": open_view_order, "n": open_new_order, "l": open_add_line,
            "s": open_submit, "a": open_approve, "j": open_reject,
            "o": open_mark_ordered, "r": open_receive, "i": open_invoice,
            "p": open_pay, "c": open_cancel, "x": open_delete_order,
        }
        handler = handlers.get(choice)
        if handler is None:
            print("  Invalid selection.")
        else:
            handler()


@_safe
def open_view_order() -> None:
    po_id = _prompt("  PO ID: ")
    o = data.get_order(po_id)
    if o is None:
        print("  No purchase order with that ID.")
        return
    _print_order_detail(o)
    _prompt("  Press Enter to continue...")


@_safe
def open_new_order() -> None:
    print("\n  ── Raise a Purchase Order ──")
    choices = data.list_supplier_choices()
    if not choices:
        print("  Add a supplier first.")
        return
    for sid, label in choices:
        print(f"    {sid}  {label}")
    o = data.create_order({
        "supplier_id": _prompt("  Supplier ID: "),
        "order_date": _prompt("  Order date (blank = today): "),
        "required_by": _prompt("  Required by (optional): "),
        "raised_by": _prompt("  Your staff ID: "),
        "notes": _prompt("  Notes: "),
    })
    print(f"\n  Raised draft {o.po_id}. Add lines, then submit it.")


@_safe
def open_add_line() -> None:
    po_id = _prompt("  PO ID: ")
    if not po_id:
        print("  Cancelled.")
        return
    from education_system.systems.nursery.domain.operations.inventory import (
        inventory as _inventory,
    )
    try:
        items = _inventory.list_item_choices()
    except Exception:
        items = []
    if items:
        print("  Stock items (linking one books the delivery into stock):")
        for iid, label in items[:30]:
            print(f"    {iid}  {label}")
    line = data.add_line(po_id, {
        "item_id": _prompt("  Stock item ID (blank = free text): "),
        "description": _prompt("  Description: "),
        "quantity": _prompt("  Quantity: "),
        "unit": _prompt("  Unit [each]: "),
        "unit_price": _prompt("  Unit price (£): "),
        "notes": _prompt("  Notes: "),
    })
    o = data.get_order(po_id)
    assert o is not None
    print(f"\n  Added line {line.line_id} (£{line.line_total:.2f}). "
          f"Order total now £{o.total:.2f}.")


@_safe
def open_submit() -> None:
    po_id = _prompt("  PO ID to submit: ")
    o = data.submit_order(po_id)
    print(f"  {o.po_id} submitted (£{o.total:.2f}). Needs a "
          f"{data.required_role(o.total)} to approve.")


@_safe
def open_approve() -> None:
    po_id = _prompt("  PO ID to approve: ")
    if not po_id:
        print("  Cancelled.")
        return
    o = data.get_order(po_id)
    if o is None:
        print("  No purchase order with that ID.")
        return
    print(f"  {o.po_id}: £{o.total:.2f} to "
          f"{o.supplier_name or o.supplier_id} — needs a "
          f"{data.required_role(o.total)}.")
    staff_id = _prompt("  Your staff ID: ")
    note = _prompt("  Note (optional): ")
    out = data.approve_order(po_id, staff_id, note or None)
    print(f"  Approved {out.po_id}.")


@_safe
def open_reject() -> None:
    po_id = _prompt("  PO ID to reject: ")
    staff_id = _prompt("  Your staff ID: ")
    note = _prompt("  Reason: ")
    out = data.reject_order(po_id, staff_id, note or None)
    print(f"  Rejected {out.po_id}.")


@_safe
def open_mark_ordered() -> None:
    po_id = _prompt("  PO ID placed with the supplier: ")
    print(f"  {data.mark_ordered(po_id).po_id} marked as ordered.")


@_safe
def open_receive() -> None:
    po_id = _prompt("  PO ID received: ")
    if not po_id:
        print("  Cancelled.")
        return
    day = _prompt("  Received date (blank = today): ")
    staff_id = _prompt("  Your staff ID: ")
    book = _prompt("  Book stock lines into inventory? (Y/n): ").lower() != "n"
    o = data.receive_order(po_id, received_date=day or None,
                           staff_id=staff_id or None, book_into_stock=book)
    linked = sum(1 for line in o.lines if line.item_id)
    print(f"  {o.po_id} received.")
    if book and linked:
        print(f"  {linked} line(s) booked into stock — no re-keying needed.")


@_safe
def open_invoice() -> None:
    po_id = _prompt("  PO ID: ")
    ref = _prompt("  Supplier invoice reference: ")
    date = _prompt("  Invoice date (blank = today): ")
    o = data.record_invoice(po_id, ref, invoice_date=date or None)
    print(f"  Invoice {o.invoice_ref} recorded, due {o.invoice_due}.")


@_safe
def open_pay() -> None:
    po_id = _prompt("  PO ID paid: ")
    date = _prompt("  Paid date (blank = today): ")
    o = data.mark_paid(po_id, paid_date=date or None)
    print(f"  {o.po_id} marked paid on {o.paid_at} (£{o.total:.2f}).")


@_safe
def open_cancel() -> None:
    po_id = _prompt("  PO ID to cancel: ")
    note = _prompt("  Reason: ")
    print(f"  {data.cancel_order(po_id, note or None).po_id} cancelled.")


@_safe
def open_delete_order() -> None:
    po_id = _prompt("  PO ID to delete: ")
    if po_id and _prompt(f"  Delete {po_id}? (y/N): ").lower() == "y":
        print(f"  Deleted {po_id}." if data.delete_order(po_id)
              else "  No purchase order with that ID.")


@_safe
def open_approvals() -> None:
    rows = data.awaiting_approval()
    print("\n  ── Awaiting Approval ──")
    if not rows:
        print("  Nothing is waiting for a signature.")
    else:
        for o in rows:
            print(f"  {o.po_id}  £{o.total:>9.2f}  "
                  f"{(o.supplier_name or o.supplier_id)[:26]:<26} "
                  f"needs a {data.required_role(o.total)}")
    _prompt("  Press Enter to continue...")


@_safe
def open_from_reorder() -> None:
    print("\n  ── Raise an Order From the Stock Reorder List ──")
    choices = data.list_supplier_choices()
    for sid, label in choices:
        print(f"    {sid}  {label}")
    sid = _prompt("  Supplier ID: ")
    if not sid:
        print("  Cancelled.")
        return
    o = data.create_order_from_reorder_list(
        sid, raised_by=_prompt("  Your staff ID: ") or None)
    print(f"\n  Raised draft {o.po_id} with {len(o.lines)} line(s), "
          f"£{o.total:.2f}.")
    _print_order_detail(o)
    _prompt("  Press Enter to continue...")


_DISPATCH = {"Suppliers & Purchase Orders": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching purchasing CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
