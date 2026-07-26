"""CLI flow for the Sixth Form Data Dashboard.

Top-level submenu lists every panel; selecting one prints the panel's
table. "All" prints every panel back-to-back. The rolling window can
be reconfigured at any time.
"""

from __future__ import annotations

import logging
from typing import Callable
from education_system.systems.sixth_form.domain.operations.reporting.data_dashboard import data_dashboard as data
from education_system.systems.sixth_form.domain.operations.reporting.data_dashboard.data_dashboard import (
    DEFAULT_WINDOW_DAYS,
    Panel,
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


def _print_panel(panel: Panel) -> None:
    lbl_col, count_col, extra_col = panel.columns
    print()
    print(f"  ── {panel.name} ──")
    if panel.note:
        print(f"  {panel.note}")
    if not panel.rows:
        return
    if extra_col:
        print(f"  {lbl_col:<32}  {count_col:>10}  {extra_col:>14}")
        print("  " + "-" * 60)
        for r in panel.rows:
            print(f"  {r.label[:32]:<32}  {r.count:>10}  {r.extra:>14}")
    else:
        print(f"  {lbl_col:<32}  {count_col:>10}")
        print("  " + "-" * 46)
        for r in panel.rows:
            print(f"  {r.label[:32]:<32}  {r.count:>10}")
    if panel.total is not None:
        print(f"  total: {panel.total}")


def _show_all(window: int) -> None:
    try:
        snap = data.build_panels(window_days=window)
    except Exception as e:
        logger.exception("data dashboard snapshot failed")
        print(f"\n  ✗ Could not load dashboard: {e}")
        _pause()
        return
    print(f"\n  ═══ Data Dashboard ═══   generated {snap.generated_at}")
    print(f"  window: last {snap.window_days} days")
    for p in snap.panels:
        _print_panel(p)
    _pause()


def _show_single(window: int, idx: int, panels: list[Panel]) -> None:
    if idx < 0 or idx >= len(panels):
        print("  Invalid panel.")
        _pause()
        return
    _print_panel(panels[idx])
    _pause()


def show_dashboard() -> None:
    window = DEFAULT_WINDOW_DAYS
    while True:
        try:
            snap = data.build_panels(window_days=window)
        except Exception as e:
            logger.exception("data dashboard snapshot failed")
            print(f"\n  ✗ Could not load dashboard: {e}")
            _pause()
            return

        print(f"\n  ═══ Data Dashboard ═══   generated {snap.generated_at}")
        print(f"  window: last {snap.window_days} days\n")
        for i, p in enumerate(snap.panels, 1):
            total = f"  ({p.total})" if p.total is not None else ""
            print(f"  {i:>2}) {p.name}{total}")
        print("\n  A) Show all   W) Change window   R) Refresh   0) Back")
        try:
            choice = input("  Select: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "" or choice == "0":
            return
        if choice == "r":
            continue
        if choice == "a":
            _show_all(window)
            continue
        if choice == "w":
            try:
                raw = _input("Window (days)", default=str(window))
                window = max(1, int(raw))
            except (ValueError, _UserAbort):
                print("    Invalid window — keeping previous.")
            continue
        if choice.isdigit():
            _show_single(window, int(choice) - 1, snap.panels)
            continue
        print("  Invalid selection.")


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Show Data Dashboard", show_dashboard),
]


def run() -> None:
    show_dashboard()


def dispatch(label: str) -> bool:
    if label != "Data Dashboard":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Data Dashboard CLI crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
