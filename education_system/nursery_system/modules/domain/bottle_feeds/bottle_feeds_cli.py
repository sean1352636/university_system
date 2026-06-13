"""CLI flow for Bottle Feeds (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.bottle_feeds import (
    bottle_feeds as data,
)
from education_system.nursery_system.modules.domain.bottle_feeds.bottle_feeds import (
    MILK_TYPES,
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


def _print_table(rows: list[data.BottleFeed]) -> None:
    if not rows:
        print("  (no bottle-feed records)")
        return
    print(f"  {'ID':<8} {'Date':<11} {'Time':<6} {'Child':<20} "
          f"{'Milk':<22} {'Offer':<6} {'Taken':<6} {'Temp'}")
    print(f"  {'-'*8} {'-'*11} {'-'*6} {'-'*20} {'-'*22} {'-'*6} {'-'*6} {'-'*4}")
    for r in rows:
        offered = str(r.offered_ml) if r.offered_ml is not None else "-"
        taken = str(r.taken_ml) if r.taken_ml is not None else "-"
        temp = "Y" if r.temperature_checked else "N"
        print(f"  {r.feed_id:<8} {r.feed_date:<11} {(r.feed_time or '-'):<6} "
              f"{(r.child_name or '-')[:20]:<20} {r.milk_type[:22]:<22} "
              f"{offered:<6} {taken:<6} {temp}")


def _print_detail(r: data.BottleFeed) -> None:
    print(f"\n  ── Bottle feed {r.feed_id} ──")
    print(f"  Child:        {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Date / time:  {r.feed_date}  {r.feed_time or '-'}")
    print(f"  Milk type:    {r.milk_type}")
    print(f"  Offered (ml): {r.offered_ml if r.offered_ml is not None else '-'}")
    print(f"  Taken (ml):   {r.taken_ml if r.taken_ml is not None else '-'}")
    print(f"  Temp checked: {'Yes' if r.temperature_checked else 'No'}")
    print(f"  Winded:       {'Yes' if r.winded else 'No'}")
    print(f"  Staff:        {r.staff_name or '-'} ({r.staff_id or '-'})")
    print(f"  Notes:        {r.notes or '-'}")


def _pick(label: str, choices: list[tuple[str, str]]) -> str | None:
    if not choices:
        print(f"  (no {label} available)")
        return None
    print(f"  {label.capitalize()}:")
    for i, (_id, text) in enumerate(choices, 1):
        print(f"    {i}) {text}")
    sel = _prompt(f"  Select {label} (number, blank to skip): ")
    if not sel:
        return None
    try:
        idx = int(sel)
    except ValueError:
        print("  Invalid selection.")
        return None
    if 1 <= idx <= len(choices):
        return choices[idx - 1][0]
    print("  Out of range.")
    return None


def _pick_milk(current: str | None = None) -> str:
    print("  Milk type:")
    for i, m in enumerate(MILK_TYPES, 1):
        print(f"    {i}) {m}")
    cur = current or "Formula"
    sel = _prompt(f"  Select milk type [{cur}]: ")
    if not sel:
        return cur
    try:
        idx = int(sel)
        if 1 <= idx <= len(MILK_TYPES):
            return MILK_TYPES[idx - 1]
    except ValueError:
        pass
    print("  Keeping current.")
    return cur


def _ask_yn(label: str, default_yes: bool) -> str:
    d = "Y/n" if default_yes else "y/N"
    v = _prompt(f"  {label}? ({d}): ").lower()
    if not v:
        return "y" if default_yes else "n"
    return "y" if v in ("y", "yes") else "n"


def _collect_fields(existing: data.BottleFeed | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    fields["feed_date"] = ask("Feed date (YYYY-MM-DD, blank=today)",
                              existing.feed_date if existing else None)
    fields["feed_time"] = ask("Feed time (HH:MM)",
                              existing.feed_time if existing else None)
    fields["milk_type"] = _pick_milk(existing.milk_type if existing else None)
    fields["offered_ml"] = ask("Offered (ml)",
                               existing.offered_ml if existing else None)
    fields["taken_ml"] = ask("Taken (ml)",
                             existing.taken_ml if existing else None)
    temp_default = bool(existing.temperature_checked) if existing else True
    fields["temperature_checked"] = _ask_yn("Temperature checked", temp_default)
    winded_default = bool(existing.winded) if existing else False
    fields["winded"] = _ask_yn("Winded", winded_default)
    staff = _pick("staff", data.list_staff_choices())
    if staff is not None:
        fields["staff_id"] = staff
    elif existing is not None:
        fields["staff_id"] = existing.staff_id or ""
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: bottle_feeds open_manager")
    date_filter: str | None = None
    while True:
        scope = f"date {date_filter}" if date_filter else "all dates"
        print(f"\n  ── Bottle Feeds ({scope}) ──")
        _print_table(data.list_records(feed_date=date_filter))
        print("\n   L) List by date    A) Add    V) View")
        print("   E) Edit    D) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "l":
            d = _prompt("  Filter date (YYYY-MM-DD, blank=all): ")
            date_filter = d or None
        elif choice == "a":
            open_add()
        elif choice == "v":
            rid = _prompt("  Feed ID: ")
            r = data.get_record(rid)
            if r is None:
                print("  No record with that ID.")
            else:
                _print_detail(r)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: bottle_feeds open_add")
    print("\n  ── Add Bottle Feed ──")
    pid = _pick("child", data.list_pupil_choices())
    if not pid:
        print("  Cancelled (no child selected).")
        return
    fields = _collect_fields()
    fields["pupil_id"] = pid
    r = data.create_record(fields)
    print(f"\n  Created bottle-feed record {r.feed_id} for {r.child_name}.")


@_safe
def open_edit() -> None:
    logger.debug("CLI: bottle_feeds open_edit")
    rid = _prompt("  Feed ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    r = data.update_record(rid, fields)
    print(f"\n  Updated bottle-feed record {r.feed_id}.")


@_safe
def open_delete() -> None:
    logger.debug("CLI: bottle_feeds open_delete")
    rid = _prompt("  Feed ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete bottle-feed record {rid} for {existing.child_name}? (y/N): "
    ).lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Bottle Feeds": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching bottle_feeds CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
