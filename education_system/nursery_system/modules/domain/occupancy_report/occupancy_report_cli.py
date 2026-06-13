"""CLI flow for the Occupancy Report (Nursery System).

Prints the per-room occupancy board (capacity vs active children) with a
setting-wide roll-up, and offers a CSV export. Read-only.
"""

from __future__ import annotations

import logging

from education_system.nursery_system.modules.domain.occupancy_report import (
    occupancy_report as data,
)

logger = logging.getLogger(__name__)


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_report() -> None:
    rows = data.list_room_occupancy()
    s = data.summary()
    print("\n═══ Occupancy Report ═══")
    print(f"  {'Room':<18} {'Age group':<18} {'Cap':>4} {'Used':>5} "
          f"{'Free':>5} {'Occ%':>6}  Status")
    print("  " + "-" * 70)
    for r in rows:
        pct = "-" if r.occupancy_pct is None else f"{r.occupancy_pct:>5}%"
        flag = " (OVER)" if r.over_capacity else ""
        print(f"  {r.name[:18]:<18} {(r.age_group or '-')[:18]:<18} "
              f"{r.capacity:>4} {r.occupied:>5} {r.places_remaining:>5} "
              f"{pct:>6}  {r.status}{flag}")
    print("  " + "-" * 70)
    overall = "-" if s["occupancy_pct"] is None else f"{s['occupancy_pct']}%"
    print(f"  Rooms: {s['rooms']}   Capacity: {s['capacity']}   "
          f"Occupied: {s['occupied']}   Free: {s['places_remaining']}   "
          f"Overall: {overall}")
    print(f"  Full rooms: {s['full_rooms']}   "
          f"Over capacity: {s['over_capacity_rooms']}   "
          f"Unplaced children: {s['unplaced_children']}")


def _export() -> None:
    try:
        raw = input("\n  Export CSV to path (blank = data dir): ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    try:
        res = data.export_csv(raw or None)
        print(f"  ✓ Wrote {res['row_count']} row(s) → {res['path']}")
    except OSError as e:
        print(f"  ✗ {e}")


def run(auth=None) -> None:
    """Entry point for the Occupancy Report CLI screen."""
    while True:
        try:
            _print_report()
        except Exception as e:  # noqa: BLE001
            logger.exception("Occupancy report failed")
            print(f"\n  ✗ Could not build report: {e}")
            _pause()
            return
        print("\n   1) Export to CSV    0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "1":
            _export()
            _pause()
        elif choice == "0" or choice == "":
            return
        else:
            print("  Invalid selection.")


def dispatch(label: str) -> bool:
    if label != "Occupancy Report":
        return False
    run()
    return True
