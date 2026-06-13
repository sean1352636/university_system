"""CLI flow for Occupancy & Income (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.occupancy import occupancy as data

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
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


@_safe
def open_dashboard() -> None:
    logger.debug("CLI: occupancy open_dashboard")
    print("\n  ── Occupancy & Income ──")

    rooms = data.list_room_occupancy()
    print("\n  Occupancy by room:")
    print(f"  {'Room':<18} {'Occupancy':<12} {'Places left':<12} {'Fill %'}")
    print(f"  {'-'*18} {'-'*12} {'-'*12} {'-'*7}")
    for r in rooms:
        occ = f"{r.occupancy}/{r.capacity}"
        pct = "-" if r.pct is None else f"{r.pct:g}%"
        print(f"  {r.name[:18]:<18} {occ:<12} {r.places_left:<12} {pct}")

    t = data.occupancy_totals()
    pct = "-" if t["pct"] is None else f"{t['pct']:g}%"
    print(f"\n  Total: {t['occupancy']}/{t['capacity']} places filled "
          f"({pct})   Places left: {t['places_left']}")

    inc = data.income_summary()
    print("\n  Income:")
    print(f"    Invoiced (fees):     £{inc['invoiced']:.2f}")
    print(f"    Collected:           £{inc['collected']:.2f}")
    print(f"    Outstanding:         £{inc['outstanding']:.2f}")
    print(f"    Payments received:   £{inc['payments_received']:.2f}")
    print(f"    Funding claimed:     £{inc['funding_total']:.2f}")
    print(f"    Funding paid:        £{inc['funding_paid']:.2f}")
    total_income = inc["collected"] + inc["funding_paid"]
    print(f"    Total income (paid): £{total_income:.2f}")

    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Occupancy & Income": open_dashboard}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching occupancy CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_dashboard()
