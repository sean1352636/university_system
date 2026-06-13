"""CLI flow for the Sixth Form KPI Dashboard.

Prints a headline tile-grid, with options to change the rolling window
or the at-risk attendance threshold and refresh.
"""

from __future__ import annotations

import logging
from typing import Callable
from education_system.sixthform_system.modules.domain.reports.kpi_dashboard import kpi_dashboard as data
from education_system.sixthform_system.modules.domain.reports.kpi_dashboard.kpi_dashboard import (
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW_DAYS,
    Snapshot,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    return s or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_snapshot(snap: Snapshot) -> None:
    print()
    print(f"  ═══ KPI Dashboard ═══   generated {snap.generated_at}")
    print(f"  window: last {snap.window_days} days")
    print()
    # Render as a two-column grid of tiles.
    tiles = snap.tiles
    width = 38
    for i in range(0, len(tiles), 2):
        left = tiles[i]
        right = tiles[i + 1] if i + 1 < len(tiles) else None
        l_lbl = f"  {left.label:<20}".ljust(width)
        l_val = f"  {left.value:<20}".ljust(width)
        l_hnt = f"  {left.hint:<20}".ljust(width)
        if right:
            r_lbl = f"{right.label:<20}"
            r_val = f"{right.value:<20}"
            r_hnt = f"{right.hint:<20}"
        else:
            r_lbl = r_val = r_hnt = ""
        print(l_lbl + r_lbl)
        print(l_val + r_val)
        print(l_hnt + r_hnt)
        print()


# ── Submenu ────────────────────────────────────────────────────────

def show_dashboard() -> None:
    window = DEFAULT_WINDOW_DAYS
    threshold = DEFAULT_THRESHOLD
    while True:
        try:
            snap = data.snapshot(window_days=window, threshold_pct=threshold)
        except Exception as e:
            logger.exception("kpi snapshot failed")
            print(f"\n  ✗ Could not load KPIs: {e}")
            _pause()
            return

        _print_snapshot(snap)
        print("  Actions:  R) Refresh   W) Change window   T) Change threshold   "
              "0) Back")
        try:
            choice = input("  Select: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "" or choice == "0":
            return
        if choice == "r":
            continue
        if choice == "w":
            try:
                raw = _input("Window (days)", default=str(window))
                window = max(1, int(raw))
            except (ValueError, _UserAbort):
                print("    Invalid window — keeping previous.")
            continue
        if choice == "t":
            try:
                raw = _input("Threshold (%)", default=str(threshold))
                threshold = max(0.0, min(100.0, float(raw)))
            except (ValueError, _UserAbort):
                print("    Invalid threshold — keeping previous.")
            continue
        print("  Invalid selection.")


# ── Module-level dispatch ──────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Show KPI Dashboard", show_dashboard),
]


def run() -> None:
    show_dashboard()


def dispatch(label: str) -> bool:
    if label != "KPI Dashboard":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("KPI Dashboard CLI crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
