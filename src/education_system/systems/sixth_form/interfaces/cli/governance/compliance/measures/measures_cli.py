"""CLI for the DfE 16-18 measures (approximations)."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.governance.compliance.measures import (
    measures as data,
)

logger = logging.getLogger(__name__)


def _input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return raw or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_rows(m: data.MeasureResult, limit: int = 40) -> None:
    if not m.rows:
        print("  (no rows)")
        return
    keys = list(m.rows[0].keys())
    print("  " + " | ".join(k[:14] for k in keys))
    for r in m.rows[:limit]:
        print("  " + " | ".join(str("" if r.get(k) is None else r.get(k))[:14]
                                for k in keys))
    if len(m.rows) > limit:
        print(f"  … {len(m.rows) - limit} more")


def show_measures() -> None:
    year = _input("Academic year", data.current_year())
    print("\n  Calculating…")
    try:
        report = data.compute_all(year)
    except Exception as e:
        logger.exception("measures failed")
        print(f"\n  ✗ {e}")
        _pause()
        return
    while True:
        print()
        print(report.text())
        print("\n  Detail: enter a measure number, or 0 to go back")
        for i, m in enumerate(report.measures, 1):
            print(f"    {i}) {m.label}")
        choice = _input("Select", "0")
        if choice == "0" or not choice.isdigit():
            return
        n = int(choice)
        if 1 <= n <= len(report.measures):
            m = report.measures[n - 1]
            print(f"\n  ── {m.label}: {m.display} ──")
            _print_rows(m)
            _pause()


def run() -> None:
    show_measures()


def dispatch(label: str) -> bool:
    if label != "16-18 Measures":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Measures CLI crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True


__all__ = ["show_measures", "run", "dispatch"]
