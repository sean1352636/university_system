"""CLI flow for Ofsted Readiness (Nursery System).

Prints an inspection-readiness scorecard (grade + ok/warning/fail counts) and
the underlying EYFS welfare checks grouped by area, each with a status marker
and any suggested action. Offers a CSV export. Read-only.
"""

from __future__ import annotations

import logging

from education_system.systems.nursery.domain.governance.compliance.ofsted import ofsted as data

logger = logging.getLogger(__name__)

_MARKERS = {"ok": "✓", "warning": "⚠", "fail": "✗", "info": "·"}


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_report() -> None:
    checks = data.readiness()
    s = data.score()
    print("\n═══ Ofsted Readiness ═══")
    print(f"  Grade: {s['grade']}   ({s['pct']}% ready)")
    print(f"  ✓ OK: {s['ok']}   ⚠ Warnings: {s['warning']}   "
          f"✗ Failures: {s['fail']}   · Info: {s['info']}")
    print("  " + "-" * 70)
    current_area = None
    for c in checks:
        if c.area != current_area:
            current_area = c.area
            print(f"\n  {c.area}")
        marker = _MARKERS.get(c.status, "?")
        print(f"    {marker} {c.title}: {c.detail}")
        if c.action:
            print(f"        → {c.action}")
    print()


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
    """Entry point for the Ofsted Readiness CLI screen."""
    while True:
        try:
            _print_report()
        except Exception as e:  # noqa: BLE001
            logger.exception("Ofsted readiness report failed")
            print(f"\n  ✗ Could not build report: {e}")
            _pause()
            return
        print("   1) Export to CSV    0) Back")
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
    if label != "Ofsted Readiness":
        return False
    run()
    return True
