"""CLI flow for Staff : Child Ratios (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.ratios import ratios as data
from education_system.nursery_system.modules.domain.ratios.ratios import (
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


def _flag(r: data.RoomRatio) -> str:
    if r.compliant is None:
        return "no ratio set"
    return "OK" if r.compliant else f"UNDER by {r.shortfall}"


def _print_table(rows: list[data.RoomRatio]) -> None:
    if not rows:
        print("  (no rooms defined — add rooms first)")
        return
    print(f"  {'Room':<18} {'Ratio':<7} {'Children':<9} {'Staff':<7} "
          f"{'Required':<9} {'Status'}")
    print(f"  {'-'*18} {'-'*7} {'-'*9} {'-'*7} {'-'*9} {'-'*16}")
    for r in rows:
        req = "-" if r.required_staff is None else str(r.required_staff)
        print(f"  {r.name[:18]:<18} {(r.staff_ratio or '-'):<7} {r.children:<9} "
              f"{r.staff:<7} {req:<9} {_flag(r)}")


@_safe
def open_manager() -> None:
    logger.debug("CLI: ratios open_manager")
    while True:
        s = data.summary()
        print("\n  ── Staff : Child Ratios ──")
        print(f"  Rooms: {s['rooms']}   Children: {s['children']}   "
              f"Staff: {s['staff']}   Breaches: {s['breaches']}   "
              f"No ratio set: {s['no_ratio_set']}")
        if s["unplaced_children"]:
            print(f"  ⚠ {s['unplaced_children']} active child(ren) not assigned to "
                  "a known room — not counted in any room above.")
        _print_table(data.list_room_ratios())
        print("\n   R) Set a room's ratio    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "r":
            open_set_ratio()
        else:
            print("  Invalid selection.")


@_safe
def open_set_ratio() -> None:
    rows = data.list_room_ratios()
    if not rows:
        print("  No rooms defined.")
        return
    print("  Rooms: " + ", ".join(f"{r.room_id}={r.name}" for r in rows))
    rid = _prompt("  Room ID: ")
    if not rid:
        print("  Cancelled.")
        return
    ratio = _prompt("  Required ratio (adults:children, e.g. 1:3): ")
    r = data.set_room_ratio(rid, ratio)
    print(f"  {r.name} ratio set to {r.staff_ratio} "
          f"(required staff now {r.required_staff}).")


_DISPATCH = {"Staff : Child Ratios": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching ratios CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
