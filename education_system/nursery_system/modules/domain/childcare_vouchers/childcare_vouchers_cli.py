"""CLI flow for Tax-Free Childcare / Vouchers (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.childcare_vouchers import (
    childcare_vouchers as data,
)
from education_system.nursery_system.modules.domain.childcare_vouchers.childcare_vouchers import (
    SCHEMES,
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


def _print_table(rows: list[data.Voucher]) -> None:
    if not rows:
        print("  (no voucher arrangements)")
        return
    print(f"  {'ID':<9} {'Child':<20} {'Scheme':<28} {'Provider':<16} "
          f"{'Monthly':>9}  {'Status'}")
    print(f"  {'-'*9} {'-'*20} {'-'*28} {'-'*16} {'-'*9}  {'-'*8}")
    for v in rows:
        amt = f"{v.expected_amount:.2f}" if v.expected_amount is not None else "-"
        print(f"  {v.voucher_id:<9} {(v.child_name or '-')[:20]:<20} "
              f"{(v.scheme or '-')[:28]:<28} {(v.provider or '-')[:16]:<16} "
              f"{amt:>9}  {v.status}")


def _print_detail(v: data.Voucher) -> None:
    print(f"\n  ── Voucher arrangement {v.voucher_id} ──")
    print(f"  Child:           {v.child_name or '-'} ({v.pupil_id})")
    print(f"  Scheme:          {v.scheme or '-'}")
    print(f"  Provider:        {v.provider or '-'}")
    print(f"  Account ref:     {v.account_ref or '-'}")
    print(f"  Expected/month:  £{v.expected_amount:.2f}" if v.expected_amount
          is not None else "  Expected/month:  -")
    print(f"  Status:          {v.status}")
    print(f"  Notes:           {v.notes or '-'}")


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


def _collect_fields(existing: data.Voucher | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["scheme"]          = ask(f"Scheme ({'/'.join(SCHEMES)})",
                                    existing.scheme if existing else None)
    fields["provider"]        = ask("Provider (employer / NS&I)",
                                    existing.provider if existing else None)
    fields["account_ref"]     = ask("Account reference",
                                    existing.account_ref if existing else None)
    fields["expected_amount"] = ask("Expected amount / month (£)",
                                    existing.expected_amount if existing else None)
    fields["status"]          = ask(f"Status ({'/'.join(STATUSES)})",
                                    existing.status if existing else "active")
    fields["notes"]           = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: vouchers open_manager")
    while True:
        s = data.summary()
        print("\n  ── Tax-Free Childcare / Vouchers ──")
        print(f"  Arrangements: {s['count']}   Active: {s['active']}   "
              f"Expected/month: £{s['expected_monthly']:.2f}")
        if s["by_scheme"]:
            print("  By scheme: " + "  ".join(
                f"{k}={v}" for k, v in sorted(s["by_scheme"].items())))
        _print_table(data.list_vouchers())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   C) For a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            vid = _prompt("  Arrangement ID: ")
            v = data.get_voucher(vid)
            if v is None:
                print("  No arrangement with that ID.")
            else:
                _print_detail(v)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_vouchers(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Voucher Arrangement ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    v = data.create_voucher(fields)
    print(f"\n  Added {v.scheme or 'arrangement'} for {v.child_name} "
          f"({v.voucher_id}).")


@_safe
def open_edit() -> None:
    vid = _prompt("  Arrangement ID: ")
    if not vid:
        print("  Cancelled.")
        return
    existing = data.get_voucher(vid)
    if existing is None:
        print("  No arrangement with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    v = data.update_voucher(vid, fields)
    print(f"\n  Updated arrangement {v.voucher_id}.")


@_safe
def open_delete() -> None:
    vid = _prompt("  Arrangement ID to delete: ")
    if not vid:
        print("  Cancelled.")
        return
    if data.get_voucher(vid) is None:
        print("  No arrangement with that ID.")
        return
    if _prompt(f"  Delete arrangement {vid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_voucher(vid):
        print(f"  Deleted arrangement {vid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Tax-Free Childcare / Vouchers": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching vouchers CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
