"""CLI flow for Payments (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.finance.payments import payments as data
from education_system.systems.nursery.domain.finance.payments.payments import (
    METHODS,
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


def _print_table(rows: list[data.Payment]) -> None:
    if not rows:
        print("  (no payments)")
        return
    print(f"  {'ID':<9} {'Date':<12} {'Child':<20} {'Amount':>9}  "
          f"{'Method':<24} {'Invoice'}")
    print(f"  {'-'*9} {'-'*12} {'-'*20} {'-'*9}  {'-'*24} {'-'*9}")
    for p in rows:
        print(f"  {p.payment_id:<9} {(p.payment_date or '-'):<12} "
              f"{(p.child_name or '-')[:20]:<20} {p.amount:>9.2f}  "
              f"{(p.method or '-')[:24]:<24} {p.invoice_id or '-'}")


def _print_detail(p: data.Payment) -> None:
    print(f"\n  ── Payment {p.payment_id} ──")
    print(f"  Child:     {p.child_name or '-'} ({p.pupil_id})")
    print(f"  Amount:    £{p.amount:.2f}")
    print(f"  Method:    {p.method or '-'}")
    print(f"  Date:      {p.payment_date or '-'}")
    print(f"  Invoice:   {p.invoice_id or '-'} ({p.invoice_period or '-'})")
    print(f"  Reference: {p.reference or '-'}")
    print(f"  Notes:     {p.notes or '-'}")


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children:")
        for _id, label in choices:
            print(f"    {label}")


def _collect_fields(existing: data.Payment | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
        open_inv = data.list_open_invoice_choices(pupil_id)
        if open_inv:
            print("  Open invoices: " + ", ".join(lbl for _i, lbl in open_inv))
    fields["invoice_id"]   = ask("Invoice ID (blank if unallocated)",
                                 existing.invoice_id if existing else None)
    fields["amount"]       = ask("Amount (£)",
                                 existing.amount if existing else None)
    fields["method"]       = ask(f"Method ({'/'.join(METHODS)})",
                                 existing.method if existing else None)
    fields["payment_date"] = ask("Payment date (YYYY-MM-DD)",
                                 existing.payment_date if existing else None)
    fields["reference"]    = ask("Reference",
                                 existing.reference if existing else None)
    fields["notes"]        = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: payments open_manager")
    while True:
        s = data.summary()
        print("\n  ── Payments ──")
        print(f"  Payments: {int(s['count'])}   "
              f"Total received: £{s['received']:.2f}")
        _print_table(data.list_payments())
        print("\n   A) Record payment    V) View    E) Edit    D) Delete")
        print("   C) For a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            pid = _prompt("  Payment ID: ")
            p = data.get_payment(pid)
            if p is None:
                print("  No payment with that ID.")
            else:
                _print_detail(p)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_payments(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Record Payment ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    p = data.create_payment(fields)
    print(f"\n  Recorded £{p.amount:.2f} from {p.child_name} ({p.payment_id})."
          + (f" Allocated to {p.invoice_id}." if p.invoice_id else ""))


@_safe
def open_edit() -> None:
    pid = _prompt("  Payment ID: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_payment(pid)
    if existing is None:
        print("  No payment with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    p = data.update_payment(pid, fields)
    print(f"\n  Updated payment {p.payment_id}.")


@_safe
def open_delete() -> None:
    pid = _prompt("  Payment ID to delete: ")
    if not pid:
        print("  Cancelled.")
        return
    if data.get_payment(pid) is None:
        print("  No payment with that ID.")
        return
    if _prompt(f"  Delete payment {pid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_payment(pid):
        print(f"  Deleted payment {pid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Payments": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching payments CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
