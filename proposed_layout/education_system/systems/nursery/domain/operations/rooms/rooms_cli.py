"""CLI flow for Rooms & Age Groups (Nursery System).

Provides the interactive manager behind the "Rooms & Age Groups" menu label
and a :func:`dispatch` hook the launcher calls for it. Every handler is
wrapped by :func:`_safe` so a domain or DB error is logged and reported
without tearing down the surrounding menu loop.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.operations.rooms import rooms as data
from education_system.systems.nursery.domain.operations.rooms.rooms import (
    RATIO_OPTIONS,
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
    """Catch unexpected errors in a CLI handler — log and keep the menu alive."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001 - last-resort guard for the menu
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _age_band(r: data.Room) -> str:
    if r.min_age_months is None and r.max_age_months is None:
        return r.age_group or "-"
    lo = "" if r.min_age_months is None else str(r.min_age_months)
    hi = "" if r.max_age_months is None else str(r.max_age_months)
    return f"{lo}-{hi} mo"


def _print_table(rows: list[data.Room]) -> None:
    if not rows:
        print("  (no rooms defined)")
        return
    print(f"  {'ID':<8} {'Name':<18} {'Age band':<12} {'Ratio':<7} "
          f"{'Occupancy':<11} {'Status'}")
    print(f"  {'-'*8} {'-'*18} {'-'*12} {'-'*7} {'-'*11} {'-'*8}")
    for r in rows:
        occ = f"{r.occupancy}/{r.capacity}"
        flag = " FULL" if r.is_full else ""
        print(f"  {r.room_id:<8} {r.name[:18]:<18} {_age_band(r):<12} "
              f"{(r.staff_ratio or '-'):<7} {occ:<11} {r.status}{flag}")


def _print_detail(r: data.Room) -> None:
    print(f"\n  ── Room {r.room_id} ──")
    print(f"  Name:          {r.name}")
    print(f"  Age group:     {r.age_group or '-'}")
    print(f"  Age band:      {_age_band(r)}")
    print(f"  Capacity:      {r.capacity}")
    print(f"  Occupancy:     {r.occupancy} (places left: {r.places_left})")
    print(f"  Staff ratio:   {r.staff_ratio or '-'}")
    print(f"  Room leader:   {r.room_leader_name or r.room_leader or '-'}")
    print(f"  Location:      {r.location or '-'}")
    print(f"  Status:        {r.status}")
    print(f"  Notes:         {r.notes or '-'}")


def _show_leaders() -> None:
    try:
        choices = data.list_leader_choices()
    except Exception:
        logger.exception("Could not load room-leader choices")
        return
    if choices:
        print("  Staff: " + ", ".join(label for _id, label in choices))


def _collect_fields(existing: data.Room | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    fields["name"]           = ask("Room name", existing.name if existing else None)
    fields["age_group"]      = ask("Age group (e.g. 2 to 3 years)",
                                   existing.age_group if existing else None)
    fields["min_age_months"] = ask("Minimum age (months)",
                                   existing.min_age_months if existing else None)
    fields["max_age_months"] = ask("Maximum age (months)",
                                   existing.max_age_months if existing else None)
    fields["capacity"]       = ask("Capacity",
                                   existing.capacity if existing else None)
    ratios = [o for o in RATIO_OPTIONS if o]
    fields["staff_ratio"]    = ask(f"Staff ratio ({'/'.join(ratios)})",
                                   existing.staff_ratio if existing else None)
    _show_leaders()
    fields["room_leader"]    = ask("Room leader (staff ID)",
                                   existing.room_leader if existing else None)
    fields["location"]       = ask("Location",
                                   existing.location if existing else None)
    fields["notes"]          = ask("Notes", existing.notes if existing else None)
    if existing is not None:
        fields["status"] = ask(f"Status ({'/'.join(STATUSES)})", existing.status)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: rooms open_manager")
    show_closed = True
    while True:
        scope = "all" if show_closed else "open only"
        print(f"\n  ── Rooms & Age Groups ({scope}) ──")
        try:
            rows = data.list_rooms(include_closed=show_closed)
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load room list")
            print(f"  Could not load rooms: {e}")
            return
        _print_table(rows)
        print("\n   A) Add room    V) View room    E) Edit room")
        print("   D) Delete room    C) Open/Close room    T) Toggle closed    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            rid = _prompt("  Room ID: ")
            r = data.get_room(rid)
            if r is None:
                print("  No room with that ID.")
            else:
                _print_detail(r)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            open_toggle_status()
        elif choice == "t":
            show_closed = not show_closed
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: rooms open_add")
    print("\n  ── Add Room ──")
    fields = _collect_fields()
    r = data.create_room(fields)
    print(f"\n  Created room {r.room_id} ({r.name}, capacity {r.capacity}).")


@_safe
def open_edit() -> None:
    logger.debug("CLI: rooms open_edit")
    print("\n  ── Edit Room ──")
    rid = _prompt("  Room ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_room(rid)
    if existing is None:
        print("  No room with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    r = data.update_room(rid, fields)
    print(f"\n  Updated room {r.room_id} ({r.name}).")


@_safe
def open_delete() -> None:
    logger.debug("CLI: rooms open_delete")
    print("\n  ── Delete Room ──")
    rid = _prompt("  Room ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_room(rid)
    if existing is None:
        print("  No room with that ID.")
        return
    confirm = _prompt(
        f"  Permanently delete {existing.name} ({rid})? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_room(rid):
        print(f"  Deleted room {rid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_toggle_status() -> None:
    logger.debug("CLI: rooms open_toggle_status")
    rid = _prompt("  Room ID to open/close: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_room(rid)
    if existing is None:
        print("  No room with that ID.")
        return
    new_status = "closed" if existing.status == "open" else "open"
    r = data.set_status(rid, new_status)
    print(f"  Room {r.room_id} is now {r.status}.")


# Maps the launcher menu label (from ``menu.py``) to the manager handler.
_DISPATCH = {
    "Rooms & Age Groups": open_manager,
}


def dispatch(label: str) -> bool:
    """Run the handler for ``label`` if this module owns it; else return False."""
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching rooms CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    """Backwards-compatible entry point — opens the rooms manager screen."""
    open_manager()
