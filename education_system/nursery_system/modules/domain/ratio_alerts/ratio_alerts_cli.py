"""CLI flow for Live Ratio Alerts (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.ratio_alerts import (
    ratio_alerts as data,
)
from education_system.nursery_system.modules.domain.ratio_alerts.ratio_alerts import (
    CATEGORIES,
    ValidationError,
)

logger = logging.getLogger(__name__)

_MARK = {"breach": "!!", "warning": " !", "info": "  "}


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


def _print_alerts(rows: list[data.Alert]) -> None:
    if not rows:
        print("  No alerts — every room meets its ratio.")
        return
    for a in rows:
        where = f" [{a.room}]" if a.room else ""
        print(f"  {_MARK.get(a.severity, '  ')} {a.severity.upper():<8} "
              f"{a.category:<15}{where} {a.message}")
        if a.detail:
            print(f"       {a.detail}")


def _print_rooms(rows: list[data.RoomState]) -> None:
    if not rows:
        print("  (no rooms defined — add rooms first)")
        return
    print(f"  {'Room':<18} {'Ratio':<7} {'Children':<9} {'Staff':<7} "
          f"{'Absent':<7} {'Required':<9} {'Headroom':<9} {'Status'}")
    print(f"  {'-'*18} {'-'*7} {'-'*9} {'-'*7} {'-'*7} {'-'*9} {'-'*9} {'-'*12}")
    for s in rows:
        if s.compliant is None:
            state = "no ratio set"
        elif s.compliant:
            state = "OK"
        else:
            state = f"UNDER by {s.shortfall}"
        req = "-" if s.required_staff is None else str(s.required_staff)
        head = "-" if s.spare_places is None else str(s.spare_places)
        print(f"  {s.room[:18]:<18} {(s.staff_ratio or '-'):<7} "
              f"{s.children_counted:<9} {s.staff_available:<7} "
              f"{s.staff_absent:<7} {req:<9} {head:<9} {state}")


@_safe
def open_manager() -> None:
    logger.debug("CLI: ratio_alerts open_manager")
    day = data._today()
    while True:
        s = data.summary(day)
        print(f"\n  ── Live Ratio Alerts — {s['date']} ──")
        print(f"  Breaches: {s['breaches']}   Warnings: {s['warnings']}   "
              f"Rooms under ratio: {s['rooms_in_breach']}   "
              f"On the edge: {s['rooms_on_edge']}")
        print(f"  Children counted from: {s['counted_from']}   "
              f"Staffing from: {s['staff_from']}   "
              f"Staff absent: {s['staff_absent']}")
        print()
        _print_rooms(data.room_states(day))
        print()
        _print_alerts(data.list_alerts(day))
        print("\n   D) Change date    B) Breaches only    F) Filter by category")
        print("   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "d":
            day = _prompt("  Date (YYYY-MM-DD): ") or day
        elif choice == "b":
            print()
            _print_alerts(data.breaches(day))
            _prompt("  Press Enter to continue...")
        elif choice == "f":
            print("  Categories: " + ", ".join(CATEGORIES))
            cat = _prompt("  Category: ")
            print()
            _print_alerts(data.list_alerts(day, category=cat or None))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


_DISPATCH = {"Live Ratio Alerts": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching ratio_alerts CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
