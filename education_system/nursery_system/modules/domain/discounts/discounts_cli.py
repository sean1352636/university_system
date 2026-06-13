"""CLI flow for Sibling Discounts (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.discounts import discounts as data
from education_system.nursery_system.modules.domain.discounts.discounts import (
    DISCOUNT_TYPES,
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


def _print_table(rows: list[data.Discount]) -> None:
    if not rows:
        print("  (no discounts)")
        return
    print(f"  {'ID':<9} {'Child':<20} {'Type':<16} {'Value':<10} "
          f"{'Reason':<22} {'Status'}")
    print(f"  {'-'*9} {'-'*20} {'-'*16} {'-'*10} {'-'*22} {'-'*8}")
    for d in rows:
        print(f"  {d.discount_id:<9} {(d.child_name or '-')[:20]:<20} "
              f"{(d.discount_type or '-')[:16]:<16} {d.value_label:<10} "
              f"{(d.reason or '-')[:22]:<22} {d.status}")


def _print_detail(d: data.Discount) -> None:
    print(f"\n  ── Discount {d.discount_id} ──")
    print(f"  Child:       {d.child_name or '-'} ({d.pupil_id})")
    print(f"  Type:        {d.discount_type or '-'}")
    print(f"  Value:       {d.value_label}")
    print(f"  Reason:      {d.reason or '-'}")
    print(f"  Active:      {d.start_date or '-'} → {d.end_date or 'ongoing'}")
    print(f"  Status:      {d.status}")
    print(f"  Notes:       {d.notes or '-'}")


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


def _collect_fields(existing: data.Discount | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["discount_type"] = ask(f"Type ({'/'.join(DISCOUNT_TYPES)})",
                                  existing.discount_type if existing else None)
    fields["percentage"]    = ask("Percentage (e.g. 10) — leave blank if fixed",
                                  existing.percentage if existing else None)
    fields["fixed_amount"]  = ask("Fixed amount (£) — leave blank if percentage",
                                  existing.fixed_amount if existing else None)
    fields["reason"]        = ask("Reason",
                                  existing.reason if existing else None)
    fields["start_date"]    = ask("Start date (YYYY-MM-DD)",
                                  existing.start_date if existing else None)
    fields["end_date"]      = ask("End date (YYYY-MM-DD, blank = ongoing)",
                                  existing.end_date if existing else None)
    fields["status"]        = ask(f"Status ({'/'.join(STATUSES)})",
                                  existing.status if existing else "active")
    fields["notes"]         = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: discounts open_manager")
    while True:
        s = data.summary()
        print("\n  ── Sibling Discounts ──")
        print(f"  Discounts: {s['count']}   Active: {s['active']}")
        if s["by_type"]:
            print("  By type: " + "  ".join(
                f"{k}={v}" for k, v in sorted(s["by_type"].items())))
        _print_table(data.list_discounts())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   C) For a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            did = _prompt("  Discount ID: ")
            d = data.get_discount(did)
            if d is None:
                print("  No discount with that ID.")
            else:
                _print_detail(d)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_discounts(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Discount ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    d = data.create_discount(fields)
    print(f"\n  Added {d.discount_type or 'discount'} ({d.value_label}) for "
          f"{d.child_name} ({d.discount_id}).")


@_safe
def open_edit() -> None:
    did = _prompt("  Discount ID: ")
    if not did:
        print("  Cancelled.")
        return
    existing = data.get_discount(did)
    if existing is None:
        print("  No discount with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    d = data.update_discount(did, fields)
    print(f"\n  Updated discount {d.discount_id}.")


@_safe
def open_delete() -> None:
    did = _prompt("  Discount ID to delete: ")
    if not did:
        print("  Cancelled.")
        return
    if data.get_discount(did) is None:
        print("  No discount with that ID.")
        return
    if _prompt(f"  Delete discount {did}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_discount(did):
        print(f"  Deleted discount {did}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Sibling Discounts": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching discounts CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
