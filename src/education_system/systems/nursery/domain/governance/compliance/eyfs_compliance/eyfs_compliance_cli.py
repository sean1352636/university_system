"""CLI flow for EYFS Compliance (Nursery System).

Prints a read-only EYFS statutory-framework compliance checklist: an overall
score header (grade + counts) followed by the checks grouped by section with a
status marker, detail and recommended action. Offers a CSV export.
"""

from __future__ import annotations

import logging

from education_system.systems.nursery.domain.governance.compliance.eyfs_compliance import (
    eyfs_compliance as data,
)

logger = logging.getLogger(__name__)

_MARKERS = {"ok": "✓", "warning": "⚠", "fail": "✗", "info": "·"}


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_report() -> None:
    checks = data.compliance()
    s = data.score()
    print("\n═══ EYFS Compliance ═══")
    print(f"  Grade: {s['grade']}   ({s['pct']}% compliant)")
    print(f"  ✓ {s['ok']} ok   ⚠ {s['warning']} warning   "
          f"✗ {s['fail']} fail   · {s['info']} info   "
          f"(scored: {s['total']})")

    # Group by section in canonical order, then any extras.
    ordered = data.sections_in_order()
    seen = {c.section for c in checks}
    sections = ordered + [s for s in sorted(seen) if s not in ordered]
    for section in sections:
        rows = [c for c in checks if c.section == section]
        if not rows:
            continue
        print(f"\n  {section}")
        print("  " + "-" * 68)
        for c in rows:
            marker = _MARKERS.get(c.status, "?")
            print(f"   {marker} {c.title}")
            print(f"       {c.detail}")
            if c.action:
                print(f"       → {c.action}")


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
    """Entry point for the EYFS Compliance CLI screen."""
    while True:
        try:
            _print_report()
        except Exception as e:  # noqa: BLE001
            logger.exception("EYFS compliance report failed")
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
    if label != "EYFS Compliance":
        return False
    run()
    return True
