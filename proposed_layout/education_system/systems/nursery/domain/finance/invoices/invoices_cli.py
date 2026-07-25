"""CLI flow for Invoices & Fees (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.finance.invoices import invoices as data
from education_system.systems.nursery.domain.finance.invoices.invoices import (
    STATUSES,
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


def _print_table(rows: list[data.Invoice]) -> None:
    if not rows:
        print("  (no invoices)")
        return
    print(f"  {'ID':<9} {'Child':<20} {'Period':<14} {'Total':>9} "
          f"{'Paid':>9} {'Balance':>9}  {'Status'}")
    print(f"  {'-'*9} {'-'*20} {'-'*14} {'-'*9} {'-'*9} {'-'*9}  {'-'*9}")
    for i in rows:
        print(f"  {i.invoice_id:<9} {(i.child_name or '-')[:20]:<20} "
              f"{(i.period or '-')[:14]:<14} {i.total_amount:>9.2f} "
              f"{i.paid:>9.2f} {i.balance:>9.2f}  {i.status}")


def _print_detail(i: data.Invoice) -> None:
    print(f"\n  ── Invoice {i.invoice_id} ──")
    print(f"  Child:            {i.child_name or '-'} ({i.pupil_id})")
    print(f"  Period:           {i.period or '-'}")
    print(f"  Issued / due:     {i.issue_date or '-'} / {i.due_date or '-'}")
    print(f"  Hours × rate:     {i.hours_billed or '-'} × "
          f"{i.hourly_rate or '-'}")
    print(f"  Gross:            £{i.gross_amount:.2f}")
    print(f"  Funded deduction: £{i.funded_deduction:.2f}")
    print(f"  Discount:         £{i.discount_amount:.2f}")
    print(f"  Total due:        £{i.total_amount:.2f}")
    print(f"  Paid:             £{i.paid:.2f}")
    print(f"  Balance:          £{i.balance:.2f}")
    print(f"  Status:           {i.status}")
    print(f"  Notes:            {i.notes or '-'}")


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


def _collect_fields(existing: data.Invoice | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["period"]           = ask("Period (e.g. June 2025)",
                                     existing.period if existing else None)
    fields["issue_date"]       = ask("Issue date (YYYY-MM-DD)",
                                     existing.issue_date if existing else None)
    fields["due_date"]         = ask("Due date (YYYY-MM-DD)",
                                     existing.due_date if existing else None)
    fields["hours_billed"]     = ask("Hours billed",
                                     existing.hours_billed if existing else None)
    fields["hourly_rate"]      = ask("Hourly rate (£)",
                                     existing.hourly_rate if existing else None)
    fields["gross_amount"]     = ask("Gross amount (£)",
                                     existing.gross_amount if existing else None)
    fields["funded_deduction"] = ask("Funded-hours deduction (£)",
                                     existing.funded_deduction if existing else None)
    fields["discount_amount"]  = ask("Discount (£)",
                                     existing.discount_amount if existing else None)
    fields["status"]           = ask(f"Status ({'/'.join(STATUSES)})",
                                     existing.status if existing else "draft")
    fields["notes"]            = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: invoices open_manager")
    while True:
        s = data.summary()
        print("\n  ── Invoices & Fees ──")
        print(f"  Invoices: {int(s['count'])}   Billed: £{s['billed']:.2f}   "
              f"Collected: £{s['collected']:.2f}   "
              f"Outstanding: £{s['outstanding']:.2f}")
        _print_table(data.list_invoices())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   S) Set status    C) For a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            iid = _prompt("  Invoice ID: ")
            i = data.get_invoice(iid)
            if i is None:
                print("  No invoice with that ID.")
            else:
                _print_detail(i)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "s":
            open_set_status()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_invoices(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Invoice ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    i = data.create_invoice(fields)
    print(f"\n  Created invoice {i.invoice_id} for {i.child_name} "
          f"(£{i.total_amount:.2f}).")


@_safe
def open_edit() -> None:
    iid = _prompt("  Invoice ID: ")
    if not iid:
        print("  Cancelled.")
        return
    existing = data.get_invoice(iid)
    if existing is None:
        print("  No invoice with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    i = data.update_invoice(iid, fields)
    print(f"\n  Updated invoice {i.invoice_id} (total £{i.total_amount:.2f}).")


@_safe
def open_delete() -> None:
    iid = _prompt("  Invoice ID to delete: ")
    if not iid:
        print("  Cancelled.")
        return
    if data.get_invoice(iid) is None:
        print("  No invoice with that ID.")
        return
    if _prompt(f"  Delete invoice {iid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_invoice(iid):
        print(f"  Deleted invoice {iid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_set_status() -> None:
    iid = _prompt("  Invoice ID: ")
    if not iid:
        print("  Cancelled.")
        return
    if data.get_invoice(iid) is None:
        print("  No invoice with that ID.")
        return
    status = _prompt(f"  New status ({'/'.join(STATUSES)}): ").lower()
    i = data.set_status(iid, status)
    print(f"  Invoice {i.invoice_id} is now {i.status}.")


_DISPATCH = {"Invoices & Fees": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching invoices CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
